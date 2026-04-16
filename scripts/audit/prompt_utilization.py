#!/usr/bin/env python3
"""Prompt Utilization Auditor — Phase 3 evidence generator.

Consumes the existing per-episode context_relevance corpus
(`data/retrieval_quality/context_relevance.jsonl`) plus any available Phase 0
audit traces (`data/audit/traces/<date>/<id>.json`) and produces the
Phase-3 utilization history + rollups required by
`docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`.

Design:

- Upstream scoring already lives in `clarvis.cognition.context_relevance`
  (importance-weighted soft-containment per section).  We reuse that signal
  rather than re-implementing tokenization; this script is the *auditor*,
  not a second scorer.
- We classify each task into one of the five canonical Phase-3 task types
  via keyword + mmr_category heuristics (SWO_FEATURE, BUG_FIX,
  RESEARCH_DISTILLATION, MAINTENANCE, SELF_REFLECTION).
- For each section we compute proxy labels HELPFUL / NEUTRAL / MISLEADING /
  NOISE from per-section score + outcome co-variation.  Hand-labels are
  expected to supersede these when a 40-task labelled subsample lands
  (tracked as Phase-3 follow-up).
- Output: `data/audit/prompt_utilization_history.jsonl` (one row per
  scored episode) plus `data/audit/prompt_utilization_summary.json`
  (rollup the scorecard doc reads).

Gate thresholds mirror the plan:
  PASS   : utilization ≥ 0.45 AND MISLEADING share < 0.10
  REVISE : 0.25 ≤ utilization < 0.45 OR 0.10 ≤ MISLEADING < 0.25
  FAIL   : utilization < 0.25 OR MISLEADING ≥ 0.25

CLI:
  python3 scripts/audit/prompt_utilization.py run
  python3 scripts/audit/prompt_utilization.py summary
  python3 scripts/audit/prompt_utilization.py sample --n 40
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
RELEVANCE_FILE = WORKSPACE / "data" / "retrieval_quality" / "context_relevance.jsonl"
TRACES_DIR = WORKSPACE / "data" / "audit" / "traces"
HISTORY_FILE = WORKSPACE / "data" / "audit" / "prompt_utilization_history.jsonl"
SUMMARY_FILE = WORKSPACE / "data" / "audit" / "prompt_utilization_summary.json"

# Phase-3 canonical task types (plan §Phase 3).
TASK_TYPES = ["swo_feature", "bug_fix", "research_distillation", "maintenance", "self_reflection"]

_SWO_RX = re.compile(r"\bSWO[_\- ]|star[_\- ]?world[_\- ]?order", re.I)
_BUG_RX = re.compile(r"\b(?:fix|bug|race|regression|crash|broken|P0|leak|lock|retry|error[_\s]+classif)\b", re.I)
_RESEARCH_RX = re.compile(r"\b(?:research|paper|arxiv|survey|distill|brief\b.*(?:survey|paper)|literature|study)\b", re.I)
_REFLECTION_RX = re.compile(r"\b(?:phi|consciousness|self[_\- ]?model|reflection|dream|meta[_\- ]?cog|evolution\b|audit\b)\b", re.I)
# Phase-3 hand-label slots.
SECTION_LABELS = ("HELPFUL", "NEUTRAL", "MISLEADING", "NOISE")

# Utilization gate thresholds (mirror plan §Phase 3).
PASS_UTIL = 0.45
REVISE_UTIL = 0.25
PASS_MISLEADING = 0.10
REVISE_MISLEADING = 0.25

# A section counts as NOISE when its score is < NOISE_SCORE_CEILING AND
# the episode succeeded anyway (i.e., output did not need it).
NOISE_SCORE_CEILING = 0.06
# A section is flagged MISLEADING when it has HIGH score on a failed/crashed
# episode (model referenced it, outcome still bad) — proxy for anchoring.
MISLEADING_SCORE_FLOOR = 0.30
MISLEADING_BAD_OUTCOMES = {"failure", "crash", "timeout"}
# A section is HELPFUL when score ≥ HELPFUL_SCORE_FLOOR AND outcome is success.
HELPFUL_SCORE_FLOOR = 0.20
GOOD_OUTCOMES = {"success", "partial_success"}


def _classify_task_type(task: str, mmr_category: str = "") -> str:
    """Heuristic mapping to one of the five Phase-3 canonical task types."""
    t = task or ""
    if _SWO_RX.search(t):
        return "swo_feature"
    if _REFLECTION_RX.search(t):
        return "self_reflection"
    if _BUG_RX.search(t):
        return "bug_fix"
    if _RESEARCH_RX.search(t):
        return "research_distillation"
    if (mmr_category or "").lower() == "research":
        return "research_distillation"
    return "maintenance"


def _label_section(score: float, outcome: str) -> str:
    """Proxy label for a single section on a single episode."""
    if outcome in MISLEADING_BAD_OUTCOMES and score >= MISLEADING_SCORE_FLOOR:
        return "MISLEADING"
    if outcome in GOOD_OUTCOMES and score >= HELPFUL_SCORE_FLOOR:
        return "HELPFUL"
    if score < NOISE_SCORE_CEILING:
        return "NOISE"
    return "NEUTRAL"


def _load_corpus() -> list[dict]:
    if not RELEVANCE_FILE.exists():
        return []
    rows: list[dict] = []
    with RELEVANCE_FILE.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_traces_by_task() -> dict[str, str]:
    """Best-effort map from task-prefix -> audit_trace_id.

    Joins trace files by their top-of-task-text prefix so we can stamp
    existing corpus rows with the Phase-0 trace id when both cover the
    same task.  Returns {} when no traces exist yet.
    """
    if not TRACES_DIR.exists():
        return {}
    mapping: dict[str, str] = {}
    for day in sorted(TRACES_DIR.iterdir()):
        if not day.is_dir():
            continue
        for fn in day.glob("*.json"):
            try:
                data = json.loads(fn.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            task = (data.get("task") or {}).get("text") or ""
            tid = data.get("audit_trace_id") or fn.stem
            if task and tid:
                mapping[task[:120]] = tid
    return mapping


def _bucketize(rows: list[dict]) -> list[dict]:
    traces = _load_traces_by_task()
    history: list[dict] = []
    for r in rows:
        task = r.get("task") or ""
        outcome = r.get("outcome") or ""
        per_section: dict[str, float] = r.get("per_section") or {}
        task_type = _classify_task_type(task, r.get("mmr_category", ""))
        section_labels = {
            name: _label_section(float(score), outcome)
            for name, score in per_section.items()
        }
        label_counts = Counter(section_labels.values())
        misleading_share = (
            label_counts.get("MISLEADING", 0) / len(section_labels)
            if section_labels else 0.0
        )
        noise_share = (
            label_counts.get("NOISE", 0) / len(section_labels)
            if section_labels else 0.0
        )
        helpful_share = (
            label_counts.get("HELPFUL", 0) / len(section_labels)
            if section_labels else 0.0
        )
        row = {
            "ts": r.get("ts"),
            "task": task[:200],
            "task_type": task_type,
            "outcome": outcome,
            "mmr_category": r.get("mmr_category"),
            "overall": r.get("overall"),
            "sections_total": r.get("sections_total"),
            "sections_referenced": r.get("sections_referenced"),
            "noise_ratio_existing": r.get("noise_ratio"),
            "per_section": per_section,
            "section_labels": section_labels,
            "label_counts": dict(label_counts),
            "misleading_share": round(misleading_share, 4),
            "noise_share": round(noise_share, 4),
            "helpful_share": round(helpful_share, 4),
            "audit_trace_id": traces.get(task[:120]),
        }
        history.append(row)
    return history


def _apply_gate(mean_util: float, misleading_share: float) -> str:
    if mean_util >= PASS_UTIL and misleading_share < PASS_MISLEADING:
        return "PASS"
    if mean_util < REVISE_UTIL or misleading_share >= REVISE_MISLEADING:
        return "FAIL"
    return "REVISE"


def _summarize(history: list[dict]) -> dict:
    if not history:
        return {"error": "empty corpus"}
    utilizations = [h["overall"] for h in history if h.get("overall") is not None]
    overall_mean = statistics.fmean(utilizations) if utilizations else 0.0
    overall_median = statistics.median(utilizations) if utilizations else 0.0

    # Strictness-honest secondary measures:
    #   raw_ratio     = sections_referenced / sections_total (binary, ≥0.12 containment)
    #   raw_mean_score = unweighted mean of per-section soft-containment scores
    raw_ratios: list[float] = []
    raw_mean_scores: list[float] = []
    for h in history:
        tot = h.get("sections_total") or 0
        ref = h.get("sections_referenced") or 0
        if tot:
            raw_ratios.append(ref / tot)
        ps = h.get("per_section") or {}
        if ps:
            raw_mean_scores.append(statistics.fmean(ps.values()))

    # Per-task-type rollup
    by_type: dict[str, list[dict]] = defaultdict(list)
    for h in history:
        by_type[h["task_type"]].append(h)

    per_type: dict[str, dict] = {}
    for t, rows in by_type.items():
        utils = [r["overall"] for r in rows if r.get("overall") is not None]
        if not utils:
            continue
        misleading = [r["misleading_share"] for r in rows]
        noise = [r["noise_share"] for r in rows]
        helpful = [r["helpful_share"] for r in rows]
        per_type[t] = {
            "n": len(rows),
            "mean_utilization": round(statistics.fmean(utils), 4),
            "median_utilization": round(statistics.median(utils), 4),
            "mean_misleading_share": round(statistics.fmean(misleading), 4),
            "mean_noise_share": round(statistics.fmean(noise), 4),
            "mean_helpful_share": round(statistics.fmean(helpful), 4),
            "gate": _apply_gate(statistics.fmean(utils), statistics.fmean(misleading)),
        }

    # Per-section rollup across all rows
    section_scores: dict[str, list[float]] = defaultdict(list)
    section_label_counts: dict[str, Counter] = defaultdict(Counter)
    for h in history:
        for name, score in (h.get("per_section") or {}).items():
            section_scores[name].append(float(score))
            section_label_counts[name][h["section_labels"].get(name, "NEUTRAL")] += 1

    per_section: dict[str, dict] = {}
    for name, scores in section_scores.items():
        labels = section_label_counts[name]
        total = sum(labels.values())
        per_section[name] = {
            "n": len(scores),
            "mean_score": round(statistics.fmean(scores), 4),
            "median_score": round(statistics.median(scores), 4),
            "p90_score": round(sorted(scores)[int(0.9 * (len(scores) - 1))], 4),
            "label_share": {
                lab: round(labels[lab] / total, 4) for lab in SECTION_LABELS
            },
            "label_counts": dict(labels),
        }

    # Outcome correlation
    outcomes = Counter(h["outcome"] for h in history)

    mean_misleading = statistics.fmean(h["misleading_share"] for h in history)
    mean_noise = statistics.fmean(h["noise_share"] for h in history)
    mean_helpful = statistics.fmean(h["helpful_share"] for h in history)
    gate = _apply_gate(overall_mean, mean_misleading)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_episodes": len(history),
        "date_range": {
            "first": history[0].get("ts", "")[:10],
            "last": history[-1].get("ts", "")[:10],
        },
        "overall_utilization": {
            "mean": round(overall_mean, 4),
            "median": round(overall_median, 4),
        },
        "raw_utilization": {
            "sections_referenced_ratio_mean": round(statistics.fmean(raw_ratios), 4) if raw_ratios else None,
            "sections_referenced_ratio_median": round(statistics.median(raw_ratios), 4) if raw_ratios else None,
            "per_section_score_mean": round(statistics.fmean(raw_mean_scores), 4) if raw_mean_scores else None,
            "per_section_score_median": round(statistics.median(raw_mean_scores), 4) if raw_mean_scores else None,
        },
        "mean_misleading_share": round(mean_misleading, 4),
        "mean_noise_share": round(mean_noise, 4),
        "mean_helpful_share": round(mean_helpful, 4),
        "outcome_distribution": dict(outcomes),
        "per_task_type": per_type,
        "per_section": per_section,
        "gate": gate,
        "gate_thresholds": {
            "PASS_UTIL": PASS_UTIL,
            "REVISE_UTIL": REVISE_UTIL,
            "PASS_MISLEADING": PASS_MISLEADING,
            "REVISE_MISLEADING": REVISE_MISLEADING,
        },
        "proxy_limits": [
            "overall score is importance-weighted soft-containment, not literal token reuse",
            "MISLEADING/HELPFUL/NOISE labels are heuristic proxies pending 40-task hand-label",
            "audit_trace_id linkage available only from 2026-04-16; historic rows lack it",
            "Phase 0 gate not yet PASS (eval 2026-04-23) — trace-backed view supersedes this snapshot",
        ],
    }


def cmd_run(args: argparse.Namespace) -> int:
    rows = _load_corpus()
    if not rows:
        print(f"No corpus at {RELEVANCE_FILE}")
        return 1
    history = _bucketize(rows)
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w") as fh:
        for h in history:
            fh.write(json.dumps(h) + "\n")
    summary = _summarize(history)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {len(history)} rows -> {HISTORY_FILE}")
    print(f"Wrote summary -> {SUMMARY_FILE}")
    print(f"Gate: {summary['gate']}  "
          f"util={summary['overall_utilization']['mean']}  "
          f"misleading={summary['mean_misleading_share']}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    if not SUMMARY_FILE.exists():
        print("Run `prompt_utilization.py run` first.")
        return 1
    data = json.loads(SUMMARY_FILE.read_text())
    print(json.dumps(data, indent=2))
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    """Stratified sampler for the 40-task hand-label subsample.

    Emits a JSON template the labeller can fill in with HELPFUL / NEUTRAL
    / MISLEADING / NOISE per section.
    """
    if not HISTORY_FILE.exists():
        if cmd_run(args) != 0:
            return 1
    history = [json.loads(line) for line in HISTORY_FILE.read_text().splitlines() if line.strip()]
    n = max(1, args.n)
    # Stratified sample per task_type, preserving outcome mix.
    buckets: dict[str, list[dict]] = defaultdict(list)
    for h in history:
        buckets[h["task_type"]].append(h)
    picks: list[dict] = []
    quota = max(1, n // max(1, len(buckets)))
    for t, rows in buckets.items():
        # Prefer recent, varied-outcome episodes.
        rows_sorted = sorted(rows, key=lambda r: r.get("ts") or "", reverse=True)
        picks.extend(rows_sorted[:quota])
    picks = picks[:n]
    labels = [
        {
            "audit_trace_id": p.get("audit_trace_id"),
            "ts": p.get("ts"),
            "task": p.get("task"),
            "task_type": p.get("task_type"),
            "outcome": p.get("outcome"),
            "section_labels_proxy": p.get("section_labels"),
            "hand_labels": {
                s: "TBD" for s in (p.get("per_section") or {})
            },
        }
        for p in picks
    ]
    out_path = WORKSPACE / "data" / "audit" / "prompt_utilization_handlabel_template.json"
    out_path.write_text(json.dumps(labels, indent=2))
    print(f"Wrote hand-label template ({len(labels)} rows) -> {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-3 prompt utilization auditor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="Score corpus + write history + summary")
    p_run.set_defaults(func=cmd_run)
    p_sum = sub.add_parser("summary", help="Print latest summary JSON")
    p_sum.set_defaults(func=cmd_summary)
    p_sample = sub.add_parser("sample", help="Emit N-row hand-label template")
    p_sample.add_argument("--n", type=int, default=40)
    p_sample.set_defaults(func=cmd_sample)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

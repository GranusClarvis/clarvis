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
HANDLABEL_FILE = WORKSPACE / "data" / "audit" / "prompt_utilization_handlabel_template.json"
HANDLABEL_PROVENANCE = WORKSPACE / "data" / "audit" / "prompt_utilization_handlabel_provenance.json"

# Phase-3 canonical task types (plan §Phase 3).
TASK_TYPES = ["swo_feature", "bug_fix", "research_distillation", "maintenance", "self_reflection"]

# --- Tag-based classifier (Phase 3 upgrade) ---
# Structured prefix→type mapping extracted from QUEUE.md task naming conventions.
# Evaluated first; falls through to keyword regex only when no tag matches.
_TAG_RX = re.compile(r"^\*{0,2}\[([A-Z][A-Z0-9_:]+?)(?:\]|\s)")

_TAG_PREFIX_MAP: dict[str, str] = {
    "SWO": "swo_feature",
    "SANCTUARY": "swo_feature",
    "STAR": "swo_feature",

    "RESEARCH": "research_distillation",
    "WIKI": "research_distillation",
    "WIKI_QUERY_RETURN_SIGNATURE_FIX": "bug_fix",
    "WIKI_METADATA_SCHEMA_ALIGNMENT": "bug_fix",
    "LLM_BRAIN_REVIEW": "research_distillation",
    "BRIEF": "research_distillation",
    "LEARNING_STRATEGY": "research_distillation",

    "FIX": "bug_fix",
    "P0": "bug_fix",
    "CALIBRATION": "bug_fix",
    "HEARTBEAT_TASK_AWARE": "bug_fix",
    "BENCH_CLR_AB": "bug_fix",

    "PHI": "self_reflection",
    "GRAPH_CONSOLIDATION": "self_reflection",
    "DEAD_SCRIPT": "self_reflection",
    "DEAD_CODE": "self_reflection",
    "REASONING_CHAIN_QUALITY": "self_reflection",
    "CRON_TIMEOUT_AUDIT": "self_reflection",
    "OSS_HARDCODED": "self_reflection",
    "PHI_REACHABILITY": "self_reflection",
    "PHI_EMERGENCY": "self_reflection",
}

_SWO_RX = re.compile(r"\bSWO[_\- ]|star[_\- ]?world[_\- ]?order|\bsanctuary\b", re.I)
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
    """Classify task into one of five canonical Phase-3 types.

    Priority: (1) structured tag-prefix lookup, (2) keyword regex, (3) mmr_category, (4) default.
    """
    t = task or ""
    # --- Stage 1: tag-prefix lookup (most reliable) ---
    tag_m = _TAG_RX.match(t)
    if tag_m:
        tag = tag_m.group(1)
        # Try full tag first, then progressively shorter prefixes
        for candidate in [tag, *[tag.rsplit("_", i)[0] for i in range(1, tag.count("_") + 1)]]:
            if candidate in _TAG_PREFIX_MAP:
                return _TAG_PREFIX_MAP[candidate]
        # No prefix match — check if tag itself signals a bug fix
        if "FIX" in tag.split("_") or tag.endswith("_FIX"):
            return "bug_fix"
    # --- Stage 2: keyword regex fallback (original heuristic, same priority order) ---
    if _SWO_RX.search(t):
        return "swo_feature"
    if _REFLECTION_RX.search(t):
        return "self_reflection"
    if _BUG_RX.search(t):
        return "bug_fix"
    if _RESEARCH_RX.search(t):
        return "research_distillation"
    # --- Stage 3: mmr_category signal ---
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


def _load_hand_labels() -> dict[str, dict[str, str]]:
    """Load hand-labels keyed by task prefix (first 200 chars)."""
    if not HANDLABEL_FILE.exists():
        return {}
    try:
        rows = json.loads(HANDLABEL_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        task = (row.get("task") or "")[:200]
        labels = row.get("hand_labels") or {}
        if task and any(v not in ("TBD", "", None) for v in labels.values()):
            mapping[task] = {k: v for k, v in labels.items() if v not in ("TBD", "", None)}
    return mapping


def _bucketize(rows: list[dict], use_hand_labels: bool = False) -> list[dict]:
    traces = _load_traces_by_task()
    hand_labels = _load_hand_labels() if use_hand_labels else {}
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
        hl = hand_labels.get(task[:200], {})
        if hl:
            for name in section_labels:
                if name in hl and hl[name] in SECTION_LABELS:
                    section_labels[name] = hl[name]
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
    use_hl = getattr(args, "hand_labels", False)
    history = _bucketize(rows, use_hand_labels=use_hl)
    if use_hl:
        print("Hand-label override: ON")
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


def cmd_handlabel(args: argparse.Namespace) -> int:
    """Report on hand-label status and compare proxy vs hand labels."""
    if not HANDLABEL_FILE.exists():
        print(f"No hand-label file at {HANDLABEL_FILE}")
        return 1
    rows = json.loads(HANDLABEL_FILE.read_text())
    labeled = [r for r in rows if any(
        v not in ("TBD", "", None) for v in (r.get("hand_labels") or {}).values()
    )]
    total_sections = sum(len(r.get("hand_labels", {})) for r in rows)
    labeled_sections = sum(
        sum(1 for v in (r.get("hand_labels", {}).values()) if v not in ("TBD", "", None))
        for r in rows
    )
    print(f"Rows: {len(rows)} total, {len(labeled)} with labels")
    print(f"Sections: {labeled_sections}/{total_sections} labeled")

    if not labeled:
        print("No labels yet.")
        return 0

    proxy_agree = 0
    proxy_disagree = 0
    misleading_count = 0
    label_dist: Counter = Counter()
    for r in labeled:
        proxy = r.get("section_labels_proxy", {})
        hand = r.get("hand_labels", {})
        for sec, hl in hand.items():
            if hl in ("TBD", "", None):
                continue
            label_dist[hl] += 1
            if hl == "MISLEADING":
                misleading_count += 1
            pl = proxy.get(sec, "")
            if pl == hl:
                proxy_agree += 1
            else:
                proxy_disagree += 1

    total_compared = proxy_agree + proxy_disagree
    print(f"\nLabel distribution: {dict(label_dist)}")
    print(f"Proxy agreement: {proxy_agree}/{total_compared} ({proxy_agree/total_compared*100:.1f}%)" if total_compared else "")
    print(f"Proxy disagreement: {proxy_disagree}/{total_compared} ({proxy_disagree/total_compared*100:.1f}%)" if total_compared else "")
    print(f"MISLEADING count: {misleading_count}")
    if misleading_count >= 5:
        print("ALERT: >= 5 MISLEADING — scorecard re-ruling required")
    else:
        print(f"OK: {misleading_count} MISLEADING (< 5 threshold)")

    if HANDLABEL_PROVENANCE.exists():
        prov = json.loads(HANDLABEL_PROVENANCE.read_text())
        print(f"\nProvenance: {prov.get('method')} / {prov.get('model')} @ {prov.get('timestamp', '')[:19]}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate classifier accuracy against hand-label template task types."""
    if not HANDLABEL_FILE.exists():
        print(f"No hand-label file at {HANDLABEL_FILE}")
        return 1
    rows = json.loads(HANDLABEL_FILE.read_text())
    correct = 0
    wrong: list[tuple[str, str, str]] = []
    for r in rows:
        task = r.get("task", "")
        expected = r.get("task_type", "")
        predicted = _classify_task_type(task, r.get("mmr_category", ""))
        if predicted == expected:
            correct += 1
        else:
            wrong.append((task[:80], expected, predicted))
    total = len(rows)
    accuracy = correct / total if total else 0.0
    print(f"Classifier accuracy: {correct}/{total} ({accuracy:.1%})")
    print(f"Target: ≥ 85.0%  —  {'PASS' if accuracy >= 0.85 else 'FAIL'}")
    if wrong:
        print(f"\nDisagreements ({len(wrong)}):")
        for task_snip, expected, predicted in wrong:
            print(f"  expected={expected:25s}  predicted={predicted:25s}  task={task_snip}")
    return 0 if accuracy >= 0.85 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-3 prompt utilization auditor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="Score corpus + write history + summary")
    p_run.add_argument("--hand-labels", action="store_true",
                        help="Override proxy labels with hand-labels where available")
    p_run.set_defaults(func=cmd_run)
    p_sum = sub.add_parser("summary", help="Print latest summary JSON")
    p_sum.set_defaults(func=cmd_summary)
    p_sample = sub.add_parser("sample", help="Emit N-row hand-label template")
    p_sample.add_argument("--n", type=int, default=40)
    p_sample.set_defaults(func=cmd_sample)
    p_hl = sub.add_parser("handlabel", help="Report hand-label status + proxy comparison")
    p_hl.set_defaults(func=cmd_handlabel)
    p_val = sub.add_parser("validate", help="Validate classifier vs hand-label template")
    p_val.set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

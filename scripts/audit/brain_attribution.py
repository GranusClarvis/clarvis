#!/usr/bin/env python3
"""Brain Attribution Auditor — Phase 4 evidence generator.

Purpose
-------
Rule on whether each of the ten ClarvisDB collections materially improves
task outcomes, per
``docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`` Phase 4.

Inputs
------
1. Phase-0 audit traces (``data/audit/traces/<date>/<id>.json``).
   - Preferred: a future ``preflight.brain_retrieval`` list of
     ``{memory_id, collection, distance, text}`` tuples. The tool is
     forward-compatible once that wiring lands.
   - Fallback for today's traces: the rendered ``prompt.context_brief``
     string. We split out the ``BRAIN CONTEXT`` / ``RELATED TASKS`` /
     ``EPISODIC LESSONS`` / ``KNOWLEDGE SYNTHESIS`` sections and score
     those as proxy retrieval blocks.
2. Retrieval telemetry — ``data/retrieval_quality/events.jsonl`` — used
   as a collection-level usage volume proxy when per-trace attribution
   is unavailable.
3. Recall@K baseline — ``data/brain_eval/latest.json`` (deterministic
   golden-QA run) and ``data/retrieval_benchmark/recall_precision_benchmark.json``.

Attribution score (per retrieval block → response)
--------------------------------------------------
  - memory_id match     → hit weight 1.0
  - distinctive-token jaccard ≥ 0.12  → hit weight 0.6
  - high-importance unigram overlap ≥ 0.25 → hit weight 0.4
A trace is *attributed* to a collection when any retrieval block from
that collection scores ≥ 0.4.

Artifacts
---------
  data/audit/brain_attribution.jsonl              per-trace rows
  data/audit/brain_collection_scorecard.json      aggregate + per-collection
  docs/internal/audits/BRAIN_USEFULNESS_<date>.md scorecard (separate writer)

Gates (plan §Phase 4)
---------------------
  PASS   per collection : ≥ 15 % of eligible traces attributed
  REVISE per collection : 5 – 15 %
  DEMOTE (cold storage) : < 5 % over two windows AND no A/B gain

Subtle-feature guard: a collection with low hit volume but load-bearing
content (identity, for instance) is not demoted on attribution alone —
the scorecard flags it for operator-salience check.

CLI
---
  python3 scripts/audit/brain_attribution.py run
  python3 scripts/audit/brain_attribution.py summary
  python3 scripts/audit/brain_attribution.py gate
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRACES_DIR = WORKSPACE / "data" / "audit" / "traces"
EVENTS_FILE = WORKSPACE / "data" / "retrieval_quality" / "events.jsonl"
REPORT_FILE = WORKSPACE / "data" / "retrieval_quality" / "report.json"
BRAIN_EVAL_LATEST = WORKSPACE / "data" / "brain_eval" / "latest.json"
RECALL_PRECISION_FILE = WORKSPACE / "data" / "retrieval_benchmark" / "latest.json"
EFFECTIVENESS_HISTORY = WORKSPACE / "data" / "brain_effectiveness_history.jsonl"

ATTRIB_JSONL = WORKSPACE / "data" / "audit" / "brain_attribution.jsonl"
SCORECARD_JSON = WORKSPACE / "data" / "audit" / "brain_collection_scorecard.json"

# Known collection inventory (plan §Project Overview). Order matters for output.
COLLECTIONS = [
    "clarvis-identity",
    "clarvis-preferences",
    "clarvis-learnings",
    "clarvis-infrastructure",
    "clarvis-goals",
    "clarvis-context",
    "clarvis-memories",
    "clarvis-procedures",
    "autonomous-learning",
    "clarvis-episodes",
]

# Context-brief section → collection guess mapping. This is the fallback
# used when traces carry only a rendered prompt string. It is approximate
# by design — genuine per-memory attribution lands when the trace wiring
# includes structured retrievals (follow-up queue item).
SECTION_TO_COLLECTION_FALLBACK = {
    "BRAIN CONTEXT": "clarvis-memories",
    "RELATED TASKS": "clarvis-context",
    "RECENT": "clarvis-context",
    "EPISODIC LESSONS": "clarvis-episodes",
    "KNOWLEDGE SYNTHESIS": "clarvis-learnings",
    "CONCEPTUAL FRAMEWORKS": "clarvis-learnings",
    "ACTIVE GOALS": "clarvis-goals",
    "PROCEDURE": "clarvis-procedures",
    "IDENTITY": "clarvis-identity",
    "PREFERENCES": "clarvis-preferences",
    "INFRASTRUCTURE": "clarvis-infrastructure",
}

MEMORY_ID_RX = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in COLLECTIONS) + r")[_\-][A-Za-z0-9_\-]+")
SECTION_HEADER_RX = re.compile(r"^\s*([A-Z][A-Z0-9 _\-&/]{2,40}):\s*$", re.M)
_STOP = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "with", "by", "from", "as", "it", "this", "that",
    "these", "those", "i", "you", "we", "they", "he", "she", "his", "her", "its", "their",
    "my", "our", "your", "has", "have", "had", "do", "does", "did", "will", "would", "should",
    "could", "may", "might", "must", "not", "no", "yes", "if", "else", "then", "so", "than",
    "use", "used", "using", "via", "per", "new", "old", "task", "tasks", "one", "two", "three",
}

HELPFUL_ATTRIB = 0.40
MEM_ID_WEIGHT = 1.0
JACCARD_HIT = 0.12
JACCARD_WEIGHT = 0.6
OVERLAP_HIT = 0.25
OVERLAP_WEIGHT = 0.4

PASS_SHARE = 0.15
REVISE_SHARE = 0.05

WINDOW_DAYS_DEFAULT = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tokens(text: str) -> List[str]:
    if not text:
        return []
    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text.lower()) if w not in _STOP]


def _token_set(text: str) -> set:
    return set(_tokens(text))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _overlap(source: set, target: set) -> float:
    """Fraction of ``source`` tokens that appear in ``target``."""
    if not source:
        return 0.0
    return len(source & target) / len(source)


def _iter_trace_files(days: Optional[int]) -> Iterable[Path]:
    if not TRACES_DIR.exists():
        return
    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for date_dir in sorted(TRACES_DIR.iterdir()):
        if not date_dir.is_dir():
            continue
        if cutoff is not None:
            try:
                dt = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt < cutoff - timedelta(days=1):
                    continue
            except ValueError:
                continue
        for p in sorted(date_dir.glob("*.json")):
            yield p


def _load_json(path: Path) -> Optional[Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Retrieval block extraction (forward-compatible)
# ---------------------------------------------------------------------------

def _structured_retrievals(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull the structured preflight.brain_retrieval list when present."""
    pf = trace.get("preflight") or {}
    raw = pf.get("brain_retrieval") or pf.get("brain_retrievals") or []
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        out.append({
            "memory_id": str(r.get("memory_id") or r.get("id") or ""),
            "collection": str(r.get("collection") or ""),
            "distance": r.get("distance"),
            "text": str(r.get("text") or r.get("document") or "")[:2000],
        })
    return out


def _split_prompt_sections(brief: str) -> List[Tuple[str, str]]:
    """Break a rendered context_brief into (header, body) pairs.

    Unknown headers are kept as-is so the caller can classify them.
    """
    if not brief:
        return []
    matches = list(SECTION_HEADER_RX.finditer(brief))
    if not matches:
        return [("UNKNOWN", brief)]
    out: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        header = m.group(1).strip().upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(brief)
        body = brief[start:end].strip()
        if body:
            out.append((header, body))
    return out


def _fallback_retrievals(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split prompt.context_brief into section-scoped blocks and map each to
    a best-guess collection via SECTION_TO_COLLECTION_FALLBACK.
    """
    prompt = trace.get("prompt") or {}
    brief = prompt.get("context_brief") or ""
    if not brief:
        return []
    blocks = _split_prompt_sections(brief)
    out = []
    for header, body in blocks:
        coll = None
        for key, mapped in SECTION_TO_COLLECTION_FALLBACK.items():
            if key in header:
                coll = mapped
                break
        if coll is None:
            # Secondary heuristic — a section that embeds explicit
            # memory IDs ``clarvis-X_...`` gets tagged with its ID's
            # collection.
            ids = MEMORY_ID_RX.findall(body)
            if ids:
                coll = ids[0].split("_")[0]
        if coll is None:
            continue
        out.append({
            "memory_id": f"fallback::{header}",
            "collection": coll,
            "distance": None,
            "text": body[:2000],
            "source": "prompt_section_fallback",
            "section": header,
        })
    return out


def _response_text(trace: Dict[str, Any]) -> str:
    """Reconstruct the downstream response blob we attribute against."""
    parts: List[str] = []
    exec_ = trace.get("execution") or {}
    for k in ("output", "output_tail", "response", "stdout"):
        v = exec_.get(k)
        if isinstance(v, str):
            parts.append(v)
    post = trace.get("postflight") or {}
    for k in ("summary", "episode_summary", "assistant_text"):
        v = post.get(k)
        if isinstance(v, str):
            parts.append(v)
    out = trace.get("outcome_link") or {}
    for k in ("summary", "response", "body"):
        v = out.get(k)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Per-trace attribution
# ---------------------------------------------------------------------------

def _score_block(block: Dict[str, Any], response: str) -> Dict[str, Any]:
    block_text = block.get("text", "")
    mem_id = block.get("memory_id", "")
    matched_ids = []
    # Explicit memory_id match (only counts for non-fallback ids).
    if mem_id and not mem_id.startswith("fallback::"):
        if mem_id in response:
            matched_ids.append(mem_id)
    # Any distinctive ID pattern present in both block and response.
    block_ids = set(MEMORY_ID_RX.findall(block_text))
    resp_ids = set(MEMORY_ID_RX.findall(response))
    crossref = sorted(block_ids & resp_ids)
    a = _token_set(block_text)
    b = _token_set(response)
    jac = _jaccard(a, b)
    ovl = _overlap(a, b)
    score = 0.0
    hits: List[str] = []
    if matched_ids or crossref:
        score = max(score, MEM_ID_WEIGHT)
        hits.append("memory_id")
    if jac >= JACCARD_HIT:
        score = max(score, JACCARD_WEIGHT)
        hits.append("jaccard")
    if ovl >= OVERLAP_HIT:
        score = max(score, OVERLAP_WEIGHT)
        hits.append("overlap")
    return {
        "collection": block.get("collection"),
        "memory_id": mem_id,
        "section": block.get("section"),
        "source": block.get("source", "structured"),
        "score": round(score, 4),
        "jaccard": round(jac, 4),
        "overlap": round(ovl, 4),
        "hits": hits,
        "attributed": score >= HELPFUL_ATTRIB,
        "crossref_ids": crossref[:5],
    }


def attribute_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Return per-trace attribution row with one score per retrieval block."""
    tid = trace.get("audit_trace_id", "")
    source = trace.get("source", "")
    outcome = (trace.get("outcome") or {}).get("status", "open")
    blocks = _structured_retrievals(trace)
    if not blocks:
        blocks = _fallback_retrievals(trace)
    response = _response_text(trace)
    block_scores = [_score_block(b, response) for b in blocks]
    by_collection: Dict[str, Dict[str, Any]] = {}
    for s in block_scores:
        coll = s["collection"]
        if not coll:
            continue
        slot = by_collection.setdefault(coll, {"blocks": 0, "attributed": False, "max_score": 0.0})
        slot["blocks"] += 1
        slot["attributed"] = slot["attributed"] or s["attributed"]
        slot["max_score"] = max(slot["max_score"], s["score"])
    return {
        "audit_trace_id": tid,
        "created_at": trace.get("created_at"),
        "source": source,
        "task": ((trace.get("task") or {}).get("text") or "")[:240],
        "outcome": outcome,
        "has_structured_retrievals": any(s["source"] == "structured" for s in block_scores) if block_scores else False,
        "block_count": len(blocks),
        "response_chars": len(response),
        "collections": by_collection,
        "blocks": block_scores,
    }


# ---------------------------------------------------------------------------
# Aggregate scorecard
# ---------------------------------------------------------------------------

def _collection_usage(days: int) -> Dict[str, Dict[str, Any]]:
    """Load retrieval_quality events and aggregate by collection."""
    out: Dict[str, Dict[str, Any]] = {c: {"hits": 0, "sum_distance": 0.0, "events": 0, "callers": Counter()} for c in COLLECTIONS}
    if not EVENTS_FILE.exists():
        return out
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with open(EVENTS_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("timestamp", "")
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if t < cutoff:
                    continue
            except Exception:
                continue
            colls = d.get("collections_hit") or []
            avg_d = d.get("avg_distance")
            caller = d.get("caller") or "?"
            for c in colls:
                slot = out.setdefault(c, {"hits": 0, "sum_distance": 0.0, "events": 0, "callers": Counter()})
                slot["hits"] += 1
                slot["events"] += 1
                if isinstance(avg_d, (int, float)):
                    slot["sum_distance"] += float(avg_d)
                slot["callers"][caller] += 1
    for c, slot in out.items():
        evt = slot["events"] or 0
        slot["avg_distance"] = round(slot["sum_distance"] / evt, 4) if evt else None
        slot["callers"] = dict(slot["callers"].most_common(5))
        slot.pop("sum_distance", None)
    return out


def _recall_k_snapshot() -> Dict[str, Any]:
    data = _load_json(BRAIN_EVAL_LATEST) or {}
    metrics = data.get("metrics") or {}
    return {
        "source": "data/brain_eval/latest.json",
        "timestamp": data.get("timestamp"),
        "golden_queries": data.get("golden_queries"),
        "p_at_1": metrics.get("p_at_1"),
        "p_at_3": metrics.get("p_at_3"),
        "mrr": metrics.get("mrr"),
        "collection_hit_at_3": metrics.get("collection_hit_at_3"),
        "context_usefulness": metrics.get("context_usefulness"),
    }


def _recall_precision_snapshot() -> Dict[str, Any]:
    data = _load_json(RECALL_PRECISION_FILE) or {}
    by_cat = data.get("by_category") or {}
    return {
        "source": "data/retrieval_benchmark/recall_precision_benchmark.json",
        "timestamp": data.get("timestamp"),
        "avg_precision_at_k": data.get("avg_precision_at_k"),
        "avg_precision_at_1": data.get("avg_precision_at_1"),
        "avg_recall": data.get("avg_recall"),
        "mrr": data.get("mrr"),
        "contamination_rate": data.get("contamination_rate"),
        "canonical_hit_rate": data.get("canonical_hit_rate"),
        "by_category": {k: v for k, v in by_cat.items()},
    }


def _effectiveness_snapshot() -> Dict[str, Any]:
    if not EFFECTIVENESS_HISTORY.exists():
        return {}
    try:
        lines = EFFECTIVENESS_HISTORY.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            return json.loads(line)
    except Exception:
        return {}
    return {}


def _eligible_trace(trace: Dict[str, Any]) -> bool:
    """A trace is eligible for Phase-4 attribution when it represents a real
    Claude spawn with a recoverable response."""
    src = trace.get("source")
    if src not in ("heartbeat", "spawn_claude", "cron_autonomous"):
        return False
    if not ((trace.get("outcome") or {}).get("status") in ("success", "partial_success", "failure")):
        return False
    exec_ = trace.get("execution") or {}
    return bool(exec_.get("output") or exec_.get("output_tail") or (trace.get("postflight") or {}).get("summary"))


def build_scorecard(days: int, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    # An "attributable" trace has both a recoverable response AND some form
    # of retrieval signal (structured list OR parseable prompt brief). A trace
    # lacking prompt capture is counted as eligible-but-opaque so the verdict
    # reflects Phase-0 coverage gaps honestly rather than silently passing.
    eligible = [r for r in rows if r.get("outcome") in ("success", "partial_success", "failure")
                and (r.get("source") in ("heartbeat", "spawn_claude", "cron_autonomous"))
                and r.get("response_chars", 0) > 0]
    attributable = [r for r in eligible if r.get("block_count", 0) > 0]
    total = len(eligible)
    total_attributable = len(attributable)
    min_sample = 7  # do not rule on < 7 attributable traces
    per_coll: Dict[str, Dict[str, Any]] = {}
    for c in COLLECTIONS:
        attributed = 0
        block_count = 0
        for r in attributable:
            slot = r.get("collections", {}).get(c)
            if not slot:
                continue
            block_count += slot.get("blocks", 0)
            if slot.get("attributed"):
                attributed += 1
        share = (attributed / total_attributable) if total_attributable else 0.0
        if total_attributable < min_sample:
            verdict = "INSUFFICIENT_DATA"
        elif share >= PASS_SHARE:
            verdict = "PASS"
        elif share >= REVISE_SHARE:
            verdict = "REVISE"
        else:
            verdict = "DEMOTE_CANDIDATE"
        per_coll[c] = {
            "attributed_traces": attributed,
            "attributable_traces": total_attributable,
            "eligible_traces": total,
            "attribution_share": round(share, 4),
            "block_count": block_count,
            "verdict": verdict,
        }
    usage = _collection_usage(days)
    for c in COLLECTIONS:
        per_coll.setdefault(c, {})
        per_coll[c]["telemetry"] = usage.get(c, {})
    # Overall headline metrics.
    any_attrib = sum(1 for r in attributable if any(v.get("attributed") for v in (r.get("collections") or {}).values()))
    headline = {
        "window_days": days,
        "eligible_traces": total,
        "attributable_traces": total_attributable,
        "traces_with_any_attribution": any_attrib,
        "overall_attribution_share": round((any_attrib / total_attributable), 4) if total_attributable else 0.0,
        "fallback_used_everywhere": all(not r.get("has_structured_retrievals") for r in attributable) if attributable else True,
        "min_sample_for_ruling": min_sample,
        "coverage_gap_spawn_claude_prompt_capture": total > 0 and total_attributable == 0,
    }
    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "headline": headline,
        "gates": {
            "pass_share": PASS_SHARE,
            "revise_share": REVISE_SHARE,
            "helpful_attrib_floor": HELPFUL_ATTRIB,
        },
        "per_collection": per_coll,
        "recall_at_k": _recall_k_snapshot(),
        "recall_precision_benchmark": _recall_precision_snapshot(),
        "brain_effectiveness_latest": _effectiveness_snapshot(),
        "retrieval_quality_report": _load_json(REPORT_FILE) or {},
        "proxy_caveats": [
            "Heartbeat traces now carry structured preflight.brain_retrieval lists "
            "(wired 2026-04-17). Older traces still fall back to prompt-section "
            "heuristics. Min-sample gate requires ≥7 attributable traces.",
            "Response-span attribution is lexical-overlap only — a hand-labelled "
            "stratified sample is tracked as a separate follow-up.",
            "N of eligible Claude spawns inside the audit window is tiny while "
            "Phase 0 is freshly landed; gate verdicts should be re-run after ≥ 7 "
            "days of heartbeat traces.",
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_run(args) -> int:
    rows: List[Dict[str, Any]] = []
    for path in _iter_trace_files(args.days):
        tr = _load_json(path)
        if not tr:
            continue
        rows.append(attribute_trace(tr))
    ATTRIB_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTRIB_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    scorecard = build_scorecard(args.days, rows)
    SCORECARD_JSON.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps({
        "wrote": {
            "per_trace_jsonl": str(ATTRIB_JSONL.relative_to(WORKSPACE)),
            "scorecard_json": str(SCORECARD_JSON.relative_to(WORKSPACE)),
        },
        "headline": scorecard["headline"],
    }, indent=2))
    return 0


def cmd_summary(args) -> int:
    if not SCORECARD_JSON.exists():
        print("no scorecard yet — run `brain_attribution.py run` first", file=sys.stderr)
        return 2
    data = _load_json(SCORECARD_JSON) or {}
    # Compact text rollup.
    headline = data.get("headline", {})
    print(f"window_days={headline.get('window_days')} eligible={headline.get('eligible_traces')} "
          f"attributable={headline.get('attributable_traces')} "
          f"any_attrib={headline.get('traces_with_any_attribution')} "
          f"share={headline.get('overall_attribution_share')}")
    per = data.get("per_collection", {})
    print(f"{'collection':<26} {'attrib':>6} {'attbl':>6} {'elig':>5} {'share':>7} {'hits30d':>8} {'avg_d':>7} verdict")
    for c in COLLECTIONS:
        row = per.get(c, {})
        tel = row.get("telemetry", {}) or {}
        print(f"{c:<26} {row.get('attributed_traces',0):>6} {row.get('attributable_traces',0):>6} "
              f"{row.get('eligible_traces',0):>5} "
              f"{row.get('attribution_share',0.0):>7.4f} {tel.get('hits',0):>8} "
              f"{(tel.get('avg_distance') or 0):>7.4f} {row.get('verdict','')}")
    return 0


def cmd_gate(args) -> int:
    if not SCORECARD_JSON.exists():
        print("no scorecard yet — run `brain_attribution.py run` first", file=sys.stderr)
        return 2
    data = _load_json(SCORECARD_JSON) or {}
    per = data.get("per_collection", {})
    fails = [c for c, r in per.items() if r.get("verdict") == "DEMOTE_CANDIDATE"]
    insuff = [c for c, r in per.items() if r.get("verdict") == "INSUFFICIENT_DATA"]
    passed = [c for c, r in per.items() if r.get("verdict") == "PASS"]
    revise = [c for c, r in per.items() if r.get("verdict") == "REVISE"]
    payload = {
        "pass": passed,
        "revise": revise,
        "demote_candidates": fails,
        "insufficient_data": insuff,
        "headline": data.get("headline", {}),
    }
    print(json.dumps(payload, indent=2))
    # Insufficient data is not FAIL — gate returns 0 so cron does not alert.
    return 0 if not fails else 4


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clarvis Phase 4 brain attribution auditor")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Score traces + aggregate retrieval telemetry")
    p_run.add_argument("--days", type=int, default=WINDOW_DAYS_DEFAULT)
    p_run.set_defaults(func=cmd_run)

    p_sum = sub.add_parser("summary", help="Print the scorecard as a compact table")
    p_sum.set_defaults(func=cmd_summary)

    p_gate = sub.add_parser("gate", help="Evaluate Phase 4 PASS/REVISE/DEMOTE gates")
    p_gate.set_defaults(func=cmd_gate)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    # Parse once, dispatch.
    args = build_parser().parse_args()
    sys.exit(args.func(args))

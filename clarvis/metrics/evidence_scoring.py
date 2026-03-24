"""CLR Evidence Attribution Scoring — cross-adapter evidence support analysis.

Scores whether answers are backed by retrieved or gold evidence, and whether
cited/supporting spans actually contain the needed facts. Works across
LongMemEval, MemBench, and BEAM adapters.

Three scoring dimensions:
  1. Evidence Support — does the retrieved evidence contain gold answer facts?
  2. Span Coverage — what fraction of gold answer parts appear in evidence?
  3. Attribution Quality — is the evidence source the correct collection?

Usage:
    python3 -m clarvis.metrics.evidence_scoring          # Run from cached results
    python3 -m clarvis.metrics.evidence_scoring --live    # Run live evaluation
    python3 -m clarvis.metrics.evidence_scoring --json    # JSON output
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
EVIDENCE_FILE = os.path.join(DATA_DIR, "evidence_scoring_latest.json")


def _load_all_tasks() -> dict[str, dict]:
    """Load all task definitions from all adapters, keyed by task ID."""
    tasks = {}
    from clarvis.metrics.longmemeval import LONGMEMEVAL_TASKS
    for t in LONGMEMEVAL_TASKS:
        tasks[t["id"]] = {**t, "source": "longmemeval"}
    from clarvis.metrics.membench import MEMBENCH_TASKS
    for t in MEMBENCH_TASKS:
        tasks[t["id"]] = {
            **t,
            "source": "membench",
            "gold_answer": t.get("expected_substrings", []),
        }
    try:
        from clarvis.metrics.beam import BEAM_TASKS
        for t in BEAM_TASKS:
            tasks[t["id"]] = {**t, "source": "beam"}
    except ImportError:
        pass
    return tasks


def _load_live_results() -> dict[str, list[dict]]:
    """Load per-task retrieval results from latest benchmark files.

    Returns dict mapping task_id -> list of retrieval result dicts.
    """
    results = {}

    # LongMemEval
    lme_path = os.path.join(DATA_DIR, "longmemeval_latest.json")
    if os.path.exists(lme_path):
        with open(lme_path) as f:
            lme = json.load(f)
        for d in lme.get("details", []):
            results[d["id"]] = d

    # MemBench
    mb_path = os.path.join(DATA_DIR, "membench_latest.json")
    if os.path.exists(mb_path):
        with open(mb_path) as f:
            mb = json.load(f)
        for d in mb.get("details", []):
            results[d["id"]] = d

    # BEAM
    beam_path = os.path.join(DATA_DIR, "beam_latest.json")
    if os.path.exists(beam_path):
        with open(beam_path) as f:
            beam = json.load(f)
        for d in beam.get("details", []):
            results[d["id"]] = d

    return results


def score_evidence_support(task: dict, retrieval_results: list[dict]) -> dict:
    """Score a single task's evidence quality.

    Args:
        task: Task definition with gold_answer and gold_evidence.
        retrieval_results: List of retrieval result dicts with 'document' key.

    Returns:
        Dict with support, span_coverage, and attribution scores.
    """
    gold_answer = task.get("gold_answer", task.get("expected_substrings", []))
    gold_evidence = task.get("gold_evidence", "")
    target_collections = set(task.get("collections", []))

    # Skip abstention tasks
    if task.get("expect_abstain"):
        return {
            "support": 1.0,
            "span_coverage": 1.0,
            "attribution": 1.0,
            "abstain_task": True,
        }

    if not retrieval_results:
        return {
            "support": 0.0,
            "span_coverage": 0.0,
            "attribution": 0.0,
            "no_results": True,
        }

    # Concatenate all retrieved documents
    all_text = " ".join(
        r.get("document", "") for r in retrieval_results
    ).lower()

    # 1. Evidence Support: does evidence contain ANY gold answer part?
    if gold_answer:
        found = sum(1 for a in gold_answer if a.lower() in all_text)
        support = round(min(1.0, found / max(len(gold_answer), 1)), 3)
    else:
        support = 0.0

    # 2. Span Coverage: what fraction of gold answer parts appear?
    if gold_answer:
        span_coverage = round(found / len(gold_answer), 3)
    else:
        span_coverage = 0.0

    # 3. Attribution: did results come from expected collections?
    if target_collections:
        result_collections = {r.get("collection", "") for r in retrieval_results}
        overlap = result_collections & target_collections
        attribution = round(len(overlap) / len(target_collections), 3)
    else:
        attribution = 1.0  # No collection constraint

    return {
        "support": support,
        "span_coverage": span_coverage,
        "attribution": attribution,
    }


def run_evidence_scoring(live: bool = False) -> dict:
    """Run evidence attribution scoring across all adapters.

    Args:
        live: If True, run live brain queries. If False, use cached results
              (only hit/first_hit available, evidence scoring is approximate).

    Returns:
        Evidence scoring report with per-task, per-adapter, and per-ability
        breakdowns.
    """
    all_tasks = _load_all_tasks()
    cached_results = _load_live_results()

    if live:
        # Run live evaluation for full evidence detail
        return _run_live_evidence_scoring(all_tasks)

    # From cached results, compute approximate scores using gold evidence
    # as proxy (since we don't have the actual retrieved documents cached)
    per_task = {}
    by_adapter: dict[str, list[dict]] = defaultdict(list)
    by_ability: dict[str, list[dict]] = defaultdict(list)

    for task_id, task in all_tasks.items():
        cached = cached_results.get(task_id)
        if not cached:
            continue

        # For cached mode, use gold_evidence as proxy for "what perfect
        # evidence would score" and the hit flag as the actual retrieval signal
        hit = cached.get("hit", False)
        first_hit = cached.get("first_hit", False)

        gold_answer = task.get("gold_answer", task.get("expected_substrings", []))
        gold_evidence = task.get("gold_evidence", "")

        if task.get("expect_abstain"):
            score = {
                "support": 1.0 if hit else 0.0,
                "span_coverage": 1.0 if hit else 0.0,
                "attribution": 1.0,
                "hit": hit,
                "first_hit": first_hit,
            }
        elif hit and gold_evidence:
            # Evidence was found — check how much of gold_answer the gold_evidence covers
            gold_text = gold_evidence.lower()
            found = sum(1 for a in gold_answer if a.lower() in gold_text)
            score = {
                "support": 1.0,
                "span_coverage": round(found / len(gold_answer), 3) if gold_answer else 0.0,
                "attribution": 1.0 if first_hit else 0.5,
                "hit": True,
                "first_hit": first_hit,
            }
        else:
            score = {
                "support": 0.0,
                "span_coverage": 0.0,
                "attribution": 0.0,
                "hit": False,
                "first_hit": first_hit,
            }

        score["task_id"] = task_id
        score["source"] = task["source"]
        score["ability"] = task.get("ability", task.get("quadrant", ""))

        per_task[task_id] = score
        by_adapter[task["source"]].append(score)
        by_ability[score["ability"]].append(score)

    # Aggregate per adapter
    adapter_summary = {}
    for adapter, scores in by_adapter.items():
        n = len(scores)
        adapter_summary[adapter] = {
            "n": n,
            "avg_support": round(sum(s["support"] for s in scores) / n, 3),
            "avg_span_coverage": round(sum(s["span_coverage"] for s in scores) / n, 3),
            "avg_attribution": round(sum(s["attribution"] for s in scores) / n, 3),
            "full_support_rate": round(sum(1 for s in scores if s["support"] >= 1.0) / n, 3),
            "zero_support_rate": round(sum(1 for s in scores if s["support"] == 0.0) / n, 3),
        }

    # Aggregate per ability
    ability_summary = {}
    for ability, scores in by_ability.items():
        n = len(scores)
        ability_summary[ability] = {
            "n": n,
            "avg_support": round(sum(s["support"] for s in scores) / n, 3),
            "avg_span_coverage": round(sum(s["span_coverage"] for s in scores) / n, 3),
            "avg_attribution": round(sum(s["attribution"] for s in scores) / n, 3),
            "weak_tasks": [s["task_id"] for s in scores if s["support"] < 0.5],
        }

    # Overall
    all_scores = list(per_task.values())
    n_total = len(all_scores)
    if n_total > 0:
        overall = {
            "n": n_total,
            "avg_support": round(sum(s["support"] for s in all_scores) / n_total, 3),
            "avg_span_coverage": round(sum(s["span_coverage"] for s in all_scores) / n_total, 3),
            "avg_attribution": round(sum(s["attribution"] for s in all_scores) / n_total, 3),
        }
    else:
        overall = {"n": 0, "avg_support": 0.0, "avg_span_coverage": 0.0, "avg_attribution": 0.0}

    report = {
        "report": "evidence_attribution_scoring",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "cached",
        "overall": overall,
        "by_adapter": adapter_summary,
        "by_ability": ability_summary,
        "per_task": per_task,
    }

    return report


def _run_live_evidence_scoring(all_tasks: dict[str, dict]) -> dict:
    """Run live brain queries and score actual retrieved evidence."""
    import sys
    sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
    from brain import brain

    per_task = {}
    by_adapter: dict[str, list[dict]] = defaultdict(list)
    by_ability: dict[str, list[dict]] = defaultdict(list)

    for task_id, task in all_tasks.items():
        query = task.get("question", task.get("query", ""))
        if not query:
            continue

        results = brain.recall(query, n=5, caller="evidence_scoring")
        result_dicts = [{"document": r.get("document", ""),
                         "collection": r.get("collection", "")} for r in results]

        score = score_evidence_support(task, result_dicts)
        score["task_id"] = task_id
        score["source"] = task["source"]
        score["ability"] = task.get("ability", task.get("quadrant", ""))

        per_task[task_id] = score
        by_adapter[task["source"]].append(score)
        by_ability[score["ability"]].append(score)

    # Same aggregation as cached mode
    adapter_summary = {}
    for adapter, scores in by_adapter.items():
        n = len(scores)
        if n == 0:
            continue
        adapter_summary[adapter] = {
            "n": n,
            "avg_support": round(sum(s["support"] for s in scores) / n, 3),
            "avg_span_coverage": round(sum(s["span_coverage"] for s in scores) / n, 3),
            "avg_attribution": round(sum(s["attribution"] for s in scores) / n, 3),
            "full_support_rate": round(sum(1 for s in scores if s["support"] >= 1.0) / n, 3),
            "zero_support_rate": round(sum(1 for s in scores if s["support"] == 0.0) / n, 3),
        }

    ability_summary = {}
    for ability, scores in by_ability.items():
        n = len(scores)
        if n == 0:
            continue
        ability_summary[ability] = {
            "n": n,
            "avg_support": round(sum(s["support"] for s in scores) / n, 3),
            "avg_span_coverage": round(sum(s["span_coverage"] for s in scores) / n, 3),
            "avg_attribution": round(sum(s["attribution"] for s in scores) / n, 3),
            "weak_tasks": [s["task_id"] for s in scores if s["support"] < 0.5],
        }

    all_scores = list(per_task.values())
    n_total = len(all_scores)
    overall = {
        "n": n_total,
        "avg_support": round(sum(s["support"] for s in all_scores) / n_total, 3) if n_total else 0.0,
        "avg_span_coverage": round(sum(s["span_coverage"] for s in all_scores) / n_total, 3) if n_total else 0.0,
        "avg_attribution": round(sum(s["attribution"] for s in all_scores) / n_total, 3) if n_total else 0.0,
    }

    return {
        "report": "evidence_attribution_scoring",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "live",
        "overall": overall,
        "by_adapter": adapter_summary,
        "by_ability": ability_summary,
        "per_task": per_task,
    }


def save_report(report: dict):
    """Save evidence scoring report."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(EVIDENCE_FILE, "w") as f:
        json.dump(report, f, indent=2)


def format_report(report: dict) -> str:
    """Format evidence scoring report for terminal."""
    lines = ["=== CLR Evidence Attribution Scoring ===", ""]
    lines.append(f"  Mode: {report.get('mode', 'cached').upper()}")

    ov = report["overall"]
    lines.append(f"  Tasks scored: {ov['n']}")
    lines.append(f"  Avg Support:       {ov['avg_support']:.1%}")
    lines.append(f"  Avg Span Coverage: {ov['avg_span_coverage']:.1%}")
    lines.append(f"  Avg Attribution:   {ov['avg_attribution']:.1%}")
    lines.append("")

    # Per adapter
    lines.append(f"  {'Adapter':<15} {'N':>4} {'Support':>9} {'SpanCov':>9} {'Attrib':>9} {'Full%':>7} {'Zero%':>7}")
    lines.append(f"  {'─' * 65}")
    for adapter in sorted(report.get("by_adapter", {}).keys()):
        a = report["by_adapter"][adapter]
        lines.append(
            f"  {adapter:<15} {a['n']:>4} {a['avg_support']:>8.1%} "
            f"{a['avg_span_coverage']:>8.1%} {a['avg_attribution']:>8.1%} "
            f"{a.get('full_support_rate', 0):>6.1%} {a.get('zero_support_rate', 0):>6.1%}"
        )

    # Per ability (top weak ones)
    lines.append("")
    lines.append(f"  {'Ability':<20} {'N':>4} {'Support':>9} {'SpanCov':>9} {'Weak Tasks'}")
    lines.append(f"  {'─' * 65}")
    for ability in sorted(report.get("by_ability", {}).keys(),
                          key=lambda a: report["by_ability"][a]["avg_support"]):
        ab = report["by_ability"][ability]
        weak = ", ".join(ab.get("weak_tasks", [])[:4]) or "—"
        if len(ab.get("weak_tasks", [])) > 4:
            weak += f" (+{len(ab['weak_tasks']) - 4})"
        lines.append(
            f"  {ability:<20} {ab['n']:>4} {ab['avg_support']:>8.1%} "
            f"{ab['avg_span_coverage']:>8.1%}  {weak}"
        )

    lines.append("")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    import sys
    args = sys.argv[1:]
    live = "--live" in args
    json_output = "--json" in args

    report = run_evidence_scoring(live=live)
    save_report(report)

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()

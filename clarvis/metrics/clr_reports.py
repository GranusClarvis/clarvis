"""CLR-Benchmark robustness reports — length, domain, and degradation analysis.

Generates three report types from CLR-Benchmark task data:
  1. Score vs Context Length — effectiveness/P@1 bucketed by gold evidence length
  2. Score vs Domain — effectiveness/P@1 grouped by target collection (topic domain)
  3. Degradation Curves — oracle vs full-history gap per ability, difficulty, and domain

These reports are required before open-sourcing CLR-Benchmark so that results
are presented as robust multi-dimensional analysis, not a single-number dashboard.

Usage:
    python3 -m clarvis.metrics.clr_reports length    # Length report
    python3 -m clarvis.metrics.clr_reports domain    # Domain report
    python3 -m clarvis.metrics.clr_reports degrade   # Degradation curves
    python3 -m clarvis.metrics.clr_reports all       # All three reports
    python3 -m clarvis.metrics.clr_reports all --json # JSON output
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DATA_DIR = os.path.join(WORKSPACE, "data", "benchmarks")
REPORTS_FILE = os.path.join(DATA_DIR, "clr_robustness_report.json")

# ── Length buckets ────────────────────────────────────────────────────

LENGTH_BUCKETS = [
    ("short", 0, 60),       # ≤60 chars gold evidence
    ("medium", 61, 120),    # 61-120 chars
    ("long", 121, 200),     # 121-200 chars
    ("very_long", 201, 9999),  # >200 chars
]

# ── Domain taxonomy ───────────────────────────────────────────────────
# Maps collection names to broader domain categories.

COLLECTION_TO_DOMAIN = {
    "clarvis-infrastructure": "infrastructure",
    "clarvis-procedures": "procedures",
    "clarvis-learnings": "learnings",
    "clarvis-identity": "identity",
    "clarvis-preferences": "preferences",
    "clarvis-context": "context",
    "clarvis-goals": "goals",
    "clarvis-memories": "memories",
    "clarvis-episodes": "episodes",
    "autonomous-learning": "learnings",
}


def _get_length_bucket(evidence_len: int) -> str:
    """Map evidence character length to a bucket label."""
    for label, lo, hi in LENGTH_BUCKETS:
        if lo <= evidence_len <= hi:
            return label
    return "very_long"


def _get_all_tasks() -> list[dict]:
    """Load all benchmark tasks from LongMemEval + MemBench with metadata."""
    from clarvis.metrics.longmemeval import LONGMEMEVAL_TASKS
    from clarvis.metrics.membench import MEMBENCH_TASKS

    tasks = []
    for t in LONGMEMEVAL_TASKS:
        gold = t.get("gold_evidence") or ""
        tasks.append({
            "id": t["id"],
            "source": "longmemeval",
            "ability": t.get("ability", ""),
            "difficulty": t.get("difficulty", "medium"),
            "collections": t.get("collections", []),
            "gold_evidence_len": len(gold),
            "length_bucket": _get_length_bucket(len(gold)),
            "domains": list({COLLECTION_TO_DOMAIN.get(c, c) for c in t.get("collections", [])}),
            "expect_abstain": t.get("expect_abstain", False),
        })
    for t in MEMBENCH_TASKS:
        gold = t.get("gold_evidence") or ""
        tasks.append({
            "id": t["id"],
            "source": "membench",
            "quadrant": t.get("quadrant", ""),
            "difficulty": "medium",  # MemBench doesn't tag difficulty
            "collections": t.get("collections", []),
            "gold_evidence_len": len(gold),
            "length_bucket": _get_length_bucket(len(gold)),
            "domains": list({COLLECTION_TO_DOMAIN.get(c, c) for c in t.get("collections", [])}),
            "temporal_hint": t.get("temporal_hint", "mid"),
        })
    return tasks


def _load_details_from_latest() -> dict[str, dict]:
    """Load per-task detail results from latest benchmark files.

    Returns dict mapping task_id -> {hit, first_hit, latency_ms, ...}.
    """
    details = {}

    lme_path = os.path.join(DATA_DIR, "longmemeval_latest.json")
    if os.path.exists(lme_path):
        with open(lme_path) as f:
            lme = json.load(f)
        for d in lme.get("details", []):
            details[d["id"]] = d

    mb_path = os.path.join(DATA_DIR, "membench_latest.json")
    if os.path.exists(mb_path):
        with open(mb_path) as f:
            mb = json.load(f)
        for d in mb.get("details", []):
            details[d["id"]] = d

    return details


def _bucket_stats(items: list[dict]) -> dict:
    """Compute effectiveness and P@1 for a group of task results."""
    if not items:
        return {"n": 0, "effectiveness": 0.0, "precision_at_1": 0.0,
                "avg_latency_ms": 0.0}
    n = len(items)
    hits = sum(1 for i in items if i.get("hit", False))
    first_hits = sum(1 for i in items if i.get("first_hit", False))
    latencies = [i.get("latency_ms", 0) for i in items if i.get("latency_ms")]
    return {
        "n": n,
        "effectiveness": round(hits / n, 3),
        "precision_at_1": round(first_hits / n, 3),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    }


# ── Report 1: Score vs Context Length ─────────────────────────────────

def report_score_vs_length(tasks: list[dict] | None = None,
                           details: dict[str, dict] | None = None) -> dict:
    """Score breakdown by gold evidence context length.

    Groups tasks into length buckets and computes effectiveness/P@1 per bucket.
    Reveals whether longer evidence contexts degrade retrieval quality.
    """
    if tasks is None:
        tasks = _get_all_tasks()
    if details is None:
        details = _load_details_from_latest()

    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        d = details.get(t["id"])
        if d:
            entry = {**d, "gold_evidence_len": t["gold_evidence_len"]}
            by_bucket[t["length_bucket"]].append(entry)

    buckets = {}
    for label, lo, hi in LENGTH_BUCKETS:
        items = by_bucket.get(label, [])
        stats = _bucket_stats(items)
        stats["range"] = f"{lo}-{hi}" if hi < 9999 else f"{lo}+"
        stats["task_ids"] = [i["id"] for i in items]
        buckets[label] = stats

    # Trend: does effectiveness decrease with length?
    ordered = [(label, buckets[label]) for label, _, _ in LENGTH_BUCKETS
               if buckets[label]["n"] > 0]
    if len(ordered) >= 2:
        first_eff = ordered[0][1]["effectiveness"]
        last_eff = ordered[-1][1]["effectiveness"]
        degradation = round(first_eff - last_eff, 3)
    else:
        degradation = 0.0

    return {
        "report": "score_vs_length",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tasks": sum(b["n"] for b in buckets.values()),
        "buckets": buckets,
        "length_degradation": degradation,
        "diagnosis": (
            f"Short→long effectiveness delta: {degradation:+.3f}. "
            + ("Significant degradation with context length."
               if degradation > 0.15
               else "Moderate length sensitivity."
               if degradation > 0.05
               else "Robust across context lengths.")
        ),
    }


# ── Report 2: Score vs Domain ─────────────────────────────────────────

def report_score_vs_domain(tasks: list[dict] | None = None,
                           details: dict[str, dict] | None = None) -> dict:
    """Score breakdown by topical domain (collection category).

    Each task may map to multiple domains. Reveals which knowledge areas
    have stronger/weaker retrieval.
    """
    if tasks is None:
        tasks = _get_all_tasks()
    if details is None:
        details = _load_details_from_latest()

    by_domain: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        d = details.get(t["id"])
        if not d:
            continue
        for domain in t["domains"]:
            by_domain[domain].append({**d, "task_meta": t})

    domains = {}
    for domain in sorted(by_domain.keys()):
        items = by_domain[domain]
        stats = _bucket_stats(items)
        stats["task_ids"] = list({i["id"] for i in items})
        stats["failures"] = [i["id"] for i in items if not i.get("hit", False)]
        domains[domain] = stats

    # Find strongest/weakest
    scored = [(d, s) for d, s in domains.items() if s["n"] >= 2]
    if scored:
        best = max(scored, key=lambda x: x[1]["effectiveness"])
        worst = min(scored, key=lambda x: x[1]["effectiveness"])
        spread = round(best[1]["effectiveness"] - worst[1]["effectiveness"], 3)
    else:
        best = worst = ("n/a", {"effectiveness": 0})
        spread = 0.0

    return {
        "report": "score_vs_domain",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tasks": len(details),
        "domains": domains,
        "best_domain": {"name": best[0], "effectiveness": best[1]["effectiveness"]},
        "worst_domain": {"name": worst[0], "effectiveness": worst[1]["effectiveness"]},
        "domain_spread": spread,
        "diagnosis": (
            f"Best: {best[0]} ({best[1]['effectiveness']:.1%}), "
            f"Worst: {worst[0]} ({worst[1]['effectiveness']:.1%}), "
            f"Spread: {spread:.3f}. "
            + ("High domain variance — some knowledge areas significantly weaker."
               if spread > 0.3
               else "Moderate domain variance."
               if spread > 0.15
               else "Consistent across domains.")
        ),
    }


# ── Report 3: Degradation Curves ─────────────────────────────────────

def report_degradation_curves(tasks: list[dict] | None = None) -> dict:
    """Oracle vs full-history degradation analysis.

    Runs both modes and computes per-dimension gaps:
    - Per ability (LongMemEval)
    - Per difficulty level
    - Per domain
    - Per temporal hint (MemBench)

    The gap quantifies how much retrieval quality costs vs perfect evidence.
    """
    if tasks is None:
        tasks = _get_all_tasks()

    # Run both modes
    from clarvis.metrics.longmemeval import run_longmemeval
    from clarvis.metrics.membench import run_membench

    # Full-history mode
    lme_normal = run_longmemeval(oracle=False)
    mb_normal = run_membench(oracle=False)

    # Oracle mode
    lme_oracle = run_longmemeval(oracle=True)
    mb_oracle = run_membench(oracle=True)

    # Build detail lookups
    normal_details = {}
    for d in lme_normal.get("details", []):
        normal_details[d["id"]] = d
    for d in mb_normal.get("details", []):
        normal_details[d["id"]] = d

    oracle_details = {}
    for d in lme_oracle.get("details", []):
        oracle_details[d["id"]] = d
    for d in mb_oracle.get("details", []):
        oracle_details[d["id"]] = d

    # ── Per-ability gap (LongMemEval) ──
    ability_curves = {}
    for ab, data in lme_normal.get("by_ability", {}).items():
        o_data = lme_oracle.get("by_ability", {}).get(ab, {})
        ability_curves[ab] = {
            "normal_eff": data.get("effectiveness", 0.0),
            "oracle_eff": o_data.get("effectiveness", 0.0),
            "gap": round(o_data.get("effectiveness", 0.0) - data.get("effectiveness", 0.0), 3),
            "normal_p1": data.get("precision_at_1", 0.0),
            "oracle_p1": o_data.get("precision_at_1", 0.0),
            "p1_gap": round(o_data.get("precision_at_1", 0.0) - data.get("precision_at_1", 0.0), 3),
        }

    # ── Per-difficulty gap ──
    difficulty_curves = {}
    for diff in ["easy", "medium", "hard"]:
        diff_tasks = [t for t in tasks if t.get("difficulty") == diff and t["source"] == "longmemeval"]
        if not diff_tasks:
            continue
        n_items = [normal_details.get(t["id"]) for t in diff_tasks if t["id"] in normal_details]
        o_items = [oracle_details.get(t["id"]) for t in diff_tasks if t["id"] in oracle_details]
        n_stats = _bucket_stats([i for i in n_items if i])
        o_stats = _bucket_stats([i for i in o_items if i])
        difficulty_curves[diff] = {
            "n": n_stats["n"],
            "normal_eff": n_stats["effectiveness"],
            "oracle_eff": o_stats["effectiveness"],
            "gap": round(o_stats["effectiveness"] - n_stats["effectiveness"], 3),
        }

    # ── Per-domain gap ──
    domain_curves = {}
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        for domain in t["domains"]:
            by_domain[domain].append(t)

    for domain, dtasks in by_domain.items():
        n_items = [normal_details.get(t["id"]) for t in dtasks if t["id"] in normal_details]
        o_items = [oracle_details.get(t["id"]) for t in dtasks if t["id"] in oracle_details]
        n_stats = _bucket_stats([i for i in n_items if i])
        o_stats = _bucket_stats([i for i in o_items if i])
        if n_stats["n"] >= 2:
            domain_curves[domain] = {
                "n": n_stats["n"],
                "normal_eff": n_stats["effectiveness"],
                "oracle_eff": o_stats["effectiveness"],
                "gap": round(o_stats["effectiveness"] - n_stats["effectiveness"], 3),
            }

    # ── Per-temporal-hint gap (MemBench) ──
    temporal_curves = {}
    for hint in ["early", "mid", "recent"]:
        hint_tasks = [t for t in tasks if t.get("temporal_hint") == hint and t["source"] == "membench"]
        if not hint_tasks:
            continue
        n_items = [normal_details.get(t["id"]) for t in hint_tasks if t["id"] in normal_details]
        o_items = [oracle_details.get(t["id"]) for t in hint_tasks if t["id"] in oracle_details]
        n_stats = _bucket_stats([i for i in n_items if i])
        o_stats = _bucket_stats([i for i in o_items if i])
        temporal_curves[hint] = {
            "n": n_stats["n"],
            "normal_eff": n_stats["effectiveness"],
            "oracle_eff": o_stats["effectiveness"],
            "gap": round(o_stats["effectiveness"] - n_stats["effectiveness"], 3),
        }

    # Aggregate
    agg_normal_eff = lme_normal["aggregate_effectiveness"]
    agg_oracle_eff = lme_oracle["aggregate_effectiveness"]
    overall_gap = round(agg_oracle_eff - agg_normal_eff, 3)

    # Worst gaps
    worst_ability = max(ability_curves.items(), key=lambda x: x[1]["gap"]) if ability_curves else ("n/a", {"gap": 0})
    worst_domain = max(domain_curves.items(), key=lambda x: x[1]["gap"]) if domain_curves else ("n/a", {"gap": 0})

    return {
        "report": "degradation_curves",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "normal_effectiveness": agg_normal_eff,
            "oracle_effectiveness": agg_oracle_eff,
            "retrieval_gap": overall_gap,
        },
        "by_ability": ability_curves,
        "by_difficulty": difficulty_curves,
        "by_domain": domain_curves,
        "by_temporal_hint": temporal_curves,
        "worst_ability_gap": {"ability": worst_ability[0], "gap": worst_ability[1]["gap"]},
        "worst_domain_gap": {"domain": worst_domain[0], "gap": worst_domain[1]["gap"]},
        "diagnosis": (
            f"Overall retrieval gap: {overall_gap:+.3f}. "
            f"Worst ability: {worst_ability[0]} (gap={worst_ability[1]['gap']:+.3f}). "
            f"Worst domain: {worst_domain[0]} (gap={worst_domain[1]['gap']:+.3f}). "
            + ("Retrieval is the primary bottleneck."
               if overall_gap > 0.15
               else "Moderate retrieval impact."
               if overall_gap > 0.05
               else "Retrieval quality is strong.")
        ),
    }


# ── Combined report ───────────────────────────────────────────────────

def generate_full_robustness_report(run_degradation: bool = True) -> dict:
    """Generate all three robustness reports.

    Args:
        run_degradation: If True, run oracle comparison (slower, ~2 brain queries
            per task). If False, only generate length and domain reports from
            cached latest results.
    """
    tasks = _get_all_tasks()
    details = _load_details_from_latest()

    report = {
        "report": "clr_robustness",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "length": report_score_vs_length(tasks, details),
        "domain": report_score_vs_domain(tasks, details),
    }

    if run_degradation:
        report["degradation"] = report_degradation_curves(tasks)
    else:
        report["degradation"] = {"skipped": True, "reason": "run_degradation=False"}

    return report


def save_robustness_report(report: dict):
    """Save robustness report to file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORTS_FILE, "w") as f:
        json.dump(report, f, indent=2)


# ── Terminal formatting ───────────────────────────────────────────────

def format_length_report(report: dict) -> str:
    """Format score-vs-length report for terminal."""
    lines = ["=== CLR Robustness: Score vs Context Length ===", ""]
    lines.append(f"  Total tasks: {report['total_tasks']}")
    lines.append("")
    lines.append(f"  {'Bucket':<12} {'Range':<10} {'N':>4} {'Eff':>7} {'P@1':>7} {'Lat(ms)':>9}")
    lines.append(f"  {'─' * 55}")

    for label, _, _ in LENGTH_BUCKETS:
        b = report["buckets"].get(label, {})
        if b.get("n", 0) == 0:
            continue
        lines.append(
            f"  {label:<12} {b['range']:<10} {b['n']:>4} "
            f"{b['effectiveness']:>6.1%} {b['precision_at_1']:>6.1%} "
            f"{b['avg_latency_ms']:>9.0f}"
        )

    lines.append("")
    lines.append(f"  Degradation (short→long): {report['length_degradation']:+.3f}")
    lines.append(f"  {report['diagnosis']}")
    lines.append("")
    return "\n".join(lines)


def format_domain_report(report: dict) -> str:
    """Format score-vs-domain report for terminal."""
    lines = ["=== CLR Robustness: Score vs Domain ===", ""]
    lines.append(f"  Total tasks: {report['total_tasks']}")
    lines.append("")
    lines.append(f"  {'Domain':<18} {'N':>4} {'Eff':>7} {'P@1':>7} {'Failures':>10}")
    lines.append(f"  {'─' * 50}")

    for domain in sorted(report["domains"].keys(),
                         key=lambda d: report["domains"][d]["effectiveness"],
                         reverse=True):
        d = report["domains"][domain]
        fails = len(d.get("failures", []))
        lines.append(
            f"  {domain:<18} {d['n']:>4} {d['effectiveness']:>6.1%} "
            f"{d['precision_at_1']:>6.1%} {fails:>10}"
        )

    lines.append("")
    b = report["best_domain"]
    w = report["worst_domain"]
    lines.append(f"  Best:  {b['name']} ({b['effectiveness']:.1%})")
    lines.append(f"  Worst: {w['name']} ({w['effectiveness']:.1%})")
    lines.append(f"  Spread: {report['domain_spread']:.3f}")
    lines.append(f"  {report['diagnosis']}")
    lines.append("")
    return "\n".join(lines)


def format_degradation_report(report: dict) -> str:
    """Format degradation curves report for terminal."""
    if report.get("skipped"):
        return "=== Degradation Curves: SKIPPED ===\n"

    lines = ["=== CLR Robustness: Degradation Curves (Oracle vs Full-History) ===", ""]

    ov = report["overall"]
    lines.append(f"  Overall: normal={ov['normal_effectiveness']:.1%} "
                 f"oracle={ov['oracle_effectiveness']:.1%} "
                 f"gap={ov['retrieval_gap']:+.3f}")
    lines.append("")

    # By ability
    lines.append(f"  {'Ability':<8} {'Normal':>8} {'Oracle':>8} {'Gap':>8} {'P@1 Gap':>9}")
    lines.append(f"  {'─' * 45}")
    for ab, curve in report.get("by_ability", {}).items():
        lines.append(
            f"  {ab:<8} {curve['normal_eff']:>7.1%} {curve['oracle_eff']:>7.1%} "
            f"{curve['gap']:>+7.3f} {curve['p1_gap']:>+8.3f}"
        )

    # By difficulty
    lines.append("")
    lines.append(f"  {'Difficulty':<10} {'N':>4} {'Normal':>8} {'Oracle':>8} {'Gap':>8}")
    lines.append(f"  {'─' * 42}")
    for diff in ["easy", "medium", "hard"]:
        curve = report.get("by_difficulty", {}).get(diff)
        if curve:
            lines.append(
                f"  {diff:<10} {curve['n']:>4} {curve['normal_eff']:>7.1%} "
                f"{curve['oracle_eff']:>7.1%} {curve['gap']:>+7.3f}"
            )

    # By domain
    lines.append("")
    lines.append(f"  {'Domain':<18} {'N':>4} {'Normal':>8} {'Oracle':>8} {'Gap':>8}")
    lines.append(f"  {'─' * 50}")
    for domain in sorted(report.get("by_domain", {}).keys(),
                         key=lambda d: report["by_domain"][d]["gap"],
                         reverse=True):
        curve = report["by_domain"][domain]
        lines.append(
            f"  {domain:<18} {curve['n']:>4} {curve['normal_eff']:>7.1%} "
            f"{curve['oracle_eff']:>7.1%} {curve['gap']:>+7.3f}"
        )

    # By temporal hint
    th = report.get("by_temporal_hint", {})
    if th:
        lines.append("")
        lines.append(f"  {'Temporal':<10} {'N':>4} {'Normal':>8} {'Oracle':>8} {'Gap':>8}")
        lines.append(f"  {'─' * 42}")
        for hint in ["early", "mid", "recent"]:
            curve = th.get(hint)
            if curve:
                lines.append(
                    f"  {hint:<10} {curve['n']:>4} {curve['normal_eff']:>7.1%} "
                    f"{curve['oracle_eff']:>7.1%} {curve['gap']:>+7.3f}"
                )

    lines.append("")
    wa = report.get("worst_ability_gap", {})
    wd = report.get("worst_domain_gap", {})
    lines.append(f"  Worst ability gap: {wa.get('ability', 'n/a')} ({wa.get('gap', 0):+.3f})")
    lines.append(f"  Worst domain gap:  {wd.get('domain', 'n/a')} ({wd.get('gap', 0):+.3f})")
    lines.append(f"  {report['diagnosis']}")
    lines.append("")
    return "\n".join(lines)


def format_full_report(report: dict) -> str:
    """Format complete robustness report for terminal."""
    parts = [
        format_length_report(report["length"]),
        format_domain_report(report["domain"]),
        format_degradation_report(report["degradation"]),
    ]
    return "\n".join(parts)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    import sys

    args = sys.argv[1:]
    cmd = args[0] if args else "all"
    json_output = "--json" in args

    if cmd == "length":
        report = report_score_vs_length()
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            print(format_length_report(report))

    elif cmd == "domain":
        report = report_score_vs_domain()
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            print(format_domain_report(report))

    elif cmd == "degrade":
        report = report_degradation_curves()
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            print(format_degradation_report(report))

    elif cmd in ("all", "full"):
        run_deg = "--no-degrade" not in args
        report = generate_full_robustness_report(run_degradation=run_deg)
        save_robustness_report(report)
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            print(format_full_report(report))
        print(f"Saved to {REPORTS_FILE}")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: clr_reports.py [length|domain|degrade|all] [--json] [--no-degrade]")
        sys.exit(1)


if __name__ == "__main__":
    main()

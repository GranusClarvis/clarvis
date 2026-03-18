#!/usr/bin/env python3
"""
Retrieval Quality Report — Unified visibility into brain retrieval health.

Combines data from:
  - data/performance_metrics.json (PI benchmark: hit_rate, precision@3, context_relevance)
  - data/retrieval_quality/report.json (per-caller recall stats, CRAG verdicts)
  - data/retrieval_quality/context_relevance.jsonl (per-section relevance over time)
  - data/clr_benchmark.json (CLR retrieval dimension)

Outputs:
  - Markdown report to stdout (or file with --out)
  - JSON summary to stdout with --json

Usage:
    python3 scripts/retrieval_quality_report.py          # Markdown to stdout
    python3 scripts/retrieval_quality_report.py --json    # JSON summary
    python3 scripts/retrieval_quality_report.py --out data/retrieval_quality/dashboard.md
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
PERF_FILE = os.path.join(WORKSPACE, "data", "performance_metrics.json")
RECALL_REPORT = os.path.join(WORKSPACE, "data", "retrieval_quality", "report.json")
RELEVANCE_FILE = os.path.join(WORKSPACE, "data", "retrieval_quality", "context_relevance.jsonl")
CLR_FILE = os.path.join(WORKSPACE, "data", "clr_benchmark.json")


def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_jsonl(path: str, max_lines: int = 200) -> list[dict]:
    lines = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return lines[-max_lines:]


def _status_icon(value: float, target: float, higher_better: bool = True) -> str:
    if value is None:
        return "-- "
    if higher_better:
        return "OK " if value >= target else "FAIL"
    else:
        return "OK " if value <= target else "FAIL"


def build_report() -> dict:
    """Build unified retrieval quality report from all data sources."""
    perf = _load_json(PERF_FILE)
    recall = _load_json(RECALL_REPORT)
    clr = _load_json(CLR_FILE)
    relevance_events = _load_jsonl(RELEVANCE_FILE)

    metrics = perf.get("metrics", {})
    details = perf.get("details", {})
    retrieval = details.get("retrieval", {})

    # --- Core metrics ---
    hit_rate = metrics.get("retrieval_hit_rate")
    precision3 = metrics.get("retrieval_precision3")
    context_rel = metrics.get("context_relevance")
    query_avg = metrics.get("brain_query_avg_ms")
    query_p95 = metrics.get("brain_query_p95_ms")

    # --- Per-collection precision ---
    cat_scores = retrieval.get("category_scores", {})

    # --- CLR retrieval dimension ---
    clr_dims = clr.get("dimensions", {})
    clr_retrieval = clr_dims.get("retrieval_precision", clr_dims.get("retrieval", {}))
    clr_score = clr_retrieval.get("score") if isinstance(clr_retrieval, dict) else None

    # --- Per-caller stats from recall report ---
    by_caller = recall.get("by_caller", {})
    total_events = recall.get("total_events", 0)
    rated_events = recall.get("rated_events", 0)

    # --- Context relevance trend ---
    section_means = defaultdict(list)
    overall_scores = []
    for evt in relevance_events:
        overall = evt.get("overall")
        if overall is not None:
            overall_scores.append(overall)
        for section, score in evt.get("per_section", {}).items():
            section_means[section].append(score)

    section_avg = {
        s: sum(v) / len(v)
        for s, v in section_means.items()
        if v
    }
    # Sort worst-first
    section_avg_sorted = sorted(section_avg.items(), key=lambda x: x[1])

    # Recent trend (last 10 vs previous 10)
    recent_trend = None
    if len(overall_scores) >= 10:
        recent_10 = sum(overall_scores[-10:]) / 10
        prev_10 = sum(overall_scores[-20:-10]) / max(len(overall_scores[-20:-10]), 1)
        recent_trend = recent_10 - prev_10 if prev_10 else None

    # --- Overall health ---
    failing = []
    if context_rel is not None and context_rel < 0.75:
        failing.append(f"context_relevance={context_rel:.3f} (target: 0.75)")
    if hit_rate is not None and hit_rate < 0.85:
        failing.append(f"hit_rate={hit_rate:.3f} (target: 0.85)")
    if precision3 is not None and precision3 < 0.70:
        failing.append(f"precision@3={precision3:.3f} (target: 0.70)")

    health = "CRITICAL" if len(failing) >= 2 else "WARNING" if failing else "HEALTHY"

    report = {
        "health": health,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "core_metrics": {
            "hit_rate": hit_rate,
            "precision_at_3": precision3,
            "context_relevance": context_rel,
            "query_avg_ms": query_avg,
            "query_p95_ms": query_p95,
            "clr_retrieval": clr_score,
        },
        "failing": failing,
        "per_collection": {
            cat: {
                "precision_at_k": info.get("avg_precision_at_k"),
                "mrr": info.get("mrr"),
                "count": info.get("count"),
            }
            for cat, info in cat_scores.items()
        },
        "per_caller": {
            caller: {
                "recalls": info.get("total_recalls"),
                "rated": info.get("rated"),
                "useful": info.get("useful"),
                "hit_rate": info.get("hit_rate"),
                "avg_distance": info.get("avg_distance"),
            }
            for caller, info in by_caller.items()
        },
        "context_relevance_detail": {
            "episodes_scored": len(relevance_events),
            "overall_mean": sum(overall_scores) / len(overall_scores) if overall_scores else None,
            "recent_trend": recent_trend,
            "per_section_mean": dict(section_avg_sorted),
            "weakest_sections": [s for s, _ in section_avg_sorted[:5]],
        },
        "feedback_coverage": {
            "total_events": total_events,
            "rated_events": rated_events,
            "coverage_pct": round(rated_events / total_events * 100, 1) if total_events else 0,
        },
    }
    return report


def format_markdown(report: dict) -> str:
    """Format report as human-readable markdown."""
    lines = []
    h = report["health"]
    icon = {"HEALTHY": "green", "WARNING": "yellow", "CRITICAL": "red"}.get(h, "?")
    lines.append(f"# Retrieval Quality Report")
    lines.append(f"_Generated: {report['generated_at'][:19]}Z_\n")
    lines.append(f"**Health: {h}**\n")

    if report["failing"]:
        lines.append("**Failing metrics:**")
        for f in report["failing"]:
            lines.append(f"- {f}")
        lines.append("")

    # Core metrics table
    cm = report["core_metrics"]
    lines.append("## Core Metrics\n")
    lines.append("| Metric | Value | Target | Status |")
    lines.append("|--------|-------|--------|--------|")
    rows = [
        ("Hit Rate", cm.get("hit_rate"), 0.85, True),
        ("Precision@3", cm.get("precision_at_3"), 0.70, True),
        ("Context Relevance", cm.get("context_relevance"), 0.75, True),
        ("Query Avg (ms)", cm.get("query_avg_ms"), 800, False),
        ("Query P95 (ms)", cm.get("query_p95_ms"), 1500, False),
    ]
    for name, val, target, higher in rows:
        v = f"{val:.3f}" if isinstance(val, float) and val < 10 else (f"{val:.1f}" if val else "--")
        s = _status_icon(val, target, higher)
        lines.append(f"| {name} | {v} | {target} | {s} |")

    if cm.get("clr_retrieval") is not None:
        lines.append(f"\nCLR Retrieval Dimension: **{cm['clr_retrieval']:.3f}**")
    lines.append("")

    # Per-collection
    pc = report.get("per_collection", {})
    if pc:
        lines.append("## Per-Collection Precision\n")
        lines.append("| Collection | P@k | MRR | Queries |")
        lines.append("|------------|-----|-----|---------|")
        for cat, info in sorted(pc.items(), key=lambda x: x[1].get("precision_at_k") or 0):
            pk = f"{info['precision_at_k']:.3f}" if info.get("precision_at_k") is not None else "--"
            mrr = f"{info['mrr']:.3f}" if info.get("mrr") is not None else "--"
            cnt = info.get("count", "?")
            lines.append(f"| {cat} | {pk} | {mrr} | {cnt} |")
        lines.append("")

    # Context relevance breakdown
    cr = report.get("context_relevance_detail", {})
    if cr.get("per_section_mean"):
        lines.append("## Context Relevance Breakdown\n")
        lines.append(f"Episodes scored: {cr['episodes_scored']}")
        if cr.get("overall_mean") is not None:
            lines.append(f"Overall mean: **{cr['overall_mean']:.3f}**")
        if cr.get("recent_trend") is not None:
            direction = "+" if cr["recent_trend"] > 0 else ""
            lines.append(f"Recent trend (last 10 vs prev 10): {direction}{cr['recent_trend']:.3f}")
        lines.append("")
        lines.append("| Section | Avg Relevance | Note |")
        lines.append("|---------|---------------|------|")
        weakest = set(cr.get("weakest_sections", []))
        for section, avg in cr["per_section_mean"].items():
            note = "WEAK" if section in weakest else ""
            lines.append(f"| {section} | {avg:.3f} | {note} |")
        lines.append("")

    # Per-caller stats
    pcaller = report.get("per_caller", {})
    if pcaller:
        lines.append("## Recall Sources\n")
        lines.append("| Caller | Recalls | Rated | Useful | Hit Rate | Avg Dist |")
        lines.append("|--------|---------|-------|--------|----------|----------|")
        for caller, info in sorted(pcaller.items(), key=lambda x: -(x[1].get("recalls") or 0)):
            recalls = info.get("recalls", "?")
            rated = info.get("rated", 0)
            useful = info.get("useful", 0)
            hr = f"{info['hit_rate']:.0%}" if info.get("hit_rate") is not None else "--"
            dist = f"{info['avg_distance']:.3f}" if info.get("avg_distance") is not None else "--"
            lines.append(f"| {caller} | {recalls} | {rated} | {useful} | {hr} | {dist} |")
        lines.append("")

    # Feedback loop
    fb = report.get("feedback_coverage", {})
    if fb:
        lines.append("## Feedback Loop\n")
        lines.append(f"- Total recall events: {fb.get('total_events', '?')}")
        lines.append(f"- Events rated for usefulness: {fb.get('rated_events', '?')} ({fb.get('coverage_pct', '?')}%)")
        lines.append("")

    # Action items
    lines.append("## Action Items\n")
    if report.get("failing"):
        for f in report["failing"]:
            lines.append(f"- **P1**: Fix {f}")
    if fb.get("coverage_pct", 100) < 20:
        lines.append(f"- **P2**: Increase usefulness rating coverage from {fb.get('coverage_pct', '?')}% to >20%")
    weak = cr.get("weakest_sections", [])
    if weak:
        top3 = weak[:3]
        lines.append(f"- **P2**: Improve weakest context sections: {', '.join(top3)}")
    if not report.get("failing") and fb.get("coverage_pct", 0) >= 20:
        lines.append("- No critical actions needed.")
    lines.append("")

    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    report = build_report()

    if "--json" in args:
        print(json.dumps(report, indent=2, default=str))
        return

    md = format_markdown(report)

    out_idx = None
    for i, a in enumerate(args):
        if a == "--out" and i + 1 < len(args):
            out_idx = i + 1
    if out_idx is not None:
        outpath = args[out_idx]
        os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
        with open(outpath, "w") as f:
            f.write(md)
        print(f"Report written to {outpath}")
    else:
        print(md)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Retrieval-quality dashboard generator (interim).

Writes data/retrieval_quality/dashboard.md from:
  - data/retrieval_benchmark/latest.json   (Precision@3, MRR, by_category)
  - data/retrieval_quality/report.json     (hit rate, query times, dead recall)
  - data/retrieval_quality/context_relevance.jsonl (per-section averages)

Canonical source TBD pending [P3_DASHBOARD_SOURCE_AUDIT]; until that audit lands
this writer aggregates the three existing producers so the dashboard has a fresh
``last_updated`` line every day. Once the audit identifies the canonical source,
collapse this generator into that source's writer.

Usage:
    python3 scripts/brain_mem/retrieval_dashboard.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
BENCHMARK_LATEST = WORKSPACE / "data/retrieval_benchmark/latest.json"
REPORT_FILE = WORKSPACE / "data/retrieval_quality/report.json"
CONTEXT_RELEVANCE = WORKSPACE / "data/retrieval_quality/context_relevance.jsonl"
DASHBOARD = WORKSPACE / "data/retrieval_quality/dashboard.md"

TARGETS = {
    "hit_rate": 0.85,
    "precision_at_3": 0.7,
    "context_relevance": 0.75,
    "query_avg_ms": 800,
    "query_p95_ms": 1500,
}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[dashboard] WARN: failed to load {path}: {e}", file=sys.stderr)
        return {}


def _load_context_relevance(path: Path, limit: int = 200) -> dict:
    """Load tail of context_relevance.jsonl and compute per-section averages."""
    if not path.exists():
        return {"episodes": 0, "overall_mean": 0.0, "per_section": {}, "trend": 0.0}
    lines: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except Exception:
                continue
    if not lines:
        return {"episodes": 0, "overall_mean": 0.0, "per_section": {}, "trend": 0.0}
    tail = lines[-limit:]
    overall_mean = sum(r.get("overall", 0.0) for r in tail) / max(len(tail), 1)
    section_sums: dict[str, float] = defaultdict(float)
    section_counts: dict[str, int] = defaultdict(int)
    for r in tail:
        for sec, val in (r.get("per_section") or {}).items():
            section_sums[sec] += float(val)
            section_counts[sec] += 1
    per_section = {
        sec: section_sums[sec] / section_counts[sec]
        for sec in section_sums
        if section_counts[sec] > 0
    }
    trend = 0.0
    if len(tail) >= 20:
        last10 = sum(r.get("overall", 0.0) for r in tail[-10:]) / 10
        prev10 = sum(r.get("overall", 0.0) for r in tail[-20:-10]) / 10
        trend = last10 - prev10
    return {
        "episodes": len(tail),
        "overall_mean": overall_mean,
        "per_section": per_section,
        "trend": trend,
    }


def _load_query_speed() -> tuple[float | None, float | None]:
    """Load avg/p95 query speed from data/performance_metrics.json if available."""
    pm = WORKSPACE / "data/performance_metrics.json"
    if not pm.exists():
        return (None, None)
    try:
        data = json.loads(pm.read_text())
        speed = data.get("brain_speed", {})
        return (speed.get("avg_ms"), speed.get("p95_ms"))
    except Exception:
        return (None, None)


def _status(value: float | None, target: float, higher_is_better: bool) -> str:
    if value is None:
        return "N/A "
    if higher_is_better:
        return "OK  " if value >= target else "FAIL"
    return "OK  " if value <= target else "FAIL"


def render() -> str:
    bench = _load_json(BENCHMARK_LATEST)
    report = _load_json(REPORT_FILE)
    cr = _load_context_relevance(CONTEXT_RELEVANCE)
    avg_ms, p95_ms = _load_query_speed()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hit_rate = report.get("hit_rate")
    precision_at_3 = bench.get("avg_precision_at_k")
    context_relevance = cr["overall_mean"]

    failing: list[str] = []
    if hit_rate is not None and hit_rate < TARGETS["hit_rate"]:
        failing.append(f"hit_rate={hit_rate:.3f} (target: {TARGETS['hit_rate']})")
    if precision_at_3 is not None and precision_at_3 < TARGETS["precision_at_3"]:
        failing.append(f"precision_at_3={precision_at_3:.3f} (target: {TARGETS['precision_at_3']})")
    if context_relevance is not None and context_relevance < TARGETS["context_relevance"]:
        failing.append(f"context_relevance={context_relevance:.3f} (target: {TARGETS['context_relevance']})")
    if avg_ms is not None and avg_ms > TARGETS["query_avg_ms"]:
        failing.append(f"query_avg_ms={avg_ms:.1f} (target: <{TARGETS['query_avg_ms']})")
    if p95_ms is not None and p95_ms > TARGETS["query_p95_ms"]:
        failing.append(f"query_p95_ms={p95_ms:.1f} (target: <{TARGETS['query_p95_ms']})")

    health = "OK" if not failing else "WARNING"

    lines: list[str] = []
    lines.append("# Retrieval Quality Report")
    lines.append(f"_Generated: {now}_")
    lines.append(f"_last_updated: {now}_")
    lines.append("")
    lines.append("> _Note: canonical-source TBD pending `[P3_DASHBOARD_SOURCE_AUDIT]`._"
                 " This writer aggregates retrieval_benchmark + retrieval_quality + "
                 "context_relevance until the audit identifies the single source.")
    lines.append("")
    lines.append(f"**Health: {health}**")
    lines.append("")
    if failing:
        lines.append("**Failing metrics:**")
        for f in failing:
            lines.append(f"- {f}")
        lines.append("")

    # Core metrics table
    def fmt(v, prec=3):
        return f"{v:.{prec}f}" if v is not None else "N/A"
    lines.append("## Core Metrics")
    lines.append("")
    lines.append("| Metric | Value | Target | Status |")
    lines.append("|--------|-------|--------|--------|")
    lines.append(f"| Hit Rate | {fmt(hit_rate)} | {TARGETS['hit_rate']} | "
                 f"{_status(hit_rate, TARGETS['hit_rate'], True)} |")
    lines.append(f"| Precision@3 | {fmt(precision_at_3)} | {TARGETS['precision_at_3']} | "
                 f"{_status(precision_at_3, TARGETS['precision_at_3'], True)} |")
    lines.append(f"| Context Relevance | {fmt(context_relevance)} | {TARGETS['context_relevance']} | "
                 f"{_status(context_relevance, TARGETS['context_relevance'], True)} |")
    lines.append(f"| Query Avg (ms) | {fmt(avg_ms, 1)} | {TARGETS['query_avg_ms']} | "
                 f"{_status(avg_ms, TARGETS['query_avg_ms'], False)} |")
    lines.append(f"| Query P95 (ms) | {fmt(p95_ms, 1)} | {TARGETS['query_p95_ms']} | "
                 f"{_status(p95_ms, TARGETS['query_p95_ms'], False)} |")
    lines.append("")

    # Per-category precision (from benchmark by_category)
    by_cat = bench.get("by_category") or {}
    if by_cat:
        lines.append("## Per-Category Precision")
        lines.append("")
        lines.append("| Category | P@3 | MRR | Queries |")
        lines.append("|----------|-----|-----|---------|")
        for cat, stats in sorted(by_cat.items(), key=lambda kv: kv[1].get("avg_precision_at_k", 0)):
            lines.append(
                f"| {cat} | {fmt(stats.get('avg_precision_at_k'))} | "
                f"{fmt(stats.get('mrr'))} | {stats.get('count', 0)} |"
            )
        lines.append("")

    # Context-relevance breakdown
    if cr["per_section"]:
        lines.append("## Context Relevance Breakdown")
        lines.append("")
        lines.append(f"Episodes scored: {cr['episodes']}")
        lines.append(f"Overall mean: **{cr['overall_mean']:.3f}**")
        if cr["episodes"] >= 20:
            sign = "+" if cr["trend"] >= 0 else ""
            lines.append(f"Recent trend (last 10 vs prev 10): {sign}{cr['trend']:.3f}")
        lines.append("")
        lines.append("| Section | Avg Relevance | Note |")
        lines.append("|---------|---------------|------|")
        for sec, val in sorted(cr["per_section"].items(), key=lambda kv: kv[1]):
            note = "WEAK" if val < 0.15 else ""
            lines.append(f"| {sec} | {val:.3f} | {note} |")
        lines.append("")

    # Provenance footer
    lines.append("## Sources")
    lines.append("")
    lines.append(f"- Benchmark: `{BENCHMARK_LATEST.relative_to(WORKSPACE)}` "
                 f"(timestamp: {bench.get('timestamp', 'unknown')})")
    lines.append(f"- Quality: `{REPORT_FILE.relative_to(WORKSPACE)}` "
                 f"(period_days: {report.get('period_days', '?')})")
    lines.append(f"- Context relevance: `{CONTEXT_RELEVANCE.relative_to(WORKSPACE)}` "
                 f"(last {cr['episodes']} episodes)")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not BENCHMARK_LATEST.exists():
        print(f"[dashboard] FATAL: missing benchmark fixture {BENCHMARK_LATEST}", file=sys.stderr)
        return 2
    md = render()
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD.write_text(md)
    print(f"[dashboard] wrote {DASHBOARD} ({len(md)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

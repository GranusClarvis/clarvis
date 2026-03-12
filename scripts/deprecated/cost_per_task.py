#!/usr/bin/env python3
"""
Per-task cost breakdown and routing effectiveness report.

Usage:
    python3 cost_per_task.py              # 7-day per-task cost report
    python3 cost_per_task.py --days 30    # 30-day report
    python3 cost_per_task.py --routing    # Routing effectiveness only
    python3 cost_per_task.py --json       # JSON output
    python3 cost_per_task.py --telegram   # Compact Telegram format
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'clarvis-cost'))
from clarvis_cost.core import CostTracker

COST_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'costs.jsonl')
ROUTER_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'router_decisions.jsonl')


def format_task_report(report: dict) -> str:
    lines = [
        f"=== Per-Task Cost Report ({report['period_days']}d) ===",
        f"Total: ${report['total_cost']:.2f} across {report['unique_tasks']} unique tasks",
        "",
    ]
    for i, t in enumerate(report["tasks"], 1):
        models = ", ".join(t["models"])
        lines.append(
            f"  {i:2d}. ${t['total_cost']:.4f} ({t['calls']}x, avg ${t['avg_cost']:.4f}) "
            f"[{models}]"
        )
        lines.append(f"      {t['task'][:90]}")
        if t["total_duration_s"] > 0:
            lines.append(f"      Duration: {t['total_duration_s']:.0f}s total")
    return "\n".join(lines)


def format_routing_report(report: dict) -> str:
    c = report["by_tier"]["cheap"]
    e = report["by_tier"]["expensive"]
    lines = [
        f"=== Routing Effectiveness ({report['period_days']}d) ===",
        f"Total calls: {report['total_calls']}",
        f"  Cheap models:     {c['count']} ({c['pct']:.0f}%) — ${c['cost']:.2f}",
        f"  Expensive models: {e['count']} ({e['pct']:.0f}%) — ${e['cost']:.2f}",
        f"  Routing rate:     {report['routing_rate']:.0f}%",
        f"  Est. savings:     ${report['estimated_savings']:.2f}",
    ]
    return "\n".join(lines)


def format_telegram(task_report: dict, routing_report: dict) -> str:
    lines = [f"Cost Report ({task_report['period_days']}d)"]
    lines.append(f"Total: ${task_report['total_cost']:.2f} | {task_report['unique_tasks']} tasks")
    lines.append(f"Routing: {routing_report['routing_rate']:.0f}% cheap | "
                 f"Saved: ${routing_report['estimated_savings']:.2f}")
    lines.append("")
    for t in task_report["tasks"][:5]:
        lines.append(f"  ${t['total_cost']:.2f} ({t['calls']}x) {t['task'][:50]}")
    return "\n".join(lines)


def main():
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    tracker = CostTracker(COST_LOG)
    routing_only = "--routing" in sys.argv
    json_out = "--json" in sys.argv
    telegram = "--telegram" in sys.argv

    if routing_only:
        report = tracker.routing_effectiveness(days=days, router_log=ROUTER_LOG)
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(format_routing_report(report))
        return

    task_report = tracker.task_costs(days=days)
    routing_report = tracker.routing_effectiveness(days=days, router_log=ROUTER_LOG)

    if json_out:
        print(json.dumps({"tasks": task_report, "routing": routing_report}, indent=2))
    elif telegram:
        print(format_telegram(task_report, routing_report))
    else:
        print(format_task_report(task_report))
        print()
        print(format_routing_report(routing_report))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cost Tracker CLI — Quick access to ClarvisCost from bash scripts.

Wraps the clarvis-cost package for easy querying from cron scripts
and command line. Tracks OpenRouter/OpenClaw API usage only
(NOT Claude Code subprocess usage).

Usage:
    python3 cost_tracker.py daily          # Today's costs (local log)
    python3 cost_tracker.py weekly         # This week's costs (local log)
    python3 cost_tracker.py monthly        # This month's costs (local log)
    python3 cost_tracker.py budget [limit] # Budget check (default $5/day)
    python3 cost_tracker.py trend [days]   # Daily trend (default 7 days)
    python3 cost_tracker.py log <model> <in_tokens> <out_tokens> [source] [task]
    python3 cost_tracker.py analyze        # Optimization suggestions
    python3 cost_tracker.py import-router  # Import router_decisions.jsonl
    python3 cost_tracker.py summary        # One-line summary for digests
    python3 cost_tracker.py realtime       # Real costs from OpenRouter API
    python3 cost_tracker.py api            # Same as realtime but JSON output
    python3 cost_tracker.py compare        # Local tracked vs API totals
    python3 cost_tracker.py telegram       # Formatted for Telegram /costs command
"""

import json
import os
import sys

# Add clarvis-cost package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'clarvis-cost'))

from clarvis_cost.core import CostTracker, estimate_cost, estimate_tokens, analyze_savings, import_router_decisions

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
COST_LOG = os.path.join(DATA_DIR, 'costs.jsonl')
ROUTER_LOG = os.path.join(DATA_DIR, 'router_decisions.jsonl')


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]
    tracker = CostTracker(COST_LOG)

    if cmd in ("daily", "day"):
        rollup = tracker.rollup("day")
        print(f"=== Daily Cost Report ===")
        print(f"Total: ${rollup['total_cost']:.4f}")
        print(f"Calls: {rollup['call_count']}")
        print(f"Tokens: {rollup['total_input_tokens']:,} in / {rollup['total_output_tokens']:,} out")
        if rollup["by_model"]:
            print(f"\nBy model:")
            for m, d in sorted(rollup["by_model"].items(), key=lambda x: -x[1]["cost"]):
                print(f"  {m}: ${d['cost']:.4f} ({d['count']} calls)")
        if rollup["by_source"]:
            print(f"\nBy source:")
            for s, d in sorted(rollup["by_source"].items(), key=lambda x: -x[1]["cost"]):
                print(f"  {s}: ${d['cost']:.4f} ({d['count']} calls)")

    elif cmd in ("weekly", "week"):
        rollup = tracker.rollup("week")
        print(f"=== Weekly Cost Report ===")
        print(f"Total: ${rollup['total_cost']:.4f}")
        print(f"Calls: {rollup['call_count']}")
        print(f"Tokens: {rollup['total_input_tokens']:,} in / {rollup['total_output_tokens']:,} out")
        if rollup["by_model"]:
            print(f"\nBy model:")
            for m, d in sorted(rollup["by_model"].items(), key=lambda x: -x[1]["cost"]):
                print(f"  {m}: ${d['cost']:.4f} ({d['count']} calls)")

    elif cmd in ("monthly", "month"):
        rollup = tracker.rollup("month")
        print(f"=== Monthly Cost Report ===")
        print(f"Total: ${rollup['total_cost']:.4f}")
        print(f"Calls: {rollup['call_count']}")
        print(f"Tokens: {rollup['total_input_tokens']:,} in / {rollup['total_output_tokens']:,} out")

    elif cmd == "budget":
        limit = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        budget = tracker.budget_check(daily_budget=limit)
        print(f"Today: ${budget['today_cost']:.4f} / ${budget['daily_budget']:.2f}")
        print(f"Used: {budget['pct_used']:.1f}%")
        print(f"Remaining: ${budget['remaining']:.4f}")
        print(f"Status: {budget['alert'].upper()}")

    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        trend = tracker.daily_trend(days)
        print(f"=== {days}-Day Cost Trend ===")
        for day in trend:
            bar = "#" * min(int(day["cost"] * 20), 40)  # Scale: $0.05 per #
            print(f"  {day['date']}: ${day['cost']:.4f}  {day['calls']}calls  {bar}")

    elif cmd == "log":
        if len(sys.argv) < 5:
            print("Usage: cost_tracker.py log <model> <in_tokens> <out_tokens> [source] [task]")
            sys.exit(1)
        model = sys.argv[2]
        in_tok = int(sys.argv[3])
        out_tok = int(sys.argv[4])
        source = sys.argv[5] if len(sys.argv) > 5 else "manual"
        task = sys.argv[6] if len(sys.argv) > 6 else ""
        entry = tracker.log(model, in_tok, out_tok, source=source, task=task)
        print(f"Logged: ${entry.cost_usd:.6f} ({model})")

    elif cmd == "analyze":
        stats = analyze_savings(tracker, ROUTER_LOG)
        print(f"=== Cost Optimization Analysis ===")
        print(f"Weekly cost: ${stats['weekly_cost']:.4f}")
        print(f"Weekly calls: {stats['weekly_calls']}")
        print(f"Weekly tokens: {stats['weekly_tokens']:,}")
        if "router_fallback_rate" in stats:
            print(f"Router fallback rate: {stats['router_fallback_rate']}%")
        if "output_input_ratio" in stats:
            print(f"Output/input ratio: {stats['output_input_ratio']}x")
        if stats.get("suggestions"):
            print(f"\nSuggestions:")
            for s in stats["suggestions"]:
                print(f"  - {s}")
        else:
            print(f"\nNo optimization suggestions at this time.")

    elif cmd == "import-router":
        count = import_router_decisions(ROUTER_LOG, tracker)
        print(f"Imported {count} router decisions into cost log")

    elif cmd == "summary":
        # One-line summary for digest integration
        budget = tracker.budget_check(daily_budget=5.0)
        rollup = tracker.rollup("day")
        models = ", ".join(f"{m}:{d['count']}" for m, d in rollup.get("by_model", {}).items())
        print(f"Cost today: ${budget['today_cost']:.4f}/{budget['daily_budget']:.2f} "
              f"({budget['pct_used']:.0f}% used, {rollup['call_count']} calls) [{models}]")

    elif cmd == "realtime":
        # Real costs from OpenRouter API
        from cost_api import fetch_usage, format_usage
        usage = fetch_usage()
        print(format_usage(usage))

    elif cmd == "api":
        # JSON output of real API data
        from cost_api import fetch_usage
        usage = fetch_usage()
        print(json.dumps(usage, indent=2))

    elif cmd == "compare":
        # Compare local tracked costs vs real API data
        from cost_api import fetch_usage
        usage = fetch_usage()
        local_day = tracker.rollup("day")
        local_week = tracker.rollup("week")
        local_month = tracker.rollup("month")
        print("=== Local Tracked vs OpenRouter API ===")
        print(f"              Local      API        Gap")
        print(f"  Daily:   ${local_day['total_cost']:>8.4f}  ${usage['daily']:>8.4f}  ${usage['daily'] - local_day['total_cost']:>8.4f}")
        print(f"  Weekly:  ${local_week['total_cost']:>8.4f}  ${usage['weekly']:>8.4f}  ${usage['weekly'] - local_week['total_cost']:>8.4f}")
        print(f"  Monthly: ${local_month['total_cost']:>8.4f}  ${usage['monthly']:>8.4f}  ${usage['monthly'] - local_month['total_cost']:>8.4f}")
        gap_pct = ((usage['monthly'] - local_month['total_cost']) / max(usage['monthly'], 0.01)) * 100
        if gap_pct > 10:
            print(f"\n  WARNING: Local tracking misses {gap_pct:.0f}% of actual costs.")
            print(f"  This gap = costs from the M2.5 interactive agent + untracked cron calls.")

    elif cmd == "telegram":
        # Formatted output for Telegram /costs command
        from cost_api import fetch_usage
        usage = fetch_usage()
        rollup = tracker.rollup("day")

        lines = []
        lines.append("OpenRouter Usage")
        lines.append(f"Today: ${usage['daily']:.2f} | Week: ${usage['weekly']:.2f} | Month: ${usage['monthly']:.2f}")
        if usage["limit"] is not None and usage["remaining"] is not None:
            pct_left = usage["remaining"] / usage["limit"] * 100 if usage["limit"] > 0 else 0
            lines.append(f"Remaining: ${usage['remaining']:.2f} / ${usage['limit']:.0f} ({pct_left:.0f}%)")

        if rollup["by_model"]:
            lines.append("")
            lines.append("Model Breakdown (today):")
            for m, d in sorted(rollup["by_model"].items(), key=lambda x: -x[1]["cost"]):
                name = m.split("/")[-1] if "/" in m else m
                lines.append(f"  {name}: ${d['cost']:.4f} ({d['count']} calls)")

        if usage.get("remaining") is not None and usage["remaining"] < 20:
            lines.append("")
            if usage["remaining"] < 10:
                lines.append("CRITICAL: Less than $10 remaining!")
            else:
                lines.append("WARNING: Less than $20 remaining")

        print("\n".join(lines))

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'python3 cost_tracker.py' with no args for help.")
        sys.exit(1)


if __name__ == "__main__":
    main()

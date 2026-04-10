#!/usr/bin/env python3
"""Cost checkpoint — log real OpenRouter usage after each spawner run.

Called by run_claude_monitored() to record actual API spending alongside
estimated per-run entries.  Each checkpoint creates an entry with
estimated=False, giving CLR's autonomy dimension and cost reports real data.

Usage:
    python3 cost_checkpoint.py <source> <task_summary> [duration_s]

Example:
    python3 cost_checkpoint.py cron_autonomous "Fix CLR ablation" 356

Phase 2 Measurement Integrity (2026-04-09): wires real cost data into
the cost tracking pipeline (task 2.5, finding F4.6.1).
"""

import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
COSTS_FILE = os.path.join(WORKSPACE, "data/costs.jsonl")


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    task = sys.argv[2] if len(sys.argv) > 2 else ""
    duration_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

    try:
        from clarvis.orch.cost_api import fetch_usage
        usage = fetch_usage()
    except Exception as e:
        # Non-fatal: if API call fails, skip silently
        print(f"[cost_checkpoint] API error (non-fatal): {e}", file=sys.stderr)
        return

    daily = usage.get("daily", 0.0)
    if daily <= 0:
        return  # No spend to log

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "openrouter-aggregate",
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": round(daily, 6),
        "source": source,
        "task": f"[real_checkpoint] {task[:130]}" if task else "[real_checkpoint]",
        "duration_s": round(duration_s, 2),
        "generation_id": "",
        "estimated": False,
        "checkpoint_type": "daily_usage",
        "usage_data": {
            "daily": usage.get("daily"),
            "remaining": usage.get("remaining"),
        },
    }

    os.makedirs(os.path.dirname(COSTS_FILE), exist_ok=True)
    with open(COSTS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[cost_checkpoint] Real: ${daily:.4f}/day, remaining=${usage.get('remaining', '?')}")


if __name__ == "__main__":
    main()

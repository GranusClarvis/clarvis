#!/usr/bin/env python3
# STATUS: MIGRATED to clarvis.cognition.cognitive_load (spine module)
# This file is a backward-compatibility shim. New code should use:
#   from clarvis.cognition.cognitive_load import compute_load, should_defer_task, estimate_task_complexity
"""Cognitive Load Monitor — backward-compat shim delegating to clarvis.cognition.cognitive_load."""

import json
import sys

from clarvis.cognition.cognitive_load import (  # noqa: F401
    compute_load, should_defer_task, estimate_task_complexity, log_sizing,
    measure_failure_rate, measure_queue_velocity, measure_cron_times,
    measure_capability_degradation, record_load, get_history,
    OVERLOAD_THRESHOLD, CAUTION_THRESHOLD,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: cognitive_load.py [check|should-defer|history]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        load = compute_load()
        record_load(load)
        print(json.dumps(load, indent=2))

    elif cmd == "should-defer":
        section = sys.argv[2] if len(sys.argv) > 2 else "P1"
        defer, reason = should_defer_task(section)
        print(reason)
        sys.exit(0 if defer else 1)

    elif cmd == "history":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        hist = get_history(days)
        if not hist:
            print("No history recorded yet.")
        else:
            scores = [h["score"] for h in hist]
            print(f"Load history ({len(hist)} measurements, last {days} days):")
            print(f"  Current: {scores[-1]:.3f}")
            print(f"  Avg:     {sum(scores)/len(scores):.3f}")
            print(f"  Min:     {min(scores):.3f}")
            print(f"  Max:     {max(scores):.3f}")
            overloaded = sum(1 for s in scores if s >= OVERLOAD_THRESHOLD)
            caution = sum(1 for s in scores if CAUTION_THRESHOLD <= s < OVERLOAD_THRESHOLD)
            print(f"  Overloaded: {overloaded}/{len(scores)} ({100*overloaded/len(scores):.0f}%)")
            print(f"  Caution:    {caution}/{len(scores)} ({100*caution/len(scores):.0f}%)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

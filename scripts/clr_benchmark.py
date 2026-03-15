#!/usr/bin/env python3
"""CLR Benchmark — thin wrapper over canonical clarvis.metrics.clr module.

Usage:
    python3 clr_benchmark.py             # Full benchmark
    python3 clr_benchmark.py quick       # Fast subset (~5s)
    python3 clr_benchmark.py record      # Full + record to history
    python3 clr_benchmark.py trend       # Show CLR trend
    python3 clr_benchmark.py compare     # Show CLR vs estimated baseline
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from clarvis.metrics.clr import (
    compute_clr, record_clr, format_clr, get_clr_trend,
    WEIGHTS, BASELINE, CLR_HISTORY,
)


def show_trend(days=14):
    entries = get_clr_trend(days=days)
    if not entries:
        print(f"No CLR history found. Run 'clr_benchmark.py record' first.")
        return
    print(f"=== CLR Trend — Last {days} Days ===")
    for entry in entries:
        ts = entry["timestamp"][:10]
        clr = entry["clr"]
        va = entry["value_add"]
        bar = "#" * int(clr * 40)
        print(f"  {ts}  CLR={clr:.3f}  +{va:.3f}  |{bar}")
    clr_values = [e["clr"] for e in entries]
    print(f"\n  Min: {min(clr_values):.3f}  Max: {max(clr_values):.3f}  Avg: {sum(clr_values)/len(clr_values):.3f}")
    if len(clr_values) >= 2:
        delta = clr_values[-1] - clr_values[0]
        direction = "improving" if delta > 0.01 else "declining" if delta < -0.01 else "stable"
        print(f"  Trend: {direction} ({'+' if delta >= 0 else ''}{delta:.3f})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    if cmd == "quick":
        result = compute_clr(quick=True)
        print(format_clr(result))
    elif cmd == "record":
        result = compute_clr(quick=False)
        print(format_clr(result))
        record_clr(result)
        print(f"\nRecorded to {CLR_HISTORY}")
    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
        show_trend(days)
    elif cmd == "compare":
        result = compute_clr(quick=False)
        print(format_clr(result))
        print(f"\n=== Baseline vs Clarvis ===")
        for dim in WEIGHTS:
            b = BASELINE[dim]
            c = result["dimensions"][dim]["score"] or 0
            delta = c - b
            print(f"  {dim:25s}  baseline={b:.2f}  clarvis={c:.3f}  delta={'+' if delta >= 0 else ''}{delta:.3f}")
    else:
        result = compute_clr(quick=False)
        print(format_clr(result))

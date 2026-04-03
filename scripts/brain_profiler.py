#!/usr/bin/env python3
"""Brain operation profiler — cProfile-based end-to-end profiling.

Profiles the 3 slowest brain operations:
  1. recall (multi-collection search)
  2. store + auto_link (store with graph update)
  3. decay_importance (batch decay across all collections)

Usage:
  python3 brain_profiler.py [report|quick|all]

  report  — Full cProfile for all 3 operations (default)
  quick   — Just time the 3 operations without cProfile detail
  all     — Both quick timing and full cProfile report

Output:
  Writes detailed report to data/brain_profile_report.txt
  Prints summary to stdout
"""

import cProfile
import io
import os
import pstats
import sys
import time
from datetime import datetime, timezone

# --- Path setup ---
WORKSPACE = "/home/agent/.openclaw/workspace"
sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))

from brain import brain  # noqa: E402

REPORT_PATH = os.path.join(WORKSPACE, "data", "brain_profile_report.txt")

# Test memory tag for cleanup
_TEST_TAG = "__profiler_bench__"
_TEST_PREFIX = "brain_profiler_test_"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warmup():
    """Warm up brain (loads embeddings, ChromaDB connection, caches)."""
    print("  Warming up brain...", end=" ", flush=True)
    t0 = time.monotonic()
    brain.recall("warmup", n=1)
    elapsed = time.monotonic() - t0
    print(f"done ({elapsed:.3f}s)")


def _cleanup_test_memories():
    """Remove any test memories left behind by the profiler."""
    removed = 0
    for col_name, col in brain.collections.items():
        try:
            results = col.get(where={"source": _TEST_TAG})
            if results and results["ids"]:
                col.delete(ids=results["ids"])
                removed += len(results["ids"])
        except Exception:
            # Some collections may not support where filter; try ID prefix
            try:
                results = col.get()
                if results and results["ids"]:
                    to_del = [i for i in results["ids"] if i.startswith(_TEST_PREFIX)]
                    if to_del:
                        col.delete(ids=to_del)
                        removed += len(to_del)
            except Exception:
                pass
    if removed:
        print(f"  Cleaned up {removed} test memories.")


def _run_profiled(label, func, sort_key="cumulative"):
    """Run func under cProfile, return (elapsed_s, pstats_text, bottleneck_line)."""
    pr = cProfile.Profile()

    t0 = time.monotonic()
    pr.enable()
    result = func()
    pr.disable()
    elapsed = time.monotonic() - t0

    # Capture stats text
    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream)
    ps.sort_stats(sort_key)
    ps.print_stats(20)
    stats_text = stream.getvalue()

    # Identify bottleneck — first non-builtin function with highest cumulative time
    stream2 = io.StringIO()
    ps2 = pstats.Stats(pr, stream=stream2)
    ps2.sort_stats("cumulative")
    ps2.print_stats(30)
    lines = stream2.getvalue().splitlines()

    bottleneck = _extract_bottleneck(lines)

    return elapsed, stats_text, bottleneck, result


def _extract_bottleneck(stat_lines):
    """Parse pstats output to find the top bottleneck function (non-trivial)."""
    skip_patterns = (
        "<built-in", "{built-in", "brain_profiler.py", "<frozen",
        "cProfile", "pstats", "{method 'disable'",
    )
    in_table = False
    for line in stat_lines:
        stripped = line.strip()
        if stripped.startswith("ncalls"):
            in_table = True
            continue
        if not in_table:
            continue
        if not stripped or stripped.startswith("---"):
            continue
        # Skip trivial entries
        if any(pat in stripped for pat in skip_patterns):
            continue
        # This is our top non-trivial entry
        return stripped
    return "(unable to determine)"


def _timed(label, func):
    """Simple timing wrapper, returns (elapsed_s, result)."""
    t0 = time.monotonic()
    result = func()
    elapsed = time.monotonic() - t0
    return elapsed, result


# ---------------------------------------------------------------------------
# Operation wrappers
# ---------------------------------------------------------------------------

def op_recall():
    """Multi-collection recall with graph expansion."""
    return brain.recall(
        "what are the most important recent learnings about architecture and performance",
        n=5,
        include_related=True,
        graph_expand=True,
        cross_collection_expand=True,
    )


def op_store():
    """Store a test memory (will be cleaned up after)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    mem_id = f"{_TEST_PREFIX}{ts}"
    return brain.store(
        "Profiler test memory — brain_profiler.py benchmark entry. "
        "This memory exists only for profiling and will be deleted.",
        collection="clarvis-learnings",
        importance=0.1,
        tags=[_TEST_TAG, "profiler"],
        source=_TEST_TAG,
        memory_id=mem_id,
    )


def op_decay():
    """Batch decay with minimal rate to avoid real impact."""
    return brain.decay_importance(decay_rate=0.001)


# ---------------------------------------------------------------------------
# Main modes
# ---------------------------------------------------------------------------

OPERATIONS = [
    ("recall (multi-collection search)", op_recall),
    ("store + auto_link (graph update)", op_store),
    ("decay_importance (batch decay)", op_decay),
]


def run_quick():
    """Quick timing of all 3 operations."""
    print("\n=== Quick Timing ===\n")
    _warmup()
    print()

    timings = []
    for label, func in OPERATIONS:
        elapsed, _ = _timed(label, func)
        timings.append((label, elapsed))
        print(f"  {label}: {elapsed:.4f}s")

    _cleanup_test_memories()

    # Summary
    print("\n--- Ranking (slowest first) ---")
    for label, elapsed in sorted(timings, key=lambda x: -x[1]):
        print(f"  {elapsed:.4f}s  {label}")

    return timings


def run_report():
    """Full cProfile report for all 3 operations."""
    print("\n=== Full cProfile Report ===\n")
    _warmup()
    print()

    report_lines = []
    report_lines.append(f"Brain Profiler Report — {datetime.now(timezone.utc).isoformat()}")
    report_lines.append("=" * 72)
    report_lines.append("")

    summaries = []

    for label, func in OPERATIONS:
        print(f"  Profiling: {label}...", end=" ", flush=True)
        elapsed, stats_text, bottleneck, _ = _run_profiled(label, func)
        print(f"{elapsed:.4f}s")

        summaries.append((label, elapsed, bottleneck))

        report_lines.append(f"\n{'='*72}")
        report_lines.append(f"OPERATION: {label}")
        report_lines.append(f"Elapsed: {elapsed:.4f}s")
        report_lines.append(f"Bottleneck: {bottleneck}")
        report_lines.append(f"{'='*72}")
        report_lines.append("")
        report_lines.append("Top 20 functions by cumulative time:")
        report_lines.append(stats_text)

    _cleanup_test_memories()

    # Summary section
    report_lines.append("\n" + "=" * 72)
    report_lines.append("SUMMARY — Ranked by wall-clock time (slowest first)")
    report_lines.append("=" * 72 + "\n")

    for label, elapsed, bottleneck in sorted(summaries, key=lambda x: -x[1]):
        report_lines.append(f"  {elapsed:.4f}s  {label}")
        report_lines.append(f"           Bottleneck: {bottleneck}")
        report_lines.append("")

    report_text = "\n".join(report_lines)

    # Write to file
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report_text)

    print(f"\n  Report written to: {REPORT_PATH}")

    # Print summary to stdout
    print("\n--- Summary (slowest first) ---")
    for label, elapsed, bottleneck in sorted(summaries, key=lambda x: -x[1]):
        print(f"  {elapsed:.4f}s  {label}")
        # Show just the function part of the bottleneck
        print(f"           -> {bottleneck[:120]}")

    return summaries


def main():
    mode = "report"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if mode not in ("report", "quick", "all"):
        print(f"Usage: {sys.argv[0]} [report|quick|all]")
        print("  report  — Full cProfile for all 3 operations (default)")
        print("  quick   — Just time the 3 operations without cProfile detail")
        print("  all     — Both quick timing and full cProfile report")
        sys.exit(1)

    print(f"Brain Profiler — mode: {mode}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    if mode == "quick":
        run_quick()
    elif mode == "report":
        run_report()
    elif mode == "all":
        run_quick()
        print("\n" + "-" * 40)
        run_report()

    print("\nDone.")


if __name__ == "__main__":
    main()

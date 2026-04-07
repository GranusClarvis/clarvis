#!/usr/bin/env python3
# STATUS: MIGRATED to clarvis.heartbeat.brain_bridge (spine module)
# This file is a backward-compatibility shim. New code should use:
#   from clarvis.heartbeat.brain_bridge import brain_preflight_context, brain_record_outcome, brain_update_context
"""Brain Bridge — backward-compat shim delegating to clarvis.heartbeat.brain_bridge."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401

from clarvis.heartbeat.brain_bridge import (  # noqa: F401
    brain_preflight_context,
    brain_record_outcome,
    brain_update_context,
)

if __name__ == "__main__":
    """Quick self-test."""
    print("=== Brain Bridge Self-Test (via spine shim) ===")

    t0 = time.monotonic()
    ctx = brain_preflight_context("Wire brain to subconscious")
    elapsed = time.monotonic() - t0
    print(f"\nPreflight context ({elapsed:.2f}s):")
    print(f"  Goals: {len(ctx['goals_text'])} bytes")
    print(f"  Context: {ctx['context'][:80] if ctx['context'] else '(idle)'}")
    print(f"  Knowledge: {len(ctx['knowledge_hints'])} bytes")
    print(f"  Working memory: {len(ctx['working_memory'])} bytes")
    print(f"  Timings: {ctx['brain_timings']}")

    mem_id = brain_record_outcome(
        "Self-test of brain_bridge.py",
        "success",
        "All tests passed",
        duration_s=1,
    )
    print(f"\nRecorded outcome: {mem_id}")

    brain_update_context("Self-test of brain_bridge.py", "success")
    print("Context updated.")

    print("\n=== Brain Bridge OK ===")

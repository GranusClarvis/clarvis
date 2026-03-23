#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.memory.memory_consolidation import ...
# Known callers: brain.py CLI, cron_reflection.sh, brain_hygiene.py
"""Memory Consolidation — thin wrapper. Implementation in clarvis/memory/memory_consolidation.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.memory_consolidation import (  # noqa: F401
    deduplicate, merge_clusters, enhanced_decay, prune_noise,
    archive_stale, enforce_memory_caps, attention_guided_prune,
    attention_guided_decay, gwt_broadcast_survivors, sleep_consolidate,
    sleep_stats, salience_report, get_consolidation_stats,
    measure_retrieval_quality, retrieval_error_report, run_consolidation,
    main,
)

if __name__ == "__main__":
    main()

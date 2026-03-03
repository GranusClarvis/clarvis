#!/usr/bin/env python3
"""Memory Consolidation — thin wrapper. Implementation in clarvis/memory/memory_consolidation.py."""
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace")
from clarvis.memory.memory_consolidation import *  # noqa: F401,F403
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

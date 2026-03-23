#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.cognition.attention import ...
# Known callers: heartbeat_preflight, heartbeat_postflight, cron_watchdog.sh, 15+ scripts
"""Attention Mechanism — thin wrapper. Implementation in clarvis/cognition/attention.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.cognition.attention import (  # noqa: F401
    attention, get_attention, get_codelet_competition, get_attention_schema,
    AttentionItem, AttentionSpotlight, AttentionCodelet, CodeletCompetition,
    AttentionSchema, ATTENTION_DIR, SPOTLIGHT_FILE, SPOTLIGHT_CAPACITY,
    DOMAIN_KEYWORDS, CODELET_STATE_FILE, SCHEMA_FILE, SCHEMA_HISTORY_FILE,
    W_IMPORTANCE, W_RECENCY, W_RELEVANCE, W_ACCESS, W_BOOST,
    DECAY_PER_TICK, EVICTION_THRESHOLD, main,
)

if __name__ == "__main__":
    main()

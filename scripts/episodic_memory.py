#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.memory.episodic_memory import ...
# Known callers: heartbeat_preflight, dream_engine, cron_reflection.sh, 12+ scripts
"""Episodic Memory — thin wrapper. Implementation in clarvis/memory/episodic_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from clarvis.memory.episodic_memory import main, episodic, EpisodicMemory  # noqa: E402, F401

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.memory.hebbian_memory import ...
# Known callers: cron_reflection.sh (daily 21:00 cron)
"""Hebbian Memory — thin wrapper. Implementation in clarvis/memory/hebbian_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.hebbian_memory import main, hebbian  # noqa: F401

if __name__ == "__main__":
    main()

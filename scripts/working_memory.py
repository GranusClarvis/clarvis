#!/usr/bin/env python3
# BRIDGE: Thin re-export wrapper for legacy sys.path imports.
# Safe to delete ONLY after all callers migrate to: from clarvis.memory.working_memory import ...
# Known callers: safe_update.sh (existence check)
"""Working Memory — thin wrapper. Implementation in clarvis/memory/working_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.working_memory import main  # noqa: F401

if __name__ == "__main__":
    main()

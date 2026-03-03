#!/usr/bin/env python3
"""Hebbian Memory — thin wrapper. Implementation in clarvis/memory/hebbian_memory.py."""
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace")
from clarvis.memory.hebbian_memory import *  # noqa: F401,F403
from clarvis.memory.hebbian_memory import hebbian, HebbianMemory, main  # noqa: F401

if __name__ == "__main__":
    main()

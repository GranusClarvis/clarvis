#!/usr/bin/env python3
"""Episodic Memory — thin wrapper. Implementation in clarvis/memory/episodic_memory.py."""
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace")
from clarvis.memory.episodic_memory import *  # noqa: F401,F403
from clarvis.memory.episodic_memory import episodic, EpisodicMemory, main  # noqa: F401

if __name__ == "__main__":
    main()

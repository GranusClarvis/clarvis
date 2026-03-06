#!/usr/bin/env python3
"""Episodic Memory — thin wrapper. Implementation in clarvis/memory/episodic_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.episodic_memory import main, EpisodicMemory  # noqa: F401

if __name__ == "__main__":
    main()

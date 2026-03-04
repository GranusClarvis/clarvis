#!/usr/bin/env python3
"""Hebbian Memory — thin wrapper. Implementation in clarvis/memory/hebbian_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.hebbian_memory import main  # noqa: F401

if __name__ == "__main__":
    main()

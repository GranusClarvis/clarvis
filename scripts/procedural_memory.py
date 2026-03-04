#!/usr/bin/env python3
"""Procedural Memory — thin wrapper. Implementation in clarvis/memory/procedural_memory.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from clarvis.memory.procedural_memory import *  # noqa: F401,F403
from clarvis.memory.procedural_memory import (  # noqa: F401
    find_procedure, find_code_templates, format_code_templates,
    store_procedure, record_use, learn_from_task, learn_from_failures,
    retire_stale, compose_procedures, list_procedures, library_stats,
    seed_code_templates, main,
)

if __name__ == "__main__":
    main()

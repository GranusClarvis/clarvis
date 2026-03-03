#!/usr/bin/env python3
"""Working Memory — thin wrapper. Implementation in clarvis/memory/working_memory.py."""
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace")
from clarvis.memory.working_memory import *  # noqa: F401,F403
from clarvis.memory.working_memory import get_buffer, attention, SPOTLIGHT_FILE, WORKING_MEM_FILE, main  # noqa: F401

if __name__ == "__main__":
    main()

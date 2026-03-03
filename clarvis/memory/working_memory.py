#!/usr/bin/env python3
"""
Working Memory — Thin shim that delegates to attention.py (unified GWT module).

Previously this was a separate GWT implementation with its own deque buffer.
Now attention.py IS the global workspace: salience competition, decay, broadcast.
This file exists for backward compatibility with cron_autonomous.sh CLI calls:
    working_memory.py add <text> <importance>
    working_memory.py load
    working_memory.py save
    working_memory.py broadcast

All functionality now lives in attention.py's AttentionSpotlight.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from attention import attention, SPOTLIGHT_FILE

# Keep the old state file path for backward-compat reads during transition
WORKING_MEM_FILE = Path("/home/agent/.openclaw/workspace/data/working_memory_state.json")


def get_buffer():
    """Return the unified attention spotlight (backward compat)."""
    return attention


def main():
    """CLI interface — delegates to attention.py."""
    if len(sys.argv) < 2:
        print("Working Memory (delegates to attention.py)")
        print(f"Spotlight: {len(attention.items)} items")
        print(json.dumps({"spotlight": attention.focus_summary()}, indent=2))
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "add":
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        importance = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        item = attention.add(content, importance=importance, source="working_memory")
        print(f"Added to spotlight (importance={importance}, salience={item.salience():.3f})")

    elif cmd == "load":
        attention._load()
        print(f"Loaded: {len(attention.items)} spotlight items")

    elif cmd == "save":
        attention._save()
        print(f"Saved: {len(attention.items)} items to {SPOTLIGHT_FILE}")

    elif cmd == "broadcast":
        print(json.dumps({"spotlight": attention.focus_summary()}, indent=2))

    elif cmd == "spotlight":
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        if content:
            attention.submit(content, source="spotlight_override", importance=0.95, relevance=0.9, boost=0.5)
            print(f"Spotlight set: {content[:60]}")
        else:
            print(attention.focus_summary())

    elif cmd == "spotlight-get":
        focus = attention.focus()
        if focus:
            print(f"Current spotlight: {focus[0]['content'][:100]}")
        else:
            print("Current spotlight: None")

    elif cmd == "clear":
        attention.clear()
        print("Working memory cleared")

    elif cmd == "clean":
        result = attention.tick()
        print(f"Cleaned: evicted={result['evicted']}, remaining={result['total']}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: add, load, save, broadcast, spotlight, spotlight-get, clear, clean")


if __name__ == "__main__":
    main()

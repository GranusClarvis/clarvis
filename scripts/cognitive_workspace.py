#!/usr/bin/env python3
"""
Cognitive Workspace — BRIDGE wrapper.

Canonical implementation: clarvis/memory/cognitive_workspace.py
This file re-exports all public API for backward compatibility with scripts
that do `from cognitive_workspace import workspace`.
"""

import json
import sys

# Re-export from spine
from clarvis.memory.cognitive_workspace import (  # noqa: F401
    CognitiveWorkspace,
    WorkspaceItem,
    workspace,
    ACTIVE_CAPACITY,
    WORKING_CAPACITY,
    DORMANT_CAPACITY,
    REUSE_RELEVANCE_THRESHOLD,
    DORMANT_SUMMARY_MAX,
)


# === CLI (preserved for backward-compatible invocation) ===
if __name__ == "__main__":
    ws = CognitiveWorkspace()

    if len(sys.argv) < 2:
        print("Cognitive Workspace — Hierarchical Active Memory Management")
        print(json.dumps(ws.stats(), indent=2))
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        print(json.dumps(ws.stats(), indent=2))

    elif cmd == "health":
        print(json.dumps(ws.health(), indent=2))

    elif cmd == "set-task":
        task = sys.argv[2] if len(sys.argv) > 2 else "unnamed task"
        result = ws.set_task(task)
        print(json.dumps(result, indent=2))

    elif cmd == "close-task":
        outcome = sys.argv[2] if len(sys.argv) > 2 else "success"
        lesson = sys.argv[3] if len(sys.argv) > 3 else ""
        result = ws.close_task(outcome=outcome, lesson=lesson)
        print(json.dumps(result, indent=2))

    elif cmd == "ingest":
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        tier = sys.argv[3] if len(sys.argv) > 3 else "working"
        importance = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        if content:
            item = ws.ingest(content, tier=tier, importance=importance)
            print(f"Ingested: {item.id} → {item.tier}")
        else:
            print("Usage: cognitive_workspace.py ingest <content> [tier] [importance]")

    elif cmd == "context":
        budget = int(sys.argv[2]) if len(sys.argv) > 2 else 600
        task = sys.argv[3] if len(sys.argv) > 3 else ""
        print(ws.get_context(budget=budget, task_query=task or None))

    elif cmd == "sync":
        imported = ws.sync_from_spotlight()
        print(f"Synced {imported} items from attention spotlight")

    elif cmd == "reuse-rate":
        rate = ws.reuse_rate()
        print(f"Memory reuse rate: {rate:.1%} (target: 58.6%)")
        print(f"  Hits: {ws._reuse_hits}, Total: {ws._reuse_total}")

    elif cmd == "buffers":
        sizes = ws._buffer_sizes()
        print(f"Active:  {sizes['active']}/{ACTIVE_CAPACITY}")
        print(f"Working: {sizes['working']}/{WORKING_CAPACITY}")
        print(f"Dormant: {sizes['dormant']}/{DORMANT_CAPACITY}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: stats, health, set-task, close-task, ingest, context, sync, reuse-rate, buffers")

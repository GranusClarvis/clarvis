#!/usr/bin/env python3
"""
DEPRECATED: Core logic moved to clarvis.orch.queue_writer (spine migration 2026-04-04).
This wrapper delegates to the spine module for backward compatibility.

New code should use: from clarvis.orch.queue_writer import add_task, add_tasks
"""

import sys

# Re-export all public API from spine module
from clarvis.orch.queue_writer import (  # noqa: F401
    add_task,
    add_tasks,
    add_task as addTask,
    archive_completed,
    ensure_subtasks_for_tag,
    mark_task_complete,
    mark_task_in_progress,
    tasks_added_today,
    QUEUE_FILE,
    STATE_FILE,
    MAX_AUTO_TASKS_PER_DAY,
    SIMILARITY_THRESHOLD,
)


if __name__ == "__main__":
    print("DEPRECATION: Use 'python3 -m clarvis queue <command>' instead of 'python3 scripts/queue_writer.py'.", file=sys.stderr)
    if len(sys.argv) < 2:
        print("Usage:")
        print("  queue_writer.py add <task> [--priority P0|P1] [--source name]")
        print("  queue_writer.py status")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "add":
        task = sys.argv[2] if len(sys.argv) > 2 else ""
        priority = "P0"
        source = "manual"
        for i, arg in enumerate(sys.argv):
            if arg == "--priority" and i + 1 < len(sys.argv):
                priority = sys.argv[i + 1]
            if arg == "--source" and i + 1 < len(sys.argv):
                source = sys.argv[i + 1]
        if task:
            added = add_task(task, priority=priority, source=source)
            print(f"{'Added' if added else 'Skipped (duplicate or cap)'}: {task[:80]}")
        else:
            print("No task text provided")

    elif cmd == "status":
        count = tasks_added_today()
        print(f"Auto-generated tasks today: {count}/{MAX_AUTO_TASKS_PER_DAY}")

    elif cmd == "archive":
        archived = archive_completed()
        print(f"Archived {archived} completed items from QUEUE.md")

    else:
        print(f"Unknown command: {cmd}")

"""clarvis queue — evolution queue management.

Wraps scripts/queue_writer.py for task injection and
reads QUEUE.md directly for display operations.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
QUEUE_FILE = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
QUEUE_ARCHIVE = WORKSPACE / "memory" / "evolution" / "QUEUE_ARCHIVE.md"


@app.command("next")
def next_task():
    """Show the next P0 task from the evolution queue."""
    if not QUEUE_FILE.exists():
        print("No queue file found.")
        raise typer.Exit(1)

    content = QUEUE_FILE.read_text()
    # Find the P0 section and extract first unchecked task
    in_p0 = False
    for line in content.splitlines():
        if "## P0" in line:
            in_p0 = True
            continue
        if in_p0 and line.startswith("## "):
            break  # Left P0 section
        if in_p0 and re.match(r"^- \[ \]", line):
            # Extract task tag and description
            match = re.match(r"^- \[ \] \[(\w+)\] (.+)", line)
            if match:
                tag, desc = match.group(1), match.group(2)
                print(f"[{tag}] {desc[:200]}")
            else:
                print(line[6:])  # Strip "- [ ] "
            return

    print("No P0 tasks pending.")


@app.command()
def status():
    """Show queue summary — counts by priority and section."""
    if not QUEUE_FILE.exists():
        print("No queue file found.")
        raise typer.Exit(1)

    content = QUEUE_FILE.read_text()

    pending = len(re.findall(r"^- \[ \]", content, re.MULTILINE))
    completed = len(re.findall(r"^- \[x\]", content, re.MULTILINE))

    # Count by section
    current_section = "Unknown"
    section_counts = {}
    for line in content.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
        elif re.match(r"^- \[ \]", line):
            section_counts[current_section] = section_counts.get(current_section, 0) + 1

    print(f"Queue: {pending} pending, {completed} completed")
    print()
    for section, count in section_counts.items():
        print(f"  {section}: {count}")

    # Check archive
    if QUEUE_ARCHIVE.exists():
        archive_content = QUEUE_ARCHIVE.read_text()
        archived = len(re.findall(r"^- \[x\]", archive_content, re.MULTILINE))
        print(f"\nArchive: {archived} completed tasks")


@app.command()
def add(
    task: str,
    priority: str = typer.Option("P1", "--priority", "-p", help="Priority: P0, P1, P2, or Backlog"),
    source: str = typer.Option("cli", "--source", "-s", help="Source identifier"),
):
    """Add a task to the evolution queue."""
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from queue_writer import add_task
    added = add_task(task, priority=priority, source=source)
    if added:
        print(f"Added to {priority}: {task}")
    else:
        print("Not added (duplicate or daily cap reached).")


@app.command()
def archive():
    """Archive completed tasks from QUEUE.md to QUEUE_ARCHIVE.md."""
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from queue_writer import archive_completed
    count = archive_completed()
    print(f"Archived {count} completed task(s).")


# ---------------------------------------------------------------------------
# Queue Engine v2 commands (sidecar state management)
# ---------------------------------------------------------------------------

@app.command("engine-stats")
def engine_stats():
    """Show queue engine health metrics (sidecar state)."""
    import json as _json
    from clarvis.orch.queue_engine import engine
    s = engine.stats()
    print(_json.dumps(s, indent=2))


@app.command("engine-select")
def engine_select():
    """Select the next eligible task via the queue engine."""
    import json as _json
    from clarvis.orch.queue_engine import engine
    task = engine.select_next()
    if task:
        print(_json.dumps(task, indent=2, default=str))
    else:
        print("No eligible tasks.")


@app.command("engine-reconcile")
def engine_reconcile():
    """Reconcile QUEUE.md with sidecar state and show all tasks."""
    from clarvis.orch.queue_engine import engine
    tasks, _ = engine.reconcile()
    for t in tasks:
        print(f"[{t['tag']}] state={t['state']} attempts={t['attempts']} priority={t['priority']}")

#!/usr/bin/env python3
"""
Shared QUEUE.md writer — single entry point for all auto-generated task injection.

Prevents duplicate tasks, coordinates concurrent writers, caps daily auto-tasks.

Usage:
    from queue_writer import add_task, add_tasks

    # Add a single task
    add_task("Fix the bug in brain.py", priority="P0", source="self_model")

    # Add multiple tasks (deduped as a batch)
    add_tasks(["task1", "task2"], priority="P1", source="goal_tracker")

CLI:
    python3 queue_writer.py add "Fix something" --priority P0 --source manual
    python3 queue_writer.py status  # Show today's auto-generated count
"""

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timezone

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
STATE_FILE = "/home/agent/.openclaw/workspace/data/queue_writer_state.json"
MAX_AUTO_TASKS_PER_DAY = 5
SIMILARITY_THRESHOLD = 0.5  # Word overlap ratio to consider a duplicate


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"date": "", "tasks_added_today": 0, "task_hashes": []}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _word_set(text: str) -> set:
    """Extract a set of meaningful words from text (lowercase, no stopwords)."""
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                 "to", "of", "in", "for", "on", "with", "at", "by", "from",
                 "and", "or", "not", "this", "that", "it", "as", "do", "if"}
    words = set(re.findall(r'[a-z]+', text.lower()))
    return words - stopwords


def _word_overlap(text1: str, text2: str) -> float:
    """Compute word overlap ratio between two texts."""
    words1 = _word_set(text1)
    words2 = _word_set(text2)
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    smaller = min(len(words1), len(words2))
    return len(intersection) / smaller if smaller > 0 else 0.0


def _read_queue() -> str:
    """Read QUEUE.md content."""
    if not os.path.exists(QUEUE_FILE):
        return ""
    with open(QUEUE_FILE) as f:
        return f.read()


def _extract_all_items(content: str) -> list:
    """Extract ALL task items from QUEUE.md (both checked and unchecked)."""
    items = []
    for line in content.split("\n"):
        # Match both - [ ] and - [x] items
        m = re.match(r'^- \[\s]\] (.+)', line)
        if m:
            items.append(m.group(1))
    return items


def _is_duplicate(new_task: str, existing_items: list) -> bool:
    """Check if a task is semantically similar to any existing item."""
    for existing in existing_items:
        overlap = _word_overlap(new_task, existing)
        if overlap >= SIMILARITY_THRESHOLD:
            return True
    return False


def add_task(task: str, priority: str = "P0", source: str = "unknown") -> bool:
    """Add a single task to QUEUE.md with deduplication and daily cap.

    Args:
        task: Task description text
        priority: "P0" or "P1" (which section to add under)
        source: Who is generating this task (for tracking)

    Returns:
        True if task was added, False if skipped (duplicate or cap reached)
    """
    return len(add_tasks([task], priority=priority, source=source)) > 0


def add_tasks(tasks: list, priority: str = "P0", source: str = "unknown") -> list:
    """Add multiple tasks to QUEUE.md with deduplication, atomic writes, daily cap.

    Args:
        tasks: List of task description strings
        priority: "P0" or "P1" (which section to add under)
        source: Who is generating these tasks (for tracking)

    Returns:
        List of tasks that were actually added (after dedup and cap filtering)
    """
    if not tasks:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Atomic file lock to prevent race conditions
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Load state and reset daily counter if new day
        state = _load_state()
        if state["date"] != today:
            state = {"date": today, "tasks_added_today": 0, "task_hashes": []}

        # Check daily cap
        remaining_cap = MAX_AUTO_TASKS_PER_DAY - state["tasks_added_today"]
        if remaining_cap <= 0:
            return []

        # Read existing queue items + archive for deduplication
        content = _read_queue()
        existing_items = _extract_all_items(content)

        # Also check archive to prevent re-adding completed/researched topics
        archive_file = os.path.join(os.path.dirname(QUEUE_FILE), "QUEUE_ARCHIVE.md")
        if os.path.exists(archive_file):
            with open(archive_file) as f:
                archive_items = _extract_all_items(f.read())
            existing_items.extend(archive_items)

        # Filter: deduplicate against existing items + archive
        new_tasks = []
        for task in tasks:
            if len(new_tasks) >= remaining_cap:
                break
            if not task or len(task.strip()) < 10:
                continue
            if _is_duplicate(task, existing_items):
                continue
            # Also check against tasks we're about to add (intra-batch dedup)
            if _is_duplicate(task, new_tasks):
                continue
            new_tasks.append(task)

        if not new_tasks:
            return []

        # Find insertion point for the priority section
        lines = content.split("\n")
        section_header = f"## {priority}"
        insert_idx = None
        for i, line in enumerate(lines):
            if section_header in line:
                insert_idx = i + 1
                break

        if insert_idx is None:
            # Section not found — append at end
            lines.append(f"\n{section_header}")
            insert_idx = len(lines)

        # Skip sub-headers and blank lines after section header
        while insert_idx < len(lines) and (
            lines[insert_idx].startswith("###") or lines[insert_idx].strip() == ""
        ):
            insert_idx += 1

        # Build task lines with source tag
        task_lines = []
        for task in new_tasks:
            # Strip existing checkbox prefix if present
            task_clean = re.sub(r'^- \[\s]\] ', '', task).strip()
            task_lines.append(f"- [ ] [{source.upper()} {today}] {task_clean}")

        # Insert tasks
        for task_line in reversed(task_lines):
            lines.insert(insert_idx, task_line)

        # Write atomically
        with open(QUEUE_FILE, "w") as f:
            f.write("\n".join(lines))

        # Update state
        state["tasks_added_today"] += len(new_tasks)
        _save_state(state)

        return new_tasks

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def ensure_subtasks_for_tag(parent_tag: str, subtasks: list[str], source: str = "auto_split") -> bool:
    """Ensure a parent task in QUEUE.md has subtasks.

    Used as a self-healing mechanism when the preflight task sizer defers an
    oversized item to a sprint slot. If the item has no indented subtasks,
    we add a small canonical breakdown so autonomous cycles can make progress.

    Args:
        parent_tag: Tag inside the first brackets, e.g. "ACTR_WIRING".
        subtasks: List of subtask strings (already include their own tags or not).
        source: Marker for where the subtasks came from.

    Returns:
        True if subtasks were inserted, False if skipped (already present / not found).
    """
    if not parent_tag or not subtasks:
        return False

    # Atomic file lock to prevent race conditions
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        content = _read_queue()
        if not content:
            return False

        lines = content.split("\n")

        # Find the parent line. We match the explicit tag first.
        parent_re = re.compile(r"^\- \[[\s]\] \[" + re.escape(parent_tag) + r"\]")
        parent_idx = None
        for i, line in enumerate(lines):
            if parent_re.search(line):
                parent_idx = i
                break

        if parent_idx is None:
            return False

        # Check if subtasks already exist (indented checklist items directly under parent)
        j = parent_idx + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j < len(lines) and re.match(r"^\s{2,}\- \[\s]\] ", lines[j]):
            return False  # already has subtasks

        # Insert subtasks immediately under parent
        insert_at = parent_idx + 1
        stamped = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        to_insert = []
        for st in subtasks:
            st_clean = re.sub(r"^\- \[\s]\] ", "", st).strip()
            if not st_clean:
                continue
            # Keep indentation consistent with existing manual subtasks (2 spaces)
            to_insert.append(f"  - [ ] [{source.upper()} {stamped}] {st_clean}")

        if not to_insert:
            return False

        lines[insert_at:insert_at] = to_insert

        with open(QUEUE_FILE, "w") as f:
            f.write("\n".join(lines))

        return True

    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            lock_fd.close()


def archive_completed():
    """Move all [x] completed items from QUEUE.md to QUEUE_ARCHIVE.md.

    Called at end of each heartbeat postflight to keep QUEUE.md lean.
    Deduplicates against existing archive entries.

    Returns number of items archived.
    """
    archive_file = os.path.join(os.path.dirname(QUEUE_FILE), "QUEUE_ARCHIVE.md")
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        content = _read_queue()
        if not content:
            return 0

        # Extract completed items and their full lines
        completed = []
        new_lines = []
        for line in content.split("\n"):
            m = re.match(r'^- \[x\] (.+)', line.strip())
            if m:
                completed.append(m.group(1))
            else:
                new_lines.append(line)

        if not completed:
            return 0

        # Read existing archive for dedup
        archive_content = ""
        if os.path.exists(archive_file):
            with open(archive_file) as f:
                archive_content = f.read()

        # Append new items to archive
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_entries = []
        for item in completed:
            if item[:50] not in archive_content:
                archive_entries.append(f"- [x] {item}")

        if archive_entries:
            with open(archive_file, "a") as f:
                f.write(f"\n## Archived {today}\n")
                f.write("\n".join(archive_entries) + "\n")

        # Rewrite QUEUE.md without completed items
        with open(QUEUE_FILE, "w") as f:
            f.write("\n".join(new_lines))

        return len(completed)

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def mark_task_in_progress(tag: str) -> bool:
    """Mark a task as in-progress by changing [ ] to [~].

    Used when auto-splitting an oversized task — the parent stays in queue
    but is marked as decomposed/in-progress so it doesn't keep being
    reconsidered as a fresh candidate each heartbeat.

    Args:
        tag: The task tag (e.g., "ACTR_WIRING")

    Returns:
        True if marked, False if not found or already marked.
    """
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        content = _read_queue()
        lines = content.split("\n")
        found = False
        marked = False

        for i, line in enumerate(lines):
            # Match unchecked task with the given tag
            m = re.match(rf'^- \[\s*\] .*\[{re.escape(tag)}\]', line.strip())
            if m:
                found = True
                # Change [ ] to [~]
                new_line = line.replace("- [ ]", "- [~]", 1)
                if new_line != line:
                    lines[i] = new_line
                    marked = True
                    break

        if marked:
            with open(QUEUE_FILE, "w") as f:
                f.write("\n".join(lines))

        return marked

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def tasks_added_today() -> int:
    """How many auto-generated tasks were added today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = _load_state()
    if state["date"] != today:
        return 0
    return state["tasks_added_today"]


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

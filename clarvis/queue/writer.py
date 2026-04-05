"""
Queue Writer — write-side queue management for QUEUE.md.

Canonical location: clarvis/queue/writer.py (moved from clarvis/orch/ 2026-04-04).

Handles task injection, deduplication, daily caps, archiving, and subtask
management. Complements engine.py (runtime state machine) by owning
the human/automated task creation side.

Usage:
    from clarvis.queue import add_task, add_tasks
    from clarvis.queue.writer import add_task, add_tasks

    add_task("Fix the bug in brain.py", priority="P0", source="self_model")
    add_tasks(["task1", "task2"], priority="P1", source="goal_tracker")

CLI (via spine):
    python3 -m clarvis queue add "Fix something" --priority P0 --source manual
    python3 -m clarvis queue status
"""

import fcntl
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
QUEUE_FILE = os.path.join(_WS, "memory", "evolution", "QUEUE.md")
STATE_FILE = os.path.join(_WS, "data", "queue_writer_state.json")


def _sync_sidecar_add(tags_and_priorities: list[tuple[str, str]]) -> None:
    """Create sidecar entries for newly added tasks so they're immediately visible to the engine.

    Called after add_task()/add_tasks() writes to QUEUE.md. This prevents
    sidecar drift: without this, new tasks only appear in the sidecar on
    the next reconcile() call (i.e., next heartbeat), and any soak_check()
    or stats() call in between would report 'missing_in_sidecar'.

    Args:
        tags_and_priorities: list of (tag, priority) tuples for newly added tasks.
    """
    if not tags_and_priorities:
        return
    try:
        from clarvis.queue.engine import _load_sidecar, _save_sidecar, _default_entry
        sidecar = _load_sidecar()
        changed = False
        for tag, priority in tags_and_priorities:
            if tag and tag not in sidecar:
                sidecar[tag] = _default_entry(tag, priority)
                changed = True
        if changed:
            _save_sidecar(sidecar)
    except Exception:
        pass  # Best-effort: reconcile() will catch up on next heartbeat


def _sync_sidecar_complete(tag: str) -> None:
    """Mark a sidecar entry as succeeded when the writer marks a task [x].

    Keeps sidecar in sync with QUEUE.md so mark_task_complete() callers
    (e.g., cron_research.sh) that don't use engine.mark_succeeded() directly
    still update the V2 state machine.
    """
    if not tag:
        return
    try:
        from clarvis.queue.engine import _load_sidecar, _save_sidecar, _now_iso
        sidecar = _load_sidecar()
        if tag in sidecar:
            entry = sidecar[tag]
            if entry.get("state") not in ("succeeded",):
                entry["state"] = "succeeded"
                entry["updated_at"] = _now_iso()
                entry["failure_reason"] = None
                _save_sidecar(sidecar)
    except Exception:
        pass  # Best-effort


def _extract_tag_from_text(text: str) -> Optional[str]:
    """Extract [TAG] from task text for sidecar sync."""
    m = re.match(r"\[([A-Z][A-Za-z0-9_:.-]+)\]", text.strip())
    return m.group(1) if m else None
MAX_AUTO_TASKS_PER_DAY = 5
SIMILARITY_THRESHOLD = 0.5  # Word overlap ratio to consider a duplicate

# Patterns that identify structural/line-count refactor tasks.
# Auto-generated tasks matching these are blocked unless from a safe source.
_STRUCTURAL_PATTERNS = re.compile(
    r'(?i)'
    r'(?:decompos\w*\s+(?:long|oversized|large)\s+func)|'
    r'(?:split\s+(?:all\s+)?(?:oversized|long)\s+func)|'
    r'(?:<=?\s*\d+\s*lines?\b)|'
    r'(?:function.length)|'
    r'(?:reduce\s+func\w*\s+to\s+(?:target\s+)?line)|'
    r'(?:DECOMPOSE_LONG_FUNCTIONS)'
)


def _is_structural_refactor_task(task: str) -> bool:
    """Check if a task description is a structural/line-count refactor.

    Returns True for tasks driven by line-count aesthetics rather than
    real maintenance concern. See Phase 5 of the Decomposition Remediation plan.
    """
    return bool(_STRUCTURAL_PATTERNS.search(task))


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
        m = re.match(r'^- \[[ x~]\] (.+)', line)
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


_RESEARCH_PATTERN = re.compile(
    r'(?i)(?:^|\[)\s*(?:research|bundle|study|investigate|explore)\b'
)


def _is_research_topic_completed(task: str, source: str = "unknown") -> bool:
    """Check if a research-like task covers a topic already completed in the topic registry.

    This is the injection-time completion lock: even if word-overlap dedup misses a
    semantically equivalent topic, the canonical topic registry will catch it.
    Only applies to research-flavored tasks (Research:, Bundle, etc.).

    Manual sources (manual, cli, user) bypass the lock — this is the explicit
    reopening path required by the completion lock protocol.
    """
    if source in ("manual", "cli", "user"):
        return False  # Explicit override allowed
    if not _RESEARCH_PATTERN.search(task):
        return False
    try:
        import importlib.util
        _novelty_path = os.path.join(_WS, "scripts", "evolution", "research_novelty.py")
        spec = importlib.util.spec_from_file_location("research_novelty", _novelty_path)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        TopicRegistry = _mod.TopicRegistry
        registry = TopicRegistry()
        match = registry.find_matching(task)
        if match is None:
            return False
        # Block if topic has been researched at least once (completion lock).
        # REFINEMENT and ALREADY_KNOWN are both blocked at injection time.
        # Only NEW (no registry match) passes through for auto-sources.
        return match.research_count >= 1
    except Exception:
        return False  # Registry unavailable — don't block


def _get_succeeded_task_texts() -> list:
    """Extract task tags from sidecar entries in 'succeeded' state.

    Covers the window between task completion and archive_completed() running.
    The sidecar is keyed by tag (e.g., QUEUE_V2_RESEARCH_COMPLETION_LOCK),
    which is also embedded in QUEUE.md task text, so word-overlap dedup works.
    """
    sidecar_file = os.path.join(_WS, "data", "queue_state.json")
    if not os.path.exists(sidecar_file):
        return []
    try:
        with open(sidecar_file) as f:
            sidecar = json.load(f)
        return [
            tag.replace("_", " ")
            for tag, entry in sidecar.items()
            if entry.get("state") == "succeeded"
        ]
    except Exception:
        return []


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

    # Mode gating: check if task injection is allowed by current runtime mode
    try:
        from clarvis.runtime.mode import should_allow_auto_task_injection
        filtered_tasks = []
        for task in tasks:
            allowed, _reason = should_allow_auto_task_injection(task, source)
            if allowed:
                filtered_tasks.append(task)
        tasks = filtered_tasks
        if not tasks:
            return []
    except ImportError:
        pass  # Mode system not installed yet — allow all

    # Provenance gate: structural refactor tasks require manual/audit source.
    # Auto-generated structural tasks are blocked to prevent metric-cult behavior.
    # See: docs/DECOMPOSITION_REMEDIATION_AND_STRUCTURAL_POLICY_PLAN_2026-03-29.md
    _STRUCTURAL_SAFE_SOURCES = frozenset({"manual", "audit", "user", "cli"})
    if source not in _STRUCTURAL_SAFE_SOURCES:
        tasks = [t for t in tasks if not _is_structural_refactor_task(t)]
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

        # Also check sidecar for succeeded tasks not yet archived
        succeeded_texts = _get_succeeded_task_texts()
        existing_items.extend(succeeded_texts)

        # Filter: deduplicate against existing items + archive + succeeded sidecar
        new_tasks = []
        for task in tasks:
            if len(new_tasks) >= remaining_cap:
                break
            if not task or len(task.strip()) < 10:
                continue
            if _is_duplicate(task, existing_items):
                continue
            # Research completion lock: check topic registry for research-like tasks
            if _is_research_topic_completed(task, source):
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
            task_clean = re.sub(r'^- \[[ x~]\] ', '', task).strip()
            task_lines.append(f"- [ ] [{source.upper()} {today}] {task_clean}")

        # Insert tasks
        for task_line in reversed(task_lines):
            lines.insert(insert_idx, task_line)

        # Write atomically
        with open(QUEUE_FILE, "w") as f:
            f.write("\n".join(lines))

        # Sync sidecar so new tasks are immediately visible to engine
        tags_priorities = []
        for task in new_tasks:
            tag = _extract_tag_from_text(task)
            if tag:
                tags_priorities.append((tag, priority))
        _sync_sidecar_add(tags_priorities)

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
        if j < len(lines) and re.match(r"^\s{2,}\- \[[ x~]\] ", lines[j]):
            return False  # already has subtasks

        # Insert subtasks immediately under parent
        insert_at = parent_idx + 1
        stamped = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        to_insert = []
        for st in subtasks:
            st_clean = re.sub(r"^\- \[[ x~]\] ", "", st).strip()
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


def mark_task_complete(task_text: str, annotation: str, queue_file: str = QUEUE_FILE, archive_file: str | None = None):
    """Mark a task complete in QUEUE.md with an annotation.

    Returns:
      - "marked" if task was found and marked [x]
      - "archived" if it already appears in QUEUE_ARCHIVE.md
      - False if not found

    Matching strategy:
      1) Prefer exact tag match when task_text contains [TAG]
      2) Fallback to prefix substring match
    """
    with open(queue_file, 'r') as f:
        lines = f.readlines()

    task_prefix = task_text[:60]
    m = re.match(r"\[([^\]]+)\]", task_text.strip())
    tag = m.group(1) if m else None

    if tag:
        tag_re = re.compile(rf"^\- \[ \] \[{re.escape(tag)}\](?=\s|$)")
        for i, line in enumerate(lines):
            if tag_re.search(line):
                lines[i] = line.replace("- [ ] ", "- [x] ", 1).rstrip() + f" ({annotation})\n"
                with open(queue_file, 'w') as f:
                    f.writelines(lines)
                _sync_sidecar_complete(tag)
                return "marked"

    for i, line in enumerate(lines):
        if line.strip().startswith("- [ ] ") and task_prefix in line:
            lines[i] = line.replace("- [ ] ", "- [x] ", 1).rstrip() + f" ({annotation})\n"
            with open(queue_file, 'w') as f:
                f.writelines(lines)
            # Try to extract tag from the matched line for sidecar sync
            line_tag = _extract_tag_from_text(line.strip().replace("- [ ] ", "", 1))
            _sync_sidecar_complete(line_tag)
            return "marked"

    if archive_file and os.path.exists(archive_file):
        with open(archive_file, 'r') as f:
            archive = f.read()
        if task_prefix in archive:
            return "archived"
    return False


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
        completed_tags = []
        new_lines = []
        for line in content.split("\n"):
            m = re.match(r'^- \[x\] (.+)', line.strip())
            if m:
                item_text = m.group(1)
                completed.append(item_text)
                tag = _extract_tag_from_text(item_text)
                if tag:
                    completed_tags.append(tag)
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

        # Sync sidecar: ensure archived tags are marked succeeded
        for tag in completed_tags:
            _sync_sidecar_complete(tag)

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

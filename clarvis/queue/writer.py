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

import time as _time

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
QUEUE_FILE = os.path.join(_WS, "memory", "evolution", "QUEUE.md")


def _flock_with_timeout(fd, timeout_s=30):
    """Acquire exclusive flock with timeout (Phase 4 safety hardening).

    Raises TimeoutError if lock cannot be acquired within timeout_s.
    """
    deadline = _time.monotonic() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (IOError, OSError):
            if _time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Could not acquire queue writer lock within {timeout_s}s"
                )
            _time.sleep(0.1)
STATE_FILE = os.path.join(_WS, "data", "queue_writer_state.json")


def _sync_sidecar_add(tags_and_priorities: list[tuple[str, str]], source: str = "unknown") -> None:
    """Create sidecar entries for newly added tasks so they're immediately visible to the engine.

    Called after add_task()/add_tasks() writes to QUEUE.md. This prevents
    sidecar drift: without this, new tasks only appear in the sidecar on
    the next reconcile() call (i.e., next heartbeat), and any soak_check()
    or stats() call in between would report 'missing_in_sidecar'.

    Args:
        tags_and_priorities: list of (tag, priority) tuples for newly added tasks.
        source: provenance string propagated into the sidecar entry.
    """
    if not tags_and_priorities:
        return
    try:
        from clarvis.queue.engine import _load_sidecar, _save_sidecar, _default_entry
        sidecar = _load_sidecar()
        changed = False
        for tag, priority in tags_and_priorities:
            if tag and tag not in sidecar:
                entry = _default_entry(tag, priority)
                entry["source"] = source
                sidecar[tag] = entry
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
    """Extract [TAG] from task text for sidecar sync. Handles **bold** wrapping
    and skips leading status markers like [UNVERIFIED] (delegates to engine)."""
    from clarvis.queue.engine import _extract_tag
    return _extract_tag(text)
MAX_AUTO_TASKS_PER_DAY = 5
SIMILARITY_THRESHOLD = 0.5  # Word overlap ratio to consider a duplicate

# Priority section caps per docs/PROJECT_LANES.md Rule 4.
# Auto-injected tasks are refused when a section exceeds its cap.
# Manual/user sources bypass caps.
P0_CAP = 10
P1_CAP = 15

# Phase 0 audit-program override: sources that record *evidence-backed* audit
# findings (see docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md §5)
# may exceed caps so the audit cannot silently suppress required follow-ups.
# A headroom ceiling still applies — absent ceiling, audit sources could
# runaway-fill. Tasks added via these sources always carry an explicit
# [AUDIT] or [AUDIT_PHASE_*] tag so they can be triaged later.
AUDIT_SOURCES = frozenset({
    "audit", "audit_phase_0", "audit_phase_1", "audit_phase_2",
    "audit_phase_3", "audit_phase_4", "audit_phase_5", "audit_phase_6",
    "audit_phase_7", "audit_phase_8", "audit_phase_9", "audit_phase_10",
    "audit_phase_11", "audit_reconciliation", "audit_meta",
})
AUDIT_CAP_HEADROOM = 10  # above the P0/P1 cap; beyond this even audit tasks are rejected.

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


def _count_unchecked_by_section(content: str) -> dict[str, int]:
    """Count unchecked tasks per priority section in QUEUE.md."""
    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    current = "P2"
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## P0"):
            current = "P0"
        elif stripped.startswith("## P1"):
            current = "P1"
        elif stripped.startswith("## P2"):
            current = "P2"
        elif stripped.startswith("## "):
            current = None
        elif current and re.match(r"^- \[ \] ", stripped):
            counts[current] = counts.get(current, 0) + 1
    return counts


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
    """Check if a research-like task is a true repeat using scope-aware classification.

    Uses RepeatClassifier for smart repeat detection that distinguishes:
      - NOVEL:         No matching topic → allow
      - SCOPE_SHIFT:   Same topic, different scope → allow
      - SHALLOW_PRIOR: Same topic, prior was shallow → allow
      - REPEAT:        Same topic, same scope, recent → block

    Manual sources (manual, cli, user) bypass via RepeatClassifier's source check.
    """
    if not _RESEARCH_PATTERN.search(task):
        return False
    try:
        import importlib.util
        _classifier_path = os.path.join(_WS, "scripts", "evolution", "repeat_classifier.py")
        spec = importlib.util.spec_from_file_location("repeat_classifier", _classifier_path)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        classifier = _mod.RepeatClassifier()
        return classifier.is_repeat(task, source=source)
    except Exception:
        return False  # Classifier unavailable — don't block


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

    # Queue auto-fill gate: block all non-user auto-injection when OFF.
    # User-directed sources (manual, cli, telegram, etc.) always pass.
    _USER_SOURCES = frozenset({"manual", "user", "cli", "telegram", "discord", "chat", "human", "prompt"})
    _RESEARCH_SOURCES = frozenset({"research_bridge", "research_discovery", "research"})
    if source.lower() not in _USER_SOURCES and source.lower() not in _RESEARCH_SOURCES:
        try:
            from clarvis.research_config import is_enabled
            if not is_enabled("queue_auto_fill"):
                return []
        except ImportError:
            pass  # Config module not available — allow (backward compat)

    # Research gate: block research-source injections when research auto-fill is OFF.
    # This prevents any code path from sneaking research tasks into the queue.
    if source.lower() in _RESEARCH_SOURCES:
        try:
            from clarvis.research_config import is_enabled
            if not is_enabled("research_auto_fill"):
                return []
        except ImportError:
            pass  # Config module not available — allow (backward compat)

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
        _flock_with_timeout(lock_fd)

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

        # Priority cap enforcement (Rule 4, docs/PROJECT_LANES.md).
        # Auto-injected tasks are refused when the target section exceeds its cap.
        # User/manual sources bypass caps so the operator can always add tasks.
        # Audit-program sources (Phase 0 override) bypass the base cap up to
        # AUDIT_CAP_HEADROOM — audit findings must not be silently suppressed
        # just because the queue is full. See docs/internal/audits/
        # CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md §5.
        src_lc = source.lower()
        if src_lc not in _USER_SOURCES:
            section_counts = _count_unchecked_by_section(content)
            cap = {"P0": P0_CAP, "P1": P1_CAP}.get(priority)
            if cap is not None:
                cap_ceiling = cap
                if src_lc in AUDIT_SOURCES:
                    cap_ceiling = cap + AUDIT_CAP_HEADROOM
                if section_counts.get(priority, 0) >= cap_ceiling:
                    return []

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

        # Build task lines with provenance suffix (Phase 13 provenance)
        task_lines = []
        for task in new_tasks:
            # Strip existing checkbox prefix if present
            task_clean = re.sub(r'^- \[[ x~]\] ', '', task).strip()
            # Strip legacy prefix-style provenance [SOURCE DATE] if present
            task_clean = re.sub(r'^\[[A-Z_]+ \d{4}-\d{2}-\d{2}\]\s*', '', task_clean).strip()
            # Strip existing provenance suffix to prevent duplication
            task_clean = re.sub(r'\s*\(added: \d{4}-\d{2}-\d{2}, source: [^)]+\)\s*$', '', task_clean).strip()
            task_lines.append(f"- [ ] {task_clean} (added: {today}, source: {source})")

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
        _sync_sidecar_add(tags_priorities, source=source)

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
        _flock_with_timeout(lock_fd)

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
            to_insert.append(f"  - [ ] {st_clean} (added: {stamped}, source: {source})")

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
      - "already_complete" if task is already [x] (e.g., Claude marked it first)
      - "archived" if it already appears in QUEUE_ARCHIVE.md
      - False if not found

    Matching strategy:
      1) Prefer exact tag match when task_text contains [TAG]
      2) Fallback to prefix substring match
      3) Check if already marked [x] (handles race with Claude Code)
    """
    with open(queue_file, 'r') as f:
        lines = f.readlines()

    task_prefix = task_text[:60]
    m = re.match(r"(?:\*\*)?(\[([^\]]+)\])", task_text.strip())
    tag = m.group(2) if m else None

    # Pass 1: Find unchecked items and mark them
    if tag:
        tag_re = re.compile(rf"^\- \[ \] (?:\*\*)?\[{re.escape(tag)}\](?=\s|$|\*)")
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

    # Pass 2: Check if already marked [x] (Claude Code may have marked it during its run)
    if tag:
        done_re = re.compile(rf"^\- \[x\] (?:\*\*)?\[{re.escape(tag)}\](?=\s|$|\*)")
        for line in lines:
            if done_re.search(line):
                _sync_sidecar_complete(tag)
                return "already_complete"

    for line in lines:
        if line.strip().startswith("- [x] ") and task_prefix in line:
            return "already_complete"

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

    Self-healing reconciliation: any [ ] line whose tag is marked 'succeeded'
    in the sidecar is flipped to [x] before the archive sweep. This catches
    drift from cases where engine.mark_succeeded() updated the sidecar but
    failed to flip every duplicate in QUEUE.md (e.g., when auto_split spawns
    multiple lines sharing one tag, and the underlying _mark_checkbox only
    flipped count=1 of them). The drift symptom was the runnable_view
    "succeeded but checkbox still [ ]" warning.

    Returns number of items archived.
    """
    archive_file = os.path.join(os.path.dirname(QUEUE_FILE), "QUEUE_ARCHIVE.md")
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        _flock_with_timeout(lock_fd)

        content = _read_queue()
        if not content:
            return 0

        # Self-heal sidecar/QUEUE.md drift: flip [ ] -> [x] for any tag whose
        # sidecar entry is 'succeeded'. Captures duplicates that engine's
        # _mark_checkbox missed (it only flipped count=1) and any other path
        # that updated the sidecar without touching QUEUE.md.
        try:
            from clarvis.queue.engine import _load_sidecar
            sidecar_succeeded = {
                tag for tag, entry in _load_sidecar().items()
                if entry.get("state") == "succeeded"
            }
        except Exception:
            sidecar_succeeded = set()

        if sidecar_succeeded:
            healed_lines = []
            for line in content.split("\n"):
                m = re.match(r'^(\s*)- \[ \] (.+)$', line)
                if m:
                    indent, item_text = m.group(1), m.group(2)
                    tag = _extract_tag_from_text(item_text)
                    if tag and tag in sidecar_succeeded:
                        line = f"{indent}- [x] {item_text} (drift-recovered: {datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
                healed_lines.append(line)
            content = "\n".join(healed_lines)

        # Extract completed items and their full lines.
        #
        # Verification guard for `[UNVERIFIED]` items (added 2026-05-01 after
        # the BunnyBagz Phase-1 false-DONE incident — see
        # `memory/evolution/bunnybagz_realignment_2026-05-01.md`):
        #
        #   - Always log every archived `[UNVERIFIED]` item with its tag, so
        #     the audit trail exists even in default (permissive) mode.
        #   - When env `CLARVIS_QUEUE_UNVERIFIED_GUARD=block` is set, refuse
        #     to archive `[UNVERIFIED]` items unless a sidecar verification
        #     record exists at `data/audit/queue_verifications/<tag>.json`.
        #     Such items stay in QUEUE.md as `[x]` so subsequent operator
        #     review can resolve them (verify or downgrade to `[ ]`).
        #
        # Default mode is `log` so existing in-flight cron isn't disrupted;
        # the operator flips to `block` once `[BB_PHASE1_VERIFICATION_PASS]`
        # lands and the verification-record producer is wired.
        guard_mode = os.environ.get("CLARVIS_QUEUE_UNVERIFIED_GUARD", "log").lower()
        verification_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(QUEUE_FILE))),
            "data", "audit", "queue_verifications",
        )
        audit_log = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(QUEUE_FILE))),
            "monitoring", "queue_unverified_archive.log",
        )

        def _has_verification_record(tag: str) -> bool:
            if not tag:
                return False
            return os.path.exists(os.path.join(verification_dir, f"{tag}.json"))

        def _log_unverified(tag: Optional[str], item_text: str, action: str) -> None:
            try:
                os.makedirs(os.path.dirname(audit_log), exist_ok=True)
                with open(audit_log, "a") as fh:
                    fh.write(json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "tag": tag,
                        "action": action,
                        "guard_mode": guard_mode,
                        "snippet": item_text[:120],
                    }) + "\n")
            except Exception:
                pass

        completed = []
        completed_tags = []
        new_lines = []
        held_unverified = 0
        for line in content.split("\n"):
            m = re.match(r'^\s*- \[x\] (.+)', line)
            if m:
                item_text = m.group(1)
                tag = _extract_tag_from_text(item_text)
                if "[UNVERIFIED]" in item_text:
                    if guard_mode == "block" and not _has_verification_record(tag):
                        _log_unverified(tag, item_text, "held")
                        new_lines.append(line)
                        held_unverified += 1
                        continue
                    _log_unverified(tag, item_text, "archived")
                completed.append(item_text)
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
        _flock_with_timeout(lock_fd)

        content = _read_queue()
        lines = content.split("\n")
        found = False
        marked = False

        for i, line in enumerate(lines):
            # Match unchecked task with the given tag
            m = re.match(rf'^- \[\s*\] .*(?:\*\*)?\[{re.escape(tag)}\]', line.strip())
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


def prune_sidecar(removed_days: int = 30, succeeded_days: int = 90) -> dict:
    """Prune old sidecar entries to bound growth.

    Removes:
      - 'removed' entries older than removed_days (default 30)
      - 'succeeded' entries older than succeeded_days (default 90)

    Returns dict with counts: {"removed": N, "succeeded": N, "total_before": N, "total_after": N}
    """
    try:
        from clarvis.queue.engine import _load_sidecar, _save_sidecar
    except ImportError:
        return {"removed": 0, "succeeded": 0, "total_before": 0, "total_after": 0}

    sidecar = _load_sidecar()
    total_before = len(sidecar)
    now = datetime.now(timezone.utc)
    pruned_removed = 0
    pruned_succeeded = 0
    to_delete = []

    for tag, entry in sidecar.items():
        state = entry.get("state", "")
        updated = entry.get("updated_at", "")
        if not updated:
            continue
        try:
            updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        age_days = (now - updated_dt).days

        if state == "removed" and age_days > removed_days:
            to_delete.append(tag)
            pruned_removed += 1
        elif state == "succeeded" and age_days > succeeded_days:
            to_delete.append(tag)
            pruned_succeeded += 1

    for tag in to_delete:
        del sidecar[tag]

    if to_delete:
        _save_sidecar(sidecar)

    return {
        "removed": pruned_removed,
        "succeeded": pruned_succeeded,
        "total_before": total_before,
        "total_after": len(sidecar),
    }


def tasks_added_today() -> int:
    """How many auto-generated tasks were added today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = _load_state()
    if state["date"] != today:
        return 0
    return state["tasks_added_today"]


def enforce_stale_demotions(stale_hours: int = 48) -> list[str]:
    """Demote in-progress ([~]) tasks that have been stalled for >stale_hours.

    Per docs/PROJECT_LANES.md Rule 5: tasks in-progress for 48h without a
    commit, PR, or artifact get demoted to P2 with a [STALLED] tag.

    Returns list of demoted task descriptions.
    """
    lock_path = QUEUE_FILE + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        _flock_with_timeout(lock_fd)
        content = _read_queue()
        if not content:
            return []

        lines = content.split("\n")
        now = datetime.now(timezone.utc)
        demoted = []
        in_progress_lines = []
        p2_insert_idx = None

        current_section = "P2"
        for i, line in enumerate(lines):
            if "## P0" in line:
                current_section = "P0"
            elif "## P1" in line:
                current_section = "P1"
            elif "## P2" in line:
                current_section = "P2"
                p2_insert_idx = i + 1

            if current_section in ("P0", "P1") and re.match(r"^- \[~\] ", line.strip()):
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                if date_match:
                    try:
                        task_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        age_hours = (now - task_date).total_seconds() / 3600
                        if age_hours >= stale_hours:
                            in_progress_lines.append(i)
                    except ValueError:
                        pass

        if not in_progress_lines or p2_insert_idx is None:
            return []

        for idx in reversed(in_progress_lines):
            original = lines.pop(idx)
            task_text = re.sub(r"^- \[~\] ", "", original.strip())
            if "[STALLED]" not in task_text:
                task_text = f"[STALLED] {task_text}"
            demoted_line = f"- [ ] {task_text}"
            demoted.append(task_text)
            if p2_insert_idx > idx:
                p2_insert_idx -= 1
            lines.insert(p2_insert_idx, demoted_line)

        if demoted:
            with open(QUEUE_FILE, "w") as f:
                f.write("\n".join(lines))

        return demoted

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def queue_health() -> dict:
    """Return queue health metrics for governance monitoring.

    Returns dict with section counts, cap status, and stale task count.
    """
    content = _read_queue()
    counts = _count_unchecked_by_section(content)
    stale = 0
    now = datetime.now(timezone.utc)
    for line in content.split("\n"):
        if re.match(r"^- \[~\] ", line.strip()):
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                try:
                    task_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if (now - task_date).total_seconds() / 3600 >= 48:
                        stale += 1
                except ValueError:
                    pass
    return {
        "p0_count": counts.get("P0", 0),
        "p1_count": counts.get("P1", 0),
        "p2_count": counts.get("P2", 0),
        "p0_cap": P0_CAP,
        "p1_cap": P1_CAP,
        "p0_over_cap": counts.get("P0", 0) > P0_CAP,
        "p1_over_cap": counts.get("P1", 0) > P1_CAP,
        "stale_in_progress": stale,
    }


def backfill_sidecar_sources() -> dict:
    """Backfill sidecar entries that have source='unknown' using queue_runs.jsonl.

    Returns dict with counts: {"backfilled": N, "still_unknown": N}.
    """
    import json as _json
    runs_file = os.path.join(_WS, "data", "queue_runs.jsonl")
    try:
        from clarvis.queue.engine import _load_sidecar, _save_sidecar
    except Exception:
        return {"backfilled": 0, "still_unknown": 0, "error": "engine not available"}

    # Build tag→source map from queue_runs.jsonl
    tag_sources: dict[str, str] = {}
    if os.path.exists(runs_file):
        with open(runs_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                    tag = rec.get("tag", "")
                    src = rec.get("source", "")
                    if tag and src:
                        tag_sources[tag] = src
                except (ValueError, KeyError):
                    continue

    # Also infer source from QUEUE.md provenance suffixes
    content = _read_queue()
    if content:
        for line in content.split("\n"):
            m = re.search(r'\(added: \d{4}-\d{2}-\d{2}, source: ([^)]+)\)', line)
            if m:
                src = m.group(1)
                tag_m = re.search(r'\[([A-Z][A-Z0-9_]+)\]', line)
                if tag_m:
                    tag_sources[tag_m.group(1)] = src

    sidecar = _load_sidecar()
    backfilled = 0
    still_unknown = 0
    for tag, entry in sidecar.items():
        if entry.get("source", "unknown") == "unknown":
            if tag in tag_sources:
                entry["source"] = tag_sources[tag]
                backfilled += 1
            else:
                still_unknown += 1

    if backfilled:
        _save_sidecar(sidecar)

    return {"backfilled": backfilled, "still_unknown": still_unknown}

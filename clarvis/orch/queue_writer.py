"""Backward-compatibility shim — queue_writer moved to clarvis.queue.writer (2026-04-04).

All public API is re-exported from the canonical location.
New code should use: from clarvis.queue.writer import add_task, add_tasks
"""

from clarvis.queue.writer import (  # noqa: F401
    add_task,
    add_tasks,
    mark_task_complete,
    archive_completed,
    ensure_subtasks_for_tag,
    mark_task_in_progress,
    tasks_added_today,
    QUEUE_FILE,
    STATE_FILE,
    MAX_AUTO_TASKS_PER_DAY,
    SIMILARITY_THRESHOLD,
)

"""Clarvis Queue — evolution queue management (engine + writer).

Canonical home for Queue V2 (formerly clarvis.orch.queue_engine / queue_writer).
Moved here per operator directive 2026-04-04: queue is its own spine domain.

Public API:
    from clarvis.queue import engine, add_task, add_tasks
    from clarvis.queue.engine import QueueEngine, parse_queue
    from clarvis.queue.writer import add_task, add_tasks, archive_completed
"""

from .engine import engine, QueueEngine, parse_queue
from .writer import (
    add_task,
    add_tasks,
    mark_task_complete,
    archive_completed,
    ensure_subtasks_for_tag,
    mark_task_in_progress,
    tasks_added_today,
    enforce_stale_demotions,
    queue_health,
)

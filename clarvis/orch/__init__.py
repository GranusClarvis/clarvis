"""Clarvis orchestration — task routing, PR factory, project agents, spawning, scoreboard, queue."""

from .router import classify_task, execute_openrouter, log_decision, get_stats
from .pr_rules import build_pr_rules_section, PR_CLASSES

# Queue has moved to clarvis.queue — re-export for backward compat
from clarvis.queue.engine import engine as queue_engine  # noqa: F401
from clarvis.queue.writer import add_task, add_tasks, mark_task_complete, archive_completed  # noqa: F401

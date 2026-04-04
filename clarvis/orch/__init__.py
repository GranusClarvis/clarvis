"""Clarvis orchestration — task routing, PR factory, project agents, spawning, scoreboard, queue."""

from .router import classify_task, execute_openrouter, log_decision, get_stats
from .pr_rules import build_pr_rules_section, PR_CLASSES
from .scoreboard import record as scoreboard_record, show as scoreboard_show, trend as scoreboard_trend
from .queue_engine import engine as queue_engine
from .queue_writer import add_task, add_tasks, mark_task_complete, archive_completed

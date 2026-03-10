"""Clarvis orchestration — task routing, PR factory, project agents, spawning."""

from .router import classify_task, execute_openrouter, log_decision, get_stats
from .pr_rules import build_pr_rules_section, PR_CLASSES

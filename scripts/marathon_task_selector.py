#!/usr/bin/env python3
"""
marathon_task_selector.py — Pick and batch tasks from QUEUE.md for marathon runs.

Reads QUEUE.md, filters/prioritizes tasks, respects dependencies and complexity,
and outputs a JSON batch suitable for claude_marathon.sh.

Usage:
    python3 marathon_task_selector.py [--max-tasks 3] [--max-chars 900]

Output (JSON to stdout):
    {
      "tasks": ["task1 text", "task2 text", ...],
      "tags": ["TAG1", "TAG2", ...],
      "batch_prompt": "formatted prompt for Claude",
      "count": 2,
      "skipped_oversized": ["TAG_X"],
      "queue_empty": false
    }
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"

# Tasks that require external credentials or special access — skip in marathon
SKIP_TAGS = {
    "AUTONOMY_LOGIN", "AUTONOMY_POST", "UNIVERSAL_WEB_AGENT",
    "GITHUB_API_TASKS", "ORCH_SUDO_OPT",
    "CLI_SUBPKG_ABSORB",  # Blocked: requires human decision (Inverse)
}

# Dependency map: tag -> set of tags that must be done first
DEPENDENCY_MAP = {
    "GRAPH_JSON_WRITE_REMOVAL": {"GRAPH_SOAK_7DAY"},
    "CLI_DEAD_SCRIPT_SWEEP": {"CLI_BRAIN_LIVE"},
    "ACTR_WIRING_4": {"ACTR_WIRING"},
}

# Tags for research sessions — deprioritize in marathon (long, uncertain)
RESEARCH_TAGS = {"RESEARCH_REPO_QWEN_AGENT", "RESEARCH_REPO_OBLITERATUS",
                 "RESEARCH_REPO_AGENCY_AGENTS", "RESEARCH_DISCOVERY"}


def parse_queue():
    """Parse QUEUE.md and return list of (tag, text, priority_rank, line_num) tuples."""
    if not os.path.exists(QUEUE_FILE):
        return []

    with open(QUEUE_FILE) as f:
        lines = f.readlines()

    tasks = []
    current_priority = 99  # default low priority
    priority_map = {
        "P0": 0,
        "Pillar 3": 10,  # graph soak tasks
        "Pillar 1": 20,
        "Pillar 2": 25,
        "Pillar 4": 30,
        "Pillar 5": 35,
        "AGI-Readiness": 15,
        "CLI Migration": 40,
        "Research": 50,
        "Backlog": 60,
        "Non-Code": 45,
        "P1": 55,
        "P2": 70,
        "NEW ITEMS": 50,
    }

    for i, line in enumerate(lines):
        # Track section headers for priority
        if line.startswith("## "):
            header = line.strip().lstrip("# ").strip()
            for key, rank in priority_map.items():
                if key.lower() in header.lower():
                    current_priority = rank
                    break
            else:
                current_priority = 50

        # Match unchecked tasks (top-level only, not indented subtasks)
        m = re.match(r'^- \[ \] \[([A-Z0-9_]+)\]\s*(.+)', line)
        if m:
            tag = m.group(1)
            text = m.group(2).strip()
            tasks.append((tag, text, current_priority, i))

    return tasks


def is_blocked(tag, completed_tags):
    """Check if a task is blocked by unfinished dependencies."""
    deps = DEPENDENCY_MAP.get(tag, set())
    if not deps:
        return False
    return not deps.issubset(completed_tags)


def get_completed_tags():
    """Get set of completed task tags from QUEUE.md."""
    if not os.path.exists(QUEUE_FILE):
        return set()

    with open(QUEUE_FILE) as f:
        content = f.read()

    tags = set()
    for m in re.finditer(r'^- \[x\] \[([A-Z0-9_]+)\]', content, re.MULTILINE):
        tags.add(m.group(1))

    # Also check [~] (in-progress/partial) — top-level items
    for m in re.finditer(r'^- \[~\] \[([A-Z0-9_]+)\]', content, re.MULTILINE):
        tags.add(m.group(1))

    return tags


def estimate_complexity(task_text):
    """Light complexity estimation (mirrors cognitive_load.estimate_task_complexity)."""
    try:
        from cognitive_load import estimate_task_complexity
        result = estimate_task_complexity(task_text)
        return result.get("complexity", "medium"), result.get("score", 0.5)
    except Exception:
        pass

    # Fallback: simple heuristic
    score = 0.0
    text_lower = task_text.lower()

    if len(task_text) > 400:
        score += 0.2
    elif len(task_text) > 300:
        score += 0.1

    heavy_keywords = ["refactor", "migrate", "comprehensive", "test suite",
                      "rewrite", "overhaul", "redesign"]
    for kw in heavy_keywords:
        if kw in text_lower:
            score += 0.2
            break

    if score >= 0.7:
        return "oversized", score
    elif score >= 0.4:
        return "complex", score
    elif score >= 0.2:
        return "medium", score
    return "simple", score


def select_batch(max_tasks=3, max_chars=900):
    """Select a batch of tasks from QUEUE.md.

    Priority order: P0 > Pillar 3 (graph soak) > smallest-first within priority.
    Skips: tasks requiring external creds, blocked tasks, oversized tasks.
    """
    all_tasks = parse_queue()
    completed_tags = get_completed_tags()

    if not all_tasks:
        return {
            "tasks": [],
            "tags": [],
            "batch_prompt": "",
            "count": 0,
            "skipped_oversized": [],
            "queue_empty": True,
        }

    # Filter and score
    candidates = []
    skipped_oversized = []

    for tag, text, priority, line_num in all_tasks:
        # Skip credential-requiring tasks
        if tag in SKIP_TAGS:
            continue

        # Skip blocked tasks
        if is_blocked(tag, completed_tags):
            continue

        # Skip research tasks (long, uncertain for marathon batching)
        if tag in RESEARCH_TAGS:
            continue

        # Check complexity
        complexity, score = estimate_complexity(text)
        if complexity == "oversized":
            skipped_oversized.append(tag)
            continue

        # Sort key: (priority_rank, text_length for smallest-first within priority)
        candidates.append({
            "tag": tag,
            "text": f"[{tag}] {text}",
            "priority": priority,
            "length": len(text),
            "complexity": complexity,
        })

    # Sort: priority first, then shortest tasks first (easier to batch)
    candidates.sort(key=lambda c: (c["priority"], c["length"]))

    # Build batch
    batch_tasks = []
    batch_tags = []
    total_chars = 0

    for c in candidates:
        if len(batch_tasks) >= max_tasks:
            break
        if total_chars + c["length"] > max_chars and batch_tasks:
            break
        batch_tasks.append(c["text"])
        batch_tags.append(c["tag"])
        total_chars += c["length"]

    # Format batch prompt
    if len(batch_tasks) == 1:
        batch_prompt = batch_tasks[0]
    elif batch_tasks:
        lines = []
        for i, t in enumerate(batch_tasks, 1):
            lines.append(f"{i}. {t}")
        batch_prompt = "TASKS (execute in order; commit after each if changes made):\n" + "\n".join(lines)
        batch_prompt += "\n\nRESULT FORMAT:\n"
        batch_prompt += "RESULT: success|partial|fail — <what changed>\n"
        for i, tag in enumerate(batch_tags, 1):
            batch_prompt += f"{i}. [{tag}]: <status>\n"
        batch_prompt += "NEXT: <suggested follow-up>"
    else:
        batch_prompt = ""

    return {
        "tasks": batch_tasks,
        "tags": batch_tags,
        "batch_prompt": batch_prompt,
        "count": len(batch_tasks),
        "skipped_oversized": skipped_oversized,
        "queue_empty": False,
    }


if __name__ == "__main__":
    max_tasks = 3
    max_chars = 900

    for i, arg in enumerate(sys.argv):
        if arg == "--max-tasks" and i + 1 < len(sys.argv):
            max_tasks = int(sys.argv[i + 1])
        elif arg == "--max-chars" and i + 1 < len(sys.argv):
            max_chars = int(sys.argv[i + 1])

    result = select_batch(max_tasks=max_tasks, max_chars=max_chars)
    print(json.dumps(result))

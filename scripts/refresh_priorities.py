#!/usr/bin/env python3
"""Refresh the authoritative 'current-priorities' memory in clarvis-goals.

Reads QUEUE.md and ROADMAP.md, extracts P0/P1/P2 items, and upserts a single
canonical memory with ID 'current-priorities' into the clarvis-goals collection.

Intended to run weekly (Sunday cron) or on-demand.

Usage:
    python3 scripts/refresh_priorities.py             # refresh
    python3 scripts/refresh_priorities.py --dry-run   # preview without storing
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
QUEUE_PATH = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
ROADMAP_PATH = WORKSPACE / "ROADMAP.md"

MEMORY_ID = "current-priorities"
COLLECTION = "clarvis-goals"
IMPORTANCE = 0.95


def extract_queue_items(queue_text: str) -> dict[str, list[str]]:
    """Parse QUEUE.md into P0/P1/P2 item lists."""
    priorities = {"P0": [], "P1": [], "P2": []}
    current_p = None

    for line in queue_text.splitlines():
        # Detect priority section headers
        if re.match(r"^## P0\b", line):
            current_p = "P0"
        elif re.match(r"^## P1\b", line):
            current_p = "P1"
        elif re.match(r"^## P2\b", line):
            current_p = "P2"
        elif re.match(r"^## (Partial|NEW)", line):
            current_p = None
        elif current_p and re.match(r"^- \[[ ~x]\]", line):
            # Extract task description, strip checkbox
            task = re.sub(r"^- \[[ ~x]\]\s*", "", line).strip()
            # Strip [TAG DATE] [TAG] prefixes for readability
            task = re.sub(r"^\[[\w_]+\s+[\d-]+\]\s*", "", task)
            task = re.sub(r"^\[[\w_]+\]\s*", "", task)
            # Remove long trailing context after em-dash or parenthetical
            if len(task) > 150:
                task = re.split(r"\s+—\s+", task, maxsplit=1)[0]
            task = re.sub(r"\s*\(.*$", "", task) if len(task) > 150 else task
            # Skip completed tasks
            if line.startswith("- [x]"):
                continue
            priorities[current_p].append(task)
        elif current_p and re.match(r"^###\s+", line):
            # Section headers become context
            section = line.lstrip("# ").strip()
            if section and not any(section in item for item in priorities[current_p]):
                priorities[current_p].append(f"[{section}]")

    return priorities


def extract_roadmap_state(roadmap_text: str) -> str:
    """Extract the Current State table from ROADMAP.md as a compact summary."""
    lines = roadmap_text.splitlines()
    in_table = False
    summary_parts = []

    for line in lines:
        if "## Current State" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("| **"):
                # Extract capability and status percentage
                m = re.match(r"\| \*\*(.+?)\*\* \| (\d+%)", line)
                if m:
                    summary_parts.append(f"{m.group(1)}: {m.group(2)}")
            elif line.startswith("---") and summary_parts:
                break

    return "; ".join(summary_parts) if summary_parts else "See ROADMAP.md"


def build_memory_text(priorities: dict, roadmap_summary: str) -> str:
    """Build the canonical priorities memory text."""
    now = datetime.now(timezone.utc)
    week = now.strftime("%Y-W%W")
    date = now.strftime("%Y-%m-%d")

    parts = [
        f"Current priorities (week of {date}, updated {week}):",
        "",
    ]

    for level in ["P0", "P1", "P2"]:
        items = priorities[level]
        label = {"P0": "URGENT / Current Sprint", "P1": "This Week", "P2": "When Idle"}[level]
        parts.append(f"{level} — {label}:")
        if items:
            for item in items[:8]:  # cap at 8 items per level
                parts.append(f"  - {item}")
        else:
            parts.append("  (none)")
        parts.append("")

    parts.append(f"Roadmap snapshot: {roadmap_summary}")
    return "\n".join(parts)


def refresh(dry_run: bool = False) -> str:
    """Read sources, build memory, upsert into brain. Returns the memory text."""
    queue_text = QUEUE_PATH.read_text() if QUEUE_PATH.exists() else ""
    roadmap_text = ROADMAP_PATH.read_text() if ROADMAP_PATH.exists() else ""

    priorities = extract_queue_items(queue_text)
    roadmap_summary = extract_roadmap_state(roadmap_text)
    memory_text = build_memory_text(priorities, roadmap_summary)

    if dry_run:
        print("=== DRY RUN — would store: ===")
        print(memory_text)
        return memory_text

    # Import brain and upsert
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from clarvis.brain import brain
    from clarvis.brain.constants import GOALS

    memory_id = brain.store(
        text=memory_text,
        collection=GOALS,
        importance=IMPORTANCE,
        tags=["priorities", "canonical", "weekly-refresh"],
        source="refresh_priorities.py",
        memory_id=MEMORY_ID,
    )
    print(f"Stored '{memory_id}' in {GOALS} (importance={IMPORTANCE})")
    print(f"Content length: {len(memory_text)} chars")
    return memory_text


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    refresh(dry_run=dry_run)

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

WORKSPACE = Path(__file__).resolve().parent.parent.parent
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


_TOP_LEVEL_HEADER = re.compile(r"^##\s+(.+)")
_ACTIVE_PRIORITY_HEADER = re.compile(r"^##\s+P[012]\b")
_SUBSECTION_HEADER = re.compile(r"^#{3,}\s+(.+)")
_RETIRED_TOKENS = re.compile(
    r"\b(retir|defer|archiv|deprecat|supersed|dropped|out[- ]of[- ]scope)",
    re.IGNORECASE,
)


def _subsection_is_active(title: str) -> bool:
    """A subsection is treated as inactive if its title flags retired/deferred work."""
    return not _RETIRED_TOKENS.search(title)


def compute_queue_progress(queue_text: str) -> dict:
    """Count checkbox states across the active weekly priority record only.

    Active scope = items under the top-level ``## P0``/``## P1``/``## P2`` headings,
    excluding subsections whose heading marks them as retired/deferred/archived
    (e.g. ``#### Retired / Deferred Items`` under P1, or
    ``### Sanctuary Asset Batches — RETIRED 2026-04-25`` under P2). Top-level blocks
    that are not active priorities (``## NEW ITEMS``, ``## Partial Items``,
    ``## Research Sessions``) are also excluded. Strikethrough items
    (``- [x] ~~...~~``) are skipped because they're retired in place.

    Returns dict: {progress, done, partial, open, total, ratio_done, ratio_active}.
    ``progress`` is a 0-100 int = floor(100 * (done + 0.5*partial) / total),
    suitable for dropping into goal metadata so weekly priorities reflect live work.
    """
    done = partial = open_ = 0
    in_active_priority = False
    in_active_subsection = True

    for line in queue_text.splitlines():
        if _TOP_LEVEL_HEADER.match(line):
            in_active_priority = bool(_ACTIVE_PRIORITY_HEADER.match(line))
            in_active_subsection = True
            continue

        m_sub = _SUBSECTION_HEADER.match(line)
        if m_sub:
            in_active_subsection = _subsection_is_active(m_sub.group(1))
            continue

        if not (in_active_priority and in_active_subsection):
            continue

        m = re.match(r"^\s*- \[([ ~x])\]", line)
        if not m:
            continue
        if "~~" in line:
            continue

        ch = m.group(1)
        if ch == "x":
            done += 1
        elif ch == "~":
            partial += 1
        else:
            open_ += 1

    total = done + partial + open_
    if total == 0:
        return {"progress": 0, "done": 0, "partial": 0, "open": 0, "total": 0,
                "ratio_done": 0.0, "ratio_active": 0.0}
    score = (done + 0.5 * partial) / total
    return {
        "progress": int(score * 100),
        "done": done,
        "partial": partial,
        "open": open_,
        "total": total,
        "ratio_done": round(done / total, 4),
        "ratio_active": round((done + partial) / total, 4),
    }


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
    progress_stats = compute_queue_progress(queue_text)
    memory_text = build_memory_text(priorities, roadmap_summary)

    if dry_run:
        print("=== DRY RUN — would store: ===")
        print(memory_text)
        print(f"\n[progress] {progress_stats}")
        return memory_text

    # Import brain and upsert
    from clarvis.brain import brain
    from clarvis.brain.constants import GOALS
    from datetime import datetime, timezone

    memory_id = brain.store(
        text=memory_text,
        collection=GOALS,
        importance=IMPORTANCE,
        tags=["priorities", "canonical", "weekly-refresh"],
        source="refresh_priorities.py",
        memory_id=MEMORY_ID,
    )
    # Stamp progress metadata so brain.get_goals() reports a live, non-zero
    # progress for the canonical weekly priorities record.
    try:
        col = brain.collections[GOALS]
        existing = col.get(ids=[memory_id])
        if existing.get("ids"):
            meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            meta["progress"] = progress_stats["progress"]
            meta["progress_done"] = progress_stats["done"]
            meta["progress_partial"] = progress_stats["partial"]
            meta["progress_open"] = progress_stats["open"]
            meta["progress_total"] = progress_stats["total"]
            meta["progress_updated"] = datetime.now(timezone.utc).isoformat()
            meta["progress_source"] = "QUEUE.md"
            col.update(ids=[memory_id], metadatas=[meta])
    except Exception as e:
        print(f"[warn] progress metadata update failed: {e}")
    print(f"Stored '{memory_id}' in {GOALS} (importance={IMPORTANCE})")
    print(f"Progress: {progress_stats['progress']}% "
          f"({progress_stats['done']}/{progress_stats['total']} done, "
          f"{progress_stats['partial']} partial)")
    print(f"Content length: {len(memory_text)} chars")
    return memory_text


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    refresh(dry_run=dry_run)

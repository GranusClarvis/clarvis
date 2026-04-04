#!/usr/bin/env python3
"""Minimal-cost /queue_clarvis summarizer.

Reads memory/evolution/QUEUE.md and prints:
- counts (pending/completed)
- P0 items
- P1 items (if present) else next section after P0
- 5 most recent completed items

Designed to avoid loading the full agent context.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


ROOT = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
QUEUE_PATH = ROOT / "memory/evolution/QUEUE.md"
QUEUE_ARCHIVE_PATH = ROOT / "memory/evolution/QUEUE_ARCHIVE.md"


CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<state>[ xX])\]\s*(?P<text>.*)$")
HEADING_RE = re.compile(r"^(?P<level>#{2,4})\s+(?P<title>.+?)\s*$")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


@dataclass
class Item:
    checked: bool
    text: str
    line_no: int
    date: Optional[str] = None


def read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def parse_items(lines: List[str]) -> Tuple[List[Item], List[Item]]:
    pending: List[Item] = []
    done: List[Item] = []

    for i, line in enumerate(lines, start=1):
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        state = m.group("state")
        text = m.group("text").strip()
        checked = state.lower() == "x"
        date_m = DATE_RE.search(text)
        date = date_m.group(1) if date_m else None
        it = Item(checked=checked, text=text, line_no=i, date=date)
        (done if checked else pending).append(it)

    return pending, done


def extract_section(lines: List[str], heading_matcher) -> List[str]:
    """Return raw checkbox lines within the first section whose heading matches heading_matcher."""
    start = None
    end = None

    for idx, line in enumerate(lines):
        hm = HEADING_RE.match(line)
        if hm and heading_matcher(hm.group("title")):
            start = idx + 1
            break

    if start is None:
        return []

    for idx in range(start, len(lines)):
        hm = HEADING_RE.match(lines[idx])
        if hm and hm.group("level") == "##":
            end = idx
            break

    block = lines[start:end] if end is not None else lines[start:]
    return [ln for ln in block if CHECKBOX_RE.match(ln)]


def extract_next_section_after(lines: List[str], title_pred) -> List[str]:
    """If P1 doesn't exist, take the next top-level section after P0."""
    p0_idx = None
    for idx, line in enumerate(lines):
        hm = HEADING_RE.match(line)
        if hm and title_pred(hm.group("title")):
            p0_idx = idx
            break
    if p0_idx is None:
        return []

    next_start = None
    for idx in range(p0_idx + 1, len(lines)):
        hm = HEADING_RE.match(lines[idx])
        if hm and hm.group("level") == "##":
            next_start = idx
            break
    if next_start is None:
        return []

    # find end
    end = None
    for idx in range(next_start + 1, len(lines)):
        hm = HEADING_RE.match(lines[idx])
        if hm and hm.group("level") == "##":
            end = idx
            break

    block = lines[next_start + 1 : end] if end is not None else lines[next_start + 1 :]
    return [ln for ln in block if CHECKBOX_RE.match(ln)]


def normalize_item_line(line: str) -> str:
    m = CHECKBOX_RE.match(line)
    if not m:
        return line.strip()
    state = m.group("state")
    text = m.group("text").strip()
    prefix = "[x]" if state.lower() == "x" else "[ ]"
    return f"- {prefix} {text}"


def main() -> int:
    if not QUEUE_PATH.exists():
        print(f"ERROR: QUEUE.md not found at {QUEUE_PATH}")
        return 1

    lines = read_lines(QUEUE_PATH)
    pending, done = parse_items(lines)

    # P0 section
    p0_lines = extract_section(lines, lambda t: t.lower().startswith("p0"))

    # P1 section (if any)
    p1_lines = extract_section(lines, lambda t: t.lower().startswith("p1"))
    if not p1_lines:
        p1_lines = extract_next_section_after(lines, lambda t: t.lower().startswith("p0"))

    # last 5 completed: take the last 5 occurrences in file order.
    # If QUEUE.md has fewer than 5, supplement from QUEUE_ARCHIVE.md.
    done_sorted = sorted(done, key=lambda it: it.line_no)
    recent_done: List[Item] = done_sorted[-5:]

    if len(recent_done) < 5 and QUEUE_ARCHIVE_PATH.exists():
        arch_lines = read_lines(QUEUE_ARCHIVE_PATH)
        _pending_a, done_a = parse_items(arch_lines)
        done_a_sorted = sorted(done_a, key=lambda it: it.line_no)
        need = 5 - len(recent_done)
        recent_done = (done_a_sorted[-need:] + recent_done)[-5:]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"📋 Clarvis Queue Summary ({now})")
    print(f"Pending: {len(pending)} | Completed: {len(done)}")

    print("\nP0:")
    if p0_lines:
        for ln in p0_lines[:10]:
            print(normalize_item_line(ln))
        if len(p0_lines) > 10:
            print(f"  … (+{len(p0_lines)-10} more)")
    else:
        print("- (none)")

    print("\nP1:")
    if p1_lines:
        for ln in p1_lines[:10]:
            print(normalize_item_line(ln))
        if len(p1_lines) > 10:
            print(f"  … (+{len(p1_lines)-10} more)")
    else:
        print("- (none)")

    print("\nRecent completed (last 5):")
    if recent_done:
        for it in recent_done:
            suffix = f" ({it.date})" if it.date else ""
            print(f"- [x] {it.text}{suffix}")
    else:
        print("- (none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

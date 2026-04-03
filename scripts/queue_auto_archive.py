#!/usr/bin/env python3
"""queue_auto_archive.py — Automatically archive completed items from QUEUE.md to QUEUE_ARCHIVE.md.

Usage:
    python3 scripts/queue_auto_archive.py            # Run archival
    python3 scripts/queue_auto_archive.py --dry-run   # Preview without writing
    python3 scripts/queue_auto_archive.py --status     # Show counts
"""

import argparse
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
QUEUE_PATH = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
ARCHIVE_PATH = WORKSPACE / "memory" / "evolution" / "QUEUE_ARCHIVE.md"
LOCK_PATH = QUEUE_PATH.with_suffix(".md.lock")
BACKUP_PATH = QUEUE_PATH.with_suffix(".md.bak")

COMPLETED_RE = re.compile(r"^\s*- \[x\] \[.+?\]")
STALE_LOCK_SECONDS = 600


# ── Lock helpers ──────────────────────────────────────────────────────────────

def acquire_lock() -> bool:
    """Acquire lockfile. Returns True on success."""
    if LOCK_PATH.exists():
        try:
            age = time.time() - LOCK_PATH.stat().st_mtime
            if age > STALE_LOCK_SECONDS:
                pid = LOCK_PATH.read_text().strip()
                print(f"Removing stale lock (age={age:.0f}s, pid={pid})")
                LOCK_PATH.unlink()
            else:
                pid = LOCK_PATH.read_text().strip()
                print(f"Lock held by pid {pid} (age={age:.0f}s). Aborting.")
                return False
        except OSError:
            pass
    try:
        LOCK_PATH.write_text(str(os.getpid()))
        return True
    except OSError as e:
        print(f"Failed to create lock: {e}")
        return False


def release_lock():
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


# ── Core logic ────────────────────────────────────────────────────────────────

def find_completed(lines: list[str]) -> list[tuple[int, str]]:
    """Return (line_index, line_text) for completed items."""
    return [(i, line) for i, line in enumerate(lines) if COMPLETED_RE.match(line)]


def build_cleaned_queue(lines: list[str], completed_indices: set[int]) -> list[str]:
    """Return queue lines with completed items removed, preserving section headers."""
    return [line for i, line in enumerate(lines) if i not in completed_indices]


def build_archive_section(completed_lines: list[str], today: str) -> str:
    """Build the archive section to prepend."""
    header = f"### Archived {today} (auto-archive)"
    items = "\n".join(line.rstrip() for line in completed_lines)
    return f"{header}\n{items}\n"


def update_queue_header(lines: list[str]) -> list[str]:
    """Update the auto-archive mention in the queue header."""
    result = []
    for line in lines:
        if "auto-archived" in line.lower() or "auto-archive" in line.lower():
            result.append("_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._\n")
        else:
            result.append(line)
    return result


def insert_into_archive(archive_text: str, new_section: str) -> str:
    """Insert new archive section after the header block (first blank line after metadata)."""
    lines = archive_text.split("\n")
    # Find insertion point: after the header metadata lines (# title, blank, _description_, _Last archived_)
    # Update "Last archived" date
    today = datetime.now().strftime("%Y-%m-%d")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("_Last archived:"):
            lines[i] = f"_Last archived: {today}_"
            insert_idx = i + 1
            break
        if line.startswith("###") or (i > 0 and line.startswith("- [x]")):
            insert_idx = i
            break
    else:
        # Fallback: insert after first blank line
        for i, line in enumerate(lines):
            if line.strip() == "" and i > 0:
                insert_idx = i + 1
                break

    # Insert after the header with a blank line separator
    before = "\n".join(lines[:insert_idx])
    after = "\n".join(lines[insert_idx:])
    return f"{before}\n\n{new_section}\n{after}"


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status():
    """Show counts of completed vs open items."""
    if not QUEUE_PATH.exists():
        print(f"QUEUE.md not found at {QUEUE_PATH}")
        return 1

    lines = QUEUE_PATH.read_text().splitlines(keepends=True)
    completed = find_completed(lines)
    open_items = [(i, l) for i, l in enumerate(lines) if re.match(r"^\s*- \[ \] \[.+?\]", l)]
    partial = [(i, l) for i, l in enumerate(lines) if re.match(r"^\s*- \[~\] \[.+?\]", l)]

    print(f"QUEUE.md status:")
    print(f"  Completed [x]: {len(completed)}")
    print(f"  Open      [ ]: {len(open_items)}")
    print(f"  Partial   [~]: {len(partial)}")
    if completed:
        print(f"\nCompleted items ready to archive:")
        for _, line in completed:
            # Truncate for readability
            task_match = re.match(r"^\s*- \[x\] (\[.+?\])", line)
            tag = task_match.group(1) if task_match else line.strip()[:80]
            print(f"  {tag}")
    else:
        print("\nNo completed items to archive.")
    return 0


def cmd_run(dry_run: bool = False):
    """Archive completed items from QUEUE.md to QUEUE_ARCHIVE.md."""
    if not QUEUE_PATH.exists():
        print(f"QUEUE.md not found at {QUEUE_PATH}")
        return 1

    queue_text = QUEUE_PATH.read_text()
    lines = queue_text.splitlines(keepends=True)
    completed = find_completed(lines)

    if not completed:
        print("No completed items to archive.")
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    completed_indices = {i for i, _ in completed}
    completed_lines = [line for _, line in completed]

    print(f"Found {len(completed)} completed item(s) to archive:")
    for _, line in completed:
        task_match = re.match(r"^\s*- \[x\] (\[.+?\])", line)
        tag = task_match.group(1) if task_match else line.strip()[:80]
        print(f"  {tag}")

    if dry_run:
        print(f"\n[DRY RUN] Would archive {len(completed)} items to {ARCHIVE_PATH.name}")
        print(f"[DRY RUN] Would update queue header in {QUEUE_PATH.name}")
        return 0

    # Acquire lock
    if not acquire_lock():
        return 1

    try:
        # Backup
        shutil.copy2(QUEUE_PATH, BACKUP_PATH)
        print(f"Backup saved to {BACKUP_PATH.name}")

        # Build new queue (remove completed, update header)
        cleaned = build_cleaned_queue(lines, completed_indices)
        cleaned = update_queue_header(cleaned)
        new_queue = "".join(cleaned)

        # Build archive section
        archive_section = build_archive_section(completed_lines, today)

        # Read or create archive
        if ARCHIVE_PATH.exists():
            archive_text = ARCHIVE_PATH.read_text()
        else:
            archive_text = (
                "# Evolution Queue — Archive\n\n"
                "_Completed items archived from QUEUE.md to reduce token footprint._\n"
                f"_Last archived: {today}_\n"
            )

        new_archive = insert_into_archive(archive_text, archive_section)

        # Write both files
        QUEUE_PATH.write_text(new_queue)
        ARCHIVE_PATH.write_text(new_archive)

        print(f"Archived {len(completed)} items to {ARCHIVE_PATH.name}")
        print("Done.")
        return 0

    except Exception as e:
        print(f"Error during archival: {e}")
        # Restore from backup
        if BACKUP_PATH.exists():
            shutil.copy2(BACKUP_PATH, QUEUE_PATH)
            print("Restored QUEUE.md from backup.")
        return 1

    finally:
        release_lock()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Archive completed items from QUEUE.md to QUEUE_ARCHIVE.md"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--status", action="store_true", help="Show item counts")
    args = parser.parse_args()

    if args.status:
        return cmd_status()
    return cmd_run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main() or 0)

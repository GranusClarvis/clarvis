#!/usr/bin/env python3
"""
Data Lifecycle Manager — archive stale reasoning chains and rotate old sessions.

Policy:
  data/reasoning_chains/*.json     — gzip-archive after 14 days → archive/ subdir
  data/reasoning_chains/sessions/  — gzip-archive after 14 days → archive/sessions/
  data/sessions/*.json             — delete after 30 days
  (reasoning_meta.json and session_map.json are never touched)

Run:  python3 scripts/data_lifecycle.py [--dry-run] [--verbose]
Cron: Sunday 05:20 CET (after goal_hygiene, before brain_hygiene)
"""

import argparse
import gzip
import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
CHAINS_DIR = WORKSPACE / "data" / "reasoning_chains"
CHAINS_SESSIONS_DIR = CHAINS_DIR / "sessions"
SESSIONS_DIR = WORKSPACE / "data" / "sessions"
ARCHIVE_DIR = CHAINS_DIR / "archive"
ARCHIVE_SESSIONS_DIR = ARCHIVE_DIR / "sessions"

# Files that should never be archived/deleted
PROTECTED = {"reasoning_meta.json", "session_map.json"}

CHAIN_MAX_AGE_DAYS = 14
SESSION_MAX_AGE_DAYS = 30

LOG_FILE = WORKSPACE / "memory" / "cron" / "data_lifecycle.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("data_lifecycle")


def file_age_days(path: Path) -> float:
    """Return file age in days based on mtime."""
    return (time.time() - path.stat().st_mtime) / 86400


def gzip_archive(src: Path, dst_dir: Path, dry_run: bool) -> int:
    """Gzip a file into dst_dir. Returns bytes freed (original size)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (src.name + ".gz")
    original_size = src.stat().st_size
    if dry_run:
        log.info("  [dry-run] would archive %s (%d bytes)", src.name, original_size)
        return original_size
    with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    src.unlink()
    log.debug("  archived %s → %s", src.name, dst.name)
    return original_size


def archive_chains(dry_run: bool, verbose: bool) -> dict:
    """Archive reasoning chain JSON files older than CHAIN_MAX_AGE_DAYS."""
    stats = {"archived": 0, "bytes_freed": 0, "skipped": 0}
    if not CHAINS_DIR.exists():
        log.warning("reasoning_chains directory not found")
        return stats

    cutoff = CHAIN_MAX_AGE_DAYS
    for f in sorted(CHAINS_DIR.glob("*.json")):
        if f.name in PROTECTED:
            continue
        age = file_age_days(f)
        if age > cutoff:
            freed = gzip_archive(f, ARCHIVE_DIR, dry_run)
            stats["archived"] += 1
            stats["bytes_freed"] += freed
        else:
            stats["skipped"] += 1
            if verbose:
                log.debug("  keep %s (%.1f days old)", f.name, age)

    # Also handle chains/sessions/ subdir
    if CHAINS_SESSIONS_DIR.exists():
        for f in sorted(CHAINS_SESSIONS_DIR.glob("*.json")):
            age = file_age_days(f)
            if age > cutoff:
                freed = gzip_archive(f, ARCHIVE_SESSIONS_DIR, dry_run)
                stats["archived"] += 1
                stats["bytes_freed"] += freed
            else:
                stats["skipped"] += 1

    return stats


def rotate_sessions(dry_run: bool, verbose: bool) -> dict:
    """Delete session files older than SESSION_MAX_AGE_DAYS."""
    stats = {"deleted": 0, "bytes_freed": 0, "skipped": 0}
    if not SESSIONS_DIR.exists():
        log.warning("sessions directory not found")
        return stats

    cutoff = SESSION_MAX_AGE_DAYS
    for f in sorted(SESSIONS_DIR.glob("*.json")):
        age = file_age_days(f)
        if age > cutoff:
            size = f.stat().st_size
            if dry_run:
                log.info("  [dry-run] would delete %s (%d bytes, %.0f days old)", f.name, size, age)
            else:
                f.unlink()
                log.debug("  deleted %s (%.0f days old)", f.name, age)
            stats["deleted"] += 1
            stats["bytes_freed"] += size
        else:
            stats["skipped"] += 1
            if verbose:
                log.debug("  keep %s (%.1f days old)", f.name, age)

    return stats


def clean_old_archives(dry_run: bool) -> dict:
    """Remove .gz archives older than 90 days to prevent unbounded growth."""
    stats = {"deleted": 0, "bytes_freed": 0}
    for archive_dir in [ARCHIVE_DIR, ARCHIVE_SESSIONS_DIR]:
        if not archive_dir.exists():
            continue
        for f in sorted(archive_dir.glob("*.gz")):
            if file_age_days(f) > 90:
                size = f.stat().st_size
                if not dry_run:
                    f.unlink()
                stats["deleted"] += 1
                stats["bytes_freed"] += size
    return stats


def main():
    parser = argparse.ArgumentParser(description="Data lifecycle manager")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--verbose", action="store_true", help="Show skipped files")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    mode = "[DRY RUN] " if args.dry_run else ""
    log.info("%s=== Data Lifecycle Run ===", mode)

    # 1. Archive old reasoning chains
    log.info("Archiving reasoning chains older than %d days...", CHAIN_MAX_AGE_DAYS)
    chain_stats = archive_chains(args.dry_run, args.verbose)
    log.info("  Chains: %d archived, %d kept, %s freed",
             chain_stats["archived"], chain_stats["skipped"],
             _fmt_bytes(chain_stats["bytes_freed"]))

    # 2. Rotate old sessions
    log.info("Rotating sessions older than %d days...", SESSION_MAX_AGE_DAYS)
    session_stats = rotate_sessions(args.dry_run, args.verbose)
    log.info("  Sessions: %d deleted, %d kept, %s freed",
             session_stats["deleted"], session_stats["skipped"],
             _fmt_bytes(session_stats["bytes_freed"]))

    # 3. Clean very old archives
    log.info("Cleaning archives older than 90 days...")
    archive_stats = clean_old_archives(args.dry_run)
    if archive_stats["deleted"]:
        log.info("  Old archives: %d removed, %s freed",
                 archive_stats["deleted"], _fmt_bytes(archive_stats["bytes_freed"]))

    # Summary
    total_freed = chain_stats["bytes_freed"] + session_stats["bytes_freed"] + archive_stats["bytes_freed"]
    total_actions = chain_stats["archived"] + session_stats["deleted"] + archive_stats["deleted"]
    log.info("Total: %d actions, %s freed", total_actions, _fmt_bytes(total_freed))

    # Machine-readable summary on stdout
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "chains_archived": chain_stats["archived"],
        "chains_kept": chain_stats["skipped"],
        "sessions_deleted": session_stats["deleted"],
        "sessions_kept": session_stats["skipped"],
        "old_archives_cleaned": archive_stats["deleted"],
        "total_bytes_freed": total_freed,
    }
    print(json.dumps(summary, indent=2))


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    main()

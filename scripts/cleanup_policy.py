#!/usr/bin/env python3
"""
Workspace File-Hygiene Policy — Weekly cleanup automation.

Retention rules:
  monitoring/*.log    — rotate at 500KB, keep 3 rotated copies (.1, .2, .3)
  memory/cron/*.log   — rotate at 200KB, keep 3 rotated copies
  memory/YYYY-MM-DD.md — compress after 3 days, delete .gz after 90 days
  data/*.jsonl        — trim to last N lines (configurable per file)
  /tmp/clarvis_*.lock — remove stale locks (>1h, PID dead)
  data/browser_sessions/screenshots/* — delete files older than 7 days

Run: python3 cleanup_policy.py [--dry-run] [--verbose]
Cron: weekly Sunday 05:30 UTC (after maintenance window)
"""

import argparse
import gzip
import json
import os
import re
import time
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")

# --- Retention Policy ---

# Log rotation: {path_glob: max_bytes}
LOG_ROTATION = {
    "monitoring/health.log": 500_000,
    "monitoring/watchdog.log": 500_000,
    "monitoring/alerts.log": 200_000,
    "monitoring/security.log": 200_000,
}

CRON_LOG_ROTATION = {
    "memory/cron/autonomous.log": 200_000,
    "memory/cron/reflection.log": 200_000,
    "memory/cron/evening.log": 200_000,
    "memory/cron/research.log": 200_000,
    "memory/cron/evolution.log": 200_000,
    "memory/cron/morning.log": 200_000,
    "memory/cron/dream.log": 200_000,
    "memory/cron/implementation_sprint.log": 200_000,
    "memory/cron/strategic_audit.log": 200_000,
    "memory/cron/graph_compaction.log": 200_000,
    "memory/cron/graph_checkpoint.log": 200_000,
    "memory/cron/chromadb_vacuum.log": 200_000,
    "memory/cron/backup.log": 200_000,
    "memory/cron/backup_verify.log": 200_000,
    "memory/cron/report_morning.log": 100_000,
    "memory/cron/report_evening.log": 100_000,
}

MAX_ROTATED_COPIES = 3

# Daily memory: compress after N days, delete .gz after M days
MEMORY_COMPRESS_AFTER_DAYS = 3
MEMORY_DELETE_GZ_AFTER_DAYS = 90

# JSONL trimming: {relative_path: max_lines_to_keep}
JSONL_TRIM = {
    "data/thought_log.jsonl": 2000,
    "data/costs.jsonl": 5000,
    "data/router_decisions.jsonl": 2000,
    "data/code_gen_outcomes.jsonl": 2000,
    "data/performance_history.jsonl": 1000,
    "data/performance_alerts.jsonl": 500,
    "data/latency_trend.jsonl": 1000,
    "data/retrieval_errors.jsonl": 500,
    "data/structural_health_history.jsonl": 500,
    "data/procedure_injection_log.jsonl": 500,
}

# Stale lock cleanup
LOCK_MAX_AGE_SECONDS = 3600  # 1 hour
LOCK_PATTERN = "/tmp/clarvis_*.lock"

# Screenshot cleanup
SCREENSHOT_DIR = WORKSPACE / "data" / "browser_sessions" / "screenshots"
SCREENSHOT_MAX_AGE_DAYS = 7


class CleanupReport:
    """Tracks what was cleaned and how much space was freed."""

    def __init__(self):
        self.actions: list[str] = []
        self.bytes_freed = 0
        self.files_removed = 0
        self.files_rotated = 0
        self.files_compressed = 0
        self.lines_trimmed = 0
        self.locks_removed = 0

    def log(self, action: str):
        self.actions.append(action)

    def summary(self) -> str:
        lines = [
            f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] === Cleanup Report ===",
            f"  Bytes freed:      {self.bytes_freed:,}",
            f"  Files rotated:    {self.files_rotated}",
            f"  Files compressed: {self.files_compressed}",
            f"  Files removed:    {self.files_removed}",
            f"  JSONL lines trimmed: {self.lines_trimmed}",
            f"  Stale locks removed: {self.locks_removed}",
        ]
        if self.actions:
            lines.append("  Actions:")
            for a in self.actions:
                lines.append(f"    - {a}")
        return "\n".join(lines)


def rotate_log(filepath: Path, max_bytes: int, report: CleanupReport, dry_run: bool):
    """Rotate a log file if it exceeds max_bytes. Keeps up to MAX_ROTATED_COPIES."""
    if not filepath.exists():
        return
    size = filepath.stat().st_size
    if size <= max_bytes:
        return

    # Shift existing rotated files: .3 -> delete, .2 -> .3, .1 -> .2
    for i in range(MAX_ROTATED_COPIES, 0, -1):
        src = filepath.with_suffix(f".log.{i}") if filepath.suffix == ".log" else Path(str(filepath) + f".{i}")
        if i == MAX_ROTATED_COPIES:
            if src.exists():
                old_size = src.stat().st_size
                if not dry_run:
                    src.unlink()
                report.bytes_freed += old_size
                report.files_removed += 1
                report.log(f"Deleted oldest rotation: {src.name}")
        else:
            dst = filepath.with_suffix(f".log.{i+1}") if filepath.suffix == ".log" else Path(str(filepath) + f".{i+1}")
            if src.exists():
                if not dry_run:
                    src.rename(dst)

    # Current -> .1
    rotated = filepath.with_suffix(f".log.1") if filepath.suffix == ".log" else Path(str(filepath) + ".1")
    if not dry_run:
        filepath.rename(rotated)
        filepath.touch()  # Create empty new log
    report.files_rotated += 1
    report.log(f"Rotated {filepath.name} ({size:,} bytes)")


def compress_old_memory(report: CleanupReport, dry_run: bool):
    """Compress daily memory files older than MEMORY_COMPRESS_AFTER_DAYS."""
    memory_dir = WORKSPACE / "memory"
    cutoff = datetime.now(timezone.utc) - timedelta(days=MEMORY_COMPRESS_AFTER_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # Find uncompressed daily memory files
    for f in sorted(memory_dir.glob("????-??-??.md")):
        # Extract date from filename
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.md$", f.name)
        if not date_match:
            continue
        file_date = date_match.group(1)
        if file_date >= cutoff_str:
            continue  # Too recent

        gz_path = f.with_suffix(".md.gz")
        if gz_path.exists():
            continue  # Already compressed

        original_size = f.stat().st_size
        if not dry_run:
            with open(f, "rb") as fin:
                with gzip.open(gz_path, "wb", compresslevel=9) as fout:
                    fout.write(fin.read())
            f.unlink()
        report.files_compressed += 1
        report.bytes_freed += original_size  # Approximate (gz is smaller)
        report.log(f"Compressed {f.name} ({original_size:,} bytes)")

    # Delete very old .gz files
    delete_cutoff = datetime.now(timezone.utc) - timedelta(days=MEMORY_DELETE_GZ_AFTER_DAYS)
    delete_str = delete_cutoff.strftime("%Y-%m-%d")
    for f in sorted(memory_dir.glob("????-??-??.md.gz")):
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.md\.gz$", f.name)
        if not date_match:
            continue
        if date_match.group(1) < delete_str:
            size = f.stat().st_size
            if not dry_run:
                f.unlink()
            report.files_removed += 1
            report.bytes_freed += size
            report.log(f"Deleted old memory archive: {f.name}")


def trim_jsonl(filepath: Path, max_lines: int, report: CleanupReport, dry_run: bool):
    """Keep only the last max_lines lines of a JSONL file."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError):
        return

    if len(lines) <= max_lines:
        return

    trimmed_count = len(lines) - max_lines
    kept = lines[-max_lines:]

    original_size = filepath.stat().st_size
    if not dry_run:
        with open(filepath, "w") as f:
            f.writelines(kept)
    new_size = sum(len(l) for l in kept)
    report.bytes_freed += original_size - new_size
    report.lines_trimmed += trimmed_count
    report.log(f"Trimmed {filepath.name}: {len(lines)} → {max_lines} lines (-{trimmed_count})")


def clean_stale_locks(report: CleanupReport, dry_run: bool):
    """Remove stale /tmp/clarvis_*.lock files where PID is dead or age > threshold."""
    import glob as globmod
    now = time.time()

    for lockfile in globmod.glob(LOCK_PATTERN):
        path = Path(lockfile)
        try:
            age = now - path.stat().st_mtime
            if age < LOCK_MAX_AGE_SECONDS:
                continue

            # Check if PID is still alive
            pid_str = path.read_text().strip()
            if pid_str.isdigit():
                try:
                    os.kill(int(pid_str), 0)
                    continue  # Process still alive, skip
                except ProcessLookupError:
                    pass  # Process dead, safe to remove
                except PermissionError:
                    continue  # Can't check, leave it

            if not dry_run:
                path.unlink()
            report.locks_removed += 1
            report.log(f"Removed stale lock: {path.name} (age={int(age)}s)")
        except (IOError, OSError):
            continue


def clean_screenshots(report: CleanupReport, dry_run: bool):
    """Delete old screenshots."""
    if not SCREENSHOT_DIR.exists():
        return
    cutoff = time.time() - (SCREENSHOT_MAX_AGE_DAYS * 86400)
    for f in SCREENSHOT_DIR.iterdir():
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                if not dry_run:
                    f.unlink()
                report.files_removed += 1
                report.bytes_freed += size
                report.log(f"Deleted old screenshot: {f.name}")
        except OSError:
            continue


def run_cleanup(dry_run: bool = False, verbose: bool = False) -> CleanupReport:
    """Execute the full cleanup policy."""
    report = CleanupReport()

    # 1. Rotate monitoring logs
    for rel_path, max_bytes in LOG_ROTATION.items():
        rotate_log(WORKSPACE / rel_path, max_bytes, report, dry_run)

    # 2. Rotate cron logs
    for rel_path, max_bytes in CRON_LOG_ROTATION.items():
        rotate_log(WORKSPACE / rel_path, max_bytes, report, dry_run)

    # 3. Compress old daily memory, delete ancient archives
    compress_old_memory(report, dry_run)

    # 4. Trim JSONL files
    for rel_path, max_lines in JSONL_TRIM.items():
        trim_jsonl(WORKSPACE / rel_path, max_lines, report, dry_run)

    # 5. Clean stale locks
    clean_stale_locks(report, dry_run)

    # 6. Clean old screenshots
    clean_screenshots(report, dry_run)

    return report


def main():
    parser = argparse.ArgumentParser(description="Workspace file-hygiene cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    parser.add_argument("--verbose", action="store_true", help="Print all actions")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args()

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}Running workspace cleanup policy...")

    report = run_cleanup(dry_run=args.dry_run, verbose=args.verbose)

    if args.json:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "bytes_freed": report.bytes_freed,
            "files_rotated": report.files_rotated,
            "files_compressed": report.files_compressed,
            "files_removed": report.files_removed,
            "lines_trimmed": report.lines_trimmed,
            "locks_removed": report.locks_removed,
            "actions": report.actions,
        }, indent=2))
    else:
        print(report.summary())

    if args.verbose and not args.json:
        for a in report.actions:
            print(f"  {a}")


if __name__ == "__main__":
    main()

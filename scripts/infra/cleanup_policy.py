#!/usr/bin/env python3
"""
Workspace File-Hygiene Policy — Weekly cleanup automation.

Retention rules:
  monitoring/*.log    — rotate at 500KB, keep 3 rotated copies (.1, .2, .3)
  memory/cron/*.log   — rotate at 200KB, keep 3 rotated copies
  memory/YYYY-MM-DD.md — compress after 3 days, delete .gz after 90 days
  data/*.jsonl        — trim to last N lines (configurable per file)
  /tmp/clarvis_*.lock — remove stale locks (>1h, PID dead)
  /tmp/clarvis-fresh*, clarvis_smoke_*, etc — remove test installs after 3 days
  data/browser_sessions/screenshots/* — delete files older than 7 days

Run: python3 cleanup_policy.py [--dry-run] [--verbose]
Cron: weekly Sunday 05:30 UTC (after maintenance window)
"""

import argparse
import gzip
import json
import os
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))

# --- Retention Policy ---

# Log rotation: {path_glob: max_bytes}
LOG_ROTATION = {
    "monitoring/health.log": 500_000,
    "monitoring/watchdog.log": 500_000,
    "monitoring/alerts.log": 200_000,
    "monitoring/security.log": 200_000,
}

CRON_LOG_ROTATION = {
    # --- Claude-spawning jobs (larger budgets, bigger logs) ---
    "memory/cron/autonomous.log": 200_000,
    "memory/cron/reflection.log": 200_000,
    "memory/cron/evening.log": 200_000,
    "memory/cron/research.log": 200_000,
    "memory/cron/evolution.log": 200_000,
    "memory/cron/morning.log": 200_000,
    "memory/cron/dream.log": 200_000,
    "memory/cron/implementation_sprint.log": 200_000,
    "memory/cron/strategic_audit.log": 200_000,
    "memory/cron/marathon.log": 200_000,
    # --- Maintenance / graph ---
    "memory/cron/graph_compaction.log": 200_000,
    "memory/cron/graph_checkpoint.log": 200_000,
    "memory/cron/graph_verify.log": 200_000,
    "memory/cron/chromadb_vacuum.log": 200_000,
    "memory/cron/backup.log": 200_000,
    "memory/cron/backup_verify.log": 200_000,
    # --- Orchestration / agents ---
    "memory/cron/orchestrator.log": 200_000,
    "memory/cron/spawn_claude.log": 200_000,
    "memory/cron/project_agents.log": 200_000,
    # --- Evaluation / benchmarks ---
    "memory/cron/llm_brain_review.log": 100_000,
    "memory/cron/brain_eval.log": 100_000,
    "memory/cron/pi_refresh.log": 100_000,
    "memory/cron/pi_benchmark.log": 100_000,
    "memory/cron/clr_benchmark.log": 100_000,
    # --- Hygiene / cleanup ---
    "memory/cron/brain_hygiene.log": 100_000,
    "memory/cron/goal_hygiene.log": 100_000,
    "memory/cron/data_lifecycle.log": 100_000,
    "memory/cron/cleanup.log": 100_000,
    "memory/cron/doctor.log": 100_000,
    # --- Reports (smaller) ---
    "memory/cron/report_morning.log": 100_000,
    "memory/cron/report_evening.log": 100_000,
    # --- Misc ---
    "memory/cron/watchdog.log": 200_000,
    "memory/cron/absolute_zero.log": 100_000,
    "memory/cron/relevance_refresh.log": 100_000,
    "memory/cron/graph_soak_manager.log": 100_000,
    "memory/cron/monthly_reflection.log": 100_000,
    "memory/cron/brief_benchmark.log": 100_000,
    "memory/cron/status_json.log": 100_000,
    "memory/cron/densify.log": 100_000,
    "memory/cron/agent_lifecycle.log": 100_000,
    "memory/cron/graph_migrate.log": 100_000,
}

MAX_ROTATED_COPIES = 2

# Daily memory: compress after N days, delete .gz after M days
MEMORY_COMPRESS_AFTER_DAYS = 3
MEMORY_DELETE_GZ_AFTER_DAYS = 90

# JSONL trimming: {relative_path: max_lines_to_keep}
# Files listed explicitly get their stated cap.
# Any unlisted .jsonl file >JSONL_AUTO_DISCOVER_BYTES is trimmed to JSONL_AUTO_DISCOVER_LINES.
JSONL_TRIM = {
    # --- High-volume operational logs ---
    "data/hebbian/access_log.jsonl": 5000,
    "data/hebbian/evolution_history.jsonl": 500,
    "data/retrieval_quality/events.jsonl": 2000,
    "data/thought_log.jsonl": 2000,
    "data/router_decisions.jsonl": 2000,
    "data/code_gen_outcomes.jsonl": 2000,
    "data/conflict_log.jsonl": 1500,
    "data/dashboard/events.jsonl": 1500,
    "data/task_sizing_log.jsonl": 1000,
    "data/costs.jsonl": 1000,
    "data/broadcast/broadcast_log.jsonl": 1000,
    "data/code_validation_outcomes.jsonl": 500,
    "data/postflight_completeness.jsonl": 500,
    # --- Analytics / history ---
    "data/meta_gradient_rl/adaptation_history.jsonl": 1000,
    "data/self_representation/state_history.jsonl": 500,
    "data/prompt_optimization/prompt_outcomes.jsonl": 500,
    "data/research_dispositions.jsonl": 500,
    "data/retrieval_quality/context_relevance.jsonl": 1000,
    "data/trajectory_eval/history.jsonl": 500,
    "data/trajectory_eval/cot_history.jsonl": 500,
    "data/calibration/predictions.jsonl": 500,
    "data/cognitive_workspace/reuse_log.jsonl": 1000,
    "data/retrieval_benchmark/history.jsonl": 500,
    "data/brief_token_stats.jsonl": 500,
    "data/attention/schema_history.jsonl": 500,
    "data/invariants_runs.jsonl": 500,
    # --- Benchmarks ---
    "data/benchmarks/brief_v2_benchmark.jsonl": 500,
    "data/orchestration_benchmarks/star-world-order_history.jsonl": 500,
    "data/orchestration_benchmarks/clarvis-db_history.jsonl": 500,
    "data/orchestration_benchmarks/kinkly_history.jsonl": 500,
    "data/orchestration_benchmarks/star-arena_history.jsonl": 500,
    "data/orchestration_benchmarks/goat_history.jsonl": 500,
    "data/orchestrator/scoreboard.jsonl": 500,
    # --- Smaller / lower volume ---
    "data/performance_history.jsonl": 1000,
    "data/performance_alerts.jsonl": 500,
    "data/latency_trend.jsonl": 1000,
    "data/retrieval_errors.jsonl": 500,
    "data/structural_health_history.jsonl": 500,
    "data/procedure_injection_log.jsonl": 500,
    "data/obligations_log.jsonl": 500,
    "data/theory_of_mind/events.jsonl": 500,
    "data/theory_of_mind/prediction_log.jsonl": 500,
    "data/directives_log.jsonl": 500,
    "data/clr_history.jsonl": 500,
    "data/decisions.jsonl": 500,
    # --- Session transcripts ---
    # Daily JSONL files are under data/session_transcripts/ and handled by
    # compress_old_transcripts() below, but auto-discover may catch very large ones.
}

# Auto-discover any .jsonl files in data/ not listed above — trim if >500KB.
JSONL_AUTO_DISCOVER_BYTES = 500_000
JSONL_AUTO_DISCOVER_LINES = 1000

# Stale lock cleanup
LOCK_MAX_AGE_SECONDS = 3600  # 1 hour
LOCK_PATTERN = "/tmp/clarvis_*.lock"

# Screenshot cleanup
SCREENSHOT_DIR = WORKSPACE / "data" / "browser_sessions" / "screenshots"
SCREENSHOT_MAX_AGE_DAYS = 7

# /tmp test install cleanup
# Naming convention (all prefixed "clarvis-" for discoverability):
#   clarvis-freshclone-*   — full repo clones for install testing
#   clarvis-fresh-venv*    — isolated venvs for pip install testing
#   clarvis-isolated-*     — isolated workspace dirs for e2e tests
#   clarvis_smoke_*        — smoke test workspaces (from fresh_install_smoke.sh)
#   clarvis_fork_*         — fork comparison dirs
# Retention: keep for 3 days (enough for debugging), then auto-remove.
# pytest tmp_path fixtures auto-clean — only manual test installs need this.
TMP_TEST_PREFIXES = [
    "clarvis-freshclone-",
    "clarvis-fresh-venv",
    "clarvis-isolated-",
    "clarvis_smoke_",
    "clarvis_fork_compare",
    "clarvis_fork_clone",
]
TMP_TEST_MAX_AGE_DAYS = 3


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
        self.tmp_installs_removed = 0

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
            f"  Tmp test installs removed: {self.tmp_installs_removed}",
        ]
        if self.actions:
            lines.append("  Actions:")
            for a in self.actions:
                lines.append(f"    - {a}")
        return "\n".join(lines)


def _rotation_path(filepath: Path, i: int) -> Path:
    """Return the path for rotation index i (e.g. foo.log.1, foo.log.2)."""
    if filepath.suffix == ".log":
        return filepath.with_suffix(f".log.{i}")
    return Path(str(filepath) + f".{i}")


def _remove_with_gz(path: Path, report: CleanupReport, dry_run: bool):
    """Remove a rotation path and/or its .gz variant, updating the report."""
    for p in (Path(str(path) + ".gz"), path):
        if p.exists():
            sz = p.stat().st_size
            if not dry_run:
                p.unlink()
            report.bytes_freed += sz
            report.files_removed += 1
            report.log(f"Deleted oldest rotation: {p.name}")


def rotate_log(filepath: Path, max_bytes: int, report: CleanupReport, dry_run: bool):
    """Rotate a log file if it exceeds max_bytes.

    Keeps up to MAX_ROTATED_COPIES rotated files:
      .log.1  — most recent rotation (uncompressed for quick inspection)
      .log.2.gz — older rotation (gzip-compressed)
    Anything beyond MAX_ROTATED_COPIES is deleted.
    """
    if not filepath.exists():
        return
    size = filepath.stat().st_size
    if size <= max_bytes:
        return

    # 1. Purge excessive generations beyond MAX_ROTATED_COPIES
    for i in range(MAX_ROTATED_COPIES + 1, MAX_ROTATED_COPIES + 5):
        _remove_with_gz(_rotation_path(filepath, i), report, dry_run)

    # 2. Delete the oldest kept slot to make room
    _remove_with_gz(_rotation_path(filepath, MAX_ROTATED_COPIES), report, dry_run)

    # 3. Shift remaining rotations up: .1 -> .2, etc.
    for i in range(MAX_ROTATED_COPIES - 1, 0, -1):
        src = _rotation_path(filepath, i)
        src_gz = Path(str(src) + ".gz")
        dst = _rotation_path(filepath, i + 1)
        # Handle both compressed and uncompressed variants
        if src_gz.exists():
            if not dry_run:
                src_gz.rename(Path(str(dst) + ".gz"))
        elif src.exists():
            if not dry_run:
                src.rename(dst)

    # 4. Current -> .1
    rotated = _rotation_path(filepath, 1)
    if not dry_run:
        filepath.rename(rotated)
        filepath.touch()  # Create empty new log
    report.files_rotated += 1
    report.log(f"Rotated {filepath.name} ({size:,} bytes)")

    # 5. Gzip the oldest kept rotation (.log.2 -> .log.2.gz)
    oldest = _rotation_path(filepath, MAX_ROTATED_COPIES)
    oldest_gz = Path(str(oldest) + ".gz")
    if oldest.exists() and not oldest_gz.exists():
        orig_sz = oldest.stat().st_size
        if not dry_run:
            with open(oldest, "rb") as fin:
                with gzip.open(oldest_gz, "wb", compresslevel=6) as fout:
                    fout.write(fin.read())
            oldest.unlink()
        gz_sz = oldest_gz.stat().st_size if oldest_gz.exists() and not dry_run else orig_sz // 4
        report.bytes_freed += orig_sz - gz_sz
        report.files_compressed += 1
        report.log(f"Compressed {oldest.name} -> {oldest_gz.name}")


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


TRANSCRIPT_DIR = WORKSPACE / "data" / "session_transcripts"
TRANSCRIPT_RAW_DIR = TRANSCRIPT_DIR / "raw"
TRANSCRIPT_COMPRESS_AFTER_DAYS = 7
TRANSCRIPT_DELETE_GZ_AFTER_DAYS = 90
TRANSCRIPT_RAW_DELETE_AFTER_DAYS = 14


def compress_old_transcripts(report: CleanupReport, dry_run: bool):
    """Compress session transcript JSONL files older than 7 days, delete .gz after 90 days.
    Also delete raw output files older than 14 days."""
    if not TRANSCRIPT_DIR.exists():
        return

    # Compress old JSONL files
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRANSCRIPT_COMPRESS_AFTER_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    for f in sorted(TRANSCRIPT_DIR.glob("????-??-??.jsonl")):
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.jsonl$", f.name)
        if not date_match or date_match.group(1) >= cutoff_str:
            continue
        gz_path = f.with_suffix(".jsonl.gz")
        if gz_path.exists():
            continue
        original_size = f.stat().st_size
        if not dry_run:
            with open(f, "rb") as fin:
                with gzip.open(gz_path, "wb", compresslevel=9) as fout:
                    fout.write(fin.read())
            f.unlink()
        report.files_compressed += 1
        report.bytes_freed += original_size
        report.log(f"Compressed transcript {f.name} ({original_size:,} bytes)")

    # Delete very old compressed transcripts
    delete_cutoff = datetime.now(timezone.utc) - timedelta(days=TRANSCRIPT_DELETE_GZ_AFTER_DAYS)
    delete_str = delete_cutoff.strftime("%Y-%m-%d")
    for f in sorted(TRANSCRIPT_DIR.glob("????-??-??.jsonl.gz")):
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.jsonl\.gz$", f.name)
        if not date_match or date_match.group(1) >= delete_str:
            continue
        size = f.stat().st_size
        if not dry_run:
            f.unlink()
        report.files_removed += 1
        report.bytes_freed += size
        report.log(f"Deleted old transcript archive: {f.name}")

    # Delete old raw output files
    if TRANSCRIPT_RAW_DIR.exists():
        raw_cutoff = time.time() - (TRANSCRIPT_RAW_DELETE_AFTER_DAYS * 86400)
        for f in TRANSCRIPT_RAW_DIR.iterdir():
            if not f.is_file():
                continue
            try:
                if f.stat().st_mtime < raw_cutoff:
                    size = f.stat().st_size
                    if not dry_run:
                        f.unlink()
                    report.files_removed += 1
                    report.bytes_freed += size
                    report.log(f"Deleted old raw transcript: {f.name}")
            except OSError:
                continue


def clean_tmp_test_installs(report: CleanupReport, dry_run: bool):
    """Remove stale /tmp test install directories older than TMP_TEST_MAX_AGE_DAYS.

    Only removes dirs/files matching known clarvis test prefixes.
    Directories are removed recursively; files are unlinked.
    """
    cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
    tmp = Path("/tmp")
    if not tmp.exists():
        return

    for entry in tmp.iterdir():
        # Check if name matches any known test prefix
        if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
            continue
        try:
            mtime = entry.stat().st_mtime
            if mtime >= cutoff:
                continue  # Too recent, keep for debugging
            if entry.is_dir():
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                if not dry_run:
                    shutil.rmtree(entry)
                report.bytes_freed += size
                report.files_removed += 1
                report.log(f"Removed stale test install: {entry.name} ({size:,} bytes, age={int((time.time()-mtime)/86400)}d)")
            elif entry.is_file():
                size = entry.stat().st_size
                if not dry_run:
                    entry.unlink()
                report.bytes_freed += size
                report.files_removed += 1
                report.log(f"Removed stale test artifact: {entry.name} ({size:,} bytes)")
        except (OSError, PermissionError):
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

    # 3b. Compress old session transcripts, delete old raw files
    compress_old_transcripts(report, dry_run)

    # 4. Trim JSONL files (explicit list)
    for rel_path, max_lines in JSONL_TRIM.items():
        trim_jsonl(WORKSPACE / rel_path, max_lines, report, dry_run)

    # 4b. Auto-discover unlisted JSONL files above size threshold
    known_jsonl = {(WORKSPACE / p).resolve() for p in JSONL_TRIM}
    data_dir = WORKSPACE / "data"
    if data_dir.exists():
        for jf in data_dir.rglob("*.jsonl"):
            if jf.resolve() in known_jsonl:
                continue
            try:
                if jf.stat().st_size > JSONL_AUTO_DISCOVER_BYTES:
                    trim_jsonl(jf, JSONL_AUTO_DISCOVER_LINES, report, dry_run)
            except OSError:
                continue

    # 5. Clean stale locks
    clean_stale_locks(report, dry_run)

    # 6. Clean old screenshots
    clean_screenshots(report, dry_run)

    # 7. Clean stale /tmp test installs
    clean_tmp_test_installs(report, dry_run)

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
            "tmp_installs_removed": report.tmp_installs_removed,
            "actions": report.actions,
        }, indent=2))
    else:
        print(report.summary())

    if args.verbose and not args.json:
        for a in report.actions:
            print(f"  {a}")


if __name__ == "__main__":
    main()

"""clarvis cron — inspect and wrap-run cron jobs.

Provides inspection of system crontab entries and a wrapper to call
existing cron_*.sh scripts via subprocess (no logic rewrite).

Usage:
    clarvis cron list          # Show clarvis cron entries from crontab
    clarvis cron status        # Last-run timestamps from memory/cron/*.log
    clarvis cron run <job>     # Wrap-call scripts/cron_<job>.sh
    clarvis cron run <job> --dry-run   # Print what would be called
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = Path("/home/agent/.openclaw/workspace")
SCRIPTS = WORKSPACE / "scripts"
CRON_LOG_DIR = WORKSPACE / "memory" / "cron"

# Map short names to script filenames.  Only entries that exist on disk
# are considered valid targets for `clarvis cron run`.
_KNOWN_JOBS = [
    "autonomous",
    "morning",
    "evening",
    "evolution",
    "reflection",
    "research",
    "implementation_sprint",
    "strategic_audit",
    "report_morning",
    "report_evening",
    "cleanup",
    "graph_checkpoint",
    "graph_compaction",
    "chromadb_vacuum",
]


def _script_path(job: str) -> Path:
    """Return the path to scripts/cron_<job>.sh."""
    return SCRIPTS / f"cron_{job}.sh"


def _log_path(job: str) -> Path:
    """Return the path to memory/cron/<job>.log."""
    return CRON_LOG_DIR / f"{job}.log"


def _parse_crontab() -> list[dict]:
    """Parse ``crontab -l`` and return clarvis-related entries."""
    try:
        raw = subprocess.check_output(["crontab", "-l"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Skip @reboot and non-clarvis lines
        if "openclaw/workspace/scripts/cron_" not in line and \
           "openclaw/workspace/scripts/backup_" not in line and \
           "openclaw/workspace/scripts/health_monitor" not in line and \
           "openclaw/workspace/scripts/dream_engine" not in line:
            continue

        # Extract schedule + command
        # Standard cron: min hour dom mon dow command...
        # @reboot handled above (skipped)
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        schedule = " ".join(parts[:5])
        command = parts[5]

        # Extract the primary script (the last scripts/*.sh or scripts/*.py in the line,
        # which is the actual job — not a sourced helper like cron_env.sh)
        all_scripts = re.findall(r"scripts/([\w_]+\.(?:sh|py))", command)
        if not all_scripts:
            script_name = command.split("/")[-1].split()[0]
        else:
            # Use the last match (skip sourced helpers like cron_env.sh)
            script_name = all_scripts[-1]

        # Skip if the primary script is just a sourced env helper
        if script_name == "cron_env.sh":
            continue

        # Derive short job name
        short = script_name.replace("cron_", "").replace(".sh", "").replace(".py", "")

        entries.append({
            "schedule": schedule,
            "script": script_name,
            "job": short,
            "full_line": line,
        })
    return entries


def _last_log_timestamp(log_file: Path) -> Optional[str]:
    """Extract the last ISO timestamp from a cron log file."""
    if not log_file.exists():
        return None
    try:
        # Read last 4KB — timestamps are near the end
        size = log_file.stat().st_size
        with open(log_file, "r") as f:
            if size > 4096:
                f.seek(size - 4096)
            tail = f.read()

        # Match ISO timestamps like [2026-03-04T20:00:01]
        timestamps = re.findall(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]", tail)
        if timestamps:
            return timestamps[-1]

        # Fallback: use file mtime
        mtime = log_file.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


@app.command("list")
def list_jobs():
    """Show clarvis cron entries from system crontab."""
    entries = _parse_crontab()
    if not entries:
        print("No clarvis cron entries found in crontab.")
        raise typer.Exit(1)

    # Column widths
    sched_w = max(len(e["schedule"]) for e in entries)
    job_w = max(len(e["job"]) for e in entries)

    print(f"{'Schedule':<{sched_w}}  {'Job':<{job_w}}  Script")
    print(f"{'─' * sched_w}  {'─' * job_w}  {'─' * 30}")
    for e in entries:
        print(f"{e['schedule']:<{sched_w}}  {e['job']:<{job_w}}  {e['script']}")
    print(f"\n{len(entries)} cron entries.")


@app.command()
def status():
    """Show last-run timestamps for cron jobs (from log files)."""
    # Collect known log files
    logs: list[tuple[str, Path]] = []
    for job in _KNOWN_JOBS:
        lp = _log_path(job)
        if lp.exists():
            logs.append((job, lp))

    # Also check for any *.log files we might have missed
    if CRON_LOG_DIR.exists():
        for lf in sorted(CRON_LOG_DIR.glob("*.log")):
            job_name = lf.stem
            if job_name not in [j for j, _ in logs]:
                logs.append((job_name, lf))

    if not logs:
        print("No cron log files found.")
        raise typer.Exit(1)

    name_w = max(len(j) for j, _ in logs)
    print(f"{'Job':<{name_w}}  {'Last Run':<20}  Log Size")
    print(f"{'─' * name_w}  {'─' * 20}  {'─' * 10}")
    for job, lf in logs:
        ts = _last_log_timestamp(lf) or "unknown"
        size = lf.stat().st_size
        if size > 1_048_576:
            size_str = f"{size / 1_048_576:.1f} MB"
        elif size > 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        print(f"{job:<{name_w}}  {ts:<20}  {size_str}")


@app.command()
def run(
    job: str = typer.Argument(help="Job name (e.g. 'reflection', 'autonomous', 'research')."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be called without executing."),
):
    """Wrap-call scripts/cron_<job>.sh via subprocess.

    This is WRAP MODE — it delegates to the existing shell script without
    rewriting any logic.  Lock acquisition, env bootstrap, and timeout
    handling remain in the shell script.
    """
    script = _script_path(job)
    if not script.exists():
        print(f"Error: script not found: {script}")
        print(f"Known jobs: {', '.join(j for j in _KNOWN_JOBS if _script_path(j).exists())}")
        raise typer.Exit(1)

    cmd = [str(script)]
    log_file = _log_path(job)

    if dry_run:
        print(f"[dry-run] Would execute: {script}")
        print(f"[dry-run] Log would append to: {log_file}")
        print(f"[dry-run] Equivalent crontab invocation:")
        print(f"  {script} >> {log_file} 2>&1")
        return

    print(f"Running: {script}")
    print(f"Log: {log_file}")
    print("(output streams to log file — this may take several minutes)")

    # Execute in workspace directory, inheriting env
    result = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if result.returncode == 0:
        print(f"\nJob '{job}' completed successfully.")
    else:
        print(f"\nJob '{job}' exited with code {result.returncode}.")
        raise typer.Exit(result.returncode)

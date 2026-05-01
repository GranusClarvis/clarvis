"""clarvis cron — inspect, install, and manage cron jobs.

Usage:
    clarvis cron list                    # Show clarvis cron entries from crontab
    clarvis cron status                  # Last-run timestamps from memory/cron/*.log
    clarvis cron run <job>               # Wrap-call scripts/cron_<job>.sh
    clarvis cron run <job> --dry-run     # Print what would be called
    clarvis cron presets                 # List available cron presets
    clarvis cron install <preset>        # Install a cron preset (with dry-run preview)
    clarvis cron install <preset> --apply  # Apply after reviewing dry-run
    clarvis cron remove                  # Remove all clarvis cron entries (with dry-run)
    clarvis cron remove --apply          # Actually remove
"""

import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
SCRIPTS = WORKSPACE / "scripts"
CRON_LOG_DIR = WORKSPACE / "memory" / "cron"
CRONTAB_REFERENCE = SCRIPTS / "crontab.reference"

# Sentinel comment that marks Clarvis-managed blocks in crontab.
_BLOCK_START = "# >>> clarvis-managed (do not edit) >>>"
_BLOCK_END = "# <<< clarvis-managed <<<"

# ── Crontab Isolation ──────────────────────────────────────────────────
# Set CLARVIS_CRONTAB_FILE to redirect all crontab read/write operations
# to a plain text file instead of the system crontab.  This is used by:
#   - Isolated tests (prevent production crontab mutation)
#   - Dry-run previews in non-standard environments
#   - Fresh installs that want to stage before committing
#
# When set, `crontab -l` and `crontab <file>` are replaced with file I/O.
_CRONTAB_FILE = os.environ.get("CLARVIS_CRONTAB_FILE", "")


def _is_isolated_workspace() -> bool:
    """Return True if workspace is under /tmp (test/isolated install)."""
    return str(WORKSPACE).startswith("/tmp")

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
    "graph_verify",
    "intra_density_boost",
    "chromadb_vacuum",
    "monthly_reflection",
    "orchestrator",
    "llm_brain_review",
    "brain_eval",
    "pi_refresh",
    "clr_benchmark",
    "absolute_zero",
]


# ── Cron Preset Definitions ─────────────────────────────────────────────
# Each preset is a list of crontab lines.  __WORKSPACE__ is replaced at
# install time with the actual workspace path.

def _ws(path: str) -> str:
    """Expand __WORKSPACE__ placeholder."""
    return path.replace("__WORKSPACE__", str(WORKSPACE))


def _job(schedule: str, script: str, log: str) -> str:
    """Build a crontab line from schedule + script + log."""
    s = _ws(script)
    l = _ws(log)
    return f"{schedule} {s} >> {l} 2>&1"


def _env_prefix() -> str:
    return f". {WORKSPACE}/scripts/cron/cron_env.sh &&"


# Shared job definitions used across presets
# Paths updated 2026-04-04 for scripts/ subdirectory reorganization:
#   cron_*.sh    → scripts/cron/
#   health/backup/infra → scripts/infra/
#   dream/cognition     → scripts/cognition/
#   brain/memory        → scripts/brain_mem/
#   metrics/benchmarks  → scripts/metrics/
#   hygiene/hooks       → scripts/hooks/
#   data lifecycle      → scripts/infra/
_JOBS = {
    # Monitoring (always recommended)
    "health_monitor": "*/15 * * * * __WORKSPACE__/scripts/infra/health_monitor.sh >> __WORKSPACE__/monitoring/health.log 2>&1",
    "watchdog": "*/30 * * * * __WORKSPACE__/scripts/cron/cron_watchdog.sh >> __WORKSPACE__/monitoring/watchdog.log 2>&1",
    # Backup
    "backup": "0 2 * * * __WORKSPACE__/scripts/infra/backup_daily.sh >> __WORKSPACE__/memory/cron/backup.log 2>&1",
    "backup_verify": "30 2 * * * __WORKSPACE__/scripts/infra/backup_verify.sh >> __WORKSPACE__/memory/cron/backup_verify.log 2>&1",
    # Maintenance window (04:00-05:00)
    "graph_checkpoint": "0 4 * * * __WORKSPACE__/scripts/cron/cron_graph_checkpoint.sh >> __WORKSPACE__/memory/cron/graph_checkpoint.log 2>&1",
    "graph_compaction": "30 4 * * * __WORKSPACE__/scripts/cron/cron_graph_compaction.sh >> __WORKSPACE__/memory/cron/graph_compaction.log 2>&1",
    "graph_verify": "45 4 * * * __WORKSPACE__/scripts/cron/cron_graph_verify.sh >> __WORKSPACE__/memory/cron/graph_verify.log 2>&1",
    "intra_density_boost": "50 4 * * * __WORKSPACE__/scripts/cron/cron_intra_density_boost.sh >> __WORKSPACE__/memory/cron/intra_density_boost.log 2>&1",
    "chromadb_vacuum": "0 5 * * * __WORKSPACE__/scripts/cron/cron_chromadb_vacuum.sh >> __WORKSPACE__/memory/cron/chromadb_vacuum.log 2>&1",
    # Core cycle
    "morning": "0 8 * * * __WORKSPACE__/scripts/cron/cron_morning.sh >> __WORKSPACE__/memory/cron/morning.log 2>&1",
    "evening": "0 18 * * * __WORKSPACE__/scripts/cron/cron_evening.sh >> __WORKSPACE__/memory/cron/evening.log 2>&1",
    "reflection": "0 21 * * * __WORKSPACE__/scripts/cron/cron_reflection.sh >> __WORKSPACE__/memory/cron/reflection.log 2>&1",
    "evolution": "0 13 * * * __WORKSPACE__/scripts/cron/cron_evolution.sh >> __WORKSPACE__/memory/cron/evolution.log 2>&1",
    # Autonomous (various hours)
    "autonomous_06": "0 6 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_07": "0 7 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_09": "0 9 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_11": "0 11 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_12": "0 12 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_15": "0 15 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_17": "0 17 * * 0,1,2,4,5 __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_19": "0 19 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_20": "0 20 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_22": "0 22 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_23": "0 23 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    "autonomous_01": "0 1 * * * __WORKSPACE__/scripts/cron/cron_autonomous.sh >> __WORKSPACE__/memory/cron/autonomous.log 2>&1",
    # Research
    "research_am": "0 10 * * * __WORKSPACE__/scripts/cron/cron_research.sh >> __WORKSPACE__/memory/cron/research.log 2>&1",
    "research_pm": "0 16 * * * __WORKSPACE__/scripts/cron/cron_research.sh >> __WORKSPACE__/memory/cron/research.log 2>&1",
    # Specialized
    "implementation_sprint": "0 14 * * * __WORKSPACE__/scripts/cron/cron_implementation_sprint.sh >> __WORKSPACE__/memory/cron/implementation_sprint.log 2>&1",
    "strategic_audit": "0 17 * * 3,6 __WORKSPACE__/scripts/cron/cron_strategic_audit.sh >> __WORKSPACE__/memory/cron/strategic_audit.log 2>&1",
    "dream": "45 2 * * * . __WORKSPACE__/scripts/cron/cron_env.sh && timeout 900 python3 __WORKSPACE__/scripts/cognition/dream_engine.py dream >> __WORKSPACE__/memory/cron/dream.log 2>&1",
    # Reports
    "report_morning": "30 9 * * * __WORKSPACE__/scripts/cron/cron_report_morning.sh >> __WORKSPACE__/memory/cron/report_morning.log 2>&1",
    "report_evening": "30 22 * * * __WORKSPACE__/scripts/cron/cron_report_evening.sh >> __WORKSPACE__/memory/cron/report_evening.log 2>&1",
    # Weekly hygiene (Sunday)
    "goal_hygiene": "10 5 * * 0 cd __WORKSPACE__ && python3 scripts/hooks/goal_hygiene.py clean >> memory/cron/goal_hygiene.log 2>&1",
    "brain_hygiene": "15 5 * * 0 cd __WORKSPACE__ && python3 scripts/brain_mem/brain_hygiene.py run >> memory/cron/brain_hygiene.log 2>&1",
    "data_lifecycle": "20 5 * * 0 cd __WORKSPACE__ && python3 scripts/infra/data_lifecycle.py >> memory/cron/data_lifecycle.log 2>&1",
    "cleanup": "30 5 * * 0 __WORKSPACE__/scripts/cron/cron_cleanup.sh >> __WORKSPACE__/memory/cron/cleanup.log 2>&1",
    # Evaluation
    "pi_refresh": "45 5 * * * __WORKSPACE__/scripts/cron/cron_pi_refresh.sh >> __WORKSPACE__/memory/cron/pi_refresh.log 2>&1",
    "status_json": "50 5 * * * . __WORKSPACE__/scripts/cron/cron_env.sh && python3 __WORKSPACE__/scripts/infra/generate_status_json.py >> __WORKSPACE__/memory/cron/status_json.log 2>&1",
    "brain_eval": "5 6 * * * __WORKSPACE__/scripts/cron/cron_brain_eval.sh >> __WORKSPACE__/memory/cron/brain_eval.log 2>&1",
    "llm_brain_review": "15 6 * * * __WORKSPACE__/scripts/cron/cron_llm_brain_review.sh >> __WORKSPACE__/memory/cron/llm_brain_review.log 2>&1",
    "heartbeat_notask_triage": "25 6 * * * __WORKSPACE__/scripts/cron/heartbeat_notask_triage.sh 7 >> __WORKSPACE__/memory/cron/heartbeat_triage.log 2>&1",
    "digest_actionability": "35 22 * * * __WORKSPACE__/scripts/maint/digest_actionability_check.sh >> __WORKSPACE__/memory/cron/digest_actionability.log 2>&1",
    "notask_attribution": "55 23 * * * __WORKSPACE__/scripts/maint/notask_attribution.sh >> __WORKSPACE__/memory/cron/notask_attribution.log 2>&1",
    "relevance_refresh": "40 2 * * * . __WORKSPACE__/scripts/cron/cron_env.sh && python3 -m clarvis cognition context-relevance refresh >> __WORKSPACE__/memory/cron/relevance_refresh.log 2>&1",
    "orchestrator": "30 19 * * * __WORKSPACE__/scripts/cron/cron_orchestrator.sh >> __WORKSPACE__/memory/cron/orchestrator.log 2>&1",
    # Monthly
    "monthly_reflection": "30 3 1 * * __WORKSPACE__/scripts/cron/cron_monthly_reflection.sh >> __WORKSPACE__/memory/cron/monthly_reflection.log 2>&1",
    "brief_benchmark": "45 3 1 * * . __WORKSPACE__/scripts/cron/cron_env.sh && python3 __WORKSPACE__/scripts/metrics/brief_benchmark.py >> __WORKSPACE__/memory/cron/brief_benchmark.log 2>&1",
    # Weekly benchmarks (Sunday)
    "pi_benchmark": "0 6 * * 0 . __WORKSPACE__/scripts/cron/cron_env.sh && python3 __WORKSPACE__/scripts/metrics/performance_benchmark.py record >> __WORKSPACE__/memory/cron/pi_benchmark.log 2>&1",
    "clr_benchmark": "30 6 * * 0 __WORKSPACE__/scripts/cron/cron_clr_benchmark.sh >> __WORKSPACE__/memory/cron/clr_benchmark.log 2>&1",
    "absolute_zero": "0 3 * * 0 __WORKSPACE__/scripts/cron/cron_absolute_zero.sh >> __WORKSPACE__/memory/cron/absolute_zero.log 2>&1",
}


# Preset definitions: which jobs are included in each preset.
_PRESETS: dict[str, dict] = {
    "minimal": {
        "description": "Monitoring + backup + weekly cleanup only. No Claude Code spawning.",
        "jobs": [
            "health_monitor", "watchdog",
            "backup", "backup_verify",
            "graph_checkpoint", "graph_compaction", "graph_verify", "intra_density_boost", "chromadb_vacuum",
            "cleanup", "data_lifecycle",
            "pi_refresh", "status_json",
        ],
    },
    "recommended": {
        "description": "Core daily cycle + maintenance + weekly hygiene. 4 autonomous runs/day.",
        "jobs": [
            # Monitoring
            "health_monitor", "watchdog",
            # Backup
            "backup", "backup_verify",
            # Maintenance
            "graph_checkpoint", "graph_compaction", "graph_verify", "intra_density_boost", "chromadb_vacuum",
            # Core daily cycle
            "morning", "evening", "reflection", "evolution",
            # Moderate autonomous (4x/day)
            "autonomous_07", "autonomous_12", "autonomous_17", "autonomous_22",
            # Research (1x/day)
            "research_am",
            # Reports
            "report_morning", "report_evening",
            # Weekly hygiene
            "goal_hygiene", "brain_hygiene", "data_lifecycle", "cleanup",
            # Evaluation
            "pi_refresh", "status_json", "brain_eval", "heartbeat_notask_triage",
            # Maintenance guards
            "digest_actionability",
            "notask_attribution",
            # Monthly
            "monthly_reflection",
        ],
    },
    "full": {
        "description": "Complete schedule: 12x autonomous, 2x research, all evaluation + benchmarks.",
        "jobs": list(_JOBS.keys()),  # Everything
    },
    "research": {
        "description": "Research-heavy: recommended + extra research + dream engine + benchmarks.",
        "jobs": [
            # Monitoring
            "health_monitor", "watchdog",
            # Backup
            "backup", "backup_verify",
            # Maintenance
            "graph_checkpoint", "graph_compaction", "graph_verify", "intra_density_boost", "chromadb_vacuum",
            # Core daily cycle
            "morning", "evening", "reflection", "evolution",
            # Moderate autonomous (6x/day)
            "autonomous_07", "autonomous_09", "autonomous_12",
            "autonomous_17", "autonomous_20", "autonomous_23",
            # Research (2x/day)
            "research_am", "research_pm",
            # Dream engine
            "dream",
            # Implementation + audit
            "implementation_sprint", "strategic_audit",
            # Reports
            "report_morning", "report_evening",
            # Weekly hygiene
            "goal_hygiene", "brain_hygiene", "data_lifecycle", "cleanup",
            # Evaluation + benchmarks
            "pi_refresh", "status_json", "brain_eval", "llm_brain_review", "relevance_refresh",
            "heartbeat_notask_triage",
            "pi_benchmark", "clr_benchmark", "absolute_zero",
            # Orchestrator
            "orchestrator",
            # Monthly
            "monthly_reflection", "brief_benchmark",
        ],
    },
}


def _script_path(job: str) -> Path:
    """Return the path to scripts/cron/cron_<job>.sh."""
    return SCRIPTS / "cron" / f"cron_{job}.sh"


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
        # Skip @reboot and non-clarvis lines — match both old flat and new subdir paths
        if "openclaw/workspace/scripts/" not in line and "openclaw/workspace" not in line:
            continue
        # Must reference a known script pattern (cron job, backup, hygiene, etc.)
        if not re.search(r"scripts/(?:cron/cron_|infra/|cognition/|brain_mem/|metrics/|hooks/|cron_|backup_|health_monitor|dream_engine)", line):
            # Also match clarvis-managed lines that use `python3 -m clarvis` or `python3 scripts/`
            if "python3 -m clarvis" not in line and "python3 scripts/" not in line:
                continue

        # Extract schedule + command
        # Standard cron: min hour dom mon dow command...
        # @reboot handled above (skipped)
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        schedule = " ".join(parts[:5])
        command = parts[5]

        # Extract the primary script — handles both flat and subdirectory layouts
        # e.g. scripts/cron/cron_autonomous.sh, scripts/infra/health_monitor.sh
        all_scripts = re.findall(r"scripts/(?:[\w_]+/)?([\w_]+\.(?:sh|py))", command)
        if not all_scripts:
            # Try python -m clarvis ... pattern
            m = re.search(r"python3 -m clarvis (\S+)", command)
            if m:
                script_name = f"clarvis_{m.group(1).replace(' ', '_')}"
            else:
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


# ── Preset / Install / Remove commands ───────────────────────────────────

def _get_current_crontab() -> str:
    """Return the raw crontab content, or empty string if none.

    If CLARVIS_CRONTAB_FILE is set, reads from that file instead of
    the system crontab.  This enables fully isolated testing.
    """
    if _CRONTAB_FILE:
        try:
            return Path(_CRONTAB_FILE).read_text()
        except FileNotFoundError:
            return ""
    try:
        return subprocess.check_output(
            ["crontab", "-l"], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _strip_clarvis_block(crontab: str) -> tuple[str, bool]:
    """Remove the clarvis-managed block from a crontab string.

    Returns (cleaned_crontab, had_block).
    """
    lines = crontab.splitlines(keepends=True)
    out: list[str] = []
    inside = False
    had_block = False
    for line in lines:
        if line.strip() == _BLOCK_START:
            inside = True
            had_block = True
            continue
        if line.strip() == _BLOCK_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out), had_block


def _build_preset_block(preset_name: str) -> str:
    """Build the crontab block for a given preset."""
    preset = _PRESETS[preset_name]
    lines = [
        _BLOCK_START,
        f"# Preset: {preset_name} — {preset['description']}",
        f"# Installed: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"# Workspace: {WORKSPACE}",
        "",
    ]
    for job_key in preset["jobs"]:
        template = _JOBS.get(job_key)
        if template:
            lines.append(_ws(template))
    lines.append("")
    lines.append(_BLOCK_END)
    return "\n".join(lines) + "\n"


def _install_crontab(new_content: str) -> None:
    """Write a new crontab via a temp file.

    If CLARVIS_CRONTAB_FILE is set, writes to that file instead of
    the system crontab.  This enables fully isolated testing.
    """
    if _CRONTAB_FILE:
        Path(_CRONTAB_FILE).write_text(new_content)
        return
    with tempfile.NamedTemporaryFile(mode="w", suffix=".crontab", delete=False) as f:
        f.write(new_content)
        tmp = f.name
    try:
        subprocess.check_call(["crontab", tmp])
    finally:
        os.unlink(tmp)


@app.command()
def presets():
    """List available cron presets and their job counts."""
    print("Available cron presets:\n")
    for name, cfg in _PRESETS.items():
        count = len(cfg["jobs"])
        print(f"  {name:<14} {count:>3} jobs  {cfg['description']}")
    print(f"\nInstall with: clarvis cron install <preset>")
    print(f"Preview first (dry-run by default), then --apply to commit.")


@app.command()
def install(
    preset: str = typer.Argument(help="Preset name: minimal, recommended, full, research"),
    apply: bool = typer.Option(False, "--apply", help="Actually install (default is dry-run preview)."),
    force: bool = typer.Option(False, "--force", help="Override safety guards (e.g. /tmp workspace)."),
):
    """Install a cron preset into the system crontab.

    By default shows a dry-run preview.  Pass --apply to write.

    Clarvis entries are wrapped in sentinel comments so they can be safely
    updated or removed later without touching other crontab entries.

    Safety: if CLARVIS_WORKSPACE is under /tmp (isolated/test install),
    --apply is blocked unless CLARVIS_CRONTAB_FILE is set or --force is passed.
    This prevents test environments from mutating production crontabs.
    """
    if preset not in _PRESETS:
        print(f"Unknown preset: {preset}")
        print(f"Available: {', '.join(_PRESETS)}")
        raise typer.Exit(1)

    # Validate that required scripts exist
    missing = []
    for job_key in _PRESETS[preset]["jobs"]:
        template = _JOBS.get(job_key, "")
        expanded = _ws(template)
        # Extract script path from the crontab line
        parts = expanded.split()
        for part in parts:
            if part.endswith(".sh") and "/" in part:
                if not Path(part).exists():
                    missing.append(f"  {job_key}: {part}")
                break
    if missing:
        print("WARNING: Some scripts are missing on disk:")
        for m in missing:
            print(m)
        print("These jobs will fail until the scripts exist.\n")

    # Safety guard: block /tmp workspaces from touching system crontab
    if apply and _is_isolated_workspace() and not _CRONTAB_FILE and not force:
        print("BLOCKED: workspace is under /tmp (isolated/test environment).")
        print("Installing to the system crontab from a temporary workspace")
        print("would mutate production crons — this is almost certainly wrong.")
        print()
        print("Options:")
        print("  1. Set CLARVIS_CRONTAB_FILE=/path/to/file to use file-based isolation")
        print("  2. Pass --force to override this safety guard")
        print("  3. Run from the real workspace instead")
        raise typer.Exit(1)

    current = _get_current_crontab()
    cleaned, had_block = _strip_clarvis_block(current)
    block = _build_preset_block(preset)
    new_crontab = cleaned.rstrip("\n") + "\n\n" + block

    cfg = _PRESETS[preset]
    target = f"file ({_CRONTAB_FILE})" if _CRONTAB_FILE else "system crontab"
    print(f"Preset: {preset} — {cfg['description']}")
    print(f"Jobs:   {len(cfg['jobs'])}")
    print(f"Target: {target}")
    if had_block:
        print("Action: REPLACE existing clarvis cron block")
    else:
        print("Action: ADD clarvis cron block to crontab")
    print()

    if not apply:
        print("--- DRY RUN: proposed crontab additions ---")
        print(block)
        print("--- end dry run ---")
        print(f"\nTo apply: clarvis cron install {preset} --apply")
        return

    # Safety: back up current crontab
    backup = WORKSPACE / "memory" / "cron" / "crontab.backup"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(current)
    print(f"Backed up current crontab to {backup}")

    _install_crontab(new_crontab)
    print(f"Installed preset '{preset}' ({len(cfg['jobs'])} jobs) to {target}.")
    print(f"Verify: clarvis cron list")


@app.command()
def remove(
    apply: bool = typer.Option(False, "--apply", help="Actually remove (default is dry-run preview)."),
    force: bool = typer.Option(False, "--force", help="Override safety guards (e.g. /tmp workspace)."),
):
    """Remove all clarvis-managed cron entries.

    Only removes the sentinel-wrapped block added by 'clarvis cron install'.
    Other crontab entries are preserved.  Default is dry-run.
    """
    # Safety guard: block /tmp workspaces from touching system crontab
    if apply and _is_isolated_workspace() and not _CRONTAB_FILE and not force:
        print("BLOCKED: workspace is under /tmp (isolated/test environment).")
        print("Set CLARVIS_CRONTAB_FILE or pass --force to override.")
        raise typer.Exit(1)

    current = _get_current_crontab()
    cleaned, had_block = _strip_clarvis_block(current)

    if not had_block:
        print("No clarvis-managed cron block found in crontab.")
        print("(Only blocks installed via 'clarvis cron install' are managed.)")
        raise typer.Exit(0)

    if not apply:
        print("--- DRY RUN: would remove clarvis cron block ---")
        # Show what would be removed
        for line in current.splitlines():
            if line.strip() == _BLOCK_START:
                break
        in_block = False
        for line in current.splitlines():
            if line.strip() == _BLOCK_START:
                in_block = True
            if in_block:
                print(f"  - {line}")
            if line.strip() == _BLOCK_END:
                in_block = False
        print("--- end dry run ---")
        print("\nTo apply: clarvis cron remove --apply")
        return

    backup = WORKSPACE / "memory" / "cron" / "crontab.backup"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(current)
    print(f"Backed up current crontab to {backup}")

    _install_crontab(cleaned)
    print("Removed clarvis-managed cron block.")
    print("Other crontab entries preserved.")

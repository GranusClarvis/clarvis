#!/usr/bin/env python3
"""
Cron Doctor — Auto-recovery for failed cron jobs.

Reads watchdog output, classifies failure types, and attempts auto-fix:
  - crash:       re-run the failed job
  - timeout:     clear stale lock, re-run with extended timeout
  - import_error: log for manual fix, add to evolution queue
  - stale_lock:  detect and clear stale lock files
  - data_issue:  recreate missing log dirs/files

Wired into cron_watchdog.sh as a recovery step after failure detection.

Usage:
    python3 cron_doctor.py diagnose          # Analyze all jobs, print report
    python3 cron_doctor.py recover           # Diagnose + attempt auto-fix
    python3 cron_doctor.py recover --dry-run # Show what would be fixed
    python3 cron_doctor.py status            # Show recovery history
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
LOG_DIR = WORKSPACE / "memory" / "cron"
DOCTOR_LOG = LOG_DIR / "doctor.log"
DOCTOR_STATE = WORKSPACE / "data" / "cron_doctor_state.json"
LOCK_DIR = Path("/tmp")

# Map job names to their cron scripts, log files, lock files, and max age (hours)
JOBS = {
    "autonomous": {
        "script": "scripts/cron/cron_autonomous.sh",
        "log": "memory/cron/autonomous.log",
        "lock": "/tmp/clarvis_autonomous.lock",
        "max_age_hours": 4,
        "timeout": 600,
    },
    "health_monitor": {
        "script": "scripts/infra/health_monitor.sh",
        "log": "monitoring/health.log",
        "lock": None,
        "max_age_hours": 1,
        "timeout": 60,
    },
    "morning_report": {
        "script": "scripts/cron/cron_report_morning.sh",
        "log": "memory/cron/report_morning.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    "evening_report": {
        "script": "scripts/cron/cron_report_evening.sh",
        "log": "memory/cron/report_evening.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    "morning_plan": {
        "script": "scripts/cron/cron_morning.sh",
        "log": "memory/cron/morning.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "evolution": {
        "script": "scripts/cron/cron_evolution.sh",
        "log": "memory/cron/evolution.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "evening_review": {
        "script": "scripts/cron/cron_evening.sh",
        "log": "memory/cron/evening.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "reflection": {
        "script": "scripts/cron/cron_reflection.sh",
        "log": "memory/cron/reflection.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "backup": {
        "script": "scripts/infra/backup_daily.sh",
        "log": "memory/cron/backup.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    "backup_verify": {
        "script": "scripts/infra/backup_verify.sh",
        "log": "memory/cron/backup_verify.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 120,
    },
    "research": {
        "script": "scripts/cron/cron_research.sh",
        "log": "memory/cron/research.log",
        "lock": "/tmp/clarvis_research.lock",
        "max_age_hours": 10,
        "timeout": 1800,
    },
    "graph_compaction": {
        "script": "scripts/cron/cron_graph_compaction.sh",
        "log": "memory/cron/graph_compaction.log",
        "lock": "/tmp/clarvis_graph_compaction.lock",
        "max_age_hours": 26,
        "timeout": 300,
    },
    "db_vacuum": {
        "script": "scripts/cron/cron_chromadb_vacuum.sh",
        "log": "memory/cron/chromadb_vacuum.log",
        "lock": "/tmp/clarvis_chromadb_vacuum.lock",
        "max_age_hours": 26,
        "timeout": 300,
    },
    # --- Daily jobs added 2026-04-09 (Phase 1: Operational Truthfulness) ---
    "graph_checkpoint": {
        "script": "scripts/cron/cron_graph_checkpoint.sh",
        "log": "memory/cron/graph_checkpoint.log",
        "lock": "/tmp/clarvis_maintenance.lock",
        "max_age_hours": 26,
        "timeout": 300,
    },
    "graph_verify": {
        "script": "scripts/cron/cron_graph_verify.sh",
        "log": "memory/cron/graph_verify.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    "implementation_sprint": {
        "script": "scripts/cron/cron_implementation_sprint.sh",
        "log": "memory/cron/implementation_sprint.log",
        "lock": "/tmp/clarvis_implementation_sprint.lock",
        "max_age_hours": 26,
        "timeout": 1800,
    },
    "strategic_audit": {
        "script": "scripts/cron/cron_strategic_audit.sh",
        "log": "memory/cron/strategic_audit.log",
        "lock": None,
        "max_age_hours": 170,  # Wed+Sat only (~3.5 day max gap)
        "timeout": 1200,
    },
    "dream_engine": {
        "script": None,
        "command": ["python3", "scripts/cognition/dream_engine.py", "dream"],
        "log": "memory/cron/dream.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 900,
    },
    "orchestrator": {
        "script": "scripts/cron/cron_orchestrator.sh",
        "log": "memory/cron/orchestrator.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "pi_refresh": {
        "script": "scripts/cron/cron_pi_refresh.sh",
        "log": "memory/cron/pi_refresh.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    "brain_eval": {
        "script": "scripts/cron/cron_brain_eval.sh",
        "log": "memory/cron/brain_eval.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "llm_brain_review": {
        "script": "scripts/cron/cron_llm_brain_review.sh",
        "log": "memory/cron/llm_brain_review.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "llm_context_review": {
        "script": "scripts/cron/cron_llm_context_review.sh",
        "log": "memory/cron/llm_context_review.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 600,
    },
    "status_json": {
        "script": None,
        "command": ["python3", "scripts/infra/generate_status_json.py"],
        "log": "memory/cron/status_json.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 120,
    },
    "relevance_refresh": {
        "script": None,
        "command": ["python3", "-m", "clarvis", "cognition", "context-relevance", "refresh"],
        "log": "memory/cron/relevance_refresh.log",
        "lock": None,
        "max_age_hours": 26,
        "timeout": 300,
    },
    # --- Weekly jobs ---
    "cleanup": {
        "script": "scripts/cron/cron_cleanup.sh",
        "log": "memory/cron/cleanup.log",
        "lock": None,
        "max_age_hours": 170,  # weekly
        "timeout": 300,
    },
    "absolute_zero": {
        "script": "scripts/cron/cron_absolute_zero.sh",
        "log": "memory/cron/absolute_zero.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 1200,
    },
    "clr_benchmark": {
        "script": "scripts/cron/cron_clr_benchmark.sh",
        "log": "memory/cron/clr_benchmark.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 600,
    },
    "goal_hygiene": {
        "script": None,
        "command": ["python3", "scripts/hooks/goal_hygiene.py", "clean"],
        "log": "memory/cron/goal_hygiene.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 300,
    },
    "brain_hygiene": {
        "script": None,
        "command": ["python3", "scripts/brain_mem/brain_hygiene.py", "run"],
        "log": "memory/cron/brain_hygiene.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 600,
    },
    "data_lifecycle": {
        "script": None,
        "command": ["python3", "scripts/infra/data_lifecycle.py"],
        "log": "memory/cron/data_lifecycle.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 300,
    },
    "pi_benchmark": {
        "script": None,
        "command": ["python3", "scripts/metrics/performance_benchmark.py", "record"],
        "log": "memory/cron/pi_benchmark.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 600,
    },
    # --- Monthly jobs ---
    "monthly_reflection": {
        "script": "scripts/cron/cron_monthly_reflection.sh",
        "log": "memory/cron/monthly_reflection.log",
        "lock": None,
        "max_age_hours": 750,  # monthly
        "timeout": 1200,
    },
    "brief_benchmark": {
        "script": None,
        "command": ["python3", "scripts/metrics/brief_benchmark.py"],
        "log": "memory/cron/brief_benchmark.log",
        "lock": None,
        "max_age_hours": 750,
        "timeout": 300,
    },
    "canonical_state_refresh": {
        "script": None,
        "command": ["python3", "scripts/hooks/canonical_state_refresh.py"],
        "log": "memory/cron/canonical_state_refresh.log",
        "lock": None,
        "max_age_hours": 170,
        "timeout": 300,
    },
}

# Backoff multiplier for retries (seconds): attempt 1 = 30s wait, attempt 2 = 120s, etc.
BACKOFF_BASE = 30
BACKOFF_MULTIPLIER = 4
MAX_RETRIES_PER_DAY = 2


def _log(msg: str):
    """Append to doctor log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    DOCTOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DOCTOR_LOG, "a") as f:
        f.write(line)


def _load_state() -> dict:
    """Load recovery state (tracks retries per job per day)."""
    DOCTOR_STATE.parent.mkdir(parents=True, exist_ok=True)
    if DOCTOR_STATE.exists():
        try:
            state = json.loads(DOCTOR_STATE.read_text())
            # Reset counters if it's a new day
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if state.get("date") != today:
                state = {"date": today, "retries": {}, "recoveries": []}
            return state
        except (json.JSONDecodeError, KeyError):
            pass
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"date": today, "retries": {}, "recoveries": []}


def _save_state(state: dict):
    DOCTOR_STATE.parent.mkdir(parents=True, exist_ok=True)
    DOCTOR_STATE.write_text(json.dumps(state, indent=2))


# === FAILURE CLASSIFICATION ===

class FailureType:
    STALE_LOCK = "stale_lock"
    MISSING_LOG = "missing_log"
    CRASH = "crash"
    TIMEOUT = "timeout"
    IMPORT_ERROR = "import_error"
    DATA_ISSUE = "data_issue"
    UNKNOWN = "unknown"


def classify_failure(job_name: str, job_config: dict) -> dict | None:
    """
    Classify the failure type for a missed job.

    Returns None if the job is healthy, or a dict with:
      - job: job name
      - type: FailureType
      - detail: human-readable explanation
      - log_tail: last lines of the log (if available)
    """
    now = time.time()
    log_path = WORKSPACE / job_config["log"]
    lock_path = Path(job_config["lock"]) if job_config.get("lock") else None
    max_age_seconds = job_config["max_age_hours"] * 3600

    # Check 1: Is the log file missing entirely?
    if not log_path.exists():
        return {
            "job": job_name,
            "type": FailureType.MISSING_LOG,
            "detail": f"Log file missing: {log_path}",
            "log_tail": "",
        }

    # Check 2: Is the log file stale?
    file_mod = log_path.stat().st_mtime
    age = now - file_mod
    if age <= max_age_seconds:
        return None  # Job is healthy

    # Job is missed — now classify WHY

    # Read last 50 lines of log for diagnosis
    log_tail = ""
    try:
        with open(log_path) as f:
            lines = f.readlines()
            log_tail = "".join(lines[-50:])
    except Exception:
        pass

    # Check 3: Stale lock file (process not running but lock remains)
    if lock_path and lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            # Check if process is still running
            try:
                os.kill(pid, 0)
                # Process is running — it might be stuck (timeout)
                return {
                    "job": job_name,
                    "type": FailureType.TIMEOUT,
                    "detail": f"Process {pid} still running (may be stuck). Lock: {lock_path}",
                    "log_tail": log_tail,
                    "pid": pid,
                }
            except ProcessLookupError:
                # Process is dead but lock remains — stale lock
                return {
                    "job": job_name,
                    "type": FailureType.STALE_LOCK,
                    "detail": f"Stale lock: PID {pid} no longer running. Lock: {lock_path}",
                    "log_tail": log_tail,
                    "lock_path": str(lock_path),
                }
        except (ValueError, FileNotFoundError):
            # Lock file is corrupt or disappeared
            return {
                "job": job_name,
                "type": FailureType.STALE_LOCK,
                "detail": f"Corrupt lock file: {lock_path}",
                "log_tail": log_tail,
                "lock_path": str(lock_path),
            }

    # Check 4: Look at log tail for error patterns
    lower_tail = log_tail.lower()

    if re.search(r"importerror|modulenotfounderror|no module named", lower_tail):
        # Extract the module name
        match = re.search(r"(?:ImportError|ModuleNotFoundError)[:\s]+.*?['\"](\S+)['\"]", log_tail)
        module = match.group(1) if match else "unknown"
        return {
            "job": job_name,
            "type": FailureType.IMPORT_ERROR,
            "detail": f"Import error: missing module '{module}'",
            "log_tail": log_tail,
        }

    if re.search(r"timeout|timed out|exit code 124|killed|signal 9", lower_tail):
        return {
            "job": job_name,
            "type": FailureType.TIMEOUT,
            "detail": "Job appears to have timed out",
            "log_tail": log_tail,
        }

    if re.search(r"traceback|error|exception|failed|exit code [1-9]", lower_tail):
        # Extract last error line
        error_lines = [l.strip() for l in log_tail.split("\n")
                       if re.search(r"error|exception|traceback|failed", l.lower())]
        last_error = error_lines[-1][:200] if error_lines else "unknown error"
        return {
            "job": job_name,
            "type": FailureType.CRASH,
            "detail": f"Crash: {last_error}",
            "log_tail": log_tail,
        }

    if re.search(r"no such file|filenotfounderror|permission denied|errno", lower_tail):
        return {
            "job": job_name,
            "type": FailureType.DATA_ISSUE,
            "detail": "Data/file issue detected in logs",
            "log_tail": log_tail,
        }

    # Default: job is stale but we can't determine why
    hours_ago = int(age / 3600)
    return {
        "job": job_name,
        "type": FailureType.UNKNOWN,
        "detail": f"Job missed (last output {hours_ago}h ago) — no obvious error in logs",
        "log_tail": log_tail,
    }


# === AUTO-RECOVERY ACTIONS ===

def recover_stale_lock(failure: dict, dry_run: bool = False) -> dict:
    """Clear a stale lock file and re-run the job."""
    lock_path = failure.get("lock_path", "")
    job_name = failure["job"]
    result = {"action": "clear_lock_and_rerun", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        result["would_do"] = f"rm {lock_path}, then re-run {run_desc}"
        return result

    # Remove stale lock
    if lock_path and os.path.exists(lock_path):
        os.remove(lock_path)
        _log(f"RECOVERED: Cleared stale lock {lock_path} for {job_name}")
        result["lock_cleared"] = True

    # Re-run the job
    return _rerun_job(job_name, result)


def recover_crash(failure: dict, dry_run: bool = False) -> dict:
    """Re-run a crashed job with backoff."""
    job_name = failure["job"]
    result = {"action": "rerun_after_crash", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        result["would_do"] = f"Re-run {run_desc}"
        return result

    return _rerun_job(job_name, result)


def recover_timeout(failure: dict, dry_run: bool = False) -> dict:
    """Kill stuck process (if any) and re-run."""
    job_name = failure["job"]
    pid = failure.get("pid")
    result = {"action": "kill_and_rerun", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        actions = []
        if pid:
            actions.append(f"kill PID {pid}")
        lock = JOBS[job_name].get("lock")
        if lock:
            actions.append(f"clear lock {lock}")
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        actions.append(f"re-run {run_desc}")
        result["would_do"] = ", ".join(actions)
        return result

    # Kill the stuck process
    if pid:
        try:
            os.kill(pid, 9)  # SIGKILL
            _log(f"RECOVERED: Killed stuck process {pid} for {job_name}")
            result["killed_pid"] = pid
            time.sleep(2)  # Wait for cleanup
        except ProcessLookupError:
            pass  # Already dead

    # Clear lock if present
    lock = JOBS[job_name].get("lock")
    if lock and os.path.exists(lock):
        os.remove(lock)
        result["lock_cleared"] = True

    return _rerun_job(job_name, result)


def recover_missing_log(failure: dict, dry_run: bool = False) -> dict:
    """Create missing log directory/file, then re-run."""
    job_name = failure["job"]
    log_path = WORKSPACE / JOBS[job_name]["log"]
    result = {"action": "create_log_and_rerun", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        result["would_do"] = f"mkdir -p {log_path.parent}, touch {log_path}, re-run {run_desc}"
        return result

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch()
    _log(f"RECOVERED: Created missing log {log_path} for {job_name}")
    result["log_created"] = True

    return _rerun_job(job_name, result)


def recover_import_error(failure: dict, dry_run: bool = False) -> dict:
    """Import errors need code fixes — queue for evolution, don't blindly re-run."""
    job_name = failure["job"]
    detail = failure["detail"]
    result = {"action": "queue_evolution_task", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        result["would_do"] = f"Add evolution task to fix: {detail}"
        return result

    # Add to evolution queue instead of blind retry
    _add_evolution_task(f"Fix {job_name} cron job: {detail}")
    _log(f"QUEUED: Import error in {job_name} — added to evolution queue: {detail}")
    result["queued"] = True
    result["detail"] = detail
    return result


def recover_data_issue(failure: dict, dry_run: bool = False) -> dict:
    """Data issues: ensure dirs exist, re-run."""
    job_name = failure["job"]
    result = {"action": "fix_data_and_rerun", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        result["would_do"] = f"Ensure data dirs exist, re-run {run_desc}"
        return result

    # Ensure common data directories exist
    for d in ["data", "data/evolution", "data/evolution/failures",
              "data/evolution/fixes", "data/dashboard", "memory/cron", "monitoring"]:
        (WORKSPACE / d).mkdir(parents=True, exist_ok=True)

    return _rerun_job(job_name, result)


def recover_unknown(failure: dict, dry_run: bool = False) -> dict:
    """Unknown failure: simple re-run (most cron misses are transient)."""
    job_name = failure["job"]
    result = {"action": "rerun_unknown", "job": job_name}

    if dry_run:
        result["dry_run"] = True
        run_desc = " ".join(JOBS[job_name].get("command", [])) or JOBS[job_name].get("script", "?")
        result["would_do"] = f"Re-run {run_desc} (unknown cause)"
        return result

    return _rerun_job(job_name, result)


# === ChromaDB Health & Repair (Phase 4: Safety Hardening) ===

def check_chromadb_health(dry_run: bool = False) -> dict:
    """Check ChromaDB health and attempt repair if broken.

    Steps:
    1. Try to import and instantiate ClarvisBrain
    2. If it fails, attempt SQLite .recover on the ChromaDB sqlite3 file
    3. If .recover fails, try restoring from latest backup
    4. Returns a result dict with success/failure details
    """
    result = {"action": "chromadb_health_check", "job": "chromadb", "type": "chromadb_health"}
    data_dir = WORKSPACE / "data" / "clarvisdb"

    # Step 1: Try brain health check
    try:
        from clarvis.brain import get_brain
        b = get_brain()
        hc = b.health_check()
        if hc["status"] == "healthy":
            result["success"] = True
            result["detail"] = f"ChromaDB healthy: {hc['total_memories']} memories"
            return result
        else:
            result["issues"] = hc.get("issues", [])
            _log(f"ChromaDB health check issues: {hc.get('issues', [])}")
    except Exception as e:
        result["init_error"] = str(e)[:200]
        _log(f"ChromaDB init failed: {e}")

    if dry_run:
        result["dry_run"] = True
        result["would_do"] = "Attempt SQLite .recover on ChromaDB data, then restore from backup if needed"
        return result

    # Step 2: Try SQLite recover on ChromaDB's internal sqlite3 file
    chroma_sqlite = data_dir / "chroma.sqlite3"
    if chroma_sqlite.exists():
        recover_path = data_dir / "chroma.sqlite3.recover"
        try:
            _log("Attempting SQLite .recover on ChromaDB...")
            proc = subprocess.run(
                ["sqlite3", str(chroma_sqlite), ".recover"],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0 and proc.stdout:
                # Write recovered SQL to a new DB, then swap
                with open(recover_path, "w") as f:
                    f.write(proc.stdout)
                result["sqlite_recover"] = "output_captured"
                _log("SQLite .recover succeeded, output saved")
            else:
                result["sqlite_recover"] = f"failed: exit {proc.returncode}"
                _log(f"SQLite .recover failed: {proc.stderr[:200]}")
        except subprocess.TimeoutExpired:
            result["sqlite_recover"] = "timed_out"
            _log("SQLite .recover timed out after 120s")
        except FileNotFoundError:
            result["sqlite_recover"] = "sqlite3_not_found"
            _log("sqlite3 binary not found for .recover")
    else:
        result["sqlite_recover"] = "no_chroma_sqlite"

    # Step 3: Try restoring from latest backup
    backup_dir = Path(os.path.expanduser("~/.openclaw/backups/daily"))
    if backup_dir.exists():
        # Find most recent backup with brain data
        backups = sorted(backup_dir.glob("*/brain/"), reverse=True)
        if backups:
            latest_backup = backups[0]
            result["backup_found"] = str(latest_backup)
            _log(f"Latest brain backup: {latest_backup}")
            # Don't auto-restore — too risky. Queue for manual review.
            _add_evolution_task(
                f"ChromaDB repair needed: init failed, .recover attempted. "
                f"Latest backup at {latest_backup}. Manual restore may be needed."
            )
            result["queued_for_review"] = True
        else:
            result["backup_found"] = None
    else:
        result["backup_found"] = None

    result["success"] = False
    result["detail"] = "ChromaDB unhealthy — repair attempted, queued for review"
    return result


# Recovery dispatch
RECOVERY_HANDLERS = {
    FailureType.STALE_LOCK: recover_stale_lock,
    FailureType.MISSING_LOG: recover_missing_log,
    FailureType.CRASH: recover_crash,
    FailureType.TIMEOUT: recover_timeout,
    FailureType.IMPORT_ERROR: recover_import_error,
    FailureType.DATA_ISSUE: recover_data_issue,
    FailureType.UNKNOWN: recover_unknown,
}


def _rerun_job(job_name: str, result: dict) -> dict:
    """Re-run a cron job script or command."""
    job = JOBS[job_name]
    timeout = job.get("timeout", 600)

    # Build command: prefer explicit "command" list, else bash wrapper around "script"
    if job.get("command"):
        cmd = list(job["command"])
        cmd_desc = " ".join(cmd)
    elif job.get("script"):
        script = WORKSPACE / job["script"]
        if not script.exists():
            result["success"] = False
            result["error"] = f"Script not found: {script}"
            _log(f"FAILED: Cannot re-run {job_name} — script missing: {script}")
            return result
        cmd = ["bash", str(script)]
        cmd_desc = str(script)
    else:
        result["success"] = False
        result["error"] = f"No script or command configured for {job_name}"
        _log(f"FAILED: Cannot re-run {job_name} — no script or command configured")
        return result

    try:
        _log(f"RERUNNING: {job_name} via {cmd_desc} (timeout={timeout}s)")
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout,
            cwd=str(WORKSPACE),
            env={**os.environ, "HOME": os.path.expanduser("~")},
        )
        result["success"] = proc.returncode == 0
        result["exit_code"] = proc.returncode
        if proc.returncode == 0:
            _log(f"RECOVERED: {job_name} re-run succeeded")
        else:
            result["stderr_tail"] = proc.stderr[-300:] if proc.stderr else ""
            _log(f"FAILED: {job_name} re-run failed (exit {proc.returncode})")
    except subprocess.TimeoutExpired:
        result["success"] = False
        result["error"] = f"Re-run timed out after {timeout}s"
        _log(f"FAILED: {job_name} re-run timed out after {timeout}s")

    return result


def _add_evolution_task(task: str):
    """Add a fix task to QUEUE.md under P0 via shared queue_writer."""
    try:
        from clarvis.queue.writer import add_task
        add_task(task, priority="P0", source="cron-doctor")
    except ImportError:
        # Fallback: direct write with file locking
        import fcntl
        queue_path = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
        if not queue_path.exists():
            return
        lock_path = str(queue_path) + ".lock"
        lock_fd = open(lock_path, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            content = queue_path.read_text()
            marker = "## P0 — Do Next Heartbeat"
            tag = f"[CRON-DOCTOR] {task}"
            if tag in content:
                return
            if marker in content:
                parts = content.split(marker, 1)
                new_task = f"\n- [ ] {tag}"
                queue_path.write_text(parts[0] + marker + new_task + parts[1])
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()


# === MAIN ENTRY POINTS ===

def diagnose() -> list[dict]:
    """Diagnose all cron jobs. Returns list of failure dicts."""
    failures = []
    for job_name, job_config in JOBS.items():
        failure = classify_failure(job_name, job_config)
        if failure:
            failures.append(failure)
    return failures


def recover(dry_run: bool = False) -> list[dict]:
    """Diagnose and attempt recovery for all failed jobs.

    Also runs ChromaDB health check (Phase 4: safety hardening).
    """
    state = _load_state()
    failures = diagnose()
    results = []

    # ChromaDB health check — runs once per recovery cycle
    chromadb_retries = state["retries"].get("chromadb", 0)
    if chromadb_retries < MAX_RETRIES_PER_DAY:
        try:
            chromadb_result = check_chromadb_health(dry_run=dry_run)
            results.append(chromadb_result)
            if not dry_run and not chromadb_result.get("success"):
                state["retries"]["chromadb"] = chromadb_retries + 1
        except Exception as ex:
            _log(f"ChromaDB health check error: {ex}")
    else:
        _log("SKIP: chromadb health check — max retries reached today")

    for failure in failures:
        job_name = failure["job"]
        failure_type = failure["type"]

        # Check retry budget
        retries = state["retries"].get(job_name, 0)
        if retries >= MAX_RETRIES_PER_DAY and not dry_run:
            result = {
                "job": job_name,
                "type": failure_type,
                "action": "skip_max_retries",
                "detail": f"Already retried {retries}x today (max={MAX_RETRIES_PER_DAY})",
                "success": False,
            }
            results.append(result)
            _log(f"SKIP: {job_name} — max retries ({MAX_RETRIES_PER_DAY}) reached today")
            continue

        # Apply backoff delay
        if retries > 0 and not dry_run:
            backoff = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** (retries - 1))
            _log(f"BACKOFF: Waiting {backoff}s before retry #{retries+1} of {job_name}")
            time.sleep(min(backoff, 300))  # Cap at 5 minutes

        # Dispatch to handler
        handler = RECOVERY_HANDLERS.get(failure_type, recover_unknown)
        try:
            result = handler(failure, dry_run=dry_run)
        except Exception as ex:
            _log(f"ERROR: Recovery handler for {job_name} raised: {ex}")
            result = {"job": job_name, "action": "handler_error", "success": False,
                      "error": str(ex)}
        result["type"] = failure_type
        result["detail"] = failure["detail"]
        results.append(result)

        # Update state
        if not dry_run:
            state["retries"][job_name] = retries + 1
            state["recoveries"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job": job_name,
                "type": failure_type,
                "success": result.get("success", False),
                "action": result.get("action", "unknown"),
            })
            _save_state(state)

    return results


def status() -> dict:
    """Show recovery history for today."""
    state = _load_state()
    return {
        "date": state["date"],
        "retries_today": state["retries"],
        "recoveries_today": len(state.get("recoveries", [])),
        "successful": sum(1 for r in state.get("recoveries", []) if r.get("success")),
        "failed": sum(1 for r in state.get("recoveries", []) if not r.get("success")),
        "details": state.get("recoveries", [])[-10:],  # Last 10
    }


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cron Doctor — Auto-recovery for Clarvis cron jobs")
        print()
        print("Usage:")
        print("  diagnose            — Classify failures for all missed jobs")
        print("  recover             — Diagnose + attempt auto-fix")
        print("  recover --dry-run   — Show what would be fixed (no action)")
        print("  status              — Show recovery history for today")
        print("  test                — Run self-test")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "diagnose":
        failures = diagnose()
        if not failures:
            print("All cron jobs healthy — no failures detected.")
        else:
            print(f"Found {len(failures)} failed job(s):\n")
            for f in failures:
                print(f"  [{f['type']:12s}] {f['job']:20s} — {f['detail']}")

    elif cmd == "recover":
        dry_run = "--dry-run" in sys.argv
        results = recover(dry_run=dry_run)
        if not results:
            print("All cron jobs healthy — nothing to recover.")
        else:
            print(f"Recovery {'simulation' if dry_run else 'attempt'} for {len(results)} job(s):\n")
            for r in results:
                status_str = "would_do" if dry_run else ("OK" if r.get("success") else "FAILED")
                detail = r.get("would_do", r.get("detail", ""))
                print(f"  [{status_str:7s}] {r['job']:20s} ({r['type']}) — {r.get('action', '')} — {detail}")

    elif cmd == "status":
        s = status()
        print(f"Cron Doctor Status ({s['date']}):")
        print(f"  Recoveries today: {s['recoveries_today']} ({s['successful']} OK, {s['failed']} failed)")
        print(f"  Retry counts: {json.dumps(s['retries_today'])}")
        if s["details"]:
            print("  Recent:")
            for d in s["details"]:
                ok = "OK" if d["success"] else "FAIL"
                print(f"    [{ok}] {d['timestamp'][:19]} {d['job']} ({d['type']}) via {d['action']}")

    elif cmd == "test":
        print("=== Cron Doctor Self-Test ===\n")

        # Test 1: Diagnose (should detect missed jobs based on log freshness)
        failures = diagnose()
        print(f"1. Diagnose: found {len(failures)} failure(s)")
        for f in failures:
            print(f"   [{f['type']}] {f['job']}: {f['detail'][:80]}")

        # Test 2: Dry-run recovery
        results = recover(dry_run=True)
        print(f"\n2. Dry-run recovery: {len(results)} action(s)")
        for r in results:
            print(f"   {r['job']}: {r.get('action', '?')} — {r.get('would_do', r.get('detail', ''))[:80]}")

        # Test 3: Status check
        s = status()
        print(f"\n3. Status: {s['recoveries_today']} recoveries today")

        # Test 4: Classification unit tests
        print("\n4. Classification unit tests:")
        # Simulate stale lock
        test_lock = Path("/tmp/clarvis_doctor_test.lock")
        test_lock.write_text("99999999")  # Fake dead PID
        test_config = {
            "script": "scripts/cron/cron_autonomous.sh",
            "log": "memory/cron/autonomous.log",
            "lock": str(test_lock),
            "max_age_hours": 0,  # Force stale
            "timeout": 10,
        }
        result = classify_failure("test_job", test_config)
        expected = FailureType.STALE_LOCK
        actual = result["type"] if result else "none"
        print(f"   Stale lock detection: {'PASS' if actual == expected else 'FAIL'} (expected={expected}, got={actual})")
        test_lock.unlink(missing_ok=True)

        print("\n=== Self-test complete ===")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

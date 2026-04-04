"""
Heartbeat Gate — Zero-LLM pre-check logic (canonical spine module).

Decides if the agent should wake up based on file/directory changes,
force-wake conditions, and consecutive skip tracking.

Exit semantics: WAKE (something changed) or SKIP (nothing changed).

Usage:
    from clarvis.heartbeat.gate import check_gate, run_gate, load_state, save_state
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# === CONFIGURATION ===

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
)
DATA_DIR = os.path.join(WORKSPACE, "data")
STATE_FILE = os.path.join(DATA_DIR, "heartbeat_gate_state.json")

WATCHED_FILES = [
    os.path.join(WORKSPACE, "memory/cron/digest.md"),
    os.path.join(WORKSPACE, "memory/evolution/QUEUE.md"),
]

WATCHED_DIRS = [
    os.path.join(WORKSPACE, "memory/cron"),
    "~/.openclaw/delivery-queue",
]

MAX_CONSECUTIVE_SKIPS = 4
FORCE_WAKE_AFTER_MIDNIGHT = True

PERF_METRICS_FILE = os.path.join(DATA_DIR, "performance_metrics.json")
CONTEXT_RELEVANCE_THRESHOLD = 0.60  # Below this, auto-prioritize context improvement


def _file_fingerprint(path: str) -> Optional[Dict]:
    """File fingerprint: mtime + size + head hash."""
    try:
        stat = os.stat(path)
        with open(path, "rb") as f:
            head = f.read(256)
        head_hash = hashlib.md5(head).hexdigest()[:12]
        return {"mtime": stat.st_mtime, "size": stat.st_size, "head_hash": head_hash}
    except (FileNotFoundError, PermissionError):
        return None


def _dir_fingerprint(dirpath: str) -> Optional[Dict]:
    """Directory fingerprint: latest mtime + file count."""
    try:
        if not os.path.isdir(dirpath):
            return None
        latest_mtime = 0.0
        file_count = 0
        for entry in os.scandir(dirpath):
            if entry.is_file():
                file_count += 1
                mtime = entry.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
        return {"latest_mtime": latest_mtime, "file_count": file_count}
    except (PermissionError, OSError):
        return None


def _today_memory_file() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(WORKSPACE, f"memory/{today}.md")


def _cron_runs_fingerprint() -> Optional[Dict]:
    return _dir_fingerprint("~/.openclaw/cron/runs")


def get_context_relevance() -> Optional[float]:
    """Read cached context_relevance from performance_metrics.json (zero-LLM)."""
    try:
        with open(PERF_METRICS_FILE) as f:
            data = json.load(f)
        return data.get("metrics", {}).get("context_relevance")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def load_state() -> Dict:
    """Load previous gate state."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError, ValueError):
        return {}


def save_state(state: Dict):
    """Save gate state atomically."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _check_force_wake(state, now, now_utc):
    """Check force-wake conditions. Returns (decision, reason, changes) or None."""
    if not state:
        return "wake", "First run — no previous state", ["first_run"]

    last_check = state.get("last_check_time", 0)
    if now - last_check > 4 * 3600:
        return "wake", f"Gap since last check: {(now - last_check) / 3600:.1f}h", ["long_gap"]

    if FORCE_WAKE_AFTER_MIDNIGHT:
        last_day = state.get("last_check_day", "")
        today = now_utc.strftime("%Y-%m-%d")
        if last_day and last_day != today:
            return "wake", f"New day: {today} (was {last_day})", ["midnight_rollover"]

    consecutive_skips = state.get("consecutive_skips", 0)
    if consecutive_skips >= MAX_CONSECUTIVE_SKIPS:
        return "wake", f"Max consecutive skips reached ({consecutive_skips})", ["max_skips"]

    return None


def _detect_file_changes(prev_files, prev_dirs):
    """Detect changes in watched files, directories, today's memory, and cron runs."""
    changes: List[str] = []

    for filepath in WATCHED_FILES:
        current = _file_fingerprint(filepath)
        previous = prev_files.get(filepath)
        if current is None and previous is not None:
            changes.append(f"deleted:{os.path.basename(filepath)}")
        elif current is not None and previous is None:
            changes.append(f"new:{os.path.basename(filepath)}")
        elif current and previous:
            if (current["mtime"] != previous["mtime"] or
                current["size"] != previous["size"] or
                current["head_hash"] != previous["head_hash"]):
                changes.append(f"modified:{os.path.basename(filepath)}")

    for dirpath in WATCHED_DIRS:
        current = _dir_fingerprint(dirpath)
        previous = prev_dirs.get(dirpath)
        if current and previous:
            if (current["latest_mtime"] != previous["latest_mtime"] or
                current["file_count"] != previous["file_count"]):
                changes.append(f"dir_changed:{os.path.basename(dirpath)}")
        elif current and not previous:
            changes.append(f"dir_new:{os.path.basename(dirpath)}")

    today_mem = _today_memory_file()
    current_mem = _file_fingerprint(today_mem)
    prev_mem = prev_files.get("today_memory")
    if current_mem and prev_mem:
        if (current_mem["mtime"] != prev_mem["mtime"] or
            current_mem["size"] != prev_mem["size"]):
            changes.append("modified:today_memory")
    elif current_mem and not prev_mem:
        changes.append("new:today_memory")

    cron_fp = _cron_runs_fingerprint()
    prev_cron = prev_dirs.get("cron_runs")
    if cron_fp and prev_cron:
        if cron_fp["latest_mtime"] != prev_cron["latest_mtime"]:
            changes.append("cron_completed")

    return changes


def check_gate() -> Tuple[str, str, List[str]]:
    """Run all gate checks.

    Returns:
        (decision, reason, changes)
        decision: "wake" or "skip"
    """
    # Mode gating: passive mode blocks autonomous execution
    try:
        from clarvis.runtime.mode import mode_policies
        policies = mode_policies()
        if not policies.get("allow_autonomous_execution", True):
            return "skip", f"Mode '{policies['mode']}' blocks autonomous execution", ["mode_passive"]
    except ImportError:
        pass  # Mode system not installed — allow all

    state = load_state()
    now = time.time()
    now_utc = datetime.now(timezone.utc)

    force = _check_force_wake(state, now, now_utc)
    if force:
        return force

    consecutive_skips = state.get("consecutive_skips", 0)
    changes = _detect_file_changes(
        state.get("file_fingerprints", {}),
        state.get("dir_fingerprints", {}),
    )

    if changes:
        return "wake", f"Changes detected: {', '.join(changes[:5])}", changes
    return "skip", f"No changes (skip #{consecutive_skips + 1}/{MAX_CONSECUTIVE_SKIPS})", changes


def run_gate(verbose: bool = False) -> Tuple[str, dict]:
    """Run gate check, update state, return (decision, output_dict).

    Returns:
        (decision, {"decision": ..., "reason": ..., "changes": [...]})
    """
    decision, reason, changes = check_gate()

    now = time.time()
    now_utc = datetime.now(timezone.utc)
    state = load_state()

    new_state = {
        "last_check_time": now,
        "last_check_day": now_utc.strftime("%Y-%m-%d"),
        "last_decision": decision,
        "last_reason": reason,
        "file_fingerprints": {},
        "dir_fingerprints": {},
        "consecutive_skips": (state.get("consecutive_skips", 0) + 1) if decision == "skip" else 0,
    }

    for filepath in WATCHED_FILES:
        fp = _file_fingerprint(filepath)
        if fp:
            new_state["file_fingerprints"][filepath] = fp

    for dirpath in WATCHED_DIRS:
        fp = _dir_fingerprint(dirpath)
        if fp:
            new_state["dir_fingerprints"][dirpath] = fp

    today_mem = _today_memory_file()
    mem_fp = _file_fingerprint(today_mem)
    if mem_fp:
        new_state["file_fingerprints"]["today_memory"] = mem_fp

    cron_fp = _cron_runs_fingerprint()
    if cron_fp:
        new_state["dir_fingerprints"]["cron_runs"] = cron_fp

    save_state(new_state)

    # Add context_relevance assessment (zero-LLM, reads cached metric)
    cr = get_context_relevance()
    priority_override = None
    if cr is not None and cr < CONTEXT_RELEVANCE_THRESHOLD:
        priority_override = "context_improvement"

    output = {
        "decision": decision,
        "reason": reason,
        "changes": changes,
        "context_relevance": cr,
        "priority_override": priority_override,
    }
    return decision, output

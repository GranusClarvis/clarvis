#!/usr/bin/env python3
"""
Heartbeat Gate — Zero-LLM pre-check that decides if M2.5 should wake.

Runs BEFORE the LLM agent wakes up. Checks if anything meaningful has
changed since the last heartbeat. If nothing changed, returns SKIP to
avoid burning tokens on an empty heartbeat.

Exit codes:
  0 = WAKE  (something changed, agent should run)
  1 = SKIP  (nothing changed, save tokens)

Output:
  JSON to stdout: {"decision": "wake"|"skip", "reason": "...", "changes": [...]}
  Human-readable reason to stderr for logging

Usage:
    python3 heartbeat_gate.py              # Normal check
    python3 heartbeat_gate.py --verbose    # Extra debug logging
    python3 heartbeat_gate.py --reset      # Clear state (forces wake on next run)
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# === CONFIGURATION ===

WORKSPACE = "/home/agent/.openclaw/workspace"
DATA_DIR = os.path.join(WORKSPACE, "data")
STATE_FILE = os.path.join(DATA_DIR, "heartbeat_gate_state.json")

# Files to monitor for changes
WATCHED_FILES = [
    os.path.join(WORKSPACE, "memory/cron/digest.md"),
    os.path.join(WORKSPACE, "memory/evolution/QUEUE.md"),
]

# Directories to check for new/modified files
WATCHED_DIRS = [
    os.path.join(WORKSPACE, "memory/cron"),           # Cron outputs
    "/home/agent/.openclaw/delivery-queue",             # Incoming messages
]

# Maximum consecutive skips before forcing a wake (prevents stale agent)
MAX_CONSECUTIVE_SKIPS = 4  # ~2 hours at 30min intervals

# Time-based force-wake conditions
FORCE_WAKE_AFTER_MIDNIGHT = True  # Always wake on first heartbeat of new day

VERBOSE = "--verbose" in sys.argv
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] GATE: {msg}", file=sys.stderr)
debug = lambda msg: VERBOSE and print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] GATE-DBG: {msg}", file=sys.stderr)


def _file_fingerprint(path: str) -> Optional[Dict]:
    """Get file fingerprint: mtime + size + first-line hash.

    The first-line hash catches cases where a file is recreated with the
    same mtime but different content (rare but possible with fast writes).
    """
    try:
        stat = os.stat(path)
        # Read first 256 bytes for a quick content hash
        with open(path, "rb") as f:
            head = f.read(256)
        head_hash = hashlib.md5(head).hexdigest()[:12]
        return {
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "head_hash": head_hash,
        }
    except FileNotFoundError:
        return None
    except PermissionError:
        return None


def _dir_fingerprint(dirpath: str) -> Optional[Dict]:
    """Get directory fingerprint: latest mtime of any file + file count.

    Detects new files, modified files, and deleted files.
    """
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
        return {
            "latest_mtime": latest_mtime,
            "file_count": file_count,
        }
    except (PermissionError, OSError):
        return None


def _today_memory_file() -> str:
    """Path to today's memory log file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(WORKSPACE, f"memory/{today}.md")


def _cron_runs_fingerprint() -> Optional[Dict]:
    """Check OpenClaw cron runs for recent completions."""
    cron_dir = "/home/agent/.openclaw/cron/runs"
    return _dir_fingerprint(cron_dir)


def load_state() -> Dict:
    """Load previous gate state. Returns empty dict on first run or corruption."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError, ValueError):
        log("State file corrupted — treating as first run")
        return {}


def save_state(state: Dict):
    """Save gate state atomically (write tmp + rename)."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def check_gate() -> Tuple[str, str, List[str]]:
    """Run all gate checks.

    Returns:
        (decision, reason, changes)
        decision: "wake" or "skip"
        reason: human-readable explanation
        changes: list of what changed
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
    changes = []
    now = time.time()
    now_utc = datetime.now(timezone.utc)

    # === FORCE WAKE CONDITIONS ===

    # 1. First run (no state)
    if not state:
        return "wake", "First run — no previous state", ["first_run"]

    # 2. State too old (something went wrong, gap > 4 hours)
    last_check = state.get("last_check_time", 0)
    if now - last_check > 4 * 3600:
        return "wake", f"Gap since last check: {(now - last_check) / 3600:.1f}h", ["long_gap"]

    # 3. Midnight rollover — first heartbeat of new day
    if FORCE_WAKE_AFTER_MIDNIGHT:
        last_day = state.get("last_check_day", "")
        today = now_utc.strftime("%Y-%m-%d")
        if last_day and last_day != today:
            return "wake", f"New day: {today} (was {last_day})", ["midnight_rollover"]

    # 4. Maximum consecutive skips reached
    consecutive_skips = state.get("consecutive_skips", 0)
    if consecutive_skips >= MAX_CONSECUTIVE_SKIPS:
        return "wake", f"Max consecutive skips reached ({consecutive_skips})", ["max_skips"]

    # === FILE CHANGE CHECKS ===

    prev_files = state.get("file_fingerprints", {})
    prev_dirs = state.get("dir_fingerprints", {})

    # 5. Check watched files
    for filepath in WATCHED_FILES:
        current = _file_fingerprint(filepath)
        previous = prev_files.get(filepath)

        if current is None and previous is not None:
            # File was deleted
            changes.append(f"deleted:{os.path.basename(filepath)}")
            debug(f"File deleted: {filepath}")
        elif current is not None and previous is None:
            # File is new (didn't exist before)
            changes.append(f"new:{os.path.basename(filepath)}")
            debug(f"New file: {filepath}")
        elif current and previous:
            # Compare fingerprints
            if (current["mtime"] != previous["mtime"] or
                current["size"] != previous["size"] or
                current["head_hash"] != previous["head_hash"]):
                changes.append(f"modified:{os.path.basename(filepath)}")
                debug(f"Modified: {filepath} (mtime:{previous['mtime']}->{current['mtime']}, "
                      f"size:{previous['size']}->{current['size']})")

    # 6. Check watched directories
    for dirpath in WATCHED_DIRS:
        current = _dir_fingerprint(dirpath)
        previous = prev_dirs.get(dirpath)

        if current and previous:
            if (current["latest_mtime"] != previous["latest_mtime"] or
                current["file_count"] != previous["file_count"]):
                dirname = os.path.basename(dirpath)
                changes.append(f"dir_changed:{dirname}")
                debug(f"Dir changed: {dirpath} (files:{previous['file_count']}->{current['file_count']})")
        elif current and not previous:
            changes.append(f"dir_new:{os.path.basename(dirpath)}")

    # 7. Check today's memory file (may not exist yet)
    today_mem = _today_memory_file()
    current_mem = _file_fingerprint(today_mem)
    prev_mem = prev_files.get("today_memory")
    if current_mem and prev_mem:
        if (current_mem["mtime"] != prev_mem["mtime"] or
            current_mem["size"] != prev_mem["size"]):
            changes.append("modified:today_memory")
    elif current_mem and not prev_mem:
        changes.append("new:today_memory")

    # 8. Check cron runs
    cron_fp = _cron_runs_fingerprint()
    prev_cron = prev_dirs.get("cron_runs")
    if cron_fp and prev_cron:
        if cron_fp["latest_mtime"] != prev_cron["latest_mtime"]:
            changes.append("cron_completed")
            debug("Cron run completed since last check")

    # === DECISION ===

    if changes:
        reason = f"Changes detected: {', '.join(changes[:5])}"
        decision = "wake"
    else:
        reason = f"No changes (skip #{consecutive_skips + 1}/{MAX_CONSECUTIVE_SKIPS})"
        decision = "skip"

    return decision, reason, changes


def run_gate() -> int:
    """Run the gate check, update state, return exit code."""
    decision, reason, changes = check_gate()

    # Build new state
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
    }

    # Update consecutive skip counter
    if decision == "skip":
        new_state["consecutive_skips"] = state.get("consecutive_skips", 0) + 1
    else:
        new_state["consecutive_skips"] = 0

    # Capture current fingerprints for next comparison
    for filepath in WATCHED_FILES:
        fp = _file_fingerprint(filepath)
        if fp:
            new_state["file_fingerprints"][filepath] = fp

    for dirpath in WATCHED_DIRS:
        fp = _dir_fingerprint(dirpath)
        if fp:
            new_state["dir_fingerprints"][dirpath] = fp

    # Today's memory file
    today_mem = _today_memory_file()
    mem_fp = _file_fingerprint(today_mem)
    if mem_fp:
        new_state["file_fingerprints"]["today_memory"] = mem_fp

    # Cron runs
    cron_fp = _cron_runs_fingerprint()
    if cron_fp:
        new_state["dir_fingerprints"]["cron_runs"] = cron_fp

    save_state(new_state)

    # Output
    log(f"{decision.upper()}: {reason}")
    output = {"decision": decision, "reason": reason, "changes": changes}
    print(json.dumps(output))

    return 0 if decision == "wake" else 1


def main():
    print("DEPRECATION: Use 'python3 -m clarvis heartbeat gate' instead of 'python3 scripts/heartbeat_gate.py'.", file=sys.stderr)

    if "--reset" in sys.argv:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("Gate state reset — next run will WAKE")
        else:
            print("No state file to reset")
        return

    # Delegate to spine module (canonical implementation)
    try:
        from clarvis.heartbeat.gate import run_gate as spine_run_gate
        decision, output = spine_run_gate(verbose=VERBOSE)
        log(f"{decision.upper()}: {output['reason']}")
        print(json.dumps(output))
        sys.exit(0 if decision == "wake" else 1)
    except ImportError:
        # Fallback to local implementation if spine not available
        exit_code = run_gate()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()

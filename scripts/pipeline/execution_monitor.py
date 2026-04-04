#!/usr/bin/env python3
"""Execution Monitor — Mid-execution progress monitoring for heartbeat pipeline.

Implements Cognitive Pattern 9: Commitment & Reconsideration (Wray et al. 2505.07087).
Monitors a spawned Claude Code task during execution. Uses process-level heuristics
(CPU activity, child processes, /proc state) as PRIMARY stall detection, since Claude
Code buffers all stdout — visible output is unreliable as a liveness signal.

Progress checkpoint detection: Scans output for progress markers when output IS visible,
but absence of output is NOT treated as a stall signal on its own.

Usage:
    python3 execution_monitor.py <output_file> <timeout_secs> <target_pid>

Writes verdict to <output_file>.reconsider.json when triggered.
Writes progress to <output_file>.progress.json on completion.
Appends to data/reconsider_log.jsonl for historical tracking.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

POLL_INTERVAL = 15  # seconds between checks
RECONSIDER_FRACTION = 0.60  # flag reconsideration at 60% (was 50% — too early for buffered output)
ABORT_FRACTION = 0.92  # graceful abort at 92% of timeout
MIN_OUTPUT_BYTES = 50  # below this = "no meaningful output"
# Number of consecutive idle polls (no CPU, no children) before declaring stall
IDLE_POLLS_FOR_STALL = 3  # 3 × 15s = 45s of confirmed process inactivity

LOG_FILE = Path("/home/agent/.openclaw/workspace/data/reconsider_log.jsonl")

# Progress marker patterns (things Claude Code outputs that indicate forward progress)
CHECKPOINT_PATTERNS = [
    re.compile(r"^\s*\d+\.\s+\[completed\]", re.MULTILINE),      # TodoWrite completions
    re.compile(r"^RESULT:\s+\w+", re.MULTILINE),                  # Final result line
    re.compile(r"mark(?:ed)?\s+.*\[x\]", re.MULTILINE | re.IGNORECASE),  # Queue task completion
    re.compile(r"^\s*\d+\s+passed", re.MULTILINE),                # pytest results
    re.compile(r"tests?\s+pass", re.MULTILINE | re.IGNORECASE),   # test pass mentions
    re.compile(r"Edit\s+tool", re.MULTILINE),                     # File edits made
    re.compile(r"Write\s+tool", re.MULTILINE),                    # File writes made
]


def count_checkpoints(text: str) -> dict:
    """Count progress checkpoints in output text.

    Returns dict with checkpoint counts and a total score.
    Each checkpoint type contributes to a progress score (0.0-1.0).
    """
    counts = {}
    total = 0
    for pattern in CHECKPOINT_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            label = pattern.pattern[:30].strip()
            counts[label] = len(matches)
            total += len(matches)

    score = min(1.0, total / 5.0)

    return {
        "checkpoint_count": total,
        "checkpoint_details": counts,
        "progress_score": round(score, 2),
    }


def _get_process_tree(pid: int) -> list:
    """Get all PIDs in the process tree (parent + all descendants)."""
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True, text=True, timeout=5
        )
        children = [int(p) for p in result.stdout.strip().split() if p]
        # Recurse one level for grandchildren (Claude → node → subprocesses)
        grandchildren = []
        for child in children:
            try:
                r2 = subprocess.run(
                    ["pgrep", "-P", str(child)],
                    capture_output=True, text=True, timeout=5
                )
                grandchildren.extend(int(p) for p in r2.stdout.strip().split() if p)
            except Exception:
                pass
        return [pid] + children + grandchildren
    except Exception:
        return [pid]


def _get_cpu_ticks(pids: list) -> int:
    """Sum utime + stime from /proc/<pid>/stat for all pids."""
    total = 0
    for p in pids:
        try:
            with open(f"/proc/{p}/stat") as f:
                fields = f.read().split()
                total += int(fields[13]) + int(fields[14])
        except (OSError, IndexError, ValueError):
            pass
    return total


def _get_process_state(pid: int) -> str:
    """Get process state character from /proc/<pid>/stat. Returns '' on error."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().split()
            return fields[2]  # R=running, S=sleeping, D=disk, Z=zombie, T=stopped
    except (OSError, IndexError):
        return ""


def _count_live_children(pid: int) -> int:
    """Count non-zombie child processes."""
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True, text=True, timeout=5
        )
        children = [int(p) for p in result.stdout.strip().split() if p]
        live = 0
        for c in children:
            state = _get_process_state(c)
            if state and state != "Z":
                live += 1
        return live
    except Exception:
        return 0


def _process_is_active(pid: int) -> bool:
    """Check if the process tree is actively using CPU.

    Samples CPU ticks over a 2-second window across the full process tree.
    Also checks for live child processes (Claude Code spawns subprocesses).
    """
    pids = _get_process_tree(pid)

    # Check 1: Any live children = likely active (Claude spawns node, git, etc.)
    live_children = _count_live_children(pid)
    if live_children > 0:
        return True

    # Check 2: CPU tick delta over 2s window
    ticks_before = _get_cpu_ticks(pids)
    time.sleep(2)
    ticks_after = _get_cpu_ticks(pids)

    if ticks_after > ticks_before:
        return True

    # Check 3: Process state — D (disk wait) or R (running) = active
    state = _get_process_state(pid)
    if state in ("R", "D"):
        return True

    return False


def monitor(output_file: str, timeout_secs: int, target_pid: int):
    """Poll process liveness and output file, flag/abort truly stalled execution.

    PRIMARY stall detection: process-level heuristics (CPU ticks, child processes,
    /proc state). Output-based checkpoints are a secondary positive signal.
    Zero output is treated as NORMAL for Claude Code (buffered stdout).
    """
    flag_file = f"{output_file}.reconsider.json"
    progress_file = f"{output_file}.progress.json"
    start = time.time()
    flagged = False
    last_checkpoint_count = 0
    last_checkpoint_time = start
    checkpoint_timeline = []  # [(elapsed_s, count)]
    consecutive_idle_polls = 0  # count of polls where process tree shows no activity
    last_active_time = start  # last time process showed CPU/child activity

    while True:
        time.sleep(POLL_INTERVAL)

        elapsed = time.time() - start
        frac = elapsed / timeout_secs if timeout_secs > 0 else 1.0

        # Check if target still alive
        try:
            os.kill(target_pid, 0)
        except (OSError, ProcessLookupError):
            break  # process finished normally

        # === Process-level liveness (PRIMARY signal) ===
        process_active = _process_is_active(target_pid)
        if process_active:
            consecutive_idle_polls = 0
            last_active_time = time.time()
        else:
            consecutive_idle_polls += 1

        # === Output-based checkpoints (SECONDARY signal) ===
        try:
            size = os.path.getsize(output_file)
        except (OSError, FileNotFoundError):
            size = 0

        has_output = size >= MIN_OUTPUT_BYTES

        cp_data = {"checkpoint_count": 0, "progress_score": 0.0}
        if has_output:
            try:
                with open(output_file, "r", errors="replace") as f:
                    text = f.read()
                cp_data = count_checkpoints(text)
            except OSError:
                pass

        current_cp = cp_data["checkpoint_count"]
        if current_cp > last_checkpoint_count:
            checkpoint_timeline.append((round(elapsed), current_cp))
            last_checkpoint_count = current_cp
            last_checkpoint_time = time.time()
            consecutive_idle_polls = 0  # checkpoint = definite progress

        # === Stall determination ===
        # A process is stalled only if BOTH conditions are true:
        # 1. Process tree shows no CPU/child activity for multiple consecutive polls
        # 2. No new output checkpoints
        # Zero output alone is NOT a stall (Claude Code buffers everything).
        is_process_stalled = consecutive_idle_polls >= IDLE_POLLS_FOR_STALL
        time_since_activity = time.time() - last_active_time

        # Output appeared or process active after flag → clear reconsideration
        if flagged and (process_active or has_output):
            try:
                os.remove(flag_file)
            except OSError:
                pass
            flagged = False

        # 60% threshold: flag reconsideration ONLY if process is truly stalled
        if (frac >= RECONSIDER_FRACTION and is_process_stalled
                and not flagged and not process_active):
            flagged = True
            verdict = {
                "reconsider": True,
                "aborted": False,
                "reason": (f"Process idle for {consecutive_idle_polls} polls "
                           f"({time_since_activity:.0f}s) at {frac:.0%} of timeout"),
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
                "checkpoints": current_cp,
                "idle_polls": consecutive_idle_polls,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_flag(flag_file, verdict)

        # 92% threshold: graceful abort ONLY if process is truly stalled
        if frac >= ABORT_FRACTION and is_process_stalled and not process_active:
            verdict = {
                "reconsider": True,
                "aborted": True,
                "reason": (f"Process idle for {consecutive_idle_polls} polls "
                           f"({time_since_activity:.0f}s) at {frac:.0%} of timeout — aborting"),
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
                "checkpoints": current_cp,
                "idle_polls": consecutive_idle_polls,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_flag(flag_file, verdict)
            _log_event(verdict)
            try:
                os.kill(target_pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            break

        if frac >= 1.0:
            break

    # Write progress summary for postflight consumption
    final_elapsed = time.time() - start
    final_cp = {"checkpoint_count": 0, "progress_score": 0.0, "checkpoint_details": {}}
    try:
        with open(output_file, "r", errors="replace") as f:
            final_cp = count_checkpoints(f.read())
    except OSError:
        pass

    progress_summary = {
        "elapsed_s": round(final_elapsed),
        "timeout_s": timeout_secs,
        "checkpoints": final_cp["checkpoint_count"],
        "progress_score": final_cp["progress_score"],
        "checkpoint_details": final_cp["checkpoint_details"],
        "checkpoint_timeline": checkpoint_timeline,
        "was_flagged": flagged,
        "idle_polls_at_end": consecutive_idle_polls,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _write_flag(progress_file, progress_summary)


def _write_flag(path: str, data: dict):
    """Write reconsideration flag file."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _log_event(data: dict):
    """Append to historical reconsideration log."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <output_file> <timeout_secs> <target_pid>", file=sys.stderr)
        sys.exit(1)

    monitor(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))

#!/usr/bin/env python3
"""Execution Monitor — Mid-execution progress monitoring for heartbeat pipeline.

Implements Cognitive Pattern 9: Commitment & Reconsideration (Wray et al. 2505.07087).
Monitors a spawned Claude Code task's output file during execution. Surfaces a
reconsideration flag when progress stalls and optionally triggers graceful abort.

Progress checkpoint detection: Scans output for progress markers (TODO completions,
RESULT lines, task completions) to distinguish "productive but slow" from "stuck".
Writes a progress summary (.progress.json) for postflight quality scoring.

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
import sys
import time
from pathlib import Path

POLL_INTERVAL = 15  # seconds between checks
RECONSIDER_FRACTION = 0.50  # flag reconsideration at 50% of timeout
ABORT_FRACTION = 0.90  # graceful abort at 90% of timeout (was 0.75 — too aggressive,
                        # Claude Code buffers output causing false "no output" detection)
MIN_OUTPUT_BYTES = 50  # below this = "no meaningful output"

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
            # Use a short label from the pattern
            label = pattern.pattern[:30].strip()
            counts[label] = len(matches)
            total += len(matches)

    # Progress score: 0.0 (no checkpoints) to 1.0 (5+ checkpoints)
    score = min(1.0, total / 5.0)

    return {
        "checkpoint_count": total,
        "checkpoint_details": counts,
        "progress_score": round(score, 2),
    }


def monitor(output_file: str, timeout_secs: int, target_pid: int):
    """Poll output file and flag/abort stalled execution.

    Tracks progress checkpoints in the output to distinguish productive work
    from stalls. Writes a progress summary on completion.
    """
    flag_file = f"{output_file}.reconsider.json"
    progress_file = f"{output_file}.progress.json"
    start = time.time()
    flagged = False
    last_checkpoint_count = 0
    last_checkpoint_time = start
    checkpoint_timeline = []  # [(elapsed_s, count)]

    while True:
        time.sleep(POLL_INTERVAL)

        elapsed = time.time() - start
        frac = elapsed / timeout_secs if timeout_secs > 0 else 1.0

        # Check if target still alive
        try:
            os.kill(target_pid, 0)
        except (OSError, ProcessLookupError):
            break  # process finished normally

        # Check output file size
        try:
            size = os.path.getsize(output_file)
        except (OSError, FileNotFoundError):
            size = 0

        has_output = size >= MIN_OUTPUT_BYTES

        # Check for progress checkpoints in output
        cp_data = {"checkpoint_count": 0, "progress_score": 0.0}
        if has_output:
            try:
                with open(output_file, "r", errors="replace") as f:
                    text = f.read()
                cp_data = count_checkpoints(text)
            except OSError:
                pass

        # Track checkpoint timeline (new checkpoints = real progress)
        current_cp = cp_data["checkpoint_count"]
        if current_cp > last_checkpoint_count:
            checkpoint_timeline.append((round(elapsed), current_cp))
            last_checkpoint_count = current_cp
            last_checkpoint_time = time.time()

        # Progress-aware stall detection: if we have checkpoints, the task
        # is making progress even if it's slow. Only flag stall if no new
        # checkpoints for a significant portion of the timeout.
        stall_duration = time.time() - last_checkpoint_time
        has_recent_progress = stall_duration < (timeout_secs * 0.4)

        # Output appeared after flag → clear reconsideration
        if flagged and (has_output or has_recent_progress):
            try:
                os.remove(flag_file)
            except OSError:
                pass
            flagged = False

        # 50% threshold: flag reconsideration (skip if making checkpoint progress)
        if frac >= RECONSIDER_FRACTION and not has_output and not flagged and not has_recent_progress:
            flagged = True
            verdict = {
                "reconsider": True,
                "aborted": False,
                "reason": f"No output after {elapsed:.0f}s ({frac:.0%} of {timeout_secs}s timeout)",
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
                "checkpoints": current_cp,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_flag(flag_file, verdict)

        # 90% threshold: graceful abort (only if process is truly idle AND no recent progress)
        if frac >= ABORT_FRACTION and not has_output and not has_recent_progress:
            # Check if process tree is actively using CPU before aborting
            if _process_is_active(target_pid):
                continue  # process is working, skip abort

            verdict = {
                "reconsider": True,
                "aborted": True,
                "reason": f"No output after {elapsed:.0f}s ({frac:.0%} of {timeout_secs}s timeout) — aborting",
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
                "checkpoints": current_cp,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_flag(flag_file, verdict)
            _log_event(verdict)
            # Graceful abort: SIGTERM to timeout process (forwards to Claude)
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


def _process_is_active(pid: int) -> bool:
    """Check if the process (or its children) are actively using CPU.

    Reads /proc/<pid>/stat to get cumulative CPU ticks, waits briefly,
    and checks if ticks increased. Returns True if CPU activity detected.
    """
    import subprocess

    try:
        # Get all PIDs in the process tree
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True, text=True, timeout=5
        )
        pids = [pid] + [int(p) for p in result.stdout.strip().split() if p]
    except Exception:
        pids = [pid]

    def get_cpu_ticks(pids):
        total = 0
        for p in pids:
            try:
                with open(f"/proc/{p}/stat") as f:
                    fields = f.read().split()
                    # fields 13,14 = utime, stime (in clock ticks)
                    total += int(fields[13]) + int(fields[14])
            except (OSError, IndexError, ValueError):
                pass
        return total

    ticks_before = get_cpu_ticks(pids)
    time.sleep(2)
    ticks_after = get_cpu_ticks(pids)

    return ticks_after > ticks_before


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

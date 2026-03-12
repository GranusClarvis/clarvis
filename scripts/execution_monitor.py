#!/usr/bin/env python3
"""Execution Monitor — Mid-execution progress monitoring for heartbeat pipeline.

Implements Cognitive Pattern 9: Commitment & Reconsideration (Wray et al. 2505.07087).
Monitors a spawned Claude Code task's output file during execution. Surfaces a
reconsideration flag when progress stalls and optionally triggers graceful abort.

Usage:
    python3 execution_monitor.py <output_file> <timeout_secs> <target_pid>

Writes verdict to <output_file>.reconsider.json when triggered.
Appends to data/reconsider_log.jsonl for historical tracking.
"""

import json
import os
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


def monitor(output_file: str, timeout_secs: int, target_pid: int):
    """Poll output file and flag/abort stalled execution."""
    flag_file = f"{output_file}.reconsider.json"
    start = time.time()
    flagged = False

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

        # Output appeared after flag → clear reconsideration
        if flagged and has_output:
            try:
                os.remove(flag_file)
            except OSError:
                pass
            flagged = False

        # 50% threshold: flag reconsideration
        if frac >= RECONSIDER_FRACTION and not has_output and not flagged:
            flagged = True
            verdict = {
                "reconsider": True,
                "aborted": False,
                "reason": f"No output after {elapsed:.0f}s ({frac:.0%} of {timeout_secs}s timeout)",
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_flag(flag_file, verdict)

        # 90% threshold: graceful abort (only if process is truly idle)
        if frac >= ABORT_FRACTION and not has_output:
            # Check if process tree is actively using CPU before aborting
            if _process_is_active(target_pid):
                continue  # process is working, skip abort

            verdict = {
                "reconsider": True,
                "aborted": True,
                "reason": f"No output after {elapsed:.0f}s ({frac:.0%} of {timeout_secs}s timeout) — aborting",
                "elapsed_secs": round(elapsed),
                "output_bytes": size,
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

#!/bin/bash
# =============================================================================
# respawn_deferred.sh — Drain the deferred-spawn ledger.
#
# Reads ledger entries written by spawn_claude.sh when it had to defer because
# the global Claude lock was held. For each pending entry:
#   - If the global lock is still held by a live clarvis process, skip.
#   - If free, atomically claim the entry, then re-invoke spawn_claude.sh
#     with the original task + flags.
#
# Triggered from:
#   - cron_watchdog.sh (every 30 min — safety net)
#   - spawn_claude.sh worker EXIT trap (immediately after a Claude run finishes)
#
# Race-safe: claim() in clarvis.agents.spawn_ledger renames the ledger file to
# `.processing-<pid>` so concurrent respawn passes can't double-fire the same
# task. On crash before consume, the file is restored on next pass.
# =============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$(cd -- "$SCRIPT_DIR/../.." && pwd)}"
export CLARVIS_WORKSPACE

source "$CLARVIS_WORKSPACE/scripts/cron/cron_env.sh"
source "$CLARVIS_WORKSPACE/scripts/cron/lock_helper.sh"

LOGFILE="$CLARVIS_WORKSPACE/memory/cron/respawn_deferred.log"
mkdir -p "$(dirname "$LOGFILE")"
LEDGER_DIR="$CLARVIS_WORKSPACE/data/deferred_spawns"

_log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] $*" >> "$LOGFILE"
}

# Single-flight guard so two respawn invocations can't fight each other.
RESPAWN_LOCK="/tmp/clarvis_respawn_deferred.lock"
exec 9>"$RESPAWN_LOCK"
if ! flock -n 9; then
    _log "another respawn pass is running — skip"
    exit 0
fi

# Quick exit if no ledger directory.
if [ ! -d "$LEDGER_DIR" ]; then
    exit 0
fi

# Reap entries older than the expiry window, then count what's left.
python3 -c "from clarvis.agents.spawn_ledger import reap_expired, log
dropped = reap_expired()
if dropped:
    log(f'reaped {len(dropped)} expired ledger entries')" 2>/dev/null || true

PENDING_COUNT=$(find "$LEDGER_DIR" -maxdepth 1 -type f -name '*.json' \
    ! -name '*.processing-*' ! -name '*.dead' ! -name '*.expired' 2>/dev/null \
    | wc -l)
if [ "$PENDING_COUNT" -eq 0 ]; then
    exit 0
fi

# Is the global Claude lock currently held? Use the same liveness rules as
# spawn_claude itself so we don't incorrectly think the lock is free.
_lock_is_held() {
    [ -f "$GLOBAL_LOCK" ] || return 1
    local gpid gage
    gpid=$(_read_lock_pid "$GLOBAL_LOCK")
    gage=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
    if [ -n "$gpid" ] && _is_clarvis_process "$gpid" && [ "$gage" -le 2400 ]; then
        return 0
    fi
    # Stale — clean up so the next spawn doesn't fight a ghost.
    rm -f "$GLOBAL_LOCK"
    return 1
}

if _lock_is_held; then
    GPID=$(_read_lock_pid "$GLOBAL_LOCK")
    GAGE=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
    _log "lock still held (PID ${GPID:-?}, age=${GAGE}s) — leaving $PENDING_COUNT deferred entries for next pass"
    exit 0
fi

_log "lock free — draining $PENDING_COUNT deferred entries"

# Drain entries one at a time. After each successful invocation we exit so
# the spawned worker can claim the lock; the next pass picks up the rest.
python3 - "$$" <<'PY' >> "$LOGFILE" 2>&1
import json
import os
import shlex
import subprocess
import sys

from clarvis.agents.spawn_ledger import (
    iter_to_respawn,
    claim,
    release,
    log as _ledger_log,
)

claimer_pid = int(sys.argv[1])
workspace = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
spawn_script = os.path.join(workspace, "scripts", "agents", "spawn_claude.sh")
processed = 0

for entry in iter_to_respawn():
    claimed = claim(entry, claimer_pid)
    if claimed is None:
        continue  # Another respawn pass got there first.

    cmd = [spawn_script, entry.task, str(entry.timeout)]
    if not entry.send_tg:
        cmd.append("--no-tg")
    if entry.isolated:
        cmd.append("--isolated")
    if entry.tg_topic:
        cmd.append(f"--topic={entry.tg_topic}")
    if entry.tg_chat_id:
        cmd.append(f"--chat={entry.tg_chat_id}")
    if entry.category:
        cmd.append(f"--category={entry.category}")
    if entry.retry_max:
        cmd.append(f"--retry={entry.retry_max}")
    for flag in entry.extra_flags or []:
        cmd.append(flag)

    _ledger_log(
        f"respawn id={entry.id} attempts={entry.attempts} "
        f"task_head={entry.task[:80]!r}"
    )
    try:
        # Detach: spawn_claude.sh forks a worker and exits. We DO NOT block on
        # the worker — the new spawn now owns the global lock and will run on
        # its own. We just need to know whether the parent invocation succeeded
        # (i.e., it didn't immediately defer again).
        result = subprocess.run(
            cmd,
            cwd=workspace,
            timeout=120,  # parent should return well under this
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _ledger_log(f"respawn OK id={entry.id} stdout_head={result.stdout[:120]!r}")
            release(claimed, entry, success=True)
            processed += 1
            # Exit the loop — give the new worker a clean run before draining more.
            break
        elif result.returncode == 75:  # EX_TEMPFAIL — deferred again
            _ledger_log(
                f"respawn DEFERRED_AGAIN id={entry.id} stdout_head={result.stdout[:120]!r}"
            )
            # The new spawn wrote a fresh ledger entry; consume the old one so
            # we don't loop on the same outdated text.
            release(claimed, entry, success=True)
            break
        else:
            _ledger_log(
                f"respawn FAIL id={entry.id} rc={result.returncode} "
                f"stderr={result.stderr[:200]!r}"
            )
            release(claimed, entry, success=False)
            # Continue to the next pending entry — this one had a hard failure.
            continue
    except subprocess.TimeoutExpired:
        _ledger_log(f"respawn TIMEOUT id={entry.id} (parent did not return in 120s)")
        release(claimed, entry, success=False)
        break
    except Exception as e:
        _ledger_log(f"respawn EXCEPTION id={entry.id} err={e!r}")
        release(claimed, entry, success=False)
        continue

if processed == 0:
    _ledger_log("respawn pass found pending entries but processed none (all claimed/locked)")
PY

exit 0

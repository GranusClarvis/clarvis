#!/bin/bash
# =============================================================================
# lock_helper.sh — Unified lock management for Clarvis cron scripts
# =============================================================================
# Source this file from any cron script to get standardized lock functions.
# Replaces duplicated lock logic across all cron_*.sh scripts.
#
# Three lock tiers:
#   1. Local job lock  — prevents overlapping runs of the same job
#   2. Global Claude lock — mutual exclusion for all Claude Code spawners
#   3. Maintenance lock — mutual exclusion for DB maintenance operations
#
# Usage:
#   source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
#
#   # Local lock (required for all scripts)
#   acquire_local_lock "/tmp/clarvis_autonomous.lock" "$LOGFILE" 2400
#
#   # Global Claude lock (for scripts that spawn Claude Code)
#   acquire_global_claude_lock "$LOGFILE"
#   # Optional: pass "queue" as 2nd arg to queue a deferred task on conflict
#   acquire_global_claude_lock "$LOGFILE" "queue"
#
#   # Maintenance lock (for DB maintenance scripts)
#   acquire_maintenance_lock "$LOGFILE"
# =============================================================================

# Global Claude lock path
GLOBAL_LOCK="/tmp/clarvis_claude_global.lock"
# Maintenance lock path
MAINTENANCE_LOCK="/tmp/clarvis_maintenance.lock"

# Internal: list of lock files to clean on EXIT
_LOCK_HELPER_FILES=()

_lock_helper_cleanup() {
    for f in "${_LOCK_HELPER_FILES[@]}"; do
        rm -f "$f"
    done
}

# Register the cleanup trap (additive — won't clobber existing traps)
trap _lock_helper_cleanup EXIT

_register_lock() {
    _LOCK_HELPER_FILES+=("$1")
    # Re-register trap with all accumulated locks
    trap _lock_helper_cleanup EXIT
}

# =============================================================================
# acquire_local_lock <lockfile> <logfile> [stale_threshold_seconds]
#
# Acquires a local job lock. Exits the script (exit 0) if the lock is held
# by an active process within the stale threshold.
#
# Args:
#   $1 — Lock file path (e.g. /tmp/clarvis_autonomous.lock)
#   $2 — Log file path for messages
#   $3 — Stale threshold in seconds (default: 0 = no stale detection)
#         If >0, locks older than this are reclaimed even if PID is alive.
# =============================================================================
acquire_local_lock() {
    local lockfile="$1"
    local logfile="$2"
    local stale_threshold="${3:-0}"

    if [ -f "$lockfile" ]; then
        local pid
        pid=$(cat "$lockfile" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            if [ "$stale_threshold" -gt 0 ] 2>/dev/null; then
                local lock_age
                lock_age=$(( $(date +%s) - $(stat -c %Y "$lockfile" 2>/dev/null || echo 0) ))
                if [ "$lock_age" -gt "$stale_threshold" ]; then
                    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Stale lock (age=${lock_age}s, PID $pid) — reclaiming" >> "$logfile"
                else
                    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid, age=${lock_age}s)" >> "$logfile"
                    exit 0
                fi
            else
                echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)" >> "$logfile"
                exit 0
            fi
        fi
    fi
    echo $$ > "$lockfile"
    _register_lock "$lockfile"
}

# =============================================================================
# acquire_global_claude_lock <logfile> [on_conflict]
#
# Acquires the global Claude Code lock (/tmp/clarvis_claude_global.lock).
# Exits the script (exit 0) if another Claude session is active.
#
# Args:
#   $1 — Log file path
#   $2 — Conflict action: "queue" to queue a deferred P0 task, or empty to just exit.
#         The queue action calls queue_writer.py with the script name.
# =============================================================================
acquire_global_claude_lock() {
    local logfile="$1"
    local on_conflict="${2:-}"

    if [ -f "$GLOBAL_LOCK" ]; then
        local gpid glock_age
        gpid=$(cat "$GLOBAL_LOCK" 2>/dev/null)
        glock_age=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
        if [ -n "$gpid" ] && kill -0 "$gpid" 2>/dev/null && [ "$glock_age" -le 2400 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] GLOBAL LOCK: Claude already running (PID $gpid, age=${glock_age}s) — deferring" >> "$logfile"
            if [ "$on_conflict" = "queue" ]; then
                local scripts_dir
                scripts_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
                local caller_name
                caller_name="$(basename "$0" .sh)"
                python3 "$scripts_dir/queue_writer.py" add \
                    "Deferred ${caller_name} (global lock conflict at $(date -u +%H:%M))" \
                    --priority P0 --source cron_overlap_guard 2>> "$logfile" || true
            fi
            exit 0
        else
            [ -n "$gpid" ] && echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] GLOBAL LOCK: Stale (age=${glock_age}s, PID $gpid) — reclaiming" >> "$logfile"
            rm -f "$GLOBAL_LOCK"
        fi
    fi
    echo $$ > "$GLOBAL_LOCK"
    _register_lock "$GLOBAL_LOCK"
}

# =============================================================================
# acquire_maintenance_lock <logfile> [stale_threshold_seconds]
#
# Acquires the maintenance lock (/tmp/clarvis_maintenance.lock).
# Exits the script (exit 0) if another maintenance operation is active.
#
# Args:
#   $1 — Log file path
#   $2 — Stale threshold in seconds (default: 600)
# =============================================================================
acquire_maintenance_lock() {
    local logfile="$1"
    local stale_threshold="${2:-600}"

    if [ -f "$MAINTENANCE_LOCK" ]; then
        local mpid mlock_age
        mpid=$(cat "$MAINTENANCE_LOCK" 2>/dev/null)
        mlock_age=$(( $(date +%s) - $(stat -c %Y "$MAINTENANCE_LOCK" 2>/dev/null || echo 0) ))
        if [ -n "$mpid" ] && kill -0 "$mpid" 2>/dev/null && [ "$mlock_age" -le "$stale_threshold" ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Maintenance lock held (PID $mpid, age=${mlock_age}s)" >> "$logfile"
            exit 0
        else
            [ -n "$mpid" ] && echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] MAINTENANCE LOCK: Stale (age=${mlock_age}s) — reclaiming" >> "$logfile"
            rm -f "$MAINTENANCE_LOCK"
        fi
    fi
    echo $$ > "$MAINTENANCE_LOCK"
    _register_lock "$MAINTENANCE_LOCK"
}

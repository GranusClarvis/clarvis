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
#   source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
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
# Lock audit journal
LOCK_AUDIT_LOG="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/monitoring/lock_audit.log"

# Internal: list of lock files to clean on EXIT
_LOCK_HELPER_FILES=()

# Internal: PID of the background timeout watchdog (if any)
_SCRIPT_TIMEOUT_PID=""

# =============================================================================
# _audit_lock <lock_name> <action> [detail]
#
# Appends a line to the centralized lock audit journal.
# Format: TIMESTAMP PID LOCK_NAME ACTION [DETAIL]
# =============================================================================
_audit_lock() {
    local lock_name="$1"
    local action="$2"
    local detail="${3:-}"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%S)"
    local line="$ts $$ $lock_name $action"
    [ -n "$detail" ] && line="$line $detail"
    echo "$line" >> "$LOCK_AUDIT_LOG" 2>/dev/null || true
}

_lock_helper_cleanup() {
    # Kill timeout watchdog if running
    if [ -n "$_SCRIPT_TIMEOUT_PID" ] && kill -0 "$_SCRIPT_TIMEOUT_PID" 2>/dev/null; then
        kill "$_SCRIPT_TIMEOUT_PID" 2>/dev/null
        wait "$_SCRIPT_TIMEOUT_PID" 2>/dev/null || true
    fi
    for f in "${_LOCK_HELPER_FILES[@]}"; do
        _audit_lock "$(basename "$f")" "RELEASE"
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

# Write PID + ISO timestamp to lock file for forensic debugging.
# Format: "PID TIMESTAMP" (e.g., "12345 2026-03-28T15:30:00")
# Backward-compatible: readers that expect only a PID will get PID via
# first field, and old single-PID lock files still parse correctly.
_write_lock() {
    local lockfile="$1"
    echo "$$ $(date -u +%Y-%m-%dT%H:%M:%S)" > "$lockfile"
}

# Read PID from lock file, handling both "PID" and "PID TIMESTAMP" formats.
_read_lock_pid() {
    local lockfile="$1"
    local content
    content=$(cat "$lockfile" 2>/dev/null) || { echo ""; return; }
    # First field is always PID
    echo "${content%% *}"
}

# =============================================================================
# set_script_timeout <seconds> <logfile>
#
# Arms a background watchdog that sends SIGTERM to the calling script after
# <seconds> seconds.  Because the EXIT trap calls _lock_helper_cleanup, all
# acquired locks are released even on timeout.
#
# Call once, early in the script, after sourcing lock_helper.sh.
# =============================================================================
set_script_timeout() {
    local seconds="$1"
    local logfile="$2"
    local parent=$$

    ( # Subshell watchdog — sleeps then kills parent
        sleep "$seconds"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] TIMEOUT: Script exceeded ${seconds}s limit — sending SIGTERM to PID $parent" >> "$logfile"
        kill -TERM "$parent" 2>/dev/null
        # Give 5s for graceful shutdown, then force-kill
        sleep 5
        kill -9 "$parent" 2>/dev/null
    ) &
    _SCRIPT_TIMEOUT_PID=$!
}

# =============================================================================
# _is_clarvis_process <pid>
#
# Returns 0 if the PID belongs to a clarvis/claude process, 1 otherwise.
# Reads /proc/<pid>/cmdline to verify the process identity, preventing
# false lock honors from PID recycling.
# =============================================================================
_is_clarvis_process() {
    local pid="$1"
    [ -z "$pid" ] && return 1

    # First: is the process alive at all?
    kill -0 "$pid" 2>/dev/null || return 1

    # Second: verify via /proc/<pid>/cmdline that it's actually ours
    local cmdline_file="/proc/$pid/cmdline"
    if [ -f "$cmdline_file" ]; then
        # cmdline is NUL-delimited; convert to spaces for matching
        local cmdline
        cmdline=$(tr '\0' ' ' < "$cmdline_file" 2>/dev/null) || return 1
        # Match known clarvis/claude process signatures
        if echo "$cmdline" | grep -qE 'clarvis|claude|cron_(autonomous|morning|evening|evolution|reflection|research|implementation|strategic|cleanup|orchestrator|report|graph|chromadb)'; then
            return 0
        fi
        # PID alive but not a clarvis process — PID was recycled
        return 1
    fi

    # /proc not available (non-Linux) — fall back to kill -0 result (already passed)
    return 0
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
        pid=$(_read_lock_pid "$lockfile")
        if [ -n "$pid" ] && _is_clarvis_process "$pid"; then
            if [ "$stale_threshold" -gt 0 ] 2>/dev/null; then
                local lock_age
                lock_age=$(( $(date +%s) - $(stat -c %Y "$lockfile" 2>/dev/null || echo 0) ))
                if [ "$lock_age" -gt "$stale_threshold" ]; then
                    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Stale lock (age=${lock_age}s, PID $pid) — reclaiming" >> "$logfile"
                    _audit_lock "$(basename "$lockfile")" "RECLAIM" "stale_age=${lock_age}s prev_pid=$pid"
                else
                    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid, age=${lock_age}s)" >> "$logfile"
                    _audit_lock "$(basename "$lockfile")" "SKIP" "held_by=$pid age=${lock_age}s"
                    exit 0
                fi
            else
                echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)" >> "$logfile"
                _audit_lock "$(basename "$lockfile")" "SKIP" "held_by=$pid"
                exit 0
            fi
        elif [ -n "$pid" ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Stale lock (PID $pid dead or recycled) — reclaiming" >> "$logfile"
            _audit_lock "$(basename "$lockfile")" "RECLAIM" "dead_pid=$pid"
        fi
    fi
    _write_lock "$lockfile"
    _register_lock "$lockfile"
    _audit_lock "$(basename "$lockfile")" "ACQUIRE"
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
        gpid=$(_read_lock_pid "$GLOBAL_LOCK")
        glock_age=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
        if [ -n "$gpid" ] && _is_clarvis_process "$gpid" && [ "$glock_age" -le 2400 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] GLOBAL LOCK: Claude already running (PID $gpid, age=${glock_age}s) — deferring" >> "$logfile"
            _audit_lock "clarvis_claude_global.lock" "SKIP" "held_by=$gpid age=${glock_age}s"
            if [ "$on_conflict" = "queue" ]; then
                local scripts_dir
                scripts_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]:-$0}")")" 2>/dev/null || scripts_dir="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron"
                local caller_name
                caller_name="$(basename "$0" .sh)"
                python3 -m clarvis queue add \
                    "Deferred ${caller_name} (global lock conflict at $(date -u +%H:%M))" \
                    --priority P0 --source cron_overlap_guard 2>> "$logfile" || true
            fi
            exit 0
        else
            if [ -n "$gpid" ]; then
                echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] GLOBAL LOCK: Stale (age=${glock_age}s, PID $gpid not clarvis) — reclaiming" >> "$logfile"
                _audit_lock "clarvis_claude_global.lock" "RECLAIM" "stale_age=${glock_age}s prev_pid=$gpid"
            fi
            rm -f "$GLOBAL_LOCK"
        fi
    fi
    _write_lock "$GLOBAL_LOCK"
    _register_lock "$GLOBAL_LOCK"
    _audit_lock "clarvis_claude_global.lock" "ACQUIRE"
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
        mpid=$(_read_lock_pid "$MAINTENANCE_LOCK")
        mlock_age=$(( $(date +%s) - $(stat -c %Y "$MAINTENANCE_LOCK" 2>/dev/null || echo 0) ))
        if [ -n "$mpid" ] && _is_clarvis_process "$mpid" && [ "$mlock_age" -le "$stale_threshold" ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Maintenance lock held (PID $mpid, age=${mlock_age}s)" >> "$logfile"
            _audit_lock "clarvis_maintenance.lock" "SKIP" "held_by=$mpid age=${mlock_age}s"
            exit 0
        else
            if [ -n "$mpid" ]; then
                echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] MAINTENANCE LOCK: Stale (age=${mlock_age}s, PID $mpid not clarvis) — reclaiming" >> "$logfile"
                _audit_lock "clarvis_maintenance.lock" "RECLAIM" "stale_age=${mlock_age}s prev_pid=$mpid"
            fi
            rm -f "$MAINTENANCE_LOCK"
        fi
    fi
    _write_lock "$MAINTENANCE_LOCK"
    _register_lock "$MAINTENANCE_LOCK"
    _audit_lock "clarvis_maintenance.lock" "ACQUIRE"
}

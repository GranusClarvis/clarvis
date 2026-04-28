#!/bin/bash
# cron_worktree_cleanup.sh — Weekly cleanup of stale .claude/worktrees/
#
# Removes worktree directories older than AGE_DAYS (default 7) using
# `git worktree remove --force`, then runs `git worktree prune` to
# clean any orphan admin metadata.  No Claude Code spawning.
#
# The currently active worktree (the one containing this script's PWD)
# is always skipped as a safety guard.
#
# Usage:
#   cron_worktree_cleanup.sh             # apply
#   cron_worktree_cleanup.sh --dry-run   # report only

set -uo pipefail

# Capture PWD BEFORE sourcing cron_env.sh (which cd's to workspace), so we
# can detect if this script was invoked from inside a worktree and skip it.
INVOCATION_PWD="${PWD:-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOGFILE="$CLARVIS_WORKSPACE/memory/cron/worktree_cleanup.log"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
acquire_local_lock "/tmp/clarvis_worktree_cleanup.lock" "$LOGFILE" 1800

WORKTREE_DIR="$CLARVIS_WORKSPACE/.claude/worktrees"
AGE_DAYS="${WORKTREE_AGE_DAYS:-7}"

ts() { date -u +%Y-%m-%dT%H:%M:%S; }

echo "[$(ts)] === Weekly worktree cleanup started (dry_run=$DRY_RUN, age_days=$AGE_DAYS) ==="

cd "$CLARVIS_WORKSPACE" || { echo "[$(ts)] FATAL: cannot cd to workspace"; exit 1; }

if [ ! -d "$WORKTREE_DIR" ]; then
    echo "[$(ts)] No .claude/worktrees/ dir — nothing to do"
    exit 0
fi

# Guard: never remove the worktree this script is currently running inside.
CURRENT_WT=""
if [ -n "$INVOCATION_PWD" ] && [[ "$INVOCATION_PWD" == "$WORKTREE_DIR"/* ]]; then
    CURRENT_WT="${INVOCATION_PWD#$WORKTREE_DIR/}"
    CURRENT_WT="${CURRENT_WT%%/*}"
    echo "[$(ts)] Active worktree detected: $CURRENT_WT (will skip)"
fi

removed=0
skipped_active=0
skipped_young=0
failed=0
now_epoch=$(date +%s)

for wt_path in "$WORKTREE_DIR"/*/; do
    [ -d "$wt_path" ] || continue
    wt_path="${wt_path%/}"
    name="$(basename "$wt_path")"

    if [ -n "$CURRENT_WT" ] && [ "$name" = "$CURRENT_WT" ]; then
        echo "[$(ts)] SKIP: $name (currently active worktree)"
        skipped_active=$((skipped_active + 1))
        continue
    fi

    mtime=$(stat -c %Y "$wt_path" 2>/dev/null || echo "$now_epoch")
    age_days=$(( (now_epoch - mtime) / 86400 ))

    if [ "$age_days" -lt "$AGE_DAYS" ]; then
        echo "[$(ts)] SKIP: $name (age=${age_days}d, threshold=${AGE_DAYS}d)"
        skipped_young=$((skipped_young + 1))
        continue
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[$(ts)] DRY: would remove $name (age=${age_days}d)"
        removed=$((removed + 1))
        continue
    fi

    echo "[$(ts)] REMOVE: $name (age=${age_days}d)"
    if git worktree remove --force "$wt_path" 2>>"$LOGFILE"; then
        removed=$((removed + 1))
    else
        # Not a registered worktree (or git fails) — fall back to rm -rf.
        echo "[$(ts)] FALLBACK: rm -rf $name"
        if rm -rf "$wt_path" 2>>"$LOGFILE"; then
            removed=$((removed + 1))
        else
            failed=$((failed + 1))
        fi
    fi
done

echo "[$(ts)] Pruning git worktree metadata..."
if [ "$DRY_RUN" -eq 1 ]; then
    git worktree prune --dry-run -v 2>&1 || echo "WARN: prune dry-run failed"
else
    git worktree prune -v 2>&1 || echo "WARN: prune failed"
fi

echo "[$(ts)] === Done: removed=$removed skipped_active=$skipped_active skipped_young=$skipped_young failed=$failed ==="

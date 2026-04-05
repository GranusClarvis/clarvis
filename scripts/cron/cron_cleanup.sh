#!/bin/bash
# File-hygiene cleanup — weekly Sunday 05:30 UTC
# Rotates logs, compresses old memory, trims JSONL, prunes stale locks.
# No Claude Code spawning — lightweight Python-only.
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOCKFILE="/tmp/clarvis_cleanup.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(awk '{print $1}' "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)"
        exit 0
    fi
fi
echo "$$ $(date -u +%Y-%m-%dT%H:%M:%S)" > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup started ==="
python3 $CLARVIS_WORKSPACE/scripts/infra/cleanup_policy.py
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup finished ==="

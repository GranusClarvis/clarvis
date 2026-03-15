#!/bin/bash
# File-hygiene cleanup — weekly Sunday 05:30 UTC
# Rotates logs, compresses old memory, trims JSONL, prunes stale locks.
# No Claude Code spawning — lightweight Python-only.
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOCKFILE="/tmp/clarvis_cleanup.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup started ==="
python3 /home/agent/.openclaw/workspace/scripts/cleanup_policy.py
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup finished ==="

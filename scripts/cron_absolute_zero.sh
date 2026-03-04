#!/bin/bash
# Absolute Zero Reasoner — weekly self-play reasoning session
# Schedule: Sunday 03:00 UTC (between dream_engine and maintenance window)
# No Claude Code spawning — lightweight Python-only (ChromaDB brain access).
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOCKFILE="/tmp/clarvis_absolute_zero.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session started ==="
python3 /home/agent/.openclaw/workspace/scripts/absolute_zero.py run 5
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session finished ==="

#!/bin/bash
# Absolute Zero Reasoner — weekly self-play reasoning session
# Schedule: Sunday 03:00 UTC (between dream_engine and maintenance window)
# No Claude Code spawning — lightweight Python-only (ChromaDB brain access).
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cron_env.sh"

LOCKFILE="/tmp/clarvis_absolute_zero.lock"

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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session started ==="
python3 $CLARVIS_WORKSPACE/scripts/cognition/absolute_zero.py run 5
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session finished ==="

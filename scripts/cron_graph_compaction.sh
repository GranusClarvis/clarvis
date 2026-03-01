#!/bin/bash
# Graph compaction — 04:30 UTC daily
# Removes orphan edges, deduplicates, backfills nodes, reports health.
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/graph_compaction.log"
LOCKFILE="/tmp/clarvis_graph_compaction.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)" >> "$LOGFILE"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph compaction started ===" >> "$LOGFILE"

python3 /home/agent/.openclaw/workspace/scripts/graph_compaction.py >> "$LOGFILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: graph_compaction.py failed (exit $EXIT_CODE)" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph compaction finished ===" >> "$LOGFILE"

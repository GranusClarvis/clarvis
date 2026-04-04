#!/bin/bash
# Graph compaction — 04:30 UTC daily
# Removes orphan edges, deduplicates, backfills nodes, reports health.
source $CLARVIS_WORKSPACE/scripts/cron/cron_env.sh
source $CLARVIS_WORKSPACE/scripts/cron/lock_helper.sh

LOGFILE="memory/cron/graph_compaction.log"

# Arm script-level timeout (600s = 10 min) — kills script and releases locks on hang
set_script_timeout 600 "$LOGFILE"

# Acquire locks: local + maintenance
acquire_local_lock "/tmp/clarvis_graph_compaction.lock" "$LOGFILE" 1800
acquire_maintenance_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph compaction started ===" >> "$LOGFILE"

python3 $CLARVIS_WORKSPACE/scripts/brain_mem/graph_compaction.py >> "$LOGFILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: graph_compaction.py failed (exit $EXIT_CODE)" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph compaction finished ===" >> "$LOGFILE"

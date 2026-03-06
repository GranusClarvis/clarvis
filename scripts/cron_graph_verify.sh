#!/bin/bash
# Graph verification — daily soak-test when CLARVIS_GRAPH_BACKEND=sqlite
# Runs graph-verify parity check between JSON and SQLite stores.
# Exits nonzero on FAIL so cron_watchdog / health_monitor can alert.
#
# Schedule: after graph_compaction (04:30), e.g. 04:45 UTC
# Only runs when CLARVIS_GRAPH_BACKEND=sqlite; exits 0 silently otherwise.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

LOGFILE="memory/cron/graph_verify.log"

# Only run when sqlite backend is active
if [ "${CLARVIS_GRAPH_BACKEND:-json}" != "sqlite" ]; then
    exit 0
fi

# Acquire maintenance lock (mutual exclusion with checkpoint/compaction/vacuum)
acquire_maintenance_lock "$LOGFILE"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === Graph verify started ===" >> "$LOGFILE"
echo "[$TS] Backend: ${CLARVIS_GRAPH_BACKEND:-json}" >> "$LOGFILE"
echo "[$TS] SQLite DB: $(ls -lh data/clarvisdb/graph.db 2>/dev/null || echo 'NOT FOUND')" >> "$LOGFILE"
echo "[$TS] JSON file: $(ls -lh data/clarvisdb/relationships.json 2>/dev/null || echo 'NOT FOUND')" >> "$LOGFILE"

DUAL_WRITE="${CLARVIS_GRAPH_DUAL_WRITE:-1}"

if [ "$DUAL_WRITE" = "0" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Dual-write disabled — running SQLite integrity check only" >> "$LOGFILE"
    OUTPUT=$(python3 - <<'PY'
import sys
from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
store = GraphStoreSQLite("/home/agent/.openclaw/workspace/data/clarvisdb/graph.db")
ok = store.integrity_check()
stats = store.stats()
store.close()
print({"integrity_ok": ok, "nodes": stats.get("nodes"), "edges": stats.get("edges")})
sys.exit(0 if ok else 1)
PY
    2>&1)
    EXIT_CODE=$?
else
    OUTPUT=$(python3 -m clarvis brain graph-verify --sample-n 200 2>&1)
    EXIT_CODE=$?
fi

echo "$OUTPUT" >> "$LOGFILE"

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FAIL: verify exited $EXIT_CODE" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph verify finished (FAIL) ===" >> "$LOGFILE"
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Graph verify finished (PASS) ===" >> "$LOGFILE"

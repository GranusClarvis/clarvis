#!/bin/bash
# Graph checkpoint — SQLite online backup at 04:00 UTC
# Provides mid-cycle recovery point after heavy nightly reflection.
# Uses SQLite's online backup API (hot backup, no locking).
# Post-cutover (2026-03-29): SQLite is the sole runtime backend.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cron_env.sh"
source "$SCRIPT_DIR/lock_helper.sh"
DATA_DIR="$CLARVIS_WORKSPACE/data/clarvisdb"
SQLITE_DB="$DATA_DIR/graph.db"
SQLITE_CHECKPOINT="$DATA_DIR/graph.checkpoint.db"
LOG_FILE="$CLARVIS_WORKSPACE/memory/cron/graph_checkpoint.log"

# Arm script-level timeout (300s = 5 min) — kills script and releases locks on hang
set_script_timeout 300 "$LOG_FILE"

# Acquire maintenance lock (mutual exclusion with graph_compaction + chromadb_vacuum)
acquire_maintenance_lock "$LOG_FILE"

echo "=== Graph Checkpoint $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG_FILE"

if [ ! -f "$SQLITE_DB" ]; then
    echo "ERROR: SQLite graph.db not found: $SQLITE_DB" >> "$LOG_FILE"
    exit 1
fi

python3 -c "
from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
store = GraphStoreSQLite('$SQLITE_DB')
st = store.stats()
print(f\"Nodes: {st['nodes']}, Edges: {st['edges']}\")
store.backup('$SQLITE_CHECKPOINT')
store.close()
print('Backup OK')
" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "WARN: SQLite backup failed" >> "$LOG_FILE"
    exit 1
fi

SHA256=$(sha256sum "$SQLITE_CHECKPOINT" | awk '{print $1}')
echo "SQLite checkpoint saved: SHA256=$SHA256" >> "$LOG_FILE"
echo "Success" >> "$LOG_FILE"
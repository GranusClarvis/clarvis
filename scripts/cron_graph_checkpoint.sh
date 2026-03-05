#!/bin/bash
# Graph checkpoint — lightweight backup at 04:00 UTC
# Provides mid-cycle recovery point after heavy nightly reflection
#
# Backend-aware: when CLARVIS_GRAPH_BACKEND=sqlite, uses SQLite's online
# backup API (hot backup, no locking) instead of cp on JSON.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/cron_env.sh"
source "$SCRIPT_DIR/lock_helper.sh"
DATA_DIR="$SCRIPT_DIR/../data/clarvisdb"
GRAPH_FILE="$DATA_DIR/relationships.json"
CHECKPOINT_FILE="$DATA_DIR/relationships.checkpoint.json"
SQLITE_DB="$DATA_DIR/graph.db"
SQLITE_CHECKPOINT="$DATA_DIR/graph.checkpoint.db"
LOG_FILE="$SCRIPT_DIR/../memory/cron/graph_checkpoint.log"

# Acquire maintenance lock (mutual exclusion with graph_compaction + chromadb_vacuum)
acquire_maintenance_lock "$LOG_FILE"

echo "=== Graph Checkpoint $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG_FILE"

BACKEND="${CLARVIS_GRAPH_BACKEND:-json}"

if [ "$BACKEND" = "sqlite" ] && [ -f "$SQLITE_DB" ]; then
    # --- SQLite backend: use online backup API ---
    echo "Backend: SQLite" >> "$LOG_FILE"

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

else
    # --- JSON backend (legacy) ---
    echo "Backend: JSON" >> "$LOG_FILE"

    if [ ! -f "$GRAPH_FILE" ]; then
        echo "Graph file not found: $GRAPH_FILE" >> "$LOG_FILE"
        exit 1
    fi

    # Count nodes and edges
    NODE_COUNT=$(grep -o '"nodes":' "$GRAPH_FILE" > /dev/null && grep -o '"from":' "$GRAPH_FILE" | wc -l || echo 0)
    EDGE_COUNT=$(grep -o '"to":' "$GRAPH_FILE" | wc -l)

    # Compute SHA-256
    SHA256=$(sha256sum "$GRAPH_FILE" | awk '{print $1}')

    # Copy to checkpoint
    cp "$GRAPH_FILE" "$CHECKPOINT_FILE"

    echo "Checkpoint saved: $NODE_COUNT nodes, $EDGE_COUNT edges, SHA256=$SHA256" >> "$LOG_FILE"
fi

echo "Success" >> "$LOG_FILE"
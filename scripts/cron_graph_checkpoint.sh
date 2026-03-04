#!/bin/bash
# Graph checkpoint — lightweight backup at 04:00 UTC
# Provides mid-cycle recovery point after heavy nightly reflection

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data/clarvisdb"
GRAPH_FILE="$DATA_DIR/relationships.json"
CHECKPOINT_FILE="$DATA_DIR/relationships.checkpoint.json"
LOG_FILE="$SCRIPT_DIR/../memory/cron/graph_checkpoint.log"

# === MAINTENANCE LOCK — mutual exclusion with graph_compaction + chromadb_vacuum ===
MAINTENANCE_LOCK="/tmp/clarvis_maintenance.lock"

if [ -f "$MAINTENANCE_LOCK" ]; then
    mpid=$(cat "$MAINTENANCE_LOCK" 2>/dev/null)
    mlock_age=$(( $(date +%s) - $(stat -c %Y "$MAINTENANCE_LOCK" 2>/dev/null || echo 0) ))
    if [ -n "$mpid" ] && kill -0 "$mpid" 2>/dev/null && [ "$mlock_age" -le 600 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SKIP: Maintenance lock held (PID $mpid, age=${mlock_age}s)" >> "$LOG_FILE"
        exit 0
    else
        [ -n "$mpid" ] && echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] MAINTENANCE LOCK: Stale (age=${mlock_age}s) — reclaiming" >> "$LOG_FILE"
        rm -f "$MAINTENANCE_LOCK"
    fi
fi
echo $$ > "$MAINTENANCE_LOCK"
trap "rm -f $MAINTENANCE_LOCK" EXIT

echo "=== Graph Checkpoint $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG_FILE"

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
echo "Success" >> "$LOG_FILE"
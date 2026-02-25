#!/bin/bash
# Graph checkpoint — lightweight backup at 04:00 UTC
# Provides mid-cycle recovery point after heavy nightly reflection

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data/clarvisdb"
GRAPH_FILE="$DATA_DIR/relationships.json"
CHECKPOINT_FILE="$DATA_DIR/relationships.checkpoint.json"
LOG_FILE="$SCRIPT_DIR/../memory/cron/graph_checkpoint.log"

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
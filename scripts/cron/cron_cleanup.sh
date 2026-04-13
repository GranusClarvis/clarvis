#!/bin/bash
# File-hygiene cleanup — weekly Sunday 05:30 UTC
# Rotates logs, compresses old memory, trims JSONL, prunes stale locks.
# No Claude Code spawning — lightweight Python-only.
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOCKFILE="/tmp/clarvis_cleanup.lock"

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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup started ==="
python3 "$CLARVIS_WORKSPACE/scripts/infra/cleanup_policy.py"

# Sidecar pruning: remove old succeeded/removed entries from queue_state.json
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Pruning sidecar (removed >30d, succeeded >90d)..."
python3 -c "
from clarvis.queue.writer import prune_sidecar
result = prune_sidecar(removed_days=30, succeeded_days=90)
print(f'Sidecar pruned: removed={result[\"removed\"]}, succeeded={result[\"succeeded\"]}, before={result[\"total_before\"]}, after={result[\"total_after\"]}')
" 2>&1 || echo "WARN: Sidecar pruning failed"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup finished ==="

#!/bin/bash
# File-hygiene cleanup — weekly Sunday 05:30 UTC
# Rotates logs, compresses old memory, trims JSONL, prunes stale locks.
# No Claude Code spawning — lightweight Python-only.
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOGFILE="$CLARVIS_WORKSPACE/memory/cron/cleanup.log"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
acquire_local_lock "/tmp/clarvis_cleanup.lock" "$LOGFILE" 3600

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup started ==="
python3 "$CLARVIS_WORKSPACE/scripts/infra/cleanup_policy.py"

# Sidecar pruning: remove old succeeded/removed entries from queue_state.json
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Pruning sidecar (removed >30d, succeeded >90d)..."
python3 -c "
from clarvis.queue.writer import prune_sidecar
result = prune_sidecar(removed_days=30, succeeded_days=90)
print(f'Sidecar pruned: removed={result[\"removed\"]}, succeeded={result[\"succeeded\"]}, before={result[\"total_before\"]}, after={result[\"total_after\"]}')
" 2>&1 || echo "WARN: Sidecar pruning failed"

# Git worktree pruning: remove stale worktrees left by agents/Claude Code
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Pruning stale git worktrees..."
cd "$CLARVIS_WORKSPACE" && git worktree prune 2>&1 || echo "WARN: Worktree pruning failed"

# Weekly re-audit: longitudinal drift detection (0 LLM, <30s)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running weekly re-audit..."
python3 "$CLARVIS_WORKSPACE/scripts/audit/reaudit_runner.py" weekly 2>&1 || echo "WARN: Weekly re-audit failed"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly cleanup finished ==="

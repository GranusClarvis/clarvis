#!/bin/bash
# Absolute Zero Reasoner — weekly self-play reasoning session
# Schedule: Sunday 03:00 UTC (between dream_engine and maintenance window)
# No Claude Code spawning — lightweight Python-only (ChromaDB brain access).
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOGFILE="$CLARVIS_WORKSPACE/memory/cron/absolute_zero.log"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
acquire_local_lock "/tmp/clarvis_absolute_zero.lock" "$LOGFILE" 3600

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session started ==="
python3 "$CLARVIS_WORKSPACE/scripts/cognition/absolute_zero.py" run 5
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === AZR weekly session finished ==="

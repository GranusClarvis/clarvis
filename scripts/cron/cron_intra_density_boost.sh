#!/bin/bash
# Intra-density boost — 04:50 CET daily (after graph compaction)
# Targets the 3 most starved collections to close the repair-vs-decay gap.
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/intra_density_boost.log"

# Arm script-level timeout (600s = 10 min)
set_script_timeout 600 "$LOGFILE"

# Acquire locks: local + maintenance
acquire_local_lock "/tmp/clarvis_intra_density_boost.lock" "$LOGFILE" 1800
acquire_maintenance_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Intra-density boost started ===" >> "$LOGFILE"

python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/intra_density_boost.py" --threshold 0.6 --cap 500 >> "$LOGFILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: intra_density_boost.py failed (exit $EXIT_CODE)" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Intra-density boost finished ===" >> "$LOGFILE"

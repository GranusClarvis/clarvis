#!/bin/bash
# Daily brain quality evaluation — runs retrieval probe + quality assessment
# No Claude Code needed (pure Python, ~15s).
#
# Recommended schedule: 06:00 daily (after PI refresh at 05:45, before autonomous runs)
# This gives fresh metrics context and avoids lock contention.

source $CLARVIS_WORKSPACE/scripts/cron/cron_env.sh
source $CLARVIS_WORKSPACE/scripts/cron/lock_helper.sh

LOGFILE="memory/cron/brain_eval.log"

# Local lock only — no Claude Code, no maintenance lock needed
acquire_local_lock "/tmp/clarvis_brain_eval.lock" "$LOGFILE" 120

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === Daily brain evaluation started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

timeout 60 python3 scripts/metrics/daily_brain_eval.py cron >> "$LOGFILE" 2>&1
EXIT_CODE=$?

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TS] Brain evaluation completed successfully" >> "$LOGFILE"
else
    echo "[$TS] Brain evaluation failed (exit=$EXIT_CODE)" >> "$LOGFILE"
fi

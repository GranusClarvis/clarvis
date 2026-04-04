#!/bin/bash
# Daily PI refresh — runs quality + episodes + brain_stats + speed benchmarks
# and updates the stored PI metrics. Fast subset (<30s) to prevent staleness
# between full weekly benchmarks (Sun 06:00).
#
# Schedule: 05:45 daily (after maintenance window, before autonomous 06:00)

source $CLARVIS_WORKSPACE/scripts/cron/cron_env.sh
source $CLARVIS_WORKSPACE/scripts/cron/lock_helper.sh

LOGFILE="memory/cron/pi_refresh.log"

# Local lock only (no Claude Code, no maintenance lock needed)
acquire_local_lock "/tmp/clarvis_pi_refresh.lock" "$LOGFILE" 120

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === PI refresh started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

timeout 60 python3 scripts/metrics/performance_benchmark.py refresh >> "$LOGFILE" 2>&1
EXIT_CODE=$?

# Also record CLR (Clarvis Rating) composite score
timeout 30 python3 -m clarvis metrics clr --record >> "$LOGFILE" 2>&1
CLR_EXIT=$?
if [ $CLR_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CLR refresh failed (exit=$CLR_EXIT)" >> "$LOGFILE"
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TS] PI refresh completed successfully" >> "$LOGFILE"
else
    echo "[$TS] PI refresh failed (exit=$EXIT_CODE)" >> "$LOGFILE"
fi

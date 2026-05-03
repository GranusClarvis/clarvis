#!/bin/bash
# BB phase verification — weekly drift audit over QUEUE_ARCHIVE.md.
#
# Sits in the maintenance window (Sunday 04:30 CET) and shares
# /tmp/clarvis_maintenance.lock with the other graph/vacuum jobs to
# prevent concurrent ChromaDB/sqlite writes.
#
# Walks `[x] [BB_*]` items archived in the last 7 days, asserts cited
# commits exist in mega-house git log, asserts cited file paths exist,
# and (when --run-tests is set) re-runs `pnpm --filter @bunnybagz/<pkg>
# test`. On drift, appends a `[BB_<TAG>_REAL]` reopen task to QUEUE.md
# via clarvis.queue.writer.add_task.

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/bb_phase_verification.log"

# Maintenance window: 5 min upper bound (no test run by default).
set_script_timeout 600 "$LOGFILE"
acquire_maintenance_lock "$LOGFILE"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === BB phase verification started ===" >> "$LOGFILE"

EXTRA_ARGS=""
if [ "${BB_VERIFICATION_RUN_TESTS:-0}" = "1" ]; then
    EXTRA_ARGS="--run-tests"
fi

python3 "${CLARVIS_WORKSPACE}/scripts/audit/bb_phase_verification.py" $EXTRA_ARGS \
    >> "$LOGFILE" 2>&1
EXIT_CODE=$?

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB phase verification finished (exit=$EXIT_CODE) ===" >> "$LOGFILE"
exit $EXIT_CODE

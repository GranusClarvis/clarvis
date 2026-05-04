#!/bin/bash
# Daily retrieval-quality dashboard refresh.
#
# 1. Runs scripts/brain_mem/retrieval_benchmark.py (golden_qa) to refresh
#    data/retrieval_benchmark/latest.json (P@3, MRR, by_category).
# 2. Runs scripts/brain_mem/retrieval_dashboard.py to write a fresh
#    data/retrieval_quality/dashboard.md with a same-day `last_updated:` line.
#
# Schedule: 06:20 daily (between brain_eval at 06:05 and llm_brain_review at 06:15+).
# Logs: memory/cron/retrieval_quality.log (cron_watchdog.sh checks freshness)
#       monitoring/retrieval_quality.log (long-running tail for ops)
#
# Canonical-source TBD pending [P3_DASHBOARD_SOURCE_AUDIT]. Until that audit
# names a single source, this job runs the existing benchmark + an interim
# aggregator over benchmark + quality + context_relevance.

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/retrieval_quality.log"
OPS_LOG="$CLARVIS_WORKSPACE/monitoring/retrieval_quality.log"
mkdir -p "$(dirname "$OPS_LOG")"

# Local lock — pure Python, no Claude Code needed
acquire_local_lock "/tmp/clarvis_retrieval_quality.lock" "$LOGFILE" 120

cd "$CLARVIS_WORKSPACE" || exit 1

TS_START="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS_START] === Retrieval-quality refresh started ===" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Step 1 — refresh benchmark fixture (writes data/retrieval_benchmark/latest.json)
timeout 120 python3 scripts/brain_mem/retrieval_benchmark.py golden_qa >> "$LOGFILE" 2>&1
BENCH_EXIT=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] benchmark exit=$BENCH_EXIT" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Step 2 — generate dashboard.md from latest.json + report.json + context_relevance.jsonl
timeout 30 python3 scripts/brain_mem/retrieval_dashboard.py >> "$LOGFILE" 2>&1
DASH_EXIT=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] dashboard exit=$DASH_EXIT" | tee -a "$LOGFILE" >> "$OPS_LOG"

# Verify dashboard freshness (must be same calendar day in UTC)
DASHBOARD_FILE="$CLARVIS_WORKSPACE/data/retrieval_quality/dashboard.md"
if [ -f "$DASHBOARD_FILE" ]; then
    DASH_AGE=$(( $(date +%s) - $(stat -c%Y "$DASHBOARD_FILE" 2>/dev/null || echo 0) ))
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] dashboard age=${DASH_AGE}s" | tee -a "$LOGFILE" >> "$OPS_LOG"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: dashboard file missing after refresh" | tee -a "$LOGFILE" >> "$OPS_LOG"
fi

TS_END="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $BENCH_EXIT -eq 0 ] && [ $DASH_EXIT -eq 0 ]; then
    echo "[$TS_END] Retrieval-quality refresh completed" | tee -a "$LOGFILE" >> "$OPS_LOG"
    exit 0
else
    echo "[$TS_END] Retrieval-quality refresh FAILED (bench=$BENCH_EXIT dashboard=$DASH_EXIT)" | tee -a "$LOGFILE" >> "$OPS_LOG"
    exit 1
fi

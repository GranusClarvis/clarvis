#!/bin/bash
# cron_bb_beta_summary.sh — Daily BB Phase 3 internal beta summary.
#
# Runs every day at 09:00 CET during the internal closed beta. Polls the
# BunnyBagz indexer for the trailing 24h of bet activity and writes a
# verdict report (GREEN / YELLOW / RED / PAUSED) to
# memory/cron/bb_beta_<YYYY-MM-DD>.md, updating the streak state at
# memory/cron/bb_beta_streak.json.
#
# Operator gating (see docs/INTERNAL_BETA_PLAN.md §4.1):
#   BUNNYBAGZ_BETA_ACTIVE=1     # required — when unset/0, this is a no-op
#   BUNNYBAGZ_INDEXER_URL=...   # default: http://localhost:42069
#
# Phase 3 cannot exit until streak.green_days >= 7. The companion
# invariant cron ([BB_PHASE3_TESTNET_7D_INVARIANT_LOG]) is the source of
# truth for on-chain invariants — this cron is engagement + ops health.

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="${CLARVIS_WORKSPACE}/memory/cron/bb_beta_summary.log"
LOCKFILE="/tmp/clarvis_bb_beta_summary.lock"

set_script_timeout 300 "$LOGFILE"
acquire_local_lock "$LOCKFILE" "$LOGFILE" 600

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === BB beta summary started ===" >> "$LOGFILE"

# Operator gate — beta is opt-in. Default off so installing the cron in
# advance of beta-on does not generate noisy red-day reports.
if [ "${BUNNYBAGZ_BETA_ACTIVE:-0}" != "1" ]; then
    echo "[$TS] beta inactive (BUNNYBAGZ_BETA_ACTIVE!=1) — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB beta summary skipped ===" >> "$LOGFILE"
    exit 0
fi

INDEXER_URL="${BUNNYBAGZ_INDEXER_URL:-http://localhost:42069}"
echo "[$TS] indexer=$INDEXER_URL" >> "$LOGFILE"

python3 "${CLARVIS_WORKSPACE}/scripts/audit/bb_beta_summary.py" \
    --indexer "$INDEXER_URL" \
    >> "$LOGFILE" 2>&1
EXIT_CODE=$?

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB beta summary finished (exit=$EXIT_CODE) ===" >> "$LOGFILE"
exit $EXIT_CODE

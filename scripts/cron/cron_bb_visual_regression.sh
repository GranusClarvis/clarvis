#!/bin/bash
# cron_bb_visual_regression.sh — Daily BunnyBagz visual regression sweep.
#
# Hooks into [BB_PHASE3_VISUAL_REGRESSION_BASELINE]. Runs
# `apps/web/scripts/visual-baseline.mjs --diff` against the saved
# baseline, parses the JSON report, and posts to Telegram when any
# captured surface exceeds pixel-diff > 5% or perceptual-hash distance
# > 10. The script itself encodes those thresholds — this cron just
# parses regressions[] and counts them.
#
# Operator gates:
#   BB_VISUAL_REGRESSION_ACTIVE=1     # required — when unset/0, no-op
#   BUNNYBAGZ_REPO_PATH=...           # default: /home/agent/agents/mega-house/workspace
#   BB_VISUAL_BASE_URL=...            # default: http://127.0.0.1:3000
#   BB_VISUAL_CDP_URL=...             # default: http://127.0.0.1:18800
#
# Suggested schedule (CET):
#   05:30 daily   /home/agent/.openclaw/workspace/scripts/cron/cron_bb_visual_regression.sh
#
# Operator updates the baseline intentionally (after a known-good UI
# change) by running:
#   cd /home/agent/agents/mega-house/workspace/apps/web && \
#       node scripts/visual-baseline.mjs --update-baseline

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="${CLARVIS_WORKSPACE}/memory/cron/bb_visual_regression.log"
LOCKFILE="/tmp/clarvis_bb_visual_regression.lock"

set_script_timeout 600 "$LOGFILE"
acquire_local_lock "$LOCKFILE" "$LOGFILE" 900

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
mkdir -p "$(dirname "$LOGFILE")"
echo "[$TS] === BB visual regression started ===" >> "$LOGFILE"

# Operator gate — opt-in (browser + dev server are heavy).
if [ "${BB_VISUAL_REGRESSION_ACTIVE:-0}" != "1" ]; then
    echo "[$TS] inactive (BB_VISUAL_REGRESSION_ACTIVE!=1) — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression skipped ===" >> "$LOGFILE"
    exit 0
fi

REPO_PATH="${BUNNYBAGZ_REPO_PATH:-/home/agent/agents/mega-house/workspace}"
BASE_URL="${BB_VISUAL_BASE_URL:-http://127.0.0.1:3000}"
CDP_URL="${BB_VISUAL_CDP_URL:-http://127.0.0.1:18800}"

if [ ! -d "$REPO_PATH/apps/web" ]; then
    echo "[$TS] repo path missing ($REPO_PATH/apps/web) — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression skipped ===" >> "$LOGFILE"
    exit 0
fi

# Liveness checks: dev server + Clarvis browser CDP must both be up.
# The visual-baseline harness can't capture if either is down. Skip
# gracefully (not a failure) so we don't alert on infra noise.
if ! curl -fsS --max-time 5 "${BASE_URL}" -o /dev/null 2>>"$LOGFILE"; then
    echo "[$TS] dev server unreachable at $BASE_URL — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression skipped ===" >> "$LOGFILE"
    exit 0
fi
if ! curl -fsS --max-time 5 "${CDP_URL}/json/version" -o /dev/null 2>>"$LOGFILE"; then
    echo "[$TS] CDP unreachable at $CDP_URL — skip" >> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression skipped ===" >> "$LOGFILE"
    exit 0
fi

# Run the harness and capture the JSON report.
REPORT_FILE="$(dirname "$LOGFILE")/bb_visual_regression_report.json"
echo "[$TS] running visual-baseline --diff (json)" >> "$LOGFILE"

cd "$REPO_PATH/apps/web" || { echo "[$TS] cd failed" >> "$LOGFILE"; exit 1; }
node scripts/visual-baseline.mjs --diff --json \
    --base-url "$BASE_URL" \
    --cdp-url "$CDP_URL" \
    > "$REPORT_FILE" 2>>"$LOGFILE"
EXIT_CODE=$?

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] harness exit=$EXIT_CODE" >> "$LOGFILE"

# Exit codes:
#   0 — no regressions
#   2 — regressions detected (still proceed to alert)
#   1 — runtime error (log and bail; no Telegram noise)
if [ "$EXIT_CODE" = "1" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression failed (runtime error) ===" >> "$LOGFILE"
    exit 1
fi

# Parse the report. Telegram alert only when regressions > 0.
REGRESSIONS=$(python3 - "$REPORT_FILE" <<'PY'
import json, sys
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        report = json.load(f)
except Exception:
    print(0)
    sys.exit(0)
print(int(report.get("regressions") or 0))
PY
)

if [ "${REGRESSIONS:-0}" -gt 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] regressions=$REGRESSIONS — sending Telegram" >> "$LOGFILE"
    python3 "${CLARVIS_WORKSPACE}/scripts/cron/cron_bb_visual_regression_notify.py" \
        --report "$REPORT_FILE" \
        >> "$LOGFILE" 2>&1
    NOTIFY_CODE=$?
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] notify exit=$NOTIFY_CODE" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] no regressions — telegram skipped" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === BB visual regression finished (exit=$EXIT_CODE) ===" >> "$LOGFILE"
exit 0

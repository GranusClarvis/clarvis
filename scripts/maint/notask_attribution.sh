#!/usr/bin/env bash
# notask_attribution.sh — Daily attribution of no-task heartbeat cycles.
#
# Phase 12 execution-shape monitor (2026-04-30) measured 2/18 = ~11% no-task
# cycles, with 100% of those bucketed as `all_filtered_by_v2`. That ad-hoc
# scan produced no daily aggregation log, so regressions are invisible to the
# watchdog. This script runs nightly at 23:55, attributes the last 24h of
# no-task cycles to one of five canonical reasons, appends a single CSV row
# to monitoring/notask_attribution.log, and exits non-zero when the no-task
# ratio breaches 25% so the cron watchdog flags the regression.
#
# Reasons:
#   all_filtered_by_v2 — queue had items, Queue V2 filtered them all out
#   queue_empty        — preflight reported queue_empty / no_tasks
#   gate_skip          — heartbeat gate decided nothing changed
#   lock_held          — another job (local/global/maintenance) held the lock
#   unknown            — "No task selected" without an attributable upstream marker
#
# CSV row shape (one per run, appended):
#   ${date_utc},${total_cycles},all_filtered_by_v2=${n},queue_empty=${n},gate_skip=${n},lock_held=${n},unknown=${n},notask=${n},ratio=${pct}
#
# Exit codes:
#   0 — no-task ratio ≤ threshold (or zero cycles in window)
#   1 — no-task ratio > threshold (regression alert)
#   2 — usage / I/O error
#
# Usage:
#   notask_attribution.sh                 # default: scan monitoring/heartbeat.log else memory/cron/autonomous.log
#   notask_attribution.sh <log_path>      # explicit log path (used by tests)
#   THRESHOLD=25 notask_attribution.sh    # override regression threshold (percent)
#   OUT_LOG=/tmp/foo.log notask_attribution.sh   # override output csv path (used by tests)

set -euo pipefail

WS="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"

# Pick the first log path that exists from explicit arg, then canonical
# monitoring/heartbeat.log, then memory/cron/autonomous.log fallback.
INPUT_LOG="${1:-}"
if [ -z "$INPUT_LOG" ]; then
    if [ -f "$WS/monitoring/heartbeat.log" ]; then
        INPUT_LOG="$WS/monitoring/heartbeat.log"
    elif [ -f "$WS/memory/cron/autonomous.log" ]; then
        INPUT_LOG="$WS/memory/cron/autonomous.log"
    fi
fi

OUT_LOG="${OUT_LOG:-$WS/monitoring/notask_attribution.log}"
THRESHOLD="${THRESHOLD:-25}"
LOCK="${LOCK:-/tmp/clarvis_notask_attribution.lock}"

mkdir -p "$(dirname "$OUT_LOG")"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
day() { date -u +%Y-%m-%d; }

cleanup() { rm -f "$LOCK"; }
trap cleanup EXIT INT TERM

# Stale-lock guard: if a previous run's PID is dead, take the lock.
if [ -e "$LOCK" ]; then
    OLD_PID=$(cat "$LOCK" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(ts)] SKIP another notask_attribution run is active (pid=$OLD_PID)" >> "$OUT_LOG"
        trap - EXIT INT TERM
        exit 0
    fi
fi
echo "$$" > "$LOCK"

if [ -z "$INPUT_LOG" ] || [ ! -f "$INPUT_LOG" ]; then
    echo "[$(ts)] SKIP no input log (looked for monitoring/heartbeat.log, memory/cron/autonomous.log)" >> "$OUT_LOG"
    exit 0
fi

# 24h cutoff in lexicographic-comparable ISO 8601 form.
CUTOFF=$(date -u -d "24 hours ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null \
         || date -u -v-24H +%Y-%m-%dT%H:%M:%S)

# Slice the last 24h window into a temp file so we can run multiple grep -c
# passes against it cheaply (the task spec calls for grep -c per reason).
WINDOW=$(mktemp)
trap 'rm -f "$LOCK" "$WINDOW"' EXIT INT TERM

awk -v cutoff="$CUTOFF" '
    /^\[[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\]/ {
        t = substr($0, 2, 19)
        if (t >= cutoff) print
    }
' "$INPUT_LOG" > "$WINDOW"

# Count totals and per-reason occurrences using grep -c (per spec).
GATE_WAKE=$(grep -c 'GATE: wake' "$WINDOW" || true)
GATE_SKIP=$(grep -c 'GATE: skip' "$WINDOW" || true)
LOCK_HELD=$(grep -cE 'SKIP: Previous run still active|GLOBAL LOCK: Claude already running|Maintenance lock held' "$WINDOW" || true)
QUEUE_EMPTY=$(grep -cE 'PREFLIGHT: status=queue_empty|PREFLIGHT: status=no_tasks' "$WINDOW" || true)
ALL_FILTERED=$(grep -c 'PREFLIGHT: status=all_filtered_by_v2' "$WINDOW" || true)
NO_TASK_LINES=$(grep -c 'No task selected' "$WINDOW" || true)
COG_DEFER=$(grep -c 'COGNITIVE LOAD: DEFERRING' "$WINDOW" || true)

# grep -c returns 0 with trailing newline; coerce to int and default empty → 0.
GATE_WAKE=${GATE_WAKE:-0};   GATE_SKIP=${GATE_SKIP:-0}
LOCK_HELD=${LOCK_HELD:-0};   QUEUE_EMPTY=${QUEUE_EMPTY:-0}
ALL_FILTERED=${ALL_FILTERED:-0}; NO_TASK_LINES=${NO_TASK_LINES:-0}
COG_DEFER=${COG_DEFER:-0}

UNEXPLAINED=$(( NO_TASK_LINES - ALL_FILTERED - QUEUE_EMPTY ))
[ "$UNEXPLAINED" -lt 0 ] && UNEXPLAINED=0
UNKNOWN=$(( UNEXPLAINED + COG_DEFER ))

NOTASK=$(( GATE_SKIP + LOCK_HELD + QUEUE_EMPTY + ALL_FILTERED + UNKNOWN ))
TOTAL=$(( GATE_WAKE + GATE_SKIP + LOCK_HELD ))

if [ "$TOTAL" -gt 0 ]; then
    PCT=$(awk -v n="$NOTASK" -v t="$TOTAL" 'BEGIN { printf "%.1f", (n/t)*100 }')
else
    PCT="0.0"
fi

CSV_LINE="$(day),${TOTAL},all_filtered_by_v2=${ALL_FILTERED},queue_empty=${QUEUE_EMPTY},gate_skip=${GATE_SKIP},lock_held=${LOCK_HELD},unknown=${UNKNOWN},notask=${NOTASK},ratio=${PCT}"
printf '%s\n' "$CSV_LINE" >> "$OUT_LOG"

# Regression gate: above threshold → non-zero exit so cron_watchdog notices.
BREACH=$(awk -v p="$PCT" -v th="$THRESHOLD" 'BEGIN { print (p+0 > th+0) ? 1 : 0 }')
if [ "$TOTAL" -gt 0 ] && [ "$BREACH" -eq 1 ]; then
    echo "[$(ts)] ALERT no-task ratio ${PCT}% > ${THRESHOLD}% threshold (notask=${NOTASK}/${TOTAL})" >&2
    exit 1
fi

exit 0

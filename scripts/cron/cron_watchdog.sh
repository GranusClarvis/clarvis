#!/bin/bash
# =============================================================================
# Cron Watchdog — Alerts if cron jobs don't run on schedule
# =============================================================================
# Checks each cron log file for recent activity. If a job hasn't produced
# output within its expected interval + grace period, flags it as MISSED.
#
# Usage:
#   ./cron_watchdog.sh           # Check all jobs, print report
#   ./cron_watchdog.sh --alert   # Also send Telegram alert on failures
# =============================================================================

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOG_DIR="$CLARVIS_WORKSPACE/memory/cron"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"
NOW=$(date +%s)
ALERT_MODE=false
FAILURES=0
REPORT=""

for arg in "$@"; do
  case "$arg" in
    --alert) ALERT_MODE=true ;;
  esac
done

# Check if a log file was modified within the expected window
# Args: name, log_file, max_age_hours
check_job() {
  local name="$1"
  local log_file="$2"
  local max_age_hours="$3"
  local max_age_seconds=$((max_age_hours * 3600))

  if [ ! -f "$log_file" ]; then
    REPORT="${REPORT}MISSED  $name — log file missing ($log_file)\n"
    ((FAILURES++)) || true
    return
  fi

  local file_mod
  file_mod=$(stat -c%Y "$log_file" 2>/dev/null || echo 0)
  local age=$((NOW - file_mod))

  if [ "$age" -gt "$max_age_seconds" ]; then
    local hours_ago=$((age / 3600))
    REPORT="${REPORT}MISSED  $name — last output ${hours_ago}h ago (limit: ${max_age_hours}h)\n"
    ((FAILURES++)) || true
  else
    local hours_ago=$((age / 3600))
    local mins_ago=$(( (age % 3600) / 60 ))
    REPORT="${REPORT}OK      $name — last output ${hours_ago}h ${mins_ago}m ago\n"
  fi
}

# --- Check each job ---
# Job name, log file, max hours since last output (interval + grace)
check_job "autonomous"      "$LOG_DIR/autonomous.log"      6    # max gap ~5h (23:00→01:00+06:00), grace 1h
check_job "health_monitor"  "$CLARVIS_WORKSPACE/monitoring/health.log" 1  # every 15m, grace 45m
check_job "morning_report"  "$LOG_DIR/report_morning.log"  26   # daily at 10:00, grace 2h
check_job "evening_report"  "$LOG_DIR/report_evening.log"  26   # daily at 22:00, grace 2h
check_job "morning_plan"    "$LOG_DIR/morning.log"          26   # daily at 08:00, grace 2h
check_job "evolution"       "$LOG_DIR/evolution.log"        26   # daily at 13:00, grace 2h
check_job "evening_review"  "$LOG_DIR/evening.log"          26   # daily at 18:00, grace 2h
check_job "reflection"      "$LOG_DIR/reflection.log"       26   # daily at 21:00, grace 2h
check_job "backup"          "$LOG_DIR/backup.log"           26   # daily at 02:00, grace 2h
check_job "backup_verify"   "$LOG_DIR/backup_verify.log"    26   # daily at 02:30, grace 2h
check_job "dream_engine"    "$LOG_DIR/dream.log"            26   # daily at 02:45, grace 2h
check_job "research"        "$LOG_DIR/research.log"         10   # 2x/day at 10,16, grace 4h
# --- Added 2026-04-09 (Phase 1: Operational Truthfulness) ---
check_job "impl_sprint"     "$LOG_DIR/implementation_sprint.log" 26  # daily at 14:00, grace 2h
check_job "strategic_audit" "$LOG_DIR/strategic_audit.log"  170  # Wed+Sat 17:00 (~3.5d max gap)
check_job "graph_checkpoint" "$LOG_DIR/graph_checkpoint.log" 26  # daily at 04:00
check_job "graph_compaction" "$LOG_DIR/graph_compaction.log" 26  # daily at 04:30
check_job "graph_verify"    "$LOG_DIR/graph_verify.log"     26   # daily at 04:45
check_job "db_vacuum"       "$LOG_DIR/chromadb_vacuum.log"  26   # daily at 05:00
check_job "orchestrator"    "$LOG_DIR/orchestrator.log"     26   # daily at 19:30
check_job "pi_refresh"      "$LOG_DIR/pi_refresh.log"       26   # daily at 05:45
check_job "brain_eval"      "$LOG_DIR/brain_eval.log"       26   # daily at 06:05
check_job "llm_brain_review" "$LOG_DIR/llm_brain_review.log" 26  # daily at 06:20
check_job "llm_context_review" "$LOG_DIR/llm_context_review.log" 26 # daily at 06:40
check_job "status_json"     "$LOG_DIR/status_json.log"      26   # daily at 05:50
check_job "relevance_refresh" "$LOG_DIR/relevance_refresh.log" 26 # daily at 02:40
check_job "calibration_report" "$LOG_DIR/calibration_report.log" 170 # Sun 06:45
# Weekly jobs
check_job "cleanup"         "$LOG_DIR/cleanup.log"          170  # Sun 05:30
check_job "absolute_zero"   "$LOG_DIR/absolute_zero.log"    170  # Sun 03:00
check_job "clr_benchmark"   "$LOG_DIR/clr_benchmark.log"    170  # Sun 06:30
check_job "goal_hygiene"    "$LOG_DIR/goal_hygiene.log"     170  # Sun 05:10
check_job "brain_hygiene"   "$LOG_DIR/brain_hygiene.log"    170  # Sun 05:15
check_job "data_lifecycle"  "$LOG_DIR/data_lifecycle.log"   170  # Sun 05:20
check_job "pi_benchmark"    "$LOG_DIR/pi_benchmark.log"     170  # Sun 06:00
# Monthly jobs
check_job "monthly_reflection" "$LOG_DIR/monthly_reflection.log" 750  # 1st 03:30
check_job "brief_benchmark" "$LOG_DIR/brief_benchmark.log"  750  # 1st 03:45

# --- Digest freshness check ---
# CLR autonomy score tanks when digest.md goes stale (>6h without update).
check_job "digest"          "$LOG_DIR/digest.md"            8    # multiple writers/day, 8h grace

# --- Stale lock check ---
# Alert on any /tmp/clarvis_*.lock files older than 2 hours.
# Lock file format: "PID [TIMESTAMP]" (timestamp optional for backward compat).
# Auto-reclaims locks held by dead processes to prevent SIGKILL orphans from
# blocking future cron runs indefinitely.
STALE_LOCK_THRESHOLD=7200  # 2 hours in seconds
STALE_LOCKS=""
STALE_LOCK_COUNT=0
RECLAIMED_COUNT=0
for lockfile in /tmp/clarvis_*.lock; do
    [ -f "$lockfile" ] || continue
    lock_mod=$(stat -c%Y "$lockfile" 2>/dev/null || echo 0)
    lock_age=$((NOW - lock_mod))
    if [ "$lock_age" -gt "$STALE_LOCK_THRESHOLD" ]; then
        lock_content=$(cat "$lockfile" 2>/dev/null || echo "?")
        lock_pid="${lock_content%% *}"  # First field = PID
        lock_ts="${lock_content#* }"    # Rest = timestamp (if present)
        [ "$lock_ts" = "$lock_content" ] && lock_ts="(no timestamp)"
        lock_name=$(basename "$lockfile")
        lock_hours=$((lock_age / 3600))
        lock_mins=$(( (lock_age % 3600) / 60 ))
        # Check if holding process is still alive
        pid_status="dead"
        if [ "$lock_pid" != "?" ] && kill -0 "$lock_pid" 2>/dev/null; then
            pid_status="alive"
        fi
        if [ "$pid_status" = "dead" ]; then
            # Auto-reclaim: process is dead (likely SIGKILL), safe to remove
            rm -f "$lockfile"
            STALE_LOCKS="${STALE_LOCKS}RECLAIM ${lock_name} — ${lock_hours}h ${lock_mins}m old (PID ${lock_pid} dead, ts=${lock_ts}) — auto-removed\n"
            ((RECLAIMED_COUNT++)) || true
        else
            STALE_LOCKS="${STALE_LOCKS}STALE   ${lock_name} — ${lock_hours}h ${lock_mins}m old (PID ${lock_pid} alive, ts=${lock_ts})\n"
            ((STALE_LOCK_COUNT++)) || true
        fi
    fi
done

if [ "$STALE_LOCK_COUNT" -gt 0 ] || [ "$RECLAIMED_COUNT" -gt 0 ]; then
    REPORT="${REPORT}${STALE_LOCKS}"
    ((FAILURES += STALE_LOCK_COUNT)) || true
else
    REPORT="${REPORT}OK      locks — no stale locks (>2h)\n"
fi

# --- Working memory health check ---
# Verify attention spotlight has active items (target: 3+)
WM_FILE="$CLARVIS_WORKSPACE/data/attention/spotlight.json"
if [ -f "$WM_FILE" ]; then
    WM_ACTIVE=$(python3 -c "
import json
with open('$WM_FILE') as f:
    data = json.load(f)
items = data.get('items', [])
active = sum(1 for i in items if i.get('salience', 0) >= 0.1)
print(active)
" 2>/dev/null || echo 0)
    if [ "$WM_ACTIVE" -lt 3 ]; then
        REPORT="${REPORT}WARN    working_memory — only ${WM_ACTIVE} active items (target: 3+)\n"
        # Auto-seed if completely empty
        if [ "$WM_ACTIVE" -eq 0 ]; then
            python3 -m clarvis.cognition.attention add "System watchdog: working memory was empty, seeded" 0.6 >> "$WATCHDOG_LOG" 2>&1
            python3 -m clarvis.cognition.attention add "Active evolution: $(date -u +%Y-%m-%d) heartbeat cycle running" 0.5 >> "$WATCHDOG_LOG" 2>&1
            REPORT="${REPORT}REPAIR  working_memory — seeded 2 items to prevent empty state\n"
        fi
    else
        REPORT="${REPORT}OK      working_memory — ${WM_ACTIVE} active items\n"
    fi
else
    REPORT="${REPORT}MISSED  working_memory — spotlight.json missing\n"
    ((FAILURES++)) || true
fi

# --- Queue governance health check ---
QH=$(python3 -c "
from clarvis.queue import queue_health
h = queue_health()
parts = []
if h['p0_over_cap']:
    parts.append(f\"P0 over cap ({h['p0_count']}/{h['p0_cap']})\")
if h['p1_over_cap']:
    parts.append(f\"P1 over cap ({h['p1_count']}/{h['p1_cap']})\")
if h['stale_in_progress'] > 0:
    parts.append(f\"{h['stale_in_progress']} stale in-progress\")
if parts:
    print('WARN    ' + ', '.join(parts))
else:
    print(f\"OK      P0={h['p0_count']}/{h['p0_cap']} P1={h['p1_count']}/{h['p1_cap']} stale={h['stale_in_progress']}\")
" 2>/dev/null || echo "MISSED  queue_health — import failed")
REPORT="${REPORT}${QH/WARN/WARN   }\n"
if echo "$QH" | grep -q "^WARN"; then
    ((FAILURES++)) || true
fi

# --- Output report ---
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S)
echo "[$TIMESTAMP] Watchdog check: $FAILURES failures" >> "$WATCHDOG_LOG"

echo "=============================="
echo "  Cron Watchdog Report"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "=============================="
echo -e "$REPORT"
echo "------------------------------"
echo "Total failures: $FAILURES"
echo "=============================="

# --- Auto-recovery: Run cron_doctor if failures detected ---
if [ "$FAILURES" -gt 0 ]; then
  echo "[$TIMESTAMP] Running cron_doctor.py recover..." >> "$WATCHDOG_LOG"
  DOCTOR_SCRIPT="$CLARVIS_WORKSPACE/scripts/cron/cron_doctor.py"
  DOCTOR_OUTPUT=$(python3 "$DOCTOR_SCRIPT" recover 2>&1)
  DOCTOR_EXIT=$?
  echo "$DOCTOR_OUTPUT"
  echo "[$TIMESTAMP] Cron doctor exit=$DOCTOR_EXIT" >> "$WATCHDOG_LOG"

  # Re-check after recovery to see how many are still failing
  STILL_FAILING=0
  recheck_job() {
    local log_file="$1"
    local max_age_hours="$2"
    local max_age_seconds=$((max_age_hours * 3600))
    if [ ! -f "$log_file" ]; then ((STILL_FAILING++)) || true; return; fi
    local file_mod; file_mod=$(stat -c%Y "$log_file" 2>/dev/null || echo 0)
    local age=$(( $(date +%s) - file_mod ))
    [ "$age" -gt "$max_age_seconds" ] && { ((STILL_FAILING++)) || true; }
  }
  # Allow adequate startup time for recovered services before rechecking
  sleep 30
  recheck_job "$LOG_DIR/autonomous.log" 4
  recheck_job "$CLARVIS_WORKSPACE/monitoring/health.log" 1
  recheck_job "$LOG_DIR/report_morning.log" 26
  recheck_job "$LOG_DIR/report_evening.log" 26
  recheck_job "$LOG_DIR/morning.log" 26
  recheck_job "$LOG_DIR/evolution.log" 26
  recheck_job "$LOG_DIR/evening.log" 26
  recheck_job "$LOG_DIR/reflection.log" 26
  recheck_job "$LOG_DIR/backup.log" 26
  recheck_job "$LOG_DIR/backup_verify.log" 26
  recheck_job "$LOG_DIR/dream.log" 26
  recheck_job "$LOG_DIR/research.log" 10
  recheck_job "$LOG_DIR/implementation_sprint.log" 26
  recheck_job "$LOG_DIR/strategic_audit.log" 170
  recheck_job "$LOG_DIR/graph_checkpoint.log" 26
  recheck_job "$LOG_DIR/graph_compaction.log" 26
  recheck_job "$LOG_DIR/graph_verify.log" 26
  recheck_job "$LOG_DIR/chromadb_vacuum.log" 26
  recheck_job "$LOG_DIR/orchestrator.log" 26
  recheck_job "$LOG_DIR/pi_refresh.log" 26
  recheck_job "$LOG_DIR/brain_eval.log" 26
  recheck_job "$LOG_DIR/llm_brain_review.log" 26
  recheck_job "$LOG_DIR/llm_context_review.log" 26
  recheck_job "$LOG_DIR/status_json.log" 26
  recheck_job "$LOG_DIR/relevance_refresh.log" 26
  recheck_job "$LOG_DIR/cleanup.log" 170
  recheck_job "$LOG_DIR/absolute_zero.log" 170
  recheck_job "$LOG_DIR/clr_benchmark.log" 170
  recheck_job "$LOG_DIR/goal_hygiene.log" 170
  recheck_job "$LOG_DIR/brain_hygiene.log" 170
  recheck_job "$LOG_DIR/data_lifecycle.log" 170
  recheck_job "$LOG_DIR/pi_benchmark.log" 170
  recheck_job "$LOG_DIR/calibration_report.log" 170
  recheck_job "$LOG_DIR/monthly_reflection.log" 750
  recheck_job "$LOG_DIR/brief_benchmark.log" 750

  RECOVERED=$(( FAILURES - STILL_FAILING ))
  echo "------------------------------"
  echo "  Recovery: $RECOVERED/$FAILURES jobs recovered"
  echo "  Still failing: $STILL_FAILING"
  echo "=============================="
  echo "[$TIMESTAMP] Recovery: $RECOVERED/$FAILURES recovered, $STILL_FAILING still failing" >> "$WATCHDOG_LOG"

  FAILURES=$STILL_FAILING
fi

# --- Send alert if failures STILL detected after recovery (with dedup) ---
# Only send Telegram alert when:
#   1. The set of failing jobs changes (new failures or recoveries), OR
#   2. It's the first alert of the day (daily reminder at most), OR
#   3. No alert was sent yet for the current failure set
ALERT_STATE_FILE="$CLARVIS_WORKSPACE/data/watchdog_alert_state.json"
CURRENT_FAILURES=$(echo -e "$REPORT" | grep -E "^MISSED|^STALE" | sort | md5sum | awk '{print $1}')
SHOULD_ALERT=false

if [ "$FAILURES" -gt 0 ] && [ "$ALERT_MODE" = true ]; then
  if [ -f "$ALERT_STATE_FILE" ]; then
    PREV_HASH=$(python3 -c "
import json
try:
    s = json.load(open('$ALERT_STATE_FILE'))
    print(s.get('failure_hash', ''))
except: print('')
" 2>/dev/null)
    PREV_DATE=$(python3 -c "
import json
try:
    s = json.load(open('$ALERT_STATE_FILE'))
    print(s.get('date', ''))
except: print('')
" 2>/dev/null)
    TODAY=$(date -u +%Y-%m-%d)
    if [ "$CURRENT_FAILURES" != "$PREV_HASH" ]; then
      SHOULD_ALERT=true  # Failure set changed
    elif [ "$TODAY" != "$PREV_DATE" ]; then
      SHOULD_ALERT=true  # First alert of a new day (daily reminder)
    fi
  else
    SHOULD_ALERT=true  # No prior state — first alert
  fi

  # Save current state regardless
  python3 -c "
import json
state = {'failure_hash': '$CURRENT_FAILURES', 'date': '$(date -u +%Y-%m-%d)', 'failures': $FAILURES, 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%S)'}
json.dump(state, open('$ALERT_STATE_FILE', 'w'), indent=2)
" 2>/dev/null

  if [ "$SHOULD_ALERT" = true ]; then
    ALERT_MSG="⚠️ Cron Watchdog Alert

${FAILURES} cron job(s) still failing after auto-recovery:

$(echo -e "$REPORT" | grep -E "MISSED|STALE")

Recovery log: memory/cron/doctor.log
Watchdog log: memory/cron/watchdog.log"

    python3 << PYEOF
import json, urllib.request, urllib.parse, os
try:
    token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
    if not token:
        with open('${OPENCLAW_HOME:-$HOME/.openclaw}/openclaw.json') as f:
            config = json.load(f)
        token = config['channels']['telegram']['botToken']
    chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
    msg = """$ALERT_MSG"""
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg})
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)
    print("Alert sent to Telegram")
except Exception as e:
    print(f"Alert send failed: {e}")
PYEOF
  else
    echo "Alert suppressed (same failures as last alert, same day)"
  fi
fi

# Send recovery notification when failures clear after a previous alert
if [ "$FAILURES" -eq 0 ] && [ "$ALERT_MODE" = true ] && [ -f "$ALERT_STATE_FILE" ]; then
  PREV_FAILURES=$(python3 -c "
import json
try:
    s = json.load(open('$ALERT_STATE_FILE'))
    print(s.get('failures', 0))
except: print(0)
" 2>/dev/null)
  if [ "$PREV_FAILURES" -gt 0 ]; then
    python3 << PYEOF
import json, urllib.request, urllib.parse, os
try:
    token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
    if not token:
        with open(os.path.expanduser('~/.openclaw/openclaw.json')) as f:
            config = json.load(f)
        token = config['channels']['telegram']['botToken']
    chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
    msg = "✅ Cron Watchdog: All jobs recovered. No failures detected."
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg})
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)
    print("Recovery notification sent to Telegram")
except Exception as e:
    print(f"Recovery notification failed: {e}")
PYEOF
    # Reset state
    python3 -c "
import json
state = {'failure_hash': '', 'date': '$(date -u +%Y-%m-%d)', 'failures': 0, 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%S)'}
json.dump(state, open('$ALERT_STATE_FILE', 'w'), indent=2)
" 2>/dev/null
  fi
fi

exit $FAILURES

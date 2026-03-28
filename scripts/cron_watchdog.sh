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

source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOG_DIR="/home/agent/.openclaw/workspace/memory/cron"
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
check_job "health_monitor"  "/home/agent/.openclaw/workspace/monitoring/health.log" 1  # every 15m, grace 45m
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
WM_FILE="/home/agent/.openclaw/workspace/data/attention/spotlight.json"
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
            python3 /home/agent/.openclaw/workspace/scripts/attention.py add "System watchdog: working memory was empty, seeded" 0.6 >> "$WATCHDOG_LOG" 2>&1
            python3 /home/agent/.openclaw/workspace/scripts/attention.py add "Active evolution: $(date -u +%Y-%m-%d) heartbeat cycle running" 0.5 >> "$WATCHDOG_LOG" 2>&1
            REPORT="${REPORT}REPAIR  working_memory — seeded 2 items to prevent empty state\n"
        fi
    else
        REPORT="${REPORT}OK      working_memory — ${WM_ACTIVE} active items\n"
    fi
else
    REPORT="${REPORT}MISSED  working_memory — spotlight.json missing\n"
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
  DOCTOR_SCRIPT="/home/agent/.openclaw/workspace/scripts/cron_doctor.py"
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
  # Brief pause to let re-runs produce output
  sleep 2
  recheck_job "$LOG_DIR/autonomous.log" 4
  recheck_job "/home/agent/.openclaw/workspace/monitoring/health.log" 1
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

  RECOVERED=$(( FAILURES - STILL_FAILING ))
  echo "------------------------------"
  echo "  Recovery: $RECOVERED/$FAILURES jobs recovered"
  echo "  Still failing: $STILL_FAILING"
  echo "=============================="
  echo "[$TIMESTAMP] Recovery: $RECOVERED/$FAILURES recovered, $STILL_FAILING still failing" >> "$WATCHDOG_LOG"

  FAILURES=$STILL_FAILING
fi

# --- Send alert if failures STILL detected after recovery ---
if [ "$FAILURES" -gt 0 ] && [ "$ALERT_MODE" = true ]; then
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
        with open('/home/agent/.openclaw/openclaw.json') as f:
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
fi

exit $FAILURES

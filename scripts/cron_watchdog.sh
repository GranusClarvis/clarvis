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
check_job "autonomous"      "$LOG_DIR/autonomous.log"      4    # every 3h, grace 1h
check_job "health_monitor"  "/home/agent/.openclaw/workspace/monitoring/health.log" 1  # every 15m, grace 45m
check_job "morning_report"  "$LOG_DIR/report_morning.log"  26   # daily at 10:00, grace 2h
check_job "evening_report"  "$LOG_DIR/report_evening.log"  26   # daily at 22:00, grace 2h
check_job "morning_plan"    "$LOG_DIR/morning.log"          26   # daily at 08:00, grace 2h
check_job "evolution"       "$LOG_DIR/evolution.log"        26   # daily at 13:00, grace 2h
check_job "evening_review"  "$LOG_DIR/evening.log"          26   # daily at 18:00, grace 2h
check_job "reflection"      "$LOG_DIR/reflection.log"       26   # daily at 21:00, grace 2h
check_job "backup"          "$LOG_DIR/backup.log"           26   # daily at 02:00, grace 2h
check_job "backup_verify"   "$LOG_DIR/backup_verify.log"    26   # daily at 02:30, grace 2h

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

$(echo -e "$REPORT" | grep "MISSED")

Recovery log: memory/cron/doctor.log
Watchdog log: memory/cron/watchdog.log"

  python3 << PYEOF
import json, urllib.request, urllib.parse
try:
    with open('/home/agent/.openclaw/openclaw.json') as f:
        config = json.load(f)
    token = config['channels']['telegram']['botToken']
    msg = """$ALERT_MSG"""
    data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": msg})
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)
    print("Alert sent to Telegram")
except Exception as e:
    print(f"Alert send failed: {e}")
PYEOF
fi

exit $FAILURES

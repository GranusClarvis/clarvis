#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
cd /home/agent/.openclaw/workspace
LOGFILE="memory/cron_evening.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"

# === DAILY CAPABILITY ASSESSMENT ===
# Run self_model.py daily update — scores all capabilities, tracks diffs, alerts on degradation
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running daily capability assessment..." >> "$LOGFILE"
ASSESSMENT_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/self_model.py daily 2>&1)
ASSESSMENT_EXIT=$?
echo "$ASSESSMENT_OUTPUT" >> "$LOGFILE"

if [ $ASSESSMENT_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Capability assessment failed (exit $ASSESSMENT_EXIT)" >> "$LOGFILE"
fi

# Check for alerts in the output (capability below threshold)
if echo "$ASSESSMENT_OUTPUT" | grep -q "ALERT:"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] !!! CAPABILITY ALERTS DETECTED — see assessment above !!!" >> "$LOGFILE"
fi

# === EXISTING: Claude Code evening audit ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running evening audit..." >> "$LOGFILE"
/home/agent/.local/bin/claude -p "Review today's work: check git status, memory/$(date +%Y-%m-%d).md, any errors in logs. What's working? Any bugs? Output: brief audit + 1 fix if needed." --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

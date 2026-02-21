#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron_evening.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"

# === PHI METRIC RECORDING ===
# Record phi metric snapshot — non-blocking, failures won't abort the rest of the cron
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording phi metric..." >> "$LOGFILE"
PHI_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/phi_metric.py record 2>&1) || true
PHI_EXIT=$?
echo "$PHI_OUTPUT" >> "$LOGFILE"

if [ $PHI_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Phi metric recording failed (exit $PHI_EXIT) — continuing anyway" >> "$LOGFILE"
fi

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

# === RETRIEVAL QUALITY REPORT ===
# Generate 7-day retrieval quality report — non-blocking
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Generating retrieval quality report..." >> "$LOGFILE"
RQ_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/retrieval_quality.py report 7 2>&1) || true
RQ_EXIT=$?
echo "$RQ_OUTPUT" >> "$LOGFILE"

if [ $RQ_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval quality report failed (exit $RQ_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === EXISTING: Claude Code evening audit ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running evening audit..." >> "$LOGFILE"
/home/agent/.local/bin/claude -p "Review today's work: check git status, memory/$(date +%Y-%m-%d).md, any errors in logs. What's working? Any bugs? Output: brief audit + 1 fix if needed." --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

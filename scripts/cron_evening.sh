#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/evening.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"

# === PHI METRIC: RECORD AND ACT ===
# Record phi metric AND act on it: drops trigger cross-linking, rises log positive episodes
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording phi metric and acting on changes..." >> "$LOGFILE"
PHI_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/phi_metric.py act 2>&1) || true
PHI_EXIT=$?
echo "$PHI_OUTPUT" >> "$LOGFILE"

if [ $PHI_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Phi metric act failed (exit $PHI_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === DAILY CAPABILITY ASSESSMENT + AUTO-REMEDIATION ===
# Run self_model.py daily update — scores capabilities, tracks diffs, alerts on degradation
# NEW: domains below 0.4 auto-generate P0 remediation tasks in QUEUE.md (sense-assess-act loop)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running daily capability assessment (with auto-remediation)..." >> "$LOGFILE"
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

# Check for remediation tasks generated
if echo "$ASSESSMENT_OUTPUT" | grep -q "REMEDIATION:"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SELF-IMPROVEMENT: Remediation tasks auto-generated for weak domains" >> "$LOGFILE"
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

# === RETRIEVAL BENCHMARK: Ground-truth precision@3 and recall ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running retrieval benchmark (20 ground-truth queries)..." >> "$LOGFILE"
BENCH_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/retrieval_benchmark.py run 2>&1) || true
BENCH_EXIT=$?
echo "$BENCH_OUTPUT" >> "$LOGFILE"

if [ $BENCH_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval benchmark failed (exit $BENCH_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === SELF-REPORT: Cognitive growth tracking ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running self-report assessment..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/self_report.py >> "$LOGFILE" 2>&1 || true

# === DASHBOARD: Regenerate monitoring dashboard ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Regenerating dashboard..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/dashboard.py >> "$LOGFILE" 2>&1 || true

# === EXISTING: Claude Code evening audit ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running evening audit..." >> "$LOGFILE"
/home/agent/.local/bin/claude -p "Review today's work: check git status, memory/$(date +%Y-%m-%d).md, any errors in logs. What's working? Any bugs? Output: brief audit + 1 fix if needed." --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

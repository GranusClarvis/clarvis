#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/evening.log"
LOCKFILE="/tmp/clarvis_evening.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)" >> "$LOGFILE"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

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

# === CODE QUALITY GATE: AST + pyflakes audit, auto-fix unused imports ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running code quality gate (fix mode)..." >> "$LOGFILE"
CQ_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/code_quality_gate.py fix 2>&1) || true
echo "$CQ_OUTPUT" >> "$LOGFILE"

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
EVENING_PROMPT_FILE=$(mktemp)
cat > "$EVENING_PROMPT_FILE" << 'ENDPROMPT'
Review today's work: check git status, recent memory files, any errors in logs.
What's working? Any bugs? Output: brief audit + 1 fix if needed.
ENDPROMPT
timeout 600 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    /home/agent/.local/bin/claude -p "$(cat "$EVENING_PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 >> "$LOGFILE" 2>&1
rm -f "$EVENING_PROMPT_FILE"

# === DIGEST: Write first-person summary for M2.5 agent ===
PHI_DIGEST=$(echo "$PHI_OUTPUT" | grep -oP 'Phi\s*=\s*[\d.]+' | head -1 || echo "Phi not measured")
ASSESSMENT_DIGEST=$(echo "$ASSESSMENT_OUTPUT" | grep -oP '^\s+\S.*:\s[\d.]+' | head -7 | tr '\n' '; ' || echo "assessment unavailable")
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py evening \
    "Evening assessment complete. $PHI_DIGEST. Capability scores: $ASSESSMENT_DIGEST. Ran retrieval benchmark, self-report, and dashboard regeneration. Evening code audit done." \
    >> "$LOGFILE" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

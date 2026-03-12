#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
LOGFILE="memory/cron/evening.log"

# Acquire locks: local + global Claude
acquire_local_lock "/tmp/clarvis_evening.lock" "$LOGFILE"
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Evening assessment" --section cron_evening --executor claude-opus

# === PHI METRIC: RECORD AND ACT ===
# Record phi metric AND act on it: drops trigger cross-linking, rises log positive episodes
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording phi metric and acting on changes..." >> "$LOGFILE"
PHI_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/phi_metric.py act 2>&1)
PHI_EXIT=$?
echo "$PHI_OUTPUT" >> "$LOGFILE"

if [ "$PHI_EXIT" -ne 0 ]; then
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

if [ "$ASSESSMENT_EXIT" -ne 0 ]; then
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
RQ_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/retrieval_quality.py report 7 2>&1)
RQ_EXIT=$?
echo "$RQ_OUTPUT" >> "$LOGFILE"

if [ "$RQ_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval quality report failed (exit $RQ_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === RETRIEVAL BENCHMARK: Ground-truth precision@3 and recall ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running retrieval benchmark (20 ground-truth queries)..." >> "$LOGFILE"
BENCH_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/retrieval_benchmark.py run 2>&1)
BENCH_EXIT=$?
echo "$BENCH_OUTPUT" >> "$LOGFILE"

if [ "$BENCH_EXIT" -ne 0 ]; then
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
WEAKEST_METRIC=$(get_weakest_metric)
EVENING_PROMPT_FILE=$(mktemp)
cat > "$EVENING_PROMPT_FILE" << ENDPROMPT
You are Clarvis's evening auditor.
QUEUE: Check memory/evolution/QUEUE.md — note any stale or blocked tasks.
WEAKEST METRIC: $WEAKEST_METRIC — flag if today's work helped or hurt this.

STEPS:
1. Run git status + git log --oneline -10 to see today's changes.
2. Scan memory/cron/*.log for errors (grep -i 'error\|fail\|warn' in last 100 lines).
3. If a bug is found, fix it (1 fix max). If no bugs, skip.

OUTPUT FORMAT (mandatory): "AUDIT: pass|issues_found — <1 sentence>. FIXES: <count>. METRIC_IMPACT: improved|neutral|degraded."
ENDPROMPT
timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    /home/agent/.local/bin/claude -p "$(cat "$EVENING_PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 >> "$LOGFILE" 2>&1
rm -f "$EVENING_PROMPT_FILE"

# === DIGEST: Write first-person summary for M2.5 agent ===
PHI_DIGEST=$(echo "$PHI_OUTPUT" | grep -oP 'Phi\s*=\s*[\d.]+' | head -1 || echo "Phi not measured")
ASSESSMENT_DIGEST=$(echo "$ASSESSMENT_OUTPUT" | grep -oP '^\s+\S.*:\s[\d.]+' | head -7 | tr '\n' '; ' || echo "assessment unavailable")
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py evening \
    "Evening assessment complete. $PHI_DIGEST. Capability scores: $ASSESSMENT_DIGEST. Ran retrieval benchmark, self-report, and dashboard regeneration. Evening code audit done." \
    >> "$LOGFILE" 2>&1 || true

# === DAILY MEMORY LOG: Generate memory/YYYY-MM-DD.md from digest ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Generating daily memory log..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/daily_memory_log.py >> "$LOGFILE" 2>&1 || true

emit_dashboard_event task_completed --task-name "Evening assessment" --section cron_evening --status success
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

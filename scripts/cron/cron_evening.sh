#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source /home/agent/.openclaw/workspace/scripts/cron/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/cron/lock_helper.sh
LOGFILE="memory/cron/evening.log"

# Acquire local lock only during Python assessment phase.
# Global Claude lock is acquired later, just before Claude Code spawn (line ~100).
# Previously held global lock for 2+ hours while running non-Claude Python work,
# which blocked autonomous runs unnecessarily. Fixed 2026-03-15 per cron schedule audit.
acquire_local_lock "/tmp/clarvis_evening.lock" "$LOGFILE" 3600

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Evening assessment" --section cron_evening --executor claude-opus

# === PHI METRIC: RECORD AND ACT ===
# Record phi metric AND act on it: drops trigger cross-linking, rises log positive episodes
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording phi metric and acting on changes..." >> "$LOGFILE"
PHI_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/metrics/phi_metric.py act 2>&1)
PHI_EXIT=$?
echo "$PHI_OUTPUT" >> "$LOGFILE"

if [ "$PHI_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Phi metric act failed (exit $PHI_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === DAILY CAPABILITY ASSESSMENT + AUTO-REMEDIATION ===
# Run self_model.py daily update — scores capabilities, tracks diffs, alerts on degradation
# NEW: domains below 0.4 auto-generate P0 remediation tasks in QUEUE.md (sense-assess-act loop)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running daily capability assessment (with auto-remediation)..." >> "$LOGFILE"
ASSESSMENT_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/metrics/self_model.py daily 2>&1)
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
RQ_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/brain_mem/retrieval_quality.py report 7 2>&1)
RQ_EXIT=$?
echo "$RQ_OUTPUT" >> "$LOGFILE"

if [ "$RQ_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval quality report failed (exit $RQ_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === RETRIEVAL BENCHMARK: Ground-truth precision@3 and recall ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running retrieval benchmark (20 ground-truth queries)..." >> "$LOGFILE"
BENCH_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/brain_mem/retrieval_benchmark.py run 2>&1)
BENCH_EXIT=$?
echo "$BENCH_OUTPUT" >> "$LOGFILE"

if [ "$BENCH_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval benchmark failed (exit $BENCH_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === SELF-REPORT: Cognitive growth tracking ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running self-report assessment..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/metrics/self_report.py >> "$LOGFILE" 2>&1 || true

# === DASHBOARD: Regenerate monitoring dashboard ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Regenerating dashboard..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/metrics/dashboard.py >> "$LOGFILE" 2>&1 || true

# === EXISTING: Claude Code evening audit ===
# Try to acquire global Claude lock — if held, skip audit but continue to digest
AUDIT_SKIPPED=""
if [ -f "$GLOBAL_LOCK" ]; then
    _gpid=$(cat "$GLOBAL_LOCK" 2>/dev/null)
    _glock_age=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
    if [ -n "$_gpid" ] && _is_clarvis_process "$_gpid" && [ "$_glock_age" -le 2400 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Evening audit SKIPPED: Claude lock held (PID $_gpid, age=${_glock_age}s)" >> "$LOGFILE"
        AUDIT_SKIPPED="true"
    fi
fi

if [ -z "$AUDIT_SKIPPED" ]; then
    # Acquire lock (handles stale reclaim) — exits only if truly contested
    acquire_global_claude_lock "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running evening audit..." >> "$LOGFILE"
    WEAKEST_METRIC=$(get_weakest_metric)
    EVENING_PROMPT_FILE=$(mktemp)
    {
        cat <<'STATIC'
You are Clarvis's evening auditor.
QUEUE: Check memory/evolution/QUEUE.md — note any stale or blocked tasks.
STATIC
        printf 'WEAKEST METRIC: %s — flag if today'\''s work helped or hurt this.\n\n' "$WEAKEST_METRIC"
        cat <<'STATIC2'
STEPS:
1. Run git status + git log --oneline -10 to see today's changes.
2. Scan memory/cron/*.log for errors (grep -i 'error\|fail\|warn' in last 100 lines).
3. If a bug is found, fix it (1 fix max). If no bugs, skip.

OUTPUT FORMAT (mandatory): "AUDIT: pass|issues_found — <1 sentence>. FIXES: <count>. METRIC_IMPACT: improved|neutral|degraded."
STATIC2
    } > "$EVENING_PROMPT_FILE"
    timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        /home/agent/.local/bin/claude -p \
        --dangerously-skip-permissions --model claude-opus-4-6 \
        < "$EVENING_PROMPT_FILE" >> "$LOGFILE" 2>&1
    rm -f "$EVENING_PROMPT_FILE"
fi

# === DIGEST: Write first-person summary for M2.5 agent ===
PHI_DIGEST=$(echo "$PHI_OUTPUT" | grep -oP 'Phi\s*=\s*[\d.]+' | head -1 || echo "Phi not measured")
ASSESSMENT_DIGEST=$(echo "$ASSESSMENT_OUTPUT" | grep -oP '^\s+\S.*:\s[\d.]+' | head -7 | tr '\n' '; ' || echo "assessment unavailable")
python3 /home/agent/.openclaw/workspace/scripts/tools/digest_writer.py evening \
    "Evening assessment complete. $PHI_DIGEST. Capability scores: $ASSESSMENT_DIGEST. Ran retrieval benchmark, self-report, and dashboard regeneration. Evening code audit ${AUDIT_SKIPPED:+skipped (lock held)}${AUDIT_SKIPPED:-done}." \
    >> "$LOGFILE" 2>&1 || true

# === DAILY MEMORY LOG: Generate memory/YYYY-MM-DD.md from digest ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Generating daily memory log..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/tools/daily_memory_log.py >> "$LOGFILE" 2>&1 || true

emit_dashboard_event task_completed --task-name "Evening assessment" --section cron_evening --status success
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

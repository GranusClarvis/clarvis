#!/bin/bash
# Evening code review - audit today's work + daily capability assessment
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
LOGFILE="memory/cron/evening.log"

# Acquire local lock only during Python assessment phase.
# Global Claude lock is acquired later, just before Claude Code spawn (line ~100).
# Previously held global lock for 2+ hours while running non-Claude Python work,
# which blocked autonomous runs unnecessarily. Fixed 2026-03-15 per cron schedule audit.
acquire_local_lock "/tmp/clarvis_evening.lock" "$LOGFILE" 3600

sync_workspace 2>> "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Evening assessment" --section cron_evening --executor claude-opus

# === PHI METRIC: RECORD AND ACT ===
# Record phi metric AND act on it: drops trigger cross-linking, rises log positive episodes
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording phi metric and acting on changes..." >> "$LOGFILE"
PHI_OUTPUT=$(python3 -c "
from clarvis.metrics.phi import record_phi, act_on_phi
r = record_phi()
a = act_on_phi(r)
print(f'Phi={r[\"phi\"]:.4f}')
for action in a['actions']:
    print(f'  {action}')
" 2>&1)
PHI_EXIT=$?
echo "$PHI_OUTPUT" >> "$LOGFILE"

if [ "$PHI_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Phi metric act failed (exit $PHI_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === DAILY CAPABILITY ASSESSMENT + AUTO-REMEDIATION ===
# Run self_model.py daily update — scores capabilities, tracks diffs, alerts on degradation
# NEW: domains below 0.4 auto-generate P0 remediation tasks in QUEUE.md (sense-assess-act loop)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running daily capability assessment (with auto-remediation)..." >> "$LOGFILE"
ASSESSMENT_OUTPUT=$(python3 -c "from clarvis.metrics.self_model import daily_update; daily_update()" 2>&1)
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
RQ_OUTPUT=$(python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/retrieval_quality.py" report 7 2>&1)
RQ_EXIT=$?
echo "$RQ_OUTPUT" >> "$LOGFILE"

if [ "$RQ_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval quality report failed (exit $RQ_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === RETRIEVAL BENCHMARK: Ground-truth precision@3 and recall ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running retrieval benchmark (20 ground-truth queries)..." >> "$LOGFILE"
BENCH_OUTPUT=$(python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/retrieval_benchmark.py" run 2>&1)
BENCH_EXIT=$?
echo "$BENCH_OUTPUT" >> "$LOGFILE"

if [ "$BENCH_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Retrieval benchmark failed (exit $BENCH_EXIT) — continuing anyway" >> "$LOGFILE"
fi

# === SELF-REPORT: Cognitive growth tracking ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running self-report assessment..." >> "$LOGFILE"
python3 "$CLARVIS_WORKSPACE/scripts/metrics/self_report.py" >> "$LOGFILE" 2>&1 || true

# === DASHBOARD: Regenerate monitoring dashboard ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Regenerating dashboard..." >> "$LOGFILE"
python3 "$CLARVIS_WORKSPACE/scripts/metrics/dashboard.py" >> "$LOGFILE" 2>&1 || true

# === HEARTBEAT HEALTH: structured outcome analysis (replaces shallow grep) ===
# Parses memory/cron/autonomous.log into per-cycle records and scores recent
# execution rate. Surfaces silent-failure patterns (all_filtered_by_v2,
# repeated no-task, instant-fail clusters) that the old grep audit missed.
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Computing heartbeat health (last 24 cycles)..." >> "$LOGFILE"
HEALTH_REPORT_FILE=$(mktemp --suffix=.txt)
HEALTH_JSON_FILE=$(mktemp --suffix=.json)
python3 -m clarvis.heartbeat.health --window 24 > "$HEALTH_REPORT_FILE" 2>> "$LOGFILE"
HEALTH_TEXT_EXIT=$?
python3 -m clarvis.heartbeat.health --window 24 --json > "$HEALTH_JSON_FILE" 2>> "$LOGFILE" || true
cat "$HEALTH_REPORT_FILE" >> "$LOGFILE"
HEALTH_SEVERITY="ok"
case "$HEALTH_TEXT_EXIT" in
    1) HEALTH_SEVERITY="warn" ;;
    2) HEALTH_SEVERITY="critical" ;;
esac
HEALTH_DIGEST=$(python3 -m clarvis.heartbeat.health --window 24 --digest 2>/dev/null || echo "heartbeat health: unavailable")
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] HEALTH: severity=$HEALTH_SEVERITY — $HEALTH_DIGEST" >> "$LOGFILE"

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
You are Clarvis's evening auditor. Your job is to detect SILENT FAILURES that
the cron pipeline didn't catch — not to grep for the word "error".

The structured heartbeat health report below replaces the old "grep -i error"
sweep. Read it first; the per-cycle outcomes tell you whether the system is
actually executing tasks or skipping them.
STATIC
        printf 'WEAKEST METRIC: %s — flag if today'\''s work helped or hurt this.\n\n' "$WEAKEST_METRIC"
        printf '## HEARTBEAT HEALTH (severity=%s)\n' "$HEALTH_SEVERITY"
        cat "$HEALTH_REPORT_FILE"
        cat <<'STATIC2'

## CHECKLIST (in order)
1. **Execution health.** From the report above, what is `executed_ok` / total?
   - If <50%, the system is mostly idling — explain why (no_task? deferred? crash?).
   - If `consecutive_no_execution >= 3` or severity is CRITICAL, treat as a P0
     incident. Find the root cause: queue selector, project-lane filter, gate
     thresholds, broken preflight. Add a P0 task to QUEUE.md if a fix is needed.
2. **Silent skips.** If `no_task` ≥ 25% of cycles, run:
     python3 -c "from clarvis.queue.engine import QueueEngine, parse_queue; \
                 print('eligible:', len(QueueEngine().ranked_eligible()), \
                       'in_queue:', len(parse_queue()))"
   If `eligible` < `in_queue`, identify which filter is dropping tasks.
3. **Recent commits + workspace.** `git status --short` and `git log --oneline -10`.
   Cross-reference today's commits against what the digest claims happened — any
   gaps suggest tasks marked done in QUEUE.md without actual code changes.
4. **One bounded fix.** If you found a concrete bug in the cron/review stack,
   fix it (≤1 fix, ≤5 files). If no clear bug, do NOT invent one.

## OUTPUT FORMAT (mandatory)
AUDIT: pass|warn|issues_found — <1 sentence diagnosis>.
HEALTH: severity=<ok|warn|critical> exec_rate=<pct> no_task_streak=<n>.
ROOT_CAUSE: <none|single sentence pointing at a specific module/file>.
FIXES: <count> — <files touched, comma-separated, or "none">.
METRIC_IMPACT: improved|neutral|degraded.
STATIC2
    } > "$EVENING_PROMPT_FILE"
    timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        ${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")} -p \
        --dangerously-skip-permissions --model claude-opus-4-7 \
        < "$EVENING_PROMPT_FILE" >> "$LOGFILE" 2>&1
    rm -f "$EVENING_PROMPT_FILE"
fi
rm -f "$HEALTH_REPORT_FILE" "$HEALTH_JSON_FILE"

# === DIGEST: Write first-person summary for M2.5 agent ===
PHI_DIGEST=$(echo "$PHI_OUTPUT" | grep -oP 'Phi\s*=\s*[\d.]+' | head -1)
[ -z "$PHI_DIGEST" ] && PHI_DIGEST="Phi not measured"
ASSESSMENT_DIGEST=$(echo "$ASSESSMENT_OUTPUT" | grep -oP '^\s{2}[A-Z][^:]+:\s[\d.]+' | head -7 | tr '\n' '; ')
[ -z "$ASSESSMENT_DIGEST" ] && ASSESSMENT_DIGEST="assessment unavailable"
python3 "$CLARVIS_WORKSPACE/scripts/tools/digest_writer.py" evening \
    "Evening assessment complete. $PHI_DIGEST. Capability scores: $ASSESSMENT_DIGEST. Ran retrieval benchmark, self-report, and dashboard regeneration. Evening code audit ${AUDIT_SKIPPED:+skipped (lock held)}${AUDIT_SKIPPED:-done}. $HEALTH_DIGEST" \
    >> "$LOGFILE" 2>&1 || true

# === DAILY MEMORY LOG: Generate memory/YYYY-MM-DD.md from digest ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Generating daily memory log..." >> "$LOGFILE"
python3 "$CLARVIS_WORKSPACE/scripts/tools/daily_memory_log.py" >> "$LOGFILE" 2>&1 || true

# Emit truthful status based on critical step exit codes
if [ "${PHI_EXIT:-0}" -eq 0 ] && [ "${ASSESSMENT_EXIT:-0}" -eq 0 ]; then
    emit_dashboard_event task_completed --task-name "Evening assessment" --section cron_evening --status success
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Evening had failures (phi=$PHI_EXIT, assessment=$ASSESSMENT_EXIT)" >> "$LOGFILE"
    emit_dashboard_event task_completed --task-name "Evening assessment" --section cron_evening --status failure
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evening routine complete ===" >> "$LOGFILE"

#!/bin/bash
# =============================================================================
# cron_orchestrator.sh — Daily orchestrator maintenance
# =============================================================================
# Runs project_agent.py promote for each active agent, then runs
# orchestration_benchmark.py and records a scoreboard snapshot.
# No Claude Code spawning — lightweight, runs in ~30-60s.
#
# Crontab: 19:30 daily (after evening 18:00, before reflection 21:00)
#   30 19 * * * /home/agent/.openclaw/workspace/scripts/cron_orchestrator.sh
# =============================================================================

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

SCRIPTS="$CLARVIS_WORKSPACE/scripts"
LOGFILE="memory/cron/orchestrator.log"

# Local lock only — no Claude Code spawned, no global lock needed
acquire_local_lock "/tmp/clarvis_orchestrator.lock" "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Orchestrator maintenance started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Orchestrator daily" --section cron_orchestrator --executor python

# Get list of active agents (parse JSON names)
AGENTS=$(python3 "$SCRIPTS/project_agent.py" list 2>/dev/null | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for a in agents:
    if a.get('tasks', 0) > 0 or a.get('status') != 'idle':
        print(a['name'])
" 2>/dev/null)

# Also include agents with any task history (even if currently idle)
ALL_AGENTS=$(python3 "$SCRIPTS/project_agent.py" list 2>/dev/null | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(a['name'])
" 2>/dev/null)

PROMOTED=0
BENCHMARKED=0
ERRORS=0

# Promote results from all agents (fast — just scans summary files)
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Promoting agent: $agent" >> "$LOGFILE"
    PROMO_OUT=$(python3 "$SCRIPTS/project_agent.py" promote "$agent" 2>&1)
    PROMO_EXIT=$?
    echo "$PROMO_OUT" >> "$LOGFILE"
    if [ $PROMO_EXIT -eq 0 ]; then
        if echo "$PROMO_OUT" | grep -q '"status": "promoted"'; then
            PROMOTED=$((PROMOTED + 1))
        fi
    else
        ERRORS=$((ERRORS + 1))
    fi
done

# Auto-generate golden QA from successful tasks
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Auto golden QA: $agent" >> "$LOGFILE"
    python3 "$SCRIPTS/project_agent.py" auto-qa "$agent" >> "$LOGFILE" 2>&1 || true
done

# Benchmark agents that have task history
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Benchmarking agent: $agent" >> "$LOGFILE"
    BENCH_OUT=$(python3 "$SCRIPTS/orchestration_benchmark.py" run "$agent" 2>&1)
    BENCH_EXIT=$?
    echo "$BENCH_OUT" >> "$LOGFILE"
    if [ $BENCH_EXIT -eq 0 ]; then
        BENCHMARKED=$((BENCHMARKED + 1))
    else
        ERRORS=$((ERRORS + 1))
    fi
done

# Record scoreboard snapshot
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording scoreboard snapshot" >> "$LOGFILE"
python3 "$SCRIPTS/orchestration_scoreboard.py" record >> "$LOGFILE" 2>&1 || true

# Summary
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Orchestrator complete: promoted=$PROMOTED benchmarked=$BENCHMARKED errors=$ERRORS" >> "$LOGFILE"

# Digest entry
python3 "$SCRIPTS/digest_writer.py" autonomous \
    "Orchestrator daily: promoted $PROMOTED agent results, benchmarked $BENCHMARKED agents. Errors: $ERRORS." \
    >> "$LOGFILE" 2>&1 || true

STATUS="success"
[ $ERRORS -gt 0 ] && STATUS="partial"

emit_dashboard_event task_completed --task-name "Orchestrator daily" --section cron_orchestrator --status "$STATUS"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Orchestrator maintenance complete ===" >> "$LOGFILE"

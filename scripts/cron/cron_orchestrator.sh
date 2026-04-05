#!/bin/bash
# =============================================================================
# cron_orchestrator.sh — Daily orchestrator maintenance
# =============================================================================
# Runs project_agent.py promote for each active agent, then runs
# orchestration_benchmark.py and records a scoreboard snapshot.
# No Claude Code spawning — lightweight, runs in ~30-60s.
#
# Crontab: 19:30 daily (after evening 18:00, before reflection 21:00)
#   30 19 * * * $CLARVIS_WORKSPACE/scripts/cron_orchestrator.sh
#
# === Pipeline ===
# 1. Promote: scan each agent's output for results to surface to Clarvis
# 2. Auto QA: generate golden QA pairs from successful tasks (for retrieval benchmarking)
# 3. Benchmark: run orchestration_benchmark.py per agent (5-dim composite score)
# 4. Scoreboard: record JSONL snapshot via orchestration_scoreboard.py
# 5. Digest: write summary line to memory/cron/digest.md
#
# === Lock Behavior ===
# Uses LOCAL lock only (/tmp/clarvis_orchestrator.lock) — no global Claude
# lock needed since this script does not spawn Claude Code. If a previous
# run is still active (same PID alive), the script exits cleanly (exit 0).
# Lock is auto-released on EXIT via lock_helper.sh trap.
#
# === Benchmark Fallback ===
# orchestration_benchmark.py and orchestration_scoreboard.py may not exist
# yet (see QUEUE item ORCH_BENCHMARK_SCRIPTS). When missing, those steps
# fail with exit 1 and increment ERRORS, but the script continues — promote
# and auto-QA still run. This is by design: partial success is better than
# skipping the entire job.
#
# === Error Count Interpretation ===
# ERRORS counts individual step failures across all agents:
#   - promote failure: agent config corrupt or project_agent.py bug
#   - benchmark failure: missing script, agent has no task history, or scoring error
#   - scoreboard failure: missing script or JSONL write error
# ERRORS > 0 → dashboard status = "partial" (not "success")
# The digest line always includes the error count for visibility.
#
# === Troubleshooting ===
# Q: Script runs but PROMOTED=0 even though agents exist
#    → Check `project_agent.py list` output (should be valid JSON array)
#    → Verify agent workspaces exist under /opt/clarvis-agents/<name>/
#
# Q: All benchmarks fail (ERRORS = agent_count)
#    → orchestration_benchmark.py likely missing. Create it or mark
#      ORCH_BENCHMARK_SCRIPTS as P1 in QUEUE.md
#
# Q: Lock file stale / script won't start
#    → Check: cat /tmp/clarvis_orchestrator.lock  →  if PID dead, rm the file
#    → lock_helper.sh auto-detects dead PIDs, so this is rare
#
# Q: "python3: command not found" or import errors
#    → cron_env.sh must set PATH correctly. Verify: bash -x cron_env.sh
# =============================================================================

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

SCRIPTS="$CLARVIS_WORKSPACE/scripts"
LOGFILE="memory/cron/orchestrator.log"

# Local lock only — no Claude Code spawned, no global lock needed
acquire_local_lock "/tmp/clarvis_orchestrator.lock" "$LOGFILE" 3600

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Orchestrator maintenance started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Orchestrator daily" --section cron_orchestrator --executor python

# Get list of all agents
ALL_AGENTS=$(python3 "$SCRIPTS/agents/project_agent.py" list 2>/dev/null | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(a['name'])
" 2>/dev/null)

# Counters — PROMOTED/BENCHMARKED track successes, ERRORS tracks any step failure.
# Final status: "success" if ERRORS=0, "partial" otherwise.
PROMOTED=0
BENCHMARKED=0
ERRORS=0

# --- Stage 1: Promote agent results into Clarvis digest ---
# Each promote call scans the agent's summary files and writes to
# memory/cron/agent_<name>_digest.md. Only increments PROMOTED if
# the output contains '"status": "promoted"' (vs "no_new_results").
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Promoting agent: $agent" >> "$LOGFILE"
    PROMO_OUT=$(python3 "$SCRIPTS/agents/project_agent.py" promote "$agent" 2>&1)
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

# --- Stage 2: Auto-generate golden QA from successful tasks ---
# Creates QA pairs for retrieval benchmarking (P@1, P@3, MRR).
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Auto golden QA: $agent" >> "$LOGFILE"
    python3 "$SCRIPTS/agents/project_agent.py" auto-qa "$agent" >> "$LOGFILE" 2>&1 || true
done

# --- Stage 3: Benchmark each agent (5-dim composite score) ---
# Scores: isolation (0.20), latency (0.20), PR success (0.25),
# retrieval (0.25), cost (0.10). Script may not exist yet — see header.
for agent in $ALL_AGENTS; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Benchmarking agent: $agent" >> "$LOGFILE"
    BENCH_OUT=$(python3 "$SCRIPTS/metrics/orchestration_benchmark.py" run "$agent" 2>&1)
    BENCH_EXIT=$?
    echo "$BENCH_OUT" >> "$LOGFILE"
    if [ $BENCH_EXIT -eq 0 ]; then
        BENCHMARKED=$((BENCHMARKED + 1))
    else
        ERRORS=$((ERRORS + 1))
    fi
done

# --- Stage 4: Record scoreboard snapshot (JSONL) ---
# Appends composite scores to data/orchestration_scoreboard.jsonl.
# Script may not exist yet — `|| true` prevents job abort.
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Recording scoreboard snapshot" >> "$LOGFILE"
python3 "$SCRIPTS/metrics/orchestration_scoreboard.py" record >> "$LOGFILE" 2>&1 || true

# Summary
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Orchestrator complete: promoted=$PROMOTED benchmarked=$BENCHMARKED errors=$ERRORS" >> "$LOGFILE"

# Digest entry
python3 "$SCRIPTS/tools/digest_writer.py" autonomous \
    "Orchestrator daily: promoted $PROMOTED agent results, benchmarked $BENCHMARKED agents. Errors: $ERRORS." \
    >> "$LOGFILE" 2>&1 || true

STATUS="success"
[ $ERRORS -gt 0 ] && STATUS="partial"

emit_dashboard_event task_completed --task-name "Orchestrator daily" --section cron_orchestrator --status "$STATUS"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Orchestrator maintenance complete ===" >> "$LOGFILE"

#!/bin/bash
# Deep evolution thinking with Claude Code (OPTIMIZED)
# KEY: Analyze progress AND write concrete new tasks to QUEUE.md
#
# OPTIMIZATION (2026-02-23): Replaced ~10 individual Python subprocess spawns for
# metrics collection with 1 batched evolution_preflight.py process.
# Savings: ~3s from eliminated cold-starts + reduced disk I/O.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

LOGFILE="memory/cron/evolution.log"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"

# Acquire locks: local + global Claude
acquire_local_lock "/tmp/clarvis_evolution.lock" "$LOGFILE"
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis starting (optimized) ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Evolution analysis" --section cron_evolution --executor claude-opus

# ============================================================================
# BATCHED METRICS COLLECTION (single Python process)
# Replaces: calibration, prediction_review, phi_metric, self_model assess,
#           retrieval_quality, parameter_evolution, confidence apply,
#           episodic stats, routing stats, goal_tracker, context_compressor
# ============================================================================
EVO_PREFLIGHT_FILE=$(mktemp --suffix=.json)
python3 "$SCRIPTS/evolution_preflight.py" > "$EVO_PREFLIGHT_FILE" 2>> "$LOGFILE"
EVO_EXIT=$?

if [ "$EVO_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Evolution preflight failed (exit $EVO_EXIT) — falling back" >> "$LOGFILE"
    # Minimal fallback: just compress context
    COMPRESSED_QUEUE=$(python3 "$SCRIPTS/context_compressor.py" queue 2>> "$LOGFILE")
    COMPRESSED_HEALTH=""
    PENDING_COUNT=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
else
    # Parse all results in a single python invocation
    eval $(python3 -c "
import json, shlex
with open('$EVO_PREFLIGHT_FILE') as f:
    d = json.load(f)
print(f'COMPRESSED_QUEUE={shlex.quote(str(d.get(\"compressed_queue\", \"\")))}')
print(f'COMPRESSED_HEALTH={shlex.quote(str(d.get(\"compressed_health\", \"\")))}')
print(f'PENDING_COUNT={shlex.quote(str(d.get(\"pending_count\", 0)))}')
t = d.get('timings', {})
print(f'EVO_PF_TIME={shlex.quote(str(t.get(\"total\", \"?\")))}')
# Extract key metrics for digest
print(f'PHI_SHORT={shlex.quote(str(d.get(\"phi_trend\", \"Phi unknown\"))[:100])}')
print(f'WEAKEST={shlex.quote(str(d.get(\"capabilities\", \"unknown\"))[:100])}')
print(f'CALIBRATION_SHORT={shlex.quote(str(d.get(\"calibration\", \"\"))[:100])}')
" 2>> "$LOGFILE")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PREFLIGHT: Collected all metrics in ${EVO_PF_TIME}s" >> "$LOGFILE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CONTEXT: compressed_queue=${#COMPRESSED_QUEUE}b health=${#COMPRESSED_HEALTH}b" >> "$LOGFILE"

# ============================================================================
# CLAUDE CODE ANALYSIS (the actual expensive part — this is the core work)
# ============================================================================
WEAKEST_METRIC=$(get_weakest_metric)
EVO_PROMPT_FILE=$(mktemp)
cat > "$EVO_PROMPT_FILE" << ENDPROMPT
You are Clarvis's strategic evolution engine.

QUEUE: Read memory/evolution/QUEUE.md — the authoritative task backlog.
WEAKEST METRIC: $WEAKEST_METRIC — at least one new task MUST target this.

STEPS:
1. Review the compressed queue below — what's pending ($PENDING_COUNT items)?
2. Check data/plans/, skills/, HEARTBEAT.md, ROADMAP.md for gaps.
3. Assess Phi trend and capability scores from health data below.

ACTION (MANDATORY if <5 pending tasks):
- Add 3-5 NEW tasks to QUEUE.md under '## NEW ITEMS'.
- Format: - [ ] <concrete, actionable task>
- At least 1 task targeting the weakest metric. At least 1 non-Python task.

$COMPRESSED_QUEUE

$COMPRESSED_HEALTH

OUTPUT FORMAT (mandatory): Start with "ANALYSIS: <1-sentence verdict>". Then "TASKS ADDED: <count>". Then list each task.
ENDPROMPT

timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    /home/agent/.local/bin/claude -p "$(cat "$EVO_PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 >> "$LOGFILE" 2>&1
rm -f "$EVO_PROMPT_FILE"

# ============================================================================
# DIGEST (lightweight — single subprocess)
# ============================================================================
python3 "$SCRIPTS/digest_writer.py" evolution \
    "Deep evolution analysis complete. ${PHI_SHORT:-Phi unknown}. Weakest: ${WEAKEST:-unknown}. $PENDING_COUNT tasks pending. Calibration: ${CALIBRATION_SHORT:-unknown}." \
    >> "$LOGFILE" 2>&1 || true

# Cleanup
rm -f "$EVO_PREFLIGHT_FILE"

emit_dashboard_event task_completed --task-name "Evolution analysis" --section cron_evolution --status success
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis complete ===" >> "$LOGFILE"

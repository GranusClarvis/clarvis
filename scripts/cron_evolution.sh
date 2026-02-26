#!/bin/bash
# Deep evolution thinking with Claude Code (OPTIMIZED)
# KEY: Analyze progress AND write concrete new tasks to QUEUE.md
#
# OPTIMIZATION (2026-02-23): Replaced ~10 individual Python subprocess spawns for
# metrics collection with 1 batched evolution_preflight.py process.
# Savings: ~3s from eliminated cold-starts + reduced disk I/O.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/evolution.log"
LOCKFILE="/tmp/clarvis_evolution.lock"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"

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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis starting (optimized) ===" >> "$LOGFILE"

# ============================================================================
# BATCHED METRICS COLLECTION (single Python process)
# Replaces: calibration, prediction_review, phi_metric, self_model assess,
#           retrieval_quality, parameter_evolution, confidence apply,
#           episodic stats, routing stats, goal_tracker, context_compressor
# ============================================================================
EVO_PREFLIGHT_FILE=$(mktemp --suffix=.json)
python3 "$SCRIPTS/evolution_preflight.py" > "$EVO_PREFLIGHT_FILE" 2>> "$LOGFILE"
EVO_EXIT=$?

if [ $EVO_EXIT -ne 0 ]; then
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
/home/agent/.local/bin/claude -p \
    "You are Clarvis's strategic evolution engine. Do a deep analysis:

    1. Review the compressed queue below — what's pending?
    2. Read the recent memory file (memory/$(date +%Y-%m-%d).md) — what happened today?
    3. Check data/plans/ — any unfinished research or ideas?
    4. Review skills/ — any missing skills that would help M2.5 or the subconscious?
    5. Check HEARTBEAT.md, ROADMAP.md — are protocols and phase assessments current?
    6. Consider non-code improvements: config tuning, prompt engineering, cron schedule optimization, skill creation.

    $COMPRESSED_QUEUE

    $COMPRESSED_HEALTH

    ANALYSIS:
    - What's working well in the evolution toward AGI/consciousness?
    - What's the biggest bottleneck based on the capability scores?
    - Which capability has the LOWEST score? Design a task to improve it.
    - How is Phi trending? What would increase information integration?

    ACTION (MANDATORY):
    - If there are fewer than 5 pending tasks in QUEUE.md, ADD 3-5 new ones.
    - Add them under '## NEW ITEMS' for urgent ones, '## Cost Efficiency' for optimization.
    - Format: - [ ] <concrete, actionable task>
    - Prioritize fixing the LOWEST capability score. Then: integration, feedback loops,
      consciousness metrics, and genuine cognitive capabilities.
    - Include at least ONE non-Python task (config tune, protocol update, skill creation,
      prompt improvement, architectural simplification, or cron optimization).
    - Available runtimes: Python 3, Node.js, Bash. Can install Rust/Go/etc. Use the right tool for the job.

    Currently $PENDING_COUNT pending tasks in queue.
    Output: 1-paragraph analysis + list of tasks added." \
    --dangerously-skip-permissions >> "$LOGFILE" 2>&1

# ============================================================================
# DIGEST (lightweight — single subprocess)
# ============================================================================
python3 "$SCRIPTS/digest_writer.py" evolution \
    "Deep evolution analysis complete. ${PHI_SHORT:-Phi unknown}. Weakest: ${WEAKEST:-unknown}. $PENDING_COUNT tasks pending. Calibration: ${CALIBRATION_SHORT:-unknown}." \
    >> "$LOGFILE" 2>&1 || true

# Cleanup
rm -f "$EVO_PREFLIGHT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis complete ===" >> "$LOGFILE"

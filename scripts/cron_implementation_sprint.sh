#!/bin/bash
# =============================================================================
# Implementation Sprint — Dedicated implementation execution slot
# =============================================================================
# Runs 1x/day at 14:00 CET (freed from cron_research_discovery.sh)
# Picks ONE implementation task from QUEUE.md (skips research tasks).
# Prioritizes P0 > P1 > Pillar tasks > Backlog.
# Uses the full heartbeat pipeline (preflight → Claude Code → postflight)
# so episodes, reasoning chains, and metrics are properly recorded.
# =============================================================================

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
LOGFILE="memory/cron/implementation_sprint.log"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"
QUEUE_FILE="memory/evolution/QUEUE.md"

# Prevent nested Claude sessions
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Acquire locks: local (with stale detection) + global Claude (queue on conflict)
acquire_local_lock "/tmp/clarvis_implementation_sprint.lock" "$LOGFILE" 2400
acquire_global_claude_lock "$LOGFILE" "queue"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Implementation Sprint starting ===" >> "$LOGFILE"

# Extract the FIRST unchecked IMPLEMENTATION task from QUEUE.md
# Skips research tasks (Research:, Bundle, study, paper, investigate, explore)
IMPL_TASK=$(python3 -c "
import re
with open('$QUEUE_FILE') as f:
    content = f.read()

lines = content.split('\n')
found = None

# Research markers to SKIP
research_markers = ['research:', 'bundle ', 'study ', 'paper ', 'explore ', 'investigate ']

for line in lines:
    stripped = line.strip()
    # Match unchecked items
    if re.match(r'^-\s*\[\s*\]', stripped):
        task = re.sub(r'^-\s*\[\s*\]\s*', '', stripped)
        # Strip auto-generated source tags
        task = re.sub(r'^\[[A-Z_]+\s+\d{4}-\d{2}-\d{2}\]\s*', '', task)
        task_lower = task.lower()
        # Skip research tasks
        if any(marker in task_lower for marker in research_markers):
            continue
        found = task
        break

if found:
    print(found)
" 2>> "$LOGFILE")

if [ -z "$IMPL_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No pending implementation tasks in QUEUE.md" >> "$LOGFILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SPRINT TASK: ${IMPL_TASK:0:120}" >> "$LOGFILE"

# Use the heartbeat pipeline for proper episode/metrics tracking
# Run preflight to get context, chain_id, episodic hints, etc.
PREFLIGHT_FILE=$(mktemp --suffix=.json)
python3 "$SCRIPTS/heartbeat_preflight.py" > "$PREFLIGHT_FILE" 2>> "$LOGFILE"
PREFLIGHT_EXIT=$?

# Extract context even if preflight had issues
CONTEXT_BRIEF=""
EPISODIC_HINTS=""
PROC_HINT=""
if [ $PREFLIGHT_EXIT -eq 0 ]; then
    # Strip non-JSON lines
    python3 -c "
import json, sys
with open('$PREFLIGHT_FILE') as f:
    lines = f.readlines()
json_lines = [l for l in lines if l.strip().startswith('{')]
if json_lines:
    with open('$PREFLIGHT_FILE', 'w') as f:
        f.write(json_lines[-1])
" 2>> "$LOGFILE"

    eval $(python3 -c "
import json, sys, shlex
with open('$PREFLIGHT_FILE') as f:
    d = json.load(f)
print(f'CONTEXT_BRIEF={shlex.quote(d.get(\"context_brief\", \"\"))}')
print(f'EPISODIC_HINTS={shlex.quote(d.get(\"episodic_hints\", \"\"))}')
proc = d.get('procedure')
if proc and proc.get('steps'):
    steps = proc['steps']
    steps_text = chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(steps))
    rate = f\"{proc.get('success_rate', 0):.0%}\"
    hint = f'PROCEDURAL MEMORY HIT (success rate: {rate}). Suggested steps:{chr(10)}{steps_text}'
    print(f'PROC_HINT={shlex.quote(hint)}')
else:
    print(\"PROC_HINT=''\")
" 2>> "$LOGFILE")
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Preflight failed (exit $PREFLIGHT_EXIT), running without context" >> "$LOGFILE"
    CONTEXT_BRIEF=$(python3 "$SCRIPTS/context_compressor.py" brief 2>> "$LOGFILE")
fi

# Build and execute prompt
TASK_OUTPUT_FILE=$(mktemp)
TASK_START=$SECONDS
PROMPT_FILE=$(mktemp --suffix=.txt)

cat > "$PROMPT_FILE" << ENDPROMPT
You are Clarvis's executive function running an IMPLEMENTATION SPRINT.

TIME BUDGET: You have ~25 minutes. Focus on completing this task fully.
AVOID THESE FAILURE PATTERNS:
- AVOID: [shallow_reasoning] Multi-step tasks need multi-step reasoning
- AVOID: [long_duration] Stay focused, complete the smallest viable increment

${CONTEXT_BRIEF:+CONTEXT:
$CONTEXT_BRIEF}

${EPISODIC_HINTS:+EPISODIC HINTS:
$EPISODIC_HINTS}

${PROC_HINT:+$PROC_HINT}

TASK: $IMPL_TASK

INSTRUCTIONS:
- This is a DEDICATED IMPLEMENTATION slot — focus on writing code, editing configs, updating protocols.
- Do the work. Be concrete. Test your changes.
- If the task is too large, do the most impactful part and note what remains.
- When done, output a summary listing what you did, comma-separated.
ENDPROMPT

timeout 1500 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \
    "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 \
    > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?
TASK_DURATION=$((SECONDS - TASK_START))
rm -f "$PROMPT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SPRINT EXECUTION: exit=$TASK_EXIT duration=${TASK_DURATION}s" >> "$LOGFILE"
tail -c 2000 "$TASK_OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

# Run postflight for episode recording and metrics
if [ $PREFLIGHT_EXIT -eq 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running postflight..." >> "$LOGFILE"
    python3 "$SCRIPTS/heartbeat_postflight.py" "$TASK_EXIT" "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE" "$TASK_DURATION" >> "$LOGFILE" 2>&1
fi

# Update digest
SUMMARY=$(tail -c 500 "$TASK_OUTPUT_FILE" 2>/dev/null | tail -5)
{
    echo ""
    echo "### Implementation Sprint — $(date -u +%H:%M) UTC"
    echo ""
    if [ $TASK_EXIT -eq 0 ]; then
        echo "Sprint task: ${IMPL_TASK:0:100}. Result: success (${TASK_DURATION}s). Summary: ${SUMMARY:0:200}"
    else
        echo "Sprint FAILED: ${IMPL_TASK:0:100}. Exit=$TASK_EXIT (${TASK_DURATION}s)."
    fi
    echo ""
    echo "---"
    echo ""
} >> "memory/cron/digest.md"

# Log cost estimate
python3 -c "
import sys, os
sys.path.insert(0, os.path.join('$SCRIPTS', '..', 'packages', 'clarvis-cost'))
try:
    from clarvis_cost.core import CostTracker
    COST_LOG = os.path.join('$SCRIPTS', '..', 'data', 'costs.jsonl')
    ct = CostTracker(COST_LOG)
    duration_min = max(1, $TASK_DURATION // 60)
    ct.log('claude-code', 5000 * duration_min, 2000 * duration_min,
           source='implementation_sprint', task='implementation', duration_s=$TASK_DURATION)
    print('Cost logged')
except Exception as e:
    print(f'Cost log failed: {e}', file=sys.stderr)
" >> "$LOGFILE" 2>&1

rm -f "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Implementation Sprint complete (${TASK_DURATION}s) ===" >> "$LOGFILE"

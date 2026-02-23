#!/bin/bash
# Autonomous Evolution Loop — Clarvis Executive Function (OPTIMIZED)
# Runs 6x/day at hours 7,10,13,16,19,22.
#
# OPTIMIZATION (2026-02-23): Replaced ~25 individual Python subprocess spawns
# with 2 batched Python processes (heartbeat_preflight.py + heartbeat_postflight.py).
# Savings: ~7-8s per heartbeat from eliminated cold-starts + reduced disk I/O.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/autonomous.log"
LOCKFILE="/tmp/clarvis_autonomous.lock"
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

# ============================================================================
# PHASE 1: BATCHED PRE-FLIGHT (single Python process)
# Replaces: attention load/tick, task_selector, cognitive_load, procedural_memory,
#           reasoning_chain open, confidence predict, episodic recall,
#           context_compressor, task_router — all in ONE import + execution.
# ============================================================================
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Heartbeat starting (optimized batched pipeline) ===" >> "$LOGFILE"

PREFLIGHT_FILE=$(mktemp --suffix=.json)
python3 "$SCRIPTS/heartbeat_preflight.py" > "$PREFLIGHT_FILE" 2>> "$LOGFILE"
PREFLIGHT_EXIT=$?

if [ $PREFLIGHT_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Preflight failed (exit $PREFLIGHT_EXIT)" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 1
fi

# Parse preflight results (single jq-like parse via python — 1 invocation for all fields)
# Safety: strip any non-JSON lines that leaked to stdout from imported modules
python3 -c "
import json, sys
with open('$PREFLIGHT_FILE') as f:
    lines = f.readlines()
# Find the JSON line (starts with '{')
json_lines = [l for l in lines if l.strip().startswith('{')]
if not json_lines:
    print('ERROR: No JSON found in preflight output', file=sys.stderr)
    sys.exit(1)
with open('$PREFLIGHT_FILE', 'w') as f:
    f.write(json_lines[-1])
" 2>> "$LOGFILE"

if [ $? -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ERROR: Preflight output contained no valid JSON" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 1
fi

eval $(python3 -c "
import json, sys, shlex
with open('$PREFLIGHT_FILE') as f:
    d = json.load(f)
status = d.get('status', 'error')
print(f'PF_STATUS={shlex.quote(status)}')
print(f'NEXT_TASK={shlex.quote(d.get(\"task\", \"\"))}')
print(f'TASK_SECTION={shlex.quote(d.get(\"task_section\", \"P1\"))}')
print(f'BEST_SALIENCE={shlex.quote(str(d.get(\"task_salience\", 0.0)))}')
print(f'SHOULD_DEFER={shlex.quote(str(d.get(\"should_defer\", False)).lower())}')
print(f'CHAIN_ID={shlex.quote(d.get(\"chain_id\", \"\") or \"\")}')
print(f'PROC_ID={shlex.quote(d.get(\"procedure_id\", \"\") or \"\")}')
print(f'TASK_EVENT={shlex.quote(d.get(\"prediction_event\", \"\"))}')
print(f'ROUTE_TIER={shlex.quote(d.get(\"route_tier\", \"complex\"))}')
print(f'ROUTE_EXECUTOR={shlex.quote(d.get(\"route_executor\", \"claude\"))}')
print(f'ROUTE_SCORE={shlex.quote(str(d.get(\"route_score\", 0.5)))}')
print(f'ROUTE_REASON={shlex.quote(d.get(\"route_reason\", \"unknown\"))}')
print(f'EPISODIC_HINTS={shlex.quote(d.get(\"episodic_hints\", \"\"))}')
print(f'CONTEXT_BRIEF={shlex.quote(d.get(\"context_brief\", \"\"))}')
# Format procedure hint
proc = d.get('procedure')
if proc and proc.get('steps'):
    steps = proc['steps']
    steps_text = chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(steps))
    rate = f\"{proc.get('success_rate', 0):.0%}\"
    hint = f'PROCEDURAL MEMORY HIT (success rate: {rate}). Suggested steps:{chr(10)}{steps_text}{chr(10)}Use these steps as a starting guide, adapt as needed.'
    print(f'PROC_HINT={shlex.quote(hint)}')
else:
    print(\"PROC_HINT=''\")
# Timings summary
timings = d.get('timings', {})
print(f'PF_TOTAL_TIME={shlex.quote(str(timings.get(\"total\", \"?\")))}')
" 2>> "$LOGFILE")

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PREFLIGHT: status=$PF_STATUS task_salience=$BEST_SALIENCE route=$ROUTE_EXECUTOR time=${PF_TOTAL_TIME}s" >> "$LOGFILE"

# Handle non-execution states
if [ "$PF_STATUS" = "queue_empty" ] || [ "$PF_STATUS" = "no_tasks" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Queue empty — spawning task generation..." >> "$LOGFILE"
    COMPRESSOR="$SCRIPTS/context_compressor.py"
    REPLENISH_CONTEXT=$(python3 "$COMPRESSOR" brief 2>> "$LOGFILE")
    timeout 300 /home/agent/.local/bin/claude -p \
        "You are Clarvis's evolution engine. The evolution queue is EMPTY.

        Here's what was recently completed and current state:
        $REPLENISH_CONTEXT

        Check scripts/ directory to see what tools exist but may not be wired in.
        Check data/plans/ for unfinished research.
        Think: What's the biggest gap between current capabilities and AGI/consciousness?

        Add 3-5 NEW unchecked tasks to QUEUE.md under '## NEW ITEMS' section.
        Format: - [ ] <concrete task description>

        Focus on: wiring existing scripts into daily use, making capabilities persistent,
        building feedback loops, improving autonomous learning.
        Do NOT duplicate completed tasks. Be concrete and actionable." \
        --dangerously-skip-permissions >> "$LOGFILE" 2>&1

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Queue replenished — will execute on next run" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 0
fi

if [ "$SHOULD_DEFER" = "true" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] COGNITIVE LOAD: DEFERRING task — ${NEXT_TASK:0:80}" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 0
fi

if [ -z "$NEXT_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No task selected — exiting" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING (salience=$BEST_SALIENCE, section=$TASK_SECTION, route=$ROUTE_EXECUTOR): ${NEXT_TASK:0:100}" >> "$LOGFILE"

# ============================================================================
# PHASE 2: TASK EXECUTION
# Routes to: OpenRouter cheap model → Gemini Flash → Claude Code
# Kill switch: set OPENROUTER_ROUTING=false to disable cheap-model routing
# ============================================================================
TASK_START_SECONDS=$SECONDS
TASK_OUTPUT_FILE=$(mktemp)
OPENROUTER_STDERR=$(mktemp)
EXECUTOR_USED="$ROUTE_EXECUTOR"

COMPRESSED_EPISODES="$EPISODIC_HINTS"

# Kill switch — set to false in cron_env.sh to disable OpenRouter routing
OPENROUTER_ROUTING="${OPENROUTER_ROUTING:-true}"

if [ "$OPENROUTER_ROUTING" = "true" ] && [ "$ROUTE_EXECUTOR" = "gemini" -o "$ROUTE_EXECUTOR" = "openrouter" ]; then
    # === TRY OPENROUTER CHEAP MODEL FIRST ===
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTING to OpenRouter (tier=$ROUTE_TIER, score=$ROUTE_SCORE)" >> "$LOGFILE"
    EXECUTOR_USED="openrouter"

    TASK_CONTEXT="$CONTEXT_BRIEF" TASK_PROC_HINT="$PROC_HINT" TASK_EPISODE_HINT="$COMPRESSED_EPISODES" \
        python3 "$SCRIPTS/task_router.py" execute-openrouter "$NEXT_TASK" > "$TASK_OUTPUT_FILE" 2> "$OPENROUTER_STDERR"
    TASK_EXIT=$?

    # Capture real cost data from stderr if available
    OR_USAGE=$(grep "^OPENROUTER_USAGE:" "$OPENROUTER_STDERR" 2>/dev/null | sed 's/^OPENROUTER_USAGE: //')
    cat "$OPENROUTER_STDERR" | grep -v "^OPENROUTER_USAGE:" | grep -v "^NEEDS_CLAUDE_CODE:" >> "$LOGFILE" 2>/dev/null

    # Inject real cost data into preflight JSON for postflight to use
    # NOTE: OR_USAGE is written to a temp file to avoid shell quoting issues
    # (single quotes/backslashes in JSON would break inline python -c)
    if [ -n "$OR_USAGE" ]; then
        OR_USAGE_FILE=$(mktemp --suffix=.json)
        echo "$OR_USAGE" > "$OR_USAGE_FILE"
        python3 -c "
import json, sys
with open('$PREFLIGHT_FILE') as f:
    d = json.load(f)
with open('$OR_USAGE_FILE') as f:
    usage = json.load(f)
d['real_cost_usd'] = usage.get('cost', 0)
d['generation_id'] = usage.get('generation_id', '')
d['actual_model'] = usage.get('actual_model', '')
d['actual_input_tokens'] = usage.get('prompt_tokens', 0)
d['actual_output_tokens'] = usage.get('completion_tokens', 0)
d['route_executor'] = 'openrouter'
with open('$PREFLIGHT_FILE', 'w') as f:
    json.dump(d, f)
" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] OPENROUTER: cost=$(python3 -c "import json; print(json.load(open('$OR_USAGE_FILE')).get('cost','?'))" 2>/dev/null)" >> "$LOGFILE"
        rm -f "$OR_USAGE_FILE"
    fi

    # Check if task needs escalation to Claude Code
    if grep -q "NEEDS_CLAUDE_CODE: true" "$OPENROUTER_STDERR" 2>/dev/null || grep -q "NEEDS_CLAUDE_CODE: true" "$TASK_OUTPUT_FILE" 2>/dev/null || [ $TASK_EXIT -ne 0 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTER: OpenRouter escalated to Claude Code (fallback)" >> "$LOGFILE"
        EXECUTOR_USED="claude"
        timeout 600 /home/agent/.local/bin/claude -p \
            "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK
    ${PROC_HINT:+
    PROCEDURAL HINT: $PROC_HINT}
    ${COMPRESSED_EPISODES:+
    EPISODIC HINTS:
  $COMPRESSED_EPISODES}
    CONTEXT: ${CONTEXT_BRIEF}
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
            --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
        TASK_EXIT=$?
    fi

elif [ "$ROUTE_EXECUTOR" = "gemini" ]; then
    # === FALLBACK: GEMINI FLASH (when OpenRouter routing disabled) ===
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTING to Gemini Flash (tier=$ROUTE_TIER, score=$ROUTE_SCORE)" >> "$LOGFILE"

    TASK_CONTEXT="$CONTEXT_BRIEF" TASK_PROC_HINT="$PROC_HINT" TASK_EPISODE_HINT="$COMPRESSED_EPISODES" \
        python3 "$SCRIPTS/task_router.py" execute "$NEXT_TASK" > "$TASK_OUTPUT_FILE" 2>&1
    TASK_EXIT=$?

    if grep -q "NEEDS_CLAUDE_CODE: true" "$TASK_OUTPUT_FILE" 2>/dev/null || [ $TASK_EXIT -ne 0 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTER: Gemini escalated to Claude Code (fallback)" >> "$LOGFILE"
        EXECUTOR_USED="claude"
        timeout 600 /home/agent/.local/bin/claude -p \
            "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK
    ${PROC_HINT:+
    PROCEDURAL HINT: $PROC_HINT}
    ${COMPRESSED_EPISODES:+
    EPISODIC HINTS:
  $COMPRESSED_EPISODES}
    CONTEXT: ${CONTEXT_BRIEF}
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
            --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
        TASK_EXIT=$?
    fi
else
    # === CLAUDE CODE (complex/reasoning tasks) ===
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTING to Claude Code (tier=$ROUTE_TIER, score=$ROUTE_SCORE)" >> "$LOGFILE"

    timeout 600 /home/agent/.local/bin/claude -p \
        "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK
    ${PROC_HINT:+
    PROCEDURAL HINT: $PROC_HINT}
    ${COMPRESSED_EPISODES:+
    EPISODIC HINTS:
  $COMPRESSED_EPISODES}
    CONTEXT: ${CONTEXT_BRIEF}
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
        --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
    TASK_EXIT=$?
fi

rm -f "$OPENROUTER_STDERR"

TASK_DURATION=$((SECONDS - TASK_START_SECONDS))
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTION: executor=$EXECUTOR_USED exit=$TASK_EXIT duration=${TASK_DURATION}s" >> "$LOGFILE"

# Log executor output (truncated to last 2000 chars to prevent log bloat)
tail -c 2000 "$TASK_OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

# ============================================================================
# PHASE 3: BATCHED POST-FLIGHT (single Python process)
# Replaces: confidence outcome, reasoning_chain close, attention broadcast,
#           procedural memory learn/record, episodic encode, evolution loop,
#           digest writer, routing log — all in ONE import + execution.
# ============================================================================
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running batched post-flight..." >> "$LOGFILE"

POSTFLIGHT_OUTPUT=$(python3 "$SCRIPTS/heartbeat_postflight.py" "$TASK_EXIT" "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE" "$TASK_DURATION" 2>> "$LOGFILE")
POSTFLIGHT_EXIT=$?

if [ $POSTFLIGHT_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Postflight failed (exit $POSTFLIGHT_EXIT)" >> "$LOGFILE"
else
    # Log postflight timings
    PF_POST_TIME=$(echo "$POSTFLIGHT_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('timings',{}).get('total','?'))" 2>/dev/null || echo "?")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] POSTFLIGHT: complete in ${PF_POST_TIME}s" >> "$LOGFILE"
fi

# Cleanup
rm -f "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Heartbeat complete (preflight=${PF_TOTAL_TIME}s + exec=${TASK_DURATION}s + postflight=${PF_POST_TIME:-?}s) ===" >> "$LOGFILE"

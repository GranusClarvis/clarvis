#!/bin/bash
# Autonomous Evolution Loop — Clarvis Executive Function (OPTIMIZED)
# Runs 8x/day at hours 7,9,11,13,15,17,19,22.
#
# OPTIMIZATION (2026-02-23): Replaced ~25 individual Python subprocess spawns
# with 2 batched Python processes (heartbeat_preflight.py + heartbeat_postflight.py).
# Savings: ~7-8s per heartbeat from eliminated cold-starts + reduced disk I/O.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
LOGFILE="memory/cron/autonomous.log"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"

# Belt-and-suspenders: forcibly remove Claude Code nesting guard env vars.
# cron_env.sh already does this, but if invoked from within a claude session
# (e.g. manual trigger during dev), the vars may leak through.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Acquire locks: local (with 2400s stale detection) + global Claude (queue on conflict)
acquire_local_lock "/tmp/clarvis_autonomous.lock" "$LOGFILE" 2400
acquire_global_claude_lock "$LOGFILE" "queue"

# ============================================================================
# PHASE 1: BATCHED PRE-FLIGHT (single Python process)
# Replaces: attention load/tick, task_selector, cognitive_load, procedural_memory,
#           reasoning_chain open, confidence predict, episodic recall,
#           context_compressor, task_router — all in ONE import + execution.
# ============================================================================
# === PRE-HEARTBEAT: Self-healing — detect and kill stuck agents ===
STUCK_COUNT=$(python3 "$SCRIPTS/agent_orchestrator.py" detect-stuck 2>/dev/null | grep -c "STUCK:" 2>/dev/null || true)
STUCK_COUNT=${STUCK_COUNT:-0}
STUCK_COUNT=$(echo "$STUCK_COUNT" | tr -d '[:space:]' | head -c 5)
if [ "$STUCK_COUNT" -gt 0 ] 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SELF-HEALING: $STUCK_COUNT stuck agents detected, healing..." >> "$LOGFILE"
    python3 "$SCRIPTS/agent_orchestrator.py" heal >> "$LOGFILE" 2>&1
fi

# Pre-compute weakest metric for prompt injection
WEAKEST_METRIC=$(get_weakest_metric)

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
    timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \
        "You are Clarvis's evolution engine. The evolution queue (memory/evolution/QUEUE.md) is EMPTY.
WEAKEST METRIC: $WEAKEST_METRIC — at least one new task MUST target this.

Recent state: $REPLENISH_CONTEXT

Scan the system for gaps: scripts/, skills/, HEARTBEAT.md, AGENTS.md, openclaw.json, crontab, data/plans/.
Add 3-5 NEW unchecked tasks to QUEUE.md under '## NEW ITEMS'. Format: - [ ] <task>
Rules: no duplicates, at least 1 non-Python task, at least 1 targeting the weakest metric.
OUTPUT FORMAT (mandatory): TASKS ADDED: <count>. Then list each task on its own line." \
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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING (salience=$BEST_SALIENCE, section=$TASK_SECTION, route=$ROUTE_EXECUTOR tier=$ROUTE_TIER): ${NEXT_TASK:0:100}" >> "$LOGFILE"

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

# Shared function: build Claude Code prompt and execute
# Deduplicates the 3 identical prompt blocks below (escalation, fallback, direct)
run_claude_code() {
    local _timeout="$1"
    local _output_file="$2"

    # Build prompt via file (shell-safe, avoids heredoc expansion issues)
    local _prompt_file
    _prompt_file=$(mktemp --suffix=.txt)
    cat > "$_prompt_file" << ENDPROMPT
You are Clarvis's executive function.

${TIME_BUDGET_HINT}
WEAKEST METRIC: $WEAKEST_METRIC — consider if your task can improve this.
QUEUE: Read memory/evolution/QUEUE.md for task backlog. Mark your task [x] when done.
${CONTEXT_BRIEF}
${PROC_HINT:+
PROCEDURAL HINT: $PROC_HINT}

TASK: $NEXT_TASK

Do the work. Be concrete. Write code, edit configs, update protocols — whatever fits. Test it.
OUTPUT FORMAT (mandatory): Start with "RESULT: success|partial|fail — <what changed>". Then 1-3 lines of detail. End with "NEXT: <suggested follow-up or none>".
ENDPROMPT

    timeout "$_timeout" env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        /home/agent/.local/bin/claude -p "$(cat "$_prompt_file")" \
        --dangerously-skip-permissions --model claude-opus-4-6 \
        > "$_output_file" 2>&1
    local _exit=$?
    rm -f "$_prompt_file"
    return $_exit
}

# Tier-aware timeout: reasoning tasks get more time, complex tasks get moderate
# User mandate: minimum 4-10 min, max 25 min for complex work
case "$ROUTE_TIER" in
    reasoning) CLAUDE_TIMEOUT=1800 ;;  # 30 min for deep reasoning
    complex)   CLAUDE_TIMEOUT=1500 ;;  # 25 min for complex tasks
    *)         CLAUDE_TIMEOUT=1200 ;;  # 20 min minimum
esac

# BUG FIX (2026-02-27): When OpenRouter escalates to Claude Code, the timeout
# must be upgraded to at least the Claude Code minimum (900s). Previously,
# "medium" tier tasks kept their 600s timeout after escalation, causing timeouts.
# This is applied later when EXECUTOR_USED changes to "claude" after escalation.

# Check if this task previously timed out (from retry tracker)
RETRY_FILE="/home/agent/.openclaw/workspace/data/task_retries.json"
PREV_TIMEOUTS=0
if [ -f "$RETRY_FILE" ]; then
    PREV_TIMEOUTS=$(python3 -c "
import json, sys
with open('$RETRY_FILE') as f:
    d = json.load(f)
key = '''${NEXT_TASK:0:80}'''
print(d.get(key, 0))
" 2>/dev/null || echo 0)
fi

# Build time-budget hint for Claude prompts
TIME_BUDGET_HINT="TIME BUDGET: You have ~$((CLAUDE_TIMEOUT / 60)) minutes. Prioritize completing something concrete over perfection."
if [ "$PREV_TIMEOUTS" -gt 0 ]; then
    TIME_BUDGET_HINT="${TIME_BUDGET_HINT}
    WARNING: This task timed out ${PREV_TIMEOUTS} time(s) before. Focus on the SMALLEST viable increment. If the task is too large, do only the most impactful part and mark the rest as TODO."
fi

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
        # Upgrade timeout: escalated tasks need Claude Code minimum (900s)
        if [ "$CLAUDE_TIMEOUT" -lt 900 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ESCALATION: upgrading timeout to 1200s (Claude Code minimum)" >> "$LOGFILE"
            CLAUDE_TIMEOUT=1200
        fi
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTER: OpenRouter escalated to Claude Code (fallback, timeout=${CLAUDE_TIMEOUT}s)" >> "$LOGFILE"
        EXECUTOR_USED="claude"
        run_claude_code "$CLAUDE_TIMEOUT" "$TASK_OUTPUT_FILE"
        TASK_EXIT=$?
    fi

elif [ "$ROUTE_EXECUTOR" = "gemini" ]; then
    # === FALLBACK: OpenRouter cheap model (when primary OpenRouter routing disabled) ===
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTING to OpenRouter fallback (tier=$ROUTE_TIER, score=$ROUTE_SCORE)" >> "$LOGFILE"
    EXECUTOR_USED="openrouter"

    TASK_CONTEXT="$CONTEXT_BRIEF" TASK_PROC_HINT="$PROC_HINT" TASK_EPISODE_HINT="$COMPRESSED_EPISODES" \
        python3 "$SCRIPTS/task_router.py" execute-openrouter "$NEXT_TASK" > "$TASK_OUTPUT_FILE" 2>&1
    TASK_EXIT=$?

    if grep -q "NEEDS_CLAUDE_CODE: true" "$TASK_OUTPUT_FILE" 2>/dev/null || [ $TASK_EXIT -ne 0 ]; then
        # Upgrade timeout: escalated tasks need Claude Code minimum (900s)
        if [ "$CLAUDE_TIMEOUT" -lt 900 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ESCALATION: upgrading timeout to 1200s (Claude Code minimum)" >> "$LOGFILE"
            CLAUDE_TIMEOUT=1200
        fi
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTER: OpenRouter escalated to Claude Code (fallback, timeout=${CLAUDE_TIMEOUT}s)" >> "$LOGFILE"
        EXECUTOR_USED="claude"
        run_claude_code "$CLAUDE_TIMEOUT" "$TASK_OUTPUT_FILE"
        TASK_EXIT=$?
    fi
else
    # === CLAUDE CODE (complex/reasoning tasks) ===
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ROUTING to Claude Code (tier=$ROUTE_TIER, score=$ROUTE_SCORE, timeout=${CLAUDE_TIMEOUT}s)" >> "$LOGFILE"

    run_claude_code "$CLAUDE_TIMEOUT" "$TASK_OUTPUT_FILE"
    TASK_EXIT=$?
fi

rm -f "$OPENROUTER_STDERR"

TASK_DURATION=$((SECONDS - TASK_START_SECONDS))
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTION: executor=$EXECUTOR_USED exit=$TASK_EXIT duration=${TASK_DURATION}s timeout=${CLAUDE_TIMEOUT}s tier=$ROUTE_TIER" >> "$LOGFILE"

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
    # Log postflight timings — extract JSON from potentially mixed output
    PF_POST_TIME=$(echo "$POSTFLIGHT_OUTPUT" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            print(d.get('timings', {}).get('total', '?'))
            sys.exit(0)
        except json.JSONDecodeError:
            pass
print('?')
" 2>/dev/null || echo "?")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] POSTFLIGHT: complete in ${PF_POST_TIME}s" >> "$LOGFILE"
fi

# Cleanup
rm -f "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Heartbeat complete (preflight=${PF_TOTAL_TIME}s + exec=${TASK_DURATION}s + postflight=${PF_POST_TIME:-?}s) ===" >> "$LOGFILE"

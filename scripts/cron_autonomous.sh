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
    emit_dashboard_event self_heal --section cron_autonomous --stuck-count "$STUCK_COUNT"
    python3 "$SCRIPTS/agent_orchestrator.py" heal >> "$LOGFILE" 2>&1
fi

# Bootstrap daily memory file if missing (first run of day creates it)
DAILY_MEM="memory/$(date -u +%Y-%m-%d).md"
if [ ! -f "$DAILY_MEM" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Bootstrapping daily memory file..." >> "$LOGFILE"
    python3 /home/agent/.openclaw/workspace/scripts/daily_memory_log.py >> "$LOGFILE" 2>&1 || true
fi

# Pre-compute weakest metric for prompt injection
WEAKEST_METRIC=$(get_weakest_metric)

# === EXTERNAL CHALLENGE INJECTION: ensure queue always has some external challenges ===
# Rate-limited internally (max 2/day, min 8h apart). Runs before preflight so challenges
# are available for task selection.
if ! grep -q '\[EXTERNAL_CHALLENGE:' "$QUEUE_FILE" 2>/dev/null || \
   ! grep -q '^\- \[ \] \[EXTERNAL_CHALLENGE:' "$QUEUE_FILE" 2>/dev/null; then
    python3 "$SCRIPTS/external_challenge_feed.py" inject >> "$LOGFILE" 2>&1 || true
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Heartbeat starting (optimized batched pipeline) ===" >> "$LOGFILE"

PREFLIGHT_FILE=$(mktemp --suffix=.json)

# === PRE-EXECUTION VALIDATION: Queue file sanity check ===
QUEUE_FILE="/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
if [ ! -f "$QUEUE_FILE" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CRASH_GUARD: Queue file missing ($QUEUE_FILE) — creating empty" >> "$LOGFILE"
    mkdir -p "$(dirname "$QUEUE_FILE")"
    echo "# Evolution Queue — Clarvis" > "$QUEUE_FILE"
elif [ ! -r "$QUEUE_FILE" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CRASH_GUARD: Queue file not readable — aborting" >> "$LOGFILE"
    exit 1
fi

python3 "$SCRIPTS/heartbeat_preflight.py" > "$PREFLIGHT_FILE" 2>> "$LOGFILE"
PREFLIGHT_EXIT=$?

if [ "$PREFLIGHT_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Preflight failed (exit $PREFLIGHT_EXIT)" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 1
fi

# Parse preflight results (single jq-like parse via python — 1 invocation for all fields)
# Safety: strip any non-JSON lines that leaked to stdout from imported modules
python3 -c "
import json, sys, os, tempfile
with open('$PREFLIGHT_FILE') as f:
    lines = f.readlines()
# Find the JSON line (starts with '{')
json_lines = [l for l in lines if l.strip().startswith('{')]
if not json_lines:
    print('ERROR: No JSON found in preflight output', file=sys.stderr)
    sys.exit(1)
# Atomic write: validate JSON, write to temp, then rename
data = json.loads(json_lines[-1])  # validate it's real JSON
fd, tmp = tempfile.mkstemp(suffix='.json', dir=os.path.dirname('$PREFLIGHT_FILE') or '/tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.rename(tmp, '$PREFLIGHT_FILE')
except Exception:
    os.unlink(tmp)
    raise
" 2>> "$LOGFILE"

if [ $? -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ERROR: Preflight output contained no valid JSON" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 1
fi

EVAL_OUTPUT=$(python3 -c "
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
print(f'CONFIDENCE_TIER={shlex.quote(d.get(\"confidence_tier\", \"HIGH\"))}')
print(f'CONFIDENCE_FOR_TIER={shlex.quote(str(d.get(\"confidence_for_tier\", 0.7)))}')
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
# Worker type classification (for prompt template selection)
task_text = d.get('task', '')
pvt = d.get('prompt_variant_task_type', '')
sys.path.insert(0, '/home/agent/.openclaw/workspace')
try:
    from clarvis.heartbeat.worker_validation import classify_worker_type
    wtype = classify_worker_type(task_text, prompt_variant_task_type=pvt)
except Exception:
    wtype = 'general'
print(f'WORKER_TYPE={shlex.quote(wtype)}')
# Timings summary
timings = d.get('timings', {})
print(f'PF_TOTAL_TIME={shlex.quote(str(timings.get(\"total\", \"?\")))}')
" 2>> "$LOGFILE")
EVAL_PARSE_EXIT=$?

if [ "$EVAL_PARSE_EXIT" -ne 0 ] || [ -z "$EVAL_OUTPUT" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CRASH_GUARD: Preflight JSON parse failed (exit $EVAL_PARSE_EXIT) — aborting" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 1
fi

eval "$EVAL_OUTPUT"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PREFLIGHT: status=$PF_STATUS task_salience=$BEST_SALIENCE route=$ROUTE_EXECUTOR confidence_tier=$CONFIDENCE_TIER time=${PF_TOTAL_TIME}s" >> "$LOGFILE"

# Handle non-execution states
if [ "$PF_STATUS" = "queue_empty" ] || [ "$PF_STATUS" = "no_tasks" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Queue empty — spawning task generation..." >> "$LOGFILE"
    COMPRESSOR="$SCRIPTS/context_compressor.py"
    REPLENISH_CONTEXT=$(python3 "$COMPRESSOR" brief 2>> "$LOGFILE")
    REPLENISH_PROMPT=$(mktemp --suffix=.txt)
    {
        cat <<'STATIC'
You are Clarvis's evolution engine. The evolution queue (memory/evolution/QUEUE.md) is EMPTY.
STATIC
        printf 'WEAKEST METRIC: %s — at least one new task MUST target this.\n\n' "$WEAKEST_METRIC"
        printf 'Recent state: %s\n\n' "$REPLENISH_CONTEXT"
        cat <<'STATIC2'
Scan the system for gaps: scripts/, skills/, HEARTBEAT.md, AGENTS.md, openclaw.json, crontab, data/plans/.
Add 3-5 NEW unchecked tasks to QUEUE.md under '## NEW ITEMS'. Format: - [ ] <task>
Rules: no duplicates, at least 1 non-Python task, at least 1 targeting the weakest metric.
OUTPUT FORMAT (mandatory): TASKS ADDED: <count>. Then list each task on its own line.
STATIC2
    } > "$REPLENISH_PROMPT"
    timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \
        --dangerously-skip-permissions --model claude-opus-4-6 \
        < "$REPLENISH_PROMPT" >> "$LOGFILE" 2>&1
    rm -f "$REPLENISH_PROMPT"

    # Also inject one external challenge alongside self-generated tasks
    python3 "$SCRIPTS/external_challenge_feed.py" inject >> "$LOGFILE" 2>&1 || true

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

# === CRASH GUARD: Validate selected task before execution ===
TASK_STRIPPED=$(echo "$NEXT_TASK" | tr -d '[:space:]')
if [ ${#TASK_STRIPPED} -lt 5 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CRASH_GUARD: Task too short or whitespace-only (${#TASK_STRIPPED} chars) — skipping: '$NEXT_TASK'" >> "$LOGFILE"
    rm -f "$PREFLIGHT_FILE"
    exit 0
fi

# === SMART BATCHING (user directive 2026-03-05): if tasks are small, do up to 3 in ONE Claude prompt ===
# We only batch when the selected executor is Claude (single long run); we do not multi-run Claude.
BATCH_TASKS="$NEXT_TASK"
BATCH_COUNT=1
if [ "$ROUTE_EXECUTOR" = "claude" ]; then
    eval "$(NEXT_TASK="$NEXT_TASK" python3 - <<'PY'
import os, re, shlex, sys
sys.path.insert(0,'/home/agent/.openclaw/workspace/scripts')
from cognitive_load import estimate_task_complexity

QUEUE_FILE = '/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md'

next_task = os.environ.get('NEXT_TASK', '').strip()
if not next_task:
    print("BATCH_COUNT=0")
    print("BATCH_TASKS='' ")
    raise SystemExit

# Pull unchecked tasks in order, keep as written after checkbox
try:
    content = open(QUEUE_FILE, 'r').read().splitlines()
except Exception:
    content = []

unchecked = []
for line in content:
    m = re.match(r'^- \[ \] (.+)$', line)
    if not m:
        continue
    task = m.group(1).strip()
    if not task:
        continue
    unchecked.append(task)

# Ensure the current NEXT_TASK is first in the batch
batch = [next_task]

# Heuristics: only batch tasks that are not oversized and not too long.
MAX_TASKS = 3
MAX_TOTAL_CHARS = 900

def ok_to_batch(t: str) -> bool:
    sizing = estimate_task_complexity(t)
    if sizing.get('recommendation') == 'defer_to_sprint':
        return False
    # avoid very long tasks even if not flagged
    if len(t) > 320:
        return False
    return True

# Prefer subtasks / simple items
for t in unchecked:
    if len(batch) >= MAX_TASKS:
        break
    if t == next_task:
        continue
    # Don't batch other big parent tasks; prefer subtasks or short tasks
    if not ok_to_batch(t):
        continue
    # Cap total size
    if sum(len(x) for x in batch) + len(t) > MAX_TOTAL_CHARS:
        continue
    batch.append(t)

# Output shell-safe vars
print(f"BATCH_COUNT={len(batch)}")
print(f"BATCH_TASKS={shlex.quote(chr(10).join(batch))}")
PY
)" 2>> "$LOGFILE" || true
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING (salience=$BEST_SALIENCE, section=$TASK_SECTION, route=$ROUTE_EXECUTOR tier=$ROUTE_TIER, worker=$WORKER_TYPE, batch=$BATCH_COUNT): ${NEXT_TASK:0:100}" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "${NEXT_TASK:0:120}" --section cron_autonomous --executor "$ROUTE_EXECUTOR" --salience "$BEST_SALIENCE" --batch-count "$BATCH_COUNT"

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

# Load worker template based on WORKER_TYPE from preflight classification
WORKER_TEMPLATE=""
WORKER_TEMPLATE_DIR="$SCRIPTS/worker_templates"
if [ -n "$WORKER_TYPE" ] && [ -f "$WORKER_TEMPLATE_DIR/${WORKER_TYPE}.txt" ]; then
    WORKER_TEMPLATE=$(cat "$WORKER_TEMPLATE_DIR/${WORKER_TYPE}.txt")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WORKER_TEMPLATE: loaded ${WORKER_TYPE}.txt" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WORKER_TEMPLATE: none (worker_type=${WORKER_TYPE:-unset})" >> "$LOGFILE"
fi

# === WORKTREE AUTO-DETECT ===
# Detect code-modifying tasks and log recommendation. Full worktree isolation
# requires run_claude_code() restructuring — for now, tag the task for future use.
WORKTREE_RECOMMENDED="false"
if echo "$NEXT_TASK" | grep -qiE '(refactor|migrate|rewrite|rename|delete|remove|restructure|move files|split|merge|extract|SPINE_MIGRATION|LEGACY_SCRIPT)'; then
    WORKTREE_RECOMMENDED="true"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WORKTREE: code-modifying task detected, isolation recommended" >> "$LOGFILE"
fi

# Shared function: build Claude Code prompt and execute
# Deduplicates the 3 identical prompt blocks below (escalation, fallback, direct)
run_claude_code() {
    local _timeout="$1"
    local _output_file="$2"

    # Build prompt via printf (shell-safe — no heredoc expansion of $, `, {})
    local _prompt_file
    _prompt_file=$(mktemp --suffix=.txt)
    {
        printf '%s\n\n' "${WORKER_TEMPLATE:-You are Clarvis executive function.}"
        printf '%s\n' "$TIME_BUDGET_HINT"
        printf 'WEAKEST METRIC: %s — consider if your task can improve this.\n' "$WEAKEST_METRIC"
        printf 'QUEUE: Read memory/evolution/QUEUE.md for task backlog. Mark your task [x] when done.\n'
        printf '%s\n' "$CONTEXT_BRIEF"
        if [ -n "$PROC_HINT" ]; then
            printf '\nPROCEDURAL HINT: %s\n' "$PROC_HINT"
        fi
        printf '\nTASKS (execute in order; if a task is already done/obsolete, mark it [x] with a brief note in QUEUE.md):\n'
        printf '%s\n' "$BATCH_TASKS" | nl -w2 -s'. '
        cat <<'STATIC_BLOCK'

Do the work. Be concrete. Write code, edit configs, update protocols — whatever fits. Test it.
Rules:
- You have one run. No second Claude invocation.
- If you can finish 2-3 tasks safely within the time budget, do so.
- After each task, update QUEUE.md (mark [x]) before moving to the next.
OUTPUT FORMAT (mandatory): Start with "RESULT: success|partial|fail — <what changed>". Then list each task with status. End with "NEXT: <suggested follow-up or none>".
STATIC_BLOCK
    } > "$_prompt_file"

    # Validate prompt is non-empty before invoking Claude
    if [ ! -s "$_prompt_file" ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROMPT_GUARD: prompt file is empty — aborting Claude invocation" >> "$LOGFILE"
        rm -f "$_prompt_file"
        return 1
    fi

    # Start Claude Code in background for progress monitoring
    # Feed prompt via stdin (not argv) to avoid shell expansion of prompt content
    timeout "$_timeout" env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        /home/agent/.local/bin/claude -p \
        --dangerously-skip-permissions --model claude-opus-4-6 \
        < "$_prompt_file" > "$_output_file" 2>&1 &
    local _claude_pid=$!

    # Pattern 9: Commitment & Reconsideration — monitor for stalled execution
    python3 "$SCRIPTS/execution_monitor.py" "$_output_file" "$_timeout" "$_claude_pid" >> "$LOGFILE" 2>&1 &
    local _monitor_pid=$!

    # Wait for Claude Code (or monitor-triggered abort)
    wait "$_claude_pid"
    local _exit=$?

    # Clean up monitor
    kill "$_monitor_pid" 2>/dev/null
    wait "$_monitor_pid" 2>/dev/null

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

if [ "$OPENROUTER_ROUTING" = "true" ] && { [ "$ROUTE_EXECUTOR" = "gemini" ] || [ "$ROUTE_EXECUTOR" = "openrouter" ]; }; then
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
import json, sys, os, tempfile
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
fd, tmp = tempfile.mkstemp(suffix='.json', dir=os.path.dirname('$PREFLIGHT_FILE') or '/tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(d, f)
    os.rename(tmp, '$PREFLIGHT_FILE')
except Exception:
    os.unlink(tmp)
    raise
" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] OPENROUTER: cost=$(python3 -c "import json; print(json.load(open('$OR_USAGE_FILE')).get('cost','?'))" 2>/dev/null)" >> "$LOGFILE"
        rm -f "$OR_USAGE_FILE"
    fi

    # Check if task needs escalation to Claude Code
    if grep -q "NEEDS_CLAUDE_CODE: true" "$OPENROUTER_STDERR" 2>/dev/null || grep -q "NEEDS_CLAUDE_CODE: true" "$TASK_OUTPUT_FILE" 2>/dev/null || [ "$TASK_EXIT" -ne 0 ]; then
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

    if grep -q "NEEDS_CLAUDE_CODE: true" "$TASK_OUTPUT_FILE" 2>/dev/null || [ "$TASK_EXIT" -ne 0 ]; then
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

# Check for reconsideration flag (Pattern 9: Commitment & Reconsideration)
RECONSIDER_FILE="${TASK_OUTPUT_FILE}.reconsider.json"
if [ -f "$RECONSIDER_FILE" ]; then
    RECONSIDER_INFO=$(python3 -c "
import json
with open('$RECONSIDER_FILE') as f:
    d = json.load(f)
print(f\"reason={d.get('reason','?')} aborted={d.get('aborted',False)}\")
" 2>/dev/null || echo "reason=unknown aborted=unknown")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] RECONSIDER: $RECONSIDER_INFO — task remains in queue for retry" >> "$LOGFILE"
    rm -f "$RECONSIDER_FILE"
fi

rm -f "$OPENROUTER_STDERR"

TASK_DURATION=$((SECONDS - TASK_START_SECONDS))
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTION: executor=$EXECUTOR_USED exit=$TASK_EXIT duration=${TASK_DURATION}s timeout=${CLAUDE_TIMEOUT}s tier=$ROUTE_TIER" >> "$LOGFILE"

# === CRASH GUARD: Detect instant-fail episodes ===
# If execution took < 10s and failed, this is likely an infrastructure crash (auth, binary, etc.)
# not a real task failure. Inject crash marker into preflight JSON so postflight records it correctly.
INSTANT_FAIL_THRESHOLD=10
if [ "$TASK_EXIT" -ne 0 ] && [ "$TASK_DURATION" -lt "$INSTANT_FAIL_THRESHOLD" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CRASH_GUARD: Instant-fail detected (${TASK_DURATION}s < ${INSTANT_FAIL_THRESHOLD}s, exit=$TASK_EXIT) — marking as crash, not failure" >> "$LOGFILE"
    # Inject crash marker into preflight JSON for postflight to pick up
    python3 -c "
import json, os, tempfile
with open('$PREFLIGHT_FILE') as f:
    d = json.load(f)
d['crash_guard'] = True
d['crash_reason'] = 'instant_fail'
d['crash_duration'] = $TASK_DURATION
fd, tmp = tempfile.mkstemp(suffix='.json', dir=os.path.dirname('$PREFLIGHT_FILE') or '/tmp')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(d, f)
    os.rename(tmp, '$PREFLIGHT_FILE')
except Exception:
    os.unlink(tmp)
    raise
" 2>> "$LOGFILE"
fi

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

if [ "$POSTFLIGHT_EXIT" -ne 0 ]; then
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

# === TELEGRAM NOTIFICATION (success/failure/timeout) ===
# Matches spawn_claude.sh pattern — sends task result to Telegram
python3 - "$TASK_EXIT" "${NEXT_TASK:0:80}" "$EXECUTOR_USED" "$TASK_DURATION" << 'TGEOF' 2>> "$LOGFILE" || true
import json, urllib.request, urllib.parse, sys, os
exit_code = int(sys.argv[1])
task_short = sys.argv[2]
executor = sys.argv[3] if len(sys.argv) > 3 else "?"
duration = sys.argv[4] if len(sys.argv) > 4 else "?"
token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
chat_id = os.environ.get("CLARVIS_TG_CHAT_ID", "")
if not token or not chat_id:
    try:
        with open('/home/agent/.openclaw/openclaw.json') as f:
            config = json.load(f)
        if not token:
            token = config['channels']['telegram']['botToken']
        if not chat_id:
            chat_id = str(config['channels']['telegram'].get('chatId', ''))
    except Exception:
        sys.exit(0)
if not token or not chat_id:
    sys.exit(0)
emoji = "\u23f0" if exit_code == 124 else ("\u274c" if exit_code != 0 else "\u2705")
status = "TIMEOUT" if exit_code == 124 else ("FAIL" if exit_code != 0 else "OK")
msg = f"{emoji} Heartbeat: {status} ({executor}, {duration}s)\n\U0001f4cb {task_short}"
if len(msg) > 4000:
    msg = msg[:3997] + "..."
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg})
try:
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)
except Exception:
    pass
TGEOF

# === GIT HYGIENE AUTO-FIX (obligation enforcement) ===
# Auto-commit+push if dirty tree >60min and changes are safe (no secrets, no large binaries)
GIT_AUTOFIX=$(python3 "$SCRIPTS/obligation_tracker.py" auto-fix 2>> "$LOGFILE")
GIT_AUTOFIX_ACTION=$(echo "$GIT_AUTOFIX" | head -1)
if echo "$GIT_AUTOFIX_ACTION" | grep -qE "committed|pushed"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] GIT-HYGIENE: $GIT_AUTOFIX_ACTION — $(echo "$GIT_AUTOFIX" | tail -1)" >> "$LOGFILE"
fi

# Cleanup
rm -f "$TASK_OUTPUT_FILE" "$PREFLIGHT_FILE" "${TASK_OUTPUT_FILE}.reconsider.json"

emit_dashboard_event task_completed --task-name "${NEXT_TASK:0:120}" --section cron_autonomous --executor "$EXECUTOR_USED" --exit-code "$TASK_EXIT" --duration-s "$TASK_DURATION" --status "$([ "$TASK_EXIT" -eq 0 ] && echo success || echo failed)"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Heartbeat complete (preflight=${PF_TOTAL_TIME}s + exec=${TASK_DURATION}s + postflight=${PF_POST_TIME:-?}s) ===" >> "$LOGFILE"

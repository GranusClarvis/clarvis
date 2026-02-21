#!/bin/bash
# Autonomous Evolution Loop — Clarvis Executive Function
# Runs every 30 minutes. Picks next evolution task. Executes it.
# Uses attention-based salience scoring to pick BEST task, not just first.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/autonomous.log"
LOCKFILE="/tmp/clarvis_autonomous.lock"

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

# === RESTORE WORKING MEMORY FROM DISK ===
python3 /home/agent/.openclaw/workspace/scripts/working_memory.py load >> "$LOGFILE" 2>&1

# === ATTENTION-BASED TASK SELECTION ===
# Uses attention.py salience scoring + brain.py context (replaces bash keyword matching)
# task_selector.py scores all tasks via GWT-inspired salience: importance, recency,
# context relevance, AGI-boost, integration-boost — then returns the best one as JSON.

SELECTOR_SCRIPT="/home/agent/.openclaw/workspace/scripts/task_selector.py"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running attention-based task selector..." >> "$LOGFILE"

# Run Python task selector — stdout=JSON result, stderr=score log
SELECTOR_OUTPUT=$(python3 "$SELECTOR_SCRIPT" 2>> "$LOGFILE")
SELECTOR_EXIT=$?

if [ $SELECTOR_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Task selector failed (exit $SELECTOR_EXIT), falling back to grep" >> "$LOGFILE"
    # Fallback: first unchecked task
    SELECTOR_OUTPUT=""
fi

# Parse the JSON output
if [ -n "$SELECTOR_OUTPUT" ]; then
    # Check for error (empty queue)
    IS_ERROR=$(echo "$SELECTOR_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'error' in d else 'no')" 2>/dev/null)

    if [ "$IS_ERROR" = "yes" ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Queue empty — spawning task generation..." >> "$LOGFILE"

        # Auto-replenish: spawn Claude Code to analyze state and add new tasks
        timeout 300 /home/agent/.local/bin/claude -p \
            "You are Clarvis's evolution engine. The evolution queue is EMPTY.

            1. Read memory/evolution/QUEUE.md to see what was already completed.
            2. Read scripts/ directory to see what tools exist but may not be wired in.
            3. Check data/plans/ for unfinished research.
            4. Think: What's the biggest gap between current capabilities and AGI/consciousness?

            Add 3-5 NEW unchecked tasks to QUEUE.md under '## P0 — Do Next Heartbeat'.
            Format: - [ ] <concrete task description>

            Focus on: wiring existing scripts into daily use, making capabilities persistent,
            building feedback loops, improving autonomous learning.
            Do NOT duplicate completed tasks. Be concrete and actionable." \
            --dangerously-skip-permissions >> "$LOGFILE" 2>&1

        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Queue replenished — will execute on next run" >> "$LOGFILE"
        exit 0
    fi

    # Extract best task text and salience from JSON
    NEXT_TASK=$(echo "$SELECTOR_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['text'])" 2>/dev/null)
    BEST_SALIENCE=$(echo "$SELECTOR_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['salience'])" 2>/dev/null)
    TASK_SECTION=$(echo "$SELECTOR_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['section'])" 2>/dev/null)

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SELECTED (salience=$BEST_SALIENCE, section=$TASK_SECTION): ${NEXT_TASK:0:80}..." >> "$LOGFILE"
fi

# Fallback if Python selector produced no result
if [ -z "$NEXT_TASK" ]; then
    NEXT_TASK=$(grep '^\- \[ \]' memory/evolution/QUEUE.md | head -1 | sed 's/^- \[ \] //')
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FALLBACK: Using first unchecked task: ${NEXT_TASK:0:80}..." >> "$LOGFILE"
fi

if [ -z "$NEXT_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No tasks available at all." >> "$LOGFILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING: $NEXT_TASK" >> "$LOGFILE"

# === PROCEDURAL MEMORY: Check for existing procedure ===
PROC_SCRIPT="/home/agent/.openclaw/workspace/scripts/procedural_memory.py"
PROC_MATCH=$(python3 "$PROC_SCRIPT" check "$NEXT_TASK" 2>> "$LOGFILE")
PROC_HINT=""
PROC_ID=""
if [ -n "$PROC_MATCH" ] && [ "$PROC_MATCH" != "{}" ]; then
    PROC_ID=$(echo "$PROC_MATCH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
    PROC_STEPS=$(echo "$PROC_MATCH" | python3 -c "import sys,json; d=json.load(sys.stdin); steps=d.get('steps',[]); [print(f'  {i+1}. {s}') for i,s in enumerate(steps)]" 2>/dev/null)
    PROC_RATE=$(echo "$PROC_MATCH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('success_rate',0):.0%}\")" 2>/dev/null)
    if [ -n "$PROC_STEPS" ]; then
        PROC_HINT="
    PROCEDURAL MEMORY HIT: A similar task was done before (success rate: ${PROC_RATE}). Suggested steps:
${PROC_STEPS}
    Use these steps as a starting guide, adapt as needed."
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROCEDURAL: Found matching procedure $PROC_ID" >> "$LOGFILE"
    fi
fi

# === REASONING CHAIN: Open chain before execution ===
REASONING_HOOK="/home/agent/.openclaw/workspace/scripts/reasoning_chain_hook.py"
CHAIN_ID=$(python3 "$REASONING_HOOK" open "$NEXT_TASK" "${TASK_SECTION:-unknown}" "${BEST_SALIENCE:-0.0}" 2>> "$LOGFILE")
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Opened chain $CHAIN_ID for task" >> "$LOGFILE"

# === PREDICTION: Log confidence prediction before execution ===
CONFIDENCE_SCRIPT="/home/agent/.openclaw/workspace/scripts/clarvis_confidence.py"
# Sanitize task text for use as event key (first 60 chars, alphanumeric + underscores)
TASK_EVENT=$(echo "$NEXT_TASK" | head -c 60 | sed 's/[^a-zA-Z0-9]/_/g')
# Use dynamic confidence from calibration data (not hardcoded)
DYNAMIC_CONF=$(python3 "$CONFIDENCE_SCRIPT" dynamic 2>/dev/null || echo "0.7")
python3 "$CONFIDENCE_SCRIPT" predict "$TASK_EVENT" "success" "$DYNAMIC_CONF" >> "$LOGFILE" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PREDICTION: Logged prediction for $TASK_EVENT (confidence=$DYNAMIC_CONF)" >> "$LOGFILE"

# Spawn Claude Code to work on the task (10 min timeout)
# Capture output and exit code for evolution loop
TASK_OUTPUT_FILE=$(mktemp)
timeout 600 /home/agent/.local/bin/claude -p \
    "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK
    ${PROC_HINT}
    CONTEXT: Read memory/evolution/QUEUE.md for full context. Use brain.py for memory.
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
    --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?

# Log the output
cat "$TASK_OUTPUT_FILE" >> "$LOGFILE"

# Save working memory state after heartbeat (survives restarts)
python3 /home/agent/.openclaw/workspace/scripts/working_memory.py save >> "$LOGFILE" 2>&1

# === OUTCOME: Record actual result for prediction feedback loop ===
if [ $TASK_EXIT -eq 0 ]; then
    python3 "$CONFIDENCE_SCRIPT" outcome "$TASK_EVENT" "success" >> "$LOGFILE" 2>&1
    # === REASONING CHAIN: Close with success outcome ===
    if [ -n "$CHAIN_ID" ]; then
        python3 "$REASONING_HOOK" close "$CHAIN_ID" "success" "$NEXT_TASK" "$TASK_EXIT" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Closed chain $CHAIN_ID (success)" >> "$LOGFILE"
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] COMPLETED: $NEXT_TASK" >> "$LOGFILE"
    # === PROCEDURAL MEMORY: Learn from success or record use ===
    if [ -n "$PROC_ID" ]; then
        python3 "$PROC_SCRIPT" used "$PROC_ID" success >> "$LOGFILE" 2>&1
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROCEDURAL: Recorded successful use of $PROC_ID" >> "$LOGFILE"
    else
        # Extract real steps from task output (not a generic template)
        EXTRACT_SCRIPT="/home/agent/.openclaw/workspace/scripts/extract_steps.py"
        EXTRACTED_STEPS=$(python3 "$EXTRACT_SCRIPT" --file "$TASK_OUTPUT_FILE" 2>/dev/null)
        if [ -n "$EXTRACTED_STEPS" ] && [ "$EXTRACTED_STEPS" != "[]" ]; then
            python3 "$PROC_SCRIPT" learn "$NEXT_TASK" "$EXTRACTED_STEPS" >> "$LOGFILE" 2>&1
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROCEDURAL: Learned procedure with extracted steps: $EXTRACTED_STEPS" >> "$LOGFILE"
        else
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROCEDURAL: Skipped learning — could not extract concrete steps from output" >> "$LOGFILE"
        fi
    fi
else
    python3 "$CONFIDENCE_SCRIPT" outcome "$TASK_EVENT" "failure" >> "$LOGFILE" 2>&1
    # === REASONING CHAIN: Close with failure outcome ===
    if [ -n "$CHAIN_ID" ]; then
        python3 "$REASONING_HOOK" close "$CHAIN_ID" "failure" "$NEXT_TASK" "$TASK_EXIT" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Closed chain $CHAIN_ID (failure)" >> "$LOGFILE"
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FAILED (exit $TASK_EXIT): $NEXT_TASK" >> "$LOGFILE"
    # === PROCEDURAL MEMORY: Record failure against procedure if used ===
    if [ -n "$PROC_ID" ]; then
        python3 "$PROC_SCRIPT" used "$PROC_ID" failure >> "$LOGFILE" 2>&1
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROCEDURAL: Recorded failed use of $PROC_ID" >> "$LOGFILE"
    fi

    # === HIVE-STYLE EVOLUTION: Failure → Evolve → Redeploy ===
    # Capture failure and trigger self-improvement
    TASK_STDERR=$(tail -c 2000 "$TASK_OUTPUT_FILE")
    python3 /home/agent/.openclaw/workspace/scripts/evolution_loop.py \
        capture "cron_autonomous" "Exit code $TASK_EXIT running task" "$NEXT_TASK" >> "$LOGFILE" 2>&1

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EVOLUTION: Failure captured, analyzing..." >> "$LOGFILE"

    # Get the failure ID (most recent) and run evolution
    FAILURE_ID=$(ls -t /home/agent/.openclaw/workspace/data/evolution/failures/fail_*_cron_autonomous.json 2>/dev/null | head -1 | xargs -I{} basename {} .json)
    if [ -n "$FAILURE_ID" ]; then
        python3 /home/agent/.openclaw/workspace/scripts/evolution_loop.py \
            evolve "$FAILURE_ID" >> "$LOGFILE" 2>&1
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EVOLUTION: Fix generated for $FAILURE_ID" >> "$LOGFILE"
    fi
fi

rm -f "$TASK_OUTPUT_FILE"
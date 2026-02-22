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

# === RESTORE ATTENTION SPOTLIGHT FROM DISK ===
# (attention.py is the unified GWT module — absorbed working_memory.py)
python3 /home/agent/.openclaw/workspace/scripts/attention.py load >> "$LOGFILE" 2>&1

# === ATTENTION TICK: Run GWT competition cycle ===
python3 /home/agent/.openclaw/workspace/scripts/attention.py tick >> "$LOGFILE" 2>&1 || true

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

    # === ATTENTION SPOTLIGHT: Load task context ===
    python3 /home/agent/.openclaw/workspace/scripts/attention.py add "CURRENT TASK: $NEXT_TASK" 0.9 >> "$LOGFILE" 2>&1
    python3 /home/agent/.openclaw/workspace/scripts/attention.py add "Task salience=$BEST_SALIENCE section=$TASK_SECTION" 0.5 >> "$LOGFILE" 2>&1
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
        # === ATTENTION: Add procedure context ===
        python3 /home/agent/.openclaw/workspace/scripts/attention.py add "PROCEDURE HIT ($PROC_ID, ${PROC_RATE} success): matched prior steps for current task" 0.7 >> "$LOGFILE" 2>&1
    fi
fi

# === REASONING CHAIN: Open chain before execution ===
REASONING_HOOK="/home/agent/.openclaw/workspace/scripts/reasoning_chain_hook.py"
CHAIN_ID=$(python3 "$REASONING_HOOK" open "$NEXT_TASK" "${TASK_SECTION:-unknown}" "${BEST_SALIENCE:-0.0}" 2>> "$LOGFILE")
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Opened chain $CHAIN_ID for task" >> "$LOGFILE"

# === ATTENTION: Add reasoning chain ID for cross-reference ===
python3 /home/agent/.openclaw/workspace/scripts/attention.py add "REASONING CHAIN: $CHAIN_ID tracking current task" 0.4 >> "$LOGFILE" 2>&1

# === PREDICTION: Log confidence prediction before execution ===
CONFIDENCE_SCRIPT="/home/agent/.openclaw/workspace/scripts/clarvis_confidence.py"
# Sanitize task text for use as event key (first 60 chars, alphanumeric + underscores)
TASK_EVENT=$(echo "$NEXT_TASK" | head -c 60 | sed 's/[^a-zA-Z0-9]/_/g')
# Use dynamic confidence from calibration data (not hardcoded)
DYNAMIC_CONF=$(python3 "$CONFIDENCE_SCRIPT" dynamic 2>/dev/null || echo "0.7")
python3 "$CONFIDENCE_SCRIPT" predict "$TASK_EVENT" "success" "$DYNAMIC_CONF" >> "$LOGFILE" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PREDICTION: Logged prediction for $TASK_EVENT (confidence=$DYNAMIC_CONF)" >> "$LOGFILE"

# === EPISODIC MEMORY: Recall similar past episodes before execution ===
EPISODIC_SCRIPT="/home/agent/.openclaw/workspace/scripts/episodic_memory.py"
EPISODE_HINT=""
SIMILAR_EPISODES=$(python3 "$EPISODIC_SCRIPT" recall "$NEXT_TASK" 2>/dev/null | head -5)
FAILURE_EPISODES=$(python3 "$EPISODIC_SCRIPT" failures 2>/dev/null | head -3)
if [ -n "$SIMILAR_EPISODES" ] || [ -n "$FAILURE_EPISODES" ]; then
    EPISODE_HINT="
    EPISODIC MEMORY — Similar past experiences:
    $SIMILAR_EPISODES

    Recent failures to avoid repeating:
    $FAILURE_EPISODES"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EPISODIC: Injecting ${#SIMILAR_EPISODES} chars of episode context" >> "$LOGFILE"
fi

# Start timer for episode duration
TASK_START_SECONDS=$SECONDS

# Spawn Claude Code to work on the task (10 min timeout)
# Capture output and exit code for evolution loop
TASK_OUTPUT_FILE=$(mktemp)
timeout 600 /home/agent/.local/bin/claude -p \
    "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK
    ${PROC_HINT}${EPISODE_HINT}
    CONTEXT: Read memory/evolution/QUEUE.md for full context. Use brain.py for memory.
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
    --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?
TASK_DURATION=$((SECONDS - TASK_START_SECONDS))

# Log the output
cat "$TASK_OUTPUT_FILE" >> "$LOGFILE"

# Save attention spotlight state after heartbeat (survives restarts)
python3 /home/agent/.openclaw/workspace/scripts/attention.py save >> "$LOGFILE" 2>&1

# === OUTCOME: Record actual result for prediction feedback loop ===
if [ $TASK_EXIT -eq 0 ]; then
    python3 "$CONFIDENCE_SCRIPT" outcome "$TASK_EVENT" "success" >> "$LOGFILE" 2>&1
    # === REASONING CHAIN: Close with success outcome + evidence ===
    if [ -n "$CHAIN_ID" ]; then
        # Extract last meaningful lines from output as evidence
        CHAIN_EVIDENCE=$(tail -c 300 "$TASK_OUTPUT_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 280)
        python3 "$REASONING_HOOK" close "$CHAIN_ID" "success" "$NEXT_TASK" "$TASK_EXIT" "$CHAIN_EVIDENCE" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Closed chain $CHAIN_ID (success, with evidence)" >> "$LOGFILE"
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] COMPLETED: $NEXT_TASK" >> "$LOGFILE"
    # === ATTENTION: Record success outcome ===
    python3 /home/agent/.openclaw/workspace/scripts/attention.py add "OUTCOME: SUCCESS — ${NEXT_TASK:0:80}" 0.8 >> "$LOGFILE" 2>&1
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
elif [ $TASK_EXIT -eq 124 ]; then
    # === TIMEOUT HANDLING (exit 124) ===
    # timeout(1) returns 124 when the command is killed. This is NOT the same as a
    # task failure — it means the task was too complex for the 10-min window.
    # Don't trigger the full evolution/failure loop for timeouts.
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] TIMEOUT (exit 124): Task exceeded 600s limit: ${NEXT_TASK:0:100}" >> "$LOGFILE"
    python3 "$CONFIDENCE_SCRIPT" outcome "$TASK_EVENT" "failure" >> "$LOGFILE" 2>&1

    # Close reasoning chain as timeout (not generic failure)
    if [ -n "$CHAIN_ID" ]; then
        CHAIN_EVIDENCE="TIMEOUT after 600s. Task too complex for single heartbeat window."
        python3 "$REASONING_HOOK" close "$CHAIN_ID" "failure" "$NEXT_TASK" "$TASK_EXIT" "$CHAIN_EVIDENCE" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Closed chain $CHAIN_ID (timeout)" >> "$LOGFILE"
    fi

    # Record failure against procedure if used
    if [ -n "$PROC_ID" ]; then
        python3 "$PROC_SCRIPT" used "$PROC_ID" failure >> "$LOGFILE" 2>&1
    fi

    # Check if the task made partial progress (output > 500 chars suggests work was done)
    OUTPUT_SIZE=$(wc -c < "$TASK_OUTPUT_FILE" 2>/dev/null || echo 0)
    if [ "$OUTPUT_SIZE" -gt 500 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] TIMEOUT-PARTIAL: Task produced ${OUTPUT_SIZE} bytes of output — may have partially completed" >> "$LOGFILE"
    fi

    python3 /home/agent/.openclaw/workspace/scripts/attention.py add "OUTCOME: TIMEOUT (600s) — ${NEXT_TASK:0:80}" 0.7 >> "$LOGFILE" 2>&1

    # Light-weight capture — log the timeout but do NOT trigger the full evolution loop.
    # Timeouts are expected for complex tasks and don't indicate a bug to fix.
    python3 /home/agent/.openclaw/workspace/scripts/evolution_loop.py \
        capture "cron_autonomous" "Timeout (exit 124) — task exceeded 600s" "$NEXT_TASK" >> "$LOGFILE" 2>&1
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] TIMEOUT: Captured for tracking (skipping evolution loop — timeouts are not bugs)" >> "$LOGFILE"
else
    python3 "$CONFIDENCE_SCRIPT" outcome "$TASK_EVENT" "failure" >> "$LOGFILE" 2>&1
    # === REASONING CHAIN: Close with failure outcome + error evidence ===
    if [ -n "$CHAIN_ID" ]; then
        CHAIN_EVIDENCE=$(tail -c 300 "$TASK_OUTPUT_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 280)
        python3 "$REASONING_HOOK" close "$CHAIN_ID" "failure" "$NEXT_TASK" "$TASK_EXIT" "$CHAIN_EVIDENCE" 2>> "$LOGFILE"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] REASONING: Closed chain $CHAIN_ID (failure, with evidence)" >> "$LOGFILE"
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FAILED (exit $TASK_EXIT): $NEXT_TASK" >> "$LOGFILE"
    # === ATTENTION: Record failure outcome (high importance — needs attention) ===
    python3 /home/agent/.openclaw/workspace/scripts/attention.py add "OUTCOME: FAILED (exit $TASK_EXIT) — ${NEXT_TASK:0:80}" 0.9 >> "$LOGFILE" 2>&1
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

# === EPISODIC MEMORY: Encode task as episode ===
TASK_STATUS="success"
[ $TASK_EXIT -ne 0 ] && TASK_STATUS="failure"
TASK_STDERR=""
[ "$TASK_STATUS" = "failure" ] && TASK_STDERR=$(tail -c 200 "$TASK_OUTPUT_FILE" 2>/dev/null)
python3 "$EPISODIC_SCRIPT" encode "$NEXT_TASK" "${TASK_SECTION:-P0}" "${BEST_SALIENCE:-0.5}" "$TASK_STATUS" "${TASK_DURATION:-0}" "$TASK_STDERR" >> "$LOGFILE" 2>&1 || true
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EPISODIC: Encoded episode ($TASK_STATUS, ${TASK_DURATION:-0}s)" >> "$LOGFILE"

# === ATTENTION BROADCAST: Feed task outcome into attention system ===
# Pass task text via env var to avoid SyntaxError from special chars (em-dashes, quotes)
BROADCAST_TASK="${NEXT_TASK:0:100}" BROADCAST_STATUS="$TASK_STATUS" python3 -c "
import os, sys; sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from attention import attention
status = os.environ.get('BROADCAST_STATUS', 'unknown')
task = os.environ.get('BROADCAST_TASK', '')
attention.submit(
    f'Heartbeat task {status}: {task}',
    source='heartbeat',
    importance=0.7 if status == 'success' else 0.9,
    relevance=0.8
)
" >> "$LOGFILE" 2>&1 || true

# === DIGEST: Write first-person summary for M2.5 agent ===
TASK_RESULT_SNIPPET=$(tail -c 200 "$TASK_OUTPUT_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 180)
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py autonomous \
    "I executed evolution task: \"${NEXT_TASK:0:120}\". Result: $TASK_STATUS (exit $TASK_EXIT, ${TASK_DURATION}s). Output: $TASK_RESULT_SNIPPET" \
    >> "$LOGFILE" 2>&1 || true

rm -f "$TASK_OUTPUT_FILE"
#!/bin/bash
# Autonomous Evolution Loop — Clarvis Executive Function
# Runs every 30 minutes. Picks next evolution task. Executes it.
# Uses attention-based salience scoring to pick BEST task, not just first.

cd /home/agent/.openclaw/workspace
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

# === ATTENTION-BASED TASK SELECTION ===
# Score all unchecked tasks and pick the highest-scoring one

# Get all unchecked tasks with their line numbers
TASKS_RAW=$(grep -n '^\- \[ \]' memory/evolution/QUEUE.md)
TASK_COUNT=$(echo "$TASKS_RAW" | grep -c '^')

if [ "$TASK_COUNT" -eq 0 ]; then
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

# Score each task using attention-based salience
# Higher scores = more important/relevant/urgent
score_task() {
    local task="$1"
    local score=0.5
    
    # Importance keywords (higher = more important for AGI/consciousness)
    if echo "$task" | grep -qi "AGI\|consciousness\|attention\|working.memory\|self.model\|reasoning\|Phi\|neural"; then
        score=$(echo "$score + 0.3" | bc -l)
    fi
    
    # Priority keywords (P0 = higher)
    if echo "$task" | grep -qi "wire\|integrate\|persistent\|feedback.loop"; then
        score=$(echo "$score + 0.15" | bc -l)
    fi
    
    # Action keywords (concrete = higher)
    if echo "$task" | grep -qi "build\|create\|implement\|add\|wire\|make"; then
        score=$(echo "$score + 0.1" | bc -l)
    fi
    
    # Cap at 1.0
    score=$(echo "$score" | bc -l)
    if (( $(echo "$score > 1.0" | bc -l) )); then
        score=1.0
    fi
    
    printf "%.2f" "$score"
}

# Score all tasks and find the highest-scoring one
BEST_TASK=""
BEST_SCORE=0

while IFS= read -r line; do
    task_num=$(echo "$line" | cut -d: -f1)
    task_text=$(echo "$line" | sed 's/^[0-9]*: \- \[ \] //')
    
    score=$(score_task "$task_text")
    
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] TASK SCORE: $score — ${task_text:0:60}..." >> "$LOGFILE"
    
    # Compare scores (bc returns 1 if first > second)
    if (( $(echo "$score > $BEST_SCORE" | bc -l) )); then
        BEST_SCORE="$score"
        BEST_TASK="$task_text"
    fi
done <<< "$TASKS_RAW"

if [ -z "$BEST_TASK" ]; then
    # Fallback: just pick first task
    BEST_TASK=$(echo "$TASKS_RAW" | head -1 | sed 's/^[0-9]*: \- \[ \] //')
    BEST_SCORE="0.50 (fallback)"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SELECTED (salience=$BEST_SCORE): ${BEST_TASK:0:80}..." >> "$LOGFILE"

NEXT_TASK="$BEST_TASK"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING: $NEXT_TASK" >> "$LOGFILE"

# Spawn Claude Code to work on the task (10 min timeout)
# Capture output and exit code for evolution loop
TASK_OUTPUT_FILE=$(mktemp)
timeout 600 /home/agent/.local/bin/claude -p \
    "You are Clarvis's executive function. Execute this evolution task:

    TASK: $NEXT_TASK

    CONTEXT: Read memory/evolution/QUEUE.md for full context. Use brain.py for memory.
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
    --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?

# Log the output
cat "$TASK_OUTPUT_FILE" >> "$LOGFILE"

if [ $TASK_EXIT -eq 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] COMPLETED: $NEXT_TASK" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] FAILED (exit $TASK_EXIT): $NEXT_TASK" >> "$LOGFILE"

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
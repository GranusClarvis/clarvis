#!/bin/bash
# Autonomous Evolution Loop — Clarvis Executive Function
# Runs every 30 minutes. Picks next evolution task. Executes it.

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

# Find next unchecked task from QUEUE.md (P0 first, then P1, then P2)
NEXT_TASK=$(grep -m1 '^\- \[ \]' memory/evolution/QUEUE.md | sed 's/^- \[ \] //')

if [ -z "$NEXT_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No pending tasks in QUEUE.md" >> "$LOGFILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] EXECUTING: $NEXT_TASK" >> "$LOGFILE"

# Spawn Claude Code to work on the task (10 min timeout)
timeout 600 /home/agent/.local/bin/claude -p \
    "You are Clarvis's executive function. Execute this evolution task:
    
    TASK: $NEXT_TASK
    
    CONTEXT: Read memory/evolution/QUEUE.md for full context. Use brain.py for memory.
    Do the work. Be concrete. Write code if needed. Test it.
    When done, output a 1-line summary of what you accomplished." \
    --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] COMPLETED: $NEXT_TASK" >> "$LOGFILE"

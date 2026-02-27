#!/bin/bash
# Morning reasoning - plan the day with Claude Code
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/morning.log"
LOCKFILE="/tmp/clarvis_morning.lock"

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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine started ===" >> "$LOGFILE"

# Step 0: Session open — restore attention state and working memory from previous session
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running session open..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/session_hook.py open >> "$LOGFILE" 2>&1

# === MORNING PLANNING (with context from prompt_builder) ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running morning planning..." >> "$LOGFILE"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"
MORNING_PROMPT=$(python3 "$SCRIPTS/prompt_builder.py" build \
    --task "It's morning. Pick top 3 priorities for today from the pending tasks. Update brain.set_context() with today's focus. Output: 3 priorities with brief reasoning." \
    --role "morning planner" --tier standard 2>> "$LOGFILE")
MORNING_PROMPT_FILE=$(mktemp)
echo "$MORNING_PROMPT" > "$MORNING_PROMPT_FILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Prompt: ${#MORNING_PROMPT} bytes" >> "$LOGFILE"
MORNING_OUTPUT_FILE=$(mktemp)
timeout 600 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    /home/agent/.local/bin/claude -p "$(cat "$MORNING_PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 > "$MORNING_OUTPUT_FILE" 2>&1
rm -f "$MORNING_PROMPT_FILE"
cat "$MORNING_OUTPUT_FILE" >> "$LOGFILE"

# === DIGEST: Write first-person summary for M2.5 agent ===
PRIORITIES=$(tail -c 500 "$MORNING_OUTPUT_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 400)
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py morning "I started my day and reviewed the evolution queue. $PRIORITIES" >> "$LOGFILE" 2>&1 || true
rm -f "$MORNING_OUTPUT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine complete ===" >> "$LOGFILE"

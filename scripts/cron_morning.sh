#!/bin/bash
# Morning reasoning - plan the day with Claude Code
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/morning.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine started ===" >> "$LOGFILE"

# Step 0: Session open — restore attention state and working memory from previous session
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running session open..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/session_hook.py open >> "$LOGFILE" 2>&1

# === MORNING PLANNING ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running morning planning..." >> "$LOGFILE"
/home/agent/.local/bin/claude -p "It's morning. Review evolution/QUEUE.md, pick top 3 priorities for today. Update brain.set_context() with today's focus. Output: 3 priorities with brief reasoning." --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine complete ===" >> "$LOGFILE"

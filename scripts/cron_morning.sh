#!/bin/bash
# Morning reasoning - plan the day with Claude Code
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/morning.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine started ===" >> "$LOGFILE"

# === MORNING PLANNING ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running morning planning..." >> "$LOGFILE"
/home/agent/.local/bin/claude -p "It's morning. Review evolution/QUEUE.md, pick top 3 priorities for today. Update brain.set_context() with today's focus. Output: 3 priorities with brief reasoning." --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine complete ===" >> "$LOGFILE"

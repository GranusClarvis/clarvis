#!/bin/bash
# Morning reasoning - plan the day with Claude Code
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
/home/agent/.local/bin/claude -p "It's morning. Review evolution/QUEUE.md, pick top 3 priorities for today. Update brain.set_context() with today's focus. Output: 3 priorities with brief reasoning." --dangerously-skip-permissions >> /home/agent/.openclaw/workspace/memory/cron_morning.log 2>&1

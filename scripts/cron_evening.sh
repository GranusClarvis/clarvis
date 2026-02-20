#!/bin/bash
# Evening code review - audit today's work
cd /home/agent/.openclaw/workspace
/home/agent/.local/bin/claude -p "Review today's work: check git status, memory/$(date +%Y-%m-%d).md, any errors in logs. What's working? Any bugs? Output: brief audit + 1 fix if needed." --dangerously-skip-permissions >> /home/agent/.openclaw/workspace/memory/cron_evening.log 2>&1

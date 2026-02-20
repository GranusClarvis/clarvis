#!/bin/bash
# Deep evolution thinking with Claude Code
cd /home/agent/.openclaw/workspace
/home/agent/.local/bin/claude -p "Analyze progress toward AGI/consciousness. Check brain.goals(), evolution/QUEUE.md, recent learnings. What's working? What's not? Suggest 1 concrete experiment or improvement. Output: analysis + recommendation." --dangerously-skip-permissions >> /home/agent/.openclaw/workspace/memory/cron_evolution.log 2>&1

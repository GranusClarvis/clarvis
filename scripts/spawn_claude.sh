#!/bin/bash
# Proper Claude Code spawner - use this instead of sessions_spawn
# Usage: ./spawn_claude.sh "task description" [timeout_seconds]

TASK="${1:-}"
TIMEOUT="${2:-600}"

if [ -z "$TASK" ]; then
    echo "Usage: ./spawn_claude.sh 'task description' [timeout]"
    exit 1
fi

cd /home/agent/.openclaw/workspace

# Create temp file for prompt (avoids shell parsing issues)
echo "$TASK" > /tmp/claude_prompt_$$.txt

# Spawn Claude Code with proper settings
timeout "$TIMEOUT" claude -p "$(cat /tmp/claude_prompt_$$.txt)" \
    --dangerously-skip-permissions \
    --model claude-opus-4-6 \
    --output-format json

RESULT=$?
rm -f /tmp/claude_prompt_$$.txt
exit $RESULT

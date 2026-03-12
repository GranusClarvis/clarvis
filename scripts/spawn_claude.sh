#!/bin/bash
# =============================================================================
# Proper Claude Code spawner — the ONLY correct way to spawn Claude Code
# Usage: ./spawn_claude.sh "task description" [timeout_seconds] [--no-tg] [--isolated] [--category=CAT] [--topic=N] [--chat=ID]
# --category: quick=600s, standard=1200s, research=1800s, build=1800s (overrides default timeout)
#
# NEVER use sessions_spawn — that spawns M2.5, not Claude Code.
# This script uses the claude CLI directly, with proper env, full paths,
# output capture, and Telegram delivery (matching cron_autonomous pattern).
#
# --isolated: Run in git worktree isolation (changes don't affect main until merged)
# =============================================================================

set -euo pipefail

# Source cron env for proper PATH, HOME, env cleanup
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

TASK="${1:-}"
TIMEOUT="${2:-1200}"
SEND_TG="true"
ISOLATED="false"
TG_TOPIC=""
TG_CHAT_ID="REDACTED_CHAT_ID"
CATEGORY=""
# Parse optional flags from args 3+
for arg in "${@:3}"; do
    case "$arg" in
        --no-tg)      SEND_TG="false" ;;
        --isolated)   ISOLATED="true" ;;
        --topic=*)    TG_TOPIC="${arg#--topic=}" ;;
        --chat=*)     TG_CHAT_ID="${arg#--chat=}" ;;
        --category=*) CATEGORY="${arg#--category=}" ;;
    esac
done

# Category-based timeout: overrides default when no explicit timeout was given
if [ -n "$CATEGORY" ] && [ "$TIMEOUT" = "1200" ]; then
    case "$CATEGORY" in
        quick)    TIMEOUT=600 ;;
        standard) TIMEOUT=1200 ;;
        research) TIMEOUT=1800 ;;
        build)    TIMEOUT=1800 ;;
        *)        echo "WARN: Unknown category '$CATEGORY', using default ${TIMEOUT}s" ;;
    esac
fi

if [ -z "$TASK" ]; then
    echo "Usage: ./spawn_claude.sh 'task description' [timeout] [--no-tg] [--isolated] [--category=CAT] [--topic=N] [--chat=ID]"
    echo "Default timeout: 1200s (20 min). Use --no-tg to skip Telegram delivery."
    echo "Use --isolated to run in git worktree isolation."
    echo "Use --category=CAT to set timeout by task type: quick=600s, standard=1200s, research=1800s, build=1800s."
    echo "Use --topic=N to deliver output to a specific Telegram topic thread."
    echo "Use --chat=ID to deliver to a specific chat (default: DM REDACTED_CHAT_ID)."
    exit 1
fi

PROMPT_FILE="/tmp/claude_prompt_$$.txt"
OUTPUT_FILE="/tmp/claude_output_$$.txt"
LOGFILE="/home/agent/.openclaw/workspace/memory/cron/spawn_claude.log"
WORK_DIR="/home/agent/.openclaw/workspace"
WORKTREE_PATH=""
WORKTREE_BRANCH=""

# === Worktree Isolation ===
if [ "$ISOLATED" = "true" ]; then
    AGENT_ID="spawn-$(date +%m%d%H%M)-$$"
    WORKTREE_PATH="/home/agent/.openclaw/workspace/.claude/worktrees/$AGENT_ID"
    WORKTREE_BRANCH="agent/$AGENT_ID"
    mkdir -p /home/agent/.openclaw/workspace/.claude/worktrees

    git -C /home/agent/.openclaw/workspace worktree add -b "$WORKTREE_BRANCH" "$WORKTREE_PATH" HEAD 2>> "$LOGFILE"
    if [ $? -eq 0 ]; then
        WORK_DIR="$WORKTREE_PATH"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: worktree=$WORKTREE_PATH branch=$WORKTREE_BRANCH" >> "$LOGFILE"
    else
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] WARN: worktree creation failed, falling back to main" >> "$LOGFILE"
        ISOLATED="false"
        WORKTREE_PATH=""
    fi
fi

# Get context brief from prompt builder (enriches prompt with brain, goals, episodes)
SCRIPTS_DIR="/home/agent/.openclaw/workspace/scripts"
CONTEXT_BRIEF=$(python3 "$SCRIPTS_DIR/prompt_builder.py" context-brief --task "$TASK" --tier standard 2>/dev/null || echo "")

# Write prompt to file using Python (shell-safe; avoids quoting issues)
python3 - "$TASK" "$WORK_DIR" "$CONTEXT_BRIEF" "$PROMPT_FILE" <<'PY'
import sys

task = sys.argv[1]
work_dir = sys.argv[2]
context = sys.argv[3]
prompt_file = sys.argv[4]

parts = ["You are Clarvis's executive function (Claude Code Opus).", ""]
if context:
    parts += ["CONTEXT:", context, ""]

parts += [
    f"TASK: {task}",
    "",
    f"Work in {work_dir} unless the task specifies another directory.",
    "Be thorough. Write code if needed. Test it. Report what you did concisely.",
]

with open(prompt_file, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))
PY

CATEGORY_TAG="${CATEGORY:+(category=$CATEGORY)}"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Spawning with ${TIMEOUT}s timeout ${CATEGORY_TAG}..." >> "$LOGFILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Task: ${TASK:0:100}..." >> "$LOGFILE"

# Acquire global Claude lock — prevent concurrent Claude Code spawns
LOGFILE="/tmp/spawn_claude_$$.log"
acquire_global_claude_lock "$LOGFILE"

# Immediate stdout feedback — so exec() monitoring sees output (prevents SIGTERM from no-output watchdog)
echo "[spawn_claude] Spawned with ${TIMEOUT}s timeout ${CATEGORY_TAG}. Task: ${TASK:0:80}"
echo "[spawn_claude] Output will be delivered via Telegram when complete."

# Belt-and-suspenders: forcibly unset Claude Code nesting guards
# (cron_env.sh already does this, but extra safety for manual invocations)
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Spawn Claude Code — setsid detaches from parent process group (prevents SIGTERM from
# OpenClaw exec() killing Claude Code when it doesn't see output for >480s)
# Capture exit code without letting set -e kill the script
RESULT=0
setsid timeout "$TIMEOUT" env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    /home/agent/.local/bin/claude -p "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions \
    --model claude-opus-4-6 \
    > "$OUTPUT_FILE" 2>&1 || RESULT=$?
rm -f "$PROMPT_FILE"

if [ $RESULT -eq 124 ]; then
    echo "[spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "$OUTPUT_FILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "$LOGFILE"
elif [ $RESULT -ne 0 ]; then
    echo "[spawn_claude] FAILED with exit code $RESULT" >> "$OUTPUT_FILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] FAILED exit=$RESULT" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Completed successfully" >> "$LOGFILE"
fi

# Log output (truncated)
tail -c 2000 "$OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

# === Telegram Delivery ===
if [ "$SEND_TG" = "true" ]; then
    # Extract last 1500 chars of output as the summary
    SUMMARY=$(tail -c 1500 "$OUTPUT_FILE" 2>/dev/null || echo "(no output)")

    python3 - "$OUTPUT_FILE" "$RESULT" "${TASK:0:80}" "$TG_CHAT_ID" "$TG_TOPIC" << 'PYEOF'
import json, urllib.request, urllib.parse, sys, os

output_file = sys.argv[1]
exit_code = int(sys.argv[2])
task_short = sys.argv[3]
chat_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "REDACTED_CHAT_ID"
topic_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else ""

# Get bot token from openclaw config
with open('/home/agent/.openclaw/openclaw.json') as f:
    config = json.load(f)
token = config['channels']['telegram']['botToken']

status = "TIMEOUT" if exit_code == 124 else ("FAIL" if exit_code != 0 else "OK")
emoji = "\u23f0" if exit_code == 124 else ("\u274c" if exit_code != 0 else "\u2705")

# Read output
try:
    with open(output_file) as f:
        content = f.read()
    summary = content[-1500:] if content else "(no output)"
except Exception:
    summary = "(output file missing)"

msg = f"{emoji} Claude Code Spawn: {status}\n\n\U0001f4cb Task: {task_short}\n\n\U0001f4dd Result:\n{summary}"

# Truncate to Telegram max (4096 chars)
if len(msg) > 4000:
    msg = msg[:3997] + "..."

params = {"chat_id": chat_id, "text": msg}
# Send to specific topic thread if provided (for forum supergroups)
if topic_id and topic_id != "1":
    params["message_thread_id"] = topic_id

data = urllib.parse.urlencode(params)
req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
try:
    urllib.request.urlopen(req, timeout=10)
    target = f"chat={chat_id}" + (f" topic={topic_id}" if topic_id else "")
    print(f"[spawn_claude] TG delivery: OK ({target})", file=sys.stderr)
except Exception as e:
    print(f"[spawn_claude] TG delivery failed: {e}", file=sys.stderr)
PYEOF
fi

# Also print to stdout for callers that capture output
cat "$OUTPUT_FILE" 2>/dev/null || true
rm -f "$OUTPUT_FILE"

# === Worktree cleanup ===
if [ "$ISOLATED" = "true" ] && [ -n "$WORKTREE_PATH" ]; then
    # Check if the worktree has changes worth keeping
    CHANGES=$(git -C "$WORKTREE_PATH" diff --stat HEAD 2>/dev/null || echo "")
    STAGED=$(git -C "$WORKTREE_PATH" diff --stat --cached HEAD 2>/dev/null || echo "")

    if [ -n "$CHANGES" ] || [ -n "$STAGED" ]; then
        # Auto-commit changes in worktree so they're preserved on the branch
        git -C "$WORKTREE_PATH" add -A 2>/dev/null || true
        git -C "$WORKTREE_PATH" commit -m "Agent work: ${TASK:0:60}" 2>/dev/null || true
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: changes committed to $WORKTREE_BRANCH" >> "$LOGFILE"
        echo "[spawn_claude] Changes saved on branch $WORKTREE_BRANCH"
        echo "[spawn_claude] Merge with: git merge $WORKTREE_BRANCH"
        echo "[spawn_claude] Or: python3 scripts/agent_lifecycle.py merge <id>"
    else
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: no changes, removing worktree" >> "$LOGFILE"
        git -C /home/agent/.openclaw/workspace worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
        git -C /home/agent/.openclaw/workspace branch -D "$WORKTREE_BRANCH" 2>/dev/null || true
    fi
fi

exit $RESULT

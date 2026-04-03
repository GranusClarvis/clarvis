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
TG_CHAT_ID="${CLARVIS_TG_CHAT_ID:-}"
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
    echo "Use --chat=ID to deliver to a specific chat (default: \$CLARVIS_TG_CHAT_ID)."
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
SPAWN_LOGFILE="/tmp/spawn_claude_$$.log"
acquire_global_claude_lock "$SPAWN_LOGFILE"

# Immediate stdout feedback — so exec() monitoring sees output (prevents SIGTERM from no-output watchdog)
echo "[spawn_claude] Spawned with ${TIMEOUT}s timeout ${CATEGORY_TAG}. Task: ${TASK:0:80}"
echo "[spawn_claude] Output will be delivered via Telegram when complete."

# The actual Claude run happens in a detached worker so the parent exec session can die
# without taking the Claude job down with it.
WORKER_SCRIPT="/tmp/spawn_claude_worker_$$.sh"
cat > "$WORKER_SCRIPT" <<EOF
#!/bin/bash
set -euo pipefail
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
GLOBAL_LOCK="/tmp/clarvis_claude_global.lock"
echo "\$\$ \$(date -u +%Y-%m-%dT%H:%M:%S)" > "\$GLOBAL_LOCK"
cleanup() {
  rm -f "\$GLOBAL_LOCK" "$WORKER_SCRIPT"
}
trap cleanup EXIT
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true
RESULT=0
run_claude_monitored "$TIMEOUT" "$OUTPUT_FILE" "$PROMPT_FILE" "/home/agent/.openclaw/workspace/memory/cron/spawn_claude.log" || RESULT=\$MONITORED_EXIT
rm -f "$PROMPT_FILE"
LOGFILE="/home/agent/.openclaw/workspace/memory/cron/spawn_claude.log"
if [ \$RESULT -eq 124 ]; then
  echo "[spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "$OUTPUT_FILE"
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "\$LOGFILE"
elif [ \$RESULT -ne 0 ]; then
  echo "[spawn_claude] FAILED with exit code \$RESULT" >> "$OUTPUT_FILE"
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] FAILED exit=\$RESULT" >> "\$LOGFILE"
else
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Completed successfully" >> "\$LOGFILE"
fi
tail -c 2000 "$OUTPUT_FILE" >> "\$LOGFILE" 2>/dev/null || true
if [ "$SEND_TG" = "true" ]; then
python3 - "$OUTPUT_FILE" "\$RESULT" "${TASK:0:80}" "$TG_CHAT_ID" "$TG_TOPIC" << 'PYEOF'
import json, urllib.request, urllib.parse, sys, os
output_file = sys.argv[1]
exit_code = int(sys.argv[2])
task_short = sys.argv[3]
chat_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else os.environ.get("CLARVIS_TG_CHAT_ID", "")
topic_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else ""
token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
if not token:
    with open('/home/agent/.openclaw/openclaw.json') as f:
        config = json.load(f)
    token = config['channels']['telegram']['botToken']
status = "TIMEOUT" if exit_code == 124 else ("FAIL" if exit_code != 0 else "OK")
emoji = "\u23f0" if exit_code == 124 else ("\u274c" if exit_code != 0 else "\u2705")
try:
    with open(output_file) as f:
        content = f.read()
    summary = content[-1500:] if content else "(no output)"
except Exception:
    summary = "(output file missing)"
msg = f"{emoji} Claude Code Spawn: {status}\n\n\U0001f4cb Task: {task_short}\n\n\U0001f4dd Result:\n{summary}"
if len(msg) > 4000:
    msg = msg[:3997] + "..."
params = {"chat_id": chat_id, "text": msg}
if topic_id and topic_id != "1":
    params["message_thread_id"] = topic_id
data = urllib.parse.urlencode(params)
req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)
PYEOF
fi
if [ "$ISOLATED" = "true" ] && [ -n "$WORKTREE_PATH" ]; then
  CHANGES=\$(git -C "$WORKTREE_PATH" diff --stat HEAD 2>/dev/null || echo "")
  STAGED=\$(git -C "$WORKTREE_PATH" diff --stat --cached HEAD 2>/dev/null || echo "")
  if [ -n "\$CHANGES" ] || [ -n "\$STAGED" ]; then
    git -C "$WORKTREE_PATH" add -A 2>/dev/null || true
    git -C "$WORKTREE_PATH" commit -m "Agent work: ${TASK:0:60}" 2>/dev/null || true
    echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: changes committed to $WORKTREE_BRANCH" >> "\$LOGFILE"

    # === Clone-Test-Verify gate (ROADMAP Phase 3.2) ===
    # Run tests in the worktree before deciding to keep or reject changes
    VERIFY_JSON=\$(python3 /home/agent/.openclaw/workspace/scripts/clone_test_verify.py verify "$WORKTREE_PATH" 2>/dev/null || echo '{"safe_to_promote": false}')
    SAFE=\$(echo "\$VERIFY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('safe_to_promote', False))" 2>/dev/null || echo "False")
    if [ "\$SAFE" = "True" ]; then
      echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] VERIFY: PASS — worktree $WORKTREE_BRANCH safe to promote" >> "\$LOGFILE"
    else
      echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] VERIFY: FAIL — worktree $WORKTREE_BRANCH has test failures (changes preserved for review)" >> "\$LOGFILE"
    fi
  else
    echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: no changes, removing worktree" >> "\$LOGFILE"
    git -C /home/agent/.openclaw/workspace worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
    git -C /home/agent/.openclaw/workspace branch -D "$WORKTREE_BRANCH" 2>/dev/null || true
  fi
fi
rm -f "$OUTPUT_FILE"
exit \$RESULT
EOF
chmod +x "$WORKER_SCRIPT"
nohup "$WORKER_SCRIPT" >/dev/null 2>&1 &
WORKER_PID=$!
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Worker detached pid=$WORKER_PID" >> "/home/agent/.openclaw/workspace/memory/cron/spawn_claude.log"
# Note: global lock is written by the worker (line ~132) which also owns cleanup.
# Do NOT write it here — that causes a race between parent and worker.

# Parent exits immediately; detached worker handles Claude, Telegram delivery, and cleanup.
exit 0

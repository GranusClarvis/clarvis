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

# Resolve workspace/script roots before sourcing env; supports direct invocation
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$(cd -- "$SCRIPT_DIR/../.." && pwd)}"
export CLARVIS_WORKSPACE
SCRIPTS_DIR="$CLARVIS_WORKSPACE/scripts"

# Source cron env for proper PATH, HOME, env cleanup
source "$SCRIPTS_DIR/cron/cron_env.sh"
source "$SCRIPTS_DIR/cron/lock_helper.sh"

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
TASK_FILE="/tmp/claude_task_$$.txt"
LOGFILE="$CLARVIS_WORKSPACE/memory/cron/spawn_claude.log"
WORK_DIR="$CLARVIS_WORKSPACE"
WORKTREE_PATH=""
WORKTREE_BRANCH=""

# === Worktree Isolation ===
if [ "$ISOLATED" = "true" ]; then
    AGENT_ID="spawn-$(date +%m%d%H%M)-$$"
    WORKTREE_PATH="$CLARVIS_WORKSPACE/.claude/worktrees/$AGENT_ID"
    WORKTREE_BRANCH="agent/$AGENT_ID"
    mkdir -p "$CLARVIS_WORKSPACE/.claude/worktrees"

    git -C "$CLARVIS_WORKSPACE" worktree add -b "$WORKTREE_BRANCH" "$WORKTREE_PATH" HEAD 2>> "$LOGFILE"
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
SCRIPTS_DIR="$CLARVIS_WORKSPACE/scripts"
CONTEXT_BRIEF=$(python3 "$SCRIPTS_DIR/tools/prompt_builder.py" context-brief --task "$TASK" --tier standard 2>> "$LOGFILE" || echo "")

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

# Queue V2: register external run if task has a [TAG]
QUEUE_RUN_ID=$(python3 -c "
from clarvis.queue.engine import engine
rid = engine.start_external_run('''${TASK//\'/\'\\\'\'}''', source='manual_spawn')
print(rid or '')
" 2>/dev/null || echo "")
if [ -n "$QUEUE_RUN_ID" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Queue V2: started run $QUEUE_RUN_ID" >> "$LOGFILE"
fi

# Phase 0 audit trace — one per real Claude spawn. Fail-open.
CLARVIS_AUDIT_TRACE_ID=$(python3 -c "
import sys
try:
    from clarvis.audit import start_trace, toggle_snapshot
    tid = start_trace(
        source='spawn_claude',
        cron_origin='${CRON_ORIGIN:-spawn_claude.sh}',
        queue_run_id='${QUEUE_RUN_ID:-}',
        task={'text': '''${TASK//\'/\'\\\'\'}'''[:500], 'category': '${CATEGORY:-}'},
        feature_toggles=toggle_snapshot(),
    )
    sys.stdout.write(tid or '')
except Exception:
    sys.stdout.write('')
" 2>/dev/null || echo "")
export CLARVIS_AUDIT_TRACE_ID
if [ -n "$CLARVIS_AUDIT_TRACE_ID" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] audit_trace_id=$CLARVIS_AUDIT_TRACE_ID" >> "$LOGFILE"
fi

# === Global Claude lock: pre-check only (no parent acquisition) ===
# The lock is owned end-to-end by the detached worker: worker writes it on
# startup, cleans it in its EXIT trap. The parent never owns the lock so there
# is no window where parent's EXIT trap could delete it before the worker has
# written its own PID. This closes the P0_SPAWN_CLAUDE_LOCK_HANDOFF_RACE.
#
# To prevent two spawners from both passing pre-check and both launching a
# worker, we atomically claim the lock with the worker's PID immediately after
# detaching it, using O_EXCL (set -C / noclobber). If we lose that race, we
# abort our worker and report DEFERRED instead of silently exit 0.
SPAWN_LOGFILE="/tmp/spawn_claude_$$.log"
EX_DEFERRED=75  # EX_TEMPFAIL — caller should retry later

_spawn_report_deferred() {
    # $1=reason_label  $2=gpid  $3=gage_seconds
    local label="$1" gpid="${2:-?}" gage="${3:-?}"
    local status="DEFERRED" queue_ok="no"
    if python3 -m clarvis queue add \
         "Deferred spawn_claude: ${TASK:0:120}" \
         --priority P0 --source spawn_claude_overlap_guard \
         >> "$LOGFILE" 2>&1; then
        status="QUEUED"
        queue_ok="yes"
    fi
    local msg="[spawn_claude] ${status}: ${label} (PID ${gpid}, age=${gage}s) — task NOT_STARTED. queue=${queue_ok}"
    echo "$msg"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] $msg" >> "$LOGFILE"
    if [ -n "${QUEUE_RUN_ID:-}" ]; then
        python3 -c "
from clarvis.queue.engine import engine
engine.end_run('$QUEUE_RUN_ID', outcome='deferred', exit_code=$EX_DEFERRED, duration_s=0)
" >> "$LOGFILE" 2>&1 || true
    fi
    if [ -n "${CLARVIS_AUDIT_TRACE_ID:-}" ]; then
        python3 -c "
from clarvis.audit import finalize_trace
finalize_trace('$CLARVIS_AUDIT_TRACE_ID', outcome='deferred', exit_code=$EX_DEFERRED, duration_s=0.0, extra={'execution': {'deferred_reason': '$label'}})
" >> "$LOGFILE" 2>&1 || true
    fi
    rm -f "$PROMPT_FILE" "$TASK_FILE" 2>/dev/null || true
}

if [ -f "$GLOBAL_LOCK" ]; then
    GPID=$(_read_lock_pid "$GLOBAL_LOCK")
    GAGE=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
    if [ -n "$GPID" ] && _is_clarvis_process "$GPID" && [ "$GAGE" -le 2400 ]; then
        _spawn_report_deferred "global Claude lock held" "$GPID" "$GAGE"
        exit $EX_DEFERRED
    else
        # Orphaned (dead PID, non-clarvis, or aged past 2400s) — safe to reclaim.
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Reclaiming stale global lock (PID=${GPID:-?}, age=${GAGE}s)" >> "$LOGFILE"
        rm -f "$GLOBAL_LOCK"
    fi
fi

# Immediate stdout feedback — so exec() monitoring sees output (prevents SIGTERM from no-output watchdog)
echo "[spawn_claude] Spawned with ${TIMEOUT}s timeout ${CATEGORY_TAG}. Task: ${TASK:0:80}"
echo "[spawn_claude] Output will be delivered via Telegram when complete."

# Save task text to file — avoids shell quoting issues in the heredoc
printf '%s' "${TASK:0:120}" > "$TASK_FILE"

# The actual Claude run happens in a detached worker so the parent exec session can die
# without taking the Claude job down with it.
WORKER_SCRIPT="/tmp/spawn_claude_worker_$$.sh"
WORKER_LOG="/tmp/spawn_claude_worker_$$.log"
cat > "$WORKER_SCRIPT" <<EOF
#!/bin/bash
set -euo pipefail
source "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"/scripts/cron/cron_env.sh
GLOBAL_LOCK="/tmp/clarvis_claude_global.lock"
_worker_owns_lock() {
  # Parent atomically wrote the lock with our PID before exec'ing us.
  # Verify the lock still names us before touching it (prevents deleting a
  # lock installed by a winner in a lost-race scenario).
  [ -f "\$GLOBAL_LOCK" ] || return 1
  local owner
  owner=\$(awk 'NR==1{print \$1}' "\$GLOBAL_LOCK" 2>/dev/null)
  [ "\$owner" = "\$\$" ]
}
if ! _worker_owns_lock; then
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude_worker] ABORT: global lock not owned by PID \$\$ — lost race, exiting without cleanup" >> "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/memory/cron/spawn_claude.log"
  rm -f "$WORKER_SCRIPT" "$PROMPT_FILE" "$TASK_FILE" "$OUTPUT_FILE" "$WORKER_LOG" 2>/dev/null || true
  exit 0
fi
cleanup() {
  # Only remove the global lock if we still own it.
  if _worker_owns_lock; then
    rm -f "\$GLOBAL_LOCK"
  fi
  rm -f "$WORKER_SCRIPT" "$OUTPUT_FILE" "$TASK_FILE" "$WORKER_LOG"
}
trap cleanup EXIT
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true
RESULT=0
START_EPOCH=\$(date +%s)
run_claude_monitored "$TIMEOUT" "$OUTPUT_FILE" "$PROMPT_FILE" "$CLARVIS_WORKSPACE/memory/cron/spawn_claude.log" || RESULT=\$MONITORED_EXIT
END_EPOCH=\$(date +%s)
DURATION=\$(( END_EPOCH - START_EPOCH ))
rm -f "$PROMPT_FILE"
LOGFILE="$CLARVIS_WORKSPACE/memory/cron/spawn_claude.log"
if [ \$RESULT -eq 124 ]; then
  echo "[spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "$OUTPUT_FILE"
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] TIMEOUT after ${TIMEOUT}s" >> "\$LOGFILE"
elif [ \$RESULT -ne 0 ]; then
  echo "[spawn_claude] FAILED with exit code \$RESULT" >> "$OUTPUT_FILE"
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] FAILED exit=\$RESULT" >> "\$LOGFILE"
else
  echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Completed successfully" >> "\$LOGFILE"
fi
# Queue V2: close run record if one was started
if [ -n "$QUEUE_RUN_ID" ]; then
  python3 -c "
from clarvis.queue.engine import engine
engine.end_run('$QUEUE_RUN_ID', outcome='success' if \$RESULT == 0 else ('timeout' if \$RESULT == 124 else 'failure'), exit_code=\$RESULT, duration_s=\$DURATION)
" 2>/dev/null && echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Queue V2: ended run $QUEUE_RUN_ID (\$RESULT)" >> "\$LOGFILE" || true
fi
# Phase 0 audit: finalize the trace with terminal outcome.
if [ -n "${CLARVIS_AUDIT_TRACE_ID:-}" ]; then
  python3 - "\$RESULT" "\$DURATION" "$OUTPUT_FILE" <<'PYEOF' 2>> "\$LOGFILE" || true
import os, sys
exit_code = int(sys.argv[1])
duration_s = float(sys.argv[2] or 0)
output_file = sys.argv[3]
tail = ""
try:
    with open(output_file) as f:
        tail = f.read()[-2000:]
except Exception:
    pass
outcome = "success" if exit_code == 0 else ("timeout" if exit_code == 124 else "failure")
try:
    from clarvis.audit import finalize_trace, update_trace
    tid = os.environ.get("CLARVIS_AUDIT_TRACE_ID", "")
    update_trace(tid, execution={"output_tail": tail, "exit_code": exit_code, "duration_s": duration_s})
    finalize_trace(tid, outcome=outcome, exit_code=exit_code, duration_s=duration_s)
except Exception as e:
    sys.stderr.write(f"[spawn_claude audit finalize failed] {e}\n")
PYEOF
fi
tail -c 2000 "$OUTPUT_FILE" >> "\$LOGFILE" 2>/dev/null || true
# === TELEGRAM DELIVERY ===
# Disable errexit for delivery/cleanup — these are best-effort, must not kill the worker
set +e
if [ "$SEND_TG" = "true" ]; then
  TASK_SHORT=\$(cat "$TASK_FILE" 2>/dev/null || echo "(task text unavailable)")
  python3 - "$OUTPUT_FILE" "\$RESULT" "\$TASK_SHORT" "$TG_CHAT_ID" "$TG_TOPIC" "\$LOGFILE" << 'PYEOF'
import json, urllib.request, urllib.parse, sys, os

logfile = sys.argv[6] if len(sys.argv) > 6 else ""

def log(msg):
    if logfile:
        try:
            with open(logfile, "a") as f:
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                f.write(f"[{ts}] [spawn_claude] {msg}\n")
        except Exception:
            pass

try:
    output_file = sys.argv[1]
    exit_code = int(sys.argv[2])
    task_short = sys.argv[3]
    chat_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else os.environ.get("CLARVIS_TG_CHAT_ID", "")
    topic_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else ""
    token = os.environ.get("CLARVIS_TG_BOT_TOKEN", "")
    if not token:
        try:
            _oc = os.environ.get('OPENCLAW_HOME', os.path.expanduser('~/.openclaw'))
            with open(os.path.join(_oc, 'openclaw.json')) as f:
                config = json.load(f)
            token = config['channels']['telegram']['botToken']
        except Exception as e:
            log(f"TG SKIP: no token (env empty, openclaw.json failed: {e})")
            sys.exit(0)
    if not chat_id:
        log("TG SKIP: no chat_id configured")
        sys.exit(0)

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
    resp = urllib.request.urlopen(req, timeout=15)
    log(f"TG OK: {status} delivered to chat={chat_id} (HTTP {resp.status})")
except Exception as e:
    log(f"TG FAIL: {e}")
PYEOF
fi
if [ "$ISOLATED" = "true" ] && [ -n "$WORKTREE_PATH" ]; then
  CHANGES=\$(git -C "$WORKTREE_PATH" diff --stat HEAD 2>/dev/null || echo "")
  STAGED=\$(git -C "$WORKTREE_PATH" diff --stat --cached HEAD 2>/dev/null || echo "")
  if [ -n "\$CHANGES" ] || [ -n "\$STAGED" ]; then
    git -C "$WORKTREE_PATH" add -A 2>/dev/null || true
    git -C "$WORKTREE_PATH" commit -m "Agent work: \$(cat "$TASK_FILE" 2>/dev/null | head -c 60)" 2>/dev/null || true
    echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: changes committed to $WORKTREE_BRANCH" >> "\$LOGFILE"

    # === Clone-Test-Verify gate (ROADMAP Phase 3.2) ===
    # Run tests in the worktree before deciding to keep or reject changes
    VERIFY_JSON=\$(python3 "$CLARVIS_WORKSPACE/scripts/tools/clone_test_verify.py" verify "$WORKTREE_PATH" 2>/dev/null || echo '{"safe_to_promote": false}')
    SAFE=\$(echo "\$VERIFY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('safe_to_promote', False))" 2>/dev/null || echo "False")
    if [ "\$SAFE" = "True" ]; then
      echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] VERIFY: PASS — worktree $WORKTREE_BRANCH safe to promote" >> "\$LOGFILE"
    else
      echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] VERIFY: FAIL — worktree $WORKTREE_BRANCH has test failures (changes preserved for review)" >> "\$LOGFILE"
    fi
  else
    echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] ISOLATED: no changes, removing worktree" >> "\$LOGFILE"
    git -C "$CLARVIS_WORKSPACE" worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
    git -C "$CLARVIS_WORKSPACE" branch -D "$WORKTREE_BRANCH" 2>/dev/null || true
  fi
fi
echo "[\$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Worker cleanup complete" >> "\$LOGFILE"
exit \$RESULT
EOF
chmod +x "$WORKER_SCRIPT"
nohup "$WORKER_SCRIPT" >/dev/null 2>&1 &
WORKER_PID=$!

# Atomic lock claim (O_EXCL). If a concurrent spawner also passed pre-check
# and raced us here, noclobber redirect fails on the loser. We write the
# worker's PID so the worker's _worker_owns_lock check passes (inside the
# worker, `$$` equals `$!` here, since bash's `&` + nohup exec preserves PID).
if ! ( set -C; echo "$WORKER_PID $(date -u +%Y-%m-%dT%H:%M:%S)" > "$GLOBAL_LOCK" ) 2>/dev/null; then
    # Lost the race. Kill our worker before it writes the lock / spawns claude.
    kill "$WORKER_PID" 2>/dev/null || true
    # Give the worker a moment to die so its EXIT trap doesn't rm the lock
    # that the winner just installed.
    wait "$WORKER_PID" 2>/dev/null || true
    RACE_GPID=$(_read_lock_pid "$GLOBAL_LOCK")
    RACE_GAGE=$(( $(date +%s) - $(stat -c %Y "$GLOBAL_LOCK" 2>/dev/null || echo 0) ))
    _spawn_report_deferred "post-precheck race lost to concurrent spawn" "$RACE_GPID" "$RACE_GAGE"
    rm -f "$WORKER_SCRIPT" 2>/dev/null || true
    exit $EX_DEFERRED
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [spawn_claude] Worker detached pid=$WORKER_PID (global lock claimed atomically)" >> "$CLARVIS_WORKSPACE/memory/cron/spawn_claude.log"

# Parent exits immediately; detached worker owns the global lock (writes on
# startup, removes via EXIT trap) and handles Claude, Telegram, cleanup.
exit 0

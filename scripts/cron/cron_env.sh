#!/bin/bash
# =============================================================================
# Cron Environment Bootstrap
# =============================================================================
# Source this at the top of every cron script to get the full interactive PATH
# and environment that scripts need (python3, claude, openclaw, npm, etc.)
#
# Usage: source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
# =============================================================================

export HOME="${HOME:-$HOME}"
export PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:$HOME/.npm-global/bin:$HOME/go/bin:$HOME/.cargo/bin"
export NODE_PATH="$HOME/.npm-global/lib/node_modules"
export LANG="en_US.UTF-8"

# Prevent "nested Claude Code session" errors when cron scripts are
# triggered manually from inside a Claude Code session.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Systemd user session (required for openclaw gateway management since v2026.2.23)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

# Workspace (defined early — other sections reference $CLARVIS_WORKSPACE)
export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"

# Ensure all script subdirs are on Python path (belt-and-suspenders with _paths.py)
export PYTHONPATH="$CLARVIS_WORKSPACE/scripts${PYTHONPATH:+:$PYTHONPATH}"

# Telegram delivery (consumed by budget_alert.py, cron_report_*.sh, cron_watchdog.sh, spawn_claude.sh)
# Secrets loaded from .env file (not tracked). See .env.example for required vars.
if [ -f "$CLARVIS_WORKSPACE/.env" ]; then
    set -a; . "$CLARVIS_WORKSPACE/.env"; set +a
fi
export CLARVIS_TG_BOT_TOKEN="${CLARVIS_TG_BOT_TOKEN:-}"
export CLARVIS_TG_CHAT_ID="${CLARVIS_TG_CHAT_ID:-}"
export CLARVIS_TG_GROUP_ID="${CLARVIS_TG_GROUP_ID:-}"
export CLARVIS_TG_REPORTS_TOPIC="${CLARVIS_TG_REPORTS_TOPIC:-5}"

# Guard: reject placeholder API keys copied from .env.example
_is_placeholder() {
    case "$1" in
        *your-key-here*|*your-*-here*|*your-personal-*|*your-group-*|\
        *example*|*placeholder*|*CHANGE_ME*|*TODO*|"") return 0 ;;
        *) return 1 ;;
    esac
}
if _is_placeholder "${OPENROUTER_API_KEY:-}"; then
    export OPENROUTER_API_KEY=""
fi
if _is_placeholder "${CLARVIS_TG_BOT_TOKEN:-}"; then
    export CLARVIS_TG_BOT_TOKEN=""
fi
if _is_placeholder "${CLARVIS_TG_CHAT_ID:-}"; then
    export CLARVIS_TG_CHAT_ID=""
fi
if _is_placeholder "${CLARVIS_TG_GROUP_ID:-}"; then
    export CLARVIS_TG_GROUP_ID=""
fi

cd "$CLARVIS_WORKSPACE" || exit 1

# Graph storage backend: SQLite (cutover finalized 2026-03-29).
# JSON graph file is archived; no longer written at runtime.
# Limit OpenBLAS/NumPy thread spawning — prevents thread exhaustion under the
# PAM nproc limit (4096 in /etc/security/limits.d/agent.conf).
export OPENBLAS_NUM_THREADS=4
export OMP_NUM_THREADS=4

export CLARVIS_GRAPH_BACKEND="sqlite"
export CLARVIS_GRAPH_DUAL_WRITE="0"

# Project Lane — operator-directed project override.
# When set, tasks tagged [PROJECT:<value>] get +0.3 scoring boost in task_selector,
# ensuring operator-assigned project work wins over internal experimentation.
# Set to empty string or unset to disable. See docs/PROJECT_LANES.md.
# Examples: "SWO", "SANCTUARY", ""
export CLARVIS_PROJECT_LANE="${CLARVIS_PROJECT_LANE:-SWO}"

# Self-repo sync policy. Controls whether sync_workspace() pulls origin/main
# into Clarvis's own workspace before cron/spawn work.
#   "skip"  — (default) do NOT auto-sync; Clarvis commits/pushes directly
#             to main, so pulling could conflict with in-flight work.
#   "auto"  — ff-only pull from origin/main (old behavior). Safe when
#             Clarvis is only consuming, not authoring, commits on main.
# Project-agent workspaces use their own aggressive sync
# (_sync_and_checkout_work_branch / worktree_create) and are NOT affected
# by this variable.
export CLARVIS_SELF_SYNC="${CLARVIS_SELF_SYNC:-skip}"

# Shared helper: get current weakest performance metric (fast, reads cached file)
get_weakest_metric() {
    python3 "$CLARVIS_WORKSPACE/scripts/metrics/performance_benchmark.py" weakest 2>/dev/null || echo "unknown"
}

# Check if a PID belongs to a clarvis/claude process via /proc/<pid>/cmdline.
# Returns 0 if alive + ours, 1 if dead or PID recycled.
# Usage: check_pid_is_clarvis "$pid" && echo "alive" || echo "dead/recycled"
check_pid_is_clarvis() {
    local pid="$1"
    [ -z "$pid" ] && return 1
    kill -0 "$pid" 2>/dev/null || return 1
    local cmdline_file="/proc/$pid/cmdline"
    if [ -f "$cmdline_file" ]; then
        local cmdline
        cmdline=$(tr '\0' ' ' < "$cmdline_file" 2>/dev/null) || return 1
        echo "$cmdline" | grep -qE 'clarvis|claude|cron_(autonomous|morning|evening|evolution|reflection|research|implementation|strategic|cleanup|orchestrator|report|graph|chromadb)' && return 0
        return 1  # PID recycled — not a clarvis process
    fi
    return 0  # /proc not available — trust kill -0
}

# Run Claude Code with execution monitor (background launch + progress tracking).
# The monitor detects stuck processes and can SIGTERM them at 90% timeout.
# Sets MONITORED_EXIT to the Claude process exit code.
# Writes <output_file>.progress.json for postflight consumption.
#
# Usage: run_claude_monitored <timeout_secs> <output_file> <prompt_file_or_string> [logfile]
run_claude_monitored() {
    local _timeout="$1"
    local _output_file="$2"
    local _prompt="$3"
    local _logfile="${4:-/dev/null}"
    local _scripts="$CLARVIS_WORKSPACE/scripts"

    # Ensure prompt is in a file to avoid ARG_MAX for large prompts.
    # If caller passed a file path, use it directly; otherwise write to temp file.
    local _prompt_file _owns_prompt_file=0
    if [ -f "$_prompt" ]; then
        _prompt_file="$_prompt"
    else
        _prompt_file="$(mktemp /tmp/clarvis_prompt_XXXXXX.txt)"
        printf '%s' "$_prompt" > "$_prompt_file"
        _owns_prompt_file=1
    fi

    # Budget kill switch: skip launch when budget freeze is active
    local _budget_freeze="/tmp/clarvis_budget_freeze"
    if [ -f "$_budget_freeze" ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] BUDGET_FREEZE: skipping Claude invocation (${_budget_freeze} exists)" >> "$_logfile"
        [ "$_owns_prompt_file" -eq 1 ] && rm -f "$_prompt_file"
        MONITORED_EXIT=1
        return 1
    fi

    # Validate prompt is non-empty
    if [ ! -s "$_prompt_file" ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PROMPT_GUARD: prompt file is empty — aborting Claude invocation" >> "$_logfile"
        [ "$_owns_prompt_file" -eq 1 ] && rm -f "$_prompt_file"
        MONITORED_EXIT=1
        return 1
    fi

    # Launch Claude Code in background with JSON output for token capture.
    # stderr → output_file (monitor watches this); stdout (JSON) → .json sidecar.
    local _json_file="${_output_file}.json"
    timeout "$_timeout" env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        ${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")} -p \
        --dangerously-skip-permissions --model claude-opus-4-7 \
        --output-format json \
        < "$_prompt_file" > "$_json_file" 2>"$_output_file" &
    local _claude_pid=$!

    # Launch execution monitor in background
    python3 "$_scripts/pipeline/execution_monitor.py" "$_output_file" "$_timeout" "$_claude_pid" >> "$_logfile" 2>&1 &
    local _monitor_pid=$!

    # Wait for Claude (monitor may SIGTERM it before timeout)
    wait "$_claude_pid"
    MONITORED_EXIT=$?

    # Clean up monitor
    kill "$_monitor_pid" 2>/dev/null
    wait "$_monitor_pid" 2>/dev/null

    # Extract text result from JSON output and capture token usage.
    # On parse failure (timeout, crash), fall back to raw stderr output.
    local _source
    _source="${CRON_SOURCE:-$(basename "${BASH_SOURCE[1]:-$0}" .sh 2>/dev/null || echo unknown)}"
    python3 - "$_json_file" "$_output_file" "$_source" <<'EXTRACT_PY' >> "$_logfile" 2>&1 || true
import json, sys, os
json_file, output_file, source = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(json_file) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

result_text = data.get("result", "")
if result_text:
    stderr_content = ""
    try:
        with open(output_file) as f:
            stderr_content = f.read()
    except Exception:
        pass
    with open(output_file, "w") as f:
        f.write(result_text)
        if stderr_content.strip():
            f.write("\n\n--- stderr ---\n" + stderr_content)

usage = data.get("usage", {})
total_cost = data.get("total_cost_usd")
input_tokens = usage.get("input_tokens", 0)
cache_create = usage.get("cache_creation_input_tokens", 0)
cache_read = usage.get("cache_read_input_tokens", 0)
output_tokens = usage.get("output_tokens", 0)
total_input = input_tokens + cache_create + cache_read

if total_cost is not None and total_input > 0:
    try:
        ws = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
        from clarvis.orch.cost_tracker import CostTracker
        tracker = CostTracker(os.path.join(ws, "data", "costs.jsonl"))
        duration_ms = data.get("duration_ms", 0)
        audit_trace_id = os.environ.get("CLARVIS_AUDIT_TRACE_ID", "")
        tracker.log_real(
            model="claude-code",
            input_tokens=total_input,
            output_tokens=output_tokens,
            cost_usd=total_cost,
            source=source,
            task="",
            duration_s=duration_ms / 1000.0,
            generation_id=data.get("session_id", ""),
            audit_trace_id=audit_trace_id,
        )
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[{ts}] TOKEN_CAPTURE: in={total_input} out={output_tokens} cost=${total_cost:.4f} (cache_create={cache_create} cache_read={cache_read})")
    except Exception as e:
        print(f"TOKEN_CAPTURE: cost logging failed: {e}")
EXTRACT_PY
    rm -f "$_json_file"

    # Check reconsider file
    local _reconsider_file="${_output_file}.reconsider.json"
    if [ -f "$_reconsider_file" ]; then
        local _recon_info
        _recon_info=$(python3 -c "
import json
with open('$_reconsider_file') as f:
    d = json.load(f)
print(f\"reason={d.get('reason','?')} aborted={d.get('aborted',False)}\")
" 2>/dev/null || echo "reason=unknown aborted=unknown")
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] MONITOR: RECONSIDER $_recon_info" >> "$_logfile"
        rm -f "$_reconsider_file"
    fi

    # Capture task summary before prompt file cleanup
    local _task_head
    _task_head=$(head -c 130 "$_prompt_file" 2>/dev/null | tr '\n' ' ' || echo "")

    # Clean up temp prompt file if we created one
    [ "$_owns_prompt_file" -eq 1 ] && rm -f "$_prompt_file"

    # Log real cost checkpoint from OpenRouter API (non-blocking, best-effort)
    python3 "$CLARVIS_WORKSPACE/scripts/infra/cost_checkpoint.py" \
        "$_source" "$_task_head" "$_timeout" >> "$_logfile" 2>&1 || true

    return $MONITORED_EXIT
}

# Sync Clarvis's own workspace (main branch) with origin before doing work.
# Controlled by CLARVIS_SELF_SYNC env var:
#   "skip" (default) — no-op; Clarvis commits directly to main.
#   "auto"           — ff-only pull from origin/main with stash safety.
# Project-agent workspaces have their own sync in project_agent.py and
# are NOT affected by this function.
#
# Also skips if: not on main, not a git repo, no network, or non-ff divergence.
sync_workspace() {
    if [ "${CLARVIS_SELF_SYNC:-skip}" = "skip" ]; then
        return 0
    fi

    [ -d "$CLARVIS_WORKSPACE/.git" ] || return 0

    local _branch
    _branch=$(git -C "$CLARVIS_WORKSPACE" symbolic-ref --short HEAD 2>/dev/null) || return 0
    [ "$_branch" = "main" ] || return 0

    git -C "$CLARVIS_WORKSPACE" fetch origin main --quiet 2>/dev/null || return 0

    local _local _remote
    _local=$(git -C "$CLARVIS_WORKSPACE" rev-parse HEAD 2>/dev/null)
    _remote=$(git -C "$CLARVIS_WORKSPACE" rev-parse origin/main 2>/dev/null)
    [ "$_local" = "$_remote" ] && return 0

    if ! git -C "$CLARVIS_WORKSPACE" merge-base --is-ancestor "$_local" "$_remote" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SYNC: local main diverged from origin — skipping auto-sync" >&2
        return 0
    fi

    local _stashed=0 _stash_ref=""
    if ! git -C "$CLARVIS_WORKSPACE" diff --quiet 2>/dev/null || \
       ! git -C "$CLARVIS_WORKSPACE" diff --cached --quiet 2>/dev/null; then
        git -C "$CLARVIS_WORKSPACE" stash push -q -m "cron-sync-$(date +%s)" 2>/dev/null || return 0
        _stash_ref=$(git -C "$CLARVIS_WORKSPACE" stash list -1 --format="%H" 2>/dev/null)
        _stashed=1
    fi

    git -C "$CLARVIS_WORKSPACE" merge --ff-only origin/main --quiet 2>/dev/null || {
        if [ "$_stashed" -eq 1 ]; then
            if ! git -C "$CLARVIS_WORKSPACE" stash pop -q 2>/dev/null; then
                echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SYNC: CRITICAL — stash pop failed after aborted ff-merge. Stash ref: ${_stash_ref:-unknown}. Run 'git -C $CLARVIS_WORKSPACE stash list' and 'git -C $CLARVIS_WORKSPACE stash pop' to recover." >&2
                emit_dashboard_event error --section sync_workspace --meta "stash_pop_failed_after_merge_abort stash_ref=${_stash_ref:-unknown}"
                return 1
            fi
        fi
        return 0
    }

    if [ "$_stashed" -eq 1 ]; then
        if ! git -C "$CLARVIS_WORKSPACE" stash pop -q 2>/dev/null; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SYNC: CRITICAL — stash pop failed after successful ff-merge. Stash ref: ${_stash_ref:-unknown}. Workspace is updated but local changes are stranded. Run 'git -C $CLARVIS_WORKSPACE stash show' and 'git -C $CLARVIS_WORKSPACE stash pop' to recover." >&2
            emit_dashboard_event error --section sync_workspace --meta "stash_pop_failed_after_ff_merge stash_ref=${_stash_ref:-unknown}"
            return 1
        fi
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SYNC: workspace fast-forwarded to origin/main ($(git -C "$CLARVIS_WORKSPACE" rev-parse --short HEAD))" >&2
}

# Dashboard event publisher (no-op if script missing; never blocks caller)
emit_dashboard_event() {
    python3 "$CLARVIS_WORKSPACE/scripts/metrics/dashboard_events.py" emit "$@" >/dev/null 2>&1 || true
}

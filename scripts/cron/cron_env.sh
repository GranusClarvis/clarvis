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
elif [ -f "$CLARVIS_WORKSPACE/.env" ]; then
    set -a; . "$CLARVIS_WORKSPACE/.env"; set +a
fi
export CLARVIS_TG_BOT_TOKEN="${CLARVIS_TG_BOT_TOKEN:-}"
export CLARVIS_TG_CHAT_ID="${CLARVIS_TG_CHAT_ID:-}"
export CLARVIS_TG_GROUP_ID="${CLARVIS_TG_GROUP_ID:-}"
export CLARVIS_TG_REPORTS_TOPIC="${CLARVIS_TG_REPORTS_TOPIC:-5}"
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

    # Launch Claude Code in background, feeding prompt via stdin (not argv)
    timeout "$_timeout" env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
        ${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")} -p \
        --dangerously-skip-permissions --model claude-opus-4-6 \
        < "$_prompt_file" > "$_output_file" 2>&1 &
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
    local _source
    _source="${CRON_SOURCE:-$(basename "${BASH_SOURCE[1]:-$0}" .sh 2>/dev/null || echo unknown)}"
    python3 "$CLARVIS_WORKSPACE/scripts/infra/cost_checkpoint.py" \
        "$_source" "$_task_head" "$_timeout" >> "$_logfile" 2>&1 || true

    return $MONITORED_EXIT
}

# Dashboard event publisher (no-op if script missing; never blocks caller)
emit_dashboard_event() {
    python3 "$CLARVIS_WORKSPACE/scripts/metrics/dashboard_events.py" emit "$@" >/dev/null 2>&1 || true
}

#!/bin/bash
# =============================================================================
# Cron Environment Bootstrap
# =============================================================================
# Source this at the top of every cron script to get the full interactive PATH
# and environment that scripts need (python3, claude, openclaw, npm, etc.)
#
# Usage: source /home/agent/.openclaw/workspace/scripts/cron_env.sh
# =============================================================================

export HOME="/home/agent"
export PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:/usr/local/bin:/home/agent/.local/bin:/usr/bin:/bin:/home/agent/.npm-global/bin:/home/agent/go/bin:/home/agent/.cargo/bin"
export NODE_PATH="/home/agent/.npm-global/lib/node_modules"
export LANG="en_US.UTF-8"

# Prevent "nested Claude Code session" errors when cron scripts are
# triggered manually from inside a Claude Code session.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Systemd user session (required for openclaw gateway management since v2026.2.23)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

# Workspace
export CLARVIS_WORKSPACE="/home/agent/.openclaw/workspace"
cd "$CLARVIS_WORKSPACE"

# Graph storage backend: "json" (default) or "sqlite"
# Uncomment the line below to enable SQLite graph backend for soak testing.
# Before enabling, run: python3 scripts/graph_migrate_to_sqlite.py --safe
export CLARVIS_GRAPH_BACKEND="sqlite"
# During soak: dual-write JSON+SQLite to validate parity. After soak cutover, this will be set to 0.
export CLARVIS_GRAPH_DUAL_WRITE="1"

# Shared helper: get current weakest performance metric (fast, reads cached file)
get_weakest_metric() {
    python3 "$CLARVIS_WORKSPACE/scripts/performance_benchmark.py" weakest 2>/dev/null || echo "unknown"
}

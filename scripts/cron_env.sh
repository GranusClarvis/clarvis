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

# Workspace
export CLARVIS_WORKSPACE="/home/agent/.openclaw/workspace"
cd "$CLARVIS_WORKSPACE"

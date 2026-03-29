#!/bin/bash
# Graph soak manager — post-cutover stub.
#
# Cutover finalized 2026-03-29: SQLite is the sole runtime backend.
# CLARVIS_GRAPH_DUAL_WRITE=0 (JSON no longer written at runtime).
# This script now just logs confirmation and exits.
# Safe to remove from crontab once confirmed stable.

set -euo pipefail

source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOG="/home/agent/.openclaw/workspace/memory/cron/graph_soak_manager.log"
TS="$(date -u +%Y-%m-%dT%H:%M:%S)"

echo "[$TS] Soak manager: cutover complete (2026-03-29). DUAL_WRITE=${CLARVIS_GRAPH_DUAL_WRITE:-0}. No action needed." >> "$LOG"
exit 0

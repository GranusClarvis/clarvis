#!/bin/bash
# Weekly Brier Calibration Report — Sunday ~06:45 UTC
# Computes Brier score (7-day + all-time), confidence band distribution,
# failure-rate-by-domain, and writes to memory/cron/calibration_report.md.
# No Claude Code spawning — lightweight Python-only.
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

LOCKFILE="/tmp/clarvis_calibration_report.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(awk '{print $1}' "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)"
        exit 0
    fi
fi
echo "$$ $(date -u +%Y-%m-%dT%H:%M:%S)" > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Weekly calibration report ==="
python3 "$CLARVIS_WORKSPACE/scripts/cron/calibration_report.py" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Calibration report complete ==="

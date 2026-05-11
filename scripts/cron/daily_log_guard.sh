#!/bin/bash
# daily_log_guard.sh — Continuity guard for `memory/YYYY-MM-DD.md` daily logs.
#
# Checks the most recent 7 calendar days for missing daily log files
# (either `memory/YYYY-MM-DD.md` or its compressed `.md.gz` counterpart
# counts as present, since the cleanup cron auto-compresses older logs).
#
# Writes a compact report to `memory/cron/daily_log_guard_<YYYY-MM-DD>.md`
# named for today (UTC). The script is idempotent: re-running on the same
# UTC day reuses the existing report and exits without rewriting it,
# unless `--force` is passed.
#
# If any log is missing for >24 h (i.e. older than today), the script
# appends a single queue-ready remediation suggestion to the report so
# the operator can copy it into `memory/evolution/QUEUE.md`.
#
# Usage:
#   daily_log_guard.sh           # normal run (no-op if today's report exists)
#   daily_log_guard.sh --force   # rewrite today's report
#
# Exit codes:
#   0 — clean run (report written or already present)
#   1 — bootstrap failure (workspace missing, etc.)

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"

FORCE=0
if [ "${1:-}" = "--force" ]; then
    FORCE=1
fi

TODAY="$(date -u +%Y-%m-%d)"
TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
LOGFILE="${CLARVIS_WORKSPACE}/memory/cron/daily_log_guard.log"
REPORT_DIR="${CLARVIS_WORKSPACE}/memory/cron"
REPORT="${REPORT_DIR}/daily_log_guard_${TODAY}.md"
LOCKFILE="/tmp/clarvis_daily_log_guard.lock"

mkdir -p "$REPORT_DIR"

# Lockfile with stale-lock detection (pid-based).
if [ -f "$LOCKFILE" ]; then
    OLDPID="$(cat "$LOCKFILE" 2>/dev/null || echo "")"
    if [ -n "$OLDPID" ] && kill -0 "$OLDPID" 2>/dev/null; then
        echo "[$TS] another guard run is active (pid=$OLDPID) — skip" >> "$LOGFILE"
        exit 0
    fi
    rm -f "$LOCKFILE"
fi
echo "$$" > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

# Idempotency: if today's report already exists and --force not given, skip.
if [ -f "$REPORT" ] && [ "$FORCE" -ne 1 ]; then
    echo "[$TS] report already exists for $TODAY — skip (use --force to rewrite)" >> "$LOGFILE"
    exit 0
fi

# Build the list of dates we expect: today plus the previous 6 days.
DATES=()
for offset in 0 1 2 3 4 5 6; do
    d="$(date -u -d "$TODAY -${offset} day" +%Y-%m-%d 2>/dev/null || true)"
    if [ -z "$d" ]; then
        # BSD/macOS fallback (unlikely in cron host, but defensive)
        d="$(date -u -v "-${offset}d" +%Y-%m-%d 2>/dev/null || true)"
    fi
    [ -n "$d" ] && DATES+=("$d")
done

if [ ${#DATES[@]} -eq 0 ]; then
    echo "[$TS] date enumeration failed — abort" >> "$LOGFILE"
    exit 1
fi

MISSING=()
PRESENT_PLAIN=()
PRESENT_GZ=()
for d in "${DATES[@]}"; do
    if [ -f "${CLARVIS_WORKSPACE}/memory/${d}.md" ]; then
        PRESENT_PLAIN+=("$d")
    elif [ -f "${CLARVIS_WORKSPACE}/memory/${d}.md.gz" ]; then
        PRESENT_GZ+=("$d")
    else
        MISSING+=("$d")
    fi
done

# Flag missing-for->24h: anything in MISSING that isn't today.
OVERDUE=()
for d in "${MISSING[@]:-}"; do
    [ -z "$d" ] && continue
    if [ "$d" != "$TODAY" ]; then
        OVERDUE+=("$d")
    fi
done

# Write the report.
{
    echo "# Daily Log Guard — ${TODAY}"
    echo ""
    echo "_Generated: ${TS}Z by \`scripts/cron/daily_log_guard.sh\`_"
    echo ""
    echo "Window: ${DATES[$((${#DATES[@]}-1))]} → ${DATES[0]} (last 7 days, UTC)"
    echo ""
    echo "## Summary"
    echo ""
    echo "- Present (uncompressed \`.md\`): ${#PRESENT_PLAIN[@]}"
    echo "- Present (compressed \`.md.gz\`): ${#PRESENT_GZ[@]}"
    echo "- Missing: ${#MISSING[@]}"
    echo "- Overdue >24 h: ${#OVERDUE[@]}"
    echo ""
    echo "## Detail"
    echo ""
    echo "| Date | Status |"
    echo "|------|--------|"
    for d in "${DATES[@]}"; do
        if [ -f "${CLARVIS_WORKSPACE}/memory/${d}.md" ]; then
            echo "| ${d} | present (\`.md\`) |"
        elif [ -f "${CLARVIS_WORKSPACE}/memory/${d}.md.gz" ]; then
            echo "| ${d} | present (\`.md.gz\`) |"
        else
            if [ "$d" = "$TODAY" ]; then
                echo "| ${d} | **MISSING** (today, not yet overdue) |"
            else
                echo "| ${d} | **MISSING** (overdue >24 h) |"
            fi
        fi
    done
    echo ""
    if [ ${#OVERDUE[@]} -gt 0 ]; then
        # Build a comma-joined date list for the suggestion.
        OVERDUE_LIST="$(printf '%s, ' "${OVERDUE[@]}" | sed 's/, $//')"
        echo "## Remediation"
        echo ""
        echo "${#OVERDUE[@]} log(s) missing for >24 h — append the following item to \`memory/evolution/QUEUE.md\`:"
        echo ""
        echo '```markdown'
        echo "- [ ] **[DAILY_LOG_BACKFILL_${TODAY//-/}]** Non-Python markdown. The continuity guard (\`daily_log_guard.sh\`) detected ${#OVERDUE[@]} missing daily log(s) in the last 7 days: ${OVERDUE_LIST}. Reconstruct each from \`memory/cron/autonomous.log\`, the queue [x] entries in \`memory/evolution/QUEUE.md\`, and any session digests. **Acceptance:** \`memory/<date>.md\` exists for each listed date with at least one autonomous-task entry and a brain stats header; a re-run of \`scripts/cron/daily_log_guard.sh\` reports 0 overdue. (PROJECT:CLARVIS)"
        echo '```'
        echo ""
    else
        echo "## Remediation"
        echo ""
        echo "No overdue logs. No action required."
        echo ""
    fi
} > "$REPORT"

echo "[$TS] report written: $REPORT (missing=${#MISSING[@]} overdue=${#OVERDUE[@]})" >> "$LOGFILE"
exit 0

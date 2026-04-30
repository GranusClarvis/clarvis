#!/bin/bash
# heartbeat_notask_triage.sh — Bucket no-task heartbeat cycles by reason.
#
# Diagnostic only — does NOT change heartbeat behavior. Scans the live
# autonomous.log (and rotated .1) for the last N days, classifies each
# cycle, and writes a markdown table to memory/cron/heartbeat_triage.md.
# Appends a one-line summary to memory/cron/digest.md.
#
# Buckets:
#   queue_empty   PREFLIGHT status=queue_empty/no_tasks, or "Queue empty — spawning"
#   all_filtered  PREFLIGHT status=all_filtered_by_v2 (queue had items, all filtered out)
#   lock_held     local/global/maintenance lock denied this run
#   gate_skip     heartbeat gate decided nothing changed
#   unknown       "No task selected" with no upstream reason, or COGNITIVE LOAD: DEFERRING
#
# Usage:
#   heartbeat_notask_triage.sh        # default 7-day window
#   heartbeat_notask_triage.sh 14     # 14-day window
#
# Acceptance: completes in <5s on the live log; produces a populated bucket table.

set -uo pipefail

N_DAYS="${1:-7}"
WS="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"
LOGS=("$WS/memory/cron/autonomous.log" "$WS/memory/cron/autonomous.log.1")
OUT="$WS/memory/cron/heartbeat_triage.md"
DIGEST="$WS/memory/cron/digest.md"

CUTOFF=$(date -u -d "${N_DAYS} days ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null \
         || date -u -v-"${N_DAYS}"d +%Y-%m-%dT%H:%M:%S)
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build list of existing log paths (skip missing rotations gracefully).
EXISTING_LOGS=()
for f in "${LOGS[@]}"; do
    [ -f "$f" ] && EXISTING_LOGS+=("$f")
done

if [ "${#EXISTING_LOGS[@]}" -eq 0 ]; then
    echo "ERROR: no autonomous.log found under $WS/memory/cron/" >&2
    exit 1
fi

# Single awk pass: timestamp-prefixed lines only, lexicographic compare against cutoff.
read GATE_WAKE GATE_SKIP LOCK_HELD QUEUE_EMPTY ALL_FILTERED NO_TASK_LINES COG_DEFER < <(
    awk -v cutoff="$CUTOFF" '
        /^\[[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\]/ {
            t = substr($0, 2, 19)
            if (t < cutoff) next
            if (index($0, "GATE: wake")) gw++
            else if (index($0, "GATE: skip")) gs++
            else if (index($0, "SKIP: Previous run still active") \
                  || index($0, "GLOBAL LOCK: Claude already running") \
                  || index($0, "Maintenance lock held")) lh++
            if (index($0, "Queue empty") \
             || index($0, "PREFLIGHT: status=queue_empty") \
             || index($0, "PREFLIGHT: status=no_tasks")) qe++
            if (index($0, "PREFLIGHT: status=all_filtered_by_v2")) af++
            if (index($0, "No task selected")) nt++
            if (index($0, "COGNITIVE LOAD: DEFERRING")) cd++
        }
        END { print gw+0, gs+0, lh+0, qe+0, af+0, nt+0, cd+0 }
    ' "${EXISTING_LOGS[@]}"
)

# "No task selected" lines that were NOT explained by all_filtered/queue_empty
# go into unknown, plus any COGNITIVE LOAD: DEFERRING events.
UNEXPLAINED=$(( NO_TASK_LINES - ALL_FILTERED - QUEUE_EMPTY ))
[ "$UNEXPLAINED" -lt 0 ] && UNEXPLAINED=0
UNKNOWN=$(( UNEXPLAINED + COG_DEFER ))

NO_TASK=$(( GATE_SKIP + LOCK_HELD + QUEUE_EMPTY + ALL_FILTERED + UNKNOWN ))
TOTAL=$(( GATE_WAKE + GATE_SKIP + LOCK_HELD ))
EXECUTED=$(( GATE_WAKE - QUEUE_EMPTY - ALL_FILTERED - UNKNOWN ))
[ "$EXECUTED" -lt 0 ] && EXECUTED=0

if [ "$TOTAL" -gt 0 ]; then
    PCT=$(awk -v n="$NO_TASK" -v t="$TOTAL" 'BEGIN { printf "%.1f", (n/t)*100 }')
else
    PCT="0.0"
fi

# Pick the dominant bucket (largest non-zero count) — useful for the digest line.
DOMINANT="none"
DOM_COUNT=0
for pair in "queue_empty:$QUEUE_EMPTY" "all_filtered:$ALL_FILTERED" \
            "lock_held:$LOCK_HELD" "gate_skip:$GATE_SKIP" "unknown:$UNKNOWN"; do
    name="${pair%%:*}"
    count="${pair##*:}"
    if [ "$count" -gt "$DOM_COUNT" ]; then
        DOMINANT="$name"
        DOM_COUNT="$count"
    fi
done

mkdir -p "$(dirname "$OUT")"
{
    echo "# Heartbeat No-Task Triage — last ${N_DAYS} days"
    echo
    echo "_Generated: ${NOW_UTC} by \`scripts/cron/heartbeat_notask_triage.sh\`._"
    echo
    echo "Window: \`${CUTOFF}\` → now (UTC)"
    echo "Sources: $(printf '%s ' "${EXISTING_LOGS[@]##*/}")"
    echo
    echo "## Bucket Counts"
    echo
    echo "| Bucket | Count |"
    echo "|---|---:|"
    echo "| queue_empty | ${QUEUE_EMPTY} |"
    echo "| all_filtered | ${ALL_FILTERED} |"
    echo "| lock_held | ${LOCK_HELD} |"
    echo "| gate_skip | ${GATE_SKIP} |"
    echo "| unknown | ${UNKNOWN} |"
    echo "| **no-task total** | **${NO_TASK}** |"
    echo "| executed | ${EXECUTED} |"
    echo "| **all cycles** | **${TOTAL}** |"
    echo
    echo "**No-task rate: ${PCT}% (${NO_TASK}/${TOTAL})** — dominant bucket: \`${DOMINANT}\` (${DOM_COUNT})"
    echo
    echo "## Bucket Definitions"
    echo
    echo "- \`queue_empty\` — preflight returned \`queue_empty\`/\`no_tasks\`; replenish cycle ran. Indicates queue starvation."
    echo "- \`all_filtered\` — queue had items, but Queue V2 filtered all of them. Suggests filter logic may be too aggressive."
    echo "- \`lock_held\` — another cron run was active (local job lock, global Claude lock, or maintenance lock)."
    echo "- \`gate_skip\` — heartbeat gate decided nothing changed since last run; cycle skipped to save tokens."
    echo "- \`unknown\` — \"No task selected\" without an upstream marker, or \`COGNITIVE LOAD: DEFERRING\`. Investigate."
    echo
    echo "## Reading Guide"
    echo
    echo "- High \`all_filtered\` → review Queue V2 filter logic (was the original concern that motivated this triage)."
    echo "- High \`queue_empty\` → queue replenishment may not be keeping up with consumption."
    echo "- High \`lock_held\` → cron schedule density may exceed effective parallelism."
    echo "- High \`gate_skip\` → fine if cycles align with quiet periods; investigate if blocking real work."
    echo "- High \`unknown\` → log new reason markers in cron_autonomous.sh so they bucket cleanly next time."
} > "$OUT"

# Append one-line summary to digest.md (idempotent within the same UTC minute).
if [ -f "$DIGEST" ]; then
    NOW_HM=$(date -u +%H:%M)
    LINE="[heartbeat-triage ${NOW_HM} UTC] No-task ${PCT}% (${NO_TASK}/${TOTAL}) over ${N_DAYS}d — queue_empty=${QUEUE_EMPTY}, all_filtered=${ALL_FILTERED}, lock_held=${LOCK_HELD}, gate_skip=${GATE_SKIP}, unknown=${UNKNOWN}. Dominant: ${DOMINANT}."
    if ! grep -qF "[heartbeat-triage ${NOW_HM} UTC]" "$DIGEST"; then
        printf '\n%s\n' "$LINE" >> "$DIGEST"
    fi
fi

echo "Wrote ${OUT} (no-task ${NO_TASK}/${TOTAL} = ${PCT}%, ${N_DAYS}d window, dominant=${DOMINANT})"

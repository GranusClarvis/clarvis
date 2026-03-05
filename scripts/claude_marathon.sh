#!/bin/bash
# =============================================================================
# claude_marathon.sh — Chain Claude tasks back-to-back for a fixed time budget
#
# Picks batches from QUEUE.md, spawns Claude Code, runs invariants after each
# batch, and loops until the time budget is exhausted or the queue is empty.
#
# Usage:
#   ./claude_marathon.sh [--minutes 420] [--max-batches 3] [--timeout-per-claude 2400] [--dry-run]
#
# Safety:
#   - Uses same global Claude lock as cron_autonomous (no overlap)
#   - Runs invariants_check.py after each batch — stops on failure
#   - No destructive operations
#   - Logs everything to memory/cron/marathon.log
# =============================================================================

set -euo pipefail

# Source cron env for proper PATH, HOME, env cleanup
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

# --- Defaults ---
TOTAL_MINUTES=420
MAX_BATCHES=3
TIMEOUT_PER_CLAUDE=2400
DRY_RUN="false"

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --minutes)        TOTAL_MINUTES="$2"; shift 2 ;;
        --max-batches)    MAX_BATCHES="$2"; shift 2 ;;
        --timeout-per-claude) TIMEOUT_PER_CLAUDE="$2"; shift 2 ;;
        --dry-run)        DRY_RUN="true"; shift ;;
        -h|--help)
            echo "Usage: claude_marathon.sh [--minutes N] [--max-batches N] [--timeout-per-claude N] [--dry-run]"
            echo ""
            echo "  --minutes N             Total time budget in minutes (default: 420 = 7 hours)"
            echo "  --max-batches N         Max tasks per Claude batch (default: 3)"
            echo "  --timeout-per-claude N  Timeout per Claude spawn in seconds (default: 2400)"
            echo "  --dry-run               Show what would run without executing"
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# --- Paths ---
SCRIPTS="/home/agent/.openclaw/workspace/scripts"
LOGFILE="/home/agent/.openclaw/workspace/memory/cron/marathon.log"
STOP_REPORT="/home/agent/.openclaw/workspace/docs/MARATHON_STOP_REPORT.md"
WORK_DIR="/home/agent/.openclaw/workspace"

# Belt-and-suspenders: remove nesting guards
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# --- Locking ---
acquire_local_lock "/tmp/clarvis_marathon.lock" "$LOGFILE" "$((TOTAL_MINUTES * 60 + 300))"
acquire_global_claude_lock "$LOGFILE"

# --- Time tracking ---
START_EPOCH=$(date +%s)
DEADLINE_EPOCH=$((START_EPOCH + TOTAL_MINUTES * 60))
BATCH_NUM=0
TOTAL_TASKS_DONE=0
BATCH_RESULTS=()

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] $*" >> "$LOGFILE"
}

log "=== MARATHON START === budget=${TOTAL_MINUTES}m, max_batches=${MAX_BATCHES}, timeout=${TIMEOUT_PER_CLAUDE}s"

# --- Utility: time remaining ---
time_remaining() {
    local now
    now=$(date +%s)
    echo $((DEADLINE_EPOCH - now))
}

# --- Utility: enough time for another batch? ---
has_time() {
    local remaining
    remaining=$(time_remaining)
    # Need at least timeout + 120s buffer for invariants
    if [ "$remaining" -lt $((TIMEOUT_PER_CLAUDE + 120)) ]; then
        return 1
    fi
    return 0
}

# --- Utility: run invariants check ---
run_invariants() {
    log "INVARIANTS: Running post-batch check..."
    local inv_output inv_exit
    inv_output=$(python3 "$SCRIPTS/invariants_check.py" --json 2>&1) || true
    inv_exit=$?

    # Try to parse JSON result
    local passed="false"
    passed=$(echo "$inv_output" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print('true' if data.get('passed') else 'false')
except:
    print('false')
" 2>/dev/null || echo "false")

    if [ "$passed" = "true" ]; then
        log "INVARIANTS: PASS"
        return 0
    else
        log "INVARIANTS: FAIL — stopping marathon"
        log "INVARIANTS output: $(echo "$inv_output" | tail -20)"

        # Write stop report
        cat > "$STOP_REPORT" << REPORT_EOF
# Marathon Stop Report

**Date:** $(date -u +%Y-%m-%dT%H:%M:%S)Z
**Batch:** $BATCH_NUM
**Reason:** Invariants check failed after batch

## Batches Completed
$(printf '%s\n' "${BATCH_RESULTS[@]}" 2>/dev/null || echo "None")

## Invariants Output
\`\`\`
$(echo "$inv_output" | tail -40)
\`\`\`

## Action Required
1. Check \`python3 scripts/invariants_check.py\` output
2. Fix failing checks
3. Re-run marathon: \`./scripts/claude_marathon.sh\`
REPORT_EOF
        log "STOP_REPORT written to $STOP_REPORT"
        return 1
    fi
}

# --- Utility: commit changes if working tree dirty ---
auto_commit() {
    cd "$WORK_DIR"
    if ! git diff --quiet HEAD 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
        log "AUTO-COMMIT: Working tree dirty, committing..."
        git add -A
        git commit -m "$(cat <<'EOF'
chore: marathon batch auto-commit

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
        )" >> "$LOGFILE" 2>&1 || true
        log "AUTO-COMMIT: Done"
    else
        log "AUTO-COMMIT: Working tree clean, nothing to commit"
    fi
}

# --- Utility: select tasks ---
select_tasks() {
    python3 "$SCRIPTS/marathon_task_selector.py" \
        --max-tasks "$MAX_BATCHES" \
        --max-chars 900
}

# --- Utility: auto-split oversized tasks ---
try_auto_split() {
    local tag="$1"
    log "AUTO-SPLIT: Attempting to split oversized task [$tag]"
    python3 -c "
import sys
sys.path.insert(0, '$SCRIPTS')
from queue_writer import ensure_subtasks_for_tag

subtasks = [
    'Part 1: research and design approach',
    'Part 2: implement core changes',
    'Part 3: test and validate',
]
result = ensure_subtasks_for_tag('$tag', subtasks)
print('split' if result else 'skip')
" 2>> "$LOGFILE" || true
}

# =============================================================================
# MAIN LOOP
# =============================================================================

while has_time; do
    BATCH_NUM=$((BATCH_NUM + 1))
    log "--- BATCH $BATCH_NUM --- ($(( $(time_remaining) / 60 ))m remaining)"

    # --- Select tasks ---
    SELECTION_JSON=$(select_tasks 2>> "$LOGFILE")
    if [ -z "$SELECTION_JSON" ]; then
        log "BATCH $BATCH_NUM: Task selector returned empty — stopping"
        break
    fi

    # Parse selection
    TASK_COUNT=$(echo "$SELECTION_JSON" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('count',0))" 2>/dev/null || echo "0")
    QUEUE_EMPTY=$(echo "$SELECTION_JSON" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print('true' if d.get('queue_empty') else 'false')" 2>/dev/null || echo "false")
    BATCH_TAGS=$(echo "$SELECTION_JSON" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(','.join(d.get('tags',[])))" 2>/dev/null || echo "")
    BATCH_PROMPT=$(echo "$SELECTION_JSON" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('batch_prompt',''))" 2>/dev/null || echo "")
    SKIPPED_OVERSIZED=$(echo "$SELECTION_JSON" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(','.join(d.get('skipped_oversized',[])))" 2>/dev/null || echo "")

    # Auto-split oversized tasks if we encounter them
    if [ -n "$SKIPPED_OVERSIZED" ]; then
        IFS=',' read -ra OVERSIZED_ARRAY <<< "$SKIPPED_OVERSIZED"
        for otag in "${OVERSIZED_ARRAY[@]}"; do
            [ -n "$otag" ] && try_auto_split "$otag"
        done
    fi

    if [ "$QUEUE_EMPTY" = "true" ] || [ "$TASK_COUNT" -eq 0 ]; then
        log "BATCH $BATCH_NUM: Queue empty or no eligible tasks — stopping"
        break
    fi

    log "BATCH $BATCH_NUM: Selected $TASK_COUNT task(s): [$BATCH_TAGS]"

    # --- Dry run: just log what would happen ---
    if [ "$DRY_RUN" = "true" ]; then
        log "DRY-RUN: Would spawn Claude with:"
        log "DRY-RUN: $BATCH_PROMPT"
        BATCH_RESULTS+=("Batch $BATCH_NUM: DRY-RUN [$BATCH_TAGS]")
        continue
    fi

    # --- Cap timeout to remaining time (leave 180s for invariants + commit) ---
    REMAINING=$(time_remaining)
    EFFECTIVE_TIMEOUT=$TIMEOUT_PER_CLAUDE
    if [ "$REMAINING" -lt $((TIMEOUT_PER_CLAUDE + 180)) ]; then
        EFFECTIVE_TIMEOUT=$((REMAINING - 180))
        if [ "$EFFECTIVE_TIMEOUT" -lt 600 ]; then
            log "BATCH $BATCH_NUM: Not enough time for minimum run (${REMAINING}s remaining) — stopping"
            break
        fi
        log "BATCH $BATCH_NUM: Capping timeout to ${EFFECTIVE_TIMEOUT}s (time budget)"
    fi

    # --- Spawn Claude Code ---
    log "BATCH $BATCH_NUM: Spawning Claude (timeout=${EFFECTIVE_TIMEOUT}s)..."
    BATCH_START=$(date +%s)

    # Use spawn_claude.sh (which handles prompt writing, context enrichment, Telegram)
    SPAWN_EXIT=0
    "$SCRIPTS/spawn_claude.sh" "$BATCH_PROMPT" "$EFFECTIVE_TIMEOUT" --no-tg || SPAWN_EXIT=$?

    BATCH_DURATION=$(( $(date +%s) - BATCH_START ))
    BATCH_MINUTES=$(( BATCH_DURATION / 60 ))

    case $SPAWN_EXIT in
        0)
            log "BATCH $BATCH_NUM: SUCCESS (${BATCH_MINUTES}m)"
            BATCH_RESULTS+=("Batch $BATCH_NUM: SUCCESS [$BATCH_TAGS] (${BATCH_MINUTES}m)")
            TOTAL_TASKS_DONE=$((TOTAL_TASKS_DONE + TASK_COUNT))
            ;;
        124)
            log "BATCH $BATCH_NUM: TIMEOUT after ${BATCH_MINUTES}m"
            BATCH_RESULTS+=("Batch $BATCH_NUM: TIMEOUT [$BATCH_TAGS] (${BATCH_MINUTES}m)")
            TOTAL_TASKS_DONE=$((TOTAL_TASKS_DONE + TASK_COUNT))
            ;;
        *)
            log "BATCH $BATCH_NUM: FAILED (exit $SPAWN_EXIT, ${BATCH_MINUTES}m)"
            BATCH_RESULTS+=("Batch $BATCH_NUM: FAILED [$BATCH_TAGS] (exit=$SPAWN_EXIT, ${BATCH_MINUTES}m)")
            ;;
    esac

    # --- Auto-commit any changes ---
    auto_commit

    # --- Run invariants ---
    if ! run_invariants; then
        log "=== MARATHON STOPPED (invariant failure) after $BATCH_NUM batches, $TOTAL_TASKS_DONE tasks ==="
        exit 1
    fi

    # Brief pause between batches to let system settle
    sleep 5
done

# =============================================================================
# SUMMARY
# =============================================================================
TOTAL_DURATION=$(( $(date +%s) - START_EPOCH ))
TOTAL_DURATION_MIN=$(( TOTAL_DURATION / 60 ))

log "=== MARATHON COMPLETE === batches=$BATCH_NUM, tasks=$TOTAL_TASKS_DONE, duration=${TOTAL_DURATION_MIN}m"
for r in "${BATCH_RESULTS[@]}"; do
    log "  $r"
done

echo "Marathon complete: $BATCH_NUM batches, $TOTAL_TASKS_DONE tasks in ${TOTAL_DURATION_MIN}m"
echo "Log: $LOGFILE"

#!/bin/bash
# Monthly structural reflection — runs 1st of month at 03:30
# Analyzes 30-day episode trends, identifies structural changes needed,
# proposes ROADMAP updates, writes output to memory/cron/monthly_reflection_YYYY-MM.md
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lock_helper.sh"

LOGFILE="memory/cron/monthly_reflection.log"
MONTH_TAG=$(date -u +%Y-%m)
OUTPUT_FILE="memory/cron/monthly_reflection_${MONTH_TAG}.md"

# Acquire locks: local + global Claude
acquire_local_lock "/tmp/clarvis_monthly_reflection.lock" "$LOGFILE" 7200
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Monthly reflection starting (${MONTH_TAG}) ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Monthly structural reflection" --section cron_monthly_reflection --executor claude-opus

# Pre-compute metrics for prompt
WEAKEST_METRIC=$(get_weakest_metric)

# Build the Claude Code prompt
PROMPT_FILE=$(mktemp --suffix=.txt)
cat > "$PROMPT_FILE" << 'ENDPROMPT'
You are Clarvis performing a MONTHLY STRUCTURAL REFLECTION for the past 30 days.

This runs once per month. Your job is deep analysis — not daily task work.

## Instructions

1. **Episode trend analysis** (30-day window):
   - Read `data/episodes.jsonl` — analyze success/fail/partial rates, recurring failure patterns, capability distribution
   - Read `data/reasoning_chains.jsonl` — check reasoning quality trends, shallow-reasoning frequency
   - Read `data/predictions.jsonl` — calibration drift, domains with worst Brier scores
   - Summarize: what types of tasks succeed? What types fail? Are failures clustered?

2. **Structural script audit**:
   - Check `scripts/` for scripts that have grown beyond their original purpose (>300 lines, multiple responsibilities)
   - Identify dead code or unused scripts (check crontab + imports)
   - Flag scripts that should be migrated to `clarvis/` spine modules
   - Check for duplicated logic across scripts

3. **ROADMAP gap analysis**:
   - Read `ROADMAP.md` — identify phases marked incomplete, stalled items, percentage claims that may be outdated
   - Compare ROADMAP claims against actual system state (run quick health checks if needed)
   - Propose specific ROADMAP updates (percentage changes, new items, items to mark complete)

4. **Cron schedule efficiency**:
   - Analyze `memory/cron/autonomous.log` (last 30 days) for: timeout frequency, deferred tasks, queue-empty events, wasted slots
   - Check if any cron slots consistently produce no useful output
   - Recommend schedule adjustments if warranted

5. **Recommendations** (max 5):
   - Concrete, actionable structural changes
   - Each should reference specific files/scripts/configs
   - Priority-ranked (P0/P1/P2)

## Output format

Write your analysis as a structured markdown report. Start with a one-paragraph executive summary.
Use sections: ## Episode Trends, ## Script Audit, ## ROADMAP Gaps, ## Cron Efficiency, ## Recommendations.

IMPORTANT: Write the full report to the file specified — do not just print it to stdout.
ENDPROMPT

# Append dynamic context (printf pattern — no unquoted heredoc)
{
    printf '\n## Dynamic Context\n'
    printf '- Month: %s\n' "$MONTH_TAG"
    printf '- Weakest metric: %s\n' "$WEAKEST_METRIC"
    printf '- Output file: Write your report to `%s`\n' "$OUTPUT_FILE"
    printf '\nDo the work. Be thorough but concise. This report guides the next month of evolution.\n'
    printf 'OUTPUT FORMAT (mandatory): Start with "RESULT: success|partial|fail — <summary>". Then confirm the output file was written.\n'
} >> "$PROMPT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Spawning Claude Code for monthly reflection..." >> "$LOGFILE"

TASK_OUTPUT=$(mktemp)
timeout 1800 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
    ${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")} -p "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 \
    > "$TASK_OUTPUT" 2>&1
TASK_EXIT=$?
rm -f "$PROMPT_FILE"

# Log output (truncated)
tail -c 2000 "$TASK_OUTPUT" >> "$LOGFILE" 2>/dev/null
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Claude exit code: $TASK_EXIT" >> "$LOGFILE"

# Verify output file was created
if [ -f "$OUTPUT_FILE" ]; then
    REPORT_SIZE=$(wc -c < "$OUTPUT_FILE")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Report written: ${OUTPUT_FILE} (${REPORT_SIZE} bytes)" >> "$LOGFILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARNING: Report file not created" >> "$LOGFILE"
fi

# === DIGEST: Write first-person summary for M2.5 agent ===
SUMMARY=$(tail -c 300 "$TASK_OUTPUT" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 250)
python3 $CLARVIS_WORKSPACE/scripts/tools/digest_writer.py reflection \
    "MONTHLY REFLECTION (${MONTH_TAG}): ${SUMMARY}" \
    >> "$LOGFILE" 2>&1 || true

rm -f "$TASK_OUTPUT"

emit_dashboard_event task_completed --task-name "Monthly structural reflection" --section cron_monthly_reflection --status "$([ $TASK_EXIT -eq 0 ] && echo success || echo failed)"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Monthly reflection complete ===" >> "$LOGFILE"

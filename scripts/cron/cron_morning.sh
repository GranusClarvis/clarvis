#!/bin/bash
# Morning reasoning - plan the day with Claude Code
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/morning.log"

# Acquire locks: local + global Claude
acquire_local_lock "/tmp/clarvis_morning.lock" "$LOGFILE" 3600
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine started ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Morning planning" --section cron_morning --executor claude-opus

# Step 0: Session open — restore attention state and working memory from previous session
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running session open..." >> "$LOGFILE"
python3 $CLARVIS_WORKSPACE/scripts/hooks/session_hook.py open >> "$LOGFILE" 2>&1

# Step 0.5: Bootstrap daily memory file so all subsequent cron jobs have it
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Bootstrapping daily memory file..." >> "$LOGFILE"
python3 $CLARVIS_WORKSPACE/scripts/tools/daily_memory_log.py >> "$LOGFILE" 2>&1 || true

# === MORNING PLANNING (with context from prompt_builder) ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running morning planning..." >> "$LOGFILE"
SCRIPTS="$CLARVIS_WORKSPACE/scripts"
WEAKEST_METRIC=$(get_weakest_metric)
MORNING_PROMPT=$(python3 "$SCRIPTS/tools/prompt_builder.py" build \
    --task "Morning planning. Read memory/evolution/QUEUE.md. Pick top 3 priorities for today from pending tasks. WEAKEST METRIC: $WEAKEST_METRIC — one priority MUST target this. Update brain.set_context() with today's focus. OUTPUT FORMAT (mandatory): PRIORITY 1: <task> | PRIORITY 2: <task> | PRIORITY 3: <task> — one line each with brief reasoning." \
    --role "morning planner" --tier standard 2>> "$LOGFILE")
MORNING_PROMPT_FILE=$(mktemp)
echo "$MORNING_PROMPT" > "$MORNING_PROMPT_FILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Prompt: ${#MORNING_PROMPT} bytes" >> "$LOGFILE"
MORNING_OUTPUT_FILE=$(mktemp)
run_claude_monitored 1200 "$MORNING_OUTPUT_FILE" "$MORNING_PROMPT_FILE" "$LOGFILE"
rm -f "$MORNING_PROMPT_FILE"
cat "$MORNING_OUTPUT_FILE" >> "$LOGFILE"

# === DIGEST: Write first-person summary for M2.5 agent ===
PRIORITIES=$(tail -c 500 "$MORNING_OUTPUT_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/[^a-zA-Z0-9 _.,:;=+\-\/()@#%]//g' | tail -c 400)
python3 $CLARVIS_WORKSPACE/scripts/tools/digest_writer.py morning "I started my day and reviewed the evolution queue. $PRIORITIES" >> "$LOGFILE" 2>&1 || true
rm -f "$MORNING_OUTPUT_FILE"

emit_dashboard_event task_completed --task-name "Morning planning" --section cron_morning --status success
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Morning routine complete ===" >> "$LOGFILE"

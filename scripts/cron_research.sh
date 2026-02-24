#!/bin/bash
# =============================================================================
# Research Cron — Dedicated research execution from QUEUE.md roadmap
# =============================================================================
# Runs 3x/day at 09:00, 14:00, 20:00 UTC
# Picks ONE research task from QUEUE.md "Research Roadmap" sections and executes
# it via Claude Code. Research tasks are never picked by cron_autonomous.sh
# because engineering P1s always outscore them on salience.
#
# This dedicated cron ensures the research roadmap actually progresses.
# =============================================================================

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/research.log"
LOCKFILE="/tmp/clarvis_research.lock"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"
QUEUE_FILE="memory/evolution/QUEUE.md"

# Prevent nested Claude sessions
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
        if [ "$lock_age" -gt 2400 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARN: Stale lock (age=${lock_age}s) — reclaiming" >> "$LOGFILE"
        else
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous research run still active (PID $pid, age=${lock_age}s)" >> "$LOGFILE"
            exit 0
        fi
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research session starting ===" >> "$LOGFILE"

# Extract the FIRST unchecked research task from QUEUE.md
# Priority order: PRIORITY TRACKING (top 10 deep dives) first, then BUNDLED SESSIONS
RESEARCH_TASK=$(python3 -c "
import re
with open('$QUEUE_FILE') as f:
    content = f.read()

lines = content.split('\n')
in_priority = False
in_bundles = False
found = None

for line in lines:
    stripped = line.strip()
    # Priority tracking section (top 10 deep dives — pick these first)
    if '=== PRIORITY TRACKING ===' in line:
        in_priority = True
        in_bundles = False
        continue
    # Bundled sessions (pick after all priority items done)
    if '=== BUNDLED SESSIONS ===' in line:
        in_priority = False
        in_bundles = True
        continue
    # Exit on next major section
    if stripped.startswith('---') or (stripped.startswith('### ') and 'Bundle' not in stripped):
        if in_bundles:
            in_bundles = False
    # Match unchecked items in priority section first
    if in_priority and re.match(r'^-\s*\[\s*\]', stripped):
        task = re.sub(r'^-\s*\[\s*\]\s*', '', stripped)
        # Strip the P-number prefix for cleaner prompt
        task = re.sub(r'^P\d+:\s*', '', task)
        found = task
        break
    # Then bundled sessions
    if in_bundles and re.match(r'^-\s*\[\s*\]', stripped):
        task = re.sub(r'^-\s*\[\s*\]\s*', '', stripped)
        found = task
        break

if found:
    print(found)
" 2>> "$LOGFILE")

if [ -z "$RESEARCH_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No pending research tasks in QUEUE.md" >> "$LOGFILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] RESEARCH TASK: ${RESEARCH_TASK:0:120}" >> "$LOGFILE"

# Generate a minimal context brief
CONTEXT_BRIEF=$(python3 "$SCRIPTS/context_compressor.py" brief 2>> "$LOGFILE")

# Execute via Claude Code with generous timeout (research = deep thinking)
TASK_OUTPUT_FILE=$(mktemp)
TASK_START=$SECONDS

# Detect if this is a bundle (scan 3 topics) or a deep dive (1 topic)
IS_BUNDLE="false"
if echo "$RESEARCH_TASK" | grep -q "^Bundle "; then
    IS_BUNDLE="true"
fi

if [ "$IS_BUNDLE" = "true" ]; then
    RESEARCH_PROMPT="You are Clarvis's research engine. This is a BUNDLE session — scan 3 related topics.

TIME BUDGET: ~25 minutes. Spend ~7 min per topic. Focus on patterns and connections between them.

CURRENT CONTEXT:
$CONTEXT_BRIEF

BUNDLE: $RESEARCH_TASK

INSTRUCTIONS:
1. The bundle lists 3 topics after the theme name (separated by commas). Research each one.
2. For each topic: search the web, read abstract/key results, extract 2-3 core ideas.
3. After all 3, write a COMBINED research note to memory/research/:
   - One note per bundle, covering all 3 topics
   - Focus on: how do these topics connect? What patterns emerge?
   - 1-2 concrete implementation ideas for Clarvis from the combined insights
4. Store 3-5 key insights in the brain:
   python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.7 --collection clarvis-learnings
5. Mark the bundle complete in QUEUE.md by changing '- [ ]' to '- [x]' and adding the date

Output a 2-3 line summary of what you learned and how it applies to Clarvis."
else
    RESEARCH_PROMPT="You are Clarvis's research engine. This is a DEEP DIVE session — one topic, thorough study.

TIME BUDGET: ~25 minutes. Go deep. Understand the core ideas thoroughly.

CURRENT CONTEXT:
$CONTEXT_BRIEF

RESEARCH TASK: $RESEARCH_TASK

INSTRUCTIONS:
1. Search the web for the key paper(s) or concept mentioned in the task
2. Read and synthesize the core ideas (don't try to read entire papers — focus on abstracts, key results, and implications)
3. Store 3-5 key insights in the brain:
   python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.8 --collection clarvis-learnings
4. Write a brief research note to memory/research/ (create dir if needed):
   - Title, authors, year
   - 3-5 key ideas
   - How this could apply to Clarvis's architecture
   - 1-2 concrete implementation ideas
5. Mark the task complete in QUEUE.md by changing '- [ ]' to '- [x]' and adding the date

Output a 2-3 line summary of what you learned and how it applies to Clarvis."
fi

timeout 1800 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \
    "$RESEARCH_PROMPT" \
    --dangerously-skip-permissions > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?
TASK_DURATION=$((SECONDS - TASK_START))

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] RESEARCH EXECUTION: exit=$TASK_EXIT duration=${TASK_DURATION}s" >> "$LOGFILE"

# Log output (truncated)
tail -c 2000 "$TASK_OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

# Update digest
SUMMARY=$(tail -c 500 "$TASK_OUTPUT_FILE" 2>/dev/null | tail -5)
DIGEST_FILE="memory/cron/digest.md"
{
    echo ""
    echo "### Research — $(date -u +%H:%M) UTC"
    echo ""
    if [ $TASK_EXIT -eq 0 ]; then
        echo "Researched: ${RESEARCH_TASK:0:100}. Result: success (${TASK_DURATION}s). Summary: ${SUMMARY:0:200}"
    else
        echo "Research FAILED: ${RESEARCH_TASK:0:100}. Exit=$TASK_EXIT (${TASK_DURATION}s)."
    fi
    echo ""
    echo "---"
    echo ""
} >> "$DIGEST_FILE"

# Log cost estimate
python3 -c "
import sys
sys.path.insert(0, '$SCRIPTS')
try:
    from cost_tracker import log_cost
    log_cost('claude-code', $TASK_DURATION, 'research', task='${RESEARCH_TASK:0:80}')
    print('Cost logged')
except Exception as e:
    print(f'Cost log failed: {e}', file=sys.stderr)
" >> "$LOGFILE" 2>&1

rm -f "$TASK_OUTPUT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research session complete (${TASK_DURATION}s) ===" >> "$LOGFILE"

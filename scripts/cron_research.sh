#!/bin/bash
# =============================================================================
# Research Cron — Dedicated research execution from QUEUE.md roadmap
# =============================================================================
# Runs 2x/day at 10:00, 16:00 CET (AM + PM for topic diversity)
# Picks ONE research task from QUEUE.md (any section with "Research:" prefix)
# and executes it via Claude Code.
# When no research tasks remain, falls back to DISCOVERY mode (was cron_research_discovery.sh).
# This consolidation freed the 14:00 slot for cron_implementation_sprint.sh.
# =============================================================================

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
LOGFILE="memory/cron/research.log"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"
QUEUE_FILE="memory/evolution/QUEUE.md"

# Prevent nested Claude sessions
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

# Acquire locks: local (with stale detection) + global Claude
acquire_local_lock "/tmp/clarvis_research.lock" "$LOGFILE" 2400
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research session starting ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Research session" --section cron_research --executor claude-opus

# Extract the FIRST unchecked research task from QUEUE.md
# Looks for items with [RESEARCH] tag, "Research:" prefix, or "Bundle " prefix
# across all sections (P0, Pillar 1-4, Backlog)
RESEARCH_TASK=$(python3 -c "
import re
with open('$QUEUE_FILE') as f:
    content = f.read()

lines = content.split('\n')
found = None

for line in lines:
    stripped = line.strip()
    # Match unchecked items that are research tasks
    if re.match(r'^-\s*\[\s*\]', stripped):
        task = re.sub(r'^-\s*\[\s*\]\s*', '', stripped)
        # Strip auto-generated source tags like [RESEARCH_DISCOVERY 2026-02-27]
        task = re.sub(r'^\[[A-Z_]+\s+\d{4}-\d{2}-\d{2}\]\s*', '', task)
        task_lower = task.lower()
        # Match research tasks by various indicators
        if any(marker in task_lower for marker in ['research:', 'bundle ', '[research', 'study ', 'paper ', 'explore ', 'investigate ']):
            found = task
            break

if found:
    print(found)
" 2>> "$LOGFILE")

if [ -z "$RESEARCH_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No pending research tasks — running discovery fallback" >> "$LOGFILE"
    # Discovery fallback: instead of a separate cron_research_discovery.sh slot,
    # we discover new topics when the research queue is empty.
    # This saves one Claude Code slot per day (was 14:00, now freed for implementation sprint).

    DISC_LOCKFILE="/tmp/clarvis_research_discovery.lock"
    if [ -f "$DISC_LOCKFILE" ]; then
        disc_pid=$(cat "$DISC_LOCKFILE" 2>/dev/null)
        if [ -n "$disc_pid" ] && kill -0 "$disc_pid" 2>/dev/null; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Discovery already running (PID $disc_pid)" >> "$LOGFILE"
            exit 0
        fi
    fi
    echo $$ > "$DISC_LOCKFILE"
    # Update trap to clean discovery lockfile AND lock_helper's locks
    trap 'rm -f "$DISC_LOCKFILE"; _lock_helper_cleanup 2>/dev/null' EXIT

    # Run discovery inline (same logic as cron_research_discovery.sh)
    CONTEXT_BRIEF_DISC=$(python3 "$SCRIPTS/prompt_builder.py" context-brief --task "identify valuable research topics" --tier standard 2>/dev/null || echo "")

    # Sources: research_ingested.json + QUEUE_ARCHIVE.md (completed research topics)
    ALREADY_RESEARCHED=$(python3 -c "
import json, os, re
seen = set()

def emit(text):
    text = re.sub(r'\s+', ' ', text).strip(' -–—:')
    if not text:
        return
    key = text.lower()
    if key not in seen:
        seen.add(key)
        print(f'  - {text}')

# 1. Topics from research ingestion tracker
tracker_file = 'data/research_ingested.json'
if os.path.exists(tracker_file):
    with open(tracker_file) as f:
        d = json.load(f)
    for name in sorted(d.keys()):
        emit(name.replace('.md', '').replace('-', ' '))

# 2. Completed research/bundle items from QUEUE_ARCHIVE.md
archive_file = 'memory/evolution/QUEUE_ARCHIVE.md'
if os.path.exists(archive_file):
    with open(archive_file) as f:
        for raw in f:
            line = raw.strip()
            if not line.startswith('- [x] '):
                continue
            body = re.sub(r'^- \[x\]\s*', '', line)
            body_no_tags = re.sub(r'\[[^\]]+\]\s*', '', body).strip()
            if re.search(r'\b(research|bundle|iit|integrated information theory|global workspace|consciousness)\b', body_no_tags, re.I):
                emit(body_no_tags)
            m = re.search(r'(Research:|Bundle\s+[A-Z]:)\s*(.*)$', body, re.I)
            if m:
                emit(f'{m.group(1)} {m.group(2)}')

if not os.path.exists(tracker_file) and not os.path.exists(archive_file):
    print('  (none)')
" 2>/dev/null)

    QUEUE_RESEARCH=$(grep -i 'research\|study\|paper\|explore\|investigate\|bundle' memory/evolution/QUEUE.md 2>/dev/null | head -10 || echo "(none)")

    DISC_OUTPUT_FILE=$(mktemp)
    DISC_START=$SECONDS

    WEAKEST_METRIC=$(get_weakest_metric)
    DISC_PROMPT_FILE=$(mktemp --suffix=.txt)
    cat > "$DISC_PROMPT_FILE" << ENDDISC
You are Clarvis's research strategist. Identify 3-5 HIGH-VALUE research topics.
QUEUE: memory/evolution/QUEUE.md is the task backlog.
WEAKEST METRIC: $WEAKEST_METRIC — at least 1 topic MUST relate to improving this.
CONTEXT: $CONTEXT_BRIEF_DISC

ALREADY RESEARCHED (do NOT duplicate): $ALREADY_RESEARCHED
IN QUEUE: $QUEUE_RESEARCH

PRIORITIES: autonomous execution, AGI architecture, consciousness/IIT, open-source tools, self-improvement.
ACTION: Search web, add 3-5 topics via: python3 scripts/queue_writer.py add "Research: [topic]" --priority P1 --source research_discovery
OUTPUT FORMAT (mandatory): TOPICS ADDED: <count>. Then list each topic on its own line.
ENDDISC

    # Category: research (1800s) — matches spawn_claude.sh --category=research
    run_claude_monitored 1800 "$DISC_OUTPUT_FILE" "$DISC_PROMPT_FILE" "$LOGFILE"
    DISC_EXIT=$MONITORED_EXIT
    DISC_DURATION=$((SECONDS - DISC_START))
    rm -f "$DISC_PROMPT_FILE"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] DISCOVERY FALLBACK: exit=$DISC_EXIT duration=${DISC_DURATION}s" >> "$LOGFILE"
    tail -c 1500 "$DISC_OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

    DISC_SUMMARY=$(tail -c 300 "$DISC_OUTPUT_FILE" 2>/dev/null | tail -3)
    {
        echo ""
        echo "### Research Discovery — $(date -u +%H:%M) UTC"
        echo ""
        if [ "$DISC_EXIT" -eq 0 ]; then
            echo "Discovered research topics (via fallback). Summary: ${DISC_SUMMARY:0:200}"
        else
            echo "Discovery FAILED. Exit=$DISC_EXIT (${DISC_DURATION}s)."
        fi
        echo ""
        echo "---"
        echo ""
    } >> "memory/cron/digest.md"

    rm -f "$DISC_OUTPUT_FILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research discovery fallback complete (${DISC_DURATION}s) ===" >> "$LOGFILE"
    exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] RESEARCH TASK: ${RESEARCH_TASK:0:120}" >> "$LOGFILE"

# Pre-compute weakest metric for prompt injection
WEAKEST_METRIC=$(get_weakest_metric)

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
    RESEARCH_PROMPT="You are Clarvis's research engine. BUNDLE session — scan 3 related topics.
TIME BUDGET: ~25 min. ~7 min/topic.
QUEUE: Mark this task [x] in memory/evolution/QUEUE.md when done.
WEAKEST METRIC: $WEAKEST_METRIC — note if research findings relate to this.
CONTEXT: $CONTEXT_BRIEF

BUNDLE: $RESEARCH_TASK

STEPS:
1. Research each of the 3 topics (web search, abstracts, key results).
2. Write ONE combined note to memory/research/ (NOT ingested/). Focus on cross-topic patterns.
3. Store 3-5 insights: python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.7 --collection clarvis-learnings
4. Mark task [x] in QUEUE.md with date.

OUTPUT FORMAT (mandatory): LEARNED: <1-sentence summary>. STORED: <count> brain memories. APPLIED: <how this helps Clarvis>."
else
    RESEARCH_PROMPT="You are Clarvis's research engine. DEEP DIVE session — one topic, thorough.
TIME BUDGET: ~25 min.
QUEUE: Mark this task [x] in memory/evolution/QUEUE.md when done.
WEAKEST METRIC: $WEAKEST_METRIC — note if research findings relate to this.
CONTEXT: $CONTEXT_BRIEF

RESEARCH TASK: $RESEARCH_TASK

STEPS:
1. Search the web for the key paper(s) or concept. Focus on abstracts + key results.
2. Store 3-5 insights: python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.8 --collection clarvis-learnings
3. Write research note to memory/research/ (NOT ingested/): title, 3-5 ideas, Clarvis application.
4. Mark task [x] in QUEUE.md with date.

OUTPUT FORMAT (mandatory): LEARNED: <1-sentence summary>. STORED: <count> brain memories. APPLIED: <how this helps Clarvis>."
fi

run_claude_monitored 1800 "$TASK_OUTPUT_FILE" "$RESEARCH_PROMPT" "$LOGFILE"
TASK_EXIT=$MONITORED_EXIT
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
    if [ "$TASK_EXIT" -eq 0 ]; then
        echo "Researched: ${RESEARCH_TASK:0:100}. Result: success (${TASK_DURATION}s). Summary: ${SUMMARY:0:200}"
    else
        echo "Research FAILED: ${RESEARCH_TASK:0:100}. Exit=$TASK_EXIT (${TASK_DURATION}s)."
    fi
    echo ""
    echo "---"
    echo ""
} >> "$DIGEST_FILE"

# === RESEARCH POSTFLIGHT: Ensure insights are stored in brain ===
# Uses brain.py ingest-research (single source of truth for ingestion logic).
# Hash-based dedup prevents double-ingestion. Files get moved to ingested/ after.
if [ "$TASK_EXIT" -eq 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running research postflight..." >> "$LOGFILE"
    python3 "$SCRIPTS/brain.py" ingest-research >> "$LOGFILE" 2>&1

    # Safety net: check for files Claude Code may have written directly to ingested/
    python3 -c "
import json, os, subprocess
tracker_file = 'data/research_ingested.json'
ingested_dir = 'memory/research/ingested'
tracker = {}
if os.path.exists(tracker_file):
    with open(tracker_file) as f:
        tracker = json.load(f)
if os.path.exists(ingested_dir):
    for fname in os.listdir(ingested_dir):
        if fname.endswith('.md') and fname not in tracker:
            fpath = os.path.join(ingested_dir, fname)
            print(f'SAFETY NET: re-ingesting untracked file: {fname}')
            subprocess.run(['python3', 'scripts/brain.py', 'ingest-research', fpath, '--force'],
                           capture_output=True, text=True)
" >> "$LOGFILE" 2>&1
fi

# Log cost estimate (Claude Code research sessions ~5k input, ~2k output tokens per minute)
python3 -c "
import sys, os
sys.path.insert(0, os.path.join('$SCRIPTS', '..', 'packages', 'clarvis-cost'))
try:
    from clarvis_cost.core import CostTracker, estimate_tokens
    COST_LOG = os.path.join('$SCRIPTS', '..', 'data', 'costs.jsonl')
    ct = CostTracker(COST_LOG)
    # Rough estimate: ~5k input + ~2k output tokens per minute of research
    duration_min = max(1, $TASK_DURATION // 60)
    task_desc = '''${RESEARCH_TASK:0:150}'''
    ct.log('claude-code', 5000 * duration_min, 2000 * duration_min,
           source='research', task=task_desc[:150], duration_s=$TASK_DURATION)
    print('Cost logged')
except Exception as e:
    print(f'Cost log failed: {e}', file=sys.stderr)
" >> "$LOGFILE" 2>&1

rm -f "$TASK_OUTPUT_FILE"

emit_dashboard_event task_completed --task-name "Research session" --section cron_research --status "$([ ${TASK_EXIT:-1} -eq 0 ] && echo success || echo failed)" --duration-s "${TASK_DURATION:-0}"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research session complete (${TASK_DURATION}s) ===" >> "$LOGFILE"

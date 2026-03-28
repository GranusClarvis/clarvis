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
        task_lower = task.lower()
        # Match research tasks by various indicators
        if any(marker in task_lower for marker in ['research:', 'bundle ', '[research', 'study ', 'paper ', 'explore ', 'investigate ']):
            found = task
            break

if found:
    print(found)
" 2>> "$LOGFILE")

if [ -z "$RESEARCH_TASK" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] No pending research tasks" >> "$LOGFILE"

    # Research auto-replenish can be paused by user preference.
    # When paused, cron_research only executes explicitly queued research tasks
    # and does NOT auto-discover/add new research topics.
    RESEARCH_AUTO_REPLENISH="${RESEARCH_AUTO_REPLENISH:-0}"
    if [ "$RESEARCH_AUTO_REPLENISH" != "1" ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Auto-replenish paused; exiting without discovery fallback" >> "$LOGFILE"
        exit 0
    fi

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Auto-replenish enabled — running discovery fallback" >> "$LOGFILE"
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

# === STAGE 1: PRE-SELECT NOVELTY GATE ===
# Check if this topic has already been thoroughly researched.
# Exit codes: 0=proceed (NEW/REFINEMENT), 1=skip (ALREADY_KNOWN)
NOVELTY_RESULT=$(python3 "$SCRIPTS/research_novelty.py" classify "$RESEARCH_TASK" 2>> "$LOGFILE")
NOVELTY_EXIT=$?
NOVELTY_TIER=$(echo "$NOVELTY_RESULT" | grep "^NOVELTY:" | head -1 | sed 's/NOVELTY: //')
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] NOVELTY CHECK: tier=$NOVELTY_TIER exit=$NOVELTY_EXIT" >> "$LOGFILE"
echo "$NOVELTY_RESULT" >> "$LOGFILE"

if [ "$NOVELTY_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: topic is ALREADY_KNOWN — marking complete and exiting" >> "$LOGFILE"
    # Mark as complete with skip annotation so it doesn't get re-selected
    export RESEARCH_TASK
    python3 - <<'PY' >> "$LOGFILE" 2>&1
import os, sys
from datetime import datetime, timezone
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from queue_writer import mark_task_complete, archive_completed
queue_file = 'memory/evolution/QUEUE.md'
archive_file = 'memory/evolution/QUEUE_ARCHIVE.md'
task = os.environ.get('RESEARCH_TASK', '').strip()
annotation = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') + ' SKIP:duplicate'
result = mark_task_complete(task, annotation, queue_file=queue_file, archive_file=archive_file)
print(f'Queue skip-mark result: {result}')
archive_completed()
PY
    {
        echo ""
        echo "### Research — $(date -u +%H:%M) UTC"
        echo ""
        echo "SKIPPED (ALREADY_KNOWN): ${RESEARCH_TASK:0:100}. Duplicate topic detected by novelty gate."
        echo ""
        echo "---"
        echo ""
    } >> "memory/cron/digest.md"
    emit_dashboard_event task_completed --task-name "Research session" --section cron_research --status "skipped:duplicate" --duration-s "0"
    exit 0
fi

# === STAGE 2: PREPARE SCOPED ARTIFACT DIRECTORY ===
# Each research run writes to its own directory to prevent cross-run pollution.
RUN_ID=$(date -u +%Y-%m-%d-%H%M%S)
RUN_DIR="memory/research/runs/$RUN_ID"
mkdir -p "$RUN_DIR"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Run dir: $RUN_DIR (novelty=$NOVELTY_TIER)" >> "$LOGFILE"

# Pre-compute weakest metric for prompt injection
WEAKEST_METRIC=$(get_weakest_metric)

# Generate a minimal context brief
CONTEXT_BRIEF=$(python3 "$SCRIPTS/context_compressor.py" brief 2>> "$LOGFILE")

# Inject cross-run lessons (MetaClaw-inspired pattern)
PAST_LESSONS=$(python3 "$SCRIPTS/research_lesson_store.py" inject 2>/dev/null || echo "")

# Execute via Claude Code with generous timeout (research = deep thinking)
TASK_OUTPUT_FILE=$(mktemp)
TASK_START=$SECONDS

# Detect if this is a bundle (scan 3 topics) or a deep dive (1 topic)
IS_BUNDLE="false"
if echo "$RESEARCH_TASK" | grep -q "^Bundle "; then
    IS_BUNDLE="true"
fi

# Structured output format shared by both prompt types
STRUCTURED_OUTPUT_FMT="OUTPUT FORMAT (mandatory — must appear at end of your response):
RESEARCH_RESULT:
  TOPIC: <topic name>
  DECISION: APPLY|ARCHIVE|DISCARD
  FINDINGS: <1-3 sentence summary of what was learned>
  RELEVANCE: <how this helps Clarvis specifically>
  QUEUE_ITEMS: <semicolon-separated list of concrete implementation tasks, or 'none'>
  EFFORT: S|M|L
  STORED: <count> brain memories
If DECISION=APPLY, also queue items: python3 scripts/queue_writer.py add '<task>' --priority P1 --source research"

# IMPORTANT: Claude Code MUST write research notes to the scoped run directory,
# not to memory/research/ root. This prevents cross-run artifact pollution.
ARTIFACT_INSTRUCTION="ARTIFACT RULE: Write ALL research notes to $RUN_DIR/ (NOT memory/research/ root, NOT ingested/).
One markdown file per topic. Filename format: <topic-slug>.md"

if [ "$IS_BUNDLE" = "true" ]; then
    RESEARCH_PROMPT="You are Clarvis's research engine. BUNDLE session — scan 3 related topics.
TIME BUDGET: ~25 min. ~7 min/topic.
QUEUE: Mark this task [x] in memory/evolution/QUEUE.md when done.
WEAKEST METRIC: $WEAKEST_METRIC — note if research findings relate to this.
CONTEXT: $CONTEXT_BRIEF
$PAST_LESSONS
$ARTIFACT_INSTRUCTION

BUNDLE: $RESEARCH_TASK

STEPS:
1. Research each of the 3 topics (web search, abstracts, key results).
2. Write ONE combined note to $RUN_DIR/ (NOT memory/research/ root, NOT ingested/). Focus on cross-topic patterns.
3. Store 3-5 insights: python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.7 --collection clarvis-learnings
4. Mark task [x] in QUEUE.md with date.
5. Evaluate: is this actionable for Clarvis? Set DECISION accordingly.

$STRUCTURED_OUTPUT_FMT"
else
    RESEARCH_PROMPT="You are Clarvis's research engine. DEEP DIVE session — one topic, thorough.
TIME BUDGET: ~25 min.
QUEUE: Mark this task [x] in memory/evolution/QUEUE.md when done.
WEAKEST METRIC: $WEAKEST_METRIC — note if research findings relate to this.
CONTEXT: $CONTEXT_BRIEF
$PAST_LESSONS
$ARTIFACT_INSTRUCTION

RESEARCH TASK: $RESEARCH_TASK

STEPS:
1. Search the web for the key paper(s) or concept. Focus on abstracts + key results.
2. Store 3-5 insights: python3 scripts/brain.py remember 'I learned that [insight]' --importance 0.8 --collection clarvis-learnings
3. Write research note to $RUN_DIR/ (NOT memory/research/ root, NOT ingested/): title, 3-5 ideas, Clarvis application.
4. Mark task [x] in QUEUE.md with date.
5. Evaluate: is this actionable for Clarvis? Set DECISION accordingly.

$STRUCTURED_OUTPUT_FMT"
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

# Deterministic queue completion: do NOT rely on Claude to remember to tick the box.
if [ "$TASK_EXIT" -eq 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Marking research task complete in QUEUE.md..." >> "$LOGFILE"
    export RESEARCH_TASK
    python3 - <<'PY' >> "$LOGFILE" 2>&1
import os, sys
from datetime import datetime, timezone
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from queue_writer import mark_task_complete, archive_completed

queue_file = 'memory/evolution/QUEUE.md'
archive_file = 'memory/evolution/QUEUE_ARCHIVE.md'
research_task = os.environ.get('RESEARCH_TASK', '').strip()
annotation = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

result = mark_task_complete(research_task, annotation, queue_file=queue_file, archive_file=archive_file)
print(f'Queue mark result: {result}')
archived = archive_completed()
print(f'Queue archive moved: {archived}')
PY
fi

# === STAGE 3: POST-EXECUTE NOVELTY GATE + SCOPED INGESTION ===
# Only ingest files from the run directory. Evaluate each file's novelty before ingestion.
# NO root sweep of memory/research/*.md — that was the source of duplication.
if [ "$TASK_EXIT" -eq 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running scoped research postflight (run=$RUN_ID)..." >> "$LOGFILE"

    # Also pick up files Claude Code wrote to memory/research/ root DURING THIS RUN
    # (despite instructions) and move them into the run dir for unified processing.
    # Only move files newer than the run start to avoid swallowing unrelated historical files.
    RUN_START_EPOCH=$(date -u -d "$RUN_ID" +%s 2>/dev/null || date -u +%s)
    for stray in memory/research/*.md; do
        [ -f "$stray" ] || continue
        fname=$(basename "$stray")
        # Skip known permanent files
        case "$fname" in OBLITERATUS_review.md) continue ;; esac
        MTIME=$(stat -c %Y "$stray" 2>/dev/null || echo 0)
        if [ "$MTIME" -lt "$RUN_START_EPOCH" ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Leaving pre-existing root artifact in place: $fname" >> "$LOGFILE"
            continue
        fi
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Moving stray artifact $fname → $RUN_DIR/" >> "$LOGFILE"
        mv "$stray" "$RUN_DIR/$fname"
    done

    # Process each file in the run directory through the novelty gate
    INGESTED_COUNT=0
    SKIPPED_COUNT=0
    for research_file in "$RUN_DIR"/*.md; do
        [ -f "$research_file" ] || continue
        fname=$(basename "$research_file")

        # Evaluate novelty of this specific file
        FILE_NOVELTY=$(python3 "$SCRIPTS/research_novelty.py" evaluate-file "$research_file" 2>> "$LOGFILE")
        FILE_NOVELTY_EXIT=$?
        FILE_TIER=$(echo "$FILE_NOVELTY" | grep "^NOVELTY:" | head -1 | sed 's/NOVELTY: //')
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] File novelty: $fname → $FILE_TIER (exit=$FILE_NOVELTY_EXIT)" >> "$LOGFILE"

        if [ "$FILE_NOVELTY_EXIT" -ne 0 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP INGESTION: $fname is ALREADY_KNOWN" >> "$LOGFILE"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi

        # Ingest this specific file (not a root sweep)
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Ingesting $fname (novelty=$FILE_TIER)..." >> "$LOGFILE"
        python3 "$SCRIPTS/brain.py" ingest-research "$research_file" >> "$LOGFILE" 2>&1

        # Register topic in the novelty registry
        TOPIC_NAME=$(python3 -c "
with open('$research_file') as f:
    for line in f:
        if line.startswith('# '):
            print(line[2:].strip()); break
" 2>/dev/null)
        [ -z "$TOPIC_NAME" ] && TOPIC_NAME="$fname"
        python3 "$SCRIPTS/research_novelty.py" register "$TOPIC_NAME" --source "$fname" --memories 1 >> "$LOGFILE" 2>&1

        INGESTED_COUNT=$((INGESTED_COUNT + 1))
    done

    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Postflight: ingested=$INGESTED_COUNT skipped=$SKIPPED_COUNT" >> "$LOGFILE"
fi

    # === LESSON RECORDING: Extract structured output and record lesson ===
    python3 -c "
import sys, os, re
sys.path.insert(0, '$SCRIPTS')
from research_lesson_store import ResearchLessonStore

output_file = '$TASK_OUTPUT_FILE'
if not os.path.exists(output_file):
    sys.exit(0)

with open(output_file) as f:
    text = f.read()

# Parse RESEARCH_RESULT block from output
topic = decision = findings = queue_items_str = ''
for line in text.split('\n'):
    line = line.strip()
    if line.startswith('TOPIC:'):
        topic = line[6:].strip()
    elif line.startswith('DECISION:'):
        decision = line[9:].strip().upper()
    elif line.startswith('FINDINGS:'):
        findings = line[9:].strip()
    elif line.startswith('QUEUE_ITEMS:'):
        queue_items_str = line[12:].strip()

if not topic:
    topic = '''${RESEARCH_TASK:0:100}'''
if not decision:
    decision = 'ARCHIVE'  # Default if Claude didn't produce structured output
if not findings:
    # Fall back to last 200 chars of output
    findings = text[-200:].strip()

queue_items = [i.strip() for i in queue_items_str.split(';') if i.strip() and i.strip().lower() != 'none']

store = ResearchLessonStore()
lesson = store.record(topic=topic, decision=decision, findings=findings, queue_items=queue_items)
print(f'Lesson recorded: [{lesson.decision}] {lesson.topic[:60]}')
" >> "$LOGFILE" 2>&1

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

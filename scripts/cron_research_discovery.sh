#!/bin/bash
# =============================================================================
# Research Discovery Cron — Populate the research queue with valuable topics
# =============================================================================
# Runs 1x/day at 14:00 UTC
# Uses Claude Code to identify valuable research topics aligned with goals:
# - Autonomy, AGI, consciousness, self-improvement
# - Open-source repos and tools that could help Clarvis
# - Papers and frameworks relevant to current architecture
# Adds discovered topics to QUEUE.md research sections via queue_writer.py
# =============================================================================

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh
LOGFILE="memory/cron/research.log"
SCRIPTS="/home/agent/.openclaw/workspace/scripts"

# Acquire locks: local (with 1200s stale detection) + global Claude
acquire_local_lock "/tmp/clarvis_research_discovery.lock" "$LOGFILE" 1200
acquire_global_claude_lock "$LOGFILE" "queue"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research Discovery starting ===" >> "$LOGFILE"

# Get current goals and brain state for context
CONTEXT_BRIEF=$(python3 "$SCRIPTS/prompt_builder.py" context-brief --task "identify valuable research topics" --tier standard 2>/dev/null || echo "")

# Get list of already-researched topics to avoid duplicates
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

# Get current research items already in queue
QUEUE_RESEARCH=$(grep -i 'research\|study\|paper\|explore\|investigate\|bundle' memory/evolution/QUEUE.md 2>/dev/null | head -10 || echo "(none)")

TASK_OUTPUT_FILE=$(mktemp)
TASK_START=$SECONDS

PROMPT_FILE=$(mktemp --suffix=.txt)
cat > "$PROMPT_FILE" << 'ENDPROMPT'
You are Clarvis's research strategist. Your job is to identify 3-5 HIGH-VALUE research topics that will advance Clarvis's goals.

CONTEXT:
ENDPROMPT
echo "$CONTEXT_BRIEF" >> "$PROMPT_FILE"
cat >> "$PROMPT_FILE" << ENDPROMPT

ALREADY RESEARCHED (do NOT duplicate these):
$ALREADY_RESEARCHED

CURRENTLY IN QUEUE:
$QUEUE_RESEARCH

RESEARCH PRIORITIES (what matters most for Clarvis):
1. AUTONOMOUS EXECUTION — How to build agents that act independently: browser automation, self-directed task execution, multi-step planning, recovery from failures
2. AGI ARCHITECTURE — Cognitive architectures, meta-learning, self-modification, reasoning systems, knowledge graphs
3. CONSCIOUSNESS & INTEGRATION — IIT (Integrated Information Theory), Global Workspace Theory, phi metrics, information integration, phenomenal binding
4. OPEN-SOURCE TOOLS — GitHub repos, frameworks, libraries that Clarvis could use: agent frameworks, browser automation, LLM orchestration, memory systems, vector DBs
5. SELF-IMPROVEMENT — How systems can improve themselves: evolutionary algorithms, population-based training, auto-ML, curriculum learning

INSTRUCTIONS:
1. Search the web for 3-5 specific research topics that are:
   - Highly relevant to one of the 5 priorities above
   - NOT already researched (check the list above)
   - Concrete enough to research in a 25-minute session
   - From reputable sources (papers, major repos, well-known researchers)

2. For each topic, write a one-line description formatted as a research task.

3. Add each topic to the research queue using queue_writer.py:
   python3 scripts/queue_writer.py add "Research: [topic] — [1-line description]" --priority P1 --source research_discovery

4. Output a summary of what topics you added and why they're valuable.

Be specific — "Research: MRKL Systems (Karpas et al. 2022) — modular reasoning and knowledge integration for LLM agents" is better than "Research: agent architectures".
ENDPROMPT

timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT /home/agent/.local/bin/claude -p \
    "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions --model claude-opus-4-6 \
    > "$TASK_OUTPUT_FILE" 2>&1
TASK_EXIT=$?
TASK_DURATION=$((SECONDS - TASK_START))
rm -f "$PROMPT_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] DISCOVERY: exit=$TASK_EXIT duration=${TASK_DURATION}s" >> "$LOGFILE"
tail -c 1500 "$TASK_OUTPUT_FILE" >> "$LOGFILE" 2>/dev/null

# Update digest
SUMMARY=$(tail -c 300 "$TASK_OUTPUT_FILE" 2>/dev/null | tail -3)
{
    echo ""
    echo "### Research Discovery — $(date -u +%H:%M) UTC"
    echo ""
    if [ "$TASK_EXIT" -eq 0 ]; then
        echo "Discovered research topics. Summary: ${SUMMARY:0:200}"
    else
        echo "Discovery FAILED. Exit=$TASK_EXIT (${TASK_DURATION}s)."
    fi
    echo ""
    echo "---"
    echo ""
} >> "memory/cron/digest.md"

rm -f "$TASK_OUTPUT_FILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Research Discovery complete (${TASK_DURATION}s) ===" >> "$LOGFILE"

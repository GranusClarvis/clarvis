#!/bin/bash
# Daily reflection - consolidate memory AND generate new evolution tasks
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron_reflection.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection starting ===" >> "$LOGFILE"

# Step 1: Memory optimization (decay stale memories)
python3 -c "
import sys
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain
brain.optimize()
print('brain.optimize() complete')
" >> "$LOGFILE" 2>&1

# Step 2: Run full reflection loop (extract lessons + generate queue tasks)
python3 /home/agent/.openclaw/workspace/scripts/clarvis_reflection.py >> "$LOGFILE" 2>&1

# Step 3: Knowledge synthesis — find cross-domain connections between today's work and past learnings
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running knowledge synthesis..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/knowledge_synthesis.py >> "$LOGFILE" 2>&1

# Step 3.5: Cross-collection linking — ensure all memories have cross-collection edges
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running cross-collection linking..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/brain.py crosslink >> "$LOGFILE" 2>&1

# Step 4: Memory consolidation — deduplicate, prune noise, archive stale
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running memory consolidation..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/memory_consolidation.py consolidate >> "$LOGFILE" 2>&1

# Step 5: Conversation learning — extract patterns from transcripts, store insights
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running conversation learner..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/conversation_learner.py >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection complete ===" >> "$LOGFILE"

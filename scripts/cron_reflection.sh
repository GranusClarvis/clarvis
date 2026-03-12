#!/bin/bash
# Daily reflection - consolidate memory AND generate new evolution tasks
source /home/agent/.openclaw/workspace/scripts/cron_env.sh
source /home/agent/.openclaw/workspace/scripts/lock_helper.sh

LOGFILE="memory/cron/reflection.log"

# Acquire locks: local + global Claude (reflection writes to brain/QUEUE/graph)
acquire_local_lock "/tmp/clarvis_reflection.lock" "$LOGFILE"
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection starting ===" >> "$LOGFILE"
emit_dashboard_event task_started --task-name "Daily reflection" --section cron_reflection --executor claude-opus

# Step 0: QUEUE.md scan — count pending/completed for digest metrics
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Scanning QUEUE.md..." >> "$LOGFILE"
QUEUE_PENDING=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
QUEUE_DONE=$(grep -c '^\- \[x\]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
WEAKEST_METRIC=$(get_weakest_metric)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] QUEUE: $QUEUE_PENDING pending, $QUEUE_DONE completed. Weakest: $WEAKEST_METRIC" >> "$LOGFILE"

# Step 0.5: Context window GC — archive old completed tasks, rotate oversized logs
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running context window GC..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/context_compressor.py gc >> "$LOGFILE" 2>&1 || true

# Step 1: Memory optimization (decay stale memories) — CRITICAL
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running brain optimize..." >> "$LOGFILE"
python3 -m clarvis brain optimize >> "$LOGFILE" 2>&1
OPTIMIZE_EXIT=$?
if [ "$OPTIMIZE_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARNING: brain optimize failed with exit $OPTIMIZE_EXIT" >> "$LOGFILE"
fi

# Step 2: Run full reflection loop (extract lessons + generate queue tasks)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running reflection loop..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/clarvis_reflection.py >> "$LOGFILE" 2>&1 || true

# Step 3: Knowledge synthesis — find cross-domain connections between today's work and past learnings
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running knowledge synthesis..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/knowledge_synthesis.py >> "$LOGFILE" 2>&1 || true

# Step 3.5: Cross-collection linking — ensure all memories have cross-collection edges
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running cross-collection linking..." >> "$LOGFILE"
python3 -m clarvis brain crosslink >> "$LOGFILE" 2>&1 || true

# Step 3.6: Intra-collection linking — boost within-collection edge density (cap 5/collection)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running intra-collection linker..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/intra_linker.py --cap 5 >> "$LOGFILE" 2>&1 || true

# Step 3.7: Semantic bridge building — fill weak cross-collection gaps (cap 5/run)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running semantic bridge builder..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/semantic_bridge_builder.py --top 2 >> "$LOGFILE" 2>&1 || true

# Step 4: Memory consolidation — deduplicate, prune noise, archive stale
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running memory consolidation..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/memory_consolidation.py consolidate >> "$LOGFILE" 2>&1 || true

# Step 4.5: Hebbian memory evolution — strengthen frequently accessed, weaken neglected (A-Mem style)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running Hebbian memory evolution..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/hebbian_memory.py evolve >> "$LOGFILE" 2>&1 || true

# Step 4.6: Synaptic memory evolution — memristor-inspired STDP weight updates + consolidation
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running synaptic memory evolution..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/synaptic_memory.py evolve >> "$LOGFILE" 2>&1 || true
python3 /home/agent/.openclaw/workspace/scripts/synaptic_memory.py consolidate >> "$LOGFILE" 2>&1 || true

# Step 5: Conversation learning — extract patterns from transcripts, store insights
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running conversation learner..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/conversation_learner.py >> "$LOGFILE" 2>&1 || true

# Step 5.5: Failure amplification — surface soft failures (timeouts, retries, low scores) as negative episodes
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running failure amplifier..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/failure_amplifier.py amplify >> "$LOGFILE" 2>&1 || true

# Step 6: Episodic synthesis — analyze episodes, generate new goals from experiential patterns
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running episodic synthesis..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/episodic_memory.py synthesize >> "$LOGFILE" 2>&1 || true

# Step 6.5: Temporal self-awareness — generate growth narrative (how have I changed?)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running temporal self-awareness..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/temporal_self.py store >> "$LOGFILE" 2>&1 || true

# Step 6.7: Meta-learning — analyze learning strategies, failure patterns, recommend improvements
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running meta-learning analysis..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/meta_learning.py analyze >> "$LOGFILE" 2>&1 || true

# Step 6.9: Absolute Zero Reasoner — self-improvement through autonomous task generation (AZR)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running Absolute Zero Reasoner..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/absolute_zero.py run 3 >> "$LOGFILE" 2>&1 || true

# Step 6.95: Causal Analysis (Pearl SCM) — build structural causal model, run do-calculus, store findings
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running causal analysis (Pearl SCM)..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/causal_model.py analyze >> "$LOGFILE" 2>&1 || true

# Step 7: Session close — save attention state and working memory for next session — CRITICAL
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running session close..." >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/session_hook.py close >> "$LOGFILE" 2>&1
SESSION_EXIT=$?
if [ "$SESSION_EXIT" -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARNING: session_hook.py close failed with exit $SESSION_EXIT" >> "$LOGFILE"
fi

# === DIGEST: Write first-person summary for M2.5 agent ===
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py reflection \
    "REFLECTION: complete. QUEUE: ${QUEUE_PENDING} pending, ${QUEUE_DONE} done. WEAKEST: ${WEAKEST_METRIC}. Pipeline: optimize, reflect, synthesize, crosslink, consolidate, learn, amplify, episodic, temporal, meta-learn, AZR, causal. Session saved." \
    >> "$LOGFILE" 2>&1 || true

emit_dashboard_event task_completed --task-name "Daily reflection" --section cron_reflection --status success
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection complete ===" >> "$LOGFILE"

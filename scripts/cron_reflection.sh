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

# Failure tracking — continue on error but log and count failures
STEP_FAILURES=0
FAILED_STEPS=""

run_step() {
    local step_name="$1"
    shift
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running ${step_name}..." >> "$LOGFILE"
    "$@" >> "$LOGFILE" 2>&1
    local exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] WARNING: ${step_name} failed (exit ${exit_code})" >> "$LOGFILE"
        STEP_FAILURES=$((STEP_FAILURES + 1))
        FAILED_STEPS="${FAILED_STEPS} ${step_name}"
    fi
    return 0  # always continue
}

# Step 0: QUEUE.md scan — count pending/completed for digest metrics
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Scanning QUEUE.md..." >> "$LOGFILE"
QUEUE_PENDING=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
QUEUE_DONE=$(grep -c '^\- \[x\]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
WEAKEST_METRIC=$(get_weakest_metric)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] QUEUE: $QUEUE_PENDING pending, $QUEUE_DONE completed. Weakest: $WEAKEST_METRIC" >> "$LOGFILE"

# Step 0.5: Context window GC
run_step "context_gc" python3 /home/agent/.openclaw/workspace/scripts/context_compressor.py gc

# Step 1: Memory optimization (decay stale memories)
run_step "brain_optimize" python3 -m clarvis brain optimize

# Step 2: Full reflection loop (extract lessons + generate queue tasks)
run_step "reflection_loop" python3 /home/agent/.openclaw/workspace/scripts/clarvis_reflection.py

# Step 3: Knowledge synthesis — cross-domain connections
run_step "knowledge_synthesis" python3 /home/agent/.openclaw/workspace/scripts/knowledge_synthesis.py

# Step 3.5: Cross-collection linking
run_step "crosslink" python3 -m clarvis brain crosslink

# Step 3.6: Intra-collection linking (cap 5/collection)
run_step "intra_linker" python3 /home/agent/.openclaw/workspace/scripts/intra_linker.py --cap 5

# Step 3.7: Semantic bridge building (cap 5/run)
run_step "semantic_bridge" python3 /home/agent/.openclaw/workspace/scripts/semantic_bridge_builder.py --top 2

# Step 4: Memory consolidation — deduplicate, prune noise, archive stale
run_step "memory_consolidation" python3 /home/agent/.openclaw/workspace/scripts/memory_consolidation.py consolidate

# Step 4.5: Hebbian memory evolution (A-Mem style)
run_step "hebbian_evolve" python3 /home/agent/.openclaw/workspace/scripts/hebbian_memory.py evolve

# Step 4.6: Synaptic memory evolution — STDP weight updates + consolidation
run_step "synaptic_evolve" python3 /home/agent/.openclaw/workspace/scripts/synaptic_memory.py evolve
run_step "synaptic_consolidate" python3 /home/agent/.openclaw/workspace/scripts/synaptic_memory.py consolidate

# Step 5: Conversation learning
run_step "conversation_learner" python3 /home/agent/.openclaw/workspace/scripts/conversation_learner.py

# Step 5.5: Failure amplification — surface soft failures as negative episodes
run_step "failure_amplifier" python3 /home/agent/.openclaw/workspace/scripts/failure_amplifier.py amplify

# Step 6: Episodic synthesis
run_step "episodic_synthesis" python3 /home/agent/.openclaw/workspace/scripts/episodic_memory.py synthesize

# Step 6.5: Temporal self-awareness
run_step "temporal_self" python3 /home/agent/.openclaw/workspace/scripts/temporal_self.py store

# Step 6.7: Meta-learning analysis
run_step "meta_learning" python3 /home/agent/.openclaw/workspace/scripts/meta_learning.py analyze

# Step 6.9: Absolute Zero Reasoner (AZR)
run_step "absolute_zero" python3 /home/agent/.openclaw/workspace/scripts/absolute_zero.py run 3

# Step 6.95: Causal Analysis (Pearl SCM)
run_step "causal_model" python3 /home/agent/.openclaw/workspace/scripts/causal_model.py analyze

# Step 7: Session close — save attention state and working memory for next session — CRITICAL
run_step "session_close" python3 /home/agent/.openclaw/workspace/scripts/session_hook.py close

# === Failure summary ===
if [ "$STEP_FAILURES" -gt 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PIPELINE FAILURES: ${STEP_FAILURES} step(s) failed:${FAILED_STEPS}" >> "$LOGFILE"
    DIGEST_STATUS="REFLECTION: ${STEP_FAILURES} step(s) failed:${FAILED_STEPS}."
else
    DIGEST_STATUS="REFLECTION: complete, all steps passed."
fi

# === DIGEST: Write first-person summary for M2.5 agent ===
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py reflection \
    "${DIGEST_STATUS} QUEUE: ${QUEUE_PENDING} pending, ${QUEUE_DONE} done. WEAKEST: ${WEAKEST_METRIC}. Pipeline: optimize, reflect, synthesize, crosslink, consolidate, learn, amplify, episodic, temporal, meta-learn, AZR, causal. Session saved." \
    >> "$LOGFILE" 2>&1 || true

if [ "$STEP_FAILURES" -gt 0 ]; then
    emit_dashboard_event task_completed --task-name "Daily reflection" --section cron_reflection --status partial --meta "failures=${STEP_FAILURES}"
else
    emit_dashboard_event task_completed --task-name "Daily reflection" --section cron_reflection --status success
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection complete (${STEP_FAILURES} failures) ===" >> "$LOGFILE"

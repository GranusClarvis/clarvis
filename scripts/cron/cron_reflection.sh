#!/bin/bash
# Daily reflection - consolidate memory AND generate new evolution tasks
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/reflection.log"

# Acquire local lock only — reflection runs Python steps (no Claude Code spawning)
# Previously acquired global Claude lock but this blocked autonomous runs for 3+ hours
# unnecessarily (reflection only does brain optimization, not Claude Code execution).
# Removed 2026-03-15 per cron schedule audit.
# Stale threshold: 7200s (2h) — prevents zombie locks from blocking future runs.
# Added 2026-03-29 after 24h stuck reflection caused system-wide process exhaustion.
acquire_local_lock "/tmp/clarvis_reflection.lock" "$LOGFILE" 7200

# Arm timeout watchdog — kill after 3600s (1h) to prevent runaway reflection.
# Added 2026-03-29: memory_consolidation.py hung for 22h, exhausted NPROC limit.
set_script_timeout 3600 "$LOGFILE"

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
run_step "context_gc" python3 -m clarvis context gc

# Step 1: Memory optimization (decay stale memories)
run_step "brain_optimize" python3 -m clarvis brain optimize

# Step 2: Full reflection loop (extract lessons + generate queue tasks)
run_step "reflection_loop" python3 "$CLARVIS_WORKSPACE/scripts/cognition/clarvis_reflection.py"

# Step 3: Knowledge synthesis — cross-domain connections
run_step "knowledge_synthesis" python3 "$CLARVIS_WORKSPACE/scripts/cognition/knowledge_synthesis.py"

# Step 3.5: Cross-collection linking
run_step "crosslink" python3 -m clarvis brain crosslink

# Step 3.6: Intra-collection linking (cap 5/collection)
run_step "intra_linker" python3 "$CLARVIS_WORKSPACE/scripts/hooks/intra_linker.py" --cap 5

# Step 3.7: Semantic bridge building (cap 5/run)
# semantic_bridge_builder.py was removed; skip this step.
# run_step "semantic_bridge" python3 $CLARVIS_WORKSPACE/scripts/hooks/semantic_bridge_builder.py --top 2

# Step 4: Memory consolidation — deduplicate, prune noise, archive stale
run_step "memory_consolidation" python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/memory_consolidation.py" consolidate

# Step 4.5: Hebbian memory evolution (A-Mem style)
run_step "hebbian_evolve" python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/hebbian_memory.py" evolve

# Step 4.6: Synaptic memory evolution — STDP weight updates + consolidation
run_step "synaptic_evolve" python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/synaptic_memory.py" evolve
run_step "synaptic_consolidate" python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/synaptic_memory.py" consolidate

# Step 5: Conversation learning
run_step "conversation_learner" python3 "$CLARVIS_WORKSPACE/scripts/cognition/conversation_learner.py"

# Step 5.5: Failure amplification — surface soft failures as negative episodes
run_step "failure_amplifier" python3 "$CLARVIS_WORKSPACE/scripts/evolution/failure_amplifier.py" amplify

# Step 6: Episodic synthesis
run_step "episodic_synthesis" python3 "$CLARVIS_WORKSPACE/scripts/brain_mem/episodic_memory.py" synthesize

# Step 6.5: Temporal self-awareness
run_step "temporal_self" python3 "$CLARVIS_WORKSPACE/scripts/hooks/temporal_self.py" store

# Step 6.7: Meta-learning analysis
run_step "meta_learning" python3 "$CLARVIS_WORKSPACE/scripts/evolution/meta_learning.py" analyze

# Step 6.9: Absolute Zero Reasoner (AZR)
run_step "absolute_zero" python3 "$CLARVIS_WORKSPACE/scripts/cognition/absolute_zero.py" run 3

# Step 6.95: Causal Analysis (Pearl SCM)
run_step "causal_model" python3 "$CLARVIS_WORKSPACE/scripts/cognition/causal_model.py" analyze

# Step 6.96: Confidence recalibration (7-day rolling window)
run_step "recalibrate" python3 -c "from clarvis.cognition.confidence import recalibrate; r = recalibrate(); print(f'Brier 7d={r[\"brier_7d\"]}, all={r[\"brier_all\"]}, shift={r[\"shift_detected\"]}, threshold={r[\"new_threshold\"]}, archived={r[\"archived\"]}, swept={r[\"swept\"]}')"

# Step 6.97: Brain Effectiveness Scoring — stores retrievable memory in clarvis-learnings
# Answers "does the brain help decisions?" by aggregating CLR, episodes, chains, eval
run_step "brain_effectiveness" python3 "$CLARVIS_WORKSPACE/scripts/metrics/brain_effectiveness.py" compute_and_store

# Step 6.98: Research-to-Queue bridge (monthly — 1st of month only)
# Gated by durable config: data/research_config.json (research_bridge_monthly)
DAY_OF_MONTH=$(date +%d)
if [ "$DAY_OF_MONTH" = "01" ]; then
    BRIDGE_ALLOWED=$(python3 -c "
from clarvis.research_config import is_enabled
print('1' if is_enabled('research_bridge_monthly') else '0')
" 2>/dev/null || echo "0")
    if [ "$BRIDGE_ALLOWED" = "1" ]; then
        run_step "research_bridge" python3 "$CLARVIS_WORKSPACE/scripts/evolution/research_to_queue.py" inject --max 3
    else
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Research bridge OFF (research_config.json) — skipping" >> "$LOGFILE"
    fi
fi

# Step 7: Session close — save attention state and working memory for next session — CRITICAL
run_step "session_close" python3 "$CLARVIS_WORKSPACE/scripts/hooks/session_hook.py" close

# === Failure summary ===
if [ "$STEP_FAILURES" -gt 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] PIPELINE FAILURES: ${STEP_FAILURES} step(s) failed:${FAILED_STEPS}" >> "$LOGFILE"
    DIGEST_STATUS="REFLECTION: ${STEP_FAILURES} step(s) failed:${FAILED_STEPS}."
else
    DIGEST_STATUS="REFLECTION: complete, all steps passed."
fi

# === DIGEST: Write first-person summary for M2.5 agent ===
python3 "$CLARVIS_WORKSPACE/scripts/tools/digest_writer.py" reflection \
    "${DIGEST_STATUS} QUEUE: ${QUEUE_PENDING} pending, ${QUEUE_DONE} done. WEAKEST: ${WEAKEST_METRIC}. Pipeline: optimize, reflect, synthesize, crosslink, consolidate, learn, amplify, episodic, temporal, meta-learn, AZR, causal, brain-effectiveness. Session saved." \
    >> "$LOGFILE" 2>&1 || true

if [ "$STEP_FAILURES" -gt 0 ]; then
    emit_dashboard_event task_completed --task-name "Daily reflection" --section cron_reflection --status partial --meta "failures=${STEP_FAILURES}"
else
    emit_dashboard_event task_completed --task-name "Daily reflection" --section cron_reflection --status success
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Reflection complete (${STEP_FAILURES} failures) ===" >> "$LOGFILE"

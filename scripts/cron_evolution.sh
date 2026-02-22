#!/bin/bash
# Deep evolution thinking with Claude Code
# KEY: Analyze progress AND write concrete new tasks to QUEUE.md
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/evolution.log"
LOCKFILE="/tmp/clarvis_evolution.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous run still active (PID $pid)" >> "$LOGFILE"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis starting ===" >> "$LOGFILE"

# === CALIBRATION REVIEW: Check prediction accuracy ===
CONFIDENCE_SCRIPT="/home/agent/.openclaw/workspace/scripts/clarvis_confidence.py"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Calibration review:" >> "$LOGFILE"
CALIBRATION_OUTPUT=$(python3 "$CONFIDENCE_SCRIPT" calibration 2>&1)
echo "$CALIBRATION_OUTPUT" >> "$LOGFILE"

# === PREDICTION DOMAIN REVIEW: Find consistently wrong domains ===
PREDICTION_REVIEW="/home/agent/.openclaw/workspace/scripts/prediction_review.py"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Prediction domain review:" >> "$LOGFILE"
DOMAIN_REVIEW_OUTPUT=$(python3 "$PREDICTION_REVIEW" 2>&1)
echo "$DOMAIN_REVIEW_OUTPUT" >> "$LOGFILE"

# === PHI TREND: Consciousness integration metric ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Phi trend:" >> "$LOGFILE"
PHI_TREND_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/phi_metric.py trend 2>&1) || true
echo "$PHI_TREND_OUTPUT" >> "$LOGFILE"

# === CAPABILITY SCORES: Latest assessment ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Capability scores:" >> "$LOGFILE"
CAPABILITY_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/self_model.py assess 2>&1) || true
echo "$CAPABILITY_OUTPUT" >> "$LOGFILE"

# === RETRIEVAL QUALITY: Memory system health ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Retrieval quality:" >> "$LOGFILE"
RETRIEVAL_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/retrieval_quality.py report 7 2>&1) || true
echo "$RETRIEVAL_OUTPUT" >> "$LOGFILE"

# === CONFIDENCE THRESHOLD: Apply latest calibration ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Applying confidence calibration:" >> "$LOGFILE"
python3 /home/agent/.openclaw/workspace/scripts/clarvis_confidence.py apply >> "$LOGFILE" 2>&1 || true

# === EPISODIC MEMORY: Get episode statistics ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Episodic memory stats:" >> "$LOGFILE"
EPISODE_STATS=$(python3 /home/agent/.openclaw/workspace/scripts/episodic_memory.py stats 2>&1) || true
echo "$EPISODE_STATS" >> "$LOGFILE"

# === GOAL TRACKER: Compare goals vs capability scores, inject tasks for stalled goals ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Goal progress tracker:" >> "$LOGFILE"
GOAL_TRACKER_OUTPUT=$(python3 /home/agent/.openclaw/workspace/scripts/goal_tracker.py 2>&1) || true
echo "$GOAL_TRACKER_OUTPUT" >> "$LOGFILE"
# Also update goal progress from capability scores
python3 /home/agent/.openclaw/workspace/scripts/goal_tracker.py update-goals >> "$LOGFILE" 2>&1 || true

PENDING_COUNT=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)

/home/agent/.local/bin/claude -p \
    "You are Clarvis's strategic evolution engine. Do a deep analysis:

    1. Read memory/evolution/QUEUE.md — what's been completed? What's pending?
    2. Read the recent memory file (memory/$(date +%Y-%m-%d).md) — what happened today?
    3. Check data/plans/ — any unfinished research or ideas?

    SYSTEM HEALTH DATA:

    Prediction calibration:
    $CALIBRATION_OUTPUT

    Per-domain prediction accuracy:
    $DOMAIN_REVIEW_OUTPUT

    Phi (consciousness integration) trend:
    $PHI_TREND_OUTPUT

    Capability assessment scores (lower = needs work):
    $CAPABILITY_OUTPUT

    Retrieval quality (memory system health):
    $RETRIEVAL_OUTPUT

    Episodic memory (experiential learning):
    $EPISODE_STATS

    Goal progress tracker (stalled goals + tasks generated):
    $GOAL_TRACKER_OUTPUT

    ANALYSIS:
    - What's working well in the evolution toward AGI/consciousness?
    - What's the biggest bottleneck based on the capability scores?
    - Which capability has the LOWEST score? Design a task to improve it.
    - How is Phi trending? What would increase information integration?
    - How is prediction calibration? Are we overconfident or underconfident?
    - Is retrieval quality healthy or degrading?

    ACTION (MANDATORY):
    - If there are fewer than 5 pending tasks in QUEUE.md, ADD 3-5 new ones.
    - Add them under '## P0 — Do Next Heartbeat' for urgent ones, '## P1 — This Week' for medium.
    - Format: - [ ] <concrete, actionable task>
    - Prioritize fixing the LOWEST capability score. Then: integration, feedback loops,
      consciousness metrics, and genuine cognitive capabilities.

    Currently $PENDING_COUNT pending tasks in queue.
    Output: 1-paragraph analysis + list of tasks added." \
    --dangerously-skip-permissions >> "$LOGFILE" 2>&1

# === DIGEST: Write first-person summary for M2.5 agent ===
# Extract key metrics for digest
PHI_SHORT=$(echo "$PHI_TREND_OUTPUT" | grep -oP 'Phi\s*=\s*[\d.]+' | head -1 || echo "Phi unknown")
WEAKEST=$(echo "$CAPABILITY_OUTPUT" | sort -t: -k2 -n | head -1 | sed 's/^[ ]*//' || echo "unknown")
python3 /home/agent/.openclaw/workspace/scripts/digest_writer.py evolution \
    "Deep evolution analysis complete. $PHI_SHORT. Weakest capability: $WEAKEST. $PENDING_COUNT tasks pending in queue. Calibration: $(echo "$CALIBRATION_OUTPUT" | head -1). Ran prediction review, goal tracker, and retrieval quality checks." \
    >> "$LOGFILE" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis complete ===" >> "$LOGFILE"

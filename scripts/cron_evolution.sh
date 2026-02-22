#!/bin/bash
# Deep evolution thinking with Claude Code
# KEY: Analyze progress AND write concrete new tasks to QUEUE.md
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOGFILE="memory/cron/evolution.log"

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

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis complete ===" >> "$LOGFILE"

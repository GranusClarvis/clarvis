#!/bin/bash
# Deep evolution thinking with Claude Code
# KEY: Analyze progress AND write concrete new tasks to QUEUE.md
cd /home/agent/.openclaw/workspace

LOGFILE="memory/cron_evolution.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis starting ===" >> "$LOGFILE"

# === CALIBRATION REVIEW: Check prediction accuracy ===
CONFIDENCE_SCRIPT="/home/agent/.openclaw/workspace/scripts/clarvis_confidence.py"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Calibration review:" >> "$LOGFILE"
CALIBRATION_OUTPUT=$(python3 "$CONFIDENCE_SCRIPT" calibration 2>&1)
echo "$CALIBRATION_OUTPUT" >> "$LOGFILE"

PENDING_COUNT=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)

/home/agent/.local/bin/claude -p \
    "You are Clarvis's strategic evolution engine. Do a deep analysis:

    1. Read memory/evolution/QUEUE.md — what's been completed? What's pending?
    2. Read the recent memory file (memory/$(date +%Y-%m-%d).md) — what happened today?
    3. Check scripts/ — what capabilities exist but aren't being used daily?
    4. Check data/plans/ — any unfinished research or ideas?

    5. Check prediction calibration data:
    $CALIBRATION_OUTPUT

    ANALYSIS:
    - What's working well in the evolution toward AGI/consciousness?
    - What's the biggest bottleneck right now?
    - What capability gap is most limiting?
    - How is prediction calibration? Are we overconfident or underconfident?

    ACTION (MANDATORY):
    - If there are fewer than 5 pending tasks in QUEUE.md, ADD 3-5 new ones.
    - Add them under '## P0 — Do Next Heartbeat' for urgent ones, '## P1 — This Week' for medium.
    - Format: - [ ] <concrete, actionable task>
    - Focus on: integration (wiring scripts together), persistence (surviving restarts),
      feedback loops (learning from outcomes), and genuine cognitive capabilities.

    Currently $PENDING_COUNT pending tasks in queue.
    Output: 1-paragraph analysis + list of tasks added." \
    --dangerously-skip-permissions >> "$LOGFILE" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === Evolution analysis complete ===" >> "$LOGFILE"

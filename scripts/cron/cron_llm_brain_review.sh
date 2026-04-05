#!/bin/bash
# =============================================================================
# cron_llm_brain_review.sh — Daily LLM-judged brain quality review
# =============================================================================
# Spawns Claude Code to evaluate brain retrieval quality with actual LLM
# judgement (not just keyword matching). Builds on the deterministic
# daily_brain_eval.py by adding semantic quality assessment.
#
# Schedule: 06:15 daily (after deterministic eval at 06:00, before autonomous)
# Duration: ~90s typical (probe: 15s + Claude: ~60s + process: 5s)
# Locks: local + global Claude lock (spawns Claude Code)
#
# Principle: QUALITY OVER SPEED. Do not optimize retrieval for latency at
# the expense of better recall. This is encoded in the review prompt itself.
# =============================================================================

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/llm_brain_review.log"
CLAUDE_OUTPUT="/tmp/brain_review_output.txt"

# Acquire locks
acquire_local_lock "/tmp/clarvis_llm_brain_review.lock" "$LOGFILE" 300
acquire_global_claude_lock "$LOGFILE" "queue"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === LLM brain quality review started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

# Phase 1: Prepare (pure Python, ~15s)
echo "[$TS] Phase 1: Running probes and building prompt..." >> "$LOGFILE"
timeout 60 python3 scripts/metrics/llm_brain_review.py prepare >> "$LOGFILE" 2>&1
PREP_EXIT=$?

if [ $PREP_EXIT -ne 0 ]; then
    TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
    echo "[$TS] Phase 1 FAILED (exit=$PREP_EXIT) — aborting" >> "$LOGFILE"
    exit 1
fi

# Phase 2: Claude Code review (~60s)
PROMPT_FILE="/tmp/brain_review_prompt.txt"
if [ ! -f "$PROMPT_FILE" ]; then
    echo "[$TS] ERROR: Prompt file not found at $PROMPT_FILE" >> "$LOGFILE"
    exit 1
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] Phase 2: Spawning Claude Code for LLM review..." >> "$LOGFILE"

run_claude_monitored 600 "$CLAUDE_OUTPUT" "$PROMPT_FILE" "$LOGFILE"
CLAUDE_EXIT=$?

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $CLAUDE_EXIT -ne 0 ]; then
    echo "[$TS] Phase 2 WARNING: Claude exited with $CLAUDE_EXIT (may still have output)" >> "$LOGFILE"
fi

if [ ! -f "$CLAUDE_OUTPUT" ] || [ ! -s "$CLAUDE_OUTPUT" ]; then
    echo "[$TS] Phase 2 FAILED: No Claude output" >> "$LOGFILE"
    exit 1
fi

OUTSIZE=$(wc -c < "$CLAUDE_OUTPUT")
echo "[$TS] Claude output: ${OUTSIZE} bytes" >> "$LOGFILE"

# Phase 3: Process results (pure Python, ~2s)
echo "[$TS] Phase 3: Processing Claude output..." >> "$LOGFILE"
timeout 30 python3 scripts/metrics/llm_brain_review.py process "$CLAUDE_OUTPUT" >> "$LOGFILE" 2>&1
PROC_EXIT=$?

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $PROC_EXIT -eq 0 ]; then
    echo "[$TS] LLM brain review completed successfully" >> "$LOGFILE"
else
    echo "[$TS] Phase 3 FAILED (exit=$PROC_EXIT)" >> "$LOGFILE"
fi

# Cleanup temp files
rm -f "$PROMPT_FILE" "$CLAUDE_OUTPUT"
rm -f "$CLARVIS_WORKSPACE/data/llm_brain_review/_probe_cache.json"

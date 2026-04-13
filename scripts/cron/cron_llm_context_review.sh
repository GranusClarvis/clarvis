#!/bin/bash
# =============================================================================
# cron_llm_context_review.sh — Daily LLM-judged context & prompt quality review
# =============================================================================
# Spawns Claude Code to evaluate context assembly quality: are briefs putting
# the right information in front of the executor? Is anything critical missing?
# Is there noise that shouldn't be there?
#
# Parallels cron_llm_brain_review.sh but for the context/prompt pipeline.
#
# Schedule: 06:30 daily (after brain review at 06:15, before autonomous runs)
# Duration: ~90s typical (collect: 10s + Claude: ~60s + process: 5s)
# Locks: local + global Claude lock (spawns Claude Code)
# =============================================================================

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"

LOGFILE="memory/cron/llm_context_review.log"
CLAUDE_OUTPUT="/tmp/context_review_output.txt"

# Acquire locks
acquire_local_lock "/tmp/clarvis_llm_context_review.lock" "$LOGFILE" 300
acquire_global_claude_lock "$LOGFILE" "queue"

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
echo "[$TS] === LLM context quality review started ===" >> "$LOGFILE"

cd "$CLARVIS_WORKSPACE" || exit 1

# Phase 1: Prepare (pure Python, ~10s)
echo "[$TS] Phase 1: Collecting context data and building prompt..." >> "$LOGFILE"
timeout 60 python3 scripts/metrics/llm_context_review.py prepare >> "$LOGFILE" 2>&1
PREP_EXIT=$?

if [ $PREP_EXIT -ne 0 ]; then
    TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
    echo "[$TS] Phase 1 FAILED (exit=$PREP_EXIT) — aborting" >> "$LOGFILE"
    exit 1
fi

# Phase 2: Claude Code review (~60s)
PROMPT_FILE="/tmp/context_review_prompt.txt"
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
timeout 30 python3 scripts/metrics/llm_context_review.py process "$CLAUDE_OUTPUT" >> "$LOGFILE" 2>&1
PROC_EXIT=$?

TS="$(date -u +%Y-%m-%dT%H:%M:%S)"
if [ $PROC_EXIT -eq 0 ]; then
    echo "[$TS] LLM context review completed successfully" >> "$LOGFILE"
else
    echo "[$TS] Phase 3 FAILED (exit=$PROC_EXIT)" >> "$LOGFILE"
fi

# Cleanup temp files
rm -f "$PROMPT_FILE" "$CLAUDE_OUTPUT"
rm -f "$CLARVIS_WORKSPACE/data/llm_context_review/_prepare_cache.json"

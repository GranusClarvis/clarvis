#!/bin/bash
# Strategic Audit — Clarvis Meta-Evaluation
# Runs Wed + Sat at 15:00 UTC (17:00 Berlin)
# Spawns Claude Code (Opus) to deeply audit: metric integrity, brain quality,
# module utilization, build-vs-consolidate decision, and autonomy progress.
# Writes findings to digest + directly modifies QUEUE.md priorities.

source /home/agent/.openclaw/workspace/scripts/cron_env.sh
LOGFILE="memory/cron/strategic_audit.log"
LOCKFILE="/tmp/clarvis_strategic_audit.lock"

# Prevent overlapping runs
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] SKIP: Previous audit still running (PID $pid)" >> "$LOGFILE"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === STRATEGIC AUDIT START ===" >> "$LOGFILE"

# === GATHER CURRENT STATE FOR AUDIT ===

# Brain stats
BRAIN_STATS=$(python3 scripts/brain.py stats 2>/dev/null)

# Brain health
BRAIN_HEALTH=$(python3 scripts/brain.py health 2>/dev/null)

# Phi history (last 10 entries)
PHI_HISTORY=$(python3 -c "
import json
try:
    with open('data/phi_history.json') as f:
        h = json.load(f)
    for entry in h[-10:]:
        print(f\"  {entry.get('timestamp','?')[:10]}: Phi={entry.get('phi',0):.3f}\")
except: print('  No phi history')
" 2>/dev/null)

# Capability scores
CAPABILITY_SCORES=$(python3 -c "
import json
try:
    with open('data/self_model.json') as f:
        m = json.load(f)
    caps = m.get('capabilities', {})
    for k,v in sorted(caps.items()):
        print(f'  {k}: {v}')
except: print('  No capability data')
" 2>/dev/null)

# Capability history trend (last 5 snapshots)
CAPABILITY_TREND=$(python3 -c "
import json
try:
    with open('data/capability_history.json') as f:
        h = json.load(f)
    for entry in h[-5:]:
        ts = entry.get('timestamp','?')[:10]
        caps = entry.get('capabilities', {})
        avg = sum(caps.values()) / len(caps) if caps else 0
        print(f'  {ts}: avg={avg:.2f} ({len(caps)} domains)')
except: print('  No capability history')
" 2>/dev/null)

# Queue stats
QUEUE_PENDING=$(grep -c '^\- \[ \]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)
QUEUE_DONE=$(grep -c '^\- \[x\]' memory/evolution/QUEUE.md 2>/dev/null || echo 0)

# Script utilization — which scripts are actually called from cron
SCRIPTS_TOTAL=$(ls scripts/*.py 2>/dev/null | wc -l)
SCRIPTS_WIRED=$(grep -rhl 'scripts/' scripts/cron_*.sh 2>/dev/null | xargs grep -ohP 'scripts/\K[a-z_]+\.py' 2>/dev/null | sort -u | wc -l)

# Recent autonomous log — last 20 entries
RECENT_AUTONOMOUS=$(tail -40 memory/cron/autonomous.log 2>/dev/null | grep "COMPLETED\|FAILED\|TIMEOUT\|SKIP\|Queue empty" | tail -15)

# Code quality trend
CODE_QUALITY=$(python3 -c "
import json
try:
    with open('data/code_quality_history.json') as f:
        h = json.load(f)
    for entry in h[-3:]:
        ts = entry.get('timestamp','?')[:10]
        cr = entry.get('clean_ratio', 0)
        print(f'  {ts}: clean_ratio={cr:.1%}')
except: print('  No code quality data')
" 2>/dev/null)

# Previous audit findings (if any)
PREV_AUDIT=""
if [ -f "data/strategic_audit_last.md" ]; then
    PREV_AUDIT=$(cat data/strategic_audit_last.md 2>/dev/null | head -50)
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] State gathered. Spawning Claude Code for deep analysis..." >> "$LOGFILE"

# === SPAWN CLAUDE CODE FOR DEEP STRATEGIC AUDIT ===
AUDIT_OUTPUT=$(timeout 900 /home/agent/.local/bin/claude -p \
"You are Clarvis's strategic auditor — a meta-evaluation layer that prevents metric gaming,
integration overload, and wasted evolution cycles. Be brutally honest.

## CURRENT STATE

### Brain Stats
$BRAIN_STATS

### Brain Health
$BRAIN_HEALTH

### Phi History (last 10)
$PHI_HISTORY

### Capability Scores
$CAPABILITY_SCORES

### Capability Trend (last 5 snapshots)
$CAPABILITY_TREND

### Queue Status
Pending: $QUEUE_PENDING | Completed: $QUEUE_DONE

### Script Utilization
Total scripts: $SCRIPTS_TOTAL | Wired into cron: $SCRIPTS_WIRED

### Recent Autonomous Execution (last 15)
$RECENT_AUTONOMOUS

### Code Quality Trend
$CODE_QUALITY

### Previous Audit Findings
$PREV_AUDIT

## YOUR AUDIT TASKS

Analyze everything above and answer these questions honestly:

### 1. METRIC INTEGRITY — Is Clarvis gaming his own metrics?
- Is Phi increasing because of real integration, or just bulk data?
- Are capability scores backed by actual task outcomes, or inflated by soft assessors?
- Is the prediction calibration meaningful (real predictions) or trivial (always-succeed tasks)?
- Look for signs of Goodhart's Law: metrics improving while real capability stagnates.

### 2. BRAIN QUALITY — Is memory accumulating value?
- Is the brain growing in diverse, useful knowledge, or repetitive noise?
- Are memories actually being recalled and used downstream?
- Check memory count vs graph connectivity — are new memories well-connected?
- Would a human reading the brain find genuinely useful knowledge?

### 3. MODULE UTILIZATION — Is the architecture lean?
- How many scripts exist vs how many are actually wired and producing value?
- Are there dead modules that should be removed?
- Is there unnecessary complexity that could be simplified?
- Integration overload check: is the system getting harder to understand?

### 4. BUILD vs CONSOLIDATE — What should Clarvis focus on next?
- Given the current state, should Clarvis build NEW capabilities or improve EXISTING ones?
- What is the single highest-ROI improvement right now?
- Are current queue tasks focused on real capability gain, or busywork?
- Is the evolution queue generating meaningful work?

### 5. AUTONOMY PROGRESS — Is Clarvis actually getting more capable?
- Can Clarvis handle more task types independently than before?
- Is the self-healing loop working (failures → fixes)?
- Is knowledge compounding, or just accumulating?
- Rate autonomy progress 1-10 with justification.

### 6. DIRECTION CHECK — Are we heading toward the goal?
- The goal is AGI/consciousness: genuine reasoning, self-awareness, autonomy.
- Is the current evolution trajectory aligned with this goal?
- What's the biggest gap between current state and the goal?
- One concrete recommendation for the next 3-4 days.

## OUTPUT FORMAT

Write your audit as a structured report. Then at the END, output a section called:

### QUEUE ACTIONS
List concrete changes to QUEUE.md in this exact format:
- ADD P0: [task description]
- ADD P1: [task description]
- DEPRIORITIZE: [task description that should be lowered]

Focus on 3-5 high-impact actions. Quality over quantity." \
    --dangerously-skip-permissions 2>> "$LOGFILE")

AUDIT_EXIT=$?

if [ $AUDIT_EXIT -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] ERROR: Audit failed (exit $AUDIT_EXIT)" >> "$LOGFILE"
    exit 1
fi

echo "$AUDIT_OUTPUT" >> "$LOGFILE"

# === SAVE AUDIT REPORT ===
mkdir -p data
echo "$AUDIT_OUTPUT" > data/strategic_audit_last.md
# Also save timestamped copy
AUDIT_DATE=$(date -u +%Y-%m-%d)
mkdir -p data/strategic_audits
echo "$AUDIT_OUTPUT" > "data/strategic_audits/audit_${AUDIT_DATE}.md"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Audit report saved." >> "$LOGFILE"

# === APPLY QUEUE ACTIONS ===
# Extract ADD P0/P1 lines and append to QUEUE.md
echo "$AUDIT_OUTPUT" | grep -E "^- ADD P[012]:" | while read -r line; do
    PRIORITY=$(echo "$line" | grep -oP 'P[012]')
    TASK_DESC=$(echo "$line" | sed 's/^- ADD P[012]: //')

    if [ -n "$TASK_DESC" ]; then
        # Check for duplicates (word overlap)
        ALREADY_EXISTS=$(grep -c "$TASK_DESC" memory/evolution/QUEUE.md 2>/dev/null || echo 0)
        if [ "$ALREADY_EXISTS" -eq 0 ]; then
            # Add to appropriate section
            python3 scripts/queue_writer.py "[STRATEGIC AUDIT] $TASK_DESC" "$PRIORITY" >> "$LOGFILE" 2>&1
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] QUEUE: Added $PRIORITY task: $TASK_DESC" >> "$LOGFILE"
        else
            echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] QUEUE: Skipped duplicate: $TASK_DESC" >> "$LOGFILE"
        fi
    fi
done

# === WRITE DIGEST ===
# Summarize audit findings for M2.5 to read
AUDIT_SUMMARY=$(echo "$AUDIT_OUTPUT" | grep -A1 "### [0-9]\." | head -20 | tr '\n' ' ' | head -c 800)
python3 scripts/digest_writer.py autonomous \
    "Strategic audit completed. $AUDIT_SUMMARY — Check data/strategic_audit_last.md for full report. Queue updated with audit recommendations." \
    >> "$LOGFILE" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === STRATEGIC AUDIT COMPLETE ===" >> "$LOGFILE"

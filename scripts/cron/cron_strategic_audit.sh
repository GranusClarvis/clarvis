#!/bin/bash
# Strategic Audit — Clarvis Meta-Evaluation
# Runs Wed + Sat at 15:00 UTC (17:00 Berlin)
# Spawns Claude Code (Opus) to deeply audit: metric integrity, brain quality,
# module utilization, build-vs-consolidate decision, and autonomy progress.
# Writes findings to digest + directly modifies QUEUE.md priorities.

source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/cron_env.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}/scripts/cron")/lock_helper.sh"
LOGFILE="memory/cron/strategic_audit.log"

# Acquire locks: local + global Claude
acquire_local_lock "/tmp/clarvis_strategic_audit.lock" "$LOGFILE" 3600
acquire_global_claude_lock "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === STRATEGIC AUDIT START ===" >> "$LOGFILE"

# === STEP 0: AST SURGERY — auto-fix dead imports before audit ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running AST surgery scan with auto-fix..." >> "$LOGFILE"
AST_SURGERY_OUTPUT=$(timeout 120 python3 scripts/tools/ast_surgery.py scan --auto-fix 2>&1) || true
echo "$AST_SURGERY_OUTPUT" >> "$LOGFILE"
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] AST surgery complete." >> "$LOGFILE"

# === GATHER CURRENT STATE FOR AUDIT ===

# Brain stats
BRAIN_STATS=$(python3 scripts/brain_mem/brain.py stats 2>/dev/null)

# Brain health
BRAIN_HEALTH=$(python3 scripts/brain_mem/brain.py health 2>/dev/null)

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
SCRIPTS_TOTAL=$(find scripts/ -name '*.py' 2>/dev/null | wc -l)
SCRIPTS_WIRED=$(grep -rhl 'scripts/' scripts/cron/*.sh 2>/dev/null | xargs grep -ohP 'scripts/[a-z_]+/[a-z_]+\.py' 2>/dev/null | sort -u | wc -l)

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

# AST surgery latest results
AST_SURGERY_SUMMARY=$(python3 -c "
import json
try:
    with open('data/ast_surgery/latest.json') as f:
        r = json.load(f)
    print(f'  Files: {r[\"files_scanned\"]}, Avg quality: {r[\"avg_quality\"]:.3f}')
    print(f'  Proposals: {r[\"total_proposals\"]}')
    for t, c in r.get('proposals_by_type', {}).items():
        print(f'    {t}: {c}')
    if r.get('auto_fixes'):
        print(f'  Auto-fixed: {len(r[\"auto_fixes\"])} dead imports')
except: print('  No AST surgery data')
" 2>/dev/null)

# Previous audit findings (if any)
PREV_AUDIT=""
if [ -f "data/strategic_audit_last.md" ]; then
    PREV_AUDIT=$(cat data/strategic_audit_last.md 2>/dev/null | head -50)
fi

# === STEP 1: CLR Perturbation / Ablation Sweep ===
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] Running CLR perturbation ablation sweep..." >> "$LOGFILE"
CLR_PERTURBATION_OUTPUT=$(timeout 300 python3 $CLARVIS_WORKSPACE/clarvis/metrics/clr_perturbation.py 2>&1) || true
echo "$CLR_PERTURBATION_OUTPUT" >> "$LOGFILE"
# Extract summary for audit prompt
CLR_PERTURBATION_SUMMARY=$(echo "$CLR_PERTURBATION_OUTPUT" | grep -E "^\[perturbation\]|Baseline|CRITICAL|HELPFUL|HARMFUL|NEUTRAL" | tail -15)
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] CLR perturbation complete." >> "$LOGFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] State gathered. Spawning Claude Code for deep analysis..." >> "$LOGFILE"

# === SPAWN CLAUDE CODE FOR DEEP STRATEGIC AUDIT ===
AUDIT_START=$SECONDS

# === V2 RUN RECORD: START ===
V2_RUN_ID=$(python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('CLARVIS_WORKSPACE', os.getcwd()), 'clarvis', 'queue'))
try:
    from engine import QueueEngine
    qe = QueueEngine()
    rid = qe.start_external_run('[STRATEGIC_AUDIT] Deep strategic audit session', source='cron_strategic_audit')
    if rid:
        print(rid)
except Exception as e:
    print('', end='')
    import traceback; traceback.print_exc(file=sys.stderr)
" 2>> "$LOGFILE")
[ -n "$V2_RUN_ID" ] && echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] V2 run started: $V2_RUN_ID" >> "$LOGFILE"

AUDIT_OUTPUT=$(timeout 1200 env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  ${CLAUDE_BIN:-$(command -v claude || echo "$HOME/.local/bin/claude")} --model claude-opus-4-6 -p \
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

### AST Surgery (auto-fix dead imports, code quality scan)
$AST_SURGERY_SUMMARY

### CLR Perturbation / Ablation Results
$CLR_PERTURBATION_SUMMARY

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

Write your audit as a structured report. Then at the END, output TWO things:

### QUEUE ACTIONS
List concrete changes to QUEUE.md in this exact format:
- ADD P0: [task description]
- ADD P1: [task description]
- DEPRIORITIZE: [task description that should be lowered]

Focus on 3-5 high-impact actions. Quality over quantity.

### STRUCTURED FINDINGS
Output a JSON block (fenced with \`\`\`json) with this exact schema:
\`\`\`json
{
  \"findings\": [
    {\"priority\": \"P0\", \"category\": \"metric_integrity|brain_quality|module_utilization|build_consolidate|autonomy|direction\", \"title\": \"short title\", \"description\": \"what and why\", \"action\": \"concrete task to add to queue\"},
  ],
  \"autonomy_score\": 7,
  \"biggest_gap\": \"one sentence\"
}
\`\`\`
Include ALL P0/P1 findings in this JSON. This is machine-parsed for reliable queue injection." \
    --dangerously-skip-permissions 2>> "$LOGFILE")

AUDIT_EXIT=$?
AUDIT_DURATION=$((SECONDS - AUDIT_START))

# === V2 RUN RECORD: END ===
if [ -n "$V2_RUN_ID" ]; then
    python3 -c "
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('CLARVIS_WORKSPACE', os.getcwd()), 'clarvis', 'queue'))
try:
    from engine import QueueEngine
    qe = QueueEngine()
    outcome = 'success' if $AUDIT_EXIT == 0 else 'failure'
    qe.end_run('$V2_RUN_ID', outcome, exit_code=$AUDIT_EXIT, duration_s=$AUDIT_DURATION)
except Exception as e:
    import traceback; traceback.print_exc(file=sys.stderr)
" 2>> "$LOGFILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] V2 run ended: $V2_RUN_ID outcome=$([ $AUDIT_EXIT -eq 0 ] && echo success || echo failure) duration=${AUDIT_DURATION}s" >> "$LOGFILE"
fi

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

# === APPLY QUEUE ACTIONS (robust Python parser) ===
# Tries JSON structured findings first, falls back to grep-based extraction
python3 - << 'PYEOF' >> "$LOGFILE" 2>&1
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.getcwd()), "scripts/evolution"))
from queue_writer import add_task

# Read audit text from saved file instead of argv (avoids ARG_MAX with large audits)
audit_file = os.path.join(
    os.environ.get("CLARVIS_WORKSPACE", os.getcwd()),
    "data", "strategic_audit_last.md"
)
try:
    with open(audit_file, "r") as f:
        audit_text = f.read()
except (IOError, OSError):
    audit_text = ""
added = []

# Strategy 1: Parse JSON structured findings block
json_match = re.search(r'```json\s*(\{.*?\})\s*```', audit_text, re.DOTALL)
if json_match:
    try:
        data = json.loads(json_match.group(1))
        findings = data.get("findings", [])
        for f in findings:
            priority = f.get("priority", "P1")
            if priority not in ("P0", "P1"):
                priority = "P1"
            action = f.get("action", "").strip()
            title = f.get("title", "").strip()
            category = f.get("category", "").strip()
            if not action:
                continue
            task_desc = f"[STRATEGIC_AUDIT/{category}] {action}"
            if add_task(task_desc, priority=priority, source="strategic_audit"):
                added.append(f"{priority}: {title}")
                print(f"QUEUE: Added {priority} task from JSON: {title}")
            else:
                print(f"QUEUE: Skipped (duplicate/cap): {title}")
        # Save structured data for downstream use
        findings_path = os.path.join(
            os.environ.get("CLARVIS_WORKSPACE", os.getcwd()),
            "data", "strategic_audit_findings.json"
        )
        data["extracted_at"] = __import__("datetime").datetime.now().isoformat()
        with open(findings_path, "w") as fp:
            json.dump(data, fp, indent=2)
        print(f"Saved structured findings to {findings_path}")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"JSON parse failed ({e}), falling back to grep")
        json_match = None

# Strategy 2: Fallback — grep for "- ADD P0/P1:" lines
if not json_match or not added:
    for line in audit_text.split("\n"):
        m = re.match(r'^- ADD (P[012]): (.+)', line.strip())
        if not m:
            continue
        priority, task_desc = m.group(1), m.group(2).strip()
        if not task_desc:
            continue
        full_desc = f"[STRATEGIC_AUDIT] {task_desc}"
        if add_task(full_desc, priority=priority, source="strategic_audit"):
            added.append(f"{priority}: {task_desc[:60]}")
            print(f"QUEUE: Added {priority} task from grep: {task_desc[:60]}")
        else:
            print(f"QUEUE: Skipped (duplicate/cap): {task_desc[:60]}")

print(f"Total queue actions applied: {len(added)}")
PYEOF

# === WRITE DIGEST ===
# Summarize audit findings for M2.5 to read
AUDIT_SUMMARY=$(echo "$AUDIT_OUTPUT" | grep -A1 "### [0-9]\." | head -20 | tr '\n' ' ' | head -c 800)
python3 scripts/tools/digest_writer.py autonomous \
    "Strategic audit completed. $AUDIT_SUMMARY — Check data/strategic_audit_last.md for full report. Queue updated with audit recommendations." \
    >> "$LOGFILE" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] === STRATEGIC AUDIT COMPLETE ===" >> "$LOGFILE"

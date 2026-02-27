#!/bin/bash
# Morning Report - 10:05 CET
# Comprehensive report: what happened overnight, metrics, priorities
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOCKFILE="/tmp/clarvis_report_morning.lock"
if [ -f "$LOCKFILE" ]; then
    pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then exit 0; fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

python3 << 'PYEOF'
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import os
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

# Get bot token
with open('/home/agent/.openclaw/openclaw.json') as f:
    config = json.load(f)
TOKEN = config['channels']['telegram']['botToken']

# ==== PARSE DIGEST ====
digest_path = "/home/agent/.openclaw/workspace/memory/cron/digest.md"
digest_content = ""
if os.path.exists(digest_path):
    with open(digest_path) as f:
        digest_content = f.read()

# Parse digest entries with better extraction
entries = []
pattern = r'### (.+?) — (\d{2}:\d{2}) UTC'
for match in re.finditer(pattern, digest_content):
    entry_type = match.group(1).strip()
    timestamp = match.group(2)
    start = match.start()
    end = digest_content.find('###', start + 10)
    if end == -1:
        end = len(digest_content)
    context = digest_content[start:end].strip()
    entries.append({'type': entry_type, 'time': timestamp, 'context': context})

# Filter to overnight entries (22:00 previous day to 10:00 today)
overnight_entries = []
for e in entries:
    hour = int(e['time'].split(':')[0])
    if hour >= 22 or hour <= 9:
        overnight_entries.append(e)

# ==== BETTER TASK EXTRACTION FROM DIGEST ====
def extract_task_details(context, entry_type):
    """Extract meaningful task description from digest context"""
    # For Autonomous tasks
    if 'Autonomous' in entry_type:
        # Look for evolution task in brackets - simpler regex
        task_match = re.search(r'\[([A-Z_]+)\]', context)
        if task_match:
            return f"{task_match.group(1)}"
        
        return "Evolution task"
    
    # For Research
    if 'Research' in entry_type:
        bundle_match = re.search(r'Researched:\s*(Bundle \w+|.+?)(?:\.|—|Result)', context)
        if bundle_match:
            return bundle_match.group(1).strip()[:45]
        return "Research task"
    
    if 'Morning' in entry_type or 'Evening' in entry_type:
        return "Planning cycle"
    
    return entry_type[:30]

# ==== PARSE QUEUE BETTER ====
queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
with open(queue_path) as f:
    queue_content = f.read()

# Get P0 pending items
p0_pending = []
for match in re.finditer(r'- \[ \] \[([^\]]+)\]', queue_content):
    task = match.group(1)
    if len(p0_pending) < 3:
        p0_pending.append(task)

# Get P1 pending items  
p1_pending = []
for match in re.finditer(r'- \[ \] \[([^\]]+)\].*?—\s*(.+?)(?:\(|—|$)', queue_content):
    task_id = match.group(1)
    task_desc = match.group(2).strip()[:40]
    if len(p1_pending) < 2:
        p1_pending.append(f"{task_id}")

# Get TODAY's completed items
today_completed = []
for match in re.finditer(r'- \[x\] \[([^\]]+)\].*?(\d{4}-\d{2}-\d{2})', queue_content):
    date = match.group(2)
    if '2026-02-26' in date:
        task = match.group(1)[:35]
        today_completed.append(task)

# ==== RESEARCH PROGRESS ====
research_completed = []
for i in range(1, 11):
    if f'[x] P{i}:' in queue_content:
        m = re.search(rf'\[x\] P{i}:\s*(.+?)\s*—', queue_content)
        if m:
            research_completed.append(f"P{i}: {m.group(1)[:25]}")

research_pending = []
for i in range(1, 11):
    if f'[ ] P{i}:' in queue_content:
        m = re.search(rf'\[ \] P{i}:\s*(.+?)\s*—', queue_content)
        if m:
            research_pending.append(f"P{i}: {m.group(1)[:25]}")
        break
if not research_pending:
    research_pending = ["All done!"]

# ==== BRAIN STATS ====
from brain import brain
stats = brain.stats()

# ==== BUILD REPORT ====
lines = []

lines.append("🌅 Clarvis Morning Report")
lines.append("=" * 40)
lines.append("")

# Overnight activity - ACTUAL TASKS
lines.append("🌙 OVERNIGHT WORK")
lines.append("-" * 20)
if overnight_entries:
    for e in overnight_entries:
        result_match = re.search(r'Result: (\w+)', e['context'])
        result = result_match.group(1) if result_match else "?"
        
        task_desc = extract_task_details(e['context'], e['type'])
        
        lines.append(f"  {e['time']} → {task_desc} [{result}]")
else:
    lines.append("  (No overnight activity)")
lines.append("")

# Queue - WHAT'S PENDING
lines.append("📋 QUEUE: WHAT'S NEXT")
lines.append("-" * 20)
if p0_pending:
    lines.append("  P0 (do now):")
    for t in p0_pending:
        lines.append(f"    • {t}")
elif p1_pending:
    lines.append("  P1 (this week):")
    for t in p1_pending:
        lines.append(f"    • {t}")
else:
    lines.append("  Queue empty!")

if today_completed:
    lines.append(f"  Today: {', '.join(today_completed[:3])}")
lines.append("")

# Research - WHICH BUNDLES
lines.append("🔬 RESEARCH BUNDLES")
lines.append("-" * 20)
lines.append(f"  Done: {len(research_completed)}/10")
for r in research_completed[-3:]:
    lines.append(f"    ✓ {r}")
lines.append(f"  Next: {research_pending[0]}")
lines.append("")

# Brain state
lines.append("🧠 BRAIN STATE")
lines.append("-" * 20)
lines.append(f"  Memories: {stats['total_memories']}")
top_cols = sorted(stats['collections'].items(), key=lambda x: x[1], reverse=True)[:4]
cols_str = ", ".join([f"{k.split('-')[-1]}({v})" for k, v in top_cols])
lines.append(f"  Top: {cols_str}")

# Goals with context
lines.append("")
lines.append("🎯 GOALS")
lines.append("-" * 20)
try:
    goals = brain.get_goals()
    for g in goals[:3]:
        doc = g.get('document', '')
        prog_match = re.search(r'progress: (\d+)%', doc)
        goal_match = re.search(r'Goal:\s*([^—]+)', doc)
        if prog_match and goal_match:
            prog = prog_match.group(1)
            name = goal_match.group(1).strip()[:30]
            lines.append(f"  {name}: {prog}%")
except:
    lines.append("  (Unavailable)")

lines.append("")
lines.append("=" * 40)
lines.append("Ready for the day, sir.")

report = "\n".join(lines)

# Send to Telegram — Reports topic in group + DM fallback
GROUP_CHAT_ID = "REDACTED_GROUP_ID"
REPORTS_TOPIC = "5"
DM_CHAT_ID = "REDACTED_CHAT_ID"

# Primary: send to Reports topic in group
params = {"chat_id": GROUP_CHAT_ID, "text": report, "message_thread_id": REPORTS_TOPIC}
data = urllib.parse.urlencode(params)
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
try:
    urllib.request.urlopen(req, timeout=10)
    print("[report_morning] Sent to Reports topic")
except Exception as e:
    # Fallback: send to DM if group delivery fails
    print(f"[report_morning] Group delivery failed ({e}), falling back to DM")
    data = urllib.parse.urlencode({"chat_id": DM_CHAT_ID, "text": report})
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
    urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
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

# Extract entries from last ~16 hours (overnight period)
# Digest format: ### ⚡ Autonomous — HH:MM UTC or ### Research — HH:MM UTC
entries = []
current_date = datetime.now().strftime("%Y-%m-%d")

# Parse digest entries with timestamps
pattern = r'### (.+?) — (\d{2}:\d{2}) UTC'
for match in re.finditer(pattern, digest_content):
    entry_type = match.group(1).strip()
    timestamp = match.group(2)
    # Get context around this entry
    start = match.start()
    end = digest_content.find('###', start + 10)
    if end == -1:
        end = len(digest_content)
    context = digest_content[start:end].strip()
    entries.append({'type': entry_type, 'time': timestamp, 'context': context})

# Filter to overnight entries (22:00 previous day to 10:00 today)
# This is roughly the entries that happened while user was asleep
overnight_entries = []
for e in entries:
    hour = int(e['time'].split(':')[0])
    # Night hours: 22, 23, 00, 01, 02, 03, 04, 05, 06, 07, 08, 09
    if hour >= 22 or hour <= 9:
        overnight_entries.append(e)

# ==== PARSE QUEUE ====
queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
with open(queue_path) as f:
    queue_content = f.read()

# Count completed vs pending
p0_completed = queue_content.count('[x] [BRAIN') + queue_content.count('[x] [SPAWN') + queue_content.count('[x] [SEMANTIC')
p0_pending = queue_content.count('- [ ] [BRAIN') + queue_content.count('- [ ] [SPAWN') + queue_content.count('- [ ] [SEMANTIC')

p1_items = []
p1_match = re.search(r'## P1 — This Week\s*\n(.*?)(?=##|$)', queue_content, re.DOTALL)
if p1_match:
    for line in p1_match.group(1).strip().split('\n'):
        if '- [ ]' in line and '—' in line:
            task = line.split('—')[1].split('(')[0].strip() if '—' in line else line
            task = re.sub(r'\s*\(.*', '', task).strip()
            if task and len(task) < 50:
                p1_items.append(task)
        elif '- [ ]' in line and '—' not in line:
            task = re.sub(r'^- \[ \]\s*', '', line).strip()
            task = re.sub(r'\s*\(.*', '', task).strip()
            if task and len(task) < 50:
                p1_items.append(task)

# Research progress
research_section = re.search(r'=== COMPLETED ===.*?=== PRIORITY TRACKING ===', queue_content, re.DOTALL)
completed_research = []
if research_section:
    completed_research = re.findall(r'\[x\] (P\d+): (.+?) —', research_section.group(0))

research_pending = re.search(r'=== PRIORITY TRACKING ===\s*\n(.*?)(?====|$)', queue_content, re.DOTALL)
next_research = "None"
if research_pending:
    for line in research_pending.group(1).split('\n'):
        if '[ ] P' in line and '—' in line:
            next_research = line.split('—')[1].strip() if '—' in line else line.strip()
            break

# ==== BRAIN STATS ====
from brain import brain
stats = brain.stats()

# Get Phi if available (skip if slow/hanging)
phi_score = "N/A"

# ==== BUILD REPORT ====
lines = []

lines.append("🌅 Clarvis Morning Report")
lines.append("=" * 40)
lines.append("")

# Overnight activity
lines.append("🌙 OVERNIGHT ACTIVITY")
lines.append("-" * 20)
if overnight_entries:
    for e in overnight_entries:
        # Extract result from context
        result_match = re.search(r'Result: (\w+)', e['context'])
        result = result_match.group(1) if result_match else "?"
        
        # Extract task description
        task_match = re.search(r'executed evolution task: \[([^\]]+)\]|Researched: (.+?)(?:\.|Result)', e['context'])
        if task_match:
            if task_match.group(1):
                task_desc = task_match.group(1)
            else:
                task_desc = task_match.group(2)
        else:
            task_desc = e['type']
        
        lines.append(f"  • {e['time']} — {task_desc[:45]} [{result}]")
else:
    lines.append("  (No overnight activity logged)")
lines.append("")

# Brain state
lines.append("🧠 BRAIN STATE")
lines.append("-" * 20)
lines.append(f"  Memories: {stats['total_memories']}")
lines.append(f"  Collections: {len(stats['collections'])}")
lines.append(f"  Phi Score: {phi_score}")

# Top collections
top_cols = sorted(stats['collections'].items(), key=lambda x: x[1], reverse=True)[:5]
cols_str = ", ".join([f"{k.split('-')[-1]}({v})" for k, v in top_cols])
lines.append(f"  Top: {cols_str}")
lines.append("")

# Queue progress
lines.append("📋 EVOLUTION QUEUE")
lines.append("-" * 20)
lines.append(f"  P0 completed: {p0_completed} | pending: {p0_pending}")
if p1_items:
    lines.append(f"  P1: {p1_items[0][:40]}")
    if len(p1_items) > 1:
        lines.append(f"      {p1_items[1][:40]}")
lines.append("")

# Research progress
lines.append("🔬 RESEARCH PROGRESS")
lines.append("-" * 20)
lines.append(f"  Completed: {len(completed_research)}/10 priority")
if completed_research:
    recent = [r[1][:25] for r in completed_research[-3:]]
    lines.append(f"  Recent: {', '.join(recent)}")
lines.append(f"  Next: {next_research[:40]}")
lines.append("")

# Goals
lines.append("🎯 GOALS")
lines.append("-" * 20)
try:
    goals = brain.get_goals()
    for g in goals[:3]:
        doc = g.get('document', '')
        # Extract progress
        prog_match = re.search(r'progress: (\d+)%', doc)
        if prog_match:
            prog = prog_match.group(1)
            name = g.get('id', 'Unknown')[:25]
            lines.append(f"  {name}: {prog}%")
except:
    lines.append("  (Goals unavailable)")
lines.append("")

# Footer
lines.append("=" * 40)
lines.append("Ready for the day, sir.")

report = "\n".join(lines)

# Send to Telegram
data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": report})
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
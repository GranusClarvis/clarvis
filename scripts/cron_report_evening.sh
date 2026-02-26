#!/bin/bash
# Evening Report - 22:05 CET
# Comprehensive report: what happened today, metrics, accomplishments
source /home/agent/.openclaw/workspace/scripts/cron_env.sh

LOCKFILE="/tmp/clarvis_report_evening.lock"
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
from datetime import datetime
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

# Parse all entries for today
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

# Filter to daytime entries (10:00 to 22:00)
daytime_entries = []
for e in entries:
    hour = int(e['time'].split(':')[0])
    if 10 <= hour <= 21:
        daytime_entries.append(e)

# ==== GIT ACTIVITY ====
git_log = ""
try:
    import subprocess
    result = subprocess.run(
        ['git', 'log', '--oneline', '-10'],
        cwd='/home/agent/.openclaw/workspace',
        capture_output=True, text=True, timeout=5
    )
    git_log = result.stdout.strip()
except:
    pass

# Parse today's commits
today_commits = []
if git_log:
    for line in git_log.split('\n'):
        if '2026-02-26' in line or 'Feb 26' in line:
            today_commits.append(line)

# ==== QUEUE PROGRESS ====
queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
with open(queue_path) as f:
    queue_content = f.read()

# Count completions today (look for today's date in completed items)
today_completed = queue_content.count('2026-02-26')

# P0/P1 items
p0_match = re.search(r'## P0 — Do Next Heartbeat\s*\n(.*?)(?=##|$)', queue_content, re.DOTALL)
p0_items = []
if p0_match:
    for line in p0_match.group(1).strip().split('\n'):
        if '- [ ]' in line:
            task = re.sub(r'^- \[ \]\s*', '', line.split('—')[0] if '—' in line else line)
            task = re.sub(r'\s*\(.*', '', task).strip()
            if task:
                p0_items.append(task)

p1_match = re.search(r'## P1 — This Week\s*\n(.*?)(?=##|$)', queue_content, re.DOTALL)
p1_items = []
if p1_match:
    for line in p1_match.group(1).strip().split('\n'):
        if '- [ ]' in line:
            if '—' in line:
                task = line.split('—')[1].split('(')[0].strip()
            else:
                task = re.sub(r'^- \[ \]\s*', '', line).strip()
            task = re.sub(r'\s*\(.*', '', task).strip()
            if task and len(task) < 50:
                p1_items.append(task)

# Research completed today
research_section = re.search(r'=== COMPLETED ===.*?=== PRIORITY TRACKING ===', queue_content, re.DOTALL)
completed_today = []
if research_section:
    for match in re.finditer(r'\[x\] (P\d+): (.+?) — (\d{4}-\d{2}-\d{2})', research_section.group(0)):
        if '2026-02-26' in match.group(3):
            completed_today.append((match.group(1), match.group(2)))

# ==== BRAIN STATS ====
from brain import brain
stats = brain.stats()

# Get Phi if available (skip if slow/hanging)
phi_score = "N/A"

# Get goals
goals = brain.get_goals()

# ==== BUILD REPORT ====
lines = []

lines.append("🌙 Clarvis Evening Report")
lines.append("=" * 40)
lines.append("")

# Daytime activity summary
lines.append("📅 TODAY'S ACTIVITY")
lines.append("-" * 20)
if daytime_entries:
    # Group by type
    autonomous = [e for e in daytime_entries if 'Autonomous' in e['type']]
    research = [e for e in daytime_entries if 'Research' in e['type']]
    morning = [e for e in daytime_entries if 'Morning' in e['type']]
    
    lines.append(f"  Autonomous cycles: {len(autonomous)}")
    lines.append(f"  Research sessions: {len(research)}")
    
    # Show key results
    for e in daytime_entries[:5]:
        # Extract task/result
        task_match = re.search(r'executed evolution task: \[([^\]]+)\]|Researched: (.+?)(?:\.|Result)', e['context'])
        if task_match:
            task = task_match.group(1) or task_match.group(2)
            task = task[:40]
        else:
            task = e['type'][:40]
        
        result_match = re.search(r'Result: (\w+)', e['context'])
        result = f"[{result_match.group(1)}]" if result_match else ""
        
        lines.append(f"  • {e['time']} {task} {result}")
else:
    lines.append("  (No activity logged)")
lines.append("")

# Queue progress
lines.append("📋 QUEUE PROGRESS")
lines.append("-" * 20)
lines.append(f"  Items completed today: {today_completed}")
lines.append(f"  P0 pending: {len(p0_items)}")
if p0_items:
    lines.append(f"    → {p0_items[0][:45]}")
if p1_items:
    lines.append(f"  P1: {p1_items[0][:40]}")
    if len(p1_items) > 1:
        lines.append(f"      {p1_items[1][:40]}")
lines.append("")

# Research
lines.append("🔬 RESEARCH")
lines.append("-" * 20)
lines.append(f"  Completed today: {len(completed_today)}")
for p, topic in completed_today:
    lines.append(f"    ✓ {p}: {topic[:30]}")
lines.append("")

# Git commits
lines.append("📝 GIT COMMITS TODAY")
lines.append("-" * 20)
if today_commits:
    for commit in today_commits[:4]:
        # Simplify: remove hash, keep message
        msg = re.sub(r'^[a-f0-9]+\s*', '', commit)
        lines.append(f"  • {msg[:45]}")
else:
    lines.append("  (None)")
lines.append("")

# Brain state
lines.append("🧠 BRAIN STATE")
lines.append("-" * 20)
lines.append(f"  Total memories: {stats['total_memories']}")
lines.append(f"  Phi Score: {phi_score}")

# Show goal progress
lines.append("  Goals:")
for g in goals[:3]:
    doc = g.get('document', '')
    prog_match = re.search(r'progress: (\d+)%', doc)
    if prog_match:
        prog = prog_match.group(1)
        name = g.get('id', 'Unknown')[:20]
        lines.append(f"    {name}: {prog}%")

lines.append("")
lines.append("=" * 40)
lines.append("Ready for nighttime evolution, sir.")

report = "\n".join(lines)

# Send to Telegram
data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": report})
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
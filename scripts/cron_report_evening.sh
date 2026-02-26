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
import subprocess
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

# ==== TASK EXTRACTION ====
def extract_task_details(context, entry_type):
    if 'Autonomous' in entry_type:
        task_match = re.search(r'\[([A-Z_]+)\]', context)
        if task_match:
            return f"{task_match.group(1)}"
        return "Evolution task"
    
    if 'Research' in entry_type:
        bundle_match = re.search(r'Researched:\s*(Bundle \w+|.+?)(?:\.|—|Result)', context)
        if bundle_match:
            return bundle_match.group(1).strip()[:45]
        return "Research task"
    
    if 'Morning' in entry_type or 'Evening' in entry_type:
        return "Planning cycle"
    
    return entry_type[:30]

# ==== GIT TODAY ====
today_commits = []
try:
    result = subprocess.run(
        ['git', 'log', '--oneline', '--since="2026-02-26 00:00:00"', '--until="2026-02-26 23:59:59"'],
        cwd='/home/agent/.openclaw/workspace',
        capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split('\n'):
        if line:
            msg = re.sub(r'^[a-f0-9]+\s*', '', line)
            if msg:
                today_commits.append(msg[:50])
except:
    pass

# ==== QUEUE ====
queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
with open(queue_path) as f:
    queue_content = f.read()

# Today's completed items
today_completed = []
for match in re.finditer(r'- \[x\] \[([^\]]+)\].*?(\d{4}-\d{2}-\d{2})', queue_content):
    date = match.group(2)
    if '2026-02-26' in date:
        today_completed.append(match.group(1)[:35])

# Pending items
p0_pending = []
for match in re.finditer(r'- \[ \] \[([^\]]+)\]', queue_content):
    if len(p0_pending) < 2:
        p0_pending.append(match.group(1))

# ==== RESEARCH ====
research_done = []
for i in range(1, 11):
    if f'[x] P{i}:' in queue_content:
        m = re.search(rf'\[x\] P{i}:\s*(.+?)\s*—', queue_content)
        if m:
            research_done.append(f"P{i}: {m.group(1)[:20]}")

# ==== BRAIN STATS ====
from brain import brain
stats = brain.stats()

# ==== BUILD REPORT ====
lines = []

lines.append("🌙 Clarvis Evening Report")
lines.append("=" * 40)
lines.append("")

# Today's activity
lines.append("📅 TODAY'S WORK")
lines.append("-" * 20)
if daytime_entries:
    for e in daytime_entries:
        result_match = re.search(r'Result: (\w+)', e['context'])
        result = result_match.group(1) if result_match else "?"
        task = extract_task_details(e['context'], e['type'])
        lines.append(f"  {e['time']} → {task} [{result}]")
else:
    lines.append("  (No daytime activity)")
lines.append("")

# Completed today
lines.append("✅ COMPLETED TODAY")
lines.append("-" * 20)
if today_completed:
    for t in today_completed:
        lines.append(f"  • {t}")
else:
    lines.append("  Nothing completed today")
lines.append("")

# Git commits
lines.append("📝 GIT COMMITS")
lines.append("-" * 20)
if today_commits:
    for c in today_commits[:4]:
        lines.append(f"  • {c}")
else:
    lines.append("  None")
lines.append("")

# Research
lines.append("🔬 RESEARCH")
lines.append("-" * 20)
lines.append(f"  Done: {len(research_done)}/10")
for r in research_done[-3:]:
    lines.append(f"    ✓ {r}")
lines.append("")

# Queue
lines.append("📋 QUEUE")
lines.append("-" * 20)
if p0_pending:
    lines.append(f"  P0: {', '.join(p0_pending)}")
else:
    lines.append("  P0: empty")
lines.append(f"  Today: {len(today_completed)} items done")
lines.append("")

# Brain
lines.append("🧠 BRAIN")
lines.append("-" * 20)
lines.append(f"  Memories: {stats['total_memories']}")

lines.append("")
lines.append("=" * 40)
lines.append("Good night, sir.")

report = "\n".join(lines)

# Send to Telegram
data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": report})
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
#!/bin/bash
# Evening Report - 11:00 PM CET
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
import urllib.request
import urllib.parse
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

# Get bot token
with open('/home/agent/.openclaw/openclaw.json') as f:
    config = json.load(f)
TOKEN = config['channels']['telegram']['botToken']

stats = brain.stats()

# Read actual P1 priorities from QUEUE.md
queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
with open(queue_path) as f:
    queue_content = f.read()

# Extract P1 items completed today
p1_match = re.search(r'## P1 — This Week\s*\n(.*?)(?=##|$)', queue_content, re.DOTALL)
p1_items = []
if p1_match:
    for line in p1_match.group(1).strip().split('\n'):
        if '- [ ]' in line:
            task = re.sub(r'^- \[ \]\s*', '', line.split('—')[0] if '—' in line else line)
            task = re.sub(r'\s*\([^)]+\)\s*$', '', task).strip()
            if task and len(task) < 60:
                p1_items.append(task[:55])

# Count completed research
completed_research = queue_content.count('[x] P')

collections_str = ", ".join([f"{k.split('-')[-1]}({v})" for k,v in stats['collections'].items()])
p1_str = " • ".join(p1_items[:3]) if p1_items else "All clear"

report = f"""🌙 Clarvis Evening Report

🧠 Brain: {stats['total_memories']} memories, {len(stats['collections'])} collections
📁 Collections: {collections_str}

📋 P1: {p1_str}
🔬 Research: {completed_research}/10 priority sessions done

🎯 Current Focus: Evolution toward AGI/consciousness
🔄 Status: Ready for nighttime evolution

Sweet dreams, sir."""

# Send to Telegram
data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": report})
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
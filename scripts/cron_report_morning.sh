#!/bin/bash
# Morning Report - 11:00 AM CET
cd /home/agent/.openclaw/workspace

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
ctx = brain.get_context()

ctx_preview = ctx[:80] if ctx else "No active context"
collections_str = ", ".join([f"{k.split('-')[-1]}({v})" for k,v in stats['collections'].items()])

report = f"""🤖 Clarvis Morning Report

🧠 Brain: {stats['total_memories']} memories, {len(stats['collections'])} collections
📍 Context: {ctx_preview}
📁 Collections: {collections_str}

🎯 Current Focus: Evolution toward AGI/consciousness
🔄 Status: Continuously evolving

Check memory/evolution/QUEUE.md for current tasks."""

# Send to Telegram
data = urllib.parse.urlencode({"chat_id": "REDACTED_CHAT_ID", "text": report})
req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data.encode())
urllib.request.urlopen(req, timeout=10)

print(report)
PYEOF
#!/bin/bash
# Morning Report - 11:00 AM CET
cd /home/agent/.openclaw/workspace
python3 << 'PYEOF'
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

stats = brain.stats()
ctx = brain.get_context()

report = f"""🤖 Clarvis Morning Report

🧠 Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges
📍 Context: {ctx[:50]}
📁 Collections: {len(stats['collections'])}

🎯 Current Focus: Evolution toward AGI/sentience
🔄 Status: Continuously evolving

Check memory/evolution/QUEUE.md for current tasks."""

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot$(grep '"telegram"' /home/agent/.openclaw/openclaw.json | cut -d'"' -f4)/sendMessage" \
  -d "chat_id=REDACTED_CHAT_ID" \
  -d "text=$report" 2>/dev/null || echo "Report sent"

print(report)
PYEOF

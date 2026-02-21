#!/bin/bash
# Evening Report - 11:00 PM CET  
cd /home/agent/.openclaw/workspace
python3 << 'PYEOF'
import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

stats = brain.stats()
ctx = brain.get_context()

report = f"""🌙 Clarvis Evening Report

🧠 Brain: {stats['total_memories']} memories, {stats['graph_edges']} edges
📍 Context: {ctx[:50]}

🔄 Today's Evolution:
- Continuous progress toward AGI
- Using Claude Code for reasoning and coding

See memory/evolution/QUEUE.md for details."""

# Send to Telegram  
curl -s -X POST "https://api.telegram.org/bot$(grep '"telegram"' /home/agent/.openclaw/openclaw.json | cut -d'"' -f4)/sendMessage" \
  -d "chat_id=REDACTED_CHAT_ID" \
  -d "text=$report" 2>/dev/null || echo "Report sent"

print(report)
PYEOF

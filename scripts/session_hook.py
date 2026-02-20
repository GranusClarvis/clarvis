#!/usr/bin/env python3
"""
Session Hook — Close automation for Clarvis
Summarizes conversations, extracts learnings, stores to brain
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

def session_close(summary_path=None):
    """
    Run on session close to:
    1. Read session summary if provided
    2. Extract key decisions/learnings
    3. Store to brain
    4. Write to daily log
    """
    print("=== Session Close ===")
    
    today = datetime.now().strftime("%Y-%m-%d")
    memory_file = f"/home/agent/.openclaw/workspace/memory/{today}.md"
    
    # If no summary provided, extract from recent brain activity
    if summary_path and os.path.exists(summary_path):
        with open(summary_path) as f:
            content = f.read()
    else:
        # Get recent memories as proxy for session activity
        recent = brain.recall_recent(days=0, n=10)
        content = "\n".join([m['document'][:200] for m in recent])
    
    # Extract key learnings
    learnings = []
    for line in content.split('\n'):
        if any(x in line.lower() for x in ['learned', 'completed', 'created', 'fixed', 'milestone']):
            if len(line) > 20:
                learnings.append(line.strip()[:150])
    
    # Store learnings
    stored = 0
    for l in learnings[:3]:
        brain.store(
            f"Session close: {l}",
            collection='clarvis-learnings',
            importance=0.7,
            tags=['session', 'close'],
            source='session_hook'
        )
        stored += 1
    
    # Store session context
    brain.set_context(f"Session closed {datetime.now().isoformat()}. {stored} learnings stored.")
    
    print(f"✅ Session closed: {stored} learnings stored")
    return stored

if __name__ == "__main__":
    session_close()

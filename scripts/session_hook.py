#!/usr/bin/env python3
"""
Session Hook - Session lifecycle automation
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

def session_close(session_key=None, messages=None):
    """
    Called when session ends. Summarizes conversation, extracts learnings, stores to brain.
    """
    print(f"=== Session Close: {session_key or 'unknown'} ===")
    
    if not messages:
        print("No messages to process")
        return
    
    # Extract key info
    decisions = []
    insights = []
    action_items = []
    
    for msg in messages:
        content = msg.get('content', '')
        role = msg.get('role', '')
        
        # Simple keyword extraction
        if any(x in content.lower() for x in ['decided', 'agreed', 'will do', 'priority']):
            decisions.append(content[:150])
        if any(x in content.lower() for x in ['insight', 'realized', 'learned', 'found']):
            insights.append(content[:150])
        if any(x in content.lower() for x in ['next', 'todo', 'will', 'should']):
            action_items.append(content[:150])
    
    # Store to brain
    if decisions:
        brain.store(
            f"Session decisions: {'; '.join(decisions[:3])}",
            collection="clarvis-learnings",
            importance=0.8,
            tags=["session", "decision"],
            source="session_close"
        )
    
    if insights:
        brain.store(
            f"Session insights: {'; '.join(insights[:3])}",
            collection="clarvis-learnings",
            importance=0.7,
            tags=["session", "insight"],
            source="session_close"
        )
    
    # Update context
    brain.set_context(f"Session closed. Decisions: {len(decisions)}, Insights: {len(insights)}")
    
    print(f"Stored: {len(decisions)} decisions, {len(insights)} insights")
    return {"decisions": len(decisions), "insights": len(insights)}

if __name__ == "__main__":
    # Test
    session_close("test-session", [
        {"role": "user", "content": "I want you to prioritize Claude Code sessions"},
        {"role": "assistant", "content": "Agreed - I'll focus on P1 items with Claude Code"},
    ])

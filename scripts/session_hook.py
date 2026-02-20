#!/usr/bin/env python3
"""
Clarvis Session Hook
Called at session start and during conversations

This integrates the brain into Clarvis's actual operation.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

def session_start():
    """
    Called at session start - load brain and verify it's working
    Returns brain status
    """
    from brain import brain
    
    health = brain.health_check()
    stats = brain.stats()
    context = brain.get_context()
    
    return {
        "status": health["status"],
        "total_memories": stats["total_memories"],
        "collections": len(stats["collections"]),
        "current_context": context,
        "graph_edges": stats["graph_edges"]
    }


def end_session():
    """
    Called at session end - could save final state, etc.
    """
    from brain import brain
    
    # Could do cleanup, save context, etc.
    stats = brain.stats()
    
    return {
        "memories_at_end": stats["total_memories"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def remember_important(text, importance=0.9):
    """
    Quickly remember something important
    Use this during conversations
    """
    from auto_capture import remember
    return remember(text, importance)


def recall_context(query):
    """
    Recall relevant context for a query
    """
    from brain import brain
    return brain.recall(query, n=5)


def get_context_brief():
    """
    Get a brief context summary for the session
    """
    from brain import brain
    
    context = brain.get_context()
    goals = brain.get_goals()[:3]  # Top 3 goals
    
    brief = f"Context: {context}\n"
    brief += f"Top Goals:\n"
    for g in goals:
        brief += f"  - {g['document']}\n"
    
    return brief


# Quick aliases for use in conversations
def capture(text):
    """Quick capture during conversation"""
    from auto_capture import process
    return process(text)


if __name__ == "__main__":
    print("=== SESSION INTEGRATION TEST ===\n")
    
    # Test session start
    status = session_start()
    print(f"Session Start Status:")
    print(f"  Status: {status['status']}")
    print(f"  Total Memories: {status['total_memories']}")
    print(f"  Collections: {status['collections']}")
    print(f"  Context: {status['current_context']}")
    
    print(f"\n--- Context Brief ---")
    print(get_context_brief())
    
    print(f"\n--- Quick Capture Test ---")
    result = capture("This is a test capture from session hook")
    print(f"Captured: {result['captured']}")

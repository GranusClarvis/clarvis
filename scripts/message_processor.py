#!/usr/bin/env python3
"""
Clarvis Message Processor
Integrates ClarvisDB into message processing pipeline

Usage in conversation:
    from message_processor import process_inbound, process_outbound
    
    # Before processing message
    context = process_inbound(user_message, metadata)
    
    # After sending response
    process_outbound(assistant_response, metadata)
"""

import sys
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from smart_capture import smart_capture
from brain import brain, remember


def process_inbound(message, metadata=None):
    """
    Process incoming message - capture important context.
    
    Args:
        message: User message text
        metadata: Dict with sender, channel, timestamp, etc.
    
    Returns:
        Context dict with relevant memories for this conversation
    """
    # Get recent context
    recent = brain.recall_recent(days=3, n=5)
    
    # Check if user has specific preferences
    sender = metadata.get("sender", "") if metadata else ""
    if sender:
        prefs = brain.recall(f"preferences {sender}", n=3, min_importance=0.6)
    else:
        prefs = []
    
    # Smart capture the message
    capture_result = smart_capture(message, source="inbound", context=metadata)
    
    # Build context for agent
    context = {
        "recent_memories": [r["document"][:100] for r in recent[:3]],
        "user_preferences": [p["document"][:100] for p in prefs[:2]],
        "captured": capture_result["captured"],
        "brain_health": brain.health_check()
    }
    
    return context


def process_outbound(response, metadata=None):
    """
    Process outgoing message - capture important outputs.
    
    Args:
        response: Assistant response text
        metadata: Dict with conversation info
    
    Returns:
        Capture result
    """
    # Only capture if marked as important or contains key info
    if "remember" in response.lower() or "important" in response.lower():
        return smart_capture(response, source="outbound", context=metadata)
    
    # Check for factual/technical content
    technical_markers = ["config", "setting", "the issue is", "solution:", "to fix"]
    if any(marker in response.lower() for marker in technical_markers):
        return smart_capture(response, source="outbound_technical", context=metadata)
    
    return {"captured": False, "reason": "not_marked_important"}


def get_conversation_context(query=None, n=5):
    """
    Get context for ongoing conversation.
    Call this at the start of processing to load relevant memories.
    
    Args:
        query: Optional query to find specific context
        n: Number of memories to retrieve
    
    Returns:
        Dict with relevant memories and context
    """
    recent = brain.recall_recent(days=7, n=n)
    context = brain.get_context()
    goals = brain.get_goals()[:3]
    
    if query:
        specific = brain.recall(query, n=n, min_importance=0.5)
    else:
        specific = []
    
    return {
        "recent": [r["document"] for r in recent],
        "specific": [r["document"] for r in specific] if specific else [],
        "context": context,
        "active_goals": [g["document"] for g in goals]
    }


def update_session_context(context_text):
    """
    Update the current session context in the brain.
    Call when starting a new task or topic.
    """
    brain.set_context(context_text)
    return context_text


# Quick integration function
def init_session():
    """
    Initialize brain for a new session.
    Call this at the start of each conversation.
    
    Returns:
        Session context summary
    """
    stats = brain.stats()
    context = brain.get_context()
    goals = brain.get_goals()[:3]
    
    print(f"🧠 ClarvisDB initialized: {stats['total_memories']} memories")
    print(f"📍 Context: {context}")
    if goals:
        print(f"🎯 Active goals: {len(goals)}")
    
    return {
        "total_memories": stats["total_memories"],
        "context": context,
        "goals": goals,
        "status": "ready"
    }


if __name__ == "__main__":
    # Test
    print("=== MESSAGE PROCESSOR TEST ===\n")
    
    # Test inbound
    ctx = process_inbound("I want to build a smart memory system", {"sender": "REDACTED_CHAT_ID"})
    print(f"Inbound context: {ctx['recent_memories'][:1]}")
    print(f"Captured: {ctx['captured']}")
    
    # Test conversation context
    conv = get_conversation_context("ClarvisDB")
    print(f"\nConversation context: {conv.get('context', 'none')}")
    
    # Test init
    print("\n")
    init_session()

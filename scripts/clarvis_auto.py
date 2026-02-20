#!/usr/bin/env python3
"""
Clarvis Auto-Processing
P0: Brain processes every message automatically
"""

import sys
import os

# Add scripts to path
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

from clarvis_brain import get_brain

def process_message(message: str, role: str = "user") -> dict:
    """
    Auto-process every message through brain.
    This should be called BEFORE the model responds.
    
    Args:
        message: The message content
        role: "user" or "assistant" or "system"
    
    Returns:
        dict with processing results
    """
    brain = get_brain()
    
    results = {
        "stored": False,
        "related_memories": [],
        "goals_affected": []
    }
    
    # 1. Extract what matters - store in memory
    if message and len(message.strip()) > 0:
        brain.process(message, source=role)
        results["stored"] = True
    
    # 2. Check for related memories
    if message and len(message.strip()) > 3:
        try:
            related = brain.recall(message, n=3)
            if related and related.get("ids"):
                results["related_memories"] = related["ids"][0]
        except Exception as e:
            pass  # Don't fail if recall fails
    
    # 3. Track goal progress (check if any goals are mentioned)
    if message:
        try:
            # Simple keyword check for now
            goals = brain.get_goals()
            for goal in goals:
                if any(word in message.lower() for word in goal.get("goal", "").lower().split()[:3]):
                    results["goals_affected"].append(goal.get("id"))
        except:
            pass
    
    return results


def process_conversation(messages: list) -> dict:
    """
    Process a full conversation history.
    
    Args:
        messages: List of {"role": "user|assistant", "content": "..."}
    
    Returns:
        dict with aggregated results
    """
    total_processed = 0
    all_related = []
    goals_affected = []
    
    for msg in messages:
        result = process_message(msg.get("content", ""), msg.get("role", "user"))
        if result["stored"]:
            total_processed += 1
        all_related.extend(result["related_memories"])
        goals_affected.extend(result["goals_affected"])
    
    return {
        "messages_processed": total_processed,
        "unique_related": list(set(all_related)),
        "goals_affected": list(set(goals_affected))
    }


def auto_start() -> dict:
    """
    Called at session start - load context and check for pending work.
    """
    brain = get_brain()
    
    results = {
        "recent_memories": [],
        "pending_goals": [],
        "session_context": {}
    }
    
    # Get recent memories
    try:
        recent = brain.recall("recent", n=5)
        if recent and recent.get("ids"):
            results["recent_memories"] = recent["ids"][0]
    except:
        pass
    
    # Get pending goals
    try:
        goals = brain.get_goals()
        results["pending_goals"] = [g for g in goals if g.get("status") in ["pending", "in_progress"]]
    except:
        pass
    
    return results


if __name__ == "__main__":
    import json
    
    # CLI mode for testing
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "process" and len(sys.argv) > 2:
            # Process a single message
            message = " ".join(sys.argv[2:])
            result = process_message(message, "user")
            print(json.dumps(result, indent=2))
        
        elif command == "start":
            # Session start
            result = auto_start()
            print(json.dumps(result, indent=2))
        
        elif command == "test":
            # Test the auto-processing
            print("Testing auto-processing...")
            
            test_messages = [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "content": "I'm doing well, thank you!"},
                {"role": "user", "content": "I want to build a new feature."}
            ]
            
            result = process_conversation(test_messages)
            print(json.dumps(result, indent=2))
        
        else:
            print("Commands:")
            print("  process <message>  - Process a single message")
            print("  start             - Session start (load context)")
            print("  test              - Run test")
    else:
        print("Clarvis Auto-Processing (P0)")
        print("Usage: clarvis_auto.py <command>")
        print("  process <msg> - Process message")
        print("  start        - Session start")
        print("  test         - Run tests")
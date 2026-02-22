#!/usr/bin/env python3
"""
Clarvis Auto-Capture
Automatically extracts and stores important information from conversations

Usage:
    from auto_capture import capture
    
    capture.process("user said: remember that I hate verbose responses")
    # → Stores if importance > threshold
"""

import sys
import re
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

# Importance patterns
HIGH_IMPORTANCE_PATTERNS = [
    r"\b(remember|don'?t forget|important|critical|note that)\b",
    r"\b(prefer|hate|love|always|never)\b",
    r"\b(my name is|i am|i work|i live)\b",
    r"\b(password|key|secret|token|api)\b",  # Flag for security review
    r"\b(goal|objective|target|deadline)\b",
    r"\b(bug|fix|issue|problem|error)\b",
    r"\b(inverse|patrick|granus)\b",
]

LOW_IMPORTANCE_PATTERNS = [
    r"^(ok|okay|sure|yes|no|thanks|thank you|nice|cool|good)\.?$",
    r"^(hmm|uh|um|ah)\.?$",
]

# Category detection
CATEGORY_PATTERNS = {
    "clarvis-preferences": [
        r"\b(prefer|hate|love|like|dislike|want|don'?t want)\b",
    ],
    "clarvis-learnings": [
        r"\b(learned|lesson|mistake|don'?t do|should|shouldn'?t)\b",
        r"\b(fixed|solved|resolved|bug|issue)\b",
    ],
    "clarvis-identity": [
        r"\b(my name is|i am|i'?m called)\b",
        r"\b(creator|made me|built me)\b",
    ],
    "clarvis-infrastructure": [
        r"\b(server|host|port|ip|domain|database|api)\b",
        r"\b(running on|deployed|config)\b",
    ],
    "clarvis-goals": [
        r"\b(goal|objective|target|deadline|milestone)\b",
        r"\b(working on|building|creating)\b",
    ],
}


def assess_importance(text):
    """Assess importance of text on 0-1 scale"""
    text_lower = text.lower()
    score = 0.5  # Default
    
    for pattern in HIGH_IMPORTANCE_PATTERNS:
        if re.search(pattern, text_lower):
            score += 0.1
    
    for pattern in LOW_IMPORTANCE_PATTERNS:
        if re.search(pattern, text_lower):
            score -= 0.2
    
    return max(0.0, min(1.0, score))


def detect_category(text):
    """Detect which collection this belongs to"""
    text_lower = text.lower()
    
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return category
    
    return "clarvis-memories"  # Default


def extract_tags(text):
    """Extract relevant tags from text"""
    tags = []
    text_lower = text.lower()
    
    # Technical tags
    if re.search(r"\b(code|script|python|js|rust)\b", text_lower):
        tags.append("technical")
    if re.search(r"\b(bug|fix|error|issue)\b", text_lower):
        tags.append("bug")
    if re.search(r"\b(security|password|key|token)\b", text_lower):
        tags.append("security")
    if re.search(r"\b(inverse|patrick)\b", text_lower):
        tags.append("human")
    if re.search(r"\b(goal|objective)\b", text_lower):
        tags.append("goal")
    
    return tags


def should_capture(text, min_importance=0.6):
    """Determine if text should be captured"""
    importance = assess_importance(text)
    return importance >= min_importance


def process(text, source="conversation", force=False):
    """
    Process text and store if important
    
    Args:
        text: The text to process
        source: Where this came from
        force: Force capture regardless of importance
    
    Returns:
        dict with capture status
    """
    importance = assess_importance(text)
    
    if not force and importance < 0.6:
        return {
            "captured": False,
            "reason": f"low importance ({importance:.2f})",
            "importance": importance
        }
    
    # Detect category and tags
    category = detect_category(text)
    tags = extract_tags(text)
    
    # Store
    memory_id = brain.store(
        text,
        collection=category,
        importance=importance,
        tags=tags,
        source=source
    )
    
    return {
        "captured": True,
        "memory_id": memory_id,
        "importance": importance,
        "category": category,
        "tags": tags
    }


def process_message(user_message, assistant_response=None):
    """
    Process a full message exchange
    
    Args:
        user_message: What the user said
        assistant_response: What Clarvis responded (optional)
    
    Returns:
        list of captured memories
    """
    captured = []
    
    # Process user message
    result = process(user_message, source="user")
    if result["captured"]:
        captured.append(result)
    
    # Process assistant response if provided
    if assistant_response:
        result = process(assistant_response, source="clarvis")
        if result["captured"]:
            captured.append(result)
    
    return captured


def get_recent_context(n=5):
    """Get recent high-importance memories for context"""
    from brain import MEMORIES, LEARNINGS, GOALS
    
    memories = []
    
    # Get recent from each important collection
    for col in [MEMORIES, LEARNINGS, GOALS]:
        results = brain.recall("recent", collections=[col], n=n, min_importance=0.7)
        memories.extend(results)
    
    # Sort by importance
    memories.sort(key=lambda x: x["metadata"].get("importance", 0), reverse=True)
    
    return memories[:n]


# Convenience function for manual capture
def remember(text, importance=0.9, category=None):
    """Manually remember something important"""
    if category is None:
        category = detect_category(text)
    
    tags = extract_tags(text)
    
    memory_id = brain.store(
        text,
        collection=category,
        importance=importance,
        tags=tags,
        source="manual"
    )
    
    return memory_id


if __name__ == "__main__":
    # Test auto-capture
    test_cases = [
        "Remember that I prefer direct communication",
        "I hate verbose responses",
        "ok",
        "The server is running on port 18789",
        "My goal is to build a working brain",
        "Fixed the bug in the memory system",
        "Inverse said to focus on ClarvisDB"
    ]
    
    print("=== AUTO-CAPTURE TEST ===\n")
    
    for text in test_cases:
        result = process(text)
        status = "✓ CAPTURED" if result["captured"] else "✗ SKIPPED"
        print(f"{status}: \"{text[:40]}...\"")
        if result["captured"]:
            print(f"  Category: {result['category']}")
            print(f"  Importance: {result['importance']:.2f}")
            print(f"  Tags: {result['tags']}")
        print()

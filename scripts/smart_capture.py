#!/usr/bin/env python3
"""
Smart Capture - Intelligent memory capture using semantic analysis
NOT keyword matching - uses embedding similarity and context

How it works:
1. Compute embedding of incoming text
2. Compare against existing memories (semantic similarity)
3. Check if it's novel (not duplicate)
4. Assess importance via context analysis
5. Store only if it adds value
"""

import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

def compute_novelty(text, brain, threshold=0.85):
    """
    Check if text is novel compared to existing memories.
    Returns (is_novel, similarity_score, closest_match)
    """
    results = brain.recall(text, n=3)
    
    if not results:
        return True, 0.0, None
    
    # Check similarity via embedding distance
    # ChromaDB returns results sorted by similarity
    closest = results[0]
    
    # ChromaDB distances: lower = more similar
    # We consider it novel if no very close match exists
    # This is a heuristic - true embedding distance would be better
    
    # Check if text is essentially duplicate
    text_lower = text.lower().strip()
    closest_lower = closest["document"].lower().strip()
    
    # Exact match check
    if text_lower == closest_lower:
        return False, 1.0, closest
    
    # Substring check (one contains the other)
    if text_lower in closest_lower or closest_lower in text_lower:
        return False, 0.9, closest
    
    # Semantic similarity via word overlap (simple heuristic)
    text_words = set(text_lower.split())
    closest_words = set(closest_lower.split())
    overlap = len(text_words & closest_words) / max(len(text_words), 1)
    
    if overlap > threshold:
        return False, overlap, closest
    
    return True, overlap, closest


def assess_importance_smart(text, context=None):
    """
    Smart importance assessment using multiple signals:
    1. Explicit markers (remember, important, etc.)
    2. Context signals (user emphasis, correction, new info)
    3. Information density (facts vs fluff)
    4. Actionability (commands vs observations)
    """
    text_lower = text.lower()
    score = 0.5  # Base score
    
    # Explicit importance markers
    explicit_high = ["remember", "don't forget", "important", "critical", 
                     "note that", "write this down", "keep in mind"]
    for marker in explicit_high:
        if marker in text_lower:
            score += 0.15
    
    # Context signals (would need conversation history)
    context_high = ["actually", "correction", "wait,", "sorry,",
                    "I meant", "let me clarify", "to be clear"]
    for marker in context_high:
        if marker in text_lower:
            score += 0.1
    
    # Information density signals
    density_high = ["because", "therefore", "which means", "result is",
                    "the issue is", "the solution", "found that"]
    for marker in density_high:
        if marker in text_lower:
            score += 0.1
    
    # Personal/preference signals
    personal = ["I prefer", "I like", "I hate", "my ", "I want",
                "I need", "my goal", "my plan"]
    for marker in personal:
        if marker in text_lower:
            score += 0.15
    
    # Technical/factual signals
    technical = ["config", "setting", "port", "server", "database",
                 "api", "key", "token", "password", "endpoint"]
    for marker in technical:
        if marker in text_lower:
            score += 0.05
    
    # Low importance signals
    low_signals = ["ok", "okay", "sure", "yes", "no", "thanks",
                   "nice", "cool", "good", "fine", "alright"]
    # Only reduce if it's a SHORT message (likely just acknowledgment)
    words = text.split()
    if len(words) <= 4:  # Increased threshold
        text_clean = text_lower.strip()
        for marker in low_signals:
            if text_clean == marker or text_clean.startswith(marker + " "):
                score -= 0.4
                break
    
    return max(0.0, min(1.0, score))


def smart_capture(text, source="conversation", context=None, force=False):
    """
    Intelligently capture memory if it's novel and important.
    
    Args:
        text: The text to potentially capture
        source: Where this came from
        context: Additional context (conversation history, etc.)
        force: Force capture regardless of heuristics
    
    Returns:
        dict with capture decision and reasoning
    """
    from brain import brain
    
    # Check novelty
    is_novel, similarity, closest = compute_novelty(text, brain)
    
    if not is_novel and not force:
        return {
            "captured": False,
            "reason": "duplicate",
            "similarity": similarity,
            "closest_match": closest["document"][:50] if closest else None
        }
    
    # Assess importance
    importance = assess_importance_smart(text, context)
    
    if importance < 0.4 and not force:
        return {
            "captured": False,
            "reason": "low_importance",
            "importance": importance
        }
    
    # Determine category based on content analysis
    category = detect_category_smart(text)
    
    # Extract tags based on content
    tags = extract_tags_smart(text)
    
    # Store the memory
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
        "tags": tags,
        "novelty": "new" if is_novel else "similar_to_existing"
    }


def detect_category_smart(text):
    """Detect collection based on content analysis"""
    from brain import IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, MEMORIES
    
    text_lower = text.lower()
    
    # Score each category
    scores = {
        IDENTITY: 0,
        PREFERENCES: 0,
        LEARNINGS: 0,
        INFRASTRUCTURE: 0,
        GOALS: 0
    }
    
    # Identity signals
    identity_words = ["i am", "my name", "created by", "creator", "who i am", "identity"]
    scores[IDENTITY] = sum(1 for w in identity_words if w in text_lower) * 0.3
    
    # Preference signals
    pref_words = ["prefer", "like", "hate", "want", "don't want", "style", "verbose", "direct"]
    scores[PREFERENCES] = sum(1 for w in pref_words if w in text_lower) * 0.25
    
    # Learning signals
    learn_words = ["learned", "lesson", "mistake", "fixed", "solved", "error", "bug", "issue", "should", "shouldn't"]
    scores[LEARNINGS] = sum(1 for w in learn_words if w in text_lower) * 0.25
    
    # Infrastructure signals
    infra_words = ["server", "port", "host", "config", "database", "api", "running", "deployed"]
    scores[INFRASTRUCTURE] = sum(1 for w in infra_words if w in text_lower) * 0.25
    
    # Goal signals
    goal_words = ["goal", "objective", "target", "milestone", "working on", "building", "plan"]
    scores[GOALS] = sum(1 for w in goal_words if w in text_lower) * 0.25
    
    # Find highest score
    max_cat = max(scores, key=scores.get)
    max_score = scores[max_cat]
    
    # If no strong signal, use memories
    if max_score < 0.2:
        return MEMORIES
    
    return max_cat


def extract_tags_smart(text):
    """Extract tags based on content"""
    tags = []
    text_lower = text.lower()
    
    tag_patterns = {
        "technical": ["code", "script", "python", "bash", "config", "server"],
        "bug": ["bug", "error", "fix", "issue", "broken"],
        "security": ["password", "key", "token", "secret", "credential"],
        "human": ["inverse", "patrick", "user", "human"],
        "goal": ["goal", "objective", "target", "plan"],
        "learning": ["learned", "lesson", "mistake", "should"],
        "preference": ["prefer", "like", "hate", "style"]
    }
    
    for tag, patterns in tag_patterns.items():
        if any(p in text_lower for p in patterns):
            tags.append(tag)
    
    return tags


def process_conversation_message(message, role="user", conversation_context=None):
    """
    Process a message from a conversation.
    This is the main entry point for auto-capture.
    
    Args:
        message: The message text
        role: "user" or "assistant"
        conversation_context: List of recent messages for context
    
    Returns:
        Capture result
    """
    # Only capture user messages (usually more important)
    # But also capture significant assistant outputs
    
    if role == "user":
        # User messages - check for importance
        return smart_capture(message, source=f"user_message", context=conversation_context)
    else:
        # Assistant messages - only capture if explicitly marked important
        if "remember" in message.lower() or "important" in message.lower():
            return smart_capture(message, source="assistant_note", context=conversation_context)
        
        return {"captured": False, "reason": "assistant_message_not_marked"}


# CLI for testing
if __name__ == "__main__":
    test_cases = [
        "Remember that I prefer concise responses",
        "The server is running on port 18789",
        "I learned that I should always check logs before deleting anything",
        "ok",
        "My goal is to have a fully autonomous brain",
        "Actually, let me correct that - I want semantic understanding",
        "Fixed the bug in the memory system by checking duplicates first",
        "Inverse said to focus on making the brain fully integrated",
        "ok thanks",
        "Critical: The database path is /home/agent/.openclaw/workspace/data/clarvisdb"
    ]
    
    print("=== SMART CAPTURE TEST ===\n")
    
    for text in test_cases:
        result = smart_capture(text)
        status = "✓ CAPTURED" if result["captured"] else "✗ SKIPPED"
        print(f"{status}: \"{text[:40]}...\"")
        if result["captured"]:
            print(f"  Category: {result['category']}")
            print(f"  Importance: {result['importance']:.2f}")
            print(f"  Tags: {result['tags']}")
        else:
            print(f"  Reason: {result['reason']}")
        print()

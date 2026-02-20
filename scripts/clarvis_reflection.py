#!/usr/bin/env python3
"""
Clarvis Reflection Loop
Reads today's memory, extracts lessons, stores in brain
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from brain import brain

def get_today_memory():
    """Read today's memory file"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"/home/agent/.openclaw/workspace/memory/{today}.md"
    
    if not os.path.exists(path):
        return None
    
    with open(path) as f:
        return f.read()

def extract_lessons(content):
    """Extract key lessons from memory content"""
    lessons = []
    
    # Simple extraction: look for lines with key patterns
    lines = content.split('\n')
    for line in lines:
        # Look for action items, completions, insights
        if any(x in line.lower() for x in ['completed', 'done', 'created', 'fixed', 'milestone', 'insight', 'learned']):
            # Clean and add
            cleaned = line.strip()
            if len(cleaned) > 20 and not cleaned.startswith('#'):
                lessons.append(cleaned[:200])  # Truncate long lines
    
    return lessons[:5]  # Max 5 lessons

def store_lessons(lessons):
    """Store lessons in brain"""
    stored = 0
    for lesson in lessons:
        brain.store(
            lesson,
            collection='clarvis-learnings',
            importance=0.8,
            tags=['reflection', 'daily'],
            source='reflection_loop'
        )
        stored += 1
    return stored

def main():
    print("=== Clarvis Reflection Loop ===")
    
    # Get today's memory
    content = get_today_memory()
    if not content:
        print("No memory file for today")
        return
    
    # Extract lessons
    lessons = extract_lessons(content)
    if not lessons:
        print("No lessons extracted")
        return
    
    print(f"Found {len(lessons)} lessons")
    
    # Store in brain
    stored = store_lessons(lessons)
    print(f"Stored {stored} lessons in brain")
    
    # Show what was stored
    print("\nLessons stored:")
    for i, lesson in enumerate(lessons, 1):
        print(f"  {i}. {lesson[:80]}...")

if __name__ == "__main__":
    main()

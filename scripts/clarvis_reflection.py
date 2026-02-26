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

def count_pending_tasks():
    """Count unchecked tasks in QUEUE.md"""
    queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
    if not os.path.exists(queue_path):
        return 0
    with open(queue_path) as f:
        content = f.read()
    return content.count('- [ ]')


def generate_queue_tasks(lessons, content):
    """
    Generate new evolution tasks based on today's lessons and memory.
    Returns list of task strings to add to QUEUE.md.
    """
    tasks = []

    # Analyze what was worked on today to suggest next steps
    lines = content.split('\n')
    topics_today = set()
    for line in lines:
        lower = line.lower()
        for keyword in ['attention', 'memory', 'brain', 'reasoning', 'evolution',
                        'consciousness', 'learning', 'model', 'prediction',
                        'synthesis', 'reflection', 'working_memory', 'confidence']:
            if keyword in lower:
                topics_today.add(keyword)

    # Check what scripts exist but might not be wired in
    scripts_dir = "/home/agent/.openclaw/workspace/scripts"
    unwired_candidates = [
        ('attention.py', 'Wire attention.py into daily execution — use salience scoring in cron_autonomous task selection'),
        ('working_memory.py', 'Make working_memory.py persistent across sessions — save/load spotlight buffer to disk'),
        ('reasoning_chains.py', 'Integrate reasoning_chains.py into heartbeat — log a reasoning chain for each evolution task'),
        ('knowledge_synthesis.py', 'Run knowledge_synthesis.py in daily reflection — find new cross-domain connections'),
        ('clarvis_confidence.py', 'Review prediction outcomes — check calibration curve and adjust confidence thresholds'),
        ('self_model.py', 'Run self-assessment — update capability model based on today\'s successes and failures'),
    ]

    # Non-Python improvements to consider
    architectural_candidates = [
        'Review and update HEARTBEAT.md protocol — are all 7 steps still optimal? Remove/add steps based on recent outcomes',
        'Audit cron schedule timing — are there gaps or overlaps? Tune intervals based on actual completion times',
        'Review task_selector.py scoring weights — do AGI_KEYWORDS and INTEGRATION_KEYWORDS reflect current priorities?',
        'Update ROADMAP.md with actual progress measurements — are phase assessments still accurate?',
        'Audit skills/ directory — are all skills documented and working? Create new skills for common operations',
        'Review cron prompt templates — do they guide Claude Code toward the right kinds of work?',
        'Tune openclaw.json settings — heartbeat interval, compaction mode, max concurrent based on usage data',
        'Simplify or merge overlapping scripts — 90+ scripts may have redundancy',
    ]

    for script, task in unwired_candidates:
        script_path = os.path.join(scripts_dir, script)
        if os.path.exists(script_path):
            # Check if it's mentioned in crontab or other scripts (rough check)
            if script not in content:  # not mentioned in today's memory = probably not running
                tasks.append(task)

    # Also suggest 1-2 architectural improvements (non-Python work)
    import random
    arch_sample = random.sample(architectural_candidates, min(2, len(architectural_candidates)))
    for arch_task in arch_sample:
        if arch_task[:40] not in content:  # not already discussed today
            tasks.append(arch_task)

    # Generate tasks from lessons (what could improve based on what was learned)
    for lesson in lessons:
        lower = lesson.lower()
        if 'fail' in lower or 'error' in lower or 'broke' in lower:
            tasks.append(f"Investigate recurring failure pattern: {lesson[:80]}")
        if 'slow' in lower or 'timeout' in lower or 'performance' in lower:
            tasks.append(f"Optimize performance issue found: {lesson[:80]}")

    # Always suggest meta-improvement if queue is nearly empty
    pending = count_pending_tasks()
    if pending < 3:
        tasks.append("Deep self-analysis: What capability gap is most limiting? Design an experiment to address it")

    return tasks[:5]  # Max 5 new tasks per reflection


def add_tasks_to_queue(tasks):
    """Add new tasks to QUEUE.md under P1 section via shared queue_writer."""
    if not tasks:
        return 0
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from queue_writer import add_tasks
        added = add_tasks(tasks, priority="P1", source="reflection")
        return len(added)
    except ImportError:
        # Fallback: direct write
        queue_path = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"
        if not os.path.exists(queue_path):
            return 0
        with open(queue_path) as f:
            content = f.read()
        added = 0
        new_lines = []
        for task in tasks:
            if task[:40] not in content:
                new_lines.append(f"- [ ] {task}")
                added += 1
        if not new_lines:
            return 0
        today = datetime.now().strftime("%Y-%m-%d")
        marker = "## P1 — This Week"
        if marker in content:
            insert_block = "\n".join(new_lines)
            parts = content.split(marker, 1)
            content = parts[0] + marker + f"\n\n### Auto-generated {today}\n" + insert_block + "\n" + parts[1]
        else:
            content += "\n\n## P1 — Auto-generated " + today + "\n" + "\n".join(new_lines) + "\n"
        with open(queue_path, 'w') as f:
            f.write(content)
        return added


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
        print("No lessons extracted today, but checking queue health...")
        lessons = []  # Continue to check queue
    else:
        print(f"Found {len(lessons)} lessons")
        # Store in brain
        stored = store_lessons(lessons)
        print(f"Stored {stored} lessons in brain")
        print("\nLessons stored:")
        for i, lesson in enumerate(lessons, 1):
            print(f"  {i}. {lesson[:80]}...")

    # === KEY: Generate and add new evolution tasks ===
    pending = count_pending_tasks()
    print(f"\nQueue health: {pending} pending tasks")

    if pending < 5:
        print("Queue running low — generating new tasks...")
        new_tasks = generate_queue_tasks(lessons, content)
        if new_tasks:
            added = add_tasks_to_queue(new_tasks)
            print(f"Added {added} new tasks to QUEUE.md:")
            for t in new_tasks:
                print(f"  + {t[:80]}")
        else:
            print("No new tasks generated — queue may need manual review")
    else:
        print(f"Queue healthy ({pending} pending), skipping generation")


if __name__ == "__main__":
    main()

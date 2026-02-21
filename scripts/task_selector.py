#!/usr/bin/env python3
"""
Task Selector — Attention-based task prioritization for Clarvis

Uses attention.py salience scoring + brain.py context to pick the BEST task
from the evolution queue. Replaces the crude bash keyword matching with
proper GWT-inspired salience computation.

Called by cron_autonomous.sh before each execution cycle.

Usage:
    python3 task_selector.py           # Output best task as JSON
    python3 task_selector.py --all     # Output all scored tasks
"""

import json
import re
import sys

sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')

from attention import attention
from brain import brain

QUEUE_FILE = "/home/agent/.openclaw/workspace/memory/evolution/QUEUE.md"

# Keywords that signal AGI/consciousness relevance (high-value work)
AGI_KEYWORDS = [
    "agi", "consciousness", "attention", "working memory", "self model",
    "reasoning", "phi", "neural", "meta-cognition", "awareness", "gwt",
    "spotlight", "global workspace", "prediction", "calibration",
]

# Keywords that signal integration work (connecting existing components)
INTEGRATION_KEYWORDS = [
    "wire", "integrate", "connect", "hook", "persistent", "feedback loop",
    "into cron", "into daily", "run daily", "automat",
]


def parse_tasks(queue_file=QUEUE_FILE):
    """Parse unchecked tasks from QUEUE.md with their priority section."""
    tasks = []
    current_section = "P2"

    with open(queue_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect section headers
            if '## P0' in line:
                current_section = "P0"
            elif '## P1' in line:
                current_section = "P1"
            elif '## P2' in line:
                current_section = "P2"
            elif '## Completed' in line:
                current_section = "completed"

            # Match unchecked tasks
            match = re.match(r'^- \[ \] (.+)$', stripped)
            if match and current_section != "completed":
                tasks.append({
                    "line_num": line_num,
                    "text": match.group(1),
                    "section": current_section,
                })

    return tasks


def score_tasks(tasks):
    """
    Score each task using attention-based salience + brain context.

    Scoring factors:
      1. Section importance: P0=0.9, P1=0.6, P2=0.3
      2. Context relevance: word overlap with current brain context
      3. Recent activity relevance: overlap with last day's memories
      4. AGI/consciousness boost: tasks advancing core goals
      5. Integration boost: tasks wiring existing components together
    """
    # Get current brain context for relevance scoring
    try:
        context = brain.get_context()
    except Exception:
        context = ""

    # Get recent activity from brain for relevance
    try:
        recent = brain.recall_recent(days=1, n=10)
        recent_text = " ".join([r["document"] for r in recent])
    except Exception:
        recent_text = ""

    scored = []

    for task in tasks:
        text = task["text"]
        section = task["section"]
        text_lower = text.lower()

        # 1. Base importance from priority section
        section_importance = {"P0": 0.9, "P1": 0.6, "P2": 0.3}.get(section, 0.3)

        # 2. Relevance to current context (word overlap)
        context_words = set(context.lower().split()) if context else set()
        task_words = set(text_lower.split())
        if task_words:
            context_overlap = len(context_words & task_words) / len(task_words)
            context_relevance = min(1.0, context_overlap * 2)
        else:
            context_relevance = 0.0

        # 3. Relevance to recent activity
        recent_words = set(recent_text.lower().split()) if recent_text else set()
        if task_words:
            recent_overlap = len(recent_words & task_words) / len(task_words)
            recent_relevance = min(1.0, recent_overlap * 1.5)
        else:
            recent_relevance = 0.0

        # Combined relevance (take the stronger signal)
        relevance = max(context_relevance, recent_relevance * 0.8, 0.3)

        # 4. AGI/consciousness boost
        agi_boost = 0.0
        for kw in AGI_KEYWORDS:
            if kw in text_lower:
                agi_boost = min(0.3, agi_boost + 0.1)

        # 5. Integration/wiring boost
        integration_boost = 0.0
        for kw in INTEGRATION_KEYWORDS:
            if kw in text_lower:
                integration_boost = min(0.2, integration_boost + 0.1)

        total_boost = agi_boost + integration_boost

        # Submit to attention system for proper salience calculation
        # This uses GWT-inspired scoring: recency, importance, relevance, boost
        item = attention.submit(
            content=f"TASK: {text[:120]}",
            source="evolution_queue",
            importance=section_importance,
            relevance=relevance,
            boost=total_boost,
        )

        salience = item.salience()

        scored.append({
            "text": text,
            "section": section,
            "line_num": task["line_num"],
            "salience": round(salience, 4),
            "details": {
                "section_importance": section_importance,
                "context_relevance": round(context_relevance, 3),
                "recent_relevance": round(recent_relevance, 3),
                "agi_boost": round(agi_boost, 3),
                "integration_boost": round(integration_boost, 3),
                "combined_relevance": round(relevance, 3),
            }
        })

    # Sort by salience (highest first)
    scored.sort(key=lambda x: x["salience"], reverse=True)
    return scored


def select_best_task():
    """Main entry: parse, score, return best task as JSON on stdout."""
    tasks = parse_tasks()

    if not tasks:
        result = {"error": "no_tasks", "message": "Queue empty"}
        print(json.dumps(result))
        return None

    scored = score_tasks(tasks)

    # Log all scores to stderr (captured in cron log)
    for t in scored:
        print(
            f"SALIENCE: {t['salience']:.4f} [{t['section']}] {t['text'][:80]}",
            file=sys.stderr,
        )

    best = scored[0]

    # Also run attention tick (competition cycle) to maintain spotlight health
    attention.tick()

    # Output best task as JSON on stdout
    print(json.dumps(best))
    return best


if __name__ == "__main__":
    if "--all" in sys.argv:
        tasks = parse_tasks()
        if not tasks:
            print("No pending tasks in queue.")
            sys.exit(0)
        scored = score_tasks(tasks)
        print(f"\n{'='*70}")
        print(f"  ATTENTION-SCORED TASK RANKING ({len(scored)} tasks)")
        print(f"{'='*70}")
        for i, t in enumerate(scored):
            marker = " >>> BEST" if i == 0 else ""
            print(f"  {i+1}. [{t['salience']:.4f}] [{t['section']}] {t['text'][:70]}{marker}")
            d = t["details"]
            print(f"     importance={d['section_importance']}  relevance={d['combined_relevance']}"
                  f"  agi={d['agi_boost']}  integration={d['integration_boost']}")
        print(f"{'='*70}")
    else:
        select_best_task()

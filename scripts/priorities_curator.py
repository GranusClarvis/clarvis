#!/usr/bin/env python3
"""
Priorities Curator — maintains a single authoritative 'current priorities'
memory in clarvis-goals that is refreshed weekly.

Replaces stale daily planning fragments with one curated, searchable anchor
so that queries like "what are the current priorities?" hit a strong match.

Usage:
    python3 priorities_curator.py              # Refresh priorities memory
    python3 priorities_curator.py show         # Show current priorities memory
    python3 priorities_curator.py prune        # Prune stale planning fragments

Designed to run weekly (Sunday cron or manual). Reads:
  - QUEUE.md P0/P1 items for delivery priorities
  - clarvis-goals collection for active goals + progress
  - ROADMAP.md for strategic context
Writes:
  - Single memory ID 'current-priorities' in clarvis-goals (upserted)
  - Optionally supersedes stale daily planning fragments in clarvis-memories
"""
import sys
import os
import re
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain

WORKSPACE = Path("/home/agent/.openclaw/workspace")
QUEUE_FILE = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
ROADMAP_FILE = WORKSPACE / "ROADMAP.md"
PRIORITIES_ID = "current-priorities"
GOALS_COLLECTION = "clarvis-goals"
MEMORIES_COLLECTION = "clarvis-memories"
STATE_FILE = WORKSPACE / "data" / "priorities_curator_state.json"


def _read_queue_priorities():
    """Extract P0 and P1 items from QUEUE.md."""
    if not QUEUE_FILE.exists():
        return {"p0": [], "p1": []}

    text = QUEUE_FILE.read_text()
    p0_items = []
    p1_items = []

    # Find P0 section
    p0_match = re.search(r'## P0[^\n]*\n(.*?)(?=\n## P1|\n---)', text, re.DOTALL)
    if p0_match:
        section = p0_match.group(1)
        # Extract delivery goal bullet points
        for line in section.split('\n'):
            line = line.strip()
            if line.startswith('- ') and not line.startswith('- [x]'):
                p0_items.append(line.lstrip('- ').strip())

    # Find P1 section
    p1_match = re.search(r'## P1[^\n]*\n(.*?)(?=\n## P2|\n---)', text, re.DOTALL)
    if p1_match:
        section = p1_match.group(1)
        for line in section.split('\n'):
            line = line.strip()
            if line.startswith('- [ ]'):
                item = line.replace('- [ ]', '').strip()
                # Truncate long task descriptions
                if len(item) > 120:
                    item = item[:117] + '...'
                p1_items.append(item)

    return {"p0": p0_items, "p1": p1_items}


def _read_active_goals():
    """Read active (non-completed) goals from clarvis-goals."""
    col = brain.collections.get(GOALS_COLLECTION)
    if not col:
        return []

    results = col.get(include=['documents', 'metadatas'])
    goals = []
    for doc, meta in zip(results['documents'], results['metadatas']):
        if meta.get('lifecycle') == 'completed' or meta.get('archived') == 'true':
            continue
        progress = meta.get('progress', 0)
        name = meta.get('goal', doc[:60])
        importance = meta.get('importance', 0.5)
        goals.append({
            'name': name,
            'progress': progress,
            'importance': importance,
            'doc': doc[:120],
        })

    # Sort by importance descending
    goals.sort(key=lambda g: g['importance'], reverse=True)
    return goals


def _build_priorities_text(queue_data, goals):
    """Build the authoritative priorities text."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime('%Y-%m-%d')
    week_str = now.strftime('%Y-W%W')

    lines = [
        f"Current priorities (week of {date_str}, updated {week_str}):",
        "",
    ]

    # P0 delivery items
    if queue_data['p0']:
        lines.append("DELIVERY PRIORITIES (P0):")
        for item in queue_data['p0']:
            lines.append(f"  - {item}")
        lines.append("")

    # P1 active tasks
    if queue_data['p1']:
        lines.append("ACTIVE TASKS (P1):")
        for item in queue_data['p1'][:8]:  # Cap at 8 to keep concise
            lines.append(f"  - {item}")
        if len(queue_data['p1']) > 8:
            lines.append(f"  ... and {len(queue_data['p1']) - 8} more P1 items")
        lines.append("")

    # Active goals with progress
    if goals:
        lines.append("ACTIVE GOALS (by importance):")
        for g in goals[:8]:
            lines.append(f"  - {g['name']}: {g['progress']}% (importance={g['importance']:.2f})")
        lines.append("")

    # Strategic context
    lines.append("This memory is the authoritative source for current priorities.")
    lines.append("Updated weekly by priorities_curator.py. Supersedes daily planning fragments.")

    return "\n".join(lines)


def refresh_priorities():
    """Refresh the current-priorities memory in clarvis-goals."""
    queue_data = _read_queue_priorities()
    goals = _read_active_goals()
    text = _build_priorities_text(queue_data, goals)

    # Upsert with fixed ID so it's always one memory
    memory_id = brain.store(
        text,
        collection=GOALS_COLLECTION,
        importance=0.95,  # High importance for retrieval anchoring
        tags=["priorities", "curated", "weekly"],
        source="priorities_curator",
        memory_id=PRIORITIES_ID,
    )

    # Save state
    state = {
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "p0_count": len(queue_data['p0']),
        "p1_count": len(queue_data['p1']),
        "goal_count": len(goals),
        "memory_id": memory_id,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))

    print(f"Refreshed '{PRIORITIES_ID}' in {GOALS_COLLECTION}")
    print(f"  P0 items: {len(queue_data['p0'])}")
    print(f"  P1 items: {len(queue_data['p1'])}")
    print(f"  Active goals: {len(goals)}")
    print(f"  Text length: {len(text)} chars")
    return text


def show_priorities():
    """Show the current priorities memory if it exists."""
    col = brain.collections.get(GOALS_COLLECTION)
    if not col:
        print("No clarvis-goals collection found.")
        return

    try:
        result = col.get(ids=[PRIORITIES_ID], include=['documents', 'metadatas'])
        if result['documents']:
            print(result['documents'][0])
            print(f"\n--- Metadata ---")
            meta = result['metadatas'][0]
            print(f"  importance: {meta.get('importance')}")
            print(f"  created_at: {meta.get('created_at')}")
            print(f"  source: {meta.get('source')}")
        else:
            print("No current-priorities memory found. Run: python3 priorities_curator.py")
    except Exception as e:
        print(f"Not found: {e}")


def prune_stale_fragments():
    """Find and supersede stale daily planning fragments in clarvis-memories."""
    col = brain.collections.get(MEMORIES_COLLECTION)
    if not col:
        print("No clarvis-memories collection found.")
        return

    # Search for daily planning fragments
    results = col.query(
        query_texts=["I planned today priorities focus this week"],
        n_results=20,
        include=['documents', 'metadatas', 'distances'],
    )

    pruned = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    for doc, meta, dist in zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0],
    ):
        # Only prune close matches that look like daily planning
        if dist > 1.3:
            continue
        text_lower = doc.lower()
        if not any(phrase in text_lower for phrase in [
            'i planned today', 'today i plan', 'priorities for today',
            'focus today', 'this week focus', 'today: finish',
        ]):
            continue

        # Check if old enough to prune
        created = meta.get('created_at', '')
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                if created_dt > cutoff:
                    continue  # Too recent, keep it
            except (ValueError, TypeError):
                pass

        # Mark as superseded
        meta['superseded_by'] = PRIORITIES_ID
        meta['superseded_at'] = now.isoformat()
        # Lower importance so it stops surfacing
        meta['importance'] = max(0.1, meta.get('importance', 0.5) * 0.3)

        # Get the ID for this document
        doc_id = None
        all_docs = col.get(include=['documents'])
        for i, d in enumerate(all_docs['documents']):
            if d == doc:
                doc_id = all_docs['ids'][i]
                break

        if doc_id:
            col.update(ids=[doc_id], metadatas=[meta])
            pruned += 1
            print(f"  Superseded: {doc_id} (dist={dist:.3f})")

    print(f"\nPruned {pruned} stale planning fragments.")
    return pruned


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "refresh"

    if cmd == "show":
        show_priorities()
    elif cmd == "prune":
        prune_stale_fragments()
    elif cmd in ("refresh", "update"):
        text = refresh_priorities()
        print(f"\n--- Priority Memory Content ---\n{text}")
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: priorities_curator.py [refresh|show|prune]")
        sys.exit(1)

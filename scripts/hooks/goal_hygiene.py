#!/usr/bin/env python3
"""
Goal Hygiene — Lifecycle management for Clarvis goals.

Manages goal states: active / deprecated / archived / conflicting.
Prevents retired goals from steering salience, retrieval, and morning planning.

Lifecycle:
  active     — currently pursued, high importance, steers attention
  deprecated — no longer primary, low importance, still searchable
  archived   — moved out of active collection, preserved in archive
  conflicting — contradicts another active goal, flagged for resolution

Rules:
  - Goals at 100% progress for >7 days → auto-deprecate
  - Goals with consciousness-first language → flag for review
  - Goals not accessed in >14 days → candidate for deprecation
  - Deprecated goals with importance >0.7 → reduce importance to 0.3
  - Archived goals → moved to clarvis-memories with archive tag

Usage:
    python3 goal_hygiene.py audit      # Audit all goals, show lifecycle state
    python3 goal_hygiene.py deprecate  # Auto-deprecate stale goals
    python3 goal_hygiene.py archive    # Archive deprecated goals >14 days old
    python3 goal_hygiene.py clean      # Full pipeline: audit → deprecate → archive
    python3 goal_hygiene.py stats      # Quick stats
"""

import json
import os
import sys
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 — registers all script subdirs on sys.path
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from clarvis.brain import brain

WORKSPACE = "/home/agent/.openclaw/workspace"
GOALS_COLLECTION = "clarvis-goals"

# Stale consciousness-first patterns to flag
SNAPSHOT_FILE = os.path.join(WORKSPACE, "data", "goals_snapshot.json")

# Garbage patterns — noise from auto-store that aren't real goals
# Matched against goal name (metadata 'goal' field) and document text.
GARBAGE_PATTERNS = [
    "bridge", "sbridge", "connection between", "fm goals",
    "outcome", "gwt broadcast", "boost_", "fresh_mirror",
]
# Document-level garbage — entries that are clearly not goals (reasoning chains,
# outcomes, procedures, self-representations, meta-learning alerts, etc.)
DOC_GARBAGE_PATTERNS = [
    "reasoning chain",
    "self-representation update",
    "self-state z_t",
    "meta-learning alert",
    "gwt broadcast context",
    "procedure:",
    "evening code review",
    "morning plan",
]

CONSCIOUSNESS_PATTERNS = [
    r'(?:develop|achieve|reach|build|create)\b.*\bconsciousness\b',
    r'\bsentien[ct]',
    r'\bqualia\b',
    r'\bphenomenal\s+experience',
    r'\bsubjective experience\b',
    r'\bfeel(?:ing|s)?\b.*\breal\b',
    r'\binner life\b',
    r'\bself-aware(?:ness)?\b.*(?:genuine|true|real)',
]

# Thresholds
COMPLETE_DAYS = 7        # Days at 100% before auto-deprecate
STALE_DAYS = 14          # Days without access before deprecation candidate
ARCHIVE_DAYS = 14        # Days after deprecation before archival
DEPRECATE_IMPORTANCE = 0.3  # Reduce importance to this on deprecation


def get_all_goals():
    """Fetch all goals from the collection with full metadata."""
    col = brain.collections.get(GOALS_COLLECTION)
    if not col:
        print(f"Collection {GOALS_COLLECTION} not found")
        return []

    count = col.count()
    if count == 0:
        return []

    result = col.get(include=["documents", "metadatas", "embeddings"])
    goals = []
    for i in range(len(result["ids"])):
        goals.append({
            "id": result["ids"][i],
            "document": result["documents"][i] if result["documents"] else "",
            "metadata": result["metadatas"][i] if result["metadatas"] else {},
        })
    return goals


def classify_goal(goal):
    """Classify a goal's lifecycle state.

    Returns: (state, reasons) where state is active/deprecated/archive_candidate/conflicting
    """
    meta = goal.get("metadata", {})
    doc = goal.get("document", "")
    now = datetime.now(timezone.utc)
    reasons = []

    # Check existing lifecycle tag
    lifecycle = meta.get("lifecycle", "active")
    if lifecycle in ("deprecated", "archived"):
        return lifecycle, [f"already {lifecycle}"]

    progress = meta.get("progress", 0)
    if isinstance(progress, str):
        try:
            progress = int(progress)
        except ValueError:
            progress = 0

    # Check: 100% complete for >N days
    if progress >= 100:
        updated = meta.get("updated", "")
        if updated:
            try:
                updated_dt = datetime.fromisoformat(updated)
                days_complete = (now - updated_dt).days
                if days_complete > COMPLETE_DAYS:
                    reasons.append(f"100% complete for {days_complete} days")
            except Exception:
                pass

    # Check: not accessed recently
    last_accessed = meta.get("last_accessed", "")
    if last_accessed:
        try:
            last_dt = datetime.fromisoformat(last_accessed)
            days_stale = (now - last_dt).days
            if days_stale > STALE_DAYS:
                reasons.append(f"not accessed in {days_stale} days")
        except Exception:
            pass

    # Check: consciousness-first language
    text = (doc + " " + meta.get("text", "")).lower()
    for pattern in CONSCIOUSNESS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            reasons.append(f"consciousness-first language: /{pattern}/")
            break

    # Determine state
    if reasons:
        # Multiple signals = stronger candidate
        if len(reasons) >= 2:
            return "archive_candidate", reasons
        elif any("100% complete" in r for r in reasons):
            return "deprecate_candidate", reasons
        elif any("consciousness" in r for r in reasons):
            return "review", reasons
        else:
            return "deprecate_candidate", reasons

    return "active", []


def audit_goals():
    """Audit all goals and report lifecycle states."""
    goals = get_all_goals()
    if not goals:
        print("No goals found.")
        return {}

    states = {"active": [], "deprecate_candidate": [], "archive_candidate": [],
              "deprecated": [], "archived": [], "review": []}

    print(f"=== Goal Hygiene Audit — {len(goals)} goals ===\n")

    for goal in goals:
        state, reasons = classify_goal(goal)
        meta = goal["metadata"]
        name = meta.get("goal", goal["id"][:30])
        progress = meta.get("progress", "?")
        importance = meta.get("importance", "?")

        states[state].append(goal)

        if state != "active":
            print(f"  [{state.upper()}] {name} (progress={progress}%, importance={importance})")
            for r in reasons:
                print(f"    - {r}")

    print(f"\n--- Summary ---")
    for state, items in states.items():
        if items:
            print(f"  {state}: {len(items)}")

    return states


def deprecate_goals(dry_run=False):
    """Auto-deprecate stale goals: reduce importance and tag lifecycle=deprecated."""
    goals = get_all_goals()
    deprecated_count = 0

    for goal in goals:
        state, reasons = classify_goal(goal)
        if state not in ("deprecate_candidate", "archive_candidate"):
            continue

        meta = goal["metadata"]
        name = meta.get("goal", goal["id"][:30])

        if dry_run:
            print(f"  [DRY-RUN] Would deprecate: {name}")
            deprecated_count += 1
            continue

        # Update metadata
        new_meta = dict(meta)
        new_meta["lifecycle"] = "deprecated"
        new_meta["deprecated_at"] = datetime.now(timezone.utc).isoformat()
        old_importance = meta.get("importance", 0.5)
        if isinstance(old_importance, str):
            try:
                old_importance = float(old_importance)
            except ValueError:
                old_importance = 0.5
        new_meta["importance"] = min(old_importance, DEPRECATE_IMPORTANCE)
        new_meta["original_importance"] = old_importance

        # Update in collection
        col = brain.collections[GOALS_COLLECTION]
        col.update(
            ids=[goal["id"]],
            metadatas=[new_meta],
        )
        print(f"  Deprecated: {name} (importance {old_importance:.2f} → {DEPRECATE_IMPORTANCE})")
        deprecated_count += 1

    print(f"\nDeprecated {deprecated_count} goals.")
    return deprecated_count


def archive_goals(dry_run=False):
    """Archive deprecated goals that have been deprecated for >ARCHIVE_DAYS."""
    goals = get_all_goals()
    archived_count = 0
    now = datetime.now(timezone.utc)

    for goal in goals:
        meta = goal["metadata"]
        lifecycle = meta.get("lifecycle", "active")
        if lifecycle != "deprecated":
            continue

        deprecated_at = meta.get("deprecated_at", "")
        if not deprecated_at:
            continue

        try:
            dep_dt = datetime.fromisoformat(deprecated_at)
            days_deprecated = (now - dep_dt).days
        except Exception:
            continue

        if days_deprecated < ARCHIVE_DAYS:
            continue

        name = meta.get("goal", goal["id"][:30])

        if dry_run:
            print(f"  [DRY-RUN] Would archive: {name} (deprecated {days_deprecated}d ago)")
            archived_count += 1
            continue

        # Store in clarvis-memories with archive tag
        archive_text = f"[ARCHIVED GOAL] {goal['document']}"
        brain.store(
            archive_text,
            collection="clarvis-memories",
            importance=0.2,
            tags=["archived-goal", "goal-hygiene"],
            source="goal-hygiene",
        )

        # Remove from goals collection
        col = brain.collections[GOALS_COLLECTION]
        col.delete(ids=[goal["id"]])
        print(f"  Archived: {name} → clarvis-memories")
        archived_count += 1

    print(f"\nArchived {archived_count} goals.")
    return archived_count


def show_stats():
    """Quick stats on goal health."""
    goals = get_all_goals()
    if not goals:
        print("No goals found.")
        return

    states = {}
    for goal in goals:
        state, _ = classify_goal(goal)
        states[state] = states.get(state, 0) + 1

    total = len(goals)
    active = states.get("active", 0)
    deprecated = states.get("deprecated", 0)
    candidates = states.get("deprecate_candidate", 0) + states.get("archive_candidate", 0)
    review = states.get("review", 0)

    print(f"=== Goal Hygiene Stats ===")
    print(f"  Total goals:           {total}")
    print(f"  Active:                {active}")
    print(f"  Deprecated:            {deprecated}")
    print(f"  Deprecation candidates: {candidates}")
    print(f"  Needs review:          {review}")
    print(f"  Health:                {'GOOD' if candidates == 0 else f'{candidates} goals need attention'}")


def purge_garbage(dry_run=False):
    """Archive goals matching garbage patterns (noise from auto-store)."""
    goals = get_all_goals()
    purged = 0
    col = brain.collections[GOALS_COLLECTION]

    for goal in goals:
        meta = goal["metadata"]
        if str(meta.get("archived", "")).lower() == "true":
            continue
        if meta.get("lifecycle") in ("deprecated", "archived"):
            continue

        name = meta.get("goal", goal["id"])
        if not name or len(name.strip()) < 10:
            if dry_run:
                print(f"  [DRY-RUN] Would archive (short name): {goal['id'][:50]}")
            else:
                meta["archived"] = "true"
                col.update(ids=[goal["id"]], metadatas=[meta])
                print(f"  Archived (short name): {goal['id'][:50]}")
            purged += 1
            continue

        nl = name.lower().strip()
        doc_lower = goal.get("document", "").lower()

        # Match name-level garbage patterns
        if any(p in nl for p in GARBAGE_PATTERNS):
            if dry_run:
                print(f"  [DRY-RUN] Would archive (garbage name): {name[:50]}")
            else:
                meta["archived"] = "true"
                col.update(ids=[goal["id"]], metadatas=[meta])
                print(f"  Archived (garbage name): {name[:50]}")
            purged += 1
            continue

        # Match document-level garbage patterns (non-goal content stored in goals)
        if any(p in doc_lower for p in DOC_GARBAGE_PATTERNS):
            matched = next(p for p in DOC_GARBAGE_PATTERNS if p in doc_lower)
            if dry_run:
                print(f"  [DRY-RUN] Would archive (garbage doc: '{matched}'): {name[:50]}")
            else:
                meta["archived"] = "true"
                col.update(ids=[goal["id"]], metadatas=[meta])
                print(f"  Archived (garbage doc: '{matched}'): {name[:50]}")
            purged += 1

    print(f"\nPurged {purged} garbage goals.")
    return purged


def write_snapshot():
    """Write a compact goals snapshot using canonical get_goals_summary()."""
    summary = brain.get_goals_summary(top_n=15)
    snapshot = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "active_goals": summary,
    }
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"\nSnapshot written: {SNAPSHOT_FILE} ({len(summary)} goals)")
    return snapshot


def clean():
    """Full pipeline: purge garbage → audit → deprecate → archive → snapshot."""
    print("=== Step 0: Purge Garbage ===")
    purge_garbage()
    print()

    print("=== Step 1: Audit ===")
    states = audit_goals()
    print()

    candidates = len(states.get("deprecate_candidate", [])) + len(states.get("archive_candidate", []))
    if candidates > 0:
        print(f"=== Step 2: Deprecate ({candidates} candidates) ===")
        deprecate_goals()
        print()

    print("=== Step 3: Archive (deprecated >14 days) ===")
    archive_goals()
    print()

    print("=== Step 4: Snapshot ===")
    write_snapshot()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "audit":
        audit_goals()
    elif cmd == "deprecate":
        deprecate_goals()
    elif cmd == "archive":
        archive_goals()
    elif cmd == "clean":
        clean()
    elif cmd == "stats":
        show_stats()
    elif cmd == "dry-run":
        print("=== Dry Run: Deprecation ===")
        deprecate_goals(dry_run=True)
        print("\n=== Dry Run: Archival ===")
        archive_goals(dry_run=True)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: goal_hygiene.py [audit|deprecate|archive|clean|stats|dry-run]")

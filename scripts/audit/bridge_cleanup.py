#!/usr/bin/env python3
"""AUDIT_PHASE_4_5_BRIDGE_CLEANUP — Remove synthetic bridge/boost entries from primary collections.

Bridge/boost memories are graph relationship metadata that leaked into content
collections, polluting retrieval. They belong in the graph layer only.

Target collections: identity, infrastructure, memories (primary collections
where bridge content is noise). Other collections are scanned too for completeness.

Usage:
    python3 scripts/audit/bridge_cleanup.py              # dry-run (report only)
    python3 scripts/audit/bridge_cleanup.py --apply      # delete entries
    python3 scripts/audit/bridge_cleanup.py --export     # export before delete
"""
import argparse
import json
import os
import sys
import time

# Spine imports
from clarvis.brain import brain
from clarvis.brain.constants import (
    IDENTITY, INFRASTRUCTURE, MEMORIES,
    PREFERENCES, LEARNINGS, GOALS, CONTEXT,
    PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
    ALL_COLLECTIONS,
)
from clarvis.brain.search import _BRIDGE_ID_PREFIXES, _BRIDGE_TEXT_PREFIXES

# Primary collections where bridge content is definitively noise
PRIMARY_TARGETS = {IDENTITY, INFRASTRUCTURE, MEMORIES}

EXPORT_DIR = os.path.join(
    os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
    "data", "audit",
)


def find_bridge_entries(collection_name):
    """Scan a collection for bridge/boost entries by ID prefix and text prefix."""
    col = brain.collections.get(collection_name)
    if col is None or col.count() == 0:
        return []

    results = col.get(include=["documents", "metadatas"])
    ids = results.get("ids", [])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])

    matches = []
    for i, mem_id in enumerate(ids):
        doc = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}

        is_bridge = False
        reason = ""

        # Check ID prefix
        if any(mem_id.startswith(prefix) for prefix in _BRIDGE_ID_PREFIXES):
            is_bridge = True
            reason = f"id_prefix:{mem_id.split('_')[0]}_"

        # Check document text prefix
        if doc and any(doc.startswith(prefix) for prefix in _BRIDGE_TEXT_PREFIXES):
            is_bridge = True
            reason = reason or f"text_prefix:{doc[:30]}"

        if is_bridge:
            matches.append({
                "id": mem_id,
                "collection": collection_name,
                "document": doc[:200] if doc else "",
                "metadata": meta,
                "reason": reason,
            })

    return matches


def export_entries(entries, path):
    """Export bridge entries to JSON for audit trail."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "total": len(entries),
            "entries": entries,
        }, f, indent=2, default=str)
    print(f"Exported {len(entries)} entries to {path}")


def delete_entries(entries):
    """Delete bridge entries from their collections."""
    by_collection = {}
    for entry in entries:
        col_name = entry["collection"]
        by_collection.setdefault(col_name, []).append(entry["id"])

    total_deleted = 0
    for col_name, ids in by_collection.items():
        col = brain.collections.get(col_name)
        if col is None:
            print(f"  SKIP {col_name}: collection not available")
            continue
        col.delete(ids=ids)
        total_deleted += len(ids)
        print(f"  Deleted {len(ids)} from {col_name}")

    return total_deleted


def main():
    parser = argparse.ArgumentParser(description="Bridge cleanup for primary collections")
    parser.add_argument("--apply", action="store_true", help="Actually delete entries")
    parser.add_argument("--export", action="store_true", help="Export entries before delete")
    parser.add_argument("--all-collections", action="store_true",
                        help="Scan all collections, not just primary targets")
    args = parser.parse_args()

    target_collections = ALL_COLLECTIONS if args.all_collections else PRIMARY_TARGETS
    all_matches = []

    print(f"Scanning {len(target_collections)} collections for bridge/boost entries...")
    for col_name in sorted(target_collections):
        matches = find_bridge_entries(col_name)
        if matches:
            print(f"  {col_name}: {len(matches)} bridge entries found")
            all_matches.extend(matches)
        else:
            print(f"  {col_name}: clean")

    print(f"\nTotal bridge entries: {len(all_matches)}")

    if not all_matches:
        print("Nothing to clean up.")
        return 0

    # Show summary
    by_reason = {}
    for m in all_matches:
        by_reason.setdefault(m["reason"], 0)
        by_reason[m["reason"]] += 1
    print("\nBy reason:")
    for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    if args.export or args.apply:
        export_path = os.path.join(
            EXPORT_DIR,
            f"bridge_cleanup_{time.strftime('%Y-%m-%d')}.json",
        )
        export_entries(all_matches, export_path)

    if args.apply:
        print("\nDeleting entries...")
        deleted = delete_entries(all_matches)
        print(f"\nDone: {deleted} entries removed.")
    else:
        print("\nDry run — use --apply to delete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

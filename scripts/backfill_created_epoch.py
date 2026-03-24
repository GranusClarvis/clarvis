#!/usr/bin/env python3
"""Backfill created_epoch (int timestamp) for all existing memories.

One-time migration: parses created_at ISO string → Unix epoch int.
Memories without created_at get epoch=0 as a sentinel.

Usage:
    python3 scripts/backfill_created_epoch.py          # dry-run
    python3 scripts/backfill_created_epoch.py --apply   # apply changes
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clarvis"))
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone


def backfill(dry_run=True):
    from brain import brain

    total_updated = 0
    total_skipped = 0
    total_missing_created_at = 0

    for col_name, col in brain.collections.items():
        results = col.get(include=["metadatas", "documents"])
        if not results.get("ids"):
            continue

        batch_ids = []
        batch_docs = []
        batch_metas = []

        for i, mem_id in enumerate(results["ids"]):
            meta = results["metadatas"][i] if results.get("metadatas") else {}

            # Skip if already has created_epoch (including sentinel value 0)
            if meta.get("created_epoch") is not None:
                total_skipped += 1
                continue

            created_at = meta.get("created_at", "")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    epoch = int(dt.timestamp())
                except (ValueError, TypeError):
                    epoch = 0
                    total_missing_created_at += 1
            else:
                epoch = 0
                total_missing_created_at += 1

            meta["created_epoch"] = epoch
            batch_ids.append(mem_id)
            batch_docs.append(results["documents"][i] if results.get("documents") else "")
            batch_metas.append(meta)

        if batch_ids and not dry_run:
            # ChromaDB upsert in batches of 500
            for start in range(0, len(batch_ids), 500):
                end = start + 500
                col.upsert(
                    ids=batch_ids[start:end],
                    documents=batch_docs[start:end],
                    metadatas=batch_metas[start:end],
                )

        count = len(batch_ids)
        total_updated += count
        if count > 0:
            print(f"  {col_name}: {count} memories {'would be' if dry_run else ''} updated")

    print(f"\nTotal: {total_updated} updated, {total_skipped} already had epoch, {total_missing_created_at} missing created_at (set to 0)")
    if dry_run:
        print("DRY RUN — no changes written. Use --apply to apply.")
    else:
        print("DONE — all memories now have created_epoch metadata.")
    return total_updated


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    backfill(dry_run=not apply)

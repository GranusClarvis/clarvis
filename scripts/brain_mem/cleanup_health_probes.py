#!/usr/bin/env python3
"""Hard-delete orphan health-probe records from clarvis-memories.

Background: `ClarvisBrain.health_check()` writes a probe memory and tries to
delete it. Until 2026-05-10 the cleanup was wrapped in `except: pass`, so
every transient failure left the probe behind. The audit
`docs/internal/audits/P3_CHUNK_GRANULARITY_AUDIT_2026-05-07.md` §5 found
that ~60% of `clarvis-memories` were orphan health probes, dragging
retrieval quality.

This script removes records in `clarvis-memories` where:
  - id starts with `_health_probe_`, OR
  - document starts with `health_probe_`

Usage:
    python3 scripts/brain_mem/cleanup_health_probes.py            # dry-run
    python3 scripts/brain_mem/cleanup_health_probes.py --apply    # delete
    python3 scripts/brain_mem/cleanup_health_probes.py --apply --batch-size 50
"""
import argparse
import sys
import time

from clarvis.brain import brain
from clarvis.brain.constants import MEMORIES


def find_probes():
    col = brain.collections[MEMORIES]
    res = col.get()
    ids = res.get("ids") or []
    docs = res.get("documents") or []
    targets = []
    for mid, doc in zip(ids, docs):
        if mid.startswith("_health_probe_") or (doc and doc.startswith("health_probe_")):
            targets.append(mid)
    return targets, len(ids)


def main():
    ap = argparse.ArgumentParser(description="Cleanup orphan health-probe memories.")
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete (default is dry-run).")
    ap.add_argument("--batch-size", type=int, default=100,
                    help="Log progress every N deletions (default 100).")
    args = ap.parse_args()

    t0 = time.monotonic()
    targets, total = find_probes()
    n = len(targets)
    pct = (100.0 * n / total) if total else 0.0
    print(f"clarvis-memories total:    {total}")
    print(f"health-probe candidates:   {n} ({pct:.1f}%)")
    if not targets:
        print("nothing to do.")
        return 0

    if not args.apply:
        print("DRY-RUN — pass --apply to delete.")
        print(f"sample ids: {targets[:5]}")
        return 0

    print(f"applying hard-delete to {n} records...")
    deleted = 0
    failed = 0
    for mid in targets:
        try:
            r = brain.delete_memory(
                mid, collection=MEMORIES,
                reason="health_probe_orphan_cleanup", hard=True,
            )
            if r.get("success"):
                deleted += 1
            else:
                failed += 1
                print(f"  skip {mid}: {r.get('message')}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {mid}: {e}")
        if deleted and deleted % args.batch_size == 0:
            print(f"  ...{deleted}/{n} deleted")

    elapsed = time.monotonic() - t0
    print(f"done. deleted={deleted} failed={failed} in {elapsed:.1f}s")

    # Verify
    after, total_after = find_probes()
    print(f"post-cleanup clarvis-memories total: {total_after}")
    print(f"remaining health-probe candidates:   {len(after)}")
    return 0 if not after else 1


if __name__ == "__main__":
    sys.exit(main())

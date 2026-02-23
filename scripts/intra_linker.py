#!/usr/bin/env python3
"""
Intra-collection linker — boost within-collection edge density.

For each collection, find same-collection memory pairs with high semantic
similarity (cosine > 0.7) but no existing intra-collection edge, then
create 'similar_to' edges.  Capped at 5 new edges per collection per run
to avoid bloat.

Usage:
    python3 intra_linker.py              # Run linking
    python3 intra_linker.py --dry-run    # Preview without writing
    python3 intra_linker.py --cap 10     # Override per-collection cap
"""

import os
import sys
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import ClarvisBrain, ALL_COLLECTIONS


# L2 distance threshold that corresponds to cosine similarity ~ 0.7
# For unit-norm embeddings: L2^2 = 2(1 - cos), so cos=0.7 -> L2 = sqrt(0.6) ≈ 0.775
# ChromaDB MiniLM embeddings are approximately unit-norm, so we use 0.78 as cutoff.
SIMILARITY_THRESHOLD_DIST = 0.78


def build_existing_intra_pairs(brain):
    """Build set of existing intra-collection edge pairs for fast dedup."""
    pairs = set()
    for e in brain.graph.get("edges", []):
        src_col = e.get("source_collection", "")
        tgt_col = e.get("target_collection", "")
        # Intra-collection: same collection or both empty (legacy similar_to)
        if src_col == tgt_col or e.get("type") == "similar_to":
            pairs.add((e["from"], e["to"]))
            pairs.add((e["to"], e["from"]))
    return pairs


def run_intra_linker(cap_per_collection=5, dry_run=False, verbose=True):
    """
    For each collection, find high-similarity pairs missing intra edges.

    Returns:
        dict with per-collection stats and total new edges created.
    """
    brain = ClarvisBrain()
    existing_pairs = build_existing_intra_pairs(brain)

    total_new = 0
    results = {}

    for col_name in ALL_COLLECTIONS:
        col = brain.collections.get(col_name)
        if col is None or col.count() < 2:
            continue

        all_data = col.get(include=["documents"])
        ids = all_data.get("ids", [])
        docs = all_data.get("documents", [])

        if len(ids) < 2:
            continue

        candidates = []  # (id_a, id_b, distance)

        # Query each memory against its own collection to find close neighbors
        # Process in batches to limit queries on large collections
        sample_ids = ids
        sample_docs = docs

        # For very large collections, sample to avoid O(n^2) cost
        if len(ids) > 100:
            import random
            indices = random.sample(range(len(ids)), 100)
            sample_ids = [ids[i] for i in indices]
            sample_docs = [docs[i] for i in indices]

        for mem_id, doc in zip(sample_ids, sample_docs):
            if not doc or len(doc) < 10:
                continue

            try:
                results_q = col.query(
                    query_texts=[doc],
                    n_results=min(6, len(ids)),  # top 6, skip self
                )
            except Exception:
                continue

            if not results_q["ids"] or not results_q["ids"][0]:
                continue

            for rid, dist in zip(results_q["ids"][0], results_q["distances"][0]):
                if rid == mem_id:
                    continue
                if dist < SIMILARITY_THRESHOLD_DIST:
                    # Check both directions for existing edge
                    if (mem_id, rid) not in existing_pairs:
                        candidates.append((mem_id, rid, dist))

        # Deduplicate candidates: keep unique pairs, sorted by distance (best first)
        seen = set()
        unique_candidates = []
        for a, b, d in sorted(candidates, key=lambda x: x[2]):
            pair = tuple(sorted([a, b]))
            if pair not in seen:
                seen.add(pair)
                unique_candidates.append((a, b, d))

        # Cap per collection
        to_add = unique_candidates[:cap_per_collection]
        col_new = 0

        for a, b, dist in to_add:
            sim = max(0, 1.0 - dist / 2.0)
            if dry_run:
                if verbose:
                    print(f"  [DRY] {col_name}: {a[:30]}... <-> {b[:30]}... dist={dist:.3f} sim={sim:.2f}")
                col_new += 1
            else:
                brain.add_relationship(
                    a, b, "similar_to",
                    source_collection=col_name,
                    target_collection=col_name,
                )
                existing_pairs.add((a, b))
                existing_pairs.add((b, a))
                col_new += 1
                if verbose:
                    print(f"  {col_name}: +edge dist={dist:.3f} sim={sim:.2f}")

        if col_new > 0:
            results[col_name] = col_new
            total_new += col_new
            if verbose:
                print(f"  {col_name}: {col_new} new intra edges")

    if verbose:
        print(f"\nIntra-linker {'(DRY RUN) ' if dry_run else ''}complete: {total_new} new edges across {len(results)} collections")

    return {"new_edges": total_new, "per_collection": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Intra-collection linker")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--cap", type=int, default=5, help="Max new edges per collection (default 5)")
    args = parser.parse_args()

    result = run_intra_linker(cap_per_collection=args.cap, dry_run=args.dry_run)
    print(f"Total new intra edges: {result['new_edges']}")

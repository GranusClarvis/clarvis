#!/usr/bin/env python3
"""PHI_INTRA_DENSITY_BOOST — Add intra-collection edges for semantically similar memories.

Iterates each collection, computes pairwise cosine similarity on embeddings,
and adds intra-collection edges for similar pairs (cosine > threshold) that
lack an existing graph edge. Capped at MAX_EDGES_PER_COLLECTION to avoid bloat.

Usage:
    python3 scripts/brain_mem/intra_density_boost.py [--dry-run] [--threshold 0.6] [--cap 500]
"""
import argparse
import numpy as np

from clarvis.brain import brain


def cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity matrix."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid div by zero
    normed = embeddings / norms
    return normed @ normed.T


def get_existing_intra_edges(collection: str) -> set:
    """Get set of (from_id, to_id) for existing intra-collection edges."""
    existing = set()
    if brain._sqlite_store is not None:
        for etype in ("intra_similar", "semantic_similar", "similar", "hebbian_association"):
            edges = brain._sqlite_store.get_edges(edge_type=etype)
            for e in edges:
                src_col = e.get("source_collection", "")
                tgt_col = e.get("target_collection", "")
                if src_col == tgt_col == collection or (not src_col and not tgt_col):
                    existing.add((e["from_id"], e["to_id"]))
                    existing.add((e["to_id"], e["from_id"]))
    return existing


def boost_collection(collection_name: str, threshold: float = 0.6,
                     cap: int = 500, dry_run: bool = False) -> int:
    """Add intra-collection edges for one collection. Returns edges added."""
    col = brain.collections.get(collection_name)
    if col is None:
        print(f"  SKIP {collection_name}: not found")
        return 0

    result = col.get(include=["embeddings"])
    ids = result["ids"]
    embeddings = np.array(result["embeddings"])

    if len(ids) < 2:
        print(f"  SKIP {collection_name}: only {len(ids)} memories")
        return 0

    print(f"  {collection_name}: {len(ids)} memories, computing similarity...")

    sim_matrix = cosine_similarity_matrix(embeddings)
    existing = get_existing_intra_edges(collection_name)

    # Find pairs above threshold, sorted by similarity (highest first)
    candidates = []
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            sim = sim_matrix[i, j]
            if sim >= threshold:
                pair = (ids[i], ids[j])
                if pair not in existing and (pair[1], pair[0]) not in existing:
                    candidates.append((sim, ids[i], ids[j]))

    candidates.sort(reverse=True)
    to_add = candidates[:cap]

    print(f"    {len(candidates)} similar pairs found, adding {len(to_add)} edges"
          f"{' (dry-run)' if dry_run else ''}")

    added = 0
    for sim, from_id, to_id in to_add:
        if not dry_run:
            brain.add_relationship(
                from_id, to_id, "intra_similar",
                source_collection=collection_name,
                target_collection=collection_name,
            )
        added += 1

    return added


def main():
    parser = argparse.ArgumentParser(description="Boost intra-collection density for Phi")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually add edges")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Cosine similarity threshold (default: 0.6)")
    parser.add_argument("--cap", type=int, default=500,
                        help="Max edges per collection (default: 500)")
    args = parser.parse_args()

    total_added = 0

    # Target the worst collections first
    target_order = [
        "clarvis-learnings",      # 0.280
        "autonomous-learning",    # 0.287
        "clarvis-memories",       # 0.311
        "clarvis-identity",       # 0.322
        "clarvis-context",        # 0.355
        "clarvis-procedures",     # 0.386
        "clarvis-infrastructure", # 0.409
        "clarvis-goals",          # 0.419
        "clarvis-preferences",    # 0.443
        "clarvis-episodes",       # 0.552
    ]

    print(f"Intra-density boost: threshold={args.threshold}, cap={args.cap}/collection")
    print()

    for col_name in target_order:
        added = boost_collection(col_name, args.threshold, args.cap, args.dry_run)
        total_added += added

    print(f"\nTotal edges added: {total_added}")
    return total_added


if __name__ == "__main__":
    main()

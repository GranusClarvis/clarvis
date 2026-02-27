#!/usr/bin/env python3
"""
Intra-collection linker — boost within-collection edge density.

For each collection, fetch embeddings for all memories, compute pairwise
cosine similarity, and create 'similar_to' edges for pairs with
similarity > 0.7 that lack an existing intra-collection edge.

Capped at 5 new edges per collection per run (configurable via --cap)
to avoid graph bloat.

Target: intra_density component in Phi >= 0.50.

Usage:
    python3 intra_linker.py              # Run linking
    python3 intra_linker.py --dry-run    # Preview without writing
    python3 intra_linker.py --cap 10     # Override per-collection cap
    python3 intra_linker.py --threshold 0.8  # Stricter similarity cutoff
"""

import json
import os
import sys
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain, ALL_COLLECTIONS, GRAPH_FILE  # Use singleton to prevent data loss from concurrent writes


def _load_graph_safe():
    """Load the graph JSON, repairing truncation or trailing garbage.

    Concurrent writers (hebbian_memory, claude subprocesses) can corrupt
    the file mid-write.  This handles:
      - Truncated JSON (incomplete edge at end)
      - Extra data appended after valid JSON close
      - Both at once

    Returns the parsed graph dict (or empty default).
    """
    if not os.path.exists(GRAPH_FILE):
        return {"nodes": {}, "edges": []}

    with open(GRAPH_FILE, 'r') as f:
        raw = f.read()

    # 1. Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Handle "Extra data": find first complete JSON object
    decoder = json.JSONDecoder()
    try:
        data, end = decoder.raw_decode(raw.lstrip())
        if isinstance(data, dict) and "edges" in data:
            print(f"  [repair] Stripped trailing garbage after char {end}")
            return data
    except json.JSONDecodeError:
        pass

    # 3. Handle truncation: find last complete edge }, close the structure
    last_complete = raw.rfind('},')
    if last_complete > 0:
        fixed = raw[:last_complete + 1] + '\n  ]\n}'
        try:
            data = json.loads(fixed)
            print(f"  [repair] Fixed truncated graph: "
                  f"{len(data.get('nodes', {}))} nodes, {len(data.get('edges', []))} edges")
            return data
        except json.JSONDecodeError:
            pass

    print("  [repair] Could not repair graph — using empty graph")
    return {"nodes": {}, "edges": []}

COSINE_THRESHOLD = 0.7
DEFAULT_CAP = 5


def cosine_similarity_matrix(embeddings):
    """Compute pairwise cosine similarity for a matrix of embeddings.

    Args:
        embeddings: np.ndarray of shape (n, dim)

    Returns:
        np.ndarray of shape (n, n) with cosine similarities.
    """
    # Normalize rows to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid division by zero
    normed = embeddings / norms
    return normed @ normed.T


def build_existing_intra_pairs(brain):
    """Build set of existing intra-collection edge pairs for fast dedup."""
    pairs = set()
    for e in brain.graph.get("edges", []):
        src_col = e.get("source_collection", "")
        tgt_col = e.get("target_collection", "")
        # Intra-collection: same collection, or legacy similar_to without collection tags
        if src_col == tgt_col or e.get("type") == "similar_to":
            pairs.add((e["from"], e["to"]))
            pairs.add((e["to"], e["from"]))
    return pairs


def run_intra_linker(cap_per_collection=DEFAULT_CAP, dry_run=False,
                     threshold=COSINE_THRESHOLD, verbose=True):
    """
    For each collection, compute pairwise cosine similarity from embeddings
    and create intra-collection edges for high-similarity pairs.

    Returns:
        dict with per-collection stats, total new edges, and density snapshot.
    """
    # Use the brain singleton - its _save_graph() handles concurrent writes safely
    # via read-before-write merge, preventing lost-update race conditions.
    brain._load_graph()  # Refresh to get latest state
    existing_pairs = build_existing_intra_pairs(brain)

    total_new = 0
    results = {}
    density_before = {}
    density_after = {}

    for col_name in ALL_COLLECTIONS:
        col = brain.collections.get(col_name)
        if col is None or col.count() < 2:
            continue

        # Fetch IDs and embeddings for the entire collection
        all_data = col.get(include=["embeddings"])
        ids = all_data.get("ids", [])
        embeddings_raw = all_data.get("embeddings")

        if embeddings_raw is None or len(embeddings_raw) == 0 or len(ids) < 2:
            continue

        embeddings = np.array(embeddings_raw, dtype=np.float32)

        # For very large collections, subsample to avoid O(n^2) blowup
        if len(ids) > 200:
            import random
            indices = random.sample(range(len(ids)), 200)
            ids = [ids[i] for i in indices]
            embeddings = embeddings[indices]

        n = len(ids)

        # Compute density BEFORE linking
        intra_edges_before = 0
        for i in range(n):
            for j in range(i + 1, n):
                if (ids[i], ids[j]) in existing_pairs:
                    intra_edges_before += 1
        max_edges = n * (n - 1) // 2
        density_before[col_name] = intra_edges_before / max_edges if max_edges > 0 else 0

        # Compute full cosine similarity matrix
        sim_matrix = cosine_similarity_matrix(embeddings)

        # Collect candidates: pairs with sim > threshold and no existing edge
        candidates = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim > threshold and (ids[i], ids[j]) not in existing_pairs:
                    candidates.append((ids[i], ids[j], sim))

        # Sort by similarity descending (best pairs first)
        candidates.sort(key=lambda x: x[2], reverse=True)

        # Cap per collection
        to_add = candidates[:cap_per_collection]
        col_new = 0

        for a, b, sim in to_add:
            if dry_run:
                if verbose:
                    print(f"  [DRY] {col_name}: {a[:35]}... <-> {b[:35]}... cos={sim:.3f}")
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
                    print(f"  {col_name}: +edge cos={sim:.3f}")

        # Compute density AFTER linking
        intra_edges_after = intra_edges_before + col_new
        density_after[col_name] = intra_edges_after / max_edges if max_edges > 0 else 0

        if col_new > 0 or verbose:
            results[col_name] = col_new
            total_new += col_new
            if verbose:
                d_before = density_before[col_name]
                d_after = density_after[col_name]
                avail = len(candidates)
                print(f"  {col_name}: {col_new} new edges "
                      f"(density {d_before:.4f} -> {d_after:.4f}, "
                      f"{avail} candidates above threshold)")

    # Compute aggregate intra-density (same formula as phi_metric.py)
    avg_density = (sum(density_after.values()) / len(density_after)
                   if density_after else 0)
    # Phi normalizes density as min(1.0, raw_density * 5)
    phi_normalized = min(1.0, avg_density * 5)

    if verbose:
        prefix = "(DRY RUN) " if dry_run else ""
        print(f"\nIntra-linker {prefix}complete: "
              f"{total_new} new edges across {sum(1 for v in results.values() if v > 0)} collections")
        print(f"Avg raw intra-density: {avg_density:.4f}")
        print(f"Phi intra_density component (raw*5, capped 1.0): {phi_normalized:.4f}")
        if phi_normalized < 0.50:
            deficit = 0.50 - phi_normalized
            print(f"  Target 0.50 — deficit: {deficit:.4f}. "
                  f"Run again or increase --cap to close the gap.")
        else:
            print(f"  Target 0.50 — ACHIEVED ({phi_normalized:.4f})")

    return {
        "new_edges": total_new,
        "per_collection": results,
        "density_before": density_before,
        "density_after": density_after,
        "avg_density_raw": round(avg_density, 4),
        "phi_intra_density": round(phi_normalized, 4),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Intra-collection linker")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP,
                        help=f"Max new edges per collection (default {DEFAULT_CAP})")
    parser.add_argument("--threshold", type=float, default=COSINE_THRESHOLD,
                        help=f"Cosine similarity threshold (default {COSINE_THRESHOLD})")
    args = parser.parse_args()

    result = run_intra_linker(
        cap_per_collection=args.cap,
        dry_run=args.dry_run,
        threshold=args.threshold,
    )
    print(f"\nTotal new intra edges: {result['new_edges']}")
    print(f"Phi intra_density: {result['phi_intra_density']}")

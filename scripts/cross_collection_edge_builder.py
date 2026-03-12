#!/usr/bin/env python3
"""
Cross-Collection Edge Builder — Bulk-create graph edges between semantically
similar memories across different collections.

Goal: Raise cross_collection_connectivity (currently ~0.49) to 0.55+ by adding
targeted cross-collection graph edges WITHOUT creating new memories.

Strategy:
1. For each collection, sample memories (up to N)
2. Query every OTHER collection for near matches (cosine distance < threshold)
3. Collect all candidate edges
4. Deduplicate against existing edges
5. Bulk-insert into both JSON graph and SQLite store

Usage:
    python3 scripts/cross_collection_edge_builder.py              # Full run
    python3 scripts/cross_collection_edge_builder.py --dry-run    # Preview only
    python3 scripts/cross_collection_edge_builder.py --threshold 1.2  # Custom distance threshold
"""

import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain as _brain


def build_existing_edge_set(brain):
    """Build a set of existing (from, to) pairs for fast dedup."""
    existing = set()
    for e in brain.graph.get("edges", []):
        f, t = e["from"], e["to"]
        existing.add((f, t))
        existing.add((t, f))  # bidirectional check
    return existing


def find_cross_collection_candidates(brain, sample_per_col=100, distance_threshold=1.3, n_results=3):
    """Find candidate cross-collection edges.

    For each collection, sample memories and query all other collections.
    Returns list of (from_id, to_id, from_col, to_col, distance) tuples.
    """
    collections = {}
    for name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            collections[name] = col

    candidates = []
    col_names = list(collections.keys())

    for src_name in col_names:
        src_col = collections[src_name]
        src_count = src_col.count()
        limit = min(sample_per_col, src_count)

        try:
            src_data = src_col.get(limit=limit, include=["documents"])
        except TypeError:
            # Older ChromaDB versions may not support include= on .get()
            src_data = src_col.get(limit=limit)
        src_ids = src_data.get("ids", [])
        src_docs = src_data.get("documents", [])

        for mid, doc in zip(src_ids, src_docs):
            if not doc or len(doc) < 10:
                continue
            # Skip bridge/mirror memories
            if mid.startswith(("bridge_", "sbridge_", "boost_", "tm_")):
                continue

            for dst_name in col_names:
                if dst_name == src_name:
                    continue
                dst_col = collections[dst_name]
                try:
                    r = dst_col.query(
                        query_texts=[doc],
                        n_results=n_results,
                        include=["distances"]
                    )
                    if not (r["ids"] and r["ids"][0]):
                        continue
                    for i in range(len(r["ids"][0])):
                        rid = r["ids"][0][i]
                        dist = r["distances"][0][i]
                        if dist < distance_threshold:
                            candidates.append((mid, rid, src_name, dst_name, dist))
                except Exception:
                    continue

    return candidates


def bulk_add_cross_edges(brain, candidates, existing_edges, dry_run=False):
    """Add cross-collection edges in bulk, skipping existing ones.

    Returns count of new edges added.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    new_edges = []
    seen = set()

    for from_id, to_id, from_col, to_col, dist in candidates:
        # Skip if edge already exists
        if (from_id, to_id) in existing_edges:
            continue
        # Skip duplicate candidates
        pair_key = (min(from_id, to_id), max(from_id, to_id))
        if pair_key in seen:
            continue
        seen.add(pair_key)

        new_edges.append({
            "from_id": from_id,
            "to_id": to_id,
            "from_col": from_col,
            "to_col": to_col,
            "dist": dist,
        })

    if dry_run:
        return len(new_edges), new_edges[:10]

    if not new_edges:
        return 0, []

    # Batch add to JSON graph
    graph = brain.graph
    nodes = graph.setdefault("nodes", {})
    edges = graph.setdefault("edges", [])

    for e in new_edges:
        if e["from_id"] not in nodes:
            nodes[e["from_id"]] = {
                "collection": e["from_col"],
                "added_at": now_str,
            }
        if e["to_id"] not in nodes:
            nodes[e["to_id"]] = {
                "collection": e["to_col"],
                "added_at": now_str,
            }
        edges.append({
            "from": e["from_id"],
            "to": e["to_id"],
            "type": "cross_collection",
            "created_at": now_str,
            "source_collection": e["from_col"],
            "target_collection": e["to_col"],
        })

    # Save JSON graph via brain's atomic save (handles edge count header + locking)
    brain._save_graph()
    print(f"  JSON graph saved: {len(edges)} total edges")

    # Bulk add to SQLite if available
    sqlite_store = getattr(brain, '_sqlite_store', None)
    if sqlite_store is not None:
        sqlite_edges = []
        for e in new_edges:
            sqlite_edges.append((
                e["from_id"],
                e["to_id"],
                "cross_collection",
                now_str,
                e["from_col"],
                e["to_col"],
                1.0,  # weight
            ))
        try:
            # Also add nodes
            sqlite_nodes = []
            added_nodes = set()
            for e in new_edges:
                if e["from_id"] not in added_nodes:
                    sqlite_nodes.append((e["from_id"], e["from_col"], now_str, 0))
                    added_nodes.add(e["from_id"])
                if e["to_id"] not in added_nodes:
                    sqlite_nodes.append((e["to_id"], e["to_col"], now_str, 0))
                    added_nodes.add(e["to_id"])
            if sqlite_nodes:
                sqlite_store.bulk_add_nodes(sqlite_nodes)
            sqlite_store.bulk_add_edges(sqlite_edges)
            print(f"  SQLite: {len(sqlite_edges)} edges added")
        except Exception as ex:
            print(f"  Warning: SQLite bulk add failed: {ex}")

    return len(new_edges), new_edges[:5]


def graph_transitive_expand(brain, dry_run=False, max_new_edges=20000):
    """Fast cross-collection edge expansion using graph traversal (no embedding queries).

    Strategy: For each existing cross-collection edge (A in col1 <-> B in col2),
    find A's same-collection neighbors and B's same-collection neighbors.
    Add cross-collection edges between A's neighbors and B, and B's neighbors and A.

    This is 1-hop transitive closure for cross-collection connectivity.
    Pure graph operations, extremely fast.
    """
    print("=== Graph Transitive Cross-Collection Expansion ===")

    edges = brain.graph.get("edges", [])
    nodes = brain.graph.get("nodes", {})

    # Build node -> collection mapping
    node_col = {}
    for nid, ndata in nodes.items():
        col = ndata.get("collection", "")
        if col:
            node_col[nid] = col

    # Also infer from collection data
    for col_name, col in brain.collections.items():
        ids = col.get().get("ids", [])
        for mid in ids:
            node_col[mid] = col_name

    # Build adjacency and identify existing cross-collection edges
    adj = defaultdict(set)
    existing_pairs = set()
    cross_edges_list = []

    for e in edges:
        f, t = e["from"], e["to"]
        adj[f].add(t)
        adj[t].add(f)
        existing_pairs.add((f, t))
        existing_pairs.add((t, f))

        f_col = node_col.get(f, "")
        t_col = node_col.get(t, "")
        if f_col and t_col and f_col != t_col:
            cross_edges_list.append((f, t, f_col, t_col))

    cross_count = len(cross_edges_list)
    total = len(edges)
    print(f"Current: {cross_count} cross-collection edge directions, {total} total edges")
    print(f"Current ratio: {cross_count / total:.4f}" if total else "No edges")

    # For each cross-collection edge, expand to neighbors
    new_candidates = []
    seen = set()

    for a, b, a_col, b_col in cross_edges_list:
        # A's neighbors in same collection -> connect to B
        for a_neighbor in adj[a]:
            if node_col.get(a_neighbor) == a_col and a_neighbor != b:
                pair = (min(a_neighbor, b), max(a_neighbor, b))
                n_col = node_col.get(a_neighbor, "")
                if n_col and n_col != b_col and pair not in seen and (a_neighbor, b) not in existing_pairs:
                    seen.add(pair)
                    new_candidates.append((a_neighbor, b, n_col, b_col))

        # B's neighbors in same collection -> connect to A
        for b_neighbor in adj[b]:
            if node_col.get(b_neighbor) == b_col and b_neighbor != a:
                pair = (min(a, b_neighbor), max(a, b_neighbor))
                n_col = node_col.get(b_neighbor, "")
                if n_col and n_col != a_col and pair not in seen and (a, b_neighbor) not in existing_pairs:
                    seen.add(pair)
                    new_candidates.append((a, b_neighbor, a_col, n_col))

        if len(new_candidates) >= max_new_edges:
            break

    new_candidates = new_candidates[:max_new_edges]
    print(f"Found {len(new_candidates)} new cross-collection edges via transitive expansion")

    if dry_run:
        # Show distribution
        pair_counts = defaultdict(int)
        for _, _, fc, tc in new_candidates:
            pair_key = " <-> ".join(sorted([fc, tc]))
            pair_counts[pair_key] += 1
        for pk in sorted(pair_counts, key=pair_counts.get, reverse=True)[:10]:
            print(f"  {pk}: {pair_counts[pk]}")
        return len(new_candidates)

    if not new_candidates:
        print("No new edges to add.")
        return 0

    # Bulk add to JSON graph
    now_str = datetime.now(timezone.utc).isoformat()
    graph = brain.graph
    g_nodes = graph.setdefault("nodes", {})
    g_edges = graph.setdefault("edges", [])

    for from_id, to_id, from_col, to_col in new_candidates:
        if from_id not in g_nodes:
            g_nodes[from_id] = {"collection": from_col, "added_at": now_str}
        if to_id not in g_nodes:
            g_nodes[to_id] = {"collection": to_col, "added_at": now_str}
        g_edges.append({
            "from": from_id,
            "to": to_id,
            "type": "transitive_cross",
            "created_at": now_str,
            "source_collection": from_col,
            "target_collection": to_col,
        })

    # Save JSON graph via brain's atomic save (handles edge count header + locking)
    brain._save_graph()
    print(f"  JSON graph saved: {len(g_edges)} total edges")

    # Bulk add to SQLite
    sqlite_store = getattr(brain, '_sqlite_store', None)
    if sqlite_store is not None:
        sqlite_edges = []
        sqlite_nodes_set = set()
        sqlite_nodes = []
        for from_id, to_id, from_col, to_col in new_candidates:
            sqlite_edges.append((from_id, to_id, "transitive_cross", now_str, from_col, to_col, 1.0))
            if from_id not in sqlite_nodes_set:
                sqlite_nodes.append((from_id, from_col, now_str, 0))
                sqlite_nodes_set.add(from_id)
            if to_id not in sqlite_nodes_set:
                sqlite_nodes.append((to_id, to_col, now_str, 0))
                sqlite_nodes_set.add(to_id)
        try:
            if sqlite_nodes:
                sqlite_store.bulk_add_nodes(sqlite_nodes)
            sqlite_store.bulk_add_edges(sqlite_edges)
            print(f"  SQLite: {len(sqlite_edges)} edges added")
        except Exception as ex:
            print(f"  Warning: SQLite bulk add failed: {ex}")

    # Verify
    new_total = len(g_edges)
    # Count cross edges in the updated graph
    new_cross = 0
    for e in g_edges:
        fc = e.get("source_collection", "")
        tc = e.get("target_collection", "")
        if fc and tc and fc != tc:
            new_cross += 1
    ratio = new_cross / new_total if new_total > 0 else 0
    print(f"\nAfter: {new_cross} cross / {new_total} total = {ratio:.4f}")

    return len(new_candidates)


def run(sample_per_col=100, distance_threshold=1.3, n_results=3, dry_run=False, mode="transitive", max_edges=20000):
    """Main entry point."""
    brain = _brain

    if mode == "transitive":
        return graph_transitive_expand(brain, dry_run=dry_run, max_new_edges=max_edges)

    print("=== Cross-Collection Edge Builder (Embedding Mode) ===")
    print(f"Config: sample={sample_per_col}/col, dist_threshold={distance_threshold}, n_results={n_results}")

    # Current state
    edges = brain.graph.get("edges", [])
    cross = sum(1 for e in edges
                if e.get("source_collection") != e.get("target_collection")
                and e.get("source_collection") and e.get("target_collection"))
    total = len(edges)
    print(f"Current: {cross} cross / {total} total = {cross/total:.4f}" if total > 0 else "No edges")

    print("\nScanning for cross-collection candidates...")
    existing = build_existing_edge_set(brain)
    print(f"  Existing edge pairs: {len(existing)//2}")

    candidates = find_cross_collection_candidates(
        brain, sample_per_col=sample_per_col,
        distance_threshold=distance_threshold, n_results=n_results
    )
    print(f"  Raw candidates: {len(candidates)}")

    # Distribution
    pair_counts = defaultdict(int)
    for _, _, fc, tc, _ in candidates:
        pair_key = " <-> ".join(sorted([fc, tc]))
        pair_counts[pair_key] += 1
    print(f"  Across {len(pair_counts)} collection pairs")

    count, sample = bulk_add_cross_edges(brain, candidates, existing, dry_run=dry_run)
    print(f"\n{'Would add' if dry_run else 'Added'}: {count} new cross-collection edges")

    if not dry_run and count > 0:
        # Verify
        edges_after = brain.graph.get("edges", [])
        cross_after = sum(1 for e in edges_after
                         if e.get("source_collection") != e.get("target_collection")
                         and e.get("source_collection") and e.get("target_collection"))
        total_after = len(edges_after)
        ratio = cross_after / total_after if total_after > 0 else 0
        print(f"After: {cross_after} cross / {total_after} total = {ratio:.4f}")
        target_ratio = 0.55
        if ratio < target_ratio:
            needed = int((target_ratio * total_after - cross_after) / (1 - target_ratio))
            print(f"  Still need ~{needed} more cross edges for {target_ratio}")

    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cross-Collection Edge Builder")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=["transitive", "embedding"], default="transitive",
                        help="Mode: transitive (fast graph-based) or embedding (slow query-based)")
    parser.add_argument("--sample", type=int, default=100, help="Memories to sample per collection (embedding mode)")
    parser.add_argument("--threshold", type=float, default=1.3, help="Max cosine distance (embedding mode)")
    parser.add_argument("--n-results", type=int, default=3, help="Matches per query (embedding mode)")
    parser.add_argument("--max-edges", type=int, default=20000, help="Max new edges to add (transitive mode)")
    args = parser.parse_args()

    run(sample_per_col=args.sample, distance_threshold=args.threshold,
        n_results=args.n_results, dry_run=args.dry_run, mode=args.mode,
        max_edges=args.max_edges)

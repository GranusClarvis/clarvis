#!/usr/bin/env python3
"""
Graph Compaction — 04:30 UTC daily cron
Maintains graph health: removes orphan edges, deduplicates, backfills nodes.

Steps:
  1. Remove orphan edges (edges referencing memory IDs not in any ChromaDB collection)
  2. Deduplicate edges (same from/to/type)
  3. Backfill graph nodes (via brain.backfill_graph_nodes())
  4. Report health metrics
"""
import fcntl
import json
import os
import sys
import time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from brain import get_brain


def _save_graph_atomic(brain):
    """Write graph directly, bypassing _save_graph()'s read-merge logic.

    brain._save_graph() merges on-disk edges back in to handle concurrent
    additions.  That defeats intentional deletions during compaction.
    We use the same atomic-write + exclusive-lock pattern but skip the merge.
    """
    tmp_path = brain.graph_file + ".tmp"
    with open(tmp_path, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(brain.graph, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(tmp_path, brain.graph_file)


def _collect_all_memory_ids(brain):
    """Build set of all memory IDs across all ChromaDB collections."""
    all_ids = set()
    for name, col in brain.collections.items():
        try:
            result = col.get(include=[])
            all_ids.update(result["ids"])
        except Exception as e:
            print(f"  WARN: Could not read collection {name}: {e}")
    return all_ids


def remove_orphan_edges(brain, all_ids, dry_run=False):
    """Remove edges where from/to ID doesn't exist in any ChromaDB collection."""
    edges = brain.graph.get("edges", [])
    keep = []
    removed = 0
    for edge in edges:
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if from_id in all_ids and to_id in all_ids:
            keep.append(edge)
        else:
            removed += 1
            if dry_run:
                print(f"  [dry-run] would remove: {from_id} -> {to_id} ({edge.get('type', '?')})")

    if not dry_run and removed > 0:
        brain.graph["edges"] = keep

    return removed


def deduplicate_edges(brain, dry_run=False):
    """Remove duplicate edges (same from, to, type triple). Keep earliest."""
    edges = brain.graph.get("edges", [])
    seen = set()
    unique = []
    dupes = 0
    for edge in edges:
        key = (edge.get("from", ""), edge.get("to", ""), edge.get("type", ""))
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
            unique.append(edge)

    if not dry_run and dupes > 0:
        brain.graph["edges"] = unique

    return dupes


def remove_orphan_nodes(brain, all_ids, dry_run=False):
    """Remove nodes not referenced by any edge and not in any collection."""
    edge_ids = set()
    for e in brain.graph.get("edges", []):
        edge_ids.add(e.get("from", ""))
        edge_ids.add(e.get("to", ""))
    edge_ids.discard("")

    nodes = brain.graph.get("nodes", {})
    orphan_nodes = [nid for nid in nodes if nid not in edge_ids and nid not in all_ids]
    removed = len(orphan_nodes)

    if not dry_run and removed > 0:
        for nid in orphan_nodes:
            del brain.graph["nodes"][nid]

    return removed


def health_metrics(brain):
    """Return a dict of graph health metrics."""
    s = brain.stats()
    edges = brain.graph.get("edges", [])
    nodes = brain.graph.get("nodes", {})

    # Edge type distribution
    type_counts = {}
    for e in edges:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Cross-collection vs intra-collection
    cross = sum(1 for e in edges
                if e.get("source_collection") and e.get("target_collection")
                and e["source_collection"] != e["target_collection"])
    intra = len(edges) - cross

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_memories": s["total_memories"],
        "edge_types": type_counts,
        "cross_collection_edges": cross,
        "intra_collection_edges": intra,
        "density": round(len(edges) / max(len(nodes), 1), 2),
    }


def run_compaction(dry_run=False):
    """Full compaction pipeline.

    All mutations happen in-memory, then a single atomic write at the end
    bypasses _save_graph()'s read-merge (which would re-add deleted edges).
    """
    t0 = time.time()
    brain = get_brain()
    s_before = brain.stats()
    print(f"Graph before: {s_before['graph_nodes']} nodes, {s_before['graph_edges']} edges")

    # Collect all ChromaDB IDs once (shared by orphan-edge and orphan-node steps)
    all_ids = _collect_all_memory_ids(brain)
    print(f"ChromaDB memories scanned: {len(all_ids)}")

    # 1. Remove orphan edges
    orphan_edges = remove_orphan_edges(brain, all_ids, dry_run=dry_run)
    print(f"Orphan edges removed: {orphan_edges}")

    # 2. Deduplicate edges
    dupes = deduplicate_edges(brain, dry_run=dry_run)
    print(f"Duplicate edges removed: {dupes}")

    # 3. Backfill missing nodes — inline to avoid brain._save_graph() merge
    backfilled = 0
    from datetime import datetime, timezone
    for edge in brain.graph.get("edges", []):
        for key in ("from", "to"):
            node_id = edge.get(key)
            if node_id and node_id not in brain.graph["nodes"]:
                col_key = "source" if key == "from" else "target"
                collection = edge.get(f"{col_key}_collection")
                brain.graph["nodes"][node_id] = {
                    "collection": collection or brain._infer_collection(node_id),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "backfilled": True,
                }
                backfilled += 1
    print(f"Nodes backfilled: {backfilled}")

    # 4. Remove orphan nodes (unreferenced by edges AND not in any collection)
    orphan_nodes = remove_orphan_nodes(brain, all_ids, dry_run=dry_run)
    print(f"Orphan nodes removed: {orphan_nodes}")

    # Single atomic write — bypass merge so deletions stick
    if not dry_run and (orphan_edges + dupes + backfilled + orphan_nodes) > 0:
        _save_graph_atomic(brain)

    # 5. Health metrics
    metrics = health_metrics(brain)
    elapsed = round(time.time() - t0, 1)
    print("\n=== Graph Health ===")
    print(f"Nodes: {metrics['total_nodes']}, Edges: {metrics['total_edges']}, Memories: {metrics['total_memories']}")
    print(f"Density (edges/node): {metrics['density']}")
    print(f"Cross-collection: {metrics['cross_collection_edges']}, Intra-collection: {metrics['intra_collection_edges']}")
    for t, c in sorted(metrics["edge_types"].items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print(f"\nCompaction completed in {elapsed}s")

    return {
        "orphan_edges_removed": orphan_edges,
        "duplicates_removed": dupes,
        "nodes_backfilled": backfilled,
        "orphan_nodes_removed": orphan_nodes,
        "health": metrics,
        "elapsed_s": elapsed,
    }


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY RUN (no changes) ===\n")
    run_compaction(dry_run=dry)

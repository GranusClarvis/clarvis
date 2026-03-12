#!/usr/bin/env python3
"""
Graph Compaction — 04:30 UTC daily cron
Maintains graph health: removes orphan edges, deduplicates, backfills nodes.

Steps:
  1. Remove orphan edges (edges referencing memory IDs not in any ChromaDB collection)
  2. Deduplicate edges (same from/to/type)
  3. Backfill graph nodes (via brain.backfill_graph_nodes())
  4. Report health metrics

Backend-aware: when CLARVIS_GRAPH_BACKEND=sqlite, compaction runs via SQL
(no need to load the full JSON graph into memory).
"""
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from brain import get_brain


# ====================================================================
# JSON backend helpers (legacy)
# ====================================================================

def _save_graph_atomic(brain):
    """Write graph directly, bypassing _save_graph()'s read-merge logic.

    brain._save_graph() merges on-disk edges back in to handle concurrent
    additions.  That defeats intentional deletions during compaction.
    We use the same atomic-write + exclusive-lock pattern but skip the merge.
    """
    tmp_path = f"{brain.graph_file}.tmp.{os.getpid()}"
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


# ====================================================================
# SQLite backend — compaction via SQL (avoids loading full JSON graph)
# ====================================================================

def _sqlite_remove_orphan_edges(store, all_ids, dry_run=False):
    """Remove edges referencing nodes not in any ChromaDB collection (SQL)."""
    conn = store._conn
    # Get all node IDs referenced by edges
    rows = conn.execute(
        "SELECT DISTINCT from_id FROM edges UNION SELECT DISTINCT to_id FROM edges"
    ).fetchall()
    edge_node_ids = {r[0] for r in rows}
    orphan_ids = edge_node_ids - all_ids
    if not orphan_ids:
        return 0

    if dry_run:
        count = 0
        for oid in orphan_ids:
            n = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE from_id = ? OR to_id = ?",
                (oid, oid),
            ).fetchone()[0]
            count += n
        return count

    # Delete edges referencing orphan IDs in batches
    removed = 0
    batch = list(orphan_ids)
    # SQLite max variable limit is ~999, batch accordingly
    for i in range(0, len(batch), 500):
        chunk = batch[i:i+500]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            f"DELETE FROM edges WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
            chunk + chunk,
        )
        removed += cur.rowcount
    conn.commit()
    return removed


def _sqlite_remove_orphan_nodes(store, all_ids, dry_run=False):
    """Remove nodes not referenced by any edge and not in any collection (SQL)."""
    conn = store._conn
    # Nodes referenced by edges
    rows = conn.execute(
        "SELECT DISTINCT from_id FROM edges UNION SELECT DISTINCT to_id FROM edges"
    ).fetchall()
    edge_node_ids = {r[0] for r in rows}

    # All node IDs in the nodes table
    rows = conn.execute("SELECT id FROM nodes").fetchall()
    all_node_ids = {r[0] for r in rows}

    orphan_nodes = all_node_ids - edge_node_ids - all_ids
    if not orphan_nodes or dry_run:
        return len(orphan_nodes)

    batch = list(orphan_nodes)
    removed = 0
    for i in range(0, len(batch), 500):
        chunk = batch[i:i+500]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", chunk)
        removed += cur.rowcount
    conn.commit()
    return removed


def _sqlite_backfill_nodes(store, brain, dry_run=False):
    """Register nodes referenced by edges but missing from the nodes table (SQL)."""
    conn = store._conn
    # Find edge endpoints not in nodes table
    rows = conn.execute("""
        SELECT DISTINCT e.from_id, e.source_collection
        FROM edges e LEFT JOIN nodes n ON e.from_id = n.id
        WHERE n.id IS NULL
        UNION
        SELECT DISTINCT e.to_id, e.target_collection
        FROM edges e LEFT JOIN nodes n ON e.to_id = n.id
        WHERE n.id IS NULL
    """).fetchall()

    if not rows or dry_run:
        return len(rows)

    now_str = datetime.now(timezone.utc).isoformat()
    tuples = []
    for r in rows:
        nid = r[0]
        col = r[1] or brain._infer_collection(nid)
        tuples.append((nid, col, now_str, 1))
    store.bulk_add_nodes(tuples)
    return len(tuples)


def _sqlite_health_metrics(store, brain):
    """Return health metrics from SQLite store."""
    s = brain.stats()
    st = store.stats()

    # Cross-collection count
    conn = store._conn
    cross = conn.execute(
        "SELECT COUNT(*) FROM edges "
        "WHERE source_collection IS NOT NULL AND target_collection IS NOT NULL "
        "AND source_collection != target_collection"
    ).fetchone()[0]
    total_edges = st["edges"]
    intra = total_edges - cross

    return {
        "total_nodes": st["nodes"],
        "total_edges": total_edges,
        "total_memories": s["total_memories"],
        "edge_types": st["edge_types"],
        "cross_collection_edges": cross,
        "intra_collection_edges": intra,
        "density": round(total_edges / max(st["nodes"], 1), 2),
    }


def run_compaction_sqlite(brain, dry_run=False):
    """Compaction pipeline using SQL operations on the SQLite graph store."""
    t0 = time.time()
    store = brain._sqlite_store
    print(f"Backend: SQLite ({store.db_path})")

    st = store.stats()
    print(f"Graph before: {st['nodes']} nodes, {st['edges']} edges")

    all_ids = _collect_all_memory_ids(brain)
    print(f"ChromaDB memories scanned: {len(all_ids)}")

    # 1. Remove orphan edges (SQL DELETE)
    orphan_edges = _sqlite_remove_orphan_edges(store, all_ids, dry_run=dry_run)
    print(f"Orphan edges removed: {orphan_edges}")

    # 2. Deduplicate — SQLite UNIQUE constraint prevents dupes, so this is a no-op.
    #    (JSON may still have dupes; they won't be imported on migration.)
    print(f"Duplicate edges removed: 0 (UNIQUE constraint)")

    # 3. Backfill missing nodes
    backfilled = _sqlite_backfill_nodes(store, brain, dry_run=dry_run)
    print(f"Nodes backfilled: {backfilled}")

    # 4. Remove orphan nodes
    orphan_nodes = _sqlite_remove_orphan_nodes(store, all_ids, dry_run=dry_run)
    print(f"Orphan nodes removed: {orphan_nodes}")

    # 5. Health metrics
    metrics = _sqlite_health_metrics(store, brain)
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
        "duplicates_removed": 0,
        "nodes_backfilled": backfilled,
        "orphan_nodes_removed": orphan_nodes,
        "health": metrics,
        "elapsed_s": elapsed,
    }


# ====================================================================
# JSON backend — compaction via in-memory manipulation (original)
# ====================================================================

def run_compaction_json(brain, dry_run=False):
    """Full compaction pipeline for JSON backend.

    All mutations happen in-memory, then a single atomic write at the end
    bypasses _save_graph()'s read-merge (which would re-add deleted edges).
    """
    t0 = time.time()
    print("Backend: JSON")
    s_before = brain.stats()
    print(f"Graph before: {s_before['graph_nodes']} nodes, {s_before['graph_edges']} edges")

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


def run_compaction(dry_run=False):
    """Dispatch to backend-specific compaction pipeline.

    When dual-write is active (backend=sqlite + CLARVIS_GRAPH_DUAL_WRITE=1),
    compact BOTH stores to keep them in sync.  Otherwise compaction only runs
    on SQLite while JSON keeps growing, causing parity drift.
    """
    brain = get_brain()
    if brain._sqlite_store is not None:
        result = run_compaction_sqlite(brain, dry_run=dry_run)
        # Also compact JSON when dual-write is active to prevent drift
        dual_write = os.environ.get("CLARVIS_GRAPH_DUAL_WRITE", "1") != "0"
        if dual_write:
            print("\n--- JSON dual-write compaction (sync) ---")
            run_compaction_json(brain, dry_run=dry_run)
        return result
    return run_compaction_json(brain, dry_run=dry_run)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY RUN (no changes) ===\n")
    run_compaction(dry_run=dry)

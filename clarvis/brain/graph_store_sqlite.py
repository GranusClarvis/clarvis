"""SQLite + WAL graph store — drop-in replacement for JSON graph storage.

Schema mirrors the existing JSON structure (nodes dict + edges list) but uses
SQLite for ACID transactions, indexed lookups, and incremental writes.

Usage:
    from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
    store = GraphStoreSQLite("/path/to/graph.db")
    store.add_node("node1", "clarvis-memories", "2026-03-05T00:00:00+00:00")
    store.add_edge("node1", "node2", "similar_to")
    neighbors = store.get_related("node1", depth=1)
"""

import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone

_log = logging.getLogger("clarvis.brain.graph_store_sqlite")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    collection  TEXT NOT NULL,
    added_at    TEXT NOT NULL,
    backfilled  INTEGER DEFAULT 0,
    metadata    TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id             TEXT NOT NULL,
    to_id               TEXT NOT NULL,
    type                TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    source_collection   TEXT,
    target_collection   TEXT,
    weight              REAL DEFAULT 1.0,
    last_decay          TEXT,
    UNIQUE(from_id, to_id, type)
);

CREATE INDEX IF NOT EXISTS idx_edge_from       ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edge_to         ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edge_type       ON edges(type);
CREATE INDEX IF NOT EXISTS idx_edge_from_type  ON edges(from_id, type);
CREATE INDEX IF NOT EXISTS idx_node_collection ON nodes(collection);
"""


class GraphStoreSQLite:
    """SQLite-backed graph store with WAL mode.

    Thread-safety: each instance holds its own connection. For multi-thread
    use, create one instance per thread or use check_same_thread=False with
    external synchronization.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self):
        """Create schema and set pragmas."""
        c = self._conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=5000")
        c.executescript(_SCHEMA_SQL)
        c.commit()

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def add_node(self, node_id: str, collection: str, added_at: str,
                 backfilled: bool = False, metadata: str | None = None):
        """Insert a node. Ignores if already exists."""
        self._conn.execute(
            "INSERT OR IGNORE INTO nodes (id, collection, added_at, backfilled, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (node_id, collection, added_at, int(backfilled), metadata),
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> dict | None:
        """Return node dict or None."""
        row = self._conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def node_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def remove_node(self, node_id: str) -> int:
        """Remove a node by id. Returns count removed."""
        cur = self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def add_edge(self, from_id: str, to_id: str, edge_type: str, *,
                 created_at: str | None = None,
                 source_collection: str | None = None,
                 target_collection: str | None = None,
                 weight: float = 1.0) -> bool:
        """Insert an edge. Returns True if inserted, False if duplicate.

        Uses INSERT OR IGNORE so duplicates (from_id, to_id, type) are
        silently skipped — no application-level dedup needed.
        """
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO edges "
            "(from_id, to_id, type, created_at, source_collection, target_collection, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (from_id, to_id, edge_type, created_at,
             source_collection, target_collection, weight),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_edges(self, *, from_id: str | None = None,
                  to_id: str | None = None,
                  edge_type: str | None = None) -> list[dict]:
        """Query edges with optional filters."""
        clauses = []
        params = []
        if from_id is not None:
            clauses.append("from_id = ?")
            params.append(from_id)
        if to_id is not None:
            clauses.append("to_id = ?")
            params.append(to_id)
        if edge_type is not None:
            clauses.append("type = ?")
            params.append(edge_type)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM edges{where}", params
        ).fetchall()
        return [dict(r) for r in rows]

    def edge_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    def remove_edges(self, *, from_id: str | None = None,
                     to_id: str | None = None,
                     edge_type: str | None = None,
                     where_sql: str | None = None,
                     params: tuple = ()) -> int:
        """Remove edges matching filters. Returns count removed.

        Either use keyword filters (from_id, to_id, edge_type) OR provide
        raw where_sql + params for advanced queries.
        """
        if where_sql:
            cur = self._conn.execute(
                f"DELETE FROM edges WHERE {where_sql}", params
            )
        else:
            clauses = []
            p = []
            if from_id is not None:
                clauses.append("from_id = ?")
                p.append(from_id)
            if to_id is not None:
                clauses.append("to_id = ?")
                p.append(to_id)
            if edge_type is not None:
                clauses.append("type = ?")
                p.append(edge_type)
            if not clauses:
                return 0  # Safety: refuse to delete all edges with no filter
            cur = self._conn.execute(
                "DELETE FROM edges WHERE " + " AND ".join(clauses), p
            )
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def get_related(self, node_id: str, depth: int = 1) -> list[dict]:
        """Get memories related to a node, traversing up to `depth` hops.

        Returns list of dicts: [{id, relationship, depth}, ...].
        Matches GraphMixin.get_related() return format exactly.
        """
        related = []
        visited = set()

        def traverse(nid: str, current_depth: int):
            if current_depth > depth or nid in visited:
                return
            visited.add(nid)

            # Outgoing edges
            rows = self._conn.execute(
                "SELECT to_id, type FROM edges WHERE from_id = ?", (nid,)
            ).fetchall()
            for row in rows:
                target = row["to_id"]
                related.append({
                    "id": target,
                    "relationship": row["type"],
                    "depth": current_depth,
                })
                traverse(target, current_depth + 1)

            # Incoming edges (inverse)
            rows = self._conn.execute(
                "SELECT from_id, type FROM edges WHERE to_id = ?", (nid,)
            ).fetchall()
            for row in rows:
                source = row["from_id"]
                related.append({
                    "id": source,
                    "relationship": f"inverse-{row['type']}",
                    "depth": current_depth,
                })
                traverse(source, current_depth + 1)

        traverse(node_id, 1)
        return related

    def neighbors(self, node_id: str) -> list[dict]:
        """Get direct neighbors (depth=1). Convenience alias."""
        return self.get_related(node_id, depth=1)

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def decay_edges(self, half_life_days: float = 30, prune_below: float = 0.02,
                    decay_types: set | None = None,
                    dry_run: bool = False) -> dict:
        """Apply exponential age decay to edges and prune weak ones.

        Matches GraphMixin.decay_edges() return format.
        """
        if decay_types is None:
            decay_types = {"hebbian_association"}

        now = datetime.now(timezone.utc)
        placeholders = ",".join("?" for _ in decay_types)
        rows = self._conn.execute(
            f"SELECT id, created_at, weight FROM edges WHERE type IN ({placeholders})",
            list(decay_types),
        ).fetchall()

        decayed = 0
        pruned = 0
        weights_after = []
        to_prune = []
        to_update = []

        for row in rows:
            created_str = row["created_at"]
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                age_days = (now - created).total_seconds() / 86400.0
            except (ValueError, TypeError):
                age_days = 0.0

            current_weight = row["weight"] if row["weight"] is not None else 1.0
            decay_factor = math.pow(2, -age_days / half_life_days)
            new_weight = current_weight * decay_factor

            if new_weight < prune_below:
                pruned += 1
                to_prune.append(row["id"])
            else:
                decayed += 1
                weights_after.append(new_weight)
                to_update.append((round(new_weight, 6), now.isoformat(), row["id"]))

        total_before = self.edge_count()

        if not dry_run and (to_prune or to_update):
            if to_update:
                self._conn.executemany(
                    "UPDATE edges SET weight = ?, last_decay = ? WHERE id = ?",
                    to_update,
                )
            if to_prune:
                self._conn.executemany(
                    "DELETE FROM edges WHERE id = ?",
                    [(eid,) for eid in to_prune],
                )
            self._conn.commit()

        total_after = total_before - (len(to_prune) if not dry_run else 0)
        avg_weight = sum(weights_after) / len(weights_after) if weights_after else 0.0

        return {
            "decayed": decayed,
            "pruned": pruned,
            "total_before": total_before,
            "total_after": total_after,
            "avg_weight": round(avg_weight, 4),
        }

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_add_nodes(self, nodes: list[tuple]):
        """Bulk insert nodes. Each tuple: (id, collection, added_at, backfilled).

        Uses executemany + INSERT OR IGNORE for speed.
        """
        self._conn.executemany(
            "INSERT OR IGNORE INTO nodes (id, collection, added_at, backfilled) "
            "VALUES (?, ?, ?, ?)",
            nodes,
        )
        self._conn.commit()

    def bulk_add_edges(self, edges: list[tuple]):
        """Bulk insert edges. Each tuple:
        (from_id, to_id, type, created_at, source_collection, target_collection, weight).

        Uses executemany + INSERT OR IGNORE for speed. Wraps in a single
        transaction for atomicity.
        """
        self._conn.executemany(
            "INSERT OR IGNORE INTO edges "
            "(from_id, to_id, type, created_at, source_collection, target_collection, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            edges,
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Stats & integrity
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return graph statistics."""
        node_count = self.node_count()
        edge_count = self.edge_count()

        # Edge type distribution
        rows = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM edges GROUP BY type ORDER BY cnt DESC"
        ).fetchall()
        edge_types = {r["type"]: r["cnt"] for r in rows}

        # Node collection distribution
        rows = self._conn.execute(
            "SELECT collection, COUNT(*) as cnt FROM nodes GROUP BY collection ORDER BY cnt DESC"
        ).fetchall()
        node_collections = {r["collection"]: r["cnt"] for r in rows}

        return {
            "nodes": node_count,
            "edges": edge_count,
            "edge_types": edge_types,
            "node_collections": node_collections,
            "db_path": self.db_path,
            "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
        }

    def integrity_check(self) -> bool:
        """Run PRAGMA integrity_check. Returns True if OK."""
        result = self._conn.execute("PRAGMA integrity_check").fetchone()
        ok = result[0] == "ok"
        if not ok:
            _log.error("SQLite integrity check failed: %s", result[0])
        return ok

    def backup(self, dst_path: str):
        """Hot backup using SQLite's online backup API."""
        dst = sqlite3.connect(dst_path)
        try:
            self._conn.backup(dst)
        finally:
            dst.close()
        _log.info("Graph backup written to %s", dst_path)

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def import_from_json(self, json_path: str) -> dict:
        """Import nodes and edges from a relationships.json file.

        Returns dict with counts: {nodes_imported, edges_imported, duplicates_skipped}.
        """
        with open(json_path, "r") as f:
            data = json.load(f)

        nodes = data.get("nodes", {})
        edges = data.get("edges", [])

        # Prepare node tuples
        node_tuples = []
        for nid, ndata in nodes.items():
            node_tuples.append((
                nid,
                ndata.get("collection", "unknown"),
                ndata.get("added_at", datetime.now(timezone.utc).isoformat()),
                int(ndata.get("backfilled", False)),
            ))

        # Prepare edge tuples
        edge_tuples = []
        for e in edges:
            edge_tuples.append((
                e["from"],
                e["to"],
                e.get("type", "unknown"),
                e.get("created_at", datetime.now(timezone.utc).isoformat()),
                e.get("source_collection"),
                e.get("target_collection"),
                e.get("weight", 1.0),
            ))

        # Bulk insert in a single transaction
        nodes_before = self.node_count()
        edges_before = self.edge_count()

        self._conn.executemany(
            "INSERT OR IGNORE INTO nodes (id, collection, added_at, backfilled) "
            "VALUES (?, ?, ?, ?)",
            node_tuples,
        )
        self._conn.executemany(
            "INSERT OR IGNORE INTO edges "
            "(from_id, to_id, type, created_at, source_collection, target_collection, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            edge_tuples,
        )
        self._conn.commit()

        nodes_after = self.node_count()
        edges_after = self.edge_count()

        return {
            "nodes_imported": nodes_after - nodes_before,
            "edges_imported": edges_after - edges_before,
            "nodes_in_json": len(node_tuples),
            "edges_in_json": len(edge_tuples),
            "duplicates_skipped": len(edge_tuples) - (edges_after - edges_before),
        }

    def export_json(self, path: str):
        """Export the graph to JSON format (same schema as relationships.json)."""
        nodes = {}
        for row in self._conn.execute("SELECT * FROM nodes").fetchall():
            nodes[row["id"]] = {
                "collection": row["collection"],
                "added_at": row["added_at"],
            }
            if row["backfilled"]:
                nodes[row["id"]]["backfilled"] = True

        edges = []
        for row in self._conn.execute("SELECT * FROM edges ORDER BY id").fetchall():
            edge = {
                "from": row["from_id"],
                "to": row["to_id"],
                "type": row["type"],
                "created_at": row["created_at"],
            }
            if row["source_collection"]:
                edge["source_collection"] = row["source_collection"]
            if row["target_collection"]:
                edge["target_collection"] = row["target_collection"]
            if row["weight"] is not None and row["weight"] != 1.0:
                edge["weight"] = row["weight"]
            if row["last_decay"]:
                edge["last_decay"] = row["last_decay"]
            edges.append(edge)

        data = {"nodes": nodes, "edges": edges, "_edge_count": len(edges)}

        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(path) or ".", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

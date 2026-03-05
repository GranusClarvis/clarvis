"""Tests for GraphStoreSQLite — schema, insert, query, migration."""

import json
import os
import tempfile

import pytest

from clarvis.brain.graph_store_sqlite import GraphStoreSQLite


@pytest.fixture
def tmp_db():
    """Create a GraphStoreSQLite in a temp directory."""
    with tempfile.TemporaryDirectory(prefix="clarvis_graph_test_") as tmpdir:
        db_path = os.path.join(tmpdir, "graph.db")
        store = GraphStoreSQLite(db_path)
        yield store, tmpdir
        store.close()


@pytest.fixture
def sample_json(tmp_path):
    """Create a sample relationships.json for migration tests."""
    data = {
        "nodes": {
            "clarvis-memories_20260301_100000": {
                "collection": "clarvis-memories",
                "added_at": "2026-03-01T10:00:00+00:00",
            },
            "clarvis-learnings_20260301_100001": {
                "collection": "clarvis-learnings",
                "added_at": "2026-03-01T10:00:01+00:00",
            },
            "clarvis-goals_20260301_100002": {
                "collection": "clarvis-goals",
                "added_at": "2026-03-01T10:00:02+00:00",
                "backfilled": True,
            },
        },
        "edges": [
            {
                "from": "clarvis-memories_20260301_100000",
                "to": "clarvis-learnings_20260301_100001",
                "type": "similar_to",
                "created_at": "2026-03-01T10:00:05+00:00",
                "source_collection": "clarvis-memories",
                "target_collection": "clarvis-learnings",
            },
            {
                "from": "clarvis-memories_20260301_100000",
                "to": "clarvis-goals_20260301_100002",
                "type": "cross_collection",
                "created_at": "2026-03-01T10:00:06+00:00",
                "source_collection": "clarvis-memories",
                "target_collection": "clarvis-goals",
            },
            {
                "from": "clarvis-learnings_20260301_100001",
                "to": "clarvis-goals_20260301_100002",
                "type": "hebbian_association",
                "created_at": "2026-03-01T10:00:07+00:00",
                "weight": 0.8,
            },
        ],
        "_edge_count": 3,
    }
    path = str(tmp_path / "relationships.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path, data


# ====================================================================
# Schema tests
# ====================================================================

class TestSchema:
    def test_creates_tables(self, tmp_db):
        store, _ = tmp_db
        # Verify tables exist
        tables = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "nodes" in table_names
        assert "edges" in table_names

    def test_wal_mode_enabled(self, tmp_db):
        store, _ = tmp_db
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_indices_created(self, tmp_db):
        store, _ = tmp_db
        indices = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        idx_names = {i["name"] for i in indices}
        assert "idx_edge_from" in idx_names
        assert "idx_edge_to" in idx_names
        assert "idx_edge_type" in idx_names
        assert "idx_edge_from_type" in idx_names
        assert "idx_node_collection" in idx_names

    def test_integrity_check_passes(self, tmp_db):
        store, _ = tmp_db
        assert store.integrity_check() is True


# ====================================================================
# Node tests
# ====================================================================

class TestNodes:
    def test_add_and_get_node(self, tmp_db):
        store, _ = tmp_db
        store.add_node("n1", "clarvis-memories", "2026-03-01T00:00:00+00:00")
        node = store.get_node("n1")
        assert node is not None
        assert node["id"] == "n1"
        assert node["collection"] == "clarvis-memories"
        assert node["backfilled"] == 0

    def test_add_node_idempotent(self, tmp_db):
        store, _ = tmp_db
        store.add_node("n1", "clarvis-memories", "2026-03-01T00:00:00+00:00")
        store.add_node("n1", "clarvis-memories", "2026-03-02T00:00:00+00:00")  # duplicate
        assert store.node_count() == 1

    def test_backfilled_flag(self, tmp_db):
        store, _ = tmp_db
        store.add_node("n1", "clarvis-goals", "2026-03-01T00:00:00+00:00", backfilled=True)
        node = store.get_node("n1")
        assert node["backfilled"] == 1

    def test_node_not_found(self, tmp_db):
        store, _ = tmp_db
        assert store.get_node("nonexistent") is None


# ====================================================================
# Edge tests
# ====================================================================

class TestEdges:
    def test_add_edge(self, tmp_db):
        store, _ = tmp_db
        inserted = store.add_edge("a", "b", "similar_to")
        assert inserted is True
        assert store.edge_count() == 1

    def test_add_edge_duplicate_ignored(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        inserted = store.add_edge("a", "b", "similar_to")  # duplicate
        assert inserted is False
        assert store.edge_count() == 1

    def test_different_types_not_duplicate(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("a", "b", "cross_collection")
        assert store.edge_count() == 2

    def test_get_edges_by_from(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("a", "c", "cross_collection")
        store.add_edge("d", "a", "similar_to")
        edges = store.get_edges(from_id="a")
        assert len(edges) == 2

    def test_get_edges_by_type(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("a", "c", "cross_collection")
        edges = store.get_edges(edge_type="similar_to")
        assert len(edges) == 1
        assert edges[0]["from_id"] == "a"
        assert edges[0]["to_id"] == "b"

    def test_remove_edges(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("a", "c", "similar_to")
        store.add_edge("a", "d", "cross_collection")
        removed = store.remove_edges(from_id="a", edge_type="similar_to")
        assert removed == 2
        assert store.edge_count() == 1

    def test_remove_edges_no_filter_safe(self, tmp_db):
        """Refuse to delete all edges when no filter given."""
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        removed = store.remove_edges()
        assert removed == 0
        assert store.edge_count() == 1

    def test_edge_weight_default(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        edges = store.get_edges(from_id="a")
        assert edges[0]["weight"] == 1.0

    def test_edge_custom_weight(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "hebbian_association", weight=0.75)
        edges = store.get_edges(from_id="a")
        assert edges[0]["weight"] == 0.75


# ====================================================================
# Traversal tests
# ====================================================================

class TestTraversal:
    def test_get_related_depth_1(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("a", "c", "cross_collection")
        store.add_edge("d", "a", "similar_to")  # inverse

        related = store.get_related("a", depth=1)
        ids = {r["id"] for r in related}
        assert "b" in ids
        assert "c" in ids
        assert "d" in ids
        assert len(related) == 3

    def test_get_related_depth_2(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("b", "c", "similar_to")
        store.add_edge("c", "d", "similar_to")

        related = store.get_related("a", depth=2)
        ids = {r["id"] for r in related}
        assert "b" in ids
        assert "c" in ids
        # d is at depth 3, should not be included
        assert "d" not in ids

    def test_get_related_inverse_labeled(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("x", "a", "hebbian_association")

        related = store.get_related("a", depth=1)
        assert len(related) == 1
        assert related[0]["id"] == "x"
        assert related[0]["relationship"] == "inverse-hebbian_association"

    def test_neighbors_alias(self, tmp_db):
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        neighbors = store.neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == "b"

    def test_get_related_no_cycle(self, tmp_db):
        """Cycles should not cause infinite loops."""
        store, _ = tmp_db
        store.add_edge("a", "b", "similar_to")
        store.add_edge("b", "a", "similar_to")
        related = store.get_related("a", depth=3)
        # Should terminate without error
        assert len(related) >= 1


# ====================================================================
# Bulk operations
# ====================================================================

class TestBulk:
    def test_bulk_add_nodes(self, tmp_db):
        store, _ = tmp_db
        nodes = [
            ("n1", "clarvis-memories", "2026-03-01T00:00:00+00:00", 0),
            ("n2", "clarvis-learnings", "2026-03-01T00:00:01+00:00", 0),
            ("n3", "clarvis-goals", "2026-03-01T00:00:02+00:00", 1),
        ]
        store.bulk_add_nodes(nodes)
        assert store.node_count() == 3

    def test_bulk_add_edges(self, tmp_db):
        store, _ = tmp_db
        edges = [
            ("a", "b", "similar_to", "2026-03-01T00:00:00+00:00", "col1", "col1", 1.0),
            ("a", "c", "cross_collection", "2026-03-01T00:00:01+00:00", "col1", "col2", 1.0),
            ("b", "c", "hebbian_association", "2026-03-01T00:00:02+00:00", None, None, 0.9),
        ]
        store.bulk_add_edges(edges)
        assert store.edge_count() == 3


# ====================================================================
# Migration / Import tests
# ====================================================================

class TestMigration:
    def test_import_from_json(self, tmp_db, sample_json):
        store, tmpdir = tmp_db
        json_path, json_data = sample_json

        result = store.import_from_json(json_path)
        assert result["nodes_imported"] == 3
        assert result["edges_imported"] == 3
        assert result["duplicates_skipped"] == 0

    def test_import_preserves_node_data(self, tmp_db, sample_json):
        store, _ = tmp_db
        json_path, json_data = sample_json

        store.import_from_json(json_path)
        node = store.get_node("clarvis-goals_20260301_100002")
        assert node is not None
        assert node["collection"] == "clarvis-goals"
        assert node["backfilled"] == 1

    def test_import_preserves_edge_data(self, tmp_db, sample_json):
        store, _ = tmp_db
        json_path, json_data = sample_json

        store.import_from_json(json_path)
        edges = store.get_edges(
            from_id="clarvis-learnings_20260301_100001",
            edge_type="hebbian_association"
        )
        assert len(edges) == 1
        assert edges[0]["weight"] == 0.8

    def test_import_count_matches_json(self, tmp_db, sample_json):
        store, _ = tmp_db
        json_path, json_data = sample_json

        store.import_from_json(json_path)
        assert store.node_count() == len(json_data["nodes"])
        assert store.edge_count() == len(json_data["edges"])

    def test_import_idempotent(self, tmp_db, sample_json):
        store, _ = tmp_db
        json_path, _ = sample_json

        store.import_from_json(json_path)
        result = store.import_from_json(json_path)  # second import
        assert result["nodes_imported"] == 0
        assert result["edges_imported"] == 0
        assert store.node_count() == 3
        assert store.edge_count() == 3


# ====================================================================
# Export tests
# ====================================================================

class TestExport:
    def test_export_json_roundtrip(self, tmp_db, sample_json):
        store, tmpdir = tmp_db
        json_path, json_data = sample_json

        store.import_from_json(json_path)
        export_path = os.path.join(tmpdir, "exported.json")
        store.export_json(export_path)

        with open(export_path) as f:
            exported = json.load(f)

        assert len(exported["nodes"]) == len(json_data["nodes"])
        assert len(exported["edges"]) == len(json_data["edges"])
        assert exported["_edge_count"] == len(json_data["edges"])


# ====================================================================
# Stats & backup
# ====================================================================

class TestStatsAndBackup:
    def test_stats(self, tmp_db, sample_json):
        store, _ = tmp_db
        json_path, _ = sample_json
        store.import_from_json(json_path)

        stats = store.stats()
        assert stats["nodes"] == 3
        assert stats["edges"] == 3
        assert "similar_to" in stats["edge_types"]
        assert stats["edge_types"]["similar_to"] == 1
        assert "clarvis-memories" in stats["node_collections"]

    def test_backup(self, tmp_db, sample_json):
        store, tmpdir = tmp_db
        json_path, _ = sample_json
        store.import_from_json(json_path)

        backup_path = os.path.join(tmpdir, "backup.db")
        store.backup(backup_path)

        # Verify backup is a valid SQLite DB with same data
        backup = GraphStoreSQLite(backup_path)
        assert backup.node_count() == 3
        assert backup.edge_count() == 3
        assert backup.integrity_check() is True
        backup.close()


# ====================================================================
# Context manager
# ====================================================================

class TestLifecycle:
    def test_context_manager(self, tmp_path):
        db_path = str(tmp_path / "graph.db")
        with GraphStoreSQLite(db_path) as store:
            store.add_edge("a", "b", "similar_to")
            assert store.edge_count() == 1
        # After context exit, connection should be closed
        assert store._conn is None

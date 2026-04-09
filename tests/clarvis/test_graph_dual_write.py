"""Tests for graph backend (post-cutover: SQLite-only writes).

After the 2026-03-29 cutover, add_relationship() writes SQLite only
when the SQLite backend is active — dual-write is no longer the
default.  JSON fallback is tested separately for the json-only path.
"""

import json
import os
import tempfile

import pytest

from clarvis.brain.graph_store_sqlite import GraphStoreSQLite


# ---------------------------------------------------------------------------
# Helpers — lightweight GraphMixin host (avoids full ClarvisBrain + ChromaDB)
# ---------------------------------------------------------------------------

class _FakeCollections(dict):
    """Minimal stand-in for self.collections used by _infer_collection."""
    pass


def _make_graph_mixin(tmpdir, backend="sqlite"):
    """Create a minimal object that hosts GraphMixin methods."""
    from clarvis.brain.graph import GraphMixin

    class _Host(GraphMixin):
        pass

    host = _Host()
    host.graph_file = os.path.join(tmpdir, "relationships.json")
    host.graph_sqlite_file = os.path.join(tmpdir, "graph.db")
    host.graph_backend = backend
    host.collections = _FakeCollections()
    host._load_graph()
    return host


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dual_host():
    """GraphMixin host with sqlite backend (dual-write enabled)."""
    with tempfile.TemporaryDirectory(prefix="clarvis_dual_test_") as tmpdir:
        host = _make_graph_mixin(tmpdir, backend="sqlite")
        yield host, tmpdir
        if host._sqlite_store is not None:
            host._sqlite_store.close()


@pytest.fixture
def json_only_host():
    """GraphMixin host with json backend (no dual-write)."""
    with tempfile.TemporaryDirectory(prefix="clarvis_json_test_") as tmpdir:
        host = _make_graph_mixin(tmpdir, backend="json")
        yield host, tmpdir


# ====================================================================
# Dual-write: add_relationship
# ====================================================================

class TestSQLiteWriteAddRelationship:
    """Post-cutover: add_relationship writes to SQLite only (no JSON dual-write)."""

    def test_writes_to_sqlite_only(self, dual_host):
        host, tmpdir = dual_host
        host.add_relationship("a", "b", "similar_to",
                              source_collection="clarvis-memories",
                              target_collection="clarvis-learnings")

        # SQLite side — edge written
        sqlite_edges = host._sqlite_store.get_edges(from_id="a", to_id="b")
        assert len(sqlite_edges) == 1
        assert sqlite_edges[0]["type"] == "similar_to"

        # Nodes in SQLite
        assert host._sqlite_store.get_node("a") is not None
        assert host._sqlite_store.get_node("b") is not None

        # JSON side — NOT written (post-cutover behavior)
        assert len(host.graph["edges"]) == 0

    def test_duplicate_not_added(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("a", "b", "similar_to")  # duplicate

        assert host._sqlite_store.edge_count() == 1

    def test_different_types_both_added(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("a", "b", "cross_collection")

        assert host._sqlite_store.edge_count() == 2


# ====================================================================
# Dual-write: backfill
# ====================================================================

class TestBackfill:
    def test_backfill_noop_when_sqlite_active(self, dual_host):
        """Post-cutover: backfill delegates to SQL compaction, returns 0."""
        host, _ = dual_host
        host.graph["edges"].append({
            "from": "orphan_a", "to": "orphan_b",
            "type": "test", "created_at": "2026-03-05T00:00:00+00:00",
            "source_collection": "clarvis-memories",
            "target_collection": "clarvis-learnings",
        })
        count = host.backfill_graph_nodes()
        assert count == 0  # SQLite active — defers to compaction SQL

    def test_backfill_works_json_only(self, json_only_host):
        """JSON fallback: backfill populates missing nodes from edges."""
        host, _ = json_only_host
        host.graph["edges"].append({
            "from": "orphan_a", "to": "orphan_b",
            "type": "test", "created_at": "2026-03-05T00:00:00+00:00",
            "source_collection": "clarvis-memories",
            "target_collection": "clarvis-learnings",
        })
        count = host.backfill_graph_nodes()
        assert count == 2
        assert "orphan_a" in host.graph["nodes"]
        assert "orphan_b" in host.graph["nodes"]


# ====================================================================
# Read from SQLite
# ====================================================================

class TestReadFromSQLite:
    def test_get_related_uses_sqlite(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("a", "c", "cross_collection")
        host.add_relationship("d", "a", "hebbian_association")

        related = host.get_related("a", depth=1)
        ids = {r["id"] for r in related}
        assert "b" in ids
        assert "c" in ids
        assert "d" in ids

    def test_get_related_depth_2(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("b", "c", "similar_to")
        host.add_relationship("c", "d", "similar_to")

        related = host.get_related("a", depth=2)
        ids = {r["id"] for r in related}
        assert "b" in ids
        assert "c" in ids
        assert "d" not in ids  # depth 3

    def test_get_related_inverse(self, dual_host):
        host, _ = dual_host
        host.add_relationship("x", "a", "hebbian_association")

        related = host.get_related("a", depth=1)
        assert len(related) >= 1
        assert related[0]["relationship"] == "inverse-hebbian_association"


# ====================================================================
# JSON-only backend (no dual-write)
# ====================================================================

class TestJsonOnlyBackend:
    def test_no_sqlite_store(self, json_only_host):
        host, _ = json_only_host
        assert host._sqlite_store is None

    def test_add_relationship_json_only(self, json_only_host):
        host, tmpdir = json_only_host
        host.add_relationship("a", "b", "similar_to")

        assert len(host.graph["edges"]) == 1
        # No SQLite file should exist
        assert not os.path.exists(os.path.join(tmpdir, "graph.db"))

    def test_get_related_json_fallback(self, json_only_host):
        host, _ = json_only_host
        host.add_relationship("a", "b", "similar_to")

        related = host.get_related("a", depth=1)
        assert len(related) == 1
        assert related[0]["id"] == "b"


# ====================================================================
# Decay dual-write
# ====================================================================

class TestSQLiteDecay:
    def test_decay_applies_to_sqlite(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "hebbian_association")

        assert host._sqlite_store.edge_count() == 1

        result = host.decay_edges(half_life_days=30, prune_below=0.02)
        assert result["decayed"] == 1
        assert result["pruned"] == 0


# ====================================================================
# Parity verification
# ====================================================================

class TestVerifyParity:
    """Post-cutover: verify_graph_parity runs SQLite integrity check only."""

    def test_integrity_after_writes(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to",
                              source_collection="clarvis-memories",
                              target_collection="clarvis-learnings")

        result = host.verify_graph_parity(sample_n=10)
        assert result["parity_ok"] is True
        assert result["integrity_ok"] is True
        assert result["sqlite_edges"] == 1
        assert result["sqlite_nodes"] == 2

    def test_error_when_no_sqlite(self, json_only_host):
        host, _ = json_only_host
        result = host.verify_graph_parity()
        assert "error" in result


# ====================================================================
# Bulk intra-link dual-write (unit-level, no ChromaDB)
# ====================================================================

class TestBulkIntraLinkDualWrite:
    def test_sqlite_batch_collects(self, dual_host):
        """Verify that manually appended intra edges + _save_graph work with SQLite."""
        host, _ = dual_host
        from datetime import datetime, timezone

        now_str = datetime.now(timezone.utc).isoformat()

        # Simulate what bulk_intra_link does internally
        host.graph["nodes"]["m1"] = {"collection": "clarvis-memories", "added_at": now_str}
        host.graph["nodes"]["m2"] = {"collection": "clarvis-memories", "added_at": now_str}
        host.graph["edges"].append({
            "from": "m1", "to": "m2",
            "type": "intra_similar", "created_at": now_str,
            "source_collection": "clarvis-memories",
            "target_collection": "clarvis-memories",
        })
        host._save_graph()

        # Now batch-insert to SQLite as bulk_intra_link would
        host._sqlite_store.bulk_add_nodes([
            ("m1", "clarvis-memories", now_str, 0),
            ("m2", "clarvis-memories", now_str, 0),
        ])
        host._sqlite_store.bulk_add_edges([
            ("m1", "m2", "intra_similar", now_str,
             "clarvis-memories", "clarvis-memories", 1.0),
        ])

        assert host._sqlite_store.edge_count() == 1
        assert host._sqlite_store.node_count() == 2

        result = host.verify_graph_parity(sample_n=10)
        assert result["parity_ok"] is True

"""Tests for Phase 2 dual-write/dual-read graph backend.

Verifies that when CLARVIS_GRAPH_BACKEND=sqlite:
  - Writes go to both JSON and SQLite
  - Reads come from SQLite
  - Parity verification works
  - Rollback to JSON-only works when backend=json
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

class TestDualWriteAddRelationship:
    def test_writes_to_both_backends(self, dual_host):
        host, tmpdir = dual_host
        host.add_relationship("a", "b", "similar_to",
                              source_collection="clarvis-memories",
                              target_collection="clarvis-learnings")

        # JSON side
        assert len(host.graph["edges"]) == 1
        assert host.graph["edges"][0]["from"] == "a"
        assert host.graph["edges"][0]["to"] == "b"

        # SQLite side
        sqlite_edges = host._sqlite_store.get_edges(from_id="a", to_id="b")
        assert len(sqlite_edges) == 1
        assert sqlite_edges[0]["type"] == "similar_to"

        # Nodes in SQLite
        assert host._sqlite_store.get_node("a") is not None
        assert host._sqlite_store.get_node("b") is not None

    def test_duplicate_not_added(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("a", "b", "similar_to")  # duplicate

        assert len(host.graph["edges"]) == 1
        assert host._sqlite_store.edge_count() == 1

    def test_different_types_both_added(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        host.add_relationship("a", "b", "cross_collection")

        assert len(host.graph["edges"]) == 2
        assert host._sqlite_store.edge_count() == 2

    def test_json_file_persisted(self, dual_host):
        host, tmpdir = dual_host
        host.add_relationship("x", "y", "test_type")

        json_path = os.path.join(tmpdir, "relationships.json")
        assert os.path.exists(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert len(data["edges"]) == 1
        assert data["edges"][0]["from"] == "x"


# ====================================================================
# Dual-write: backfill
# ====================================================================

class TestDualWriteBackfill:
    def test_backfill_syncs_to_sqlite(self, dual_host):
        host, _ = dual_host
        # Manually add edges referencing nodes not in the graph
        host.graph["edges"].append({
            "from": "orphan_a", "to": "orphan_b",
            "type": "test", "created_at": "2026-03-05T00:00:00+00:00",
            "source_collection": "clarvis-memories",
            "target_collection": "clarvis-learnings",
        })
        host._save_graph()

        count = host.backfill_graph_nodes()
        assert count == 2

        # Both nodes should be in SQLite
        assert host._sqlite_store.get_node("orphan_a") is not None
        assert host._sqlite_store.get_node("orphan_b") is not None


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

class TestDualWriteDecay:
    def test_decay_applies_to_both(self, dual_host):
        host, _ = dual_host
        # Add a hebbian edge
        host.add_relationship("a", "b", "hebbian_association")

        # Verify it exists in both
        assert host._sqlite_store.edge_count() == 1

        # Decay (won't prune fresh edges, but will update weights)
        result = host.decay_edges(half_life_days=30, prune_below=0.02)
        assert result["decayed"] == 1
        assert result["pruned"] == 0


# ====================================================================
# Parity verification
# ====================================================================

class TestVerifyParity:
    def test_parity_ok_after_dual_writes(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to",
                              source_collection="clarvis-memories",
                              target_collection="clarvis-learnings")
        host.add_relationship("b", "c", "cross_collection",
                              source_collection="clarvis-learnings",
                              target_collection="clarvis-goals")

        result = host.verify_graph_parity(sample_n=10)
        assert result["parity_ok"] is True
        assert result["json_nodes"] == result["sqlite_nodes"]
        assert result["json_unique_edges"] == result["sqlite_edges"]
        assert result["sample_mismatched"] == 0

    def test_parity_detects_missing_edge(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")

        # Manually add an edge only to JSON (simulating a desync)
        host.graph["edges"].append({
            "from": "x", "to": "y", "type": "test",
            "created_at": "2026-03-05T00:00:00+00:00",
        })
        host.graph["nodes"]["x"] = {"collection": "unknown", "added_at": "2026-03-05T00:00:00+00:00"}
        host.graph["nodes"]["y"] = {"collection": "unknown", "added_at": "2026-03-05T00:00:00+00:00"}

        result = host.verify_graph_parity(sample_n=100)
        assert result["parity_ok"] is False
        # Either edge_delta or sample_mismatched should be nonzero
        assert result["edge_delta"] != 0 or result["sample_mismatched"] > 0

    def test_parity_error_when_no_sqlite(self, json_only_host):
        host, _ = json_only_host
        result = host.verify_graph_parity()
        assert "error" in result

    def test_parity_reports_json_duplicates(self, dual_host):
        host, _ = dual_host
        host.add_relationship("a", "b", "similar_to")
        # Force a duplicate into JSON (bypassing dedup check)
        host.graph["edges"].append({
            "from": "a", "to": "b", "type": "similar_to",
            "created_at": "2026-03-05T00:00:00+00:00",
        })

        result = host.verify_graph_parity(sample_n=10)
        assert result["json_duplicates"] == 1
        assert result["json_edges"] == 2
        assert result["json_unique_edges"] == 1


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

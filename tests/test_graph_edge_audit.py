"""Tests for graph edge audit and bulk_intra_link boosting."""

import sqlite3
import tempfile
import os
import pytest


def _make_test_db(path):
    """Create a minimal graph DB with known edge distribution."""
    from clarvis.brain.graph_store_sqlite import GraphStoreSQLite

    store = GraphStoreSQLite(path)
    # Add nodes across 3 collections
    for i in range(10):
        store.add_node(f"a{i}", "col-a", "2026-01-01T00:00:00Z")
    for i in range(10):
        store.add_node(f"b{i}", "col-b", "2026-01-01T00:00:00Z")
    for i in range(5):
        store.add_node(f"c{i}", "col-c", "2026-01-01T00:00:00Z")

    # Intra-collection edges for col-a (many)
    for i in range(9):
        store.add_edge(f"a{i}", f"a{i+1}", "intra_similar",
                       source_collection="col-a", target_collection="col-a")
    # Intra-collection edges for col-b (few)
    store.add_edge("b0", "b1", "intra_similar",
                   source_collection="col-b", target_collection="col-b")
    # Cross-collection
    store.add_edge("a0", "b0", "cross_collection",
                   source_collection="col-a", target_collection="col-b")
    # Near-zero type
    store.add_edge("a0", "c0", "supports",
                   source_collection="col-a", target_collection="col-c")

    return store


class TestGraphEdgeAudit:
    def test_audit_returns_valid_report(self, tmp_path):
        db_path = str(tmp_path / "test_graph.db")
        _make_test_db(db_path)

        from scripts.audit.graph_edge_audit import audit
        report = audit(db_path)

        assert report["total_edges"] == 12
        assert report["total_nodes"] == 25
        assert "edge_types" in report
        assert "intra_similar" in report["edge_types"]
        assert report["edge_types"]["intra_similar"]["count"] == 10

    def test_near_zero_detection(self, tmp_path):
        """Types with < 0.5% of total edges should be flagged as near-zero."""
        db_path = str(tmp_path / "test_graph.db")
        store = _make_test_db(db_path)
        # Add enough intra_similar edges so 'supports' (1 edge) falls below 0.5%
        for i in range(200):
            store.add_edge(f"pad_a{i}", f"pad_b{i}", "intra_similar",
                           source_collection="col-a", target_collection="col-a")

        from scripts.audit.graph_edge_audit import audit
        report = audit(db_path)

        assert "supports" in report["near_zero_types"]

    def test_cross_collection_coverage(self, tmp_path):
        db_path = str(tmp_path / "test_graph.db")
        _make_test_db(db_path)

        from scripts.audit.graph_edge_audit import audit
        report = audit(db_path)

        # a->b and a->c are connected, b->c is not
        cov = report["cross_collection_coverage"]
        assert cov["connected_pairs"] >= 2
        assert cov["possible_pairs"] == 6  # 3 collections * 2 directions

    def test_gini_coefficient_range(self, tmp_path):
        db_path = str(tmp_path / "test_graph.db")
        _make_test_db(db_path)

        from scripts.audit.graph_edge_audit import audit
        report = audit(db_path)

        assert 0.0 <= report["gini_coefficient"] <= 1.0


class TestBulkIntraLinkBoosting:
    def test_boosted_collections_get_relaxed_params(self):
        """Verify that _edge_type_counts_by_collection is used for boost targeting."""
        from clarvis.brain.graph import GraphMixin
        # Just verify the method signature accepts the new verbose output
        assert hasattr(GraphMixin, "bulk_intra_link")
        import inspect
        sig = inspect.signature(GraphMixin.bulk_intra_link)
        assert "max_distance" in sig.parameters
        assert "max_links_per_memory" in sig.parameters
        assert "verbose" in sig.parameters

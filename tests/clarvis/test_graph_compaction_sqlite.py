"""Tests for Phase 3 — SQLite-optimized graph compaction.

Verifies that the SQLite compaction path (used when brain._sqlite_store is set):
  - Removes orphan edges via SQL DELETE
  - Removes orphan nodes via SQL DELETE
  - Backfills missing nodes via SQL INSERT
  - Reports correct health metrics from SQLite
"""

import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add scripts dir to path
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from clarvis.brain.graph_store_sqlite import GraphStoreSQLite


@pytest.fixture
def sqlite_store():
    """Create a temporary SQLite graph store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "graph.db")
        store = GraphStoreSQLite(db_path)
        yield store
        store.close()


@pytest.fixture
def populated_store(sqlite_store):
    """Store with nodes and edges, some orphaned."""
    now = datetime.now(timezone.utc).isoformat()

    # Valid nodes (exist in "ChromaDB")
    sqlite_store.add_node("mem-1", "clarvis-memories", now)
    sqlite_store.add_node("mem-2", "clarvis-memories", now)
    sqlite_store.add_node("mem-3", "clarvis-learnings", now)
    # Orphan node (not referenced by edges, not in ChromaDB)
    sqlite_store.add_node("orphan-node", "clarvis-memories", now)

    # Valid edges (both endpoints exist in ChromaDB)
    sqlite_store.add_edge("mem-1", "mem-2", "similar_to", created_at=now,
                          source_collection="clarvis-memories",
                          target_collection="clarvis-memories")
    sqlite_store.add_edge("mem-2", "mem-3", "cross_collection", created_at=now,
                          source_collection="clarvis-memories",
                          target_collection="clarvis-learnings")
    # Orphan edge (endpoint "deleted-mem" not in ChromaDB)
    sqlite_store.add_edge("mem-1", "deleted-mem", "hebbian_association",
                          created_at=now)
    sqlite_store.add_edge("deleted-mem2", "mem-2", "concept_link",
                          created_at=now)

    return sqlite_store


def _make_all_ids():
    """Simulate ChromaDB memory IDs."""
    return {"mem-1", "mem-2", "mem-3"}


class TestSQLiteOrphanEdgeRemoval:
    def test_removes_orphan_edges(self, populated_store):
        from graph_compaction import _sqlite_remove_orphan_edges

        all_ids = _make_all_ids()
        assert populated_store.edge_count() == 4

        removed = _sqlite_remove_orphan_edges(populated_store, all_ids)
        assert removed == 2  # deleted-mem and deleted-mem2 edges
        assert populated_store.edge_count() == 2

    def test_dry_run_no_change(self, populated_store):
        from graph_compaction import _sqlite_remove_orphan_edges

        all_ids = _make_all_ids()
        removed = _sqlite_remove_orphan_edges(populated_store, all_ids, dry_run=True)
        assert removed == 2
        assert populated_store.edge_count() == 4  # unchanged

    def test_no_orphans(self, sqlite_store):
        from graph_compaction import _sqlite_remove_orphan_edges

        now = datetime.now(timezone.utc).isoformat()
        sqlite_store.add_node("a", "col", now)
        sqlite_store.add_node("b", "col", now)
        sqlite_store.add_edge("a", "b", "link", created_at=now)

        removed = _sqlite_remove_orphan_edges(sqlite_store, {"a", "b"})
        assert removed == 0
        assert sqlite_store.edge_count() == 1


class TestSQLiteOrphanNodeRemoval:
    def test_removes_orphan_nodes(self, populated_store):
        from graph_compaction import _sqlite_remove_orphan_nodes

        # First remove orphan edges so "orphan-node" is unreferenced
        from graph_compaction import _sqlite_remove_orphan_edges
        _sqlite_remove_orphan_edges(populated_store, _make_all_ids())

        all_ids = _make_all_ids()
        removed = _sqlite_remove_orphan_nodes(populated_store, all_ids)
        assert removed == 1  # orphan-node
        assert populated_store.node_count() == 3

    def test_dry_run_no_change(self, populated_store):
        from graph_compaction import _sqlite_remove_orphan_nodes

        from graph_compaction import _sqlite_remove_orphan_edges
        _sqlite_remove_orphan_edges(populated_store, _make_all_ids())

        all_ids = _make_all_ids()
        initial_count = populated_store.node_count()
        removed = _sqlite_remove_orphan_nodes(populated_store, all_ids, dry_run=True)
        assert removed == 1
        assert populated_store.node_count() == initial_count


class TestSQLiteBackfillNodes:
    def test_backfills_missing_nodes(self, sqlite_store):
        from graph_compaction import _sqlite_backfill_nodes

        now = datetime.now(timezone.utc).isoformat()
        # Add an edge referencing nodes not in the nodes table
        sqlite_store.add_edge("new-1", "new-2", "link", created_at=now,
                              source_collection="clarvis-memories",
                              target_collection="clarvis-learnings")

        brain = MagicMock()
        brain._infer_collection.return_value = "clarvis-memories"

        backfilled = _sqlite_backfill_nodes(sqlite_store, brain)
        assert backfilled == 2
        assert sqlite_store.node_count() == 2

        n1 = sqlite_store.get_node("new-1")
        assert n1 is not None
        assert n1["collection"] == "clarvis-memories"
        assert n1["backfilled"] == 1

    def test_no_backfill_needed(self, sqlite_store):
        from graph_compaction import _sqlite_backfill_nodes

        now = datetime.now(timezone.utc).isoformat()
        sqlite_store.add_node("a", "col", now)
        sqlite_store.add_node("b", "col", now)
        sqlite_store.add_edge("a", "b", "link", created_at=now)

        brain = MagicMock()
        backfilled = _sqlite_backfill_nodes(sqlite_store, brain)
        assert backfilled == 0


class TestSQLiteHealthMetrics:
    def test_health_metrics(self, populated_store):
        from graph_compaction import _sqlite_health_metrics

        brain = MagicMock()
        brain.stats.return_value = {"total_memories": 100}

        metrics = _sqlite_health_metrics(populated_store, brain)
        assert metrics["total_nodes"] == 4  # 3 valid + 1 orphan
        assert metrics["total_edges"] == 4
        assert metrics["total_memories"] == 100
        assert metrics["cross_collection_edges"] == 1  # mem-2 -> mem-3
        assert "similar_to" in metrics["edge_types"]
        assert metrics["density"] > 0


class TestCompactionDispatch:
    def test_dispatches_to_sqlite(self):
        """Verify run_compaction dispatches to SQLite path when _sqlite_store set."""
        from graph_compaction import run_compaction

        with patch("graph_compaction.get_brain") as mock_get_brain:
            brain = MagicMock()
            brain._sqlite_store = MagicMock()  # non-None -> SQLite path
            mock_get_brain.return_value = brain

            with patch("graph_compaction.run_compaction_sqlite") as mock_sqlite:
                mock_sqlite.return_value = {"test": True}
                result = run_compaction(dry_run=True)
                mock_sqlite.assert_called_once_with(brain, dry_run=True)

    def test_dispatches_to_json(self):
        """Verify run_compaction dispatches to JSON path when _sqlite_store is None."""
        from graph_compaction import run_compaction

        with patch("graph_compaction.get_brain") as mock_get_brain:
            brain = MagicMock()
            brain._sqlite_store = None
            mock_get_brain.return_value = brain

            with patch("graph_compaction.run_compaction_json") as mock_json:
                mock_json.return_value = {"test": True}
                result = run_compaction(dry_run=True)
                mock_json.assert_called_once_with(brain, dry_run=True)

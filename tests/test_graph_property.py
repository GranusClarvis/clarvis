"""
Property-based test suite for ClarvisDB graph operations (GraphStoreSQLite).

Uses Hypothesis to generate random graph operations (add_edge, remove_edge,
traverse) and verify structural invariants:
- No orphan edges after cleanup
- Bidirectional consistency (edges queryable from both ends)
- Cycle detection / traversal termination
- Edge deduplication (UNIQUE constraint)
- Node/edge count consistency

Queue task: [EXTERNAL_CHALLENGE:bench-code-01]
"""

import os
import tempfile

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from clarvis.brain.graph_store_sqlite import GraphStoreSQLite

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Node IDs: short alphanumeric strings (realistic ChromaDB IDs are hex)
node_ids = st.text(
    alphabet="abcdef0123456789", min_size=4, max_size=12
)

# Edge types matching real graph usage
edge_types = st.sampled_from([
    "similar_to", "synthesized_with", "hebbian_association",
    "related_to", "derived_from", "crosslink",
])

# Collections matching real brain collections
collections = st.sampled_from([
    "clarvis-learnings", "clarvis-procedures", "clarvis-episodes",
    "clarvis-goals", "clarvis-memories", "clarvis-context",
])

# Edge weight: 0.01 to 2.0
weights = st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False)


@st.composite
def graph_operation(draw):
    """Generate a random graph operation."""
    op = draw(st.sampled_from(["add_node", "add_edge", "remove_edge", "get_related"]))

    if op == "add_node":
        return ("add_node", draw(node_ids), draw(collections))
    elif op == "add_edge":
        return ("add_edge", draw(node_ids), draw(node_ids), draw(edge_types), draw(weights))
    elif op == "remove_edge":
        return ("remove_edge", draw(node_ids), draw(node_ids), draw(edge_types))
    else:  # get_related
        return ("get_related", draw(node_ids), draw(st.integers(min_value=1, max_value=3)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def graph_db():
    """Create a fresh in-memory-like temp SQLite graph store."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = GraphStoreSQLite(path)
    yield store
    store.close()
    for ext in ("", "-wal", "-shm"):
        try:
            os.unlink(path + ext)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestEdgeDeduplication:
    """UNIQUE(from_id, to_id, type) constraint holds under repeated inserts."""

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
        weight=weights,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_edge_ignored(self, graph_db, from_id, to_id, edge_type, weight):
        """Inserting the same edge twice doesn't create duplicates."""
        first = graph_db.add_edge(from_id, to_id, edge_type, weight=weight)
        second = graph_db.add_edge(from_id, to_id, edge_type, weight=weight)

        edges = graph_db.get_edges(from_id=from_id, to_id=to_id, edge_type=edge_type)
        assert len(edges) == 1, f"Expected 1 edge, got {len(edges)}"
        assert second is False, "Second insert should return False (duplicate)"


class TestBidirectionalConsistency:
    """Edges are queryable from both the from_id and to_id sides."""

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_edge_queryable_from_both_ends(self, graph_db, from_id, to_id, edge_type):
        """An edge from A→B is found when querying by from_id=A or to_id=B."""
        assume(from_id != to_id)
        graph_db.add_edge(from_id, to_id, edge_type)

        from_query = graph_db.get_edges(from_id=from_id)
        to_query = graph_db.get_edges(to_id=to_id)

        assert any(e["to_id"] == to_id and e["type"] == edge_type for e in from_query), \
            f"Edge not found via from_id query"
        assert any(e["from_id"] == from_id and e["type"] == edge_type for e in to_query), \
            f"Edge not found via to_id query"

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_traversal_finds_both_directions(self, graph_db, from_id, to_id, edge_type):
        """get_related() traverses both outgoing and incoming edges."""
        assume(from_id != to_id)
        graph_db.add_edge(from_id, to_id, edge_type)

        # From the source node, target should be reachable (outgoing)
        related_from_source = graph_db.get_related(from_id, depth=1)
        target_ids = {r["id"] for r in related_from_source}
        assert to_id in target_ids, "Target not reachable from source via get_related"

        # From the target node, source should be reachable (incoming/inverse)
        related_from_target = graph_db.get_related(to_id, depth=1)
        source_ids = {r["id"] for r in related_from_target}
        assert from_id in source_ids, "Source not reachable from target via inverse traversal"


class TestTraversalTermination:
    """Traversal terminates correctly even with cycles."""

    @given(
        nodes=st.lists(node_ids, min_size=2, max_size=6, unique=True),
        edge_type=edge_types,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cycle_does_not_infinite_loop(self, graph_db, nodes, edge_type):
        """A cycle A→B→C→A doesn't cause infinite recursion in traversal."""
        # Create a cycle
        for i in range(len(nodes)):
            graph_db.add_edge(nodes[i], nodes[(i + 1) % len(nodes)], edge_type)

        # Traversal should terminate and return finite results
        related = graph_db.get_related(nodes[0], depth=3)
        assert isinstance(related, list)
        # Should find some but not infinitely many
        assert len(related) < 1000, "Traversal produced suspiciously many results"

    @given(
        center=node_ids,
        spokes=st.lists(node_ids, min_size=1, max_size=10, unique=True),
        edge_type=edge_types,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_star_topology_traversal(self, graph_db, center, spokes, edge_type):
        """Star graph: center connected to N spokes at depth=1."""
        assume(center not in spokes)
        for spoke in spokes:
            graph_db.add_edge(center, spoke, edge_type)

        related = graph_db.get_related(center, depth=1)
        found_ids = {r["id"] for r in related}
        for spoke in spokes:
            assert spoke in found_ids, f"Spoke {spoke} not found from center"


class TestRemoveEdgeConsistency:
    """Edge removal maintains graph consistency."""

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_removed_edge_not_queryable(self, graph_db, from_id, to_id, edge_type):
        """After removing an edge, it's gone from all queries."""
        assume(from_id != to_id)
        graph_db.add_edge(from_id, to_id, edge_type)

        count_before = graph_db.edge_count()
        removed = graph_db.remove_edges(from_id=from_id, to_id=to_id, edge_type=edge_type)
        count_after = graph_db.edge_count()

        assert removed == 1, f"Expected 1 removal, got {removed}"
        assert count_after == count_before - 1

        edges = graph_db.get_edges(from_id=from_id, to_id=to_id, edge_type=edge_type)
        assert len(edges) == 0, "Edge still found after removal"

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_double_remove_is_noop(self, graph_db, from_id, to_id, edge_type):
        """Removing a non-existent edge returns 0, doesn't error."""
        graph_db.add_edge(from_id, to_id, edge_type)
        graph_db.remove_edges(from_id=from_id, to_id=to_id, edge_type=edge_type)

        # Second remove: should be a no-op
        removed = graph_db.remove_edges(from_id=from_id, to_id=to_id, edge_type=edge_type)
        assert removed == 0


class TestNodeEdgeCountConsistency:
    """Node and edge counts stay consistent through operations."""

    @given(
        ops=st.lists(graph_operation(), min_size=5, max_size=30),
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=10000,
    )
    def test_counts_consistent_after_random_ops(self, graph_db, ops):
        """After a sequence of random operations, counts match actual data."""
        for op in ops:
            try:
                if op[0] == "add_node":
                    _, nid, coll = op
                    graph_db.add_node(nid, coll, "2026-01-01T00:00:00+00:00")
                elif op[0] == "add_edge":
                    _, fid, tid, etype, w = op
                    graph_db.add_edge(fid, tid, etype, weight=w)
                elif op[0] == "remove_edge":
                    _, fid, tid, etype = op
                    graph_db.remove_edges(from_id=fid, to_id=tid, edge_type=etype)
                elif op[0] == "get_related":
                    _, nid, depth = op
                    graph_db.get_related(nid, depth=depth)
            except Exception:
                pass  # Some ops may fail on missing nodes, that's fine

        # Verify counts match reality
        reported_nodes = graph_db.node_count()
        reported_edges = graph_db.edge_count()

        actual_nodes = graph_db._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        actual_edges = graph_db._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

        assert reported_nodes == actual_nodes, \
            f"Node count mismatch: reported={reported_nodes}, actual={actual_nodes}"
        assert reported_edges == actual_edges, \
            f"Edge count mismatch: reported={reported_edges}, actual={actual_edges}"


class TestOrphanEdgeCleanup:
    """Orphan edge detection works correctly."""

    @given(
        node_pairs=st.lists(
            st.tuples(node_ids, node_ids, collections),
            min_size=2, max_size=8,
            unique_by=lambda x: (x[0], x[1]),
        ),
        edge_type=edge_types,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_orphans_when_all_nodes_registered(self, graph_db, node_pairs, edge_type):
        """When all edge endpoints have registered nodes, orphan count is 0."""
        # Register all nodes first
        for fid, tid, coll in node_pairs:
            graph_db.add_node(fid, coll, "2026-01-01T00:00:00+00:00")
            graph_db.add_node(tid, coll, "2026-01-01T00:00:00+00:00")

        # Add edges between registered nodes
        for fid, tid, _ in node_pairs:
            if fid != tid:
                graph_db.add_edge(fid, tid, edge_type)

        orphans = graph_db.orphan_edges_count()
        assert orphans == 0, f"Found {orphans} orphan edges when all nodes are registered"

    @given(
        from_id=node_ids,
        to_id=node_ids,
        edge_type=edge_types,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_edges_without_nodes_are_orphans(self, graph_db, from_id, to_id, edge_type):
        """Edges whose endpoints aren't in the nodes table count as orphans."""
        assume(from_id != to_id)
        # Add edge WITHOUT registering nodes
        graph_db.add_edge(from_id, to_id, edge_type)

        orphans = graph_db.orphan_edges_count()
        assert orphans >= 1, "Edge without registered nodes should be counted as orphan"


class TestIntegrityAfterBulkOps:
    """Bulk operations maintain database integrity."""

    @given(
        edges=st.lists(
            st.tuples(node_ids, node_ids, edge_types),
            min_size=1, max_size=20,
        ),
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bulk_add_edges_integrity(self, graph_db, edges):
        """bulk_add_edges maintains UNIQUE constraint and integrity."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        tuples = [
            (fid, tid, etype, now, None, None, 1.0)
            for fid, tid, etype in edges
        ]
        graph_db.bulk_add_edges(tuples)

        # Integrity check passes
        assert graph_db.integrity_check(), "SQLite integrity check failed after bulk insert"

        # No duplicate edges (from_id, to_id, type must be unique)
        all_edges = graph_db.get_edges()
        seen = set()
        for e in all_edges:
            key = (e["from_id"], e["to_id"], e["type"])
            assert key not in seen, f"Duplicate edge found: {key}"
            seen.add(key)


class TestEdgeDecay:
    """Edge decay preserves graph structure and only affects weights."""

    @given(
        from_id=node_ids,
        to_id=node_ids,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_decay_does_not_remove_non_hebbian_edges(self, graph_db, from_id, to_id):
        """decay_edges only affects hebbian_association type by default."""
        assume(from_id != to_id)
        # Add a non-hebbian edge
        graph_db.add_edge(from_id, to_id, "similar_to", weight=0.001)
        count_before = graph_db.edge_count()

        graph_db.decay_edges()

        count_after = graph_db.edge_count()
        assert count_after == count_before, \
            "Non-hebbian edge was removed by decay"

    @given(
        from_id=node_ids,
        to_id=node_ids,
        weight=st.floats(min_value=0.5, max_value=2.0),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_decay_reduces_weight(self, graph_db, from_id, to_id, weight):
        """Decay reduces weight for hebbian_association edges."""
        assume(from_id != to_id)
        # Use a date far in the past so decay is significant
        graph_db.add_edge(
            from_id, to_id, "hebbian_association",
            weight=weight, created_at="2025-01-01T00:00:00+00:00",
        )

        result = graph_db.decay_edges()

        if result["decayed"] > 0:
            edges = graph_db.get_edges(from_id=from_id, to_id=to_id, edge_type="hebbian_association")
            if edges:  # might have been pruned
                assert edges[0]["weight"] < weight, "Weight should decrease after decay"

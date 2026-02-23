"""Tests for ClarvisPhi core computation."""

import json
import os
import tempfile

from clarvis_phi import compute_phi, PhiConfig, PhiTracker, partition_analysis


def test_empty_system():
    """Empty system: reachability is vacuously 1.0, so phi = 0.25 * 1.0 = 0.25."""
    result = compute_phi(nodes={}, edges=[])
    assert result["phi"] == 0.25  # only reachability contributes
    assert result["components"]["collection_reachability"] == 1.0


def test_single_partition():
    """Single partition = fully integrated by definition."""
    nodes = {"a": "p1", "b": "p1", "c": "p1"}
    edges = [("a", "b", "similar"), ("b", "c", "similar")]
    result = compute_phi(nodes, edges)
    # Reachability is 1.0 (only one partition), intra should be > 0
    assert result["components"]["collection_reachability"] == 1.0
    assert result["components"]["intra_collection_density"] > 0


def test_two_disconnected_partitions():
    """Two partitions with no bridges should have low cross-connectivity."""
    nodes = {"a": "p1", "b": "p1", "c": "p2", "d": "p2"}
    edges = [("a", "b", "similar"), ("c", "d", "similar")]
    result = compute_phi(nodes, edges)
    assert result["components"]["cross_collection_connectivity"] == 0.0
    assert result["components"]["collection_reachability"] == 0.0


def test_fully_connected():
    """Well-connected graph should score high."""
    nodes = {"a": "p1", "b": "p1", "c": "p2", "d": "p2"}
    edges = [
        ("a", "b", "similar"), ("c", "d", "similar"),
        ("a", "c", "cross"), ("b", "d", "cross"),
    ]
    result = compute_phi(nodes, edges)
    assert result["components"]["cross_collection_connectivity"] == 0.5
    assert result["components"]["collection_reachability"] == 1.0
    assert result["phi"] > 0.3


def test_custom_config():
    """Custom weights should change the result."""
    nodes = {"a": "p1", "b": "p2"}
    edges = [("a", "b", "cross")]
    default = compute_phi(nodes, edges)
    custom = compute_phi(nodes, edges, config=PhiConfig(w_reachability=0.90, w_cross_connectivity=0.10, w_intra_density=0.0, w_semantic_overlap=0.0))
    assert custom["phi"] != default["phi"]


def test_partition_analysis():
    """MIP should identify the weakest-linked partition."""
    nodes = {"a": "p1", "b": "p1", "c": "p2", "d": "p2", "e": "p3"}
    edges = [
        ("a", "b", "similar"),
        ("c", "d", "similar"),
        ("a", "c", "cross"), ("a", "d", "cross"), ("b", "c", "cross"),  # p1<->p2 strong
        ("d", "e", "cross"),  # p2<->p3 weak (1 edge)
    ]
    mip = partition_analysis(nodes, edges)
    # p3 has fewest cross-edges (1), should be MIP
    assert mip["mip_partition"] == "p3"
    assert mip["mip_loss"] < mip["per_partition_loss"]["p1"]


def test_similarity_fn():
    """Semantic component should use the provided function."""
    nodes = {"a": "p1", "b": "p2"}
    edges = [("a", "b", "cross")]
    result_no_sim = compute_phi(nodes, edges)
    result_with_sim = compute_phi(nodes, edges, similarity_fn=lambda a, b: 0.8)
    assert result_with_sim["phi"] > result_no_sim["phi"]
    assert result_with_sim["components"]["semantic_cross_collection"] > 0


def test_tracker_persistence():
    """Tracker should persist and load history."""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "history.json")
        nodes = {"a": "p1", "b": "p2"}
        edges = [("a", "b", "cross")]

        tracker1 = PhiTracker(path)
        tracker1.record(nodes, edges)
        tracker1.record(nodes, edges)
        assert len(tracker1.history) == 2

        # Load from disk
        tracker2 = PhiTracker(path)
        assert len(tracker2.history) == 2
        trend = tracker2.trend()
        assert trend["trend"] == "stable"
        assert trend["measurements"] == 2


def test_tracker_delta():
    """Tracker delta should compute change from previous."""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "history.json")
        tracker = PhiTracker(path)

        nodes1 = {"a": "p1", "b": "p2"}
        tracker.record(nodes1, [("a", "b", "cross")])

        nodes2 = {"a": "p1", "b": "p1", "c": "p2"}
        tracker.record(nodes2, [("a", "b", "similar"), ("b", "c", "cross")])

        delta = tracker.delta()
        assert isinstance(delta, float)


def test_interpretation_levels():
    """Interpretation should vary by Phi level."""
    nodes_low = {"a": "p1", "b": "p2"}
    result_low = compute_phi(nodes_low, [])
    assert "Fragmented" in result_low["interpretation"] or "Emerging" in result_low["interpretation"]

    nodes_high = {f"n{i}": f"p{i%3}" for i in range(12)}
    edges_high = [(f"n{i}", f"n{(i+1)%12}", "cross") for i in range(12)]
    result_high = compute_phi(nodes_high, edges_high)
    # Should be at least moderate
    assert result_high["phi"] > 0.1


if __name__ == "__main__":
    test_empty_system()
    test_single_partition()
    test_two_disconnected_partitions()
    test_fully_connected()
    test_custom_config()
    test_partition_analysis()
    test_similarity_fn()
    test_tracker_persistence()
    test_tracker_delta()
    test_interpretation_levels()
    print("All tests passed!")

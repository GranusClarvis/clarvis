"""
ClarvisPhi — IIT-inspired information integration measurement.

Measures how interconnected a partitioned knowledge system is, inspired by
Tononi's Integrated Information Theory. High Phi = unified, deeply integrated
system. Low Phi = siloed, fragmented.

Backend-agnostic: provide nodes, edges, and an optional similarity function.
No database dependencies required.

Usage:
    from clarvis_phi import compute_phi, PhiConfig, PhiTracker

    result = compute_phi(
        nodes={"m1": "identity", "m2": "goals", "m3": "identity"},
        edges=[("m1", "m2", "cross"), ("m1", "m3", "similar")],
    )
    print(result["phi"])        # 0.0 - 1.0
    print(result["components"]) # per-component breakdown

    # Track over time
    tracker = PhiTracker("/path/to/history.json")
    tracker.record(nodes, edges)
    print(tracker.trend())
"""

from clarvis_phi.core import (
    compute_phi,
    PhiConfig,
    PhiResult,
    intra_collection_density,
    cross_collection_integration,
    semantic_cross_collection,
    collection_reachability,
    partition_analysis,
)
from clarvis_phi.tracker import PhiTracker

__version__ = "1.0.0"
__all__ = [
    "compute_phi",
    "PhiConfig",
    "PhiResult",
    "PhiTracker",
    "intra_collection_density",
    "cross_collection_integration",
    "semantic_cross_collection",
    "collection_reachability",
    "partition_analysis",
]

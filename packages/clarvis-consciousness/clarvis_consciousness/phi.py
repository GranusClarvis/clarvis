"""
Phi (Integrated Information) — standalone metric computation.

Measures how interconnected a memory system is across partitions.
Based on IIT (Tononi): Phi quantifies information integration — how much
information is lost when the system is partitioned into independent parts.

High Phi = unified, interconnected whole. Low Phi = siloed, fragmented.

This module is backend-agnostic: you provide nodes, edges, and an optional
similarity function. No ChromaDB or filesystem dependency.

Usage:
    from clarvis_consciousness.phi import compute_phi, PhiConfig

    result = compute_phi(
        nodes={"mem1": "identity", "mem2": "goals", "mem3": "identity"},
        edges=[("mem1", "mem2", "cross"), ("mem1", "mem3", "similar")],
        similarity_fn=my_similarity,   # optional
    )
    print(result["phi"])        # 0.0 - 1.0
    print(result["components"]) # per-component breakdown
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

Edge = Tuple[str, str, str]  # (from_id, to_id, edge_type)
SimilarityFn = Callable[[str, str], float]  # (collection_a, collection_b) -> 0-1


@dataclass
class PhiConfig:
    """Tunable weights for the four Phi components."""
    w_intra_density: float = 0.20
    w_cross_connectivity: float = 0.20
    w_semantic_overlap: float = 0.35
    w_reachability: float = 0.25
    # Normalization: raw intra-density is typically 0-0.2 for sparse graphs
    intra_density_scale: float = 5.0


def intra_collection_density(
    nodes: Dict[str, str],
    adj: Dict[str, Set[str]],
) -> Tuple[float, Dict[str, float]]:
    """
    Component 1: Within-collection link density.

    Richer internal connections = more integrated modules.

    Returns:
        (average_density, per_collection_density)
    """
    col_nodes: Dict[str, Set[str]] = defaultdict(set)
    for nid, col in nodes.items():
        col_nodes[col].add(nid)

    densities = []
    per_collection: Dict[str, float] = {}

    for col, members in col_nodes.items():
        if col == "unknown" or len(members) < 2:
            continue

        total_links = 0
        for nid in members:
            neighbors_in_col = sum(1 for n in adj.get(nid, set()) if n in members)
            total_links += neighbors_in_col

        actual_edges = total_links / 2  # bidirectional
        max_edges = len(members) * (len(members) - 1) / 2
        density = actual_edges / max_edges if max_edges > 0 else 0

        densities.append(density)
        per_collection[col] = round(density, 4)

    avg = sum(densities) / len(densities) if densities else 0.0
    return avg, per_collection


def cross_collection_integration(
    nodes: Dict[str, str],
    edges: List[Edge],
) -> Tuple[float, Dict[str, int]]:
    """
    Component 2: Cross-collection connectivity.

    Ratio of edges connecting different collections to total edges.
    """
    if not edges:
        return 0.0, {"cross": 0, "same": 0, "total": 0}

    cross = 0
    same = 0
    for f, t, _ in edges:
        f_col = nodes.get(f, "unknown")
        t_col = nodes.get(t, "unknown")
        if f_col != t_col and f_col != "unknown" and t_col != "unknown":
            cross += 1
        else:
            same += 1

    total = cross + same
    score = cross / total if total > 0 else 0.0
    return score, {"cross": cross, "same": same, "total": total}


def semantic_cross_collection(
    nodes: Dict[str, str],
    similarity_fn: Optional[SimilarityFn] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Component 3: Semantic overlap across collection boundaries.

    If a similarity_fn is provided, it's called for each pair of collections
    and should return a 0-1 similarity score. Otherwise returns 0.

    Args:
        nodes: node_id -> collection mapping
        similarity_fn: (col_a, col_b) -> similarity score [0, 1]

    Returns:
        (average_similarity, per_pair_similarity)
    """
    if similarity_fn is None:
        return 0.0, {}

    collections = {col for col in set(nodes.values()) if col != "unknown"}
    if len(collections) < 2:
        return 0.0, {}

    cols = sorted(collections)
    pair_scores: List[float] = []
    pair_details: Dict[str, float] = {}

    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            try:
                sim = similarity_fn(c1, c2)
                sim = max(0.0, min(1.0, sim))
                pair_scores.append(sim)
                pair_details[f"{c1} <-> {c2}"] = round(sim, 4)
            except Exception:
                pass

    overall = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
    return overall, pair_details


def collection_reachability(
    nodes: Dict[str, str],
    adj: Dict[str, Set[str]],
) -> Tuple[float, Dict[str, List[str]]]:
    """
    Component 4: Can information flow between all collection pairs via graph?

    Full integration = every collection reaches every other.
    Uses BFS on the collection-level adjacency graph.
    """
    col_adj: Dict[str, Set[str]] = defaultdict(set)
    for nid in adj:
        nid_col = nodes.get(nid, "unknown")
        if nid_col == "unknown":
            continue
        for neighbor in adj[nid]:
            n_col = nodes.get(neighbor, "unknown")
            if n_col != "unknown" and nid_col != n_col:
                col_adj[nid_col].add(n_col)

    active_cols = {c for c in set(nodes.values()) if c != "unknown"}
    if len(active_cols) < 2:
        return 1.0, {}

    # BFS reachability from each collection
    reachability: Dict[str, Set[str]] = {}
    for start in active_cols:
        visited: Set[str] = set()
        queue = [start]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            for neighbor in col_adj.get(curr, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        reachability[start] = visited - {start}

    total_pairs = 0
    connected_pairs = 0
    cols_list = list(active_cols)
    for i in range(len(cols_list)):
        for j in range(i + 1, len(cols_list)):
            total_pairs += 1
            if cols_list[j] in reachability.get(cols_list[i], set()):
                connected_pairs += 1

    score = connected_pairs / total_pairs if total_pairs > 0 else 0.0
    return score, {k: sorted(v) for k, v in reachability.items()}


def _build_adjacency(
    edges: List[Edge],
) -> Dict[str, Set[str]]:
    """Build bidirectional adjacency from edge list."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for f, t, _ in edges:
        adj[f].add(t)
        adj[t].add(f)
    return adj


def compute_phi(
    nodes: Dict[str, str],
    edges: List[Edge],
    similarity_fn: Optional[SimilarityFn] = None,
    config: Optional[PhiConfig] = None,
) -> Dict:
    """
    Compute the composite Phi metric.

    Args:
        nodes: Mapping of node_id -> collection_name.
        edges: List of (from_id, to_id, edge_type) tuples.
        similarity_fn: Optional (col_a, col_b) -> float [0,1] for semantic overlap.
        config: Optional PhiConfig for weight tuning.

    Returns:
        Dict with phi (float), components (dict), details (dict), interpretation (str).
    """
    if config is None:
        config = PhiConfig()

    adj = _build_adjacency(edges)

    # Component 1: Intra-collection link density
    ic_score, ic_details = intra_collection_density(nodes, adj)
    ic_normalized = min(1.0, ic_score * config.intra_density_scale)

    # Component 2: Cross-collection connectivity
    cc_score, cc_details = cross_collection_integration(nodes, edges)

    # Component 3: Semantic similarity across collections
    sc_score, sc_details = semantic_cross_collection(nodes, similarity_fn)

    # Component 4: Collection reachability
    cr_score, cr_reach = collection_reachability(nodes, adj)

    # Weighted composite
    phi = (
        config.w_intra_density * ic_normalized
        + config.w_cross_connectivity * cc_score
        + config.w_semantic_overlap * sc_score
        + config.w_reachability * cr_score
    )

    return {
        "phi": round(phi, 4),
        "components": {
            "intra_collection_density": round(ic_normalized, 4),
            "cross_collection_connectivity": round(cc_score, 4),
            "semantic_cross_collection": round(sc_score, 4),
            "collection_reachability": round(cr_score, 4),
        },
        "details": {
            "intra_density_per_collection": ic_details,
            "cross_edges": cc_details,
            "semantic_pairs": sc_details,
            "reachability": cr_reach,
        },
        "interpretation": _interpret(
            phi, ic_normalized, cc_score, sc_score, cr_score
        ),
    }


def _interpret(phi: float, ic: float, cc: float, sc: float, cr: float) -> str:
    """Human-readable interpretation of Phi result."""
    if phi < 0.15:
        level = "Fragmented -- memories are siloed with minimal integration."
    elif phi < 0.3:
        level = "Emerging -- some integration forming, mostly within modules."
    elif phi < 0.5:
        level = "Moderate -- meaningful integration across memory modules."
    elif phi < 0.7:
        level = "High -- memories form a well-connected, unified network."
    else:
        level = "Deep integration -- approaching unified information structure."

    components = {
        "intra-density": ic,
        "cross-collection": cc,
        "semantic overlap": sc,
        "reachability": cr,
    }
    weakest = min(components, key=components.get)
    strongest = max(components, key=components.get)

    return (
        f"Phi={phi:.3f}: {level} "
        f"Strongest: {strongest} ({components[strongest]:.3f}). "
        f"Weakest: {weakest} ({components[weakest]:.3f})."
    )


class PhiTracker:
    """Track Phi over time with rolling history.

    Lightweight alternative to the full Clarvis phi_metric.py: just stores
    snapshots in a list you can serialize however you like.
    """

    def __init__(self, max_history: int = 90):
        self.history: List[Dict] = []
        self.max_history = max_history

    def record(
        self,
        nodes: Dict[str, str],
        edges: List[Edge],
        similarity_fn: Optional[SimilarityFn] = None,
        config: Optional[PhiConfig] = None,
    ) -> Dict:
        """Compute Phi and append to history."""
        result = compute_phi(nodes, edges, similarity_fn, config)
        self.history.append({
            "phi": result["phi"],
            "components": result["components"],
        })
        self.history = self.history[-self.max_history:]
        return result

    def trend(self) -> Dict:
        """Analyze trend: increasing, stable, or decreasing."""
        if len(self.history) < 2:
            return {"trend": "insufficient_data", "measurements": len(self.history)}

        phis = [h["phi"] for h in self.history]
        first_half = phis[:len(phis) // 2]
        second_half = phis[len(phis) // 2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = avg_second - avg_first

        if delta > 0.05:
            direction = "increasing"
        elif delta < -0.05:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "trend": direction,
            "delta": round(delta, 4),
            "current": phis[-1],
            "min": round(min(phis), 4),
            "max": round(max(phis), 4),
            "measurements": len(self.history),
        }

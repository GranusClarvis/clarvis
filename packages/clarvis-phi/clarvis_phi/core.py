"""
Core Phi computation — backend-agnostic IIT-inspired integration metric.

Measures information integration across a partitioned graph system using
four components inspired by Tononi's Integrated Information Theory:

  1. Intra-partition density  — richness within modules
  2. Cross-partition bridges  — explicit connections between modules
  3. Semantic overlap         — latent similarity across boundaries
  4. Partition reachability   — global information flow topology

The composite Phi score (0-1) quantifies how much the system is "more than
the sum of its parts" — the hallmark of integrated information.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, TypedDict

Edge = Tuple[str, str, str]  # (from_id, to_id, edge_type)
SimilarityFn = Callable[[str, str], float]  # (partition_a, partition_b) -> 0-1


class PhiResult(TypedDict):
    phi: float
    components: Dict[str, float]
    details: Dict[str, object]
    interpretation: str
    partition_analysis: Dict[str, object]


@dataclass
class PhiConfig:
    """Tunable weights for the four Phi components."""

    w_intra_density: float = 0.20
    w_cross_connectivity: float = 0.20
    w_semantic_overlap: float = 0.35
    w_reachability: float = 0.25
    # Raw intra-density is typically 0-0.2 for sparse graphs; scale up
    intra_density_scale: float = 5.0


def _build_adjacency(edges: List[Edge]) -> Dict[str, Set[str]]:
    """Build bidirectional adjacency from edge list."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for f, t, _ in edges:
        adj[f].add(t)
        adj[t].add(f)
    return adj


def intra_collection_density(
    nodes: Dict[str, str],
    adj: Dict[str, Set[str]],
) -> Tuple[float, Dict[str, float]]:
    """
    Component 1: Within-partition link density.

    Richer internal connections = more integrated modules.
    Returns (average_density, per_partition_density).
    """
    part_nodes: Dict[str, Set[str]] = defaultdict(set)
    for nid, part in nodes.items():
        part_nodes[part].add(nid)

    densities = []
    per_partition: Dict[str, float] = {}

    for part, members in part_nodes.items():
        if part == "unknown" or len(members) < 2:
            continue

        total_links = 0
        for nid in members:
            total_links += sum(1 for n in adj.get(nid, set()) if n in members)

        actual_edges = total_links / 2  # bidirectional
        max_edges = len(members) * (len(members) - 1) / 2
        density = actual_edges / max_edges if max_edges > 0 else 0

        densities.append(density)
        per_partition[part] = round(density, 4)

    avg = sum(densities) / len(densities) if densities else 0.0
    return avg, per_partition


def cross_collection_integration(
    nodes: Dict[str, str],
    edges: List[Edge],
) -> Tuple[float, Dict[str, int]]:
    """
    Component 2: Cross-partition connectivity.

    Ratio of edges connecting different partitions to total edges.
    """
    if not edges:
        return 0.0, {"cross": 0, "same": 0, "total": 0}

    cross = 0
    same = 0
    for f, t, _ in edges:
        f_part = nodes.get(f, "unknown")
        t_part = nodes.get(t, "unknown")
        if f_part != t_part and f_part != "unknown" and t_part != "unknown":
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
    Component 3: Semantic overlap across partition boundaries.

    If a similarity_fn is provided, it's called for each pair of partitions
    and should return a 0-1 similarity score. Otherwise returns 0.
    """
    if similarity_fn is None:
        return 0.0, {}

    partitions = {p for p in set(nodes.values()) if p != "unknown"}
    if len(partitions) < 2:
        return 0.0, {}

    parts = sorted(partitions)
    pair_scores: List[float] = []
    pair_details: Dict[str, float] = {}

    for i, p1 in enumerate(parts):
        for p2 in parts[i + 1 :]:
            try:
                sim = similarity_fn(p1, p2)
                sim = max(0.0, min(1.0, sim))
                pair_scores.append(sim)
                pair_details[f"{p1} <-> {p2}"] = round(sim, 4)
            except Exception:
                pass

    overall = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
    return overall, pair_details


def collection_reachability(
    nodes: Dict[str, str],
    adj: Dict[str, Set[str]],
) -> Tuple[float, Dict[str, List[str]]]:
    """
    Component 4: Can information flow between all partition pairs via graph?

    Full integration = every partition reaches every other. Uses BFS on
    the partition-level adjacency graph.
    """
    part_adj: Dict[str, Set[str]] = defaultdict(set)
    for nid in adj:
        nid_part = nodes.get(nid, "unknown")
        if nid_part == "unknown":
            continue
        for neighbor in adj[nid]:
            n_part = nodes.get(neighbor, "unknown")
            if n_part != "unknown" and nid_part != n_part:
                part_adj[nid_part].add(n_part)

    active_parts = {p for p in set(nodes.values()) if p != "unknown"}
    if len(active_parts) < 2:
        return 1.0, {}

    # BFS reachability from each partition
    reachability: Dict[str, Set[str]] = {}
    for start in active_parts:
        visited: Set[str] = set()
        queue = [start]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            for neighbor in part_adj.get(curr, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        reachability[start] = visited - {start}

    total_pairs = 0
    connected_pairs = 0
    parts_list = list(active_parts)
    for i in range(len(parts_list)):
        for j in range(i + 1, len(parts_list)):
            total_pairs += 1
            if parts_list[j] in reachability.get(parts_list[i], set()):
                connected_pairs += 1

    score = connected_pairs / total_pairs if total_pairs > 0 else 0.0
    return score, {k: sorted(v) for k, v in reachability.items()}


def partition_analysis(
    nodes: Dict[str, str],
    edges: List[Edge],
) -> Dict[str, object]:
    """
    IIT partition analysis: estimate information loss under the Minimum
    Information Partition (MIP).

    For each partition, compute how much integration is lost if that partition
    is severed from the rest. The partition whose removal causes the *least*
    loss approximates the MIP — and that minimum loss is closer to true Phi.

    This is a practical approximation (exact MIP is NP-hard for large systems).
    """
    adj = _build_adjacency(edges)
    partitions = {p for p in set(nodes.values()) if p != "unknown"}

    if len(partitions) < 2:
        return {"mip_partition": None, "mip_loss": 0.0, "per_partition_loss": {}}

    # Count cross-partition edges per partition
    part_cross_edges: Dict[str, int] = defaultdict(int)
    total_cross = 0
    for f, t, _ in edges:
        fp = nodes.get(f, "unknown")
        tp = nodes.get(t, "unknown")
        if fp != tp and fp != "unknown" and tp != "unknown":
            part_cross_edges[fp] += 1
            part_cross_edges[tp] += 1
            total_cross += 1

    if total_cross == 0:
        return {"mip_partition": None, "mip_loss": 0.0, "per_partition_loss": {}}

    # Loss if we sever partition P = cross-edges touching P / total cross-edges
    per_loss: Dict[str, float] = {}
    for p in partitions:
        per_loss[p] = round(part_cross_edges.get(p, 0) / total_cross, 4)

    # MIP = partition whose removal causes minimum information loss
    mip = min(per_loss, key=per_loss.get)

    return {
        "mip_partition": mip,
        "mip_loss": per_loss[mip],
        "per_partition_loss": per_loss,
        "total_cross_edges": total_cross,
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
        "cross-partition": cc,
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


def compute_phi(
    nodes: Dict[str, str],
    edges: List[Edge],
    similarity_fn: Optional[SimilarityFn] = None,
    config: Optional[PhiConfig] = None,
) -> PhiResult:
    """
    Compute the composite Phi metric.

    Args:
        nodes: Mapping of node_id -> partition_name.
        edges: List of (from_id, to_id, edge_type) tuples.
        similarity_fn: Optional (part_a, part_b) -> float [0,1] for semantic overlap.
        config: Optional PhiConfig for weight tuning.

    Returns:
        PhiResult with phi, components, details, interpretation, partition_analysis.
    """
    if config is None:
        config = PhiConfig()

    adj = _build_adjacency(edges)

    # Component 1: Intra-partition link density
    ic_score, ic_details = intra_collection_density(nodes, adj)
    ic_normalized = min(1.0, ic_score * config.intra_density_scale)

    # Component 2: Cross-partition connectivity
    cc_score, cc_details = cross_collection_integration(nodes, edges)

    # Component 3: Semantic similarity across partitions
    sc_score, sc_details = semantic_cross_collection(nodes, similarity_fn)

    # Component 4: Partition reachability
    cr_score, cr_reach = collection_reachability(nodes, adj)

    # Weighted composite
    phi = (
        config.w_intra_density * ic_normalized
        + config.w_cross_connectivity * cc_score
        + config.w_semantic_overlap * sc_score
        + config.w_reachability * cr_score
    )

    # MIP analysis
    mip = partition_analysis(nodes, edges)

    return {
        "phi": round(phi, 4),
        "components": {
            "intra_collection_density": round(ic_normalized, 4),
            "cross_collection_connectivity": round(cc_score, 4),
            "semantic_cross_collection": round(sc_score, 4),
            "collection_reachability": round(cr_score, 4),
        },
        "details": {
            "intra_density_per_partition": ic_details,
            "cross_edges": cc_details,
            "semantic_pairs": sc_details,
            "reachability": cr_reach,
        },
        "partition_analysis": mip,
        "interpretation": _interpret(phi, ic_normalized, cc_score, sc_score, cr_score),
    }

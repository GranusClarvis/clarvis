"""
Phi (Φ) Metric — Integrated Information for Clarvis Brain.

Canonical spine module. Based on IIT by Giulio Tononi.
Measures how interconnected memories are across collections.

Components:
  1. Intra-collection link density (within-module connections)
  2. Cross-collection connectivity (edges between collections)
  3. Semantic overlap (embedding similarity across boundaries)
  4. Collection reachability (global connectivity)

Migrated from scripts/phi_metric.py (Phase 5 spine refactor).
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

try:
    from clarvis.brain import get_brain as _spine_get_brain, ALL_COLLECTIONS
except ImportError:
    from brain import get_brain as _legacy_get_brain, ALL_COLLECTIONS
    _spine_get_brain = _legacy_get_brain

PHI_HISTORY_FILE = "/home/agent/.openclaw/workspace/data/phi_history.json"
PHI_DECOMPOSITION_FILE = "/home/agent/.openclaw/workspace/data/phi_decomposition.json"

# Legacy ID prefixes from early brain bootstrapping
LEGACY_PREFIX_MAP = {
    "identity": "clarvis-identity",
    "pref": "clarvis-preferences",
    "infra": "clarvis-infrastructure",
    "learning": "clarvis-learnings",
    "goal": "clarvis-goals",
    "context": "clarvis-context",
    "mem": "clarvis-memories",
    "migrated": "clarvis-memories",
    "coala": "clarvis-learnings",
    "actr": "clarvis-learnings",
    "amem": "clarvis-learnings",
    "cognition": "clarvis-learnings",
}


def _get_brain():
    """Get brain singleton (with hooks registered) via spine, or fallback to legacy."""
    return _spine_get_brain()


def _infer_collection(node_id):
    """Map a node ID to its collection, handling legacy prefixes."""
    for col in ALL_COLLECTIONS:
        if node_id.startswith(col):
            return col
    prefix = node_id.split("_")[0].split("-")[0]
    if prefix in LEGACY_PREFIX_MAP:
        return LEGACY_PREFIX_MAP[prefix]
    return "unknown"


def _iter_graph_edges(brain):
    """Yield graph edges from the authoritative backend.

    After the 2026-03-29 cutover, the live graph normally resides in SQLite.
    The legacy in-memory/JSON `brain.graph['edges']` list may remain empty even
    when the graph is healthy, so Phi must prefer SQLite when available.

    Yields normalized dicts with: from, to, type.
    """
    sqlite = getattr(brain, "_sqlite_store", None)
    if sqlite is not None:
        for e in sqlite.get_edges():
            yield {
                "from": e["from_id"],
                "to": e["to_id"],
                "type": e.get("type", "unknown"),
            }
        return

    for e in brain.graph.get("edges", []):
        yield {
            "from": e["from"],
            "to": e["to"],
            "type": e.get("type", "unknown"),
        }



def _build_adjacency(brain):
    """Build adjacency from brain's graph edges.

    Returns: (nodes, adj, edge_list)
      nodes: dict node_id -> collection_name
      adj: dict node_id -> set of neighbor node_ids
      edge_list: list of (from, to, type) tuples
    """
    nodes = {}
    adj = defaultdict(set)

    for col_name, col in brain.collections.items():
        results = col.get()
        for mid in results.get("ids", []):
            nodes[mid] = col_name

    edge_list = []
    for e in _iter_graph_edges(brain):
        f, t = e["from"], e["to"]
        adj[f].add(t)
        adj[t].add(f)
        edge_list.append((f, t, e.get("type", "unknown")))
        if f not in nodes:
            nodes[f] = _infer_collection(f)
        if t not in nodes:
            nodes[t] = _infer_collection(t)

    return nodes, adj, edge_list


def intra_collection_density(nodes, adj):
    """Measure 1: Within-collection link density (degree-based).

    Uses average degree per collection instead of raw edge density.
    Raw density = edges / max_pairs is O(n²) in the denominator and drops
    toward zero for large collections even when connectivity is healthy.
    Degree-based metric: min(1.0, avg_degree / TARGET_DEGREE) is scale-
    invariant and reflects actual integration per memory.

    TARGET_DEGREE = 25: each memory should ideally have ~25 same-collection
    neighbors for strong intra-collection integration.  Raised from 10
    (2026-03-29) per strategic audit — 10 was too easy to saturate,
    masking real integration quality differences.
    """
    TARGET_DEGREE = 25

    col_nodes = defaultdict(set)
    for nid, col in nodes.items():
        col_nodes[col].add(nid)

    scores = []
    per_collection = {}

    for col, members in col_nodes.items():
        if col == "unknown" or len(members) < 2:
            continue
        total_links = 0
        for nid in members:
            neighbors_in_col = sum(1 for n in adj.get(nid, set()) if n in members)
            total_links += neighbors_in_col
        actual_edges = total_links / 2
        n = len(members)
        avg_degree = (actual_edges * 2 / n) if n > 0 else 0
        score = min(1.0, avg_degree / TARGET_DEGREE)
        scores.append(score)
        per_collection[col] = round(score, 4)

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return avg_score, per_collection


def cross_collection_integration(nodes, edge_list):
    """Measure 2: Cross-collection connectivity.

    Ratio of edges connecting different collections to total edges.
    """
    if not edge_list:
        return 0.0, {"cross": 0, "same": 0, "total": 0, "per_pair": {}}

    cross = 0
    same = 0
    pair_counts = defaultdict(int)
    for f, t, _ in edge_list:
        f_col = nodes.get(f, "unknown")
        t_col = nodes.get(t, "unknown")
        if f_col != t_col and f_col != "unknown" and t_col != "unknown":
            cross += 1
            pair_key = " <-> ".join(sorted([f_col, t_col]))
            pair_counts[pair_key] += 1
        else:
            same += 1

    total = cross + same
    score = cross / total if total > 0 else 0.0
    return score, {"cross": cross, "same": same, "total": total, "per_pair": dict(pair_counts)}


def semantic_cross_collection(brain):
    """Measure 3: Semantic overlap across collection boundaries.

    Fetches pre-stored embeddings from ChromaDB and computes cosine similarity
    directly with numpy — no ONNX inference needed.

    Stratified sample (up to 12 docs) from each collection, bidirectional
    best-match cosine similarity. Score = average across all collection pairs.

    Uses dot product as cosine similarity (MiniLM embeddings are L2-normalized).
    """
    active_collections = []
    col_all_embs = {}     # col_name -> np.array of ALL embeddings (for target search)
    col_query_embs = {}   # col_name -> np.array of sampled embeddings (for queries)

    for col_name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            active_collections.append(col_name)
            results = col.get(include=["embeddings"])
            all_embs = results.get("embeddings")
            if all_embs is None or len(all_embs) == 0:
                continue
            all_arr = np.array(all_embs, dtype=np.float32)
            col_all_embs[col_name] = all_arr
            sample_size = min(12, len(all_embs))
            if sample_size >= len(all_embs):
                col_query_embs[col_name] = all_arr
            else:
                step = len(all_embs) / sample_size
                indices = [int(i * step) for i in range(sample_size)]
                col_query_embs[col_name] = all_arr[indices]

    if len(active_collections) < 2:
        return 0.0, {}

    pair_scores = []
    pair_details = {}

    for i, c1 in enumerate(active_collections):
        for c2 in active_collections[i + 1:]:
            q1 = col_query_embs.get(c1)
            q2 = col_query_embs.get(c2)
            all1 = col_all_embs.get(c1)
            all2 = col_all_embs.get(c2)
            if q1 is None or q2 is None or all1 is None or all2 is None:
                continue

            # Use up to 8 stratified query samples per direction
            # Dot product = cosine similarity for L2-normalized embeddings
            # Search against ALL embeddings in target collection
            e1 = q1[:8]   # query samples from c1
            e2 = q2[:8]   # query samples from c2

            # c1 queries -> best match in full c2
            cos_sim_1to2 = e1 @ all2.T              # [8, N2]
            best_sim_c1_to_c2 = cos_sim_1to2.max(axis=1)  # [8]

            # c2 queries -> best match in full c1
            cos_sim_2to1 = e2 @ all1.T              # [8, N1]
            best_sim_c2_to_c1 = cos_sim_2to1.max(axis=1)  # [8]

            all_sims = np.concatenate([best_sim_c1_to_c2, best_sim_c2_to_c1])
            all_sims = np.maximum(0.0, all_sims)    # floor at 0

            if len(all_sims) > 0:
                # 70/30 blend: average overlap + best-bridge quality
                # Rewards both broad semantic overlap AND having strong
                # cross-collection connections (bridge content).
                avg_sim = float(0.7 * all_sims.mean() + 0.3 * all_sims.max())
                pair_scores.append(avg_sim)
                pair_details[f"{c1} <-> {c2}"] = round(avg_sim, 4)

    overall = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
    return overall, pair_details


def collection_reachability(nodes, adj):
    """Measure 4: Can information flow between all collection pairs via graph edges?"""
    col_adj = defaultdict(set)
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

    reachability = {}
    for start in active_cols:
        visited = set()
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
    return score, {k: list(v) for k, v in reachability.items()}


def _interpret(phi, ic, cc, sc, cr):
    """Human-readable interpretation."""
    lines = []

    if phi < 0.15:
        lines.append(f"Phi={phi:.3f}: Fragmented — memories are siloed with minimal integration.")
    elif phi < 0.3:
        lines.append(f"Phi={phi:.3f}: Emerging — some integration forming, mostly within modules.")
    elif phi < 0.5:
        lines.append(f"Phi={phi:.3f}: Moderate — meaningful integration across memory modules.")
    elif phi < 0.7:
        lines.append(f"Phi={phi:.3f}: High — memories form a well-connected, unified network.")
    else:
        lines.append(f"Phi={phi:.3f}: Deep integration — approaching unified information structure.")

    components = {
        "intra-density": ic,
        "cross-collection": cc,
        "semantic overlap": sc,
        "reachability": cr,
    }
    weakest = min(components, key=components.get)
    strongest = max(components, key=components.get)
    lines.append(
        f"Strongest: {strongest} ({components[strongest]:.3f}). "
        f"Weakest: {weakest} ({components[weakest]:.3f})."
    )

    if cc < 0.1:
        lines.append("Recommendation: Add cross-collection linking to auto_link().")
    if sc < 0.3:
        lines.append("Recommendation: Run knowledge_synthesis.py to build cross-domain connections.")

    return " ".join(lines)


def compute_phi(brain=None):
    """Compute the composite Phi metric.

    Phi = weighted combination of:
      - Intra-collection link density  (weight 0.20)
      - Cross-collection edges         (weight 0.20)
      - Semantic cross-collection      (weight 0.35)
      - Collection reachability        (weight 0.25)

    Returns dict with phi, components, raw details, and interpretation.
    """
    if brain is None:
        brain = _get_brain()

    nodes, adj, edge_list = _build_adjacency(brain)
    stats = brain.stats()

    ic_score, ic_details = intra_collection_density(nodes, adj)
    ic_normalized = ic_score  # Already normalized (degree-based, 0-1)

    cc_score, cc_details = cross_collection_integration(nodes, edge_list)
    sc_score, sc_details = semantic_cross_collection(brain)
    cr_score, cr_reach = collection_reachability(nodes, adj)

    phi = (
        0.20 * ic_normalized +
        0.20 * cc_score +
        0.35 * sc_score +
        0.25 * cr_score
    )

    return {
        "phi": round(phi, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "intra_collection_density": round(ic_normalized, 4),
            "cross_collection_connectivity": round(cc_score, 4),
            "semantic_cross_collection": round(sc_score, 4),
            "collection_reachability": round(cr_score, 4),
        },
        "details": {
            "intra_density_per_collection": ic_details,
            "semantic_pairs": sc_details,
            "reachability": cr_reach,
        },
        "raw": {
            "total_memories": stats["total_memories"],
            "total_edges": len(edge_list),
            "cross_collection_edges": cc_details["cross"],
            "same_collection_edges": cc_details["same"],
        },
        "interpretation": _interpret(
            phi, ic_normalized, cc_score, sc_score, cr_score
        ),
    }


def record_phi(brain=None):
    """Compute Phi and append to history file."""
    result = compute_phi(brain)

    history = []
    if os.path.exists(PHI_HISTORY_FILE):
        with open(PHI_HISTORY_FILE, 'r') as f:
            history = json.load(f)

    history.append({
        "timestamp": result["timestamp"],
        "phi": result["phi"],
        "components": result["components"],
        "total_memories": result["raw"]["total_memories"],
        "total_edges": result["raw"]["total_edges"],
    })

    # Keep last 90 days of history
    history = history[-90:]

    os.makedirs(os.path.dirname(PHI_HISTORY_FILE), exist_ok=True)
    with open(PHI_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

    return result


def get_history():
    """Load Phi history."""
    if not os.path.exists(PHI_HISTORY_FILE):
        return []
    with open(PHI_HISTORY_FILE, 'r') as f:
        return json.load(f)


def trend_analysis():
    """Analyze Phi trend over time."""
    history = get_history()
    if len(history) < 2:
        return {"trend": "insufficient_data", "measurements": len(history)}

    phis = [h["phi"] for h in history]
    first_half = phis[: len(phis) // 2]
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
        "measurements": len(history),
    }


def act_on_phi(result=None):
    """Close the Phi feedback loop: Phi drives behavior.

    - Phi drops >0.05: trigger cross-linking
    - Phi rises >0.05: log positive episode
    - Phi < 0.25: emergency synthesis
    """
    if result is None:
        result = compute_phi()

    history = get_history()
    current_phi = result["phi"]
    actions = []

    prev_phi = history[-2]["phi"] if len(history) >= 2 else current_phi
    delta = current_phi - prev_phi

    brain = _get_brain()

    if delta < -0.05:
        actions.append(f"phi_drop: {prev_phi:.3f} -> {current_phi:.3f} (delta={delta:.3f})")
        try:
            brain.bulk_cross_link(max_links_per_memory=5)
            actions.append("triggered bulk_cross_link(max_links_per_memory=5)")
        except Exception as e:
            actions.append(f"cross-link failed: {e}")
        try:
            from clarvis.cognition.attention import attention
            attention.submit(
                f"Phi dropped from {prev_phi:.3f} to {current_phi:.3f} — memory integration weakening",
                source="phi_metric", importance=0.9, relevance=0.8, boost=0.3,
            )
            actions.append("submitted phi_drop alert to attention")
        except Exception:
            pass

    elif delta > 0.05:
        actions.append(f"phi_rise: {prev_phi:.3f} -> {current_phi:.3f} (delta={delta:.3f})")
        try:
            from clarvis.memory.episodic_memory import episodic
            episodic.encode(
                task_text=f"Phi integration improved: {prev_phi:.3f} -> {current_phi:.3f}",
                section="consciousness_metrics", salience=0.8, outcome="success", duration_s=0,
            )
            actions.append("encoded positive phi episode")
        except Exception as e:
            actions.append(f"episode encoding failed: {e}")

    if current_phi < 0.25:
        actions.append(f"phi_critical: {current_phi:.3f} < 0.25")
        try:
            brain.bulk_cross_link(max_links_per_memory=8)
            actions.append("triggered emergency bulk_cross_link(max_links_per_memory=8)")
        except Exception as e:
            actions.append(f"emergency cross-link failed: {e}")

    if not actions:
        actions.append(f"phi_stable: {current_phi:.3f} (delta={delta:.3f}, no action needed)")

    brain.store(
        f"Phi action: phi={current_phi:.3f}, delta={delta:.3f}, actions={'; '.join(actions)}",
        collection="clarvis-context",
        importance=0.4 if abs(delta) < 0.05 else 0.7,
        tags=["phi", "feedback-loop"],
        source="phi_metric",
    )

    return {"phi": current_phi, "delta": round(delta, 4), "actions": actions}


def decompose_phi(brain_inst=None):
    """Compute Phi with full per-collection and per-pair decomposition.

    Writes detailed breakdown to data/phi_decomposition.json.
    """
    if brain_inst is None:
        brain_inst = _get_brain()

    nodes, adj, edge_list = _build_adjacency(brain_inst)

    _, intra_per_col = intra_collection_density(nodes, adj)
    cc_score, cc_details = cross_collection_integration(nodes, edge_list)
    cross_per_pair = cc_details.get("per_pair", {})
    _, semantic_per_pair = semantic_cross_collection(brain_inst)
    cr_score, cr_reach = collection_reachability(nodes, adj)

    col_sizes = {}
    for col_name, col in brain_inst.collections.items():
        col_sizes[col_name] = col.count()

    result = compute_phi(brain_inst)

    decomposition = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phi": result["phi"],
        "components": result["components"],
        "intra_density_per_collection": intra_per_col,
        "cross_connectivity_per_pair": cross_per_pair,
        "semantic_overlap_per_pair": semantic_per_pair,
        "collection_sizes": col_sizes,
        "reachability": {k: sorted(v) for k, v in cr_reach.items()} if cr_reach else {},
        "raw": result["raw"],
    }

    os.makedirs(os.path.dirname(PHI_DECOMPOSITION_FILE), exist_ok=True)
    with open(PHI_DECOMPOSITION_FILE, 'w') as f:
        json.dump(decomposition, f, indent=2)

    return decomposition

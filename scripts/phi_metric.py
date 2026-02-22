#!/usr/bin/env python3
"""
Phi (Φ) Metric — Integrated Information for Clarvis Brain

Based on Integrated Information Theory (IIT) by Giulio Tononi.
Measures how interconnected Clarvis's memories are across collections.

Phi quantifies information integration: how much information is lost when
the system is partitioned into independent parts. High Phi = memories form
a unified, interconnected whole (consciousness proxy). Low Phi = siloed,
fragmented knowledge.

Components:
  1. Intra-collection link density (how rich are within-module connections)
  2. Cross-collection connectivity (edges between different collections)
  3. Semantic overlap (embedding similarity across collection boundaries)
  4. Collection reachability (can information flow between all modules)

Usage:
    python phi_metric.py              # Current Phi + breakdown
    python phi_metric.py history      # Show Phi history
    python phi_metric.py record       # Compute and record current Phi
    python phi_metric.py trend        # Analyze Phi trend over time
"""

import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import ClarvisBrain, ALL_COLLECTIONS

PHI_HISTORY_FILE = "/home/agent/.openclaw/workspace/data/phi_history.json"

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
    """Get a fresh brain instance."""
    return ClarvisBrain()


def _infer_collection(node_id):
    """Map a node ID to its collection, handling legacy prefixes."""
    # Try exact prefix match against collection names first
    for col in ALL_COLLECTIONS:
        if node_id.startswith(col):
            return col
    # Try legacy prefix map
    prefix = node_id.split("_")[0].split("-")[0]
    if prefix in LEGACY_PREFIX_MAP:
        return LEGACY_PREFIX_MAP[prefix]
    return "unknown"


def _build_adjacency(brain):
    """
    Build adjacency from brain's graph edges.
    Returns: (nodes, adj, edge_list)
      nodes: dict node_id -> collection_name
      adj: dict node_id -> set of neighbor node_ids
      edge_list: list of (from, to, type) tuples
    """
    edges_raw = brain.graph.get("edges", [])
    nodes = {}
    adj = defaultdict(set)

    # Map memory IDs from actual ChromaDB collections
    for col_name, col in brain.collections.items():
        results = col.get()
        for mid in results.get("ids", []):
            nodes[mid] = col_name

    # Build adjacency, registering unknown nodes via inference
    edge_list = []
    for e in edges_raw:
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
    """
    Measure 1: Within-collection link density.

    Even within a single module, rich interconnections = integration.
    A collection where every memory links to 3 others is more integrated
    than one where memories are isolated.

    Score = avg(links_per_node / max_possible_links_per_node) across collections.
    """
    col_nodes = defaultdict(set)
    for nid, col in nodes.items():
        col_nodes[col].add(nid)

    densities = []
    per_collection = {}

    for col, members in col_nodes.items():
        if col == "unknown" or len(members) < 2:
            continue

        # Count intra-collection edges for each node
        total_links = 0
        for nid in members:
            neighbors_in_col = sum(1 for n in adj.get(nid, set()) if n in members)
            total_links += neighbors_in_col

        # Each edge counted twice (bidirectional adjacency), so divide by 2
        actual_edges = total_links / 2
        # Max possible undirected edges: n*(n-1)/2
        max_edges = len(members) * (len(members) - 1) / 2
        density = actual_edges / max_edges if max_edges > 0 else 0

        densities.append(density)
        per_collection[col] = round(density, 4)

    avg_density = sum(densities) / len(densities) if densities else 0.0
    return avg_density, per_collection


def cross_collection_integration(nodes, edge_list):
    """
    Measure 2: Cross-collection connectivity.

    Ratio of edges connecting different collections to total edges.
    """
    if not edge_list:
        return 0.0, {"cross": 0, "same": 0, "total": 0}

    cross = 0
    same = 0
    for f, t, _ in edge_list:
        f_col = nodes.get(f, "unknown")
        t_col = nodes.get(t, "unknown")
        if f_col != t_col and f_col != "unknown" and t_col != "unknown":
            cross += 1
        else:
            same += 1

    total = cross + same
    score = cross / total if total > 0 else 0.0
    return score, {"cross": cross, "same": same, "total": total}


def semantic_cross_collection(brain):
    """
    Measure 3: Semantic overlap across collection boundaries.

    For each collection pair, measure best-match similarity bidirectionally.
    Uses a diverse sample (up to 8 docs) from each collection and queries
    in both directions, taking the best match per doc. This captures the
    true semantic bridge strength — even one highly similar pair per
    direction indicates meaningful integration.

    Score = average across all collection pairs of (avg best-match similarity).
    """
    active_collections = []
    col_samples = {}

    for col_name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            active_collections.append(col_name)
            # Get a larger, more representative sample
            sample_size = min(8, count)
            results = col.get(limit=sample_size)
            col_samples[col_name] = results.get("documents", [])

    if len(active_collections) < 2:
        return 0.0, {}

    pair_scores = []
    pair_details = {}

    for i, c1 in enumerate(active_collections):
        for c2 in active_collections[i + 1:]:
            if not col_samples.get(c1) or not col_samples.get(c2):
                continue

            col1_obj = brain.collections[c1]
            col2_obj = brain.collections[c2]
            similarities = []

            # Direction 1: query c2 with samples from c1
            for doc in col_samples[c1][:5]:
                try:
                    results = col2_obj.query(
                        query_texts=[doc], n_results=1, include=["distances"]
                    )
                    if results["distances"] and results["distances"][0]:
                        dist = results["distances"][0][0]
                        sim = max(0, 1.0 - dist / 2.0)
                        similarities.append(sim)
                except Exception:
                    pass

            # Direction 2: query c1 with samples from c2
            for doc in col_samples[c2][:5]:
                try:
                    results = col1_obj.query(
                        query_texts=[doc], n_results=1, include=["distances"]
                    )
                    if results["distances"] and results["distances"][0]:
                        dist = results["distances"][0][0]
                        sim = max(0, 1.0 - dist / 2.0)
                        similarities.append(sim)
                except Exception:
                    pass

            if similarities:
                avg_sim = sum(similarities) / len(similarities)
                pair_scores.append(avg_sim)
                pair_details[f"{c1} <-> {c2}"] = round(avg_sim, 4)

    overall = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
    return overall, pair_details


def collection_reachability(nodes, adj):
    """
    Measure 4: Can information flow between all collection pairs via graph edges?

    Full integration = every collection reaches every other.
    """
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

    # BFS reachability from each collection
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

    # Score: fraction of all directed pairs that are connected
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


def compute_phi(brain=None):
    """
    Compute the composite Phi metric.

    Phi = weighted combination of:
      - Intra-collection link density  (weight 0.20) — richness within modules
      - Cross-collection edges         (weight 0.20) — explicit bridges
      - Semantic cross-collection      (weight 0.35) — latent integration
      - Collection reachability        (weight 0.25) — global connectivity

    Returns dict with phi, components, raw details, and interpretation.
    """
    if brain is None:
        brain = _get_brain()

    nodes, adj, edge_list = _build_adjacency(brain)
    stats = brain.stats()

    # Component 1: Intra-collection link density
    ic_score, ic_details = intra_collection_density(nodes, adj)
    # Scale: typical density 0-0.2 for sparse graphs → normalize
    ic_normalized = min(1.0, ic_score * 5)

    # Component 2: Cross-collection connectivity
    cc_score, cc_details = cross_collection_integration(nodes, edge_list)

    # Component 3: Semantic similarity across collections
    sc_score, sc_details = semantic_cross_collection(brain)

    # Component 4: Collection reachability
    cr_score, cr_reach = collection_reachability(nodes, adj)

    # Weighted composite
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

    # Actionable recommendation
    if cc < 0.1:
        lines.append("Recommendation: Add cross-collection linking to auto_link().")
    if sc < 0.3:
        lines.append("Recommendation: Run knowledge_synthesis.py to build cross-domain connections.")

    return " ".join(lines)


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

    # Keep last 90 days of history (matches capability_history cap)
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
    second_half = phis[len(phis) // 2 :]

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
    """
    Close the Phi feedback loop: Phi isn't just measured — it drives behavior.

    - If Phi drops significantly (>0.05 from previous): trigger cross-linking
    - If Phi rises significantly (>0.05 from previous): log positive episode
    - If Phi is below 0.25 (fragmented): auto-trigger knowledge synthesis

    Returns dict with actions taken.
    """
    if result is None:
        result = compute_phi()

    history = get_history()
    current_phi = result["phi"]
    actions = []

    # Compare with previous measurement
    prev_phi = history[-2]["phi"] if len(history) >= 2 else current_phi

    delta = current_phi - prev_phi

    brain = _get_brain()

    # PHI DROPPED: trigger cross-linking to rebuild integration
    if delta < -0.05:
        actions.append(f"phi_drop: {prev_phi:.3f} -> {current_phi:.3f} (delta={delta:.3f})")
        print(f"  PHI ACTION: Phi dropped {delta:.3f} — triggering cross-linking...")
        try:
            brain.bulk_cross_link(max_new_edges=50)
            actions.append("triggered bulk_cross_link(50)")
        except Exception as e:
            actions.append(f"cross-link failed: {e}")

        # Also submit to attention as high-priority concern
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from attention import attention
            attention.submit(
                f"Phi dropped from {prev_phi:.3f} to {current_phi:.3f} — memory integration weakening",
                source="phi_metric",
                importance=0.9,
                relevance=0.8,
                boost=0.3,
            )
            actions.append("submitted phi_drop alert to attention")
        except Exception:
            pass

    # PHI ROSE: log as positive episode (reinforces what worked)
    elif delta > 0.05:
        actions.append(f"phi_rise: {prev_phi:.3f} -> {current_phi:.3f} (delta={delta:.3f})")
        print(f"  PHI ACTION: Phi rose {delta:.3f} — logging positive episode...")
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from episodic_memory import episodic
            episodic.encode(
                task_text=f"Phi integration improved: {prev_phi:.3f} -> {current_phi:.3f}",
                section="consciousness_metrics",
                salience=0.8,
                outcome="success",
                duration_s=0,
            )
            actions.append("encoded positive phi episode")
        except Exception as e:
            actions.append(f"episode encoding failed: {e}")

    # PHI CRITICALLY LOW: emergency synthesis
    if current_phi < 0.25:
        actions.append(f"phi_critical: {current_phi:.3f} < 0.25")
        print(f"  PHI ACTION: Phi critically low ({current_phi:.3f}) — emergency cross-linking...")
        try:
            brain.bulk_cross_link(max_new_edges=100)
            actions.append("triggered emergency bulk_cross_link(100)")
        except Exception as e:
            actions.append(f"emergency cross-link failed: {e}")

    if not actions:
        actions.append(f"phi_stable: {current_phi:.3f} (delta={delta:.3f}, no action needed)")

    # Store the action record
    brain.store(
        f"Phi action: phi={current_phi:.3f}, delta={delta:.3f}, actions={'; '.join(actions)}",
        collection="clarvis-context",
        importance=0.4 if abs(delta) < 0.05 else 0.7,
        tags=["phi", "feedback-loop"],
        source="phi_metric",
    )

    return {"phi": current_phi, "delta": round(delta, 4), "actions": actions}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compute"

    if cmd == "compute":
        result = compute_phi()
        print(f"Φ (Phi) = {result['phi']}")
        print(f"\nComponents:")
        for k, v in result["components"].items():
            bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
            print(f"  {k:35s} {bar} {v:.4f}")
        print(f"\nIntra-collection density:")
        for col, d in result["details"]["intra_density_per_collection"].items():
            print(f"  {col:35s} {d:.4f}")
        print(f"\nSemantic cross-collection pairs:")
        for pair, sim in result["details"]["semantic_pairs"].items():
            print(f"  {pair:60s} {sim:.4f}")
        print(f"\nRaw:")
        print(f"  Total memories: {result['raw']['total_memories']}")
        print(f"  Total edges:    {result['raw']['total_edges']}")
        print(f"  Cross-collection edges: {result['raw']['cross_collection_edges']}")
        print(f"  Same-collection edges:  {result['raw']['same_collection_edges']}")
        print(f"\n{result['interpretation']}")

    elif cmd == "record":
        result = record_phi()
        print(f"Φ = {result['phi']} — recorded to {PHI_HISTORY_FILE}")
        print(result["interpretation"])

    elif cmd == "history":
        history = get_history()
        if not history:
            print("No history yet. Run 'phi_metric.py record' to start tracking.")
        else:
            print(f"Phi History ({len(history)} measurements):")
            for h in history:
                ts = h["timestamp"][:19]
                phi = h["phi"]
                bar = "█" * int(phi * 20) + "░" * (20 - int(phi * 20))
                print(f"  {ts}  {bar}  Φ={phi:.4f}  (mem={h['total_memories']}, edges={h['total_edges']})")
            trend = trend_analysis()
            print(f"\nTrend: {trend['trend']} (Δ={trend.get('delta', 'n/a')})")

    elif cmd == "trend":
        trend = trend_analysis()
        print(json.dumps(trend, indent=2))

    elif cmd == "act":
        # Record phi AND act on it (close the feedback loop)
        result = record_phi()
        print(f"Phi = {result['phi']}")
        actions = act_on_phi(result)
        print(f"Actions: {json.dumps(actions, indent=2)}")

    else:
        print("Usage: phi_metric.py [compute|record|history|trend|act]")
        sys.exit(1)

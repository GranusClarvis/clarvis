"""
Clarvis adapter — wires ClarvisPhi into the Clarvis brain system.

Provides a drop-in replacement for scripts/phi_metric.py using the
standalone package, with brain-backed data loading and feedback loops.

Usage:
    from clarvis_phi.clarvis_adapter import compute_clarvis_phi, act_on_phi
    result = compute_clarvis_phi()
    actions = act_on_phi(result)
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from clarvis_phi.core import Edge, SimilarityFn, compute_phi
from clarvis_phi.tracker import PhiTracker

WORKSPACE = "/home/agent/.openclaw/workspace"
PHI_HISTORY = os.path.join(WORKSPACE, "data/phi_history.json")
SCRIPTS_DIR = os.path.join(WORKSPACE, "scripts")

ALL_COLLECTIONS = [
    "clarvis-identity",
    "clarvis-preferences",
    "clarvis-learnings",
    "clarvis-infrastructure",
    "clarvis-goals",
    "clarvis-context",
    "clarvis-memories",
    "clarvis-procedures",
    "autonomous-learning",
    "clarvis-episodes",
]

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
    """Import and return ClarvisBrain."""
    sys.path.insert(0, SCRIPTS_DIR)
    from brain import ClarvisBrain
    return ClarvisBrain()


def _infer_collection(node_id: str) -> str:
    """Map a node ID to its collection, handling legacy prefixes."""
    for col in ALL_COLLECTIONS:
        if node_id.startswith(col):
            return col
    prefix = node_id.split("_")[0].split("-")[0]
    return LEGACY_PREFIX_MAP.get(prefix, "unknown")


def _load_graph(brain) -> Tuple[Dict[str, str], List[Edge]]:
    """Extract nodes and edges from ClarvisBrain."""
    edges_raw = brain.graph.get("edges", [])
    nodes: Dict[str, str] = {}

    for col_name, col in brain.collections.items():
        results = col.get()
        for mid in results.get("ids", []):
            nodes[mid] = col_name

    edge_list: List[Edge] = []
    for e in edges_raw:
        f, t = e["from"], e["to"]
        edge_list.append((f, t, e.get("type", "unknown")))
        if f not in nodes:
            nodes[f] = _infer_collection(f)
        if t not in nodes:
            nodes[t] = _infer_collection(t)

    return nodes, edge_list


def _make_similarity_fn(brain) -> SimilarityFn:
    """Create a similarity function using ChromaDB queries."""
    col_samples: Dict[str, list] = {}
    for col_name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            sample_size = min(8, count)
            results = col.get(limit=sample_size)
            col_samples[col_name] = results.get("documents", [])

    def similarity_fn(col_a: str, col_b: str) -> float:
        if col_a not in col_samples or col_b not in col_samples:
            return 0.0
        if not col_samples[col_a] or not col_samples[col_b]:
            return 0.0

        similarities = []
        col_a_obj = brain.collections.get(col_a)
        col_b_obj = brain.collections.get(col_b)
        if not col_a_obj or not col_b_obj:
            return 0.0

        # Direction 1: query col_b with samples from col_a
        for doc in col_samples[col_a][:5]:
            try:
                results = col_b_obj.query(
                    query_texts=[doc], n_results=1, include=["distances"]
                )
                if results["distances"] and results["distances"][0]:
                    dist = results["distances"][0][0]
                    similarities.append(max(0, 1.0 - dist / 2.0))
            except Exception:
                pass

        # Direction 2: query col_a with samples from col_b
        for doc in col_samples[col_b][:5]:
            try:
                results = col_a_obj.query(
                    query_texts=[doc], n_results=1, include=["distances"]
                )
                if results["distances"] and results["distances"][0]:
                    dist = results["distances"][0][0]
                    similarities.append(max(0, 1.0 - dist / 2.0))
            except Exception:
                pass

        return sum(similarities) / len(similarities) if similarities else 0.0

    return similarity_fn


def compute_clarvis_phi(brain=None) -> Dict:
    """Compute Phi from the live Clarvis brain. Drop-in for phi_metric.compute_phi()."""
    if brain is None:
        brain = _get_brain()

    nodes, edges = _load_graph(brain)
    sim_fn = _make_similarity_fn(brain)

    result = compute_phi(nodes, edges, similarity_fn=sim_fn)

    stats = brain.stats()
    result["raw"] = {
        "total_memories": stats["total_memories"],
        "total_edges": len(edges),
        "cross_collection_edges": result["details"]["cross_edges"]["cross"],
        "same_collection_edges": result["details"]["cross_edges"]["same"],
    }

    return result


def record_clarvis_phi(brain=None) -> Dict:
    """Compute Phi and record to history file."""
    from datetime import datetime, timezone

    result = compute_clarvis_phi(brain)
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    history = []
    if os.path.exists(PHI_HISTORY):
        with open(PHI_HISTORY, "r") as f:
            history = json.load(f)

    history.append({
        "timestamp": result["timestamp"],
        "phi": result["phi"],
        "components": result["components"],
        "total_memories": result["raw"]["total_memories"],
        "total_edges": result["raw"]["total_edges"],
    })
    history = history[-90:]

    os.makedirs(os.path.dirname(PHI_HISTORY), exist_ok=True)
    with open(PHI_HISTORY, "w") as f:
        json.dump(history, f, indent=2)

    return result


def act_on_phi(result: Optional[Dict] = None) -> Dict:
    """Close the Phi feedback loop. Drop-in for phi_metric.act_on_phi()."""
    if result is None:
        result = compute_clarvis_phi()

    history = []
    if os.path.exists(PHI_HISTORY):
        with open(PHI_HISTORY, "r") as f:
            history = json.load(f)

    current_phi = result["phi"]
    prev_phi = history[-2]["phi"] if len(history) >= 2 else current_phi
    delta = current_phi - prev_phi
    actions = []

    brain = _get_brain()

    if delta < -0.05:
        actions.append(f"phi_drop: {prev_phi:.3f} -> {current_phi:.3f}")
        try:
            brain.bulk_cross_link(max_links_per_memory=5)
            actions.append("triggered bulk_cross_link(5)")
        except Exception as e:
            actions.append(f"cross-link failed: {e}")

    elif delta > 0.05:
        actions.append(f"phi_rise: {prev_phi:.3f} -> {current_phi:.3f}")
        try:
            sys.path.insert(0, SCRIPTS_DIR)
            from episodic_memory import episodic
            episodic.encode(
                task_text=f"Phi improved: {prev_phi:.3f} -> {current_phi:.3f}",
                section="consciousness_metrics",
                salience=0.8,
                outcome="success",
                duration_s=0,
            )
            actions.append("encoded positive phi episode")
        except Exception:
            pass

    if current_phi < 0.25:
        actions.append(f"phi_critical: {current_phi:.3f}")
        try:
            brain.bulk_cross_link(max_links_per_memory=8)
            actions.append("triggered emergency bulk_cross_link(8)")
        except Exception as e:
            actions.append(f"emergency cross-link failed: {e}")

    if not actions:
        actions.append(f"phi_stable: {current_phi:.3f} (delta={delta:.3f})")

    brain.store(
        f"Phi action: phi={current_phi:.3f}, delta={delta:.3f}, actions={'; '.join(actions)}",
        collection="clarvis-context",
        importance=0.4 if abs(delta) < 0.05 else 0.7,
        tags=["phi", "feedback-loop"],
        source="clarvis_phi",
    )

    return {"phi": current_phi, "delta": round(delta, 4), "actions": actions}


def get_tracker() -> PhiTracker:
    """Get a PhiTracker wired to Clarvis history file."""
    return PhiTracker(PHI_HISTORY)

#!/usr/bin/env python3
"""
Consciousness Theory Ablation Harness

Systematically disables GWT broadcast / IIT integration / HOT monitoring
and measures functional degradation. Based on Butlin/Chalmers (2023) indicator
properties and arXiv:2512.19155 ablation methodology.

Layers tested:
  1. GWT Broadcast  — attention spotlight → brain context (Global Workspace Theory)
  2. IIT Integration — cross-collection graph edges + semantic overlap (Integrated Info)
  3. HOT Monitoring  — meta-cognition awareness tracking (Higher-Order Thought)

Each ablation disables one layer, runs functional probes, and measures impact.
Result: per-layer degradation scores showing which layers are complementary
vs. redundant.

Usage:
    python3 ablation_harness.py              # Run full ablation suite
    python3 ablation_harness.py --layer gwt  # Ablate only GWT
    python3 ablation_harness.py --layer iit  # Ablate only IIT
    python3 ablation_harness.py --layer hot  # Ablate only HOT
    python3 ablation_harness.py --report     # Show last results
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
_workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS_FILE = os.path.join(_workspace, "data", "ablation_results.json")
HISTORY_FILE = os.path.join(_workspace, "data", "ablation_history.jsonl")

# Probe queries spanning different cognitive domains
PROBE_QUERIES = [
    "How does the heartbeat pipeline work?",
    "What is the current Phi score and trend?",
    "How are memories consolidated across collections?",
    "What cron jobs run during maintenance window?",
    "How does attention salience scoring work?",
    "What is the agent orchestrator architecture?",
    "How does episodic memory encoding function?",
    "What are the current evolution queue priorities?",
]


def _safe_import(module_path, fallback=None):
    """Import with fallback for resilience."""
    try:
        parts = module_path.rsplit(".", 1)
        mod = __import__(parts[0], fromlist=[parts[1]] if len(parts) > 1 else [])
        return getattr(mod, parts[1]) if len(parts) > 1 else mod
    except (ImportError, AttributeError):
        return fallback


# ── Functional Probes ─────────────────────────────────────────────


def probe_retrieval_quality(brain):
    """Probe 1: Search retrieval quality across collections.

    Returns: dict with mean_results, mean_distance, coverage (fraction of
    collections that return results).
    Uses a subset of probes to stay within time budget (~7.5s per query).
    """
    results_counts = []
    distances = []
    collections_hit = set()

    # Use only 3 probes to keep within time budget (brain queries ~7.5s each)
    for query in PROBE_QUERIES[:3]:
        try:
            hits = brain.recall(query, n=5)
            results_counts.append(len(hits))
            for hit in hits:
                if "distance" in hit:
                    distances.append(hit["distance"])
                col = hit.get("collection", "unknown")
                collections_hit.add(col)
        except Exception:
            results_counts.append(0)

    total_collections = len(brain.collections)
    return {
        "mean_results": sum(results_counts) / max(len(results_counts), 1),
        "mean_distance": sum(distances) / max(len(distances), 1) if distances else 1.0,
        "coverage": len(collections_hit) / max(total_collections, 1),
        "total_hits": sum(results_counts),
    }


def probe_phi_components(brain):
    """Probe 2: Phi sub-components (measures integration directly).

    Computes graph-based components directly (skips expensive semantic_cross_collection
    which does O(n^2) embedding queries). Semantic overlap is estimated from
    a small sample instead.

    Returns: dict with phi components + composite.
    """
    try:
        from clarvis.metrics.phi import (
            _build_adjacency,
            intra_collection_density, cross_collection_integration,
            collection_reachability,
        )

        nodes, adj, edge_list = _build_adjacency(brain)

        ic_score, _ = intra_collection_density(nodes, adj)
        cc_score, cc_details = cross_collection_integration(nodes, edge_list)
        cr_score, _ = collection_reachability(nodes, adj)

        # Fast semantic estimate: query 2 samples across 2 collections
        semantic_est = 0.0
        try:
            cols = list(brain.collections.keys())
            if len(cols) >= 2:
                col1 = brain.collections[cols[0]]
                col2 = brain.collections[cols[1]]
                docs1 = col1.get(include=["documents"])["documents"][:2]
                sims = []
                for doc in docs1:
                    r = col2.query(query_texts=[doc], n_results=1, include=["distances"])
                    if r["distances"] and r["distances"][0]:
                        sims.append(max(0, 1.0 - r["distances"][0][0] / 2.0))
                if sims:
                    semantic_est = sum(sims) / len(sims)
        except Exception:
            pass

        # Approximate phi with same weights as canonical
        phi = 0.20 * ic_score + 0.20 * cc_score + 0.35 * semantic_est + 0.25 * cr_score

        return {
            "phi": round(phi, 4),
            "intra_density": round(ic_score, 4),
            "cross_connectivity": round(cc_score, 4),
            "semantic_overlap": round(semantic_est, 4),
            "reachability": round(cr_score, 4),
        }
    except Exception as e:
        return {"phi": 0.0, "error": str(e)}


def probe_context_assembly(brain):
    """Probe 3: Context brief generation quality.

    Measures token count, section count, and whether GWT/attention data appears.
    """
    try:
        from clarvis.context.assembly import generate_tiered_brief
        brief = generate_tiered_brief("Test ablation task", tier="standard")
        text = brief if isinstance(brief, str) else json.dumps(brief)
        tokens_approx = len(text.split())
        has_gwt = "GWT" in text or "broadcast" in text.lower() or "spotlight" in text.lower()
        has_attention = "attention" in text.lower() or "codelet" in text.lower()
        has_meta = "awareness" in text.lower() or "meta" in text.lower()
        section_count = text.count("===") + text.count("---") + text.count("##")
        return {
            "tokens": tokens_approx,
            "sections": section_count,
            "has_gwt_data": has_gwt,
            "has_attention_data": has_attention,
            "has_meta_data": has_meta,
        }
    except Exception as e:
        return {"tokens": 0, "error": str(e)}


def probe_attention_state():
    """Probe 4: Attention mechanism health.

    Measures spotlight occupancy, codelet competition, schema state.
    """
    try:
        from clarvis.cognition.attention import attention
        spotlight = attention.focus()
        items_count = len(spotlight) if isinstance(spotlight, list) else 0

        try:
            competition = attention.get_codelet_competition()
            if hasattr(competition, 'compete'):
                comp_result = competition.compete()
                winner = comp_result.get("winner", "none")
            else:
                winner = "unavailable"
        except Exception:
            winner = "unavailable"

        try:
            schema = attention.get_attention_schema()
            schema_confidence = schema.confidence if hasattr(schema, 'confidence') else 0.5
        except Exception:
            schema_confidence = 0.5

        return {
            "spotlight_items": items_count,
            "winner_domain": winner,
            "schema_confidence": schema_confidence,
        }
    except Exception as e:
        return {"spotlight_items": 0, "error": str(e)}


def probe_meta_cognition():
    """Probe 5: Meta-cognitive state health (HOT layer).

    Returns awareness level, working memory size, meta-thought count.
    """
    try:
        from clarvis.metrics.self_model import load_meta
        meta = load_meta()
        return {
            "awareness_level": meta.get("awareness_level", "unknown"),
            "working_memory_size": len(meta.get("working_memory", [])),
            "meta_thought_count": len(meta.get("meta_thoughts", [])),
            "cognitive_state": meta.get("cognitive_state", "unknown"),
        }
    except Exception as e:
        return {"awareness_level": "error", "error": str(e)}


def run_all_probes(brain, label="baseline"):
    """Run all probes and return combined results."""
    t0 = time.time()
    results = {
        "label": label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retrieval": probe_retrieval_quality(brain),
        "phi": probe_phi_components(brain),
        "context": probe_context_assembly(brain),
        "attention": probe_attention_state(),
        "meta_cognition": probe_meta_cognition(),
        "duration_s": 0,
    }
    results["duration_s"] = round(time.time() - t0, 2)
    return results


# ── Ablation Functions ────────────────────────────────────────────


def ablate_gwt(brain):
    """Disable GWT broadcast: attention spotlight becomes invisible to other modules.

    The GWT broadcast pushes spotlight contents into brain context,
    making them available system-wide. This ablation suppresses both:
    1. The broadcast() call (no brain context update)
    2. The focus()/focus_summary() output (spotlight returns empty)

    This simulates a system where parallel processors run but never
    share results via the global workspace.
    """
    from clarvis.cognition import attention as attn_module

    original_broadcast = attn_module.attention.broadcast
    original_focus = attn_module.attention.focus
    original_focus_summary = attn_module.attention.focus_summary

    attn_module.attention.broadcast = lambda: "(GWT ablated)"
    attn_module.attention.focus = lambda: []
    attn_module.attention.focus_summary = lambda: "(GWT ablated — no spotlight)"

    # Also suppress brain.set_context to prevent indirect broadcast
    original_set_context = brain.set_context if hasattr(brain, 'set_context') else None
    if original_set_context:
        brain.set_context = lambda x: None

    try:
        results = run_all_probes(brain, label="ablated_gwt")
    finally:
        attn_module.attention.broadcast = original_broadcast
        attn_module.attention.focus = original_focus
        attn_module.attention.focus_summary = original_focus_summary
        if original_set_context:
            brain.set_context = original_set_context

    return results


def ablate_iit(brain):
    """Disable IIT integration: zero out cross-collection edges.

    IIT measures how interconnected memories are across collections.
    This ablation makes the graph appear fragmented — each collection
    is an isolated island.
    """
    from clarvis.metrics import phi as phi_module

    original_build_adjacency = phi_module._build_adjacency

    def isolated_adjacency(brain_inst):
        """Build adjacency but remove all cross-collection edges."""
        nodes, adj, edge_list = original_build_adjacency(brain_inst)

        # Filter: keep only same-collection edges
        filtered_edges = []
        filtered_adj = {}
        for nid in adj:
            filtered_adj[nid] = set()

        for f, t, etype in edge_list:
            f_col = nodes.get(f, "unknown")
            t_col = nodes.get(t, "unknown")
            if f_col == t_col:
                filtered_edges.append((f, t, etype))
                if f not in filtered_adj:
                    filtered_adj[f] = set()
                if t not in filtered_adj:
                    filtered_adj[t] = set()
                filtered_adj[f].add(t)
                filtered_adj[t].add(f)

        from collections import defaultdict
        adj_dd = defaultdict(set, filtered_adj)
        return nodes, adj_dd, filtered_edges

    phi_module._build_adjacency = isolated_adjacency

    try:
        results = run_all_probes(brain, label="ablated_iit")
    finally:
        phi_module._build_adjacency = original_build_adjacency

    return results


def ablate_hot(brain):
    """Disable HOT monitoring: meta-cognition returns empty/default state.

    HOT (Higher-Order Thought) theory says consciousness requires
    thoughts about thoughts. This ablation removes meta-cognitive
    awareness — the system loses self-monitoring.
    """
    from clarvis.metrics import self_model as sm_module

    original_load_meta = sm_module.load_meta

    def empty_meta():
        return {
            "awareness_level": "disabled",
            "current_focus": None,
            "cognitive_state": "disabled",
            "working_memory": [],
            "meta_thoughts": [],
            "user_model": {},
            "attention_shifts": 0,
            "reflections": [],
        }

    sm_module.load_meta = empty_meta

    try:
        results = run_all_probes(brain, label="ablated_hot")
    finally:
        sm_module.load_meta = original_load_meta

    return results


def ablate_all(brain):
    """Disable all three layers simultaneously — maximum degradation test."""
    from clarvis.cognition import attention as attn_module
    from clarvis.metrics import phi as phi_module
    from clarvis.metrics import self_model as sm_module

    # Save originals
    orig_broadcast = attn_module.attention.broadcast
    orig_set_ctx = brain.set_context if hasattr(brain, 'set_context') else None
    orig_adjacency = phi_module._build_adjacency
    orig_load_meta = sm_module.load_meta

    # Save GWT extras
    orig_focus = attn_module.attention.focus
    orig_focus_summary = attn_module.attention.focus_summary

    # Apply all ablations
    attn_module.attention.broadcast = lambda: "(all ablated)"
    attn_module.attention.focus = lambda: []
    attn_module.attention.focus_summary = lambda: "(all ablated)"
    if orig_set_ctx:
        brain.set_context = lambda x: None

    def isolated_adjacency(brain_inst):
        nodes, adj, edge_list = orig_adjacency(brain_inst)
        from collections import defaultdict
        filtered = [(f, t, e) for f, t, e in edge_list if nodes.get(f) == nodes.get(t)]
        adj2 = defaultdict(set)
        for f, t, _ in filtered:
            adj2[f].add(t)
            adj2[t].add(f)
        return nodes, adj2, filtered

    phi_module._build_adjacency = isolated_adjacency
    sm_module.load_meta = lambda: {
        "awareness_level": "disabled", "current_focus": None,
        "cognitive_state": "disabled", "working_memory": [],
        "meta_thoughts": [], "user_model": {}, "attention_shifts": 0,
        "reflections": [],
    }

    try:
        results = run_all_probes(brain, label="ablated_all")
    finally:
        attn_module.attention.broadcast = orig_broadcast
        attn_module.attention.focus = orig_focus
        attn_module.attention.focus_summary = orig_focus_summary
        if orig_set_ctx:
            brain.set_context = orig_set_ctx
        phi_module._build_adjacency = orig_adjacency
        sm_module.load_meta = orig_load_meta

    return results


# ── Analysis ──────────────────────────────────────────────────────


def compute_degradation(baseline, ablated):
    """Compute degradation scores between baseline and ablated results.

    Returns dict of metric_name -> degradation (positive = worse when ablated).
    """
    degradation = {}

    # Retrieval degradation
    b_ret = baseline.get("retrieval", {})
    a_ret = ablated.get("retrieval", {})
    if b_ret.get("mean_results", 0) > 0:
        degradation["retrieval_results"] = round(
            1.0 - a_ret.get("mean_results", 0) / b_ret["mean_results"], 4
        )
    degradation["retrieval_coverage"] = round(
        b_ret.get("coverage", 0) - a_ret.get("coverage", 0), 4
    )

    # Phi degradation
    b_phi = baseline.get("phi", {})
    a_phi = ablated.get("phi", {})
    if b_phi.get("phi", 0) > 0:
        degradation["phi_total"] = round(
            1.0 - a_phi.get("phi", 0) / b_phi["phi"], 4
        )
    for component in ["intra_density", "cross_connectivity", "semantic_overlap", "reachability"]:
        bv = b_phi.get(component, 0)
        av = a_phi.get(component, 0)
        if bv > 0:
            degradation[f"phi_{component}"] = round(1.0 - av / bv, 4)

    # Context degradation
    b_ctx = baseline.get("context", {})
    a_ctx = ablated.get("context", {})
    if b_ctx.get("tokens", 0) > 0:
        degradation["context_tokens"] = round(
            1.0 - a_ctx.get("tokens", 0) / b_ctx["tokens"], 4
        )
    # Binary features
    for feat in ["has_gwt_data", "has_attention_data", "has_meta_data"]:
        if b_ctx.get(feat) and not a_ctx.get(feat):
            degradation[f"context_{feat}_lost"] = 1.0
        else:
            degradation[f"context_{feat}_lost"] = 0.0

    # Attention degradation
    b_attn = baseline.get("attention", {})
    a_attn = ablated.get("attention", {})
    if b_attn.get("spotlight_items", 0) > 0:
        degradation["attention_items"] = round(
            1.0 - a_attn.get("spotlight_items", 0) / b_attn["spotlight_items"], 4
        )

    # Meta-cognition degradation
    b_meta = baseline.get("meta_cognition", {})
    a_meta = ablated.get("meta_cognition", {})
    if a_meta.get("awareness_level") == "disabled":
        degradation["meta_awareness_lost"] = 1.0
    elif b_meta.get("awareness_level") != a_meta.get("awareness_level"):
        degradation["meta_awareness_lost"] = 0.5
    else:
        degradation["meta_awareness_lost"] = 0.0

    return degradation


def compute_composite_degradation(degradation):
    """Single 0-1 score: how much did this ablation hurt?

    Weighted by importance:
      - Phi components: 0.35 (direct consciousness measure)
      - Retrieval: 0.25 (functional capability)
      - Context: 0.20 (downstream task quality)
      - Meta-cognition: 0.10 (self-awareness)
      - Attention: 0.10 (focus management)
    """
    phi_keys = [k for k in degradation if k.startswith("phi_")]
    ret_keys = [k for k in degradation if k.startswith("retrieval_")]
    ctx_keys = [k for k in degradation if k.startswith("context_") and "lost" not in k]
    ctx_binary = [k for k in degradation if k.endswith("_lost")]
    meta_keys = [k for k in degradation if k.startswith("meta_")]
    attn_keys = [k for k in degradation if k.startswith("attention_")]

    def avg(keys):
        vals = [degradation.get(k, 0) for k in keys]
        return sum(vals) / max(len(vals), 1)

    composite = (
        0.35 * avg(phi_keys) +
        0.25 * avg(ret_keys) +
        0.15 * avg(ctx_keys) +
        0.05 * avg(ctx_binary) +
        0.10 * avg(meta_keys) +
        0.10 * avg(attn_keys)
    )
    return round(max(0, min(1, composite)), 4)


def analyze_complementarity(all_degradations):
    """Determine if layers are complementary (each hurts independently)
    or redundant (removing one doesn't matter because others compensate).

    Returns analysis dict with per-layer importance and complementarity score.
    """
    layers = {}
    for layer_name, deg in all_degradations.items():
        if layer_name == "all":
            continue
        composite = compute_composite_degradation(deg)
        layers[layer_name] = {
            "composite_degradation": composite,
            "is_essential": composite > 0.05,  # >5% degradation = essential
            "degradation_details": deg,
        }

    all_deg = all_degradations.get("all", {})
    all_composite = compute_composite_degradation(all_deg) if all_deg else 0

    # Complementarity: sum of individual > all means redundancy
    # sum of individual < all means synergy (super-additive)
    individual_sum = sum(l["composite_degradation"] for l in layers.values())

    if all_composite > 0:
        complementarity = individual_sum / all_composite
        # >1 = redundant overlap, <1 = synergistic, ~1 = additive/complementary
    else:
        complementarity = 1.0

    # Rank by importance
    ranked = sorted(layers.items(), key=lambda x: x[1]["composite_degradation"], reverse=True)

    return {
        "per_layer": layers,
        "ranked_importance": [name for name, _ in ranked],
        "individual_sum": round(individual_sum, 4),
        "combined_degradation": round(all_composite, 4),
        "complementarity_ratio": round(complementarity, 4),
        "interpretation": _interpret_complementarity(complementarity, layers),
    }


def _interpret_complementarity(ratio, layers):
    """Human-readable interpretation of complementarity analysis."""
    essential = [name for name, data in layers.items() if data["is_essential"]]
    redundant = [name for name, data in layers.items() if not data["is_essential"]]

    lines = []
    if ratio > 1.2:
        lines.append(f"Layers show REDUNDANCY (ratio={ratio:.2f}): removing individual layers has overlapping effects.")
    elif ratio < 0.8:
        lines.append(f"Layers show SYNERGY (ratio={ratio:.2f}): combined removal is worse than sum of parts.")
    else:
        lines.append(f"Layers are COMPLEMENTARY (ratio={ratio:.2f}): each contributes independently.")

    if essential:
        lines.append(f"Essential layers (>5% degradation): {', '.join(essential)}")
    if redundant:
        lines.append(f"Candidate for pruning (<5% degradation): {', '.join(redundant)}")

    return " ".join(lines)


# ── Main Execution ────────────────────────────────────────────────


def run_ablation_suite(layers=None):
    """Run the full ablation suite.

    Args:
        layers: list of layer names to ablate, or None for all.
                Valid: ["gwt", "iit", "hot"]
    """
    from clarvis.brain import get_brain
    brain = get_brain()

    if layers is None:
        layers = ["gwt", "iit", "hot"]

    print(f"=== Consciousness Theory Ablation Harness ===")
    print(f"Layers to test: {', '.join(layers)}")
    print(f"Probe queries: {len(PROBE_QUERIES)}")
    print()

    # Step 1: Baseline (all layers active)
    print("[1/{}] Running baseline (all layers active)...".format(len(layers) + 2))
    t0 = time.time()
    baseline = run_all_probes(brain, label="baseline")
    print(f"    Baseline complete in {baseline['duration_s']}s")
    print(f"    Phi={baseline['phi'].get('phi', 'n/a')}, "
          f"Retrieval coverage={baseline['retrieval'].get('coverage', 'n/a'):.2f}, "
          f"Attention items={baseline['attention'].get('spotlight_items', 'n/a')}")
    print()

    # Step 2: Ablate each layer
    ablation_funcs = {
        "gwt": ("GWT Broadcast", ablate_gwt),
        "iit": ("IIT Integration", ablate_iit),
        "hot": ("HOT Monitoring", ablate_hot),
    }

    ablated_results = {}
    degradations = {}

    for i, layer in enumerate(layers):
        name, func = ablation_funcs[layer]
        step = i + 2
        print(f"[{step}/{len(layers) + 2}] Ablating {name}...")
        result = func(brain)
        ablated_results[layer] = result
        deg = compute_degradation(baseline, result)
        degradations[layer] = deg
        composite = compute_composite_degradation(deg)
        print(f"    Complete in {result['duration_s']}s — composite degradation: {composite:.4f}")

        # Show most affected metrics
        top_impacts = sorted(deg.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        for metric, val in top_impacts:
            if abs(val) > 0.001:
                print(f"    {metric}: {val:+.4f}")
        print()

    # Step 3: Ablate all layers together
    step = len(layers) + 2
    print(f"[{step}/{step}] Ablating ALL layers together...")
    all_result = ablate_all(brain)
    ablated_results["all"] = all_result
    all_deg = compute_degradation(baseline, all_result)
    degradations["all"] = all_deg
    all_composite = compute_composite_degradation(all_deg)
    print(f"    Complete in {all_result['duration_s']}s — composite degradation: {all_composite:.4f}")
    print()

    # Step 4: Analyze complementarity
    analysis = analyze_complementarity(degradations)

    # Build final report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "ablations": ablated_results,
        "degradations": degradations,
        "analysis": analysis,
    }

    # Save results
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, 'w') as f:
        json.dump(report, f, indent=2)

    # Append to history
    history_entry = {
        "timestamp": report["timestamp"],
        "baseline_phi": baseline["phi"].get("phi", 0),
        "per_layer": {k: compute_composite_degradation(v) for k, v in degradations.items()},
        "complementarity_ratio": analysis["complementarity_ratio"],
        "ranked": analysis["ranked_importance"],
    }
    with open(HISTORY_FILE, 'a') as f:
        f.write(json.dumps(history_entry) + "\n")

    # Print summary
    print("=" * 60)
    print("ABLATION RESULTS")
    print("=" * 60)
    print(f"\nBaseline Phi: {baseline['phi'].get('phi', 'n/a')}")
    print(f"\nPer-layer degradation (composite score, 0=no impact, 1=total loss):")
    for layer in analysis["ranked_importance"]:
        data = analysis["per_layer"][layer]
        bar = "█" * int(data["composite_degradation"] * 40) + "░" * (40 - int(data["composite_degradation"] * 40))
        essential = "ESSENTIAL" if data["is_essential"] else "prunable"
        print(f"  {layer:5s}  {bar}  {data['composite_degradation']:.4f}  [{essential}]")

    print(f"\nAll layers disabled: {all_composite:.4f}")
    print(f"Sum of individual:  {analysis['individual_sum']:.4f}")
    print(f"Complementarity ratio: {analysis['complementarity_ratio']:.4f}")
    print(f"\n{analysis['interpretation']}")
    print(f"\nResults saved to {RESULTS_FILE}")

    return report


def show_report():
    """Display last ablation results."""
    if not os.path.exists(RESULTS_FILE):
        print("No ablation results found. Run ablation_harness.py first.")
        return

    with open(RESULTS_FILE) as f:
        report = json.load(f)

    analysis = report["analysis"]
    print(f"Last ablation: {report['timestamp']}")
    print(f"Baseline Phi: {report['baseline']['phi'].get('phi', 'n/a')}")
    print(f"\nRanked importance: {' > '.join(analysis['ranked_importance'])}")
    print(f"Complementarity ratio: {analysis['complementarity_ratio']}")
    print(f"\n{analysis['interpretation']}")

    print("\nDetailed degradation per layer:")
    for layer, data in analysis["per_layer"].items():
        print(f"\n  {layer} (composite={data['composite_degradation']:.4f}):")
        for metric, val in sorted(data["degradation_details"].items(), key=lambda x: -abs(x[1])):
            if abs(val) > 0.001:
                print(f"    {metric:40s} {val:+.4f}")

    # History trend
    if os.path.exists(HISTORY_FILE):
        print("\n\nHistory:")
        with open(HISTORY_FILE) as f:
            for line in f:
                entry = json.loads(line.strip())
                ts = entry["timestamp"][:16]
                layers_str = ", ".join(f"{k}={v:.3f}" for k, v in entry["per_layer"].items() if k != "all")
                print(f"  {ts}  {layers_str}  ratio={entry['complementarity_ratio']:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consciousness Theory Ablation Harness")
    parser.add_argument("--layer", choices=["gwt", "iit", "hot"],
                        help="Ablate only this layer (default: all)")
    parser.add_argument("--report", action="store_true",
                        help="Show last results instead of running")
    args = parser.parse_args()

    if args.report:
        show_report()
    elif args.layer:
        run_ablation_suite(layers=[args.layer])
    else:
        run_ablation_suite()

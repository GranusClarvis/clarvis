#!/usr/bin/env python3
"""
Semantic Bridge Builder — Create explicit bridge memories between weakly-connected collections.

For each collection pair with semantic overlap < threshold (default 0.30),
finds the top-N most semantically similar cross-collection memory pairs and
creates explicit bridge memories that reference both sides. Bridges are stored
in the sparser collection to boost its connectivity.

Usage:
    python semantic_bridge_builder.py              # Run bridge building (default threshold 0.50)
    python semantic_bridge_builder.py --threshold 0.55  # Custom threshold
    python semantic_bridge_builder.py --dry-run    # Show what would be created without storing
    python semantic_bridge_builder.py --top 5      # Top 5 pairs per weak link (default 5)
    python semantic_bridge_builder.py status        # Show current weak pairs without modifying
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain as _brain_singleton

BRIDGE_STATE_FILE = "/home/agent/.openclaw/workspace/data/bridge_builder_state.json"


def find_weak_pairs(brain, threshold=0.50):
    """
    Identify collection pairs with semantic overlap below threshold.
    Uses stratified sampling matching phi_metric.py for consistency.
    Skips existing bridge memories to measure organic overlap only.

    Returns list of (col1, col2, overlap_score) sorted by overlap ascending.
    """
    active_collections = []
    col_samples = {}

    for col_name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            active_collections.append(col_name)
            # Stratified sampling: get all docs, pick evenly spaced subset
            # Matches phi_metric.py methodology (12 samples, evenly spaced)
            all_results = col.get(include=["documents"])
            all_docs = all_results.get("documents", [])
            # Filter out bridge memories for organic measurement
            organic_docs = [d for d in all_docs if d and
                           not d.startswith("BRIDGE [") and
                           not d.startswith("Connection between")]
            sample_size = min(12, len(organic_docs))
            if sample_size >= len(organic_docs):
                col_samples[col_name] = organic_docs
            else:
                step = len(organic_docs) / sample_size
                indices = [int(i * step) for i in range(sample_size)]
                col_samples[col_name] = [organic_docs[i] for i in indices]

    weak_pairs = []
    for i, c1 in enumerate(active_collections):
        for c2 in active_collections[i + 1:]:
            if not col_samples.get(c1) or not col_samples.get(c2):
                continue

            similarities = []
            # Bidirectional: query 8 samples each way (matches phi_metric)
            col2_obj = brain.collections[c2]
            for doc in col_samples[c1][:8]:
                try:
                    results = col2_obj.query(query_texts=[doc], n_results=1, include=["distances"])
                    if results["distances"] and results["distances"][0]:
                        dist = results["distances"][0][0]
                        sim = max(0, 1.0 - dist / 2.0)
                        similarities.append(sim)
                except Exception:
                    pass

            col1_obj = brain.collections[c1]
            for doc in col_samples[c2][:8]:
                try:
                    results = col1_obj.query(query_texts=[doc], n_results=1, include=["distances"])
                    if results["distances"] and results["distances"][0]:
                        dist = results["distances"][0][0]
                        sim = max(0, 1.0 - dist / 2.0)
                        similarities.append(sim)
                except Exception:
                    pass

            if similarities:
                avg_sim = sum(similarities) / len(similarities)
                if avg_sim < threshold:
                    weak_pairs.append((c1, c2, round(avg_sim, 4)))

    weak_pairs.sort(key=lambda x: x[2])
    return weak_pairs


_BRIDGE_PREFIXES = (
    "BRIDGE [", "Connection between", "Phi action:", "Phi integration",
    "Cross-domain link:", "Cross-domain insight:", "Semantic bridge between",
)
_BRIDGE_MARKERS = (
    "This connects to", " — relates to — ", " — related insight from ",
    "perspective:", "In auto-learning:", "In episodes:",
    "In memories ", "In procedures ", "In learnings ",
)
_BRIDGE_ID_PREFIXES = ("bridge_", "sbridge_", "cross_link_", "xlink_")


def _is_bridge_memory(mid, doc):
    """Check if a memory is a bridge/cross-link rather than organic content."""
    if any(mid.startswith(p) for p in _BRIDGE_ID_PREFIXES):
        return True
    if any(doc.startswith(p) for p in _BRIDGE_PREFIXES):
        return True
    if any(m in doc for m in _BRIDGE_MARKERS):
        return True
    return False


def find_best_cross_pairs(brain, col1_name, col2_name, top_n=5):
    """
    For two collections, find the top-N most semantically similar organic memory pairs.
    Skips bridge/cross-link memories to find genuine cross-domain connections.

    Returns list of dicts: {col1_id, col1_doc, col2_id, col2_doc, distance, similarity}
    """
    col1 = brain.collections[col1_name]
    col2 = brain.collections[col2_name]

    # Get all docs from col1, skip bridges
    c1_data = col1.get()
    c1_ids = c1_data.get("ids", [])
    c1_docs = c1_data.get("documents", [])

    # Filter to organic docs only
    organic = [(mid, doc) for mid, doc in zip(c1_ids, c1_docs)
               if doc and len(doc) >= 20 and not _is_bridge_memory(mid, doc)]

    # Stratified subsample if too many (avoid excessive queries)
    if len(organic) > 40:
        step = len(organic) / 40
        organic = [organic[int(i * step)] for i in range(40)]

    candidates = []
    for mid, doc in organic:
        try:
            results = col2.query(query_texts=[doc], n_results=5, include=["distances", "documents"])
            if (results["ids"] and results["ids"][0] and
                results["distances"] and results["distances"][0] and
                results["documents"] and results["documents"][0]):
                # Find best non-bridge match
                for ri in range(len(results["ids"][0])):
                    rid = results["ids"][0][ri]
                    rdoc = results["documents"][0][ri] or ""
                    if _is_bridge_memory(rid, rdoc):
                        continue
                    if len(rdoc) < 20:
                        continue
                    dist = results["distances"][0][ri]
                    sim = max(0, 1.0 - dist / 2.0)
                    candidates.append({
                        "col1_id": mid,
                        "col1_doc": doc,
                        "col2_id": rid,
                        "col2_doc": rdoc,
                        "distance": dist,
                        "similarity": sim,
                    })
                    break
        except Exception:
            continue

    # Sort by similarity descending (best matches first)
    candidates.sort(key=lambda x: x["similarity"], reverse=True)

    # Deduplicate: don't use the same col2 memory twice
    seen_col2 = set()
    unique = []
    for c in candidates:
        if c["col2_id"] not in seen_col2:
            seen_col2.add(c["col2_id"])
            unique.append(c)
            if len(unique) >= top_n:
                break

    return unique


def create_bridge_memory(brain, pair, col1_name, col2_name):
    """
    Create an explicit bridge memory that references both sides.
    Store in BOTH collections to maximize semantic overlap measured by phi_metric.

    The bridge text blends content from both memories naturally so it
    embeds close to both source documents in vector space.
    """
    # Extract key content (strip existing bridge prefixes if any)
    doc1 = pair["col1_doc"][:150].strip()
    doc2 = pair["col2_doc"][:150].strip()

    # Short collection labels
    c1_short = col1_name.replace("clarvis-", "").replace("autonomous-", "auto-")
    c2_short = col2_name.replace("clarvis-", "").replace("autonomous-", "auto-")

    # Create bridge text that naturally blends both domains
    bridge_text = (
        f"Connection between {c1_short} and {c2_short}: "
        f"{doc1} — relates to — {doc2}"
    )

    # Stable ID for idempotency
    base_id = f"sbridge_{pair['col1_id'][:25]}_{pair['col2_id'][:25]}"
    base_id = base_id.replace(" ", "_").replace("/", "_")[:70]

    stored_ids = []

    # Store in BOTH collections to boost bidirectional semantic overlap
    for target_col in [col1_name, col2_name]:
        bridge_id = f"{base_id}_{target_col[:15]}"[:80]
        mem_id = brain.store(
            bridge_text,
            collection=target_col,
            importance=0.6,
            tags=["semantic-bridge", col1_name, col2_name],
            source="semantic_bridge_builder",
            memory_id=bridge_id,
        )
        stored_ids.append(mem_id)

    # Create explicit cross-collection edges
    brain.add_relationship(pair["col1_id"], stored_ids[0], "semantic_bridge")
    brain.add_relationship(pair["col2_id"], stored_ids[1], "semantic_bridge")
    brain.add_relationship(pair["col1_id"], pair["col2_id"], "bridged_similarity")
    brain.add_relationship(stored_ids[0], stored_ids[1], "cross_collection")

    return {
        "bridge_id": stored_ids[0],
        "target_collection": f"{col1_name}+{col2_name}",
        "text_preview": bridge_text[:100],
    }


def load_state():
    """Load previous bridge builder state for incremental runs."""
    if os.path.exists(BRIDGE_STATE_FILE):
        with open(BRIDGE_STATE_FILE, 'r') as f:
            return json.load(f)
    return {"bridges_created": [], "last_run": None}


def save_state(state):
    """Save bridge builder state."""
    os.makedirs(os.path.dirname(BRIDGE_STATE_FILE), exist_ok=True)
    with open(BRIDGE_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def run(threshold=0.50, top_n=5, dry_run=False, verbose=True):
    """
    Main bridge building pipeline.

    DEPRECATED: Static bridge creation is superseded by dynamic cross-collection
    query expansion in brain.recall(cross_collection_expand=True). New bridge
    creation is disabled. Use 'status' subcommand to inspect existing bridges.

    Returns summary dict."""
    # Gate: no new bridge creation — dynamic expansion replaces static bridges
    if not dry_run:
        print("⚠ Bridge creation disabled — using dynamic cross-collection expansion instead.")
        print("  See: brain.recall(cross_collection_expand=True)")
        print("  Run with --dry-run to see what WOULD have been created.")
        return {"status": "disabled", "reason": "dynamic_expansion_replaces_static_bridges"}

    """
    Legacy pipeline (retained for dry-run analysis):

    1. Find all collection pairs with semantic overlap < threshold
    2. For each weak pair, find top-N most similar cross-collection memories
    3. Create bridge memories referencing both sides
    4. Store in the sparser collection

    Returns summary dict.
    """
    brain = _brain_singleton
    state = load_state()

    if verbose:
        print("Semantic Bridge Builder")
        print(f"  Threshold: {threshold}")
        print(f"  Top pairs per weak link: {top_n}")
        print(f"  Dry run: {dry_run}")
        print()

    # Step 1: Find weak pairs
    weak_pairs = find_weak_pairs(brain, threshold)

    if verbose:
        print(f"Found {len(weak_pairs)} collection pairs below threshold {threshold}:")
        for c1, c2, score in weak_pairs:
            print(f"  {c1} <-> {c2}: {score:.4f}")
        print()

    if not weak_pairs:
        print("No weak pairs found. All collection pairs above threshold.")
        return {"weak_pairs": 0, "bridges_created": 0}

    # Step 2 & 3: For each weak pair, find best cross-pairs and create bridges
    bridges_created = []
    total_bridges = 0

    for col1, col2, overlap in weak_pairs:
        if verbose:
            print(f"Building bridges for {col1} <-> {col2} (overlap={overlap:.4f})...")

        best_pairs = find_best_cross_pairs(brain, col1, col2, top_n)

        if verbose:
            print(f"  Found {len(best_pairs)} candidate pairs:")

        for pair in best_pairs:
            if verbose:
                print(f"    sim={pair['similarity']:.3f}: "
                      f"\"{pair['col1_doc'][:50]}...\" <-> \"{pair['col2_doc'][:50]}...\"")

            if not dry_run:
                bridge = create_bridge_memory(brain, pair, col1, col2)
                bridges_created.append({
                    "col1": col1,
                    "col2": col2,
                    "bridge_id": bridge["bridge_id"],
                    "target": bridge["target_collection"],
                    "similarity": pair["similarity"],
                })
                total_bridges += 1

                if verbose:
                    print(f"    -> Created bridge in {bridge['target_collection']}: {bridge['bridge_id']}")

        if verbose:
            print()

    # Save state
    if not dry_run:
        state["bridges_created"].extend(bridges_created)
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_threshold"] = threshold
        state["last_weak_pairs"] = len(weak_pairs)
        state["last_bridges_count"] = total_bridges
        save_state(state)

    summary = {
        "weak_pairs": len(weak_pairs),
        "bridges_created": total_bridges,
        "dry_run": dry_run,
        "threshold": threshold,
        "details": bridges_created,
    }

    if verbose:
        print(f"Summary: {len(weak_pairs)} weak pairs, {total_bridges} bridges created")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Semantic Bridge Builder")
    parser.add_argument("cmd", nargs="?", default="run", help="Command: run (default) or status")
    parser.add_argument("--threshold", type=float, default=0.50, help="Overlap threshold (default 0.50)")
    parser.add_argument("--top", type=int, default=5, help="Top N pairs per weak link (default 5)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without storing")
    args = parser.parse_args()

    if args.cmd == "status":
        brain = _brain_singleton
        weak = find_weak_pairs(brain, args.threshold)
        print(f"Pairs with semantic overlap < {args.threshold}:")
        for c1, c2, score in weak:
            print(f"  {c1} <-> {c2}: {score:.4f}")
        print(f"\nTotal weak pairs: {len(weak)}")
    else:
        run(threshold=args.threshold, top_n=args.top, dry_run=args.dry_run)

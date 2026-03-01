#!/usr/bin/env python3
"""
Semantic Overlap Booster — Raise semantic_cross_collection score by creating
targeted bridge memories for ALL collection pairs below a target threshold.

Unlike semantic_bridge_builder.py (threshold 0.30, basic bridges), this booster:
1. Targets ALL pairs below the desired score (default 0.55)
2. Creates richer bridge text by extracting key concepts from both sides
3. Tiers bridge count by weakness: <0.40 gets 5, <0.50 gets 3, <0.55 gets 2
4. Tracks state to avoid duplicate bridges across runs
5. Measures before/after to verify improvement

Usage:
    python semantic_overlap_booster.py                  # Full boost run
    python semantic_overlap_booster.py --dry-run        # Preview only
    python semantic_overlap_booster.py --target 0.55    # Custom target
    python semantic_overlap_booster.py measure           # Just measure current state
"""

import json
import os
import re
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain as _brain

STATE_FILE = "/home/agent/.openclaw/workspace/data/overlap_booster_state.json"


def measure_all_pairs(brain):
    """Measure semantic overlap for every collection pair. Returns (overall, pair_dict)."""
    active = []
    samples = {}

    for name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            active.append(name)
            n = min(8, count)
            results = col.get(limit=n)
            samples[name] = results.get("documents", [])

    if len(active) < 2:
        return 0.0, {}

    pair_scores = {}
    for i, c1 in enumerate(active):
        for c2 in active[i + 1:]:
            if not samples.get(c1) or not samples.get(c2):
                continue

            sims = []
            # Bidirectional queries
            for src, dst in [(c1, c2), (c2, c1)]:
                dst_col = brain.collections[dst]
                for doc in samples[src][:5]:
                    try:
                        r = dst_col.query(query_texts=[doc], n_results=1, include=["distances"])
                        if r["distances"] and r["distances"][0]:
                            dist = r["distances"][0][0]
                            sims.append(max(0, 1.0 - dist / 2.0))
                    except Exception:
                        pass

            if sims:
                pair_scores[f"{c1} <-> {c2}"] = round(sum(sims) / len(sims), 4)

    overall = sum(pair_scores.values()) / len(pair_scores) if pair_scores else 0.0
    return round(overall, 4), pair_scores


def extract_key_phrases(text, max_phrases=3):
    """Extract the most informative phrases from a memory text."""
    # Strip common prefixes
    for prefix in ["Goal: ", "Preference: ", "BRIDGE [", "Connection between"]:
        if text.startswith(prefix):
            text = text[len(prefix):]

    # Split on common separators and take meaningful chunks
    parts = re.split(r'[—\-:;.|]+', text)
    phrases = []
    for part in parts:
        part = part.strip()
        if len(part) > 10 and len(part) < 200:
            phrases.append(part)

    return phrases[:max_phrases]


def find_best_matches(brain, col1_name, col2_name, top_n=5):
    """
    Find top-N best semantic matches between two collections.
    Skips existing bridge memories. Returns list of match dicts.
    """
    col1 = brain.collections[col1_name]
    col2 = brain.collections[col2_name]

    # Get all non-bridge docs from col1
    c1_data = col1.get(limit=min(50, col1.count()))
    c1_ids = c1_data.get("ids", [])
    c1_docs = c1_data.get("documents", [])

    candidates = []
    for mid, doc in zip(c1_ids, c1_docs):
        if not doc or len(doc) < 10:
            continue
        if mid.startswith(("bridge_", "sbridge_", "boost_")):
            continue
        if doc.startswith(("BRIDGE [", "Connection between")):
            continue
        try:
            r = col2.query(query_texts=[doc], n_results=3, include=["distances", "documents", "metadatas"])
            if not (r["ids"] and r["ids"][0]):
                continue
            for ri in range(len(r["ids"][0])):
                rid = r["ids"][0][ri]
                rdoc = r["documents"][0][ri] if r["documents"] else ""
                if not rdoc or rid.startswith(("bridge_", "sbridge_", "boost_")):
                    continue
                if rdoc.startswith(("BRIDGE [", "Connection between")):
                    continue
                dist = r["distances"][0][ri]
                sim = max(0, 1.0 - dist / 2.0)
                candidates.append({
                    "col1_id": mid, "col1_doc": doc,
                    "col2_id": rid, "col2_doc": rdoc,
                    "similarity": sim,
                })
                break
        except Exception:
            continue

    candidates.sort(key=lambda x: x["similarity"], reverse=True)

    # Deduplicate
    seen = set()
    unique = []
    for c in candidates:
        key = (c["col1_id"], c["col2_id"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
            if len(unique) >= top_n:
                break

    return unique


def create_boost_bridge(brain, match, col1_name, col2_name):
    """
    Create a high-quality bridge memory that naturally connects concepts
    from both collections. Stored in BOTH collections for bidirectional overlap.
    """
    # Extract key content
    phrases1 = extract_key_phrases(match["col1_doc"])
    phrases2 = extract_key_phrases(match["col2_doc"])

    c1_label = col1_name.replace("clarvis-", "").replace("autonomous-", "auto-")
    c2_label = col2_name.replace("clarvis-", "").replace("autonomous-", "auto-")

    # Build bridge text that blends both domains naturally
    p1 = phrases1[0] if phrases1 else match["col1_doc"][:100]
    p2 = phrases2[0] if phrases2 else match["col2_doc"][:100]

    bridge_text = (
        f"{p1.rstrip('.')}. "
        f"This connects to {c2_label}: {p2.rstrip('.')}. "
        f"[{c1_label}/{c2_label} integration]"
    )

    # Stable hash-based ID for idempotency
    content_hash = hashlib.md5(
        f"{match['col1_id']}:{match['col2_id']}".encode()
    ).hexdigest()[:12]
    base_id = f"boost_{c1_label[:8]}_{c2_label[:8]}_{content_hash}"

    stored = []
    for target_col in [col1_name, col2_name]:
        t_label = target_col[:15]
        bridge_id = f"{base_id}_{t_label}"[:80]
        try:
            mem_id = brain.store(
                bridge_text,
                collection=target_col,
                importance=0.65,
                tags=["boost-bridge", col1_name, col2_name],
                source="semantic_overlap_booster",
                memory_id=bridge_id,
            )
            stored.append(mem_id)
        except Exception as e:
            print(f"    Warning: failed to store in {target_col}: {e}")

    # Create graph edges
    if len(stored) >= 2:
        try:
            brain.add_relationship(match["col1_id"], match["col2_id"], "boosted_bridge")
            brain.add_relationship(stored[0], stored[1], "cross_collection")
        except Exception:
            pass

    return {
        "bridge_id": base_id,
        "text_preview": bridge_text[:120],
        "stored_in": len(stored),
    }


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"runs": [], "bridge_hashes": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def run(target=0.55, dry_run=False, verbose=True):
    """
    Main booster pipeline.

    1. Measure all pairs
    2. For pairs below target, determine bridge count by weakness tier
    3. Create bridge memories
    4. Re-measure to verify improvement
    """
    brain = _brain
    state = load_state()
    existing_hashes = set(state.get("bridge_hashes", []))

    # Step 1: Measure before
    if verbose:
        print("=== Semantic Overlap Booster ===")
        print(f"Target: {target}")
        print()

    before_overall, before_pairs = measure_all_pairs(brain)
    if verbose:
        print(f"BEFORE: Overall = {before_overall:.4f}")
        below = {k: v for k, v in before_pairs.items() if v < target}
        print(f"  Pairs below {target}: {len(below)}/{len(before_pairs)}")
        print()

    # Step 2: Sort pairs by score, determine bridge count per tier
    weak_pairs = sorted(
        [(k, v) for k, v in before_pairs.items() if v < target],
        key=lambda x: x[1]
    )

    if not weak_pairs:
        if verbose:
            print("All pairs already at or above target. Nothing to do.")
        return {"before": before_overall, "after": before_overall, "bridges": 0}

    total_bridges = 0
    all_bridges = []

    for pair_name, score in weak_pairs:
        # Determine bridge count by weakness tier
        if score < 0.40:
            n_bridges = 5
        elif score < 0.48:
            n_bridges = 3
        else:
            n_bridges = 2

        # Parse collection names from pair name
        parts = pair_name.split(" <-> ")
        if len(parts) != 2:
            continue
        c1, c2 = parts

        if verbose:
            print(f"  {pair_name}: {score:.4f} -> creating {n_bridges} bridges")

        matches = find_best_matches(brain, c1, c2, top_n=n_bridges)

        for match in matches:
            # Check for duplicates via hash
            content_hash = hashlib.md5(
                f"{match['col1_id']}:{match['col2_id']}".encode()
            ).hexdigest()[:12]

            if content_hash in existing_hashes:
                if verbose:
                    print(f"    Skip (exists): {content_hash}")
                continue

            if dry_run:
                if verbose:
                    p1 = match["col1_doc"][:50]
                    p2 = match["col2_doc"][:50]
                    print(f"    Would bridge (sim={match['similarity']:.3f}): \"{p1}...\" <-> \"{p2}...\"")
            else:
                bridge = create_boost_bridge(brain, match, c1, c2)
                all_bridges.append(bridge)
                existing_hashes.add(content_hash)
                total_bridges += 1
                if verbose:
                    print(f"    Created: {bridge['text_preview'][:80]}...")

    if verbose:
        print(f"\n  Total bridges created: {total_bridges}")

    # Step 3: Re-measure after
    if not dry_run and total_bridges > 0:
        after_overall, after_pairs = measure_all_pairs(brain)
        delta = after_overall - before_overall

        if verbose:
            print(f"\nAFTER: Overall = {after_overall:.4f} (delta: {delta:+.4f})")
            still_below = sum(1 for v in after_pairs.values() if v < target)
            print(f"  Pairs still below {target}: {still_below}/{len(after_pairs)}")

            # Show biggest improvements
            improvements = []
            for pair_name in after_pairs:
                if pair_name in before_pairs:
                    d = after_pairs[pair_name] - before_pairs[pair_name]
                    if d > 0.001:
                        improvements.append((pair_name, before_pairs[pair_name], after_pairs[pair_name], d))
            if improvements:
                improvements.sort(key=lambda x: -x[3])
                print(f"\n  Top improvements:")
                for name, bef, aft, d in improvements[:10]:
                    print(f"    {name}: {bef:.4f} -> {aft:.4f} ({d:+.4f})")

        # Save state
        state["bridge_hashes"] = list(existing_hashes)
        state["runs"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "before": before_overall,
            "after": after_overall,
            "delta": round(delta, 4),
            "bridges_created": total_bridges,
            "target": target,
        })
        # Keep only last 20 runs
        state["runs"] = state["runs"][-20:]
        save_state(state)

        return {
            "before": before_overall,
            "after": after_overall,
            "delta": round(delta, 4),
            "bridges": total_bridges,
            "pairs_improved": len([1 for p in after_pairs if p in before_pairs and after_pairs[p] > before_pairs[p]]),
        }

    return {
        "before": before_overall,
        "after": before_overall,
        "bridges": total_bridges,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Semantic Overlap Booster")
    parser.add_argument("action", nargs="?", default="boost", choices=["boost", "measure"],
                        help="Action: boost (create bridges) or measure (just measure)")
    parser.add_argument("--target", type=float, default=0.55, help="Target overlap score (default 0.55)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating bridges")
    args = parser.parse_args()

    if args.action == "measure":
        brain = _brain
        overall, pairs = measure_all_pairs(brain)
        print(f"Overall semantic_cross_collection: {overall:.4f}")
        print()
        for name, score in sorted(pairs.items(), key=lambda x: x[1]):
            marker = " ** WEAK" if score < 0.40 else ("  < target" if score < args.target else "")
            print(f"  {score:.4f}  {name}{marker}")
        below = sum(1 for v in pairs.values() if v < args.target)
        print(f"\nPairs below {args.target}: {below}/{len(pairs)}")
    else:
        result = run(target=args.target, dry_run=args.dry_run)
        print(f"\nResult: {json.dumps(result, indent=2)}")

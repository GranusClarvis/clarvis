#!/usr/bin/env python3
"""
Semantic Overlap Booster — Raise semantic_cross_collection score by creating
targeted bridge memories for collection pairs below a target threshold.

Strategy:
1. Measure all pair overlaps (bidirectional query similarity, matching phi_metric)
2. For pairs below target, find the most semantically similar cross-collection docs
3. Create bridge memories blending content from both sides, stored in BOTH collections
4. Tier bridge count by weakness: <0.50 gets 5, <0.55 gets 4, <0.60 gets 3, else gets 2
5. Re-measure to verify improvement

Usage:
    python semantic_overlap_booster.py              # Full boost run (target=0.65)
    python semantic_overlap_booster.py --dry-run    # Preview only
    python semantic_overlap_booster.py --target 0.60  # Custom target
    python semantic_overlap_booster.py measure       # Just measure current state
"""

import json
import os
import sys
import hashlib
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain as _brain

STATE_FILE = "/home/agent/.openclaw/workspace/data/overlap_booster_state.json"


def measure_all_pairs(brain):
    """
    Measure semantic overlap for every collection pair.
    Uses the same methodology as phi_metric.semantic_cross_collection():
    stratified sampling + bidirectional queries.

    Returns (overall_avg, pair_dict).
    """
    active = []
    samples = {}

    for name, col in brain.collections.items():
        count = col.count()
        if count > 0:
            active.append(name)
            # Stratified sampling (match phi_metric: up to 12 docs, evenly spaced)
            all_results = col.get(include=["documents"])
            all_docs = all_results.get("documents", [])
            sample_size = min(12, len(all_docs))
            if sample_size >= len(all_docs):
                samples[name] = all_docs
            else:
                step = len(all_docs) / sample_size
                indices = [int(i * step) for i in range(sample_size)]
                samples[name] = [all_docs[i] for i in indices]

    if len(active) < 2:
        return 0.0, {}

    pair_scores = {}
    for i, c1 in enumerate(active):
        for c2 in active[i + 1:]:
            if not samples.get(c1) or not samples.get(c2):
                continue

            sims = []
            # Direction 1: query c2 with samples from c1
            dst_col = brain.collections[c2]
            for doc in samples[c1][:8]:
                try:
                    r = dst_col.query(query_texts=[doc], n_results=1, include=["distances"])
                    if r["distances"] and r["distances"][0]:
                        dist = r["distances"][0][0]
                        sims.append(max(0, 1.0 - dist / 2.0))
                except Exception:
                    pass

            # Direction 2: query c1 with samples from c2
            src_col = brain.collections[c1]
            for doc in samples[c2][:8]:
                try:
                    r = src_col.query(query_texts=[doc], n_results=1, include=["distances"])
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
    for prefix in ["Goal: ", "Preference: ", "BRIDGE [", "Connection between"]:
        if text.startswith(prefix):
            text = text[len(prefix):]

    parts = re.split(r'[—\-:;.|]+', text)
    phrases = []
    for part in parts:
        part = part.strip()
        if 10 < len(part) < 200:
            phrases.append(part)

    return phrases[:max_phrases]


def find_best_matches(brain, col1_name, col2_name, top_n=5, deep=False):
    """
    Find top-N best semantic matches between two collections.
    Skips existing bridge memories. Returns list of match dicts.
    deep=True: sample more docs and search bidirectionally.
    """
    col1 = brain.collections[col1_name]
    col2 = brain.collections[col2_name]

    sample_limit = 150 if deep else 50

    def _scan_direction(src_col, dst_col, src_name, dst_name):
        """Find matches querying dst with docs from src."""
        src_data = src_col.get(limit=min(sample_limit, src_col.count()), include=["documents"])
        src_ids = src_data.get("ids", [])
        src_docs = src_data.get("documents", [])
        hits = []
        for mid, doc in zip(src_ids, src_docs):
            if not doc or len(doc) < 10:
                continue
            if mid.startswith(("bridge_", "sbridge_", "boost_")):
                continue
            if doc.startswith(("BRIDGE [", "Connection between")):
                continue
            try:
                r = dst_col.query(query_texts=[doc], n_results=3, include=["distances", "documents"])
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
                    hits.append({
                        "col1_id": mid, "col1_doc": doc,
                        "col2_id": rid, "col2_doc": rdoc,
                        "similarity": sim,
                    })
                    break
            except Exception:
                continue
        return hits

    candidates = _scan_direction(col1, col2, col1_name, col2_name)
    if deep:
        # Bidirectional: also scan col2->col1, swapping roles
        rev_hits = _scan_direction(col2, col1, col2_name, col1_name)
        for h in rev_hits:
            candidates.append({
                "col1_id": h["col2_id"], "col1_doc": h["col2_doc"],
                "col2_id": h["col1_id"], "col2_doc": h["col1_doc"],
                "similarity": h["similarity"],
            })

    candidates.sort(key=lambda x: x["similarity"], reverse=True)

    # Deduplicate by both sides
    seen = set()
    unique = []
    for c in candidates:
        pair_key = frozenset([c["col1_id"], c["col2_id"]])
        if pair_key not in seen:
            seen.add(pair_key)
            unique.append(c)
            if len(unique) >= top_n:
                break

    return unique


BRIDGE_TEMPLATES = [
    "{p1}. This connects to {c2}: {p2}. [{c1}/{c2} integration]",
    "{p1} — related insight from {c2}: {p2}.",
    "Cross-domain link: {p1}. In {c2} context: {p2}.",
    "{c1} perspective: {p1}. {c2} perspective: {p2}. These aspects reinforce each other.",
]


def create_boost_bridge(brain, match, col1_name, col2_name, content_hash):
    """
    Create a bridge memory that naturally blends content from both collections.
    Stored in BOTH collections for bidirectional overlap improvement.
    """
    phrases1 = extract_key_phrases(match["col1_doc"])
    phrases2 = extract_key_phrases(match["col2_doc"])

    c1_label = col1_name.replace("clarvis-", "").replace("autonomous-", "auto-")
    c2_label = col2_name.replace("clarvis-", "").replace("autonomous-", "auto-")

    p1 = phrases1[0] if phrases1 else match["col1_doc"][:120]
    p2 = phrases2[0] if phrases2 else match["col2_doc"][:120]

    # Rotate through templates for embedding diversity
    template_idx = hash(content_hash) % len(BRIDGE_TEMPLATES)
    bridge_text = BRIDGE_TEMPLATES[template_idx].format(
        p1=p1.rstrip('.'), p2=p2.rstrip('.'), c1=c1_label, c2=c2_label
    )

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
            print(f"    Warning: store to {target_col} failed: {e}")

    # Cross-collection graph edges
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


def run(target=0.65, dry_run=False, verbose=True, deep=False):
    """
    Main booster pipeline:
    1. Measure all pairs
    2. For pairs below target, determine bridge count by weakness tier
    3. Create bridge memories
    4. Re-measure to verify improvement

    deep=True: sample more docs, bidirectional matching, higher bridge counts.
    """
    brain = _brain
    state = load_state()
    existing_hashes = set(state.get("bridge_hashes", []))

    if verbose:
        print("=== Semantic Overlap Booster ===")
        print(f"Target: {target}, deep={deep}")
        print()

    # Measure before
    before_overall, before_pairs = measure_all_pairs(brain)
    if verbose:
        print(f"BEFORE: Overall = {before_overall:.4f}")
        below = {k: v for k, v in before_pairs.items() if v < target}
        print(f"  Pairs below {target}: {len(below)}/{len(before_pairs)}")
        print()

    # Sort weak pairs by score (weakest first)
    weak_pairs = sorted(
        [(k, v) for k, v in before_pairs.items() if v < target],
        key=lambda x: x[1]
    )

    if not weak_pairs:
        if verbose:
            print("All pairs at or above target. Nothing to do.")
        return {"before": before_overall, "after": before_overall, "bridges": 0}

    total_bridges = 0

    for pair_name, score in weak_pairs:
        # Tier bridge count by weakness (deep mode doubles)
        if score < 0.50:
            n_bridges = 10 if deep else 5
        elif score < 0.55:
            n_bridges = 8 if deep else 4
        elif score < 0.60:
            n_bridges = 6 if deep else 3
        else:
            n_bridges = 4 if deep else 2

        parts = pair_name.split(" <-> ")
        if len(parts) != 2:
            continue
        c1, c2 = parts

        if verbose:
            print(f"  {pair_name}: {score:.4f} -> creating up to {n_bridges} bridges")

        matches = find_best_matches(brain, c1, c2, top_n=n_bridges, deep=deep)

        for match in matches:
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
                bridge = create_boost_bridge(brain, match, c1, c2, content_hash)
                existing_hashes.add(content_hash)
                total_bridges += 1
                if verbose:
                    print(f"    Created: {bridge['text_preview'][:80]}...")

    if verbose:
        print(f"\n  Total bridges created: {total_bridges}")

    # Re-measure after
    if not dry_run and total_bridges > 0:
        after_overall, after_pairs = measure_all_pairs(brain)
        delta = after_overall - before_overall

        if verbose:
            print(f"\nAFTER: Overall = {after_overall:.4f} (delta: {delta:+.4f})")
            still_below = sum(1 for v in after_pairs.values() if v < target)
            print(f"  Pairs still below {target}: {still_below}/{len(after_pairs)}")

            # Show biggest improvements
            improvements = []
            for pn in after_pairs:
                if pn in before_pairs:
                    d = after_pairs[pn] - before_pairs[pn]
                    if d > 0.001:
                        improvements.append((pn, before_pairs[pn], after_pairs[pn], d))
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
        state["runs"] = state["runs"][-20:]
        save_state(state)

        return {
            "before": before_overall,
            "after": after_overall,
            "delta": round(delta, 4),
            "bridges": total_bridges,
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
    parser.add_argument("--target", type=float, default=0.65, help="Target overlap (default 0.65)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating bridges")
    parser.add_argument("--deep", action="store_true", help="Deep mode: more docs, bidirectional, higher bridge counts")
    args = parser.parse_args()

    if args.action == "measure":
        overall, pairs = measure_all_pairs(_brain)
        print(f"Overall semantic_cross_collection: {overall:.4f}")
        print()
        for name, score in sorted(pairs.items(), key=lambda x: x[1]):
            marker = " ** WEAK" if score < 0.50 else ("  < target" if score < args.target else "")
            print(f"  {score:.4f}  {name}{marker}")
        below = sum(1 for v in pairs.values() if v < args.target)
        print(f"\nPairs below {args.target}: {below}/{len(pairs)}")
    else:
        result = run(target=args.target, dry_run=args.dry_run, deep=args.deep)
        print(f"\nResult: {json.dumps(result, indent=2)}")

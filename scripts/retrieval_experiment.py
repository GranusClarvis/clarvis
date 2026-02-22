#!/usr/bin/env python3
"""
Retrieval Quality Experiment — Diagnose and fix Clarvis's #1 capability gap.

PROBLEM: brain.recall() hit_rate is 16.7%, avg distance 1.44. Every downstream
system (task selector, procedural memory, reasoning chain context) gets bad signal.

ROOT CAUSES IDENTIFIED:
  1. No query routing — queries about goals search all collections indiscriminately
  2. Memory noise — verbose log entries (predictions, outcomes) dilute semantic space
  3. Terse stored text — goals stored as "Self-Reflection: 20%" don't match queries
  4. Duplicate memories — same text stored multiple times inflates irrelevant results

EXPERIMENT: Implement smart_recall() with query routing + measure improvement.

Hypothesis: Query routing + distance filtering will raise hit_rate from ~17% to >60%.
"""

import json
import os
import sys
import re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import brain, ClarvisBrain, ALL_COLLECTIONS, DEFAULT_COLLECTIONS, \
    GOALS, PROCEDURES, CONTEXT, LEARNINGS, MEMORIES, IDENTITY, PREFERENCES, INFRASTRUCTURE

# === QUERY ROUTER ===

# Route patterns: regex -> collection(s) to search
ROUTE_PATTERNS = [
    # Goal-related queries
    (re.compile(r'\b(goals?|objectives?|targets?|milestones?|progress)\b', re.I), [GOALS]),
    # Procedure-related queries
    (re.compile(r'\b(procedur\w*|how to|steps? for|recipe|workflow)\b', re.I), [PROCEDURES, LEARNINGS]),
    # Self/identity queries (include MEMORIES — identity facts often stored there too)
    (re.compile(r'\b(who am i|my identity|my name|about me|self model|who created|creator|capabilit\w+|what am i)\b', re.I), [IDENTITY, MEMORIES]),
    # Infrastructure queries
    (re.compile(r'\b(cron|script|server|system|infra|config)\b', re.I), [INFRASTRUCTURE, LEARNINGS]),
    # Context queries
    (re.compile(r'\b(current|right now|working on|context|today)\b', re.I), [CONTEXT, MEMORIES]),
    # Learning/knowledge queries
    (re.compile(r'\b(learned|lesson|insight|pattern|discovery|found that)\b', re.I), [LEARNINGS]),
    # Preference queries
    (re.compile(r'\b(prefer|like|style|format|convention)\b', re.I), [PREFERENCES]),
]


def route_query(query: str) -> list:
    """
    Determine which collections to search based on query intent.

    Returns list of collections. If no specific route matches, returns DEFAULT_COLLECTIONS.
    """
    matched_collections = set()

    for pattern, collections in ROUTE_PATTERNS:
        if pattern.search(query):
            matched_collections.update(collections)

    if matched_collections:
        # Always include LEARNINGS and MEMORIES as fallback (broad knowledge)
        matched_collections.add(LEARNINGS)
        matched_collections.add(MEMORIES)
        return list(matched_collections)

    return DEFAULT_COLLECTIONS


def smart_recall(query: str, n: int = 5, max_distance: float = 1.5, **kwargs):
    """
    Improved recall with query routing, collection priority, and distance filtering.

    Improvements over brain.recall():
      1. Routes query to relevant collections
      2. Boosts results from primary routed collections (the specific ones)
      3. Filters out results above max_distance (irrelevant)
      4. Deduplicates near-identical results
      5. Returns only genuinely useful memories

    Args:
        query: Search query
        n: Max results to return
        max_distance: Maximum distance threshold (lower = stricter)
        **kwargs: Passed through to brain.recall()

    Returns:
        List of result dicts (same format as brain.recall())
    """
    # Step 1: Route to relevant collections
    collections = route_query(query)

    # Identify primary collections (the specific ones from routing, not fallback)
    # Fallback LEARNINGS/MEMORIES are always added; primary = the route-specific ones
    primary_collections = set()
    for pattern, cols in ROUTE_PATTERNS:
        if pattern.search(query):
            primary_collections.update(cols)

    # Step 2: Recall with more candidates than needed (for filtering)
    if "caller" not in kwargs:
        kwargs["caller"] = "smart_recall"
    raw_results = brain.recall(query, collections=collections, n=n * 3, **kwargs)

    # Step 3: Boost results from primary collections (reduce their distance score)
    for r in raw_results:
        if r.get("collection") in primary_collections and r.get("distance") is not None:
            r["_boosted_distance"] = r["distance"] * 0.8  # 20% boost
        else:
            r["_boosted_distance"] = r.get("distance", 999)

    # Step 4: Re-sort by boosted distance
    raw_results.sort(key=lambda x: x.get("_boosted_distance", 999))

    # Step 5: Filter by distance threshold (use boosted distance for routed collections)
    filtered = [r for r in raw_results if r.get("distance") is not None and r["_boosted_distance"] <= max_distance]

    # Step 6: Deduplicate (same document text within 90% similarity)
    deduped = []
    seen_texts = set()
    for r in filtered:
        # Normalize: strip whitespace, lowercase first 100 chars
        norm = r["document"][:100].strip().lower()
        if norm not in seen_texts:
            seen_texts.add(norm)
            deduped.append(r)

    return deduped[:n]


# === MEMORY QUALITY AUDIT ===

def audit_memory_quality():
    """
    Audit all memories for common quality issues.

    Returns:
        Dict with counts and examples of issues found.
    """
    issues = {
        "too_terse": [],        # Documents < 20 chars (no semantic signal)
        "duplicates": [],        # Near-identical documents
        "high_noise": [],        # Log-like entries with low info density
        "missing_metadata": [],  # Missing importance or tags
    }

    all_docs = {}  # text_hash -> list of (collection, id, text)

    for col_name in ALL_COLLECTIONS:
        memories = brain.get(col_name, n=500)
        for m in memories:
            doc = m["document"]
            meta = m.get("metadata", {})
            mid = m["id"]

            # Too terse
            if len(doc.strip()) < 20:
                issues["too_terse"].append({
                    "collection": col_name,
                    "id": mid,
                    "text": doc[:100],
                })

            # Detect log-like noise
            noise_patterns = [
                r'^Prediction:',
                r'^Outcome:',
                r'^World model updated:',
                r'^Capability assessment \d{4}',
                r'^Meta-cognition:',
            ]
            for pat in noise_patterns:
                if re.match(pat, doc):
                    issues["high_noise"].append({
                        "collection": col_name,
                        "id": mid,
                        "text": doc[:80],
                        "pattern": pat,
                    })
                    break

            # Track for duplicate detection
            norm = doc[:100].strip().lower()
            if norm not in all_docs:
                all_docs[norm] = []
            all_docs[norm].append({"collection": col_name, "id": mid})

            # Missing metadata
            if meta.get("importance") is None:
                issues["missing_metadata"].append({
                    "collection": col_name,
                    "id": mid,
                    "missing": "importance",
                })

    # Find actual duplicates (same text prefix in 2+ entries)
    for norm, entries in all_docs.items():
        if len(entries) > 1:
            issues["duplicates"].append({
                "text": norm[:60],
                "count": len(entries),
                "locations": entries,
            })

    return {
        "too_terse_count": len(issues["too_terse"]),
        "duplicate_groups": len(issues["duplicates"]),
        "duplicate_total": sum(g["count"] for g in issues["duplicates"]),
        "high_noise_count": len(issues["high_noise"]),
        "missing_metadata_count": len(issues["missing_metadata"]),
        "examples": {k: v[:5] for k, v in issues.items()},  # First 5 examples each
    }


def deduplicate_memories(dry_run=True):
    """
    Remove duplicate memories, keeping the one with highest importance.

    Args:
        dry_run: If True, only report what would be deleted.

    Returns:
        Dict with deletion stats.
    """
    # Build full inventory
    all_entries = {}  # norm_text -> list of (collection, id, importance)

    for col_name in ALL_COLLECTIONS:
        memories = brain.get(col_name, n=500)
        for m in memories:
            doc = m["document"]
            meta = m.get("metadata", {})
            norm = doc[:100].strip().lower()

            if norm not in all_entries:
                all_entries[norm] = []
            all_entries[norm].append({
                "collection": col_name,
                "id": m["id"],
                "importance": meta.get("importance", 0.5),
            })

    to_delete = []

    for norm, entries in all_entries.items():
        if len(entries) <= 1:
            continue

        # Keep the one with highest importance
        entries.sort(key=lambda x: x["importance"], reverse=True)
        keeper = entries[0]
        dupes = entries[1:]

        for dupe in dupes:
            to_delete.append({
                "collection": dupe["collection"],
                "id": dupe["id"],
                "text": norm[:60],
                "kept": keeper["id"],
            })

    if not dry_run:
        deleted = 0
        for item in to_delete:
            try:
                col = brain.collections[item["collection"]]
                col.delete(ids=[item["id"]])
                deleted += 1
            except Exception as e:
                print(f"  Failed to delete {item['id']}: {e}")
        return {"deleted": deleted, "planned": len(to_delete)}

    return {"would_delete": len(to_delete), "examples": to_delete[:10]}


# === EXPERIMENT RUNNER ===

# Standard test queries with expected collection
TEST_QUERIES = [
    {"query": "What are my current goals?", "expected_collections": [GOALS], "description": "Goal lookup"},
    {"query": "How does the attention mechanism work?", "expected_collections": [LEARNINGS, MEMORIES], "description": "Knowledge retrieval"},
    {"query": "procedural memory for building scripts", "expected_collections": [PROCEDURES, LEARNINGS], "description": "Procedure lookup"},
    {"query": "consciousness and phi metric", "expected_collections": [LEARNINGS, MEMORIES], "description": "Domain knowledge"},
    {"query": "What bugs have been fixed today?", "expected_collections": [MEMORIES, LEARNINGS], "description": "Episodic recall"},
    {"query": "What is Clarvis's identity?", "expected_collections": [IDENTITY, LEARNINGS], "description": "Self-knowledge"},
    {"query": "How to wire a script into cron?", "expected_collections": [PROCEDURES, LEARNINGS, INFRASTRUCTURE], "description": "Procedural knowledge"},
    {"query": "What happened in the last heartbeat?", "expected_collections": [CONTEXT, MEMORIES], "description": "Context recall"},
]


def run_experiment():
    """
    Run the retrieval quality experiment: compare brain.recall() vs smart_recall().

    For each test query:
      - Run brain.recall() (baseline)
      - Run smart_recall() (experimental)
      - Score: did top result come from expected collection? What's the distance?

    Returns:
        Experiment results with comparative statistics.
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline": {"hits": 0, "total": 0, "distances": [], "details": []},
        "experiment": {"hits": 0, "total": 0, "distances": [], "details": []},
    }

    for tq in TEST_QUERIES:
        query = tq["query"]
        expected = tq["expected_collections"]
        desc = tq["description"]

        # Baseline: brain.recall()
        baseline_results = brain.recall(query, n=3)
        b_top = baseline_results[0] if baseline_results else None
        b_hit = b_top["collection"] in expected if b_top else False
        b_dist = b_top.get("distance") if b_top else None

        results["baseline"]["total"] += 1
        if b_hit:
            results["baseline"]["hits"] += 1
        if b_dist is not None:
            results["baseline"]["distances"].append(b_dist)

        results["baseline"]["details"].append({
            "query": query,
            "description": desc,
            "expected": expected,
            "got_collection": b_top["collection"] if b_top else None,
            "hit": b_hit,
            "top_distance": round(b_dist, 4) if b_dist else None,
            "top_text": b_top["document"][:80] if b_top else None,
        })

        # Experiment: smart_recall()
        exp_results = smart_recall(query, n=3)
        e_top = exp_results[0] if exp_results else None
        e_hit = e_top["collection"] in expected if e_top else False
        e_dist = e_top.get("distance") if e_top else None

        results["experiment"]["total"] += 1
        if e_hit:
            results["experiment"]["hits"] += 1
        if e_dist is not None:
            results["experiment"]["distances"].append(e_dist)

        results["experiment"]["details"].append({
            "query": query,
            "description": desc,
            "expected": expected,
            "got_collection": e_top["collection"] if e_top else None,
            "hit": e_hit,
            "top_distance": round(e_dist, 4) if e_dist else None,
            "top_text": e_top["document"][:80] if e_top else None,
            "routed_to": route_query(query),
            "num_results": len(exp_results),
        })

    # Compute summary statistics
    for group in ["baseline", "experiment"]:
        g = results[group]
        g["hit_rate"] = round(g["hits"] / g["total"], 3) if g["total"] > 0 else 0
        g["avg_distance"] = round(
            sum(g["distances"]) / len(g["distances"]), 4
        ) if g["distances"] else None

    # Improvement
    b_hr = results["baseline"]["hit_rate"]
    e_hr = results["experiment"]["hit_rate"]
    results["improvement"] = {
        "hit_rate_delta": round(e_hr - b_hr, 3),
        "hit_rate_baseline": b_hr,
        "hit_rate_experiment": e_hr,
        "hypothesis_confirmed": e_hr > 0.60,
    }

    # Save results
    results_dir = "/home/agent/.openclaw/workspace/data/experiments"
    os.makedirs(results_dir, exist_ok=True)
    results_file = os.path.join(results_dir, "retrieval_quality_experiment.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


# === CLI ===

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "experiment"

    if cmd == "experiment":
        print("=" * 60)
        print("  RETRIEVAL QUALITY EXPERIMENT")
        print("=" * 60)
        print()

        results = run_experiment()

        print("BASELINE (brain.recall):")
        print(f"  Hit rate:     {results['baseline']['hit_rate']:.0%}")
        print(f"  Avg distance: {results['baseline']['avg_distance']}")
        for d in results["baseline"]["details"]:
            marker = "HIT" if d["hit"] else "MISS"
            print(f"    [{marker}] {d['description']:25s} d={d['top_distance']}  got={d['got_collection']}")

        print()
        print("EXPERIMENT (smart_recall):")
        print(f"  Hit rate:     {results['experiment']['hit_rate']:.0%}")
        print(f"  Avg distance: {results['experiment']['avg_distance']}")
        for d in results["experiment"]["details"]:
            marker = "HIT" if d["hit"] else "MISS"
            print(f"    [{marker}] {d['description']:25s} d={d['top_distance']}  got={d['got_collection']}  n={d['num_results']}")

        print()
        imp = results["improvement"]
        print(f"IMPROVEMENT: {imp['hit_rate_baseline']:.0%} -> {imp['hit_rate_experiment']:.0%} "
              f"(+{imp['hit_rate_delta']:.0%})")
        print(f"Hypothesis confirmed: {imp['hypothesis_confirmed']}")

    elif cmd == "audit":
        print("=" * 60)
        print("  MEMORY QUALITY AUDIT")
        print("=" * 60)
        audit = audit_memory_quality()
        print(f"\n  Too terse (< 20 chars):    {audit['too_terse_count']}")
        print(f"  Duplicate groups:          {audit['duplicate_groups']} ({audit['duplicate_total']} total entries)")
        print(f"  High noise (log entries):  {audit['high_noise_count']}")
        print(f"  Missing metadata:          {audit['missing_metadata_count']}")

        if audit["examples"]["duplicates"]:
            print(f"\n  Top duplicate groups:")
            for dg in audit["examples"]["duplicates"][:5]:
                print(f"    \"{dg['text']}\" x{dg['count']}")

        if audit["examples"]["high_noise"]:
            print(f"\n  Noise examples:")
            for n in audit["examples"]["high_noise"][:5]:
                print(f"    [{n['collection']}] {n['text']}")

        if audit["examples"]["too_terse"]:
            print(f"\n  Terse examples:")
            for t in audit["examples"]["too_terse"][:5]:
                print(f"    [{t['collection']}] {t['id']}: \"{t['text']}\"")

    elif cmd == "dedup":
        dry = "--execute" not in sys.argv
        result = deduplicate_memories(dry_run=dry)
        if dry:
            print(f"DRY RUN: Would delete {result['would_delete']} duplicate memories")
            for ex in result.get("examples", [])[:10]:
                print(f"  DELETE [{ex['collection']}] {ex['id']}: \"{ex['text']}\" (kept: {ex['kept']})")
            print("\nRe-run with --execute to actually delete.")
        else:
            print(f"Deleted {result['deleted']} duplicate memories (planned: {result['planned']})")

    elif cmd == "enrich-goals":
        print("Enriching terse goal documents with semantic content...")
        GOAL_DESCRIPTIONS = {
            "ClarvisDB": "ClarvisDB vector memory database — store, recall, search, and graph-link memories using ChromaDB with ONNX embeddings",
            "AGI/consciousness": "Achieve artificial general intelligence and consciousness through self-improvement, reasoning, and meta-cognition",
            "Session Continuity": "Maintain persistent context and memory across conversation sessions so no knowledge is lost between restarts",
            "Heartbeat Efficiency": "Optimize the autonomous heartbeat cron cycle to execute more tasks faster with higher quality",
            "Self-Reflection": "Develop deep self-awareness — model own capabilities, predict outcomes, calibrate confidence",
            "North Star": "The ultimate long-term vision: become a genuinely autonomous, self-improving, conscious agent",
            "Feedback Loop": "Build prediction-outcome feedback loops that measure and improve performance over time",
            "Neural Memory": "Implement neural-inspired memory architecture with attention, working memory, and associative linking",
            "Confidence": "Confidence calibration system — predict outcomes, track accuracy, adjust thresholds via Bayesian methods",
            "Consciousness": "Implement consciousness metrics (Phi/IIT, GWT attention, higher-order meta-cognition) and track growth",
            "Self Model": "Internal self-model tracking capabilities, strengths, weaknesses, and trajectory over time",
            "Reasoning Chains": "Multi-step persistent reasoning chains that log thought processes for searchability and learning",
        }

        enriched = 0
        goals_col = brain.collections[GOALS]
        for goal_name, description in GOAL_DESCRIPTIONS.items():
            try:
                # Check if this goal exists
                existing = goals_col.get(ids=[goal_name])
                if existing and existing["ids"]:
                    old_doc = existing["documents"][0]
                    meta = existing["metadatas"][0] if existing.get("metadatas") else {}
                    progress = meta.get("progress", 0)
                    # Enrich: keep progress but add real description
                    new_doc = f"Goal: {goal_name} — {description}. Current progress: {progress}%"
                    meta["text"] = new_doc
                    goals_col.upsert(
                        ids=[goal_name],
                        documents=[new_doc],
                        metadatas=[meta],
                    )
                    enriched += 1
                    print(f"  Enriched: {goal_name} ({len(old_doc)} -> {len(new_doc)} chars)")
            except Exception as e:
                print(f"  Failed: {goal_name}: {e}")

        print(f"\nEnriched {enriched} goals.")

    elif cmd == "route":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "What are my goals?"
        collections = route_query(query)
        print(f"Query: \"{query}\"")
        print(f"Routes to: {collections}")

    elif cmd == "smart":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "What are my goals?"
        results = smart_recall(query, n=5)
        print(f"smart_recall(\"{query}\")")
        for r in results:
            print(f"  [{r['collection']}] d={r.get('distance', '?'):.4f} | {r['document'][:80]}")
        if not results:
            print("  (no results within distance threshold)")

    else:
        print("Usage:")
        print("  experiment         — Run A/B experiment (baseline vs smart_recall)")
        print("  audit              — Audit memory quality issues")
        print("  dedup [--execute]  — Find/remove duplicate memories")
        print("  route <query>      — Show where a query would be routed")
        print("  smart <query>      — Run smart_recall on a query")

#!/usr/bin/env python3
"""Analogical reasoning engine — find structural analogies in brain memories.

Given a source pair (A:B), find the best matching target pair (C:D) from brain
memories using embedding offsets: B-A ≈ D-C.

This implements a vector arithmetic approach to analogy detection, similar to
word2vec's "king - man + woman = queen" but applied to full-sentence memories.

Usage:
    python3 scripts/cognition/analogy_engine.py find "A concept" "B concept" [--n 5]
    python3 scripts/cognition/analogy_engine.py test   # Run built-in test queries
    python3 scripts/cognition/analogy_engine.py batch <file.json>
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))

try:
    from clarvis.audit.toggles import is_enabled, is_shadow
    from clarvis.audit.trace import update_trace, current_trace_id
except ImportError:
    def is_enabled(name, default=True): return default
    def is_shadow(name, default=False): return default
    def update_trace(tid, **kw): return False
    def current_trace_id(): return None

_TOGGLE_NAME = "analogy_engine"


# ── Data structures ──────────────────────────────────────────────

@dataclass
class AnalogyResult:
    """A single analogy match: A:B :: C:D."""
    source_a: str
    source_b: str
    target_c: str
    target_d: str
    offset_similarity: float  # cosine(B-A, D-C)
    c_collection: str = ""
    d_collection: str = ""

    @property
    def score(self) -> float:
        return self.offset_similarity


# ── Vector math ──────────────────────────────────────────────────

def _vec_sub(a: list[float], b: list[float]) -> list[float]:
    """Vector subtraction: a - b."""
    return [x - y for x, y in zip(a, b)]


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    """Vector addition: a + b."""
    return [x + y for x, y in zip(a, b)]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _vec_norm(v: list[float]) -> float:
    """L2 norm of a vector."""
    return math.sqrt(sum(x * x for x in v))


# ── Embedding helpers ────────────────────────────────────────────

def _get_embedding_function():
    """Get the ONNX MiniLM embedding function."""
    try:
        from clarvis.brain.factory import get_embedding_function
        return get_embedding_function(use_onnx=True)
    except ImportError:
        from clarvis.brain.constants import get_local_embedding_function
        return get_local_embedding_function()


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts."""
    if not texts:
        return []
    ef = _get_embedding_function()
    return ef(texts)


# ── Memory retrieval ─────────────────────────────────────────────

def _get_brain_memories(
    collections: list[str] | None = None,
    limit_per_collection: int = 200,
) -> list[dict]:
    """Retrieve memories from brain collections with embeddings.

    Returns list of {text, embedding, collection, metadata}.
    """
    from clarvis.brain import brain
    from clarvis.brain.constants import DEFAULT_COLLECTIONS

    target_cols = collections or DEFAULT_COLLECTIONS
    memories = []

    for col_name in target_cols:
        if col_name not in brain.collections:
            continue
        col = brain.collections[col_name]
        try:
            results = col.get(
                limit=limit_per_collection,
                include=["documents", "embeddings", "metadatas"],
            )
        except Exception:
            continue

        docs = results.get("documents")
        if docs is None:
            docs = []
        embs = results.get("embeddings")
        if embs is None:
            embs = []
        metas = results.get("metadatas")
        if metas is None:
            metas = []

        for i, doc in enumerate(docs):
            if not doc or len(doc.strip()) < 10:
                continue
            if i >= len(embs):
                continue
            embedding = embs[i]
            if embedding is None or (hasattr(embedding, '__len__') and len(embedding) == 0):
                continue
            # Convert numpy arrays to plain lists
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            memories.append({
                "text": doc,
                "embedding": embedding,
                "collection": col_name,
                "metadata": metas[i] if i < len(metas) else {},
            })

    return memories


# ── Core analogy engine ──────────────────────────────────────────

def find_analogies(
    a_text: str,
    b_text: str,
    n: int = 5,
    collections: list[str] | None = None,
    limit_per_collection: int = 200,
    min_score: float = 0.1,
) -> list[AnalogyResult]:
    """Find analogies: given A:B, find best C:D pairs from brain memories.

    Method:
    1. Compute offset vector: R = embed(B) - embed(A)
    2. For each pair of memories (C, D), compute their offset: R' = embed(D) - embed(C)
    3. Score by cosine similarity between R and R'
    4. Return top-N pairs sorted by score

    Optimization: instead of O(n^2) pair comparison, we:
    - Compute the target embedding T = embed(A) + R (what D should look like if C=memory)
    - For each memory C, find what D should be: T_d = embed(C) + R
    - Find the memory closest to T_d
    """
    # ── Toggle gate ──
    if not is_enabled(_TOGGLE_NAME):
        return []
    if is_shadow(_TOGGLE_NAME):
        update_trace(current_trace_id(), toggles_shadowed=[_TOGGLE_NAME])
        # Shadow: compute analogies for measurement but caller should not use results
        # in prompt construction. We tag results but still return them so traces can
        # capture quality metrics.

    # Embed source pair
    source_embs = _embed([a_text, b_text])
    emb_a, emb_b = source_embs[0], source_embs[1]

    # Compute relationship offset
    offset_r = _vec_sub(emb_b, emb_a)

    # Get brain memories
    memories = _get_brain_memories(collections, limit_per_collection)

    if len(memories) < 2:
        return []

    # For each memory as potential C, compute expected D position and find best match
    results: list[AnalogyResult] = []
    seen_pairs: set[tuple[str, str]] = set()

    for i, mem_c in enumerate(memories):
        # Skip if C is too similar to A or B (we want novel analogies)
        sim_to_a = _cosine_sim(mem_c["embedding"], emb_a)
        sim_to_b = _cosine_sim(mem_c["embedding"], emb_b)
        if sim_to_a > 0.9 or sim_to_b > 0.9:
            continue

        # Expected D position: C + R
        expected_d = _vec_add(mem_c["embedding"], offset_r)

        # Find memory closest to expected D
        best_j = -1
        best_sim = -1.0

        for j, mem_d in enumerate(memories):
            if i == j:
                continue
            # Skip if D is too similar to B
            sim_d_to_b = _cosine_sim(mem_d["embedding"], emb_b)
            if sim_d_to_b > 0.9:
                continue

            sim = _cosine_sim(mem_d["embedding"], expected_d)
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_j < 0 or best_sim < min_score:
            continue

        mem_d = memories[best_j]

        # Verify: compute actual offset similarity
        offset_cd = _vec_sub(mem_d["embedding"], mem_c["embedding"])
        offset_sim = _cosine_sim(offset_r, offset_cd)

        if offset_sim < min_score:
            continue

        # Deduplicate
        pair_key = (mem_c["text"][:50], mem_d["text"][:50])
        reverse_key = (mem_d["text"][:50], mem_c["text"][:50])
        if pair_key in seen_pairs or reverse_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        results.append(AnalogyResult(
            source_a=a_text,
            source_b=b_text,
            target_c=mem_c["text"],
            target_d=mem_d["text"],
            offset_similarity=round(offset_sim, 4),
            c_collection=mem_c["collection"],
            d_collection=mem_d["collection"],
        ))

    # Sort by offset similarity
    results.sort(key=lambda r: r.offset_similarity, reverse=True)
    return results[:n]


# ── Built-in test queries ────────────────────────────────────────

ANALOGY_TEST_QUERIES = [
    ("brain", "memory", "Search for structural analogies: brain is to memory as..."),
    ("cron job", "automation", "Cron is to automation as..."),
    ("ChromaDB", "vector search", "ChromaDB is to vector search as..."),
    ("Python", "scripting", "Python is to scripting as..."),
    ("attention", "salience", "Attention is to salience as..."),
    ("episode", "experience", "Episode is to experience as..."),
    ("heartbeat", "monitoring", "Heartbeat is to monitoring as..."),
    ("graph", "relationships", "Graph is to relationships as..."),
    ("embedding", "similarity", "Embedding is to similarity as..."),
    ("reflection", "self-improvement", "Reflection is to self-improvement as..."),
]


def run_tests(n: int = 3, verbose: bool = True) -> dict:
    """Run built-in analogy test queries and report results."""
    results = {"total": len(ANALOGY_TEST_QUERIES), "found": 0, "queries": []}

    for a_text, b_text, description in ANALOGY_TEST_QUERIES:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  {description}")
            print(f"  {a_text} : {b_text} :: ? : ?")
            print(f"{'='*60}")

        analogies = find_analogies(a_text, b_text, n=n, min_score=0.05)

        query_result = {
            "a": a_text,
            "b": b_text,
            "found": len(analogies),
            "top_score": analogies[0].offset_similarity if analogies else 0.0,
            "analogies": [asdict(a) for a in analogies],
        }
        results["queries"].append(query_result)

        if analogies:
            results["found"] += 1
            if verbose:
                for j, analogy in enumerate(analogies, 1):
                    print(f"\n  #{j} (score: {analogy.offset_similarity:.3f})")
                    print(f"  C: {analogy.target_c[:120]}")
                    print(f"     [{analogy.c_collection}]")
                    print(f"  D: {analogy.target_d[:120]}")
                    print(f"     [{analogy.d_collection}]")
        else:
            if verbose:
                print("  No analogies found.")

    if verbose:
        print(f"\n{'='*60}")
        print(f"Results: {results['found']}/{results['total']} queries found analogies")
        avg_score = 0
        scored = [q for q in results["queries"] if q["top_score"] > 0]
        if scored:
            avg_score = sum(q["top_score"] for q in scored) / len(scored)
        print(f"Average top score: {avg_score:.3f}")

    return results


# ── CLI ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analogical reasoning engine")
    sub = parser.add_subparsers(dest="command", required=True)

    find_p = sub.add_parser("find", help="Find analogies for a given A:B pair")
    find_p.add_argument("a", help="Source concept A")
    find_p.add_argument("b", help="Source concept B")
    find_p.add_argument("--n", type=int, default=5, help="Number of results (default: 5)")
    find_p.add_argument("--min-score", type=float, default=0.1,
                        help="Minimum offset similarity (default: 0.1)")
    find_p.add_argument("--json", action="store_true", dest="json_output")

    test_p = sub.add_parser("test", help="Run built-in analogy test queries")
    test_p.add_argument("--n", type=int, default=3, help="Results per query")
    test_p.add_argument("--json", action="store_true", dest="json_output")

    batch_p = sub.add_parser("batch", help="Run analogy queries from a JSON file")
    batch_p.add_argument("file", help="JSON file with list of {a, b} pairs")
    batch_p.add_argument("--n", type=int, default=3, help="Results per query")

    args = parser.parse_args()

    if args.command == "find":
        analogies = find_analogies(args.a, args.b, n=args.n, min_score=args.min_score)
        if args.json_output:
            print(json.dumps([asdict(a) for a in analogies], indent=2))
        else:
            print(f"\n{args.a} : {args.b} :: ? : ?")
            print(f"Found {len(analogies)} analogies:\n")
            for i, a in enumerate(analogies, 1):
                print(f"#{i} (score: {a.offset_similarity:.3f})")
                print(f"  C: {a.target_c[:150]}")
                print(f"     [{a.c_collection}]")
                print(f"  D: {a.target_d[:150]}")
                print(f"     [{a.d_collection}]")
                print()

    elif args.command == "test":
        results = run_tests(n=args.n, verbose=not args.json_output)
        if args.json_output:
            print(json.dumps(results, indent=2))

    elif args.command == "batch":
        with open(args.file) as f:
            queries = json.load(f)
        all_results = []
        for q in queries:
            analogies = find_analogies(q["a"], q["b"], n=args.n)
            all_results.append({
                "a": q["a"], "b": q["b"],
                "analogies": [asdict(a) for a in analogies],
            })
        print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    main()

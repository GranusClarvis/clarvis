"""Hybrid retrieval: embedding pre-filter → LLM re-rank.

Inspired by the Claude Code harness `findRelevantMemories.ts` approach
where Sonnet picks the top-5 most relevant memory files per turn using
a sideQuery. This module adapts that pattern for ClarvisDB:

  1. Embedding pre-filter: brain.recall() returns top-N candidates (N=10-15)
  2. LLM re-rank: A cheap model (Gemini Flash via OpenRouter) scores each
     candidate's relevance to the task, picking top-K (K=5)
  3. Fallback: If LLM call fails or times out, return embedding results as-is

The harness approach trades embedding precision for LLM judgment —
an LLM can understand intent ("what's blocking deployment?" matches
a memory about CI failures even if keywords don't overlap). Our hybrid
keeps embedding speed for pre-filtering while adding semantic understanding.

Usage:
    from clarvis.brain.llm_rerank import hybrid_recall

    results = hybrid_recall(brain, "What's blocking the release?", n=5)
    # Returns list of dicts with 'document', 'metadata', 'distance', 'rerank_score'
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
import urllib.error

_log = logging.getLogger("clarvis.brain.llm_rerank")

# === Configuration ===

# Pre-filter: fetch this many candidates from embedding search
PRE_FILTER_N = 12

# Re-rank: return this many final results (matches harness top-5)
DEFAULT_TOP_K = 5

# Model for re-ranking (cheap, fast, good at structured output)
RERANK_MODEL = "google/gemini-3-flash-preview"

# Timeout for LLM call (seconds) — must be fast for heartbeat pipeline
LLM_TIMEOUT = 15

# Max document chars to send per candidate (truncate long memories)
MAX_DOC_CHARS = 300

# Cost guard: skip LLM re-rank if disabled
ENV_ENABLE = "CLARVIS_LLM_RERANK"  # set to "1" to enable


def _get_api_key() -> str | None:
    """Get OpenRouter API key, same path as task_router."""
    try:
        from clarvis.orch.cost_api import get_api_key
        return get_api_key()
    except Exception:
        # Fallback: read from auth.json directly
        auth_path = os.path.join(os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw")), "agents/main/agent/auth.json")
        try:
            with open(auth_path) as f:
                data = json.load(f)
            for key in data.get("keys", []):
                if key.get("provider") == "openrouter":
                    return key.get("key")
            # Try flat format
            return data.get("openrouter_api_key") or data.get("api_key")
        except Exception:
            return None


def _build_rerank_prompt(query: str, candidates: list[dict]) -> str:
    """Build a prompt asking the LLM to rank candidates by relevance."""
    lines = [
        "You are a memory relevance ranker. Given a QUERY and numbered CANDIDATES, "
        "score each candidate's relevance to the query on a scale of 0-10.",
        "",
        "Rules:",
        "- 10 = directly answers the query",
        "- 7-9 = highly relevant, provides important context",
        "- 4-6 = somewhat relevant, tangentially useful",
        "- 1-3 = marginally relevant",
        "- 0 = irrelevant",
        "",
        f"QUERY: {query}",
        "",
        "CANDIDATES:",
    ]

    for i, c in enumerate(candidates):
        doc = c.get("document", "")[:MAX_DOC_CHARS]
        collection = c.get("metadata", {}).get("collection", "unknown")
        lines.append(f"[{i}] (collection: {collection}) {doc}")

    lines.extend([
        "",
        "Respond with ONLY a JSON array of objects, one per candidate:",
        '[{"idx": 0, "score": 8, "reason": "brief reason"}, ...]',
        "Include ALL candidates. No markdown fencing.",
    ])

    return "\n".join(lines)


def _call_reranker(prompt: str, api_key: str) -> list[dict] | None:
    """Call OpenRouter for re-ranking scores. Returns parsed JSON or None."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = json.dumps({
        "model": RERANK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clarvis.openclaw.local",
        "X-Title": "Clarvis LLM Reranker",
    })

    try:
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        elapsed_ms = (time.monotonic() - t0) * 1000

        content = data["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        usage = data.get("usage", {})
        _log.info("LLM rerank: %.0fms, %d prompt + %d completion tokens",
                  elapsed_ms,
                  usage.get("prompt_tokens", 0),
                  usage.get("completion_tokens", 0))

        scores = json.loads(content)
        if isinstance(scores, list):
            return scores
        _log.warning("LLM rerank returned non-list: %s", type(scores))
        return None

    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        _log.warning("LLM rerank failed: %s", e)
        return None
    except Exception as e:
        _log.warning("LLM rerank unexpected error: %s", e)
        return None


def _local_rerank(query: str, candidates: list[dict]) -> list[dict]:
    """Local cross-encoder re-rank using BM25 + semantic + importance + recency.

    This is a cost-free alternative to LLM re-ranking. It re-scores candidates
    using the CRAG composite metric (retrieval_eval.score_result) which combines:
      50% semantic similarity + 25% BM25 keyword + 15% importance + 10% recency

    The key insight: embedding recall ranks by distance alone (85% weight).
    Re-ranking with a multi-factor score can promote results that have strong
    keyword overlap or high importance even if embedding distance is slightly worse.
    This approximates what an LLM re-ranker would do — understand intent through
    multiple signals rather than just vector proximity.
    """
    from .retrieval_eval import score_result, BM25Scorer

    docs = [c.get("document", "") for c in candidates]
    bm25 = BM25Scorer(docs)

    scored = []
    for i, c in enumerate(candidates):
        composite = score_result(c, query, bm25_scorer=bm25, doc_index=i)
        scored.append((composite, i, c))

    # Sort by composite score descending, break ties by original rank
    scored.sort(key=lambda x: (-x[0], x[1]))

    for composite, orig_idx, c in scored:
        c["rerank_score"] = round(composite * 10, 2)  # scale to 0-10 for consistency
        c["rerank_reason"] = f"local cross-encoder (orig_rank={orig_idx})"
        c["rerank_method"] = "local"

    return [c for _, _, c in scored]


def hybrid_recall(
    brain_instance,
    query: str,
    n: int = DEFAULT_TOP_K,
    pre_filter_n: int = PRE_FILTER_N,
    collections=None,
    min_importance=None,
    since_days=None,
    attention_boost: bool = True,
    graph_expand: bool = False,
    force_llm: bool = False,
    mode: str = "auto",
) -> list[dict]:
    """Hybrid retrieval: embedding pre-filter → re-rank.

    Modes:
        "auto" — Try LLM re-rank if enabled, fall back to local re-rank
        "llm"  — LLM re-rank only (fails to embedding-only if no API)
        "local" — Local cross-encoder re-rank (BM25+semantic, no API cost)
        "embedding" — Embedding-only (no re-ranking, baseline)

    Args:
        brain_instance: ClarvisDB brain instance (has .recall())
        query: Search query
        n: Number of final results to return
        pre_filter_n: Number of candidates from embedding search
        collections: Optional collection filter
        min_importance: Minimum importance threshold
        since_days: Temporal filter
        attention_boost: Use GWT attention boost in pre-filter
        graph_expand: Use graph expansion in pre-filter
        force_llm: Force LLM re-rank even if env var not set
        mode: Re-ranking mode ("auto", "llm", "local", "embedding")

    Returns:
        List of result dicts with added 'rerank_score', 'rerank_reason',
        'rerank_method' fields.
    """
    t0 = time.monotonic()

    # Phase 1: Embedding pre-filter
    candidates = brain_instance.recall(
        query,
        collections=collections,
        n=pre_filter_n,
        min_importance=min_importance,
        since_days=since_days,
        attention_boost=attention_boost,
        graph_expand=graph_expand,
        filter_bridges=True,
    )

    if not candidates:
        return []

    # Phase 2: Determine re-ranking strategy
    if mode == "embedding":
        for c in candidates[:n]:
            c["rerank_score"] = None
            c["rerank_reason"] = "embedding-only"
            c["rerank_method"] = "embedding"
        return candidates[:n]

    use_llm = mode == "llm" or (mode == "auto" and (force_llm or os.environ.get(ENV_ENABLE) == "1"))

    if use_llm:
        api_key = _get_api_key()
        if api_key:
            prompt = _build_rerank_prompt(query, candidates)
            scores = _call_reranker(prompt, api_key)
            if scores is not None:
                # Merge LLM scores
                score_map = {}
                for s in scores:
                    idx = s.get("idx")
                    if isinstance(idx, int) and 0 <= idx < len(candidates):
                        score_map[idx] = {
                            "score": float(s.get("score", 0)),
                            "reason": s.get("reason", ""),
                        }
                for i, c in enumerate(candidates):
                    if i in score_map:
                        c["rerank_score"] = score_map[i]["score"]
                        c["rerank_reason"] = score_map[i]["reason"]
                        c["rerank_method"] = "llm"
                    else:
                        c["rerank_score"] = max(0, 5.0 - i * 0.5)
                        c["rerank_reason"] = "not scored by LLM"
                        c["rerank_method"] = "llm-fallback"
                reranked = sorted(
                    enumerate(candidates),
                    key=lambda x: (-x[1].get("rerank_score", 0), x[0]),
                )
                result = [c for _, c in reranked[:n]]
                elapsed_ms = (time.monotonic() - t0) * 1000
                _log.info("hybrid_recall(llm): %d → %d in %.0fms", len(candidates), len(result), elapsed_ms)
                return result
            _log.warning("LLM rerank failed, falling back to local rerank")
        else:
            _log.warning("No API key, falling back to local rerank")

    # Phase 3: Local cross-encoder re-rank (default path)
    reranked = _local_rerank(query, candidates)
    result = reranked[:n]

    elapsed_ms = (time.monotonic() - t0) * 1000
    _log.info("hybrid_recall(local): %d → %d in %.0fms", len(candidates), len(result), elapsed_ms)
    return result


def benchmark_hybrid(brain_instance, benchmark_pairs: list[dict], k: int = 3) -> dict:
    """Run benchmark comparing embedding-only vs hybrid retrieval.

    Args:
        brain_instance: ClarvisDB brain instance
        benchmark_pairs: List of dicts with 'query', 'expected_substrings', etc.
        k: Number of results to evaluate

    Returns:
        Dict with 'embedding_only' and 'hybrid' metrics for comparison.
    """
    from .retrieval_eval import score_result

    def _check_hit(result, pair):
        doc = result.get("document", "").lower()
        for sub in pair["expected_substrings"]:
            if sub.lower() in doc:
                return True
        return False

    results = {"embedding_only": [], "hybrid": [], "per_query": []}

    for pair in benchmark_pairs:
        query = pair["query"]

        # Embedding-only
        emb_results = brain_instance.recall(query, n=k, attention_boost=True, filter_bridges=True)
        emb_hits = sum(1 for r in emb_results if _check_hit(r, pair))
        emb_p_at_k = emb_hits / k if k > 0 else 0
        emb_p_at_1 = 1.0 if emb_results and _check_hit(emb_results[0], pair) else 0.0

        # Hybrid
        hyb_results = hybrid_recall(
            brain_instance, query, n=k, pre_filter_n=PRE_FILTER_N, force_llm=True,
        )
        hyb_hits = sum(1 for r in hyb_results if _check_hit(r, pair))
        hyb_p_at_k = hyb_hits / k if k > 0 else 0
        hyb_p_at_1 = 1.0 if hyb_results and _check_hit(hyb_results[0], pair) else 0.0

        query_result = {
            "id": pair.get("id", ""),
            "query": query,
            "category": pair.get("category", ""),
            "embedding": {
                "precision_at_k": emb_p_at_k,
                "precision_at_1": emb_p_at_1,
                "hits": emb_hits,
                "top_doc": (emb_results[0].get("document", "")[:100] if emb_results else ""),
            },
            "hybrid": {
                "precision_at_k": hyb_p_at_k,
                "precision_at_1": hyb_p_at_1,
                "hits": hyb_hits,
                "top_doc": (hyb_results[0].get("document", "")[:100] if hyb_results else ""),
                "rerank_scores": [r.get("rerank_score") for r in hyb_results],
            },
            "improved": hyb_p_at_k > emb_p_at_k,
            "degraded": hyb_p_at_k < emb_p_at_k,
        }
        results["per_query"].append(query_result)

    # Aggregate
    n_queries = len(benchmark_pairs)
    if n_queries > 0:
        results["embedding_only"] = {
            "avg_precision_at_k": sum(q["embedding"]["precision_at_k"] for q in results["per_query"]) / n_queries,
            "avg_precision_at_1": sum(q["embedding"]["precision_at_1"] for q in results["per_query"]) / n_queries,
        }
        results["hybrid"] = {
            "avg_precision_at_k": sum(q["hybrid"]["precision_at_k"] for q in results["per_query"]) / n_queries,
            "avg_precision_at_1": sum(q["hybrid"]["precision_at_1"] for q in results["per_query"]) / n_queries,
        }
        results["improved_count"] = sum(1 for q in results["per_query"] if q["improved"])
        results["degraded_count"] = sum(1 for q in results["per_query"] if q["degraded"])
        results["unchanged_count"] = n_queries - results["improved_count"] - results["degraded_count"]

    return results


# === CLI ===

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    usage = """Usage:
    python3 -m clarvis.brain.llm_rerank query "search text" [--n 5]
    python3 -m clarvis.brain.llm_rerank benchmark [--k 3]
    python3 -m clarvis.brain.llm_rerank compare "search text"  # side-by-side"""

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]

    # Import brain
    from clarvis.brain import brain

    if cmd == "query":
        if len(sys.argv) < 3:
            print("Error: provide a query string")
            sys.exit(1)
        q = " ".join(sys.argv[2:]).replace("--n", "").strip()
        n = 5
        for i, arg in enumerate(sys.argv):
            if arg == "--n" and i + 1 < len(sys.argv):
                n = int(sys.argv[i + 1])

        results = hybrid_recall(brain, q, n=n, force_llm=True)
        for i, r in enumerate(results):
            score = r.get("rerank_score", "?")
            reason = r.get("rerank_reason", "")
            doc = r.get("document", "")[:120]
            print(f"  [{i+1}] score={score} | {doc}")
            if reason:
                print(f"       reason: {reason}")

    elif cmd == "compare":
        if len(sys.argv) < 3:
            print("Error: provide a query string")
            sys.exit(1)
        q = " ".join(sys.argv[2:])

        print(f"Query: {q}\n")

        # Embedding-only
        print("=== Embedding-only (top 5) ===")
        emb = brain.recall(q, n=5, attention_boost=True, filter_bridges=True)
        for i, r in enumerate(emb):
            dist = r.get("distance", "?")
            doc = r.get("document", "")[:120]
            print(f"  [{i+1}] dist={dist:.3f} | {doc}")

        # Local rerank
        print("\n=== Local cross-encoder rerank (top 5) ===")
        loc = hybrid_recall(brain, q, n=5, mode="local")
        for i, r in enumerate(loc):
            score = r.get("rerank_score", "?")
            reason = r.get("rerank_reason", "")
            doc = r.get("document", "")[:120]
            print(f"  [{i+1}] score={score} | {doc}")
            if reason:
                print(f"       {reason}")

        # LLM rerank (if enabled)
        if os.environ.get(ENV_ENABLE) == "1":
            print("\n=== LLM rerank (top 5) ===")
            hyb = hybrid_recall(brain, q, n=5, mode="llm", force_llm=True)
            for i, r in enumerate(hyb):
                score = r.get("rerank_score", "?")
                reason = r.get("rerank_reason", "")
                doc = r.get("document", "")[:120]
                print(f"  [{i+1}] rerank={score} | {doc}")
                if reason:
                    print(f"       reason: {reason}")

    elif cmd == "benchmark":
        k = 3
        for i, arg in enumerate(sys.argv):
            if arg == "--k" and i + 1 < len(sys.argv):
                k = int(sys.argv[i + 1])

        # Import benchmark pairs
        from retrieval_benchmark import BENCHMARK_PAIRS

        print(f"Running hybrid benchmark ({len(BENCHMARK_PAIRS)} queries, k={k})...")
        results = benchmark_hybrid(brain, BENCHMARK_PAIRS, k=k)

        print(f"\n{'='*60}")
        print(f"EMBEDDING-ONLY:  P@{k}={results['embedding_only']['avg_precision_at_k']:.3f}  "
              f"P@1={results['embedding_only']['avg_precision_at_1']:.3f}")
        print(f"HYBRID (LLM):    P@{k}={results['hybrid']['avg_precision_at_k']:.3f}  "
              f"P@1={results['hybrid']['avg_precision_at_1']:.3f}")
        print(f"\nImproved: {results['improved_count']}/{len(BENCHMARK_PAIRS)}  "
              f"Degraded: {results['degraded_count']}/{len(BENCHMARK_PAIRS)}  "
              f"Unchanged: {results['unchanged_count']}/{len(BENCHMARK_PAIRS)}")

        # Show per-query details for improved/degraded
        for q in results["per_query"]:
            if q["improved"] or q["degraded"]:
                status = "IMPROVED" if q["improved"] else "DEGRADED"
                print(f"\n  [{status}] {q['id']}: {q['query']}")
                print(f"    Embedding P@{k}={q['embedding']['precision_at_k']:.3f} → "
                      f"Hybrid P@{k}={q['hybrid']['precision_at_k']:.3f}")

        # Save results
        out_path = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "data", "retrieval_benchmark", "hybrid_comparison.json")
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {out_path}")

    else:
        print(usage)
        sys.exit(1)

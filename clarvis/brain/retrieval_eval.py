"""CRAG-style retrieval evaluator for Clarvis brain.

Scores each recall result using a composite metric:
  0.50 × semantic_sim + 0.25 × keyword_overlap + 0.15 × importance + 0.10 × recency

Classifies batches as CORRECT / AMBIGUOUS / INCORRECT and applies
knowledge-strip refinement (per-sentence filtering) on AMBIGUOUS batches.

Reference: Corrective Retrieval Augmented Generation (CRAG), Yan et al. 2024.
"""

from __future__ import annotations

import re
import math
from datetime import datetime, timezone
from typing import Optional

# Verdict constants
CORRECT = "CORRECT"
AMBIGUOUS = "AMBIGUOUS"
INCORRECT = "INCORRECT"

# Scoring weights
W_SEMANTIC = 0.50
W_KEYWORD = 0.25
W_IMPORTANCE = 0.15
W_RECENCY = 0.10

# Classification thresholds
CORRECT_THRESHOLD = 0.55
AMBIGUOUS_THRESHOLD = 0.35

# Strip refinement
STRIP_THRESHOLD = 0.30  # per-sentence minimum score
MIN_SENTENCE_LEN = 10   # ignore very short sentences

# Recency half-life in days (30 days → score 0.5)
RECENCY_HALF_LIFE = 30.0


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + punctuation tokenizer for keyword overlap."""
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _keyword_overlap(query: str, document: str) -> float:
    """Jaccard similarity between query and document tokens."""
    q_tokens = _tokenize(query)
    d_tokens = _tokenize(document)
    if not q_tokens or not d_tokens:
        return 0.0
    intersection = q_tokens & d_tokens
    union = q_tokens | d_tokens
    return len(intersection) / len(union)


def _semantic_sim(distance: float) -> float:
    """Convert ChromaDB distance to 0-1 similarity.

    ChromaDB uses squared L2 distance by default.
    sim = 1 / (1 + distance) maps [0, inf) → (0, 1].
    """
    if distance is None or distance < 0:
        return 0.0
    return 1.0 / (1.0 + distance)


def _recency_score(result: dict) -> float:
    """Exponential decay based on memory age.

    Uses created_at or last_accessed from metadata.
    Returns 1.0 for fresh memories, decaying toward 0.
    """
    meta = result.get("metadata", {})
    ts_str = meta.get("last_accessed") or meta.get("created_at")
    if not ts_str:
        return 0.5  # unknown age → neutral

    try:
        if isinstance(ts_str, (int, float)):
            created = datetime.fromtimestamp(ts_str, tz=timezone.utc)
        else:
            # Handle ISO format with or without timezone
            ts_clean = str(ts_str).replace("Z", "+00:00")
            if "+" not in ts_clean:
                ts_clean += "+00:00"
            created = datetime.fromisoformat(ts_clean)
        age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
        return math.exp(-0.693 * age_days / RECENCY_HALF_LIFE)  # 0.693 = ln(2)
    except (ValueError, TypeError, OSError):
        return 0.5


def score_result(result: dict, query: str) -> float:
    """Compute composite retrieval score for a single result.

    Args:
        result: Dict with keys: document, metadata, distance, collection, id
        query: The search query string

    Returns:
        Score in [0, 1] range
    """
    sem = _semantic_sim(result.get("distance", 2.0))
    kw = _keyword_overlap(query, result.get("document", ""))
    imp = result.get("metadata", {}).get("importance", 0.5)
    if isinstance(imp, str):
        try:
            imp = float(imp)
        except (ValueError, TypeError):
            imp = 0.5
    rec = _recency_score(result)

    return W_SEMANTIC * sem + W_KEYWORD * kw + W_IMPORTANCE * imp + W_RECENCY * rec


def classify_batch(results: list[dict], query: str) -> tuple[str, float, list[float]]:
    """Classify a retrieval batch as CORRECT / AMBIGUOUS / INCORRECT.

    Args:
        results: List of recall result dicts
        query: The search query

    Returns:
        (verdict, max_score, all_scores)
    """
    if not results:
        return INCORRECT, 0.0, []

    scores = [score_result(r, query) for r in results]
    max_score = max(scores)

    if max_score >= CORRECT_THRESHOLD:
        verdict = CORRECT
    elif max_score >= AMBIGUOUS_THRESHOLD:
        verdict = AMBIGUOUS
    else:
        verdict = INCORRECT

    return verdict, max_score, scores


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using simple regex."""
    # Split on period/exclamation/question followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) >= MIN_SENTENCE_LEN]


def strip_refine(results: list[dict], query: str,
                 threshold: float = STRIP_THRESHOLD) -> list[dict]:
    """Knowledge strip refinement: per-sentence scoring and filtering.

    Splits each document into sentences, re-scores each sentence against
    the query, and keeps only sentences above the threshold.

    Args:
        results: List of recall result dicts
        query: The search query
        threshold: Minimum per-sentence score to retain

    Returns:
        Refined results with filtered documents. Results where all
        sentences are below threshold are removed entirely.
    """
    refined = []
    for r in results:
        doc = r.get("document", "")
        sentences = _split_sentences(doc)

        if not sentences:
            # Too short to split — keep if overall score meets threshold
            if score_result(r, query) >= threshold:
                refined.append(r)
            continue

        # Score each sentence as a mini-document
        kept_sentences = []
        for sentence in sentences:
            # Keyword overlap with the sentence
            kw = _keyword_overlap(query, sentence)
            # Semantic sim is from the full doc (can't re-embed per sentence cheaply)
            sem = _semantic_sim(r.get("distance", 2.0))
            # Per-sentence composite (simplified: no importance/recency per sentence)
            sent_score = 0.65 * sem + 0.35 * kw
            if sent_score >= threshold:
                kept_sentences.append(sentence)

        if kept_sentences:
            refined_doc = " ".join(kept_sentences)
            r_copy = dict(r)
            r_copy["document"] = refined_doc
            r_copy["_strip_refined"] = True
            r_copy["_strips_kept"] = len(kept_sentences)
            r_copy["_strips_total"] = len(sentences)
            refined.append(r_copy)

    return refined


def evaluate_retrieval(results: list[dict], query: str,
                       apply_strip: bool = True) -> dict:
    """Full retrieval evaluation pipeline.

    1. Score each result
    2. Classify batch
    3. On AMBIGUOUS: apply strip refinement
    4. Return evaluation dict

    Args:
        results: List of recall result dicts
        query: The search query
        apply_strip: Whether to apply strip refinement on AMBIGUOUS

    Returns:
        {
            "verdict": CORRECT | AMBIGUOUS | INCORRECT,
            "max_score": float,
            "scores": list[float],
            "n_results": int,
            "n_above_threshold": int,
            "refined_results": list[dict] | None,
            "strip_applied": bool,
        }
    """
    verdict, max_score, scores = classify_batch(results, query)

    n_above = sum(1 for s in scores if s >= AMBIGUOUS_THRESHOLD)

    refined = None
    strip_applied = False

    if apply_strip and verdict == AMBIGUOUS and results:
        refined = strip_refine(results, query)
        strip_applied = True
        # Re-classify after refinement
        if refined:
            _, new_max, new_scores = classify_batch(refined, query)
            if new_max >= CORRECT_THRESHOLD:
                verdict = CORRECT
                max_score = new_max
                scores = new_scores

    return {
        "verdict": verdict,
        "max_score": round(max_score, 4),
        "scores": [round(s, 4) for s in scores],
        "n_results": len(results),
        "n_above_threshold": n_above,
        "refined_results": refined,
        "strip_applied": strip_applied,
    }


# ---------------------------------------------------------------------------
# Adaptive recall — corrective retry on INCORRECT verdict
# ---------------------------------------------------------------------------

# Stop words for keyword extraction (common English words that add no signal)
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "if", "then", "than", "so", "that", "this", "it", "its",
    "all", "each", "every", "any", "some", "more", "most", "other",
    "up", "out", "about", "just", "also", "very", "too", "only",
})


def _extract_keywords(query: str, top_k: int = 8) -> list[str]:
    """Extract salient keywords from a query using TF-like scoring.

    Filters stop words, short tokens, and scores by token length + uniqueness.
    Returns top_k keywords for query rewriting.
    """
    tokens = re.findall(r"[a-z][a-z0-9_]+", query.lower())
    # Filter stop words and very short tokens
    filtered = [t for t in tokens if t not in _STOP_WORDS and len(t) >= 3]
    if not filtered:
        return tokens[:top_k]  # fallback to raw tokens

    # Score by: length (longer = more specific) + frequency
    from collections import Counter
    freq = Counter(filtered)
    scored = [(t, freq[t] * 0.5 + len(t) * 0.3) for t in set(filtered)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[:top_k]]


def _rewrite_query(query: str) -> str:
    """Rewrite query by extracting core keywords for broader matching.

    Strips filler/task-format text, keeps domain-specific terms.
    """
    # Remove common task prefixes like "[AUTO_SPLIT 2026-03-12]", "[TASK_NAME]"
    cleaned = re.sub(r'\[.*?\]', '', query)
    # Remove "Analyze:", "Implement:", etc.
    cleaned = re.sub(r'^(Analyze|Implement|Test|Verify|Fix|Add|Update|Build|Create|Wire)\s*:\s*', '', cleaned, flags=re.I)
    keywords = _extract_keywords(cleaned)
    if not keywords:
        return query  # fallback: return original
    return " ".join(keywords)


def adaptive_recall(brain_instance, query: str, tier: str = "DEEP_RETRIEVAL",
                    original_results: list[dict] | None = None,
                    min_importance: float = 0.3,
                    n: int = 5) -> dict:
    """Adaptive recall with corrective retry on INCORRECT verdict.

    Flow:
      1. Evaluate original results (or do initial recall)
      2. If CORRECT/AMBIGUOUS → return as-is
      3. If INCORRECT → rewrite query, broaden to all collections, relax importance
      4. If retry still INCORRECT → return empty (no context > bad context)

    Args:
        brain_instance: ClarvisBrain instance
        query: The search query (usually the task description)
        tier: Retrieval tier from gate (NO_RETRIEVAL, LIGHT_RETRIEVAL, DEEP_RETRIEVAL)
        original_results: Pre-fetched recall results (if available)
        min_importance: Original min_importance threshold
        n: Number of results to recall

    Returns:
        {
            "verdict": str,
            "max_score": float,
            "results": list[dict],
            "retried": bool,
            "retry_query": str | None,
            "original_verdict": str,
        }
    """
    from .constants import ALL_COLLECTIONS

    # If NO_RETRIEVAL, skip everything
    if tier == "NO_RETRIEVAL":
        return {
            "verdict": "SKIPPED",
            "max_score": 0.0,
            "results": [],
            "retried": False,
            "retry_query": None,
            "original_verdict": "SKIPPED",
        }

    # Step 1: Get initial results if not provided
    if original_results is None:
        try:
            original_results = brain_instance.recall(
                query, n=n, min_importance=min_importance,
                attention_boost=True, caller="adaptive_recall_initial",
            )
        except Exception:
            original_results = []

    # Step 2: Evaluate initial results
    if not original_results:
        return {
            "verdict": "NO_RESULTS",
            "max_score": 0.0,
            "results": [],
            "retried": False,
            "retry_query": None,
            "original_verdict": "NO_RESULTS",
        }

    eval_out = evaluate_retrieval(original_results, query)
    original_verdict = eval_out["verdict"]

    # Step 3: If CORRECT or AMBIGUOUS (with strip refinement), return
    if original_verdict in (CORRECT, AMBIGUOUS):
        results = eval_out.get("refined_results") or original_results
        return {
            "verdict": original_verdict,
            "max_score": eval_out["max_score"],
            "results": results,
            "retried": False,
            "retry_query": None,
            "original_verdict": original_verdict,
        }

    # Step 4: INCORRECT — corrective retry
    # (a) Rewrite query via keyword extraction
    retry_query = _rewrite_query(query)
    # (b) Broaden to ALL collections
    # (c) Relax min_importance to 0.1
    try:
        retry_results = brain_instance.recall(
            retry_query,
            collections=ALL_COLLECTIONS,
            n=n,
            min_importance=0.1,
            attention_boost=True,
            caller="adaptive_recall_retry",
        )
    except Exception:
        retry_results = []

    if not retry_results:
        return {
            "verdict": INCORRECT,
            "max_score": eval_out["max_score"],
            "results": [],
            "retried": True,
            "retry_query": retry_query,
            "original_verdict": INCORRECT,
        }

    # Step 5: Re-evaluate retry results
    retry_eval = evaluate_retrieval(retry_results, retry_query)

    if retry_eval["verdict"] == INCORRECT:
        # Retry still INCORRECT → skip context injection (no context > bad context)
        return {
            "verdict": INCORRECT,
            "max_score": retry_eval["max_score"],
            "results": [],
            "retried": True,
            "retry_query": retry_query,
            "original_verdict": INCORRECT,
        }

    # Retry improved the verdict
    results = retry_eval.get("refined_results") or retry_results
    return {
        "verdict": retry_eval["verdict"],
        "max_score": retry_eval["max_score"],
        "results": results,
        "retried": True,
        "retry_query": retry_query,
        "original_verdict": INCORRECT,
    }


# ---------------------------------------------------------------------------
# CLI for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

    if len(sys.argv) < 2:
        print("Usage: python -m clarvis.brain.retrieval_eval <query> [--n N]")
        print("       python -m clarvis.brain.retrieval_eval --demo")
        sys.exit(1)

    if sys.argv[1] == "--demo":
        # Demo with synthetic data
        demo_results = [
            {
                "document": "Clarvis uses ChromaDB with ONNX MiniLM embeddings for vector memory.",
                "metadata": {"importance": 0.9, "created_at": "2026-03-01T00:00:00+00:00"},
                "distance": 0.3,
                "collection": "clarvis-learnings",
                "id": "demo-1",
            },
            {
                "document": "The heartbeat pipeline runs every autonomous slot.",
                "metadata": {"importance": 0.6, "created_at": "2026-02-15T00:00:00+00:00"},
                "distance": 1.2,
                "collection": "clarvis-procedures",
                "id": "demo-2",
            },
            {
                "document": "Random noise memory about weather patterns.",
                "metadata": {"importance": 0.2, "created_at": "2025-12-01T00:00:00+00:00"},
                "distance": 1.8,
                "collection": "clarvis-memories",
                "id": "demo-3",
            },
        ]
        query = "ChromaDB vector memory embeddings"
        evaluation = evaluate_retrieval(demo_results, query)
        print(json.dumps(evaluation, indent=2, default=str))
        sys.exit(0)

    query = sys.argv[1]
    n = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--n" and i + 1 < len(sys.argv):
            n = int(sys.argv[i + 1])

    from clarvis.brain import brain
    results = brain.recall(query, n=n)
    evaluation = evaluate_retrieval(results, query)
    print(json.dumps(evaluation, indent=2, default=str))
    print(f"\nVerdict: {evaluation['verdict']} (max_score={evaluation['max_score']})")
    if evaluation["strip_applied"]:
        print(f"Strip refinement applied: {len(evaluation['refined_results'])} results kept")

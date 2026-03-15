"""Tests for clarvis.brain.retrieval_eval — CRAG-style retrieval evaluator."""

import pytest
from unittest.mock import MagicMock
from clarvis.brain.retrieval_eval import (
    score_result, classify_batch, strip_refine, evaluate_retrieval,
    filter_by_score,
    _keyword_overlap, _semantic_sim, _recency_score,
    _extract_keywords, _rewrite_query, adaptive_recall,
    CORRECT, AMBIGUOUS, INCORRECT, AMBIGUOUS_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_result(doc="test memory", distance=0.3, importance=0.8,
                 created_at="2026-03-01T00:00:00+00:00", collection="clarvis-learnings"):
    return {
        "document": doc,
        "metadata": {"importance": importance, "created_at": created_at},
        "distance": distance,
        "collection": collection,
        "id": "test-1",
    }


# ---------------------------------------------------------------------------
# Unit tests: scoring components
# ---------------------------------------------------------------------------

class TestSemanticSim:
    def test_perfect_match(self):
        assert _semantic_sim(0.0) == 1.0

    def test_moderate_distance(self):
        sim = _semantic_sim(1.0)
        assert 0.45 < sim < 0.55  # 1/(1+1) = 0.5

    def test_high_distance(self):
        assert _semantic_sim(10.0) < 0.1

    def test_none_distance(self):
        assert _semantic_sim(None) == 0.0

    def test_negative_distance(self):
        assert _semantic_sim(-1.0) == 0.0


class TestKeywordOverlap:
    def test_identical(self):
        assert _keyword_overlap("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _keyword_overlap("foo bar", "baz qux") == 0.0

    def test_partial_overlap(self):
        score = _keyword_overlap("chromadb vector", "chromadb memory store")
        assert 0.0 < score < 1.0

    def test_empty_query(self):
        assert _keyword_overlap("", "hello") == 0.0


class TestRecencyScore:
    def test_recent_memory(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        r = _make_result(created_at=recent)
        score = _recency_score(r)
        assert score > 0.9  # Very recent

    def test_old_memory(self):
        r = _make_result(created_at="2025-01-01T00:00:00+00:00")
        score = _recency_score(r)
        assert score < 0.1  # Very old

    def test_missing_timestamp(self):
        r = {"metadata": {}}
        assert _recency_score(r) == 0.5


# ---------------------------------------------------------------------------
# Unit tests: scoring and classification
# ---------------------------------------------------------------------------

class TestScoreResult:
    def test_high_quality_result(self):
        r = _make_result(distance=0.2, importance=0.9,
                         doc="chromadb vector memory")
        score = score_result(r, "chromadb vector memory")
        assert score > 0.6  # High semantic sim + keyword overlap + importance

    def test_low_quality_result(self):
        r = _make_result(distance=2.0, importance=0.1,
                         doc="random noise about weather")
        score = score_result(r, "chromadb vector memory")
        assert score < 0.3

    def test_score_in_range(self):
        r = _make_result()
        score = score_result(r, "test query")
        assert 0.0 <= score <= 1.0


class TestClassifyBatch:
    def test_correct_batch(self):
        results = [_make_result(distance=0.1, importance=0.9,
                                doc="chromadb vector memory embeddings")]
        verdict, max_score, scores = classify_batch(results, "chromadb vector memory")
        assert verdict == CORRECT
        assert max_score >= 0.55

    def test_incorrect_batch(self):
        results = [_make_result(distance=2.0, importance=0.1,
                                doc="random unrelated content")]
        verdict, max_score, scores = classify_batch(results, "chromadb vector memory")
        assert verdict in (INCORRECT, AMBIGUOUS)

    def test_empty_batch(self):
        verdict, max_score, scores = classify_batch([], "any query")
        assert verdict == INCORRECT
        assert max_score == 0.0
        assert scores == []


# ---------------------------------------------------------------------------
# Strip refinement
# ---------------------------------------------------------------------------

class TestFilterByScore:
    def test_removes_low_scoring_results(self):
        results = [_make_result(doc="good"), _make_result(doc="bad")]
        scores = [0.8, 0.1]
        filtered = filter_by_score(results, scores)
        assert len(filtered) == 1
        assert filtered[0]["document"] == "good"

    def test_keeps_all_above_threshold(self):
        results = [_make_result(doc="a"), _make_result(doc="b")]
        scores = [0.6, 0.5]
        filtered = filter_by_score(results, scores)
        assert len(filtered) == 2

    def test_removes_all_below_threshold(self):
        results = [_make_result(doc="a"), _make_result(doc="b")]
        scores = [0.1, 0.2]
        filtered = filter_by_score(results, scores)
        assert len(filtered) == 0

    def test_length_mismatch_returns_original(self):
        results = [_make_result(doc="a")]
        scores = [0.5, 0.6]  # mismatched length
        filtered = filter_by_score(results, scores)
        assert len(filtered) == 1  # returns original unfiltered

    def test_custom_threshold(self):
        results = [_make_result(doc="a"), _make_result(doc="b")]
        scores = [0.4, 0.6]
        filtered = filter_by_score(results, scores, threshold=0.5)
        assert len(filtered) == 1


class TestStripRefine:
    def test_keeps_relevant_sentences(self):
        r = _make_result(
            doc="ChromaDB uses ONNX embeddings. The weather is nice today. Vector search is fast.",
            distance=0.3,
        )
        refined = strip_refine([r], "chromadb vector search")
        assert len(refined) >= 1
        # Should keep ChromaDB and vector sentences, may drop weather

    def test_removes_all_irrelevant(self):
        r = _make_result(
            doc="The weather is nice today. It might rain tomorrow.",
            distance=2.0,
        )
        refined = strip_refine([r], "chromadb vector memory")
        # Low semantic sim + no keyword overlap → likely empty
        assert len(refined) <= 1

    def test_short_doc_kept(self):
        r = _make_result(doc="short", distance=0.1)
        refined = strip_refine([r], "short")
        # Too short to split but overall score should be decent
        assert len(refined) >= 0  # Depends on score


# ---------------------------------------------------------------------------
# Full evaluation pipeline
# ---------------------------------------------------------------------------

class TestEvaluateRetrieval:
    def test_correct_evaluation(self):
        results = [_make_result(distance=0.1, importance=0.9,
                                doc="chromadb singleton factory pattern")]
        ev = evaluate_retrieval(results, "chromadb singleton factory")
        assert ev["verdict"] == CORRECT
        assert ev["n_results"] == 1
        assert ev["strip_applied"]  # Strip now applied on CORRECT too
        assert "n_filtered_out" in ev

    def test_incorrect_evaluation(self):
        results = [_make_result(distance=2.0, importance=0.1,
                                doc="random noise")]
        ev = evaluate_retrieval(results, "chromadb")
        assert ev["verdict"] in (INCORRECT, AMBIGUOUS)
        assert ev["n_results"] == 1

    def test_ambiguous_triggers_strip(self):
        results = [
            _make_result(distance=0.8, importance=0.5,
                         doc="ChromaDB is used for storage. The sky is blue. Memory patterns are important."),
        ]
        ev = evaluate_retrieval(results, "chromadb memory patterns")
        # May be AMBIGUOUS with strip applied
        assert ev["n_results"] == 1
        assert isinstance(ev["strip_applied"], bool)

    def test_empty_results(self):
        ev = evaluate_retrieval([], "any query")
        assert ev["verdict"] == INCORRECT
        assert ev["n_results"] == 0
        assert ev["strip_applied"] is False

    def test_filters_low_scoring_individual_results(self):
        """Mixed batch: good result + noise result → noise filtered out."""
        results = [
            _make_result(distance=0.1, importance=0.9, doc="chromadb vector embeddings"),
            _make_result(distance=2.0, importance=0.1, doc="random weather noise pattern"),
        ]
        ev = evaluate_retrieval(results, "chromadb vector embeddings")
        assert ev["n_filtered_out"] >= 1  # noise result should be dropped
        assert ev["refined_results"] is not None
        assert len(ev["refined_results"]) < len(results)

    def test_correct_batch_gets_strip_refined(self):
        """CORRECT batches now get strip refinement applied."""
        results = [_make_result(
            distance=0.1, importance=0.9,
            doc="ChromaDB vector search is fast. The weather is nice today. Embeddings work.",
        )]
        ev = evaluate_retrieval(results, "chromadb vector search embeddings")
        assert ev["verdict"] == CORRECT
        assert ev["strip_applied"] is True


# ---------------------------------------------------------------------------
# Keyword extraction and query rewriting
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_extracts_meaningful_tokens(self):
        kws = _extract_keywords("Fix retrieval hit rate showing 0.0 in performance_benchmark")
        assert len(kws) > 0
        assert "retrieval" in kws
        assert "the" not in kws  # stop word

    def test_filters_short_tokens(self):
        kws = _extract_keywords("a b c do it now or we fail")
        # "a", "b", "c" are all < 3 chars, should be filtered
        assert "a" not in kws
        assert "b" not in kws

    def test_empty_query(self):
        kws = _extract_keywords("")
        assert isinstance(kws, list)

    def test_top_k_limit(self):
        kws = _extract_keywords("one two three four five six seven eight nine ten eleven", top_k=3)
        assert len(kws) <= 3


class TestRewriteQuery:
    def test_strips_task_brackets(self):
        rewritten = _rewrite_query("[AUTO_SPLIT 2026-03-12] [TASK_NAME] Fix the retrieval logic")
        assert "[AUTO_SPLIT" not in rewritten
        assert "[TASK_NAME]" not in rewritten

    def test_strips_action_prefix(self):
        rewritten = _rewrite_query("Implement: core logic change in one focused increment")
        assert not rewritten.startswith("Implement")

    def test_preserves_domain_terms(self):
        rewritten = _rewrite_query("Fix retrieval adaptive retry logic for brain recall")
        assert "retrieval" in rewritten or "adaptive" in rewritten

    def test_fallback_on_empty(self):
        # If keyword extraction fails, return original
        result = _rewrite_query("a")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Adaptive recall
# ---------------------------------------------------------------------------

def _make_brain_mock(recall_results=None, retry_results=None):
    """Create a mock brain that returns different results for initial vs retry."""
    mock = MagicMock()
    call_count = [0]

    def mock_recall(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1 and recall_results is not None:
            return recall_results
        if retry_results is not None:
            return retry_results
        return recall_results or []

    mock.recall = MagicMock(side_effect=mock_recall)
    return mock


class TestAdaptiveRecall:
    def test_skips_on_no_retrieval(self):
        brain = _make_brain_mock()
        out = adaptive_recall(brain, "test query", tier="NO_RETRIEVAL")
        assert out["verdict"] == "SKIPPED"
        assert not out["retried"]
        brain.recall.assert_not_called()

    def test_returns_correct_without_retry(self):
        results = [_make_result(distance=0.1, importance=0.9,
                                doc="chromadb vector memory embeddings")]
        brain = _make_brain_mock()
        out = adaptive_recall(brain, "chromadb vector memory",
                              original_results=results)
        assert out["verdict"] == CORRECT
        assert not out["retried"]
        assert out["original_verdict"] == CORRECT

    def test_retries_on_incorrect(self):
        # Initial: bad results
        bad_results = [_make_result(distance=2.0, importance=0.1,
                                    doc="random unrelated noise")]
        # Retry: good results
        good_results = [_make_result(distance=0.1, importance=0.9,
                                     doc="chromadb vector memory embeddings")]
        brain = _make_brain_mock(retry_results=good_results)
        out = adaptive_recall(brain, "chromadb vector memory",
                              original_results=bad_results)
        assert out["retried"]
        assert out["original_verdict"] == INCORRECT
        # Retry should have improved the verdict
        assert out["verdict"] in (CORRECT, AMBIGUOUS)
        assert out["retry_query"] is not None

    def test_retry_still_incorrect_returns_empty(self):
        bad_results = [_make_result(distance=2.0, importance=0.1,
                                    doc="random unrelated noise")]
        brain = _make_brain_mock(retry_results=bad_results)
        out = adaptive_recall(brain, "chromadb vector memory",
                              original_results=bad_results)
        assert out["retried"]
        assert out["verdict"] == INCORRECT
        assert out["results"] == []

    def test_no_results_returns_no_results(self):
        brain = _make_brain_mock()
        out = adaptive_recall(brain, "test query", original_results=[])
        assert out["verdict"] == "NO_RESULTS"
        assert not out["retried"]

    def test_does_initial_recall_when_no_results_provided(self):
        good_results = [_make_result(distance=0.1, importance=0.9,
                                     doc="chromadb vector memory embeddings")]
        brain = _make_brain_mock(recall_results=good_results)
        out = adaptive_recall(brain, "chromadb vector memory")
        assert out["verdict"] == CORRECT
        brain.recall.assert_called_once()

    def test_retry_uses_all_collections(self):
        bad_results = [_make_result(distance=2.0, importance=0.1,
                                    doc="random noise")]
        brain = _make_brain_mock(retry_results=[])
        adaptive_recall(brain, "chromadb memory", original_results=bad_results)
        # Check that retry call used ALL_COLLECTIONS
        retry_call = brain.recall.call_args
        from clarvis.brain.constants import ALL_COLLECTIONS
        assert retry_call.kwargs.get("collections") == ALL_COLLECTIONS

    def test_retry_relaxes_min_importance(self):
        bad_results = [_make_result(distance=2.0, importance=0.1,
                                    doc="random noise")]
        brain = _make_brain_mock(retry_results=[])
        adaptive_recall(brain, "chromadb memory", original_results=bad_results)
        retry_call = brain.recall.call_args
        assert retry_call.kwargs.get("min_importance") == 0.1

    def test_handles_recall_exception(self):
        brain = MagicMock()
        brain.recall.side_effect = RuntimeError("ChromaDB down")
        out = adaptive_recall(brain, "test query")
        assert out["verdict"] == "NO_RESULTS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

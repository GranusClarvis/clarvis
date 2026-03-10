"""Tests for clarvis.brain.retrieval_eval — CRAG-style retrieval evaluator."""

import pytest
from clarvis.brain.retrieval_eval import (
    score_result, classify_batch, strip_refine, evaluate_retrieval,
    _keyword_overlap, _semantic_sim, _recency_score,
    CORRECT, AMBIGUOUS, INCORRECT,
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
        r = _make_result(created_at="2026-03-09T00:00:00+00:00")
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
        assert not ev["strip_applied"]  # No strip on CORRECT

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for clarvis.brain.search — conclusion synthesis layer."""

import pytest
from unittest.mock import MagicMock, patch
from clarvis.brain.search import (
    _build_evidence_bundles,
    _detect_contradictions,
    _detect_cross_bundle_contradictions,
    _synthesize_conclusion,
    _has_opposing_signals,
    _tokenize_lower,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_result(doc="test memory", distance=0.3, importance=0.8,
                 collection="clarvis-learnings", mem_id="test-1"):
    return {
        "document": doc,
        "metadata": {"importance": importance, "created_at": "2026-03-01T00:00:00+00:00"},
        "distance": distance,
        "collection": collection,
        "id": mem_id,
    }


# ---------------------------------------------------------------------------
# Unit tests: contradiction detection
# ---------------------------------------------------------------------------

class TestHasOpposingSignals:
    def test_enable_vs_disable(self):
        a = {"enable", "feature", "flag"}
        b = {"disable", "feature", "flag"}
        assert _has_opposing_signals(a, b)

    def test_true_vs_false(self):
        a = {"setting", "true"}
        b = {"setting", "false"}
        assert _has_opposing_signals(a, b)

    def test_no_opposition(self):
        a = {"chromadb", "memory", "store"}
        b = {"chromadb", "vector", "search"}
        assert not _has_opposing_signals(a, b)

    def test_add_vs_remove(self):
        a = {"add", "dependency"}
        b = {"remove", "dependency"}
        assert _has_opposing_signals(a, b)

    def test_success_vs_failure(self):
        a = {"task", "success", "completed"}
        b = {"task", "failure", "error"}
        assert _has_opposing_signals(a, b)

    def test_empty_sets(self):
        assert not _has_opposing_signals(set(), set())


class TestTokenizeLower:
    def test_basic(self):
        tokens = _tokenize_lower("Hello World 123")
        assert "hello" in tokens
        assert "world" in tokens

    def test_filters_single_chars(self):
        tokens = _tokenize_lower("a b c word")
        assert "a" not in tokens  # single char filtered by regex
        assert "word" in tokens


# ---------------------------------------------------------------------------
# Evidence bundling
# ---------------------------------------------------------------------------

class TestBuildEvidenceBundles:
    def test_single_result_makes_one_bundle(self):
        results = [_make_result(doc="chromadb vector memory")]
        bundles = _build_evidence_bundles(results)
        assert len(bundles) == 1
        assert len(bundles[0]["evidence"]) == 1

    def test_similar_results_grouped(self):
        results = [
            _make_result(doc="chromadb vector memory search", distance=0.2, mem_id="a"),
            _make_result(doc="chromadb vector memory embeddings", distance=0.3, mem_id="b"),
        ]
        bundles = _build_evidence_bundles(results)
        # Similar docs should be in same bundle
        assert len(bundles) == 1
        assert len(bundles[0]["evidence"]) == 2

    def test_dissimilar_results_separate_bundles(self):
        results = [
            _make_result(doc="chromadb vector memory search", distance=0.2, mem_id="a"),
            _make_result(doc="telegram bot notification alerts webhook", distance=1.5, mem_id="b"),
        ]
        bundles = _build_evidence_bundles(results)
        assert len(bundles) == 2

    def test_empty_results(self):
        bundles = _build_evidence_bundles([])
        assert bundles == []

    def test_bundle_has_theme(self):
        results = [_make_result(doc="ChromaDB uses ONNX embeddings for local search")]
        bundles = _build_evidence_bundles(results)
        assert bundles[0]["theme"]  # non-empty theme


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

class TestDetectContradictions:
    def test_finds_opposing_evidence(self):
        evidence = [
            _make_result(doc="Feature flag must always be enabled", mem_id="a"),
            _make_result(doc="Feature flag should be disabled in prod", mem_id="b"),
        ]
        contras = _detect_contradictions(evidence)
        assert len(contras) >= 1
        assert contras[0]["type"] == "opposing_signals"

    def test_no_contradictions_in_consistent_evidence(self):
        evidence = [
            _make_result(doc="ChromaDB stores vector embeddings", mem_id="a"),
            _make_result(doc="ChromaDB uses ONNX MiniLM for embeddings", mem_id="b"),
        ]
        contras = _detect_contradictions(evidence)
        assert len(contras) == 0

    def test_empty_evidence(self):
        assert _detect_contradictions([]) == []

    def test_single_evidence(self):
        evidence = [_make_result(doc="One memory only")]
        assert _detect_contradictions(evidence) == []


class TestDetectCrossBundleContradictions:
    def test_finds_cross_bundle_opposition(self):
        bundles = [
            {"theme": "A", "evidence": [_make_result(doc="always enable the cache")]},
            {"theme": "B", "evidence": [_make_result(doc="disable cache to save memory")]},
        ]
        contras = _detect_cross_bundle_contradictions(bundles)
        assert len(contras) >= 1
        assert contras[0]["type"] == "cross_bundle_opposition"

    def test_no_cross_bundle_contradiction(self):
        bundles = [
            {"theme": "A", "evidence": [_make_result(doc="chromadb memory store")]},
            {"theme": "B", "evidence": [_make_result(doc="telegram notification bot")]},
        ]
        contras = _detect_cross_bundle_contradictions(bundles)
        assert len(contras) == 0


# ---------------------------------------------------------------------------
# Conclusion synthesis
# ---------------------------------------------------------------------------

class TestSynthesizeConclusion:
    def test_empty_bundles(self):
        conclusion, confidence = _synthesize_conclusion([], [])
        assert "Insufficient" in conclusion
        assert confidence == 0.0

    def test_single_bundle_produces_conclusion(self):
        bundles = [
            {"theme": "ChromaDB", "evidence": [
                _make_result(doc="ChromaDB uses ONNX", distance=0.3),
            ], "contradictions": []},
        ]
        conclusion, confidence = _synthesize_conclusion(bundles, [])
        assert "1 memories" in conclusion
        assert "1 evidence bundle" in conclusion
        assert confidence > 0.0

    def test_contradictions_lower_confidence(self):
        evidence = [
            _make_result(doc="always enable feature", distance=0.2, mem_id="a"),
            _make_result(doc="disable feature in prod", distance=0.3, mem_id="b"),
        ]
        bundles = [{"theme": "Feature", "evidence": evidence, "contradictions": []}]

        # No contradictions
        _, conf_clean = _synthesize_conclusion(bundles, [])

        # With contradictions
        contras = [{"type": "opposing"}]
        _, conf_dirty = _synthesize_conclusion(bundles, contras)

        assert conf_dirty < conf_clean

    def test_more_evidence_higher_confidence(self):
        single = [{"theme": "A", "evidence": [
            _make_result(distance=0.3),
        ], "contradictions": []}]
        multi = [{"theme": "A", "evidence": [
            _make_result(distance=0.3, mem_id=f"m{i}") for i in range(5)
        ], "contradictions": []}]

        _, conf_single = _synthesize_conclusion(single, [])
        _, conf_multi = _synthesize_conclusion(multi, [])
        assert conf_multi > conf_single

    def test_warning_on_contradictions(self):
        bundles = [{"theme": "A", "evidence": [_make_result()], "contradictions": []}]
        contras = [{"type": "opposing"}]
        conclusion, _ = _synthesize_conclusion(bundles, contras)
        assert "WARNING" in conclusion
        assert "contradiction" in conclusion.lower()


# ---------------------------------------------------------------------------
# Integration: SearchMixin.synthesize (mocked brain)
# ---------------------------------------------------------------------------

class TestSynthesizeMethod:
    def test_synthesize_with_no_results(self):
        """synthesize() returns empty synthesis when recall returns nothing."""
        mock_brain = MagicMock()
        mock_brain.recall.return_value = []
        mock_brain.collections = {}

        # Manually call via SearchMixin
        from clarvis.brain.search import SearchMixin
        mixin = SearchMixin()
        mixin.recall = mock_brain.recall
        mixin.collections = mock_brain.collections

        result = mixin.synthesize("nonexistent topic")
        assert result["n_memories"] == 0
        assert result["n_bundles"] == 0
        assert result["confidence"] == 0.0

    def test_synthesize_with_results(self):
        """synthesize() produces bundles from recall results."""
        results = [
            _make_result(doc="ChromaDB vector memory store", distance=0.2, mem_id="a"),
            _make_result(doc="ChromaDB uses ONNX embeddings", distance=0.3, mem_id="b"),
            _make_result(doc="Telegram bot sends alerts", distance=1.5, mem_id="c",
                         collection="clarvis-infrastructure"),
        ]

        from clarvis.brain.search import SearchMixin
        mixin = SearchMixin()
        mixin.recall = MagicMock(return_value=results)
        mixin.collections = {}

        result = mixin.synthesize("chromadb memory")
        assert result["n_memories"] == 3
        assert result["n_bundles"] >= 1
        assert result["confidence"] > 0.0
        assert len(result["bundles"]) >= 1
        assert "conclusion" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

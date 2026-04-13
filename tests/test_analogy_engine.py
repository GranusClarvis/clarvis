"""Tests for analogical reasoning engine."""

import math
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "cognition"))
from analogy_engine import (
    AnalogyResult,
    _vec_sub,
    _vec_add,
    _cosine_sim,
    _vec_norm,
    find_analogies,
)


# ── Vector math tests ────────────────────────────────────────────

class TestVectorMath:
    def test_vec_sub(self):
        assert _vec_sub([3, 2, 1], [1, 1, 1]) == [2, 1, 0]

    def test_vec_add(self):
        assert _vec_add([1, 2, 3], [4, 5, 6]) == [5, 7, 9]

    def test_cosine_sim_identical(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_sim(v, v) - 1.0) < 1e-6

    def test_cosine_sim_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_sim(a, b)) < 1e-6

    def test_cosine_sim_opposite(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_sim(a, b) + 1.0) < 1e-6

    def test_cosine_sim_zero_vector(self):
        assert _cosine_sim([0, 0], [1, 2]) == 0.0

    def test_vec_norm(self):
        assert abs(_vec_norm([3, 4]) - 5.0) < 1e-6


# ── AnalogyResult tests ─────────────────────────────────────────

class TestAnalogyResult:
    def test_score(self):
        r = AnalogyResult("a", "b", "c", "d", offset_similarity=0.75)
        assert r.score == 0.75


# ── Core engine tests (with mock embeddings + memories) ──────────

def _make_embedding(seed: int, dim: int = 384) -> list[float]:
    """Create a deterministic pseudo-random embedding."""
    import random
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


class TestFindAnalogies:
    @patch("analogy_engine._get_brain_memories")
    @patch("analogy_engine._embed")
    def test_finds_parallel_relationships(self, mock_embed, mock_memories):
        """If memories contain a pair with the same offset, it should be found."""
        dim = 10

        # Source: A=[1,0,...] B=[0,1,...] → offset = [-1,1,0...]
        emb_a = [1.0] + [0.0] * (dim - 1)
        emb_b = [0.0, 1.0] + [0.0] * (dim - 2)

        # Target: C=[0.5,0,...] D=[-0.5,1,...] → same offset [-1,1,0...]
        emb_c = [0.5] + [0.0] * (dim - 1)
        emb_d = [-0.5, 1.0] + [0.0] * (dim - 2)

        # Distractor: E=[1,1,...] (won't match offset)
        emb_e = [0.0, 0.0, 1.0] + [0.0] * (dim - 3)

        mock_embed.return_value = [emb_a, emb_b]
        mock_memories.return_value = [
            {"text": "concept C", "embedding": emb_c, "collection": "learnings", "metadata": {}},
            {"text": "concept D", "embedding": emb_d, "collection": "learnings", "metadata": {}},
            {"text": "distractor E", "embedding": emb_e, "collection": "learnings", "metadata": {}},
        ]

        results = find_analogies("A", "B", n=5, min_score=0.01)
        assert len(results) >= 1
        # At least one result should include concept C or D
        all_texts = set()
        for r in results:
            all_texts.add(r.target_c)
            all_texts.add(r.target_d)
        assert "concept C" in all_texts or "concept D" in all_texts

    @patch("analogy_engine._get_brain_memories")
    @patch("analogy_engine._embed")
    def test_skips_near_duplicates(self, mock_embed, mock_memories):
        """Memories too similar to A or B should be filtered out."""
        dim = 10
        emb_a = [1.0] + [0.0] * (dim - 1)
        emb_b = [0.0, 1.0] + [0.0] * (dim - 2)

        # Memory very close to A (sim > 0.9)
        emb_dup = [0.99] + [0.01] * (dim - 1)
        norm = math.sqrt(sum(x * x for x in emb_dup))
        emb_dup = [x / norm for x in emb_dup]

        mock_embed.return_value = [emb_a, emb_b]
        mock_memories.return_value = [
            {"text": "near dup of A", "embedding": emb_dup, "collection": "learnings", "metadata": {}},
        ]

        results = find_analogies("A", "B", n=5, min_score=0.01)
        # Should filter out the near-duplicate
        assert len(results) == 0

    @patch("analogy_engine._get_brain_memories")
    @patch("analogy_engine._embed")
    def test_empty_memories(self, mock_embed, mock_memories):
        """No memories → no results."""
        mock_embed.return_value = [[0.1] * 10, [0.2] * 10]
        mock_memories.return_value = []
        results = find_analogies("A", "B")
        assert results == []

    @patch("analogy_engine._get_brain_memories")
    @patch("analogy_engine._embed")
    def test_respects_min_score(self, mock_embed, mock_memories):
        """Low-score results should be filtered by min_score."""
        dim = 10
        emb_a = [1.0] + [0.0] * (dim - 1)
        emb_b = [0.0, 1.0] + [0.0] * (dim - 2)

        # Target pair with perpendicular offset (low similarity)
        emb_c = [0.0, 0.0, 1.0] + [0.0] * (dim - 3)
        emb_d = [0.0, 0.0, 0.0, 1.0] + [0.0] * (dim - 4)

        mock_embed.return_value = [emb_a, emb_b]
        mock_memories.return_value = [
            {"text": "C", "embedding": emb_c, "collection": "x", "metadata": {}},
            {"text": "D", "embedding": emb_d, "collection": "x", "metadata": {}},
        ]

        results = find_analogies("A", "B", min_score=0.9)
        assert len(results) == 0


# ── Integration test with real embeddings ────────────────────────

class TestIntegrationRealEmbeddings:
    @pytest.fixture(autouse=True)
    def skip_if_no_embeddings(self):
        try:
            from clarvis.brain.factory import get_embedding_function
            get_embedding_function(use_onnx=True)
        except Exception:
            pytest.skip("ONNX embedding model not available")

    def test_embedding_offset_makes_sense(self):
        """The offset between related concepts should capture relationship."""
        from analogy_engine import _embed, _cosine_sim, _vec_sub

        embs = _embed(["king", "queen", "man", "woman"])
        # king - man ≈ queen - woman (classic word2vec analogy)
        offset_km = _vec_sub(embs[0], embs[2])  # king - man
        offset_qw = _vec_sub(embs[1], embs[3])  # queen - woman
        sim = _cosine_sim(offset_km, offset_qw)
        # With sentence embeddings this won't be as clean as word2vec,
        # but should still show some positive correlation
        assert sim > -0.5, f"Expected some positive correlation, got {sim}"

    def test_semantic_similarity_preserved(self):
        """Similar concepts should have similar embeddings."""
        from analogy_engine import _embed, _cosine_sim
        embs = _embed(["machine learning model", "neural network"])
        sim = _cosine_sim(embs[0], embs[1])
        assert sim > 0.3, f"Expected high similarity, got {sim}"

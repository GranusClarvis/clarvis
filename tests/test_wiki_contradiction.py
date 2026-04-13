"""Tests for wiki contradiction detector."""

import math
import pytest
from unittest.mock import patch
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "wiki"))
from wiki_contradiction import (
    WikiPage,
    Contradiction,
    _extract_claims,
    _extract_body_claims,
    _negation_score,
    _cosine_similarity,
    _tokenize,
    find_tag_pairs,
    detect_contradictions,
    format_report,
    load_wiki_pages,
)


# ── Claim extraction tests ───────────────────────────────────────

class TestExtractClaims:
    def test_extracts_real_claims(self):
        content = """---
title: Test
---
# Test

## Key Claims

- Neural networks can approximate any function given sufficient capacity
- Gradient descent converges to local minima in non-convex landscapes

## Evidence
"""
        claims = _extract_claims(content)
        assert len(claims) == 2
        assert "Neural networks" in claims[0]
        assert "Gradient descent" in claims[1]

    def test_skips_placeholder_claims(self):
        content = """## Key Claims

- _Claims pending extraction from full paper text._

## Evidence
"""
        claims = _extract_claims(content)
        assert len(claims) == 0

    def test_strips_citations(self):
        content = """## Key Claims

- Attention is all you need [Source: Vaswani et al. 2017]

## Evidence
"""
        claims = _extract_claims(content)
        assert len(claims) == 1
        assert "[Source:" not in claims[0]

    def test_skips_short_claims(self):
        content = """## Key Claims

- Too short
- This is a sufficiently long claim about something

## Evidence
"""
        claims = _extract_claims(content)
        assert len(claims) == 1

    def test_empty_content(self):
        assert _extract_claims("") == []
        assert _extract_claims("No key claims section here") == []


class TestExtractBodyClaims:
    def test_extracts_bold_claims(self):
        content = """# Title

**Conservative**: Rich internal models reconstruct the world so thoroughly the agent works offline
**Radical**: Fast frugal action-oriented solutions mean the world is its own best model

## Evidence

- Some evidence here
"""
        claims = _extract_body_claims(content)
        # Body claims only extract "- **...**:" prefixed items
        assert len(claims) == 0  # These aren't bullet-prefixed

    def test_extracts_bullet_bold_claims(self):
        content = """# Title

- **Conservative**: Rich internal models reconstruct the world so thoroughly the agent works offline
- **Radical**: Fast frugal action-oriented solutions mean the world is its own best model

## Evidence
"""
        claims = _extract_body_claims(content)
        assert len(claims) == 2

    def test_skips_excluded_sections(self):
        content = """## Open Questions

- **Question**: What is the meaning of this very important question about life?

## Update History

- **Update**: Something changed significantly in the latest version release
"""
        claims = _extract_body_claims(content)
        assert len(claims) == 0


# ── Negation / opposition tests ──────────────────────────────────

class TestNegationScore:
    def test_negation_asymmetry(self):
        score, evidence = _negation_score(
            "Models can generalize to unseen data",
            "Models cannot generalize to unseen data"
        )
        assert score >= 0.4
        assert any("negation" in e for e in evidence)

    def test_opposition_pairs(self):
        score, evidence = _negation_score(
            "This approach increases performance significantly",
            "This approach decreases performance significantly"
        )
        assert score >= 0.3
        assert any("opposition" in e for e in evidence)

    def test_no_opposition(self):
        score, evidence = _negation_score(
            "The sky is blue today",
            "Water flows downhill naturally"
        )
        assert score == 0.0
        assert evidence == []

    def test_hedging_markers(self):
        score, evidence = _negation_score(
            "The method works well however it has limitations",
            "The method works well in all cases"
        )
        assert score > 0.0
        assert any("hedging" in e for e in evidence)


# ── Cosine similarity tests ──────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


# ── Tag pair grouping tests ──────────────────────────────────────

class TestFindTagPairs:
    def test_groups_by_shared_tag(self):
        pages = [
            WikiPage("a", "Page A", Path("/a.md"), ["ai/llm", "memory"], []),
            WikiPage("b", "Page B", Path("/b.md"), ["ai/llm"], []),
            WikiPage("c", "Page C", Path("/c.md"), ["infra"], []),
        ]
        groups = find_tag_pairs(pages)
        assert "ai/llm" in groups
        assert len(groups["ai/llm"]) == 2
        assert "infra" not in groups  # Only 1 page
        assert "memory" not in groups  # Only 1 page

    def test_empty_pages(self):
        assert find_tag_pairs([]) == {}

    def test_no_shared_tags(self):
        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm"], []),
            WikiPage("b", "B", Path("/b.md"), ["infra/ops"], []),
        ]
        assert find_tag_pairs(pages) == {}


# ── Full detection tests (with mock embeddings) ─────────────────

def _mock_embeddings(texts):
    """Return deterministic embeddings for testing.

    Similar texts get similar vectors; texts with 'not' get flipped vectors.
    """
    vectors = []
    for text in texts:
        base = [0.0] * 384
        tokens = set(text.lower().split())
        # Hash tokens to deterministic positions
        for token in tokens:
            h = hash(token) % 384
            base[h] += 0.1
        # Normalize
        norm = math.sqrt(sum(x * x for x in base)) or 1.0
        vectors.append([x / norm for x in base])
    return vectors


class TestDetectContradictions:
    @patch("wiki_contradiction._get_embeddings", side_effect=_mock_embeddings)
    def test_no_contradictions_different_topics(self, mock_emb):
        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm"],
                     ["Python is a programming language"]),
            WikiPage("b", "B", Path("/b.md"), ["ai/llm"],
                     ["The weather today is sunny and warm"]),
        ]
        result = detect_contradictions(pages, similarity_threshold=0.8)
        assert len(result) == 0

    @patch("wiki_contradiction._get_embeddings", side_effect=_mock_embeddings)
    def test_no_claims(self, mock_emb):
        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm"], []),
            WikiPage("b", "B", Path("/b.md"), ["ai/llm"], []),
        ]
        result = detect_contradictions(pages)
        assert len(result) == 0

    @patch("wiki_contradiction._get_embeddings", side_effect=_mock_embeddings)
    def test_no_shared_tags(self, mock_emb):
        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm"],
                     ["Models can generalize"]),
            WikiPage("b", "B", Path("/b.md"), ["infra/ops"],
                     ["Models cannot generalize"]),
        ]
        result = detect_contradictions(pages)
        assert len(result) == 0  # No shared tags

    @patch("wiki_contradiction._get_embeddings")
    def test_detects_contradiction_with_high_sim_and_negation(self, mock_emb):
        """When embeddings are nearly identical but one has negation → contradiction."""
        # Return nearly identical embeddings
        base = [0.1] * 384
        norm = math.sqrt(sum(x * x for x in base))
        normalized = [x / norm for x in base]
        mock_emb.return_value = [normalized, normalized]  # identical

        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm"],
                     ["Transformers can process sequences efficiently"]),
            WikiPage("b", "B", Path("/b.md"), ["ai/llm"],
                     ["Transformers cannot process sequences efficiently"]),
        ]
        result = detect_contradictions(pages, similarity_threshold=0.5, min_opposition=0.1)
        assert len(result) == 1
        c = result[0]
        assert c.page_a_slug == "a"
        assert c.page_b_slug == "b"
        assert c.similarity >= 0.99
        assert c.opposition_score >= 0.4
        assert "ai/llm" in c.shared_tags
        assert c.confidence > 0

    @patch("wiki_contradiction._get_embeddings")
    def test_detects_opposition_pairs(self, mock_emb):
        """Opposition word pairs (increase/decrease) should be flagged."""
        base = [0.1] * 384
        norm = math.sqrt(sum(x * x for x in base))
        normalized = [x / norm for x in base]
        mock_emb.return_value = [normalized, normalized]

        pages = [
            WikiPage("a", "A", Path("/a.md"), ["research/paper"],
                     ["Attention increases model performance"]),
            WikiPage("b", "B", Path("/b.md"), ["research/paper"],
                     ["Attention decreases model performance"]),
        ]
        result = detect_contradictions(pages, similarity_threshold=0.5, min_opposition=0.1)
        assert len(result) == 1
        assert any("opposition" in e for e in result[0].evidence)

    @patch("wiki_contradiction._get_embeddings")
    def test_deduplicates_pairs(self, mock_emb):
        """Same pair shouldn't appear twice even if pages share multiple tags."""
        base = [0.1] * 384
        norm = math.sqrt(sum(x * x for x in base))
        normalized = [x / norm for x in base]
        mock_emb.return_value = [normalized, normalized]

        pages = [
            WikiPage("a", "A", Path("/a.md"), ["ai/llm", "research/paper"],
                     ["Models are not scalable"]),
            WikiPage("b", "B", Path("/b.md"), ["ai/llm", "research/paper"],
                     ["Models are scalable"]),
        ]
        result = detect_contradictions(pages, similarity_threshold=0.5, min_opposition=0.1)
        assert len(result) == 1  # Deduplicated


# ── Contradiction confidence tests ───────────────────────────────

class TestContradictionConfidence:
    def test_confidence_calculation(self):
        c = Contradiction(
            page_a_slug="a", page_a_title="A", claim_a="x",
            page_b_slug="b", page_b_title="B", claim_b="y",
            similarity=0.9, opposition_score=0.8,
            shared_tags=["ai/llm"],
        )
        expected = min(1.0, 0.9 * (0.5 + 0.5 * 0.8))
        assert abs(c.confidence - expected) < 1e-6

    def test_confidence_capped_at_1(self):
        c = Contradiction(
            page_a_slug="a", page_a_title="A", claim_a="x",
            page_b_slug="b", page_b_title="B", claim_b="y",
            similarity=1.0, opposition_score=1.0,
            shared_tags=["ai/llm"],
        )
        assert c.confidence <= 1.0


# ── Report formatting tests ──────────────────────────────────────

class TestFormatReport:
    def test_empty_report(self):
        pages = [WikiPage("a", "A", Path("/a.md"), [], [])]
        report = format_report([], pages)
        assert "Pages scanned: 1" in report
        assert "Contradictions found: 0" in report

    def test_report_with_contradictions(self):
        pages = [WikiPage("a", "A", Path("/a.md"), ["ai"], ["claim"])]
        contras = [Contradiction(
            page_a_slug="a", page_a_title="Page A", claim_a="X is true",
            page_b_slug="b", page_b_title="Page B", claim_b="X is not true",
            similarity=0.95, opposition_score=0.7,
            shared_tags=["ai"],
            evidence=["negation in B: not"],
        )]
        report = format_report(contras, pages)
        assert "Contradiction #1" in report
        assert "Page A" in report
        assert "Page B" in report
        assert "X is true" in report


# ── Integration test with real embeddings ────────────────────────

class TestIntegrationRealEmbeddings:
    """Integration tests using the actual ONNX embedding model."""

    @pytest.fixture(autouse=True)
    def skip_if_no_embeddings(self):
        try:
            from clarvis.brain.factory import get_embedding_function
            get_embedding_function(use_onnx=True)
        except Exception:
            pytest.skip("ONNX embedding model not available")

    def test_similar_claims_high_similarity(self):
        """Semantically similar claims should have high cosine similarity."""
        from wiki_contradiction import _get_embeddings, _cosine_similarity
        embs = _get_embeddings([
            "Deep learning models require large amounts of training data",
            "Neural networks need massive datasets for training",
        ])
        sim = _cosine_similarity(embs[0], embs[1])
        assert sim > 0.6, f"Expected high similarity, got {sim}"

    def test_different_claims_low_similarity(self):
        """Unrelated claims should have low cosine similarity."""
        from wiki_contradiction import _get_embeddings, _cosine_similarity
        embs = _get_embeddings([
            "Deep learning models require large amounts of training data",
            "The French Revolution began in 1789",
        ])
        sim = _cosine_similarity(embs[0], embs[1])
        assert sim < 0.4, f"Expected low similarity, got {sim}"

    def test_negated_claims_still_similar(self):
        """Negated claims should still have high embedding similarity."""
        from wiki_contradiction import _get_embeddings, _cosine_similarity
        embs = _get_embeddings([
            "Transformers can process long sequences efficiently",
            "Transformers cannot process long sequences efficiently",
        ])
        sim = _cosine_similarity(embs[0], embs[1])
        # Negated sentences are still semantically similar in embedding space
        assert sim > 0.7, f"Expected high similarity for negated pair, got {sim}"

    def test_full_pipeline_synthetic(self):
        """End-to-end: synthetic pages with contradictory claims should be detected."""
        pages = [
            WikiPage("page-a", "Page A", Path("/a.md"), ["ai/llm"], [
                "Attention mechanisms are essential for model performance",
                "Larger models consistently outperform smaller ones",
            ]),
            WikiPage("page-b", "Page B", Path("/b.md"), ["ai/llm"], [
                "Attention mechanisms are not necessary for good model performance",
                "Smaller models can match the performance of larger models",
            ]),
        ]
        result = detect_contradictions(pages, similarity_threshold=0.6, min_opposition=0.1)
        # Should find at least one contradiction
        assert len(result) >= 1, f"Expected contradictions, found {len(result)}"
        # The most confident should involve the attention claim pair
        top = result[0]
        assert top.opposition_score > 0
        assert "ai/llm" in top.shared_tags

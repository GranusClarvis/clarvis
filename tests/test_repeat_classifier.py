#!/usr/bin/env python3
"""
Tests for repeat_classifier.py — smart repeat detection.

Test philosophy: FALSE POSITIVE MINIMIZATION.
Every test case documents a real scenario where naive dedup would wrongly
block a legitimate research topic. The test suite is designed so that if
any scope-shift case is accidentally classified as REPEAT, the test fails.
"""

import json
import os
import sys
import tempfile
import pytest

# Make scripts/evolution importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "evolution"))

from repeat_classifier import (
    RepeatClassifier,
    Scope,
    extract_scope,
    canonical_topic_id,
    NOVEL,
    SCOPE_SHIFT,
    REPEAT,
    SHALLOW_PRIOR,
)
from research_novelty import TopicRegistry, TopicEntry, _word_overlap, _normalize


# --- Fixtures ---

@pytest.fixture
def tmp_registry(tmp_path):
    """Create a TopicRegistry backed by a temp file with sample topics."""
    reg_path = str(tmp_path / "registry.json")
    registry_data = {
        "iit 4.0": {
            "canonical_name": "iit 4.0",
            "aliases": ["iit llm representations", "integrated information theory"],
            "source_files": ["2026-03-09-iit-4.0.md"],
            "first_seen": "2026-03-09T10:00:00Z",
            "last_researched": "2026-04-01T10:00:00Z",  # 4 days ago
            "research_count": 2,
            "memory_count": 5,
            "last_novelty": "",
        },
        "retrieval optimization": {
            "canonical_name": "retrieval optimization",
            "aliases": ["arag hierarchical retrieval", "retrieval optimization"],
            "source_files": ["retrieval-optimization.md"],
            "first_seen": "2026-03-10T10:00:00Z",
            "last_researched": "2026-04-01T10:00:00Z",
            "research_count": 3,
            "memory_count": 12,
            "last_novelty": "",
        },
        "world models jepa dreamer": {
            "canonical_name": "world models jepa dreamer",
            "aliases": ["free energy world models"],
            "source_files": ["world-models.md"],
            "first_seen": "2026-03-08T10:00:00Z",
            "last_researched": "2026-03-01T10:00:00Z",  # >14 days ago (old)
            "research_count": 3,
            "memory_count": 18,
            "last_novelty": "",
        },
        "consciousness architectures": {
            "canonical_name": "consciousness architectures",
            "aliases": ["global workspace theory implementation"],
            "source_files": ["consciousness-arch.md"],
            "first_seen": "2026-03-15T10:00:00Z",
            "last_researched": "2026-04-02T10:00:00Z",
            "research_count": 1,
            "memory_count": 1,  # shallow
            "last_novelty": "",
        },
    }
    with open(reg_path, "w") as f:
        json.dump(registry_data, f)
    return TopicRegistry(path=reg_path)


@pytest.fixture
def classifier(tmp_registry):
    return RepeatClassifier(registry=tmp_registry)


# =============================================================================
# SCOPE EXTRACTION TESTS
# =============================================================================

class TestScopeExtraction:
    """Test that scope dimensions are correctly extracted from topic text."""

    def test_depth_intro(self):
        scope = extract_scope("Research: IIT basics and overview for beginners")
        assert scope.depth == "intro"

    def test_depth_survey(self):
        scope = extract_scope("Survey of consciousness measurement techniques 2025")
        assert scope.depth == "survey"

    def test_depth_deep_dive(self):
        scope = extract_scope("Deep dive into Phi computation methods")
        assert scope.depth == "focused"

    def test_depth_implementation(self):
        scope = extract_scope("Build a prototype consciousness monitor with IIT")
        assert scope.depth == "implementation"

    def test_depth_advanced(self):
        scope = extract_scope("Mathematical formalization of scalable Phi approximations")
        assert scope.depth == "advanced"

    def test_angle_theory(self):
        scope = extract_scope("Theoretical foundations of global workspace theory")
        assert scope.angle == "theory"

    def test_angle_practice(self):
        scope = extract_scope("Practical deployment of RAG pipelines in production")
        assert scope.angle == "practice"

    def test_angle_critique(self):
        scope = extract_scope("Critique of IIT limitations and weaknesses")
        assert scope.angle == "critique"

    def test_angle_comparison(self):
        scope = extract_scope("Benchmark comparison: IIT vs GWT vs attention schema")
        assert scope.angle == "comparison"

    def test_unknown_scope_for_vague_text(self):
        """Vague topic text should NOT produce false scope signals."""
        scope = extract_scope("Research: consciousness stuff")
        assert scope.is_fully_unknown() or scope.depth == "unknown"

    def test_scope_terms_populated(self):
        scope = extract_scope("Deep dive theoretical analysis of IIT")
        assert len(scope.scope_terms) > 0


# =============================================================================
# SCOPE COMPARISON TESTS
# =============================================================================

class TestScopeComparison:
    """Test that scope.differs_from() correctly identifies meaningful differences."""

    def test_different_depth(self):
        a = Scope(depth="intro", angle="theory")
        b = Scope(depth="advanced", angle="theory")
        assert a.differs_from(b)

    def test_different_angle(self):
        a = Scope(depth="survey", angle="theory")
        b = Scope(depth="survey", angle="critique")
        assert a.differs_from(b)

    def test_same_scope(self):
        a = Scope(depth="survey", angle="theory")
        b = Scope(depth="survey", angle="theory")
        assert not a.differs_from(b)

    def test_unknown_vs_unknown_no_diff(self):
        """Two unknown dimensions must NOT count as different.
        This is the key false-positive guard: vague topics should not
        get a free pass as 'scope shift' just because both are unknown."""
        a = Scope(depth="unknown", angle="unknown")
        b = Scope(depth="unknown", angle="unknown")
        assert not a.differs_from(b)

    def test_unknown_vs_known_weak_no_diff(self):
        """One unknown + one known WEAK signal on same dimension = no difference.
        We can't confirm they differ if one side has no signal and
        the other has a weak/generic signal."""
        a = Scope(depth="unknown", angle="theory")
        b = Scope(depth="survey", angle="theory")
        assert not a.differs_from(b)

    def test_unknown_vs_known_strong_signal_is_diff(self):
        """If new scope has a STRONG signal (critique, implementation, etc.)
        and prior is fully unknown, treat as scope shift."""
        new = Scope(depth="unknown", angle="critique")
        prior = Scope(depth="unknown", angle="unknown")
        assert new.differs_from(prior)

    def test_strong_signal_only_when_prior_fully_unknown(self):
        """Strong signal rule only fires when prior is FULLY unknown.
        If prior has any known dimension, fall back to normal rules."""
        new = Scope(depth="unknown", angle="critique")
        prior = Scope(depth="survey", angle="unknown")
        assert not new.differs_from(prior)  # prior not fully unknown

    def test_both_known_different(self):
        a = Scope(depth="intro", angle="theory", specificity="broad")
        b = Scope(depth="advanced", angle="practice", specificity="focused")
        assert a.differs_from(b)


# =============================================================================
# CANONICAL TOPIC ID TESTS
# =============================================================================

class TestCanonicalTopicId:
    """Test canonical ID generation."""

    def test_deterministic(self):
        """Same input always produces same ID."""
        assert canonical_topic_id("IIT 4.0") == canonical_topic_id("IIT 4.0")

    def test_normalization(self):
        """Minor formatting differences produce same ID."""
        id1 = canonical_topic_id("Research: IIT 4.0 overview")
        id2 = canonical_topic_id("research:  iit 4.0  overview")
        assert id1 == id2

    def test_different_topics_different_ids(self):
        id1 = canonical_topic_id("IIT 4.0")
        id2 = canonical_topic_id("retrieval optimization")
        assert id1 != id2

    def test_slug_format(self):
        tid = canonical_topic_id("World Models JEPA Dreamer")
        assert "-" in tid
        assert tid == tid.lower()
        # Should contain readable slug + hash suffix
        assert len(tid) > 8  # At least hash


# =============================================================================
# REPEAT CLASSIFIER — CORE VERDICT TESTS
# =============================================================================

class TestRepeatClassifier:
    """Test the full classify() pipeline."""

    def test_novel_topic(self, classifier):
        """Completely new topic → NOVEL."""
        result = classifier.classify("Research: quantum error correction for AI systems")
        assert result.verdict == NOVEL

    def test_exact_repeat_blocked(self, classifier):
        """Same topic, same scope, recent, well-covered → REPEAT."""
        result = classifier.classify("Research: retrieval optimization techniques")
        assert result.verdict == REPEAT
        assert result.canonical_name == "retrieval optimization"

    def test_manual_source_bypasses(self, classifier):
        """Manual sources always get NOVEL (explicit override)."""
        result = classifier.classify("Research: retrieval optimization", source="manual")
        assert result.verdict == NOVEL

    def test_cli_source_bypasses(self, classifier):
        result = classifier.classify("Research: retrieval optimization", source="cli")
        assert result.verdict == NOVEL

    def test_user_source_bypasses(self, classifier):
        result = classifier.classify("Research: retrieval optimization", source="user")
        assert result.verdict == NOVEL


# =============================================================================
# FALSE POSITIVE PREVENTION — The critical tests
# =============================================================================

class TestFalsePositivePrevention:
    """These tests ensure we NEVER suppress legitimate research angles.

    Each test represents a real scenario where naive word-overlap dedup
    would wrongly block a topic. If any of these fail, the classifier
    is too aggressive.
    """

    def test_same_topic_different_depth_allowed(self, classifier):
        """IIT survey vs IIT implementation = different depth → allow."""
        # "iit 4.0" is in registry (survey-ish), this is implementation
        result = classifier.classify(
            "Research: Build a prototype IIT consciousness monitor — implementation guide"
        )
        # Should NOT be REPEAT (either SCOPE_SHIFT or NOVEL)
        assert result.verdict != REPEAT, (
            f"False positive! Implementation angle of known topic was blocked. "
            f"Got: {result.verdict}, reason: {result.reason}"
        )

    def test_same_topic_different_angle_allowed(self, classifier):
        """IIT theory vs IIT critique = different angle → allow."""
        result = classifier.classify(
            "Research: Critique of IIT 4.0 — limitations, weaknesses, and counterarguments"
        )
        assert result.verdict != REPEAT, (
            f"False positive! Critique angle was blocked. "
            f"Got: {result.verdict}, reason: {result.reason}"
        )

    def test_old_topic_always_allowed(self, classifier):
        """Topic last researched >14 days ago → always allowed regardless of scope."""
        # "world models jepa dreamer" was last researched >14d ago
        result = classifier.classify("Research: World models and JEPA architectures")
        assert result.verdict != REPEAT, (
            f"False positive! Old topic was blocked. "
            f"Got: {result.verdict}, reason: {result.reason}"
        )

    def test_shallow_prior_always_allowed(self, classifier):
        """Topic with <3 memories → always allowed (prior was shallow)."""
        # "consciousness architectures" has only 1 memory
        result = classifier.classify("Research: Consciousness architectures for AI systems")
        assert result.verdict == SHALLOW_PRIOR

    def test_vague_topic_not_false_shifted(self, classifier):
        """Vague rewording of known topic should be REPEAT, not SCOPE_SHIFT.
        Both scopes unknown → differs_from returns False → no false scope shift."""
        # This is basically "retrieval optimization" rephrased without scope markers
        result = classifier.classify("Research: retrieval optimization methods and approaches")
        assert result.verdict == REPEAT, (
            f"Vague rewording should be REPEAT, not {result.verdict}. "
            "Unknown scopes should not trigger false scope shifts."
        )

    def test_completely_different_topic_not_matched(self, classifier):
        """Topics with no word overlap should be NOVEL, not matched to anything."""
        result = classifier.classify("Research: Rust async runtime performance profiling")
        assert result.verdict == NOVEL

    def test_partial_word_overlap_not_false_match(self, classifier):
        """Topics sharing a few words but being fundamentally different should be NOVEL."""
        # Shares "optimization" with "retrieval optimization" but different topic
        result = classifier.classify("Research: GPU memory optimization for LLM inference")
        # Should NOT match "retrieval optimization" just because of shared word
        assert result.verdict in (NOVEL, SCOPE_SHIFT), (
            f"Partial word overlap caused false match. Got: {result.verdict}"
        )


# =============================================================================
# IS_REPEAT CONVENIENCE METHOD
# =============================================================================

class TestIsRepeat:
    def test_repeat_returns_true(self, classifier):
        assert classifier.is_repeat("Research: retrieval optimization") is True

    def test_novel_returns_false(self, classifier):
        assert classifier.is_repeat("Research: quantum computing for NLP") is False

    def test_manual_returns_false(self, classifier):
        assert classifier.is_repeat("Research: retrieval optimization", source="manual") is False


# =============================================================================
# CLASSIFY RESULT METADATA
# =============================================================================

class TestClassifyResultMetadata:
    def test_result_has_topic_id(self, classifier):
        result = classifier.classify("Research: retrieval optimization")
        assert result.topic_id != ""
        assert len(result.topic_id) > 8

    def test_result_has_scopes(self, classifier):
        result = classifier.classify("Research: Deep dive into IIT theoretical foundations")
        assert result.new_scope is not None

    def test_result_has_match_score(self, classifier):
        result = classifier.classify("Research: retrieval optimization")
        assert result.match_score > 0.0

    def test_novel_result_has_no_canonical(self, classifier):
        result = classifier.classify("Research: completely new quantum topic XYZ")
        assert result.canonical_name == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

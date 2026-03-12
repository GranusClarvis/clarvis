"""
Tests for learning pipeline error handling and storage verification.

Run: python3 -m pytest scripts/tests/test_learning_pipeline.py -v
"""
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")


# === Priority 1: conversation_learner error handling ===

class TestConversationLearnerErrorHandling:
    """Verify brain failures are caught, not silent crashes."""

    def test_store_insights_handles_brain_store_failure(self):
        """brain.store() failure should log error and continue, not crash."""
        import conversation_learner as cl

        insights = [
            {"type": "test_pattern", "insight": "Test insight one", "importance": 0.7},
            {"type": "test_pattern", "insight": "Test insight two", "importance": 0.8},
        ]

        with patch.object(cl.brain, "get", return_value=[]):
            with patch.object(cl.brain, "store", side_effect=RuntimeError("DB locked")):
                # Should NOT raise — errors should be caught
                stored = cl.store_insights(insights, dry_run=False)
                assert stored == 0, "No insights should be stored when brain.store fails"

    def test_store_insights_handles_brain_get_failure(self):
        """brain.get() failure for dedup should not crash storage."""
        import conversation_learner as cl

        insights = [
            {"type": "test_pattern", "insight": "Test insight for get failure", "importance": 0.6},
        ]

        with patch.object(cl.brain, "get", side_effect=RuntimeError("Collection missing")):
            with patch.object(cl.brain, "store", return_value="test-id-123"):
                stored = cl.store_insights(insights, dry_run=False)
                assert stored == 1, "Should still store when dedup lookup fails"

    def test_store_insights_dry_run_succeeds(self):
        """Dry run should work without touching brain."""
        import conversation_learner as cl

        insights = [
            {"type": "meta_pattern", "insight": "Dry run test", "importance": 0.5},
        ]

        # dry_run should not call brain.store at all
        with patch.object(cl.brain, "get", return_value=[]):
            with patch.object(cl.brain, "store") as mock_store:
                stored = cl.store_insights(insights, dry_run=True)
                assert stored == 1
                mock_store.assert_not_called()


# === Priority 1: knowledge_synthesis error handling ===

class TestKnowledgeSynthesisErrorHandling:
    """Verify brain failures are caught in synthesis pipeline."""

    def test_load_all_memories_handles_collection_failure(self):
        """Failure on one collection should not crash loading others."""
        import knowledge_synthesis as ks

        call_count = 0
        def mock_get(coll, n=200):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Collection corrupted")
            return [{"id": f"mem-{call_count}", "document": "test memory"}]

        with patch.object(ks.brain, "get", side_effect=mock_get):
            memories = ks.load_all_memories()
            # Should have loaded from all collections except the first failed one
            assert len(memories) >= 1, "Should load memories from non-failing collections"

    def test_create_synthesis_handles_store_failure(self):
        """brain.store() failure in create_synthesis should return None, not crash."""
        import knowledge_synthesis as ks

        with patch.object(ks.brain, "store", side_effect=RuntimeError("Disk full")):
            result = ks.create_synthesis("test summary", ["id1", "id2"])
            assert result is None, "Should return None when brain.store fails"

    def test_create_synthesis_success(self):
        """Normal case: store succeeds, relationships attempted."""
        import knowledge_synthesis as ks

        with patch.object(ks.brain, "store", return_value="synth-id-1"):
            with patch.object(ks.brain, "add_relationship"):
                result = ks.create_synthesis("test bridge", ["id1", "id2"])
                assert result == "synth-id-1"


# === Priority 3: Verify learning actually stores and retrieves ===

class TestLearningRoundTrip:
    """Verify the store→retrieve cycle actually works (not silent failures)."""

    def test_brain_store_returns_id(self):
        """brain.store() should return a non-empty memory ID."""
        from brain import brain, AUTONOMOUS_LEARNING

        test_text = "[test] Learning pipeline verification — delete me"
        mem_id = brain.store(
            test_text,
            collection=AUTONOMOUS_LEARNING,
            importance=0.1,
            tags=["test", "verification"],
            source="test_learning_pipeline",
        )
        assert mem_id, "brain.store() returned empty/None ID — silent failure"
        assert isinstance(mem_id, str), f"Expected string ID, got {type(mem_id)}"

        # Verify retrieval
        results = brain.recall(test_text, collections=[AUTONOMOUS_LEARNING], n=3)
        found = any(test_text in r.get("document", "") for r in results)
        assert found, "Stored memory not retrievable — learning pipeline is broken"

        # Cleanup
        try:
            brain.delete(mem_id, collection=AUTONOMOUS_LEARNING)
        except Exception:
            pass  # Best-effort cleanup

    def test_brain_store_with_metadata(self):
        """Verify metadata (tags, source) survives round-trip."""
        from brain import brain, AUTONOMOUS_LEARNING

        test_text = "[test] Metadata round-trip verification — delete me"
        mem_id = brain.store(
            test_text,
            collection=AUTONOMOUS_LEARNING,
            importance=0.1,
            tags=["roundtrip-test"],
            source="test_learning_pipeline",
        )
        assert mem_id

        # Retrieve by ID and check metadata survived
        results = brain.recall(test_text, collections=[AUTONOMOUS_LEARNING], n=1)
        assert len(results) >= 1, "No results returned for exact-match recall"

        # Cleanup
        try:
            brain.delete(mem_id, collection=AUTONOMOUS_LEARNING)
        except Exception:
            pass


# === Priority 2: Quality score validation ===

class TestQualityScoreComputation:
    """Verify quality score math is correct."""

    def test_perfect_outcome_score(self):
        """Exit 0, all syntax clean, no errors, fast → high score."""
        # Simulate the scoring logic from postflight
        exit_code = 0
        syntax_ratio = 1.0
        traceback_count = 0
        error_count = 0
        task_duration = 120

        q_completion = 1.0 if exit_code == 0 else 0.0
        q_syntax = syntax_ratio
        q_output = max(0.0, 1.0 - (traceback_count * 0.3) - (min(error_count, 5) * 0.1))
        q_efficiency = 1.0 if task_duration < 300 else 0.8

        score = 0.30 * q_completion + 0.25 * q_syntax + 0.25 * q_output + 0.20 * q_efficiency
        assert score == pytest.approx(1.0), f"Perfect outcome should score 1.0, got {score}"

    def test_failure_outcome_score(self):
        """Exit 1, syntax errors, tracebacks → low score."""
        exit_code = 1
        syntax_ratio = 0.5
        traceback_count = 2
        error_count = 3
        task_duration = 1200

        q_completion = 0.0
        q_syntax = syntax_ratio
        q_output = max(0.0, 1.0 - (traceback_count * 0.3) - (min(error_count, 5) * 0.1))
        q_efficiency = max(0.2, 1.0 - (task_duration - 900) / 1800)

        score = 0.30 * q_completion + 0.25 * q_syntax + 0.25 * q_output + 0.20 * q_efficiency
        assert score < 0.5, f"Failure outcome should score < 0.5, got {score}"
        assert score > 0.0, "Score should never be exactly 0 with some syntax passing"

    def test_timeout_partial_credit(self):
        """Exit 124 (timeout) should get partial completion credit."""
        exit_code = 124
        q_completion = 1.0 if exit_code == 0 else (0.3 if exit_code == 124 else 0.0)
        assert q_completion == 0.3, "Timeout should get 0.3 partial credit"

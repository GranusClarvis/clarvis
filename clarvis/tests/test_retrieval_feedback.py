"""Tests for clarvis.brain.retrieval_feedback — RL-lite retrieval quality feedback."""

import json
import pytest
from pathlib import Path

from clarvis.brain.retrieval_feedback import (
    RetrievalFeedback,
    REWARD_MAP,
    EMA_ALPHA,
    SUGGESTION_INTERVAL,
    MIN_EPISODES_FOR_SUGGESTION,
    _default_params,
)


@pytest.fixture
def tmp_feedback(tmp_path):
    """Create a RetrievalFeedback instance using a temp directory."""
    return RetrievalFeedback(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# Reward computation
# ---------------------------------------------------------------------------

class TestComputeReward:
    def test_correct_success_positive(self, tmp_feedback):
        assert tmp_feedback.compute_reward("CORRECT", "success") == 1.0

    def test_incorrect_success_negative(self, tmp_feedback):
        assert tmp_feedback.compute_reward("INCORRECT", "success") == -0.5

    def test_incorrect_failure_positive(self, tmp_feedback):
        """INCORRECT + failure = retrieval correctly identified bad context."""
        assert tmp_feedback.compute_reward("INCORRECT", "failure") == 0.2

    def test_skipped_is_neutral(self, tmp_feedback):
        assert tmp_feedback.compute_reward("SKIPPED", "success") == 0.0
        assert tmp_feedback.compute_reward("SKIPPED", "failure") == 0.0

    def test_unknown_combo_returns_zero(self, tmp_feedback):
        assert tmp_feedback.compute_reward("UNKNOWN_VERDICT", "success") == 0.0

    def test_all_map_entries_in_range(self):
        for key, reward in REWARD_MAP.items():
            assert -1.0 <= reward <= 1.0, f"{key} → {reward} out of range"


# ---------------------------------------------------------------------------
# Recording episodes
# ---------------------------------------------------------------------------

class TestRecord:
    def test_basic_record(self, tmp_feedback):
        result = tmp_feedback.record("CORRECT", "success", max_score=0.72)
        assert result["reward"] == 1.0
        assert result["verdict"] == "CORRECT"
        assert result["outcome"] == "success"
        assert result["total_episodes"] == 1

    def test_ema_updates(self, tmp_feedback):
        """EMA should converge toward 1.0 with repeated successes."""
        for _ in range(10):
            result = tmp_feedback.record("CORRECT", "success")
        # After 10 successes, EMA should be well above 0.5
        assert result["ema_success_rate"] > 0.8

    def test_ema_tracks_failures(self, tmp_feedback):
        """EMA should decrease with repeated failures."""
        for _ in range(10):
            result = tmp_feedback.record("CORRECT", "failure")
        assert result["ema_success_rate"] < 0.2

    def test_verdict_counts_increment(self, tmp_feedback):
        tmp_feedback.record("CORRECT", "success")
        tmp_feedback.record("CORRECT", "failure")
        tmp_feedback.record("INCORRECT", "failure")
        assert tmp_feedback.params["verdict_counts"]["CORRECT"] == 2
        assert tmp_feedback.params["verdict_counts"]["INCORRECT"] == 1

    def test_reward_history_appended(self, tmp_feedback):
        tmp_feedback.record("AMBIGUOUS", "success", max_score=0.42)
        history = tmp_feedback.params["reward_history"]
        assert len(history) == 1
        assert history[0]["verdict"] == "AMBIGUOUS"
        assert history[0]["max_score"] == 0.42

    def test_reward_history_capped_at_100(self, tmp_feedback):
        for i in range(120):
            tmp_feedback.record("CORRECT", "success")
        assert len(tmp_feedback.params["reward_history"]) <= 100

    def test_persists_to_disk(self, tmp_feedback):
        tmp_feedback.record("CORRECT", "success")
        assert tmp_feedback.params_file.exists()
        with open(tmp_feedback.params_file) as f:
            data = json.load(f)
        assert data["total_episodes"] == 1

    def test_defensive_unknown_verdict(self, tmp_feedback):
        """Recording an unknown verdict should not crash."""
        result = tmp_feedback.record("NEVER_SEEN", "success")
        assert result["reward"] == 0.0
        assert result["total_episodes"] == 1


# ---------------------------------------------------------------------------
# Persistence and loading
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_load_from_existing(self, tmp_path):
        fb1 = RetrievalFeedback(data_dir=tmp_path)
        fb1.record("CORRECT", "success")
        fb1.record("INCORRECT", "failure")

        # New instance should load persisted state
        fb2 = RetrievalFeedback(data_dir=tmp_path)
        assert fb2.params["total_episodes"] == 2
        assert fb2.params["verdict_counts"]["CORRECT"] == 1

    def test_corrupted_file_returns_defaults(self, tmp_path):
        params_file = tmp_path / "retrieval_params.json"
        params_file.write_text("NOT VALID JSON {{{")
        fb = RetrievalFeedback(data_dir=tmp_path)
        assert fb.params["total_episodes"] == 0

    def test_missing_keys_filled_from_defaults(self, tmp_path):
        params_file = tmp_path / "retrieval_params.json"
        params_file.write_text(json.dumps({"version": 1, "total_episodes": 5}))
        fb = RetrievalFeedback(data_dir=tmp_path)
        assert fb.params["total_episodes"] == 5
        assert "CORRECT" in fb.params["ema_success_rate"]


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

class TestSuggestions:
    def test_suggestions_generated_at_interval(self, tmp_feedback):
        """Suggestions should be generated after SUGGESTION_INTERVAL episodes."""
        generated = False
        for i in range(SUGGESTION_INTERVAL + 1):
            result = tmp_feedback.record("CORRECT", "success")
            if result["suggestions_generated"]:
                generated = True
        assert generated
        assert tmp_feedback.suggestions_file.exists()

    def test_suggestion_content_valid(self, tmp_feedback):
        # Record enough CORRECT episodes to trigger suggestion
        for _ in range(SUGGESTION_INTERVAL + 1):
            tmp_feedback.record("CORRECT", "success")
        with open(tmp_feedback.suggestions_file) as f:
            data = json.load(f)
        assert "suggestions" in data
        assert "note" in data
        assert "HUMAN REVIEW" in data["note"]
        assert isinstance(data["suggestions"], list)

    def test_low_correct_success_suggests_raise(self, tmp_path):
        """If CORRECT verdict has low success rate, suggest raising threshold."""
        fb = RetrievalFeedback(data_dir=tmp_path)
        # Artificially set counts high enough for suggestion
        fb.params["verdict_counts"]["CORRECT"] = MIN_EPISODES_FOR_SUGGESTION + 5
        fb.params["ema_success_rate"]["CORRECT"] = 0.45  # Below 0.6
        fb.params["total_episodes"] = SUGGESTION_INTERVAL
        fb.params["last_suggestion_at"] = 0
        result = fb._generate_suggestions()
        assert result is True
        with open(fb.suggestions_file) as f:
            data = json.load(f)
        param_suggestions = [s for s in data["suggestions"]
                             if s.get("parameter") == "CORRECT_THRESHOLD"]
        assert len(param_suggestions) == 1
        assert param_suggestions[0]["suggested"] == 0.60  # Raise it

    def test_high_correct_success_suggests_lower(self, tmp_path):
        fb = RetrievalFeedback(data_dir=tmp_path)
        fb.params["verdict_counts"]["CORRECT"] = MIN_EPISODES_FOR_SUGGESTION + 5
        fb.params["ema_success_rate"]["CORRECT"] = 0.90  # Above 0.85
        fb.params["total_episodes"] = SUGGESTION_INTERVAL
        fb.params["last_suggestion_at"] = 0
        result = fb._generate_suggestions()
        assert result is True
        with open(fb.suggestions_file) as f:
            data = json.load(f)
        param_suggestions = [s for s in data["suggestions"]
                             if s.get("parameter") == "CORRECT_THRESHOLD"]
        assert len(param_suggestions) == 1
        assert param_suggestions[0]["suggested"] == 0.50  # Lower it

    def test_no_suggestions_when_insufficient_data(self, tmp_path):
        fb = RetrievalFeedback(data_dir=tmp_path)
        fb.params["verdict_counts"]["CORRECT"] = 3  # Way below minimum
        fb.params["total_episodes"] = SUGGESTION_INTERVAL
        fb.params["last_suggestion_at"] = 0
        fb._generate_suggestions()
        with open(fb.suggestions_file) as f:
            data = json.load(f)
        # Should get "none" suggestion
        assert any(s.get("parameter") == "none" for s in data["suggestions"])


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, tmp_feedback):
        stats = tmp_feedback.get_stats()
        assert stats["total_episodes"] == 0
        assert stats["avg_recent_reward"] == 0.0

    def test_stats_after_records(self, tmp_feedback):
        tmp_feedback.record("CORRECT", "success")
        tmp_feedback.record("INCORRECT", "failure")
        stats = tmp_feedback.get_stats()
        assert stats["total_episodes"] == 2
        assert stats["avg_recent_reward"] != 0.0
        assert stats["verdict_counts"]["CORRECT"] == 1


# ---------------------------------------------------------------------------
# Default params structure
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_params_structure(self):
        params = _default_params()
        assert params["version"] == 1
        assert params["total_episodes"] == 0
        assert "CORRECT" in params["ema_success_rate"]
        assert "INCORRECT" in params["verdict_counts"]
        assert isinstance(params["reward_history"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

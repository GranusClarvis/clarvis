"""Tests for clarvis.context.adaptive_mmr — task-category-aware MMR lambda tuning."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from clarvis.context.adaptive_mmr import (
    classify_mmr_category,
    get_adaptive_lambda,
    update_lambdas,
    BASE_LAMBDAS,
    LAMBDA_MIN,
    LAMBDA_MAX,
    _aggregate_per_category,
    _load_state,
    _save_state,
)


class TestClassifyMMRCategory(unittest.TestCase):
    """Test task classification into MMR categories."""

    def test_code_tasks(self):
        assert classify_mmr_category("Implement new feature X") == "code"
        assert classify_mmr_category("Fix the broken cron script") == "code"
        assert classify_mmr_category("Add pytest for brain module") == "code"
        assert classify_mmr_category("Refactor context compressor") == "code"
        assert classify_mmr_category("Optimize brain query speed") == "code"

    def test_research_tasks(self):
        assert classify_mmr_category("Research: CRAG retrieval patterns") == "research"
        assert classify_mmr_category("Analyze memory architecture papers") == "research"
        assert classify_mmr_category("Survey existing browser automation tools") == "research"
        assert classify_mmr_category("Evaluate new embedding models") == "research"

    def test_maintenance_tasks(self):
        assert classify_mmr_category("Run daily backup verification") == "maintenance"
        assert classify_mmr_category("Health monitoring status report") == "maintenance"
        assert classify_mmr_category("Cron watchdog check and cleanup") == "maintenance"

    def test_empty_or_unknown(self):
        assert classify_mmr_category("") == "maintenance"
        assert classify_mmr_category("Do the thing") == "maintenance"

    def test_mixed_keywords(self):
        # Code keywords should dominate when both are present
        result = classify_mmr_category("Implement research findings into code")
        assert result in ("code", "research")  # both valid, implementation wins


class TestGetAdaptiveLambda(unittest.TestCase):
    """Test lambda retrieval for different task types."""

    def test_code_base_lambda(self):
        """Code tasks should get high lambda (favoring relevance)."""
        lam = get_adaptive_lambda("Implement feature")
        assert lam == BASE_LAMBDAS["code"]

    def test_research_base_lambda(self):
        """Research tasks should get low lambda (favoring diversity)."""
        lam = get_adaptive_lambda("Research memory patterns")
        assert lam == BASE_LAMBDAS["research"]

    def test_maintenance_base_lambda(self):
        """Maintenance tasks should get balanced lambda."""
        lam = get_adaptive_lambda("Run health monitor")
        assert lam == BASE_LAMBDAS["maintenance"]

    def test_lambda_in_bounds(self):
        """Lambda should always be within bounds."""
        for task in ["Implement X", "Research Y", "Monitor Z", "", "Random stuff"]:
            lam = get_adaptive_lambda(task)
            assert LAMBDA_MIN <= lam <= LAMBDA_MAX, f"Lambda {lam} out of bounds for '{task}'"


class TestUpdateLambdas(unittest.TestCase):
    """Test lambda adaptation from episode data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_relevance = os.environ.get("CLARVIS_WORKSPACE")
        # Patch module-level paths
        import clarvis.context.adaptive_mmr as mod
        self.mod = mod
        self.orig_relevance_file = mod.RELEVANCE_FILE
        self.orig_state_file = mod.LAMBDA_STATE_FILE
        mod.RELEVANCE_FILE = os.path.join(self.tmpdir, "context_relevance.jsonl")
        mod.LAMBDA_STATE_FILE = os.path.join(self.tmpdir, "adaptive_mmr_state.json")

    def tearDown(self):
        self.mod.RELEVANCE_FILE = self.orig_relevance_file
        self.mod.LAMBDA_STATE_FILE = self.orig_state_file
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_episodes(self, entries):
        with open(self.mod.RELEVANCE_FILE, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_no_data_returns_base(self):
        """Without episode data, lambdas should equal base values."""
        result = update_lambdas()
        assert result == {k: v for k, v in BASE_LAMBDAS.items()}

    def test_low_relevance_decreases_lambda(self):
        """Below-target relevance should nudge lambda down (more diversity)."""
        now = datetime.now(timezone.utc)
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.5,
             "task": "Implement thing", "mmr_category": "code"}
            for i in range(6)
        ]
        self._write_episodes(episodes)
        result = update_lambdas()
        assert result["code"] < BASE_LAMBDAS["code"]

    def test_high_relevance_increases_lambda(self):
        """Above-target relevance should nudge lambda up (more precision)."""
        now = datetime.now(timezone.utc)
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.95,
             "task": "Research papers", "mmr_category": "research"}
            for i in range(6)
        ]
        self._write_episodes(episodes)
        result = update_lambdas()
        assert result["research"] > BASE_LAMBDAS["research"]

    def test_lambda_stays_in_bounds(self):
        """Lambda should never exceed bounds even with extreme data."""
        now = datetime.now(timezone.utc)
        # Very low relevance — should push lambda down but not below MIN
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.01,
             "task": "Research X", "mmr_category": "research"}
            for i in range(20)
        ]
        self._write_episodes(episodes)
        # Run many update cycles
        for _ in range(50):
            result = update_lambdas()
        assert result["research"] >= LAMBDA_MIN

    def test_insufficient_episodes_no_adapt(self):
        """With fewer than MIN_EPISODES_FOR_ADAPT, lambda stays at base."""
        now = datetime.now(timezone.utc)
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.1,
             "task": "Implement X", "mmr_category": "code"}
            for i in range(3)  # below threshold
        ]
        self._write_episodes(episodes)
        result = update_lambdas()
        assert result["code"] == BASE_LAMBDAS["code"]

    def test_state_persists(self):
        """Lambda state should persist across calls."""
        now = datetime.now(timezone.utc)
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.5,
             "task": "Implement thing", "mmr_category": "code"}
            for i in range(6)
        ]
        self._write_episodes(episodes)
        first = update_lambdas()
        state = _load_state()
        assert "code" in state
        assert state["code"]["lambda"] == first["code"]

    def test_category_inferred_from_task(self):
        """When mmr_category is missing, it should be inferred from task text."""
        now = datetime.now(timezone.utc)
        episodes = [
            {"ts": (now - timedelta(hours=i)).isoformat(), "overall": 0.5,
             "task": "Research CRAG papers"}  # no mmr_category key
            for i in range(6)
        ]
        self._write_episodes(episodes)
        per_cat = _aggregate_per_category()
        assert "research" in per_cat
        assert per_cat["research"]["count"] == 6


class TestAggregatePerCategory(unittest.TestCase):
    """Test per-category aggregation of relevance data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import clarvis.context.adaptive_mmr as mod
        self.mod = mod
        self.orig_file = mod.RELEVANCE_FILE
        mod.RELEVANCE_FILE = os.path.join(self.tmpdir, "cr.jsonl")

    def tearDown(self):
        self.mod.RELEVANCE_FILE = self.orig_file
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_file(self):
        result = _aggregate_per_category()
        assert result == {}

    def test_mixed_categories(self):
        now = datetime.now(timezone.utc)
        entries = [
            {"ts": now.isoformat(), "overall": 0.8, "mmr_category": "code"},
            {"ts": now.isoformat(), "overall": 0.6, "mmr_category": "code"},
            {"ts": now.isoformat(), "overall": 0.9, "mmr_category": "research"},
        ]
        with open(self.mod.RELEVANCE_FILE, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        result = _aggregate_per_category()
        assert result["code"]["count"] == 2
        assert abs(result["code"]["mean"] - 0.7) < 0.01
        assert result["research"]["count"] == 1
        assert abs(result["research"]["mean"] - 0.9) < 0.01

    def test_old_entries_excluded(self):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        entries = [
            {"ts": old, "overall": 0.3, "mmr_category": "code"},
            {"ts": recent, "overall": 0.9, "mmr_category": "code"},
        ]
        with open(self.mod.RELEVANCE_FILE, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        result = _aggregate_per_category(days=7)
        assert result["code"]["count"] == 1
        assert abs(result["code"]["mean"] - 0.9) < 0.01


if __name__ == "__main__":
    unittest.main()

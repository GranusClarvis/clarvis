"""
Smoke tests for clarvis.learning.MetaLearner.

Ensures coverage_pct > 0 for the learning spine module by exercising
instantiation and the core analysis/advice methods with synthetic data.

Run: python3 -m pytest tests/test_clarvis_learning.py -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import clarvis.learning.meta_learning as ml
from clarvis.learning import MetaLearner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EPISODES = [
    {"task": "build new feature X", "outcome": "success", "duration_s": 180,
     "timestamp": "2026-04-01T10:00:00", "error": "", "section": "autonomous"},
    {"task": "fix broken import in brain.py", "outcome": "success", "duration_s": 60,
     "timestamp": "2026-04-02T11:00:00", "error": "", "section": "autonomous"},
    {"task": "research meta-learning papers", "outcome": "success", "duration_s": 300,
     "timestamp": "2026-04-03T09:00:00", "error": "", "section": "research"},
    {"task": "wire heartbeat to new module", "outcome": "failure", "duration_s": 500,
     "timestamp": "2026-04-04T14:00:00", "error": "ImportError: No module named 'foo'",
     "section": "autonomous"},
    {"task": "improve brain recall speed", "outcome": "success", "duration_s": 200,
     "timestamp": "2026-04-05T08:00:00", "error": "", "section": "autonomous"},
    {"task": "build dashboard view", "outcome": "failure", "duration_s": 900,
     "timestamp": "2026-04-06T10:00:00", "error": "timeout", "section": "autonomous"},
    {"task": "refactor cost tracker", "outcome": "success", "duration_s": 150,
     "timestamp": "2026-04-07T12:00:00", "error": "", "section": "autonomous"},
]

SAMPLE_CAPABILITY_HISTORY = {
    "snapshots": [
        {"date": "2026-04-01", "scores": {"coding": 0.6, "reasoning": 0.5, "memory": 0.7}},
        {"date": "2026-04-05", "scores": {"coding": 0.65, "reasoning": 0.55, "memory": 0.72}},
        {"date": "2026-04-10", "scores": {"coding": 0.7, "reasoning": 0.6, "memory": 0.73}},
    ]
}


@pytest.fixture
def learner(tmp_path, monkeypatch):
    """Create a MetaLearner with isolated data directory."""
    data_dir = tmp_path / "meta_learning"
    data_dir.mkdir()

    # Redirect all file paths to tmp
    monkeypatch.setattr(ml, "DATA_DIR", data_dir)
    monkeypatch.setattr(ml, "ANALYSIS_FILE", data_dir / "analysis.json")
    monkeypatch.setattr(ml, "HISTORY_FILE", data_dir / "history.jsonl")
    monkeypatch.setattr(ml, "RECOMMENDATIONS_FILE", data_dir / "recommendations.json")
    monkeypatch.setattr(ml, "INJECTION_HISTORY_FILE", data_dir / "injection_history.json")

    # Write synthetic episodes
    ep_file = tmp_path / "episodes.json"
    ep_file.write_text(json.dumps(SAMPLE_EPISODES))
    monkeypatch.setattr(ml, "EPISODES_FILE", ep_file)

    # Write synthetic capability history
    cap_file = tmp_path / "capability_history.json"
    cap_file.write_text(json.dumps(SAMPLE_CAPABILITY_HISTORY))
    monkeypatch.setattr(ml, "CAPABILITY_HISTORY_FILE", cap_file)

    # Point Hebbian log / autonomous log to non-existent (empty data is fine)
    monkeypatch.setattr(ml, "HEBBIAN_ACCESS_LOG", tmp_path / "no_hebbian.jsonl")
    monkeypatch.setattr(ml, "AUTONOMOUS_LOG", tmp_path / "no_autonomous.log")
    monkeypatch.setattr(ml, "REASONING_CHAINS_DIR", tmp_path / "no_chains")

    return MetaLearner()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMetaLearnerInstantiation:
    """MetaLearner should instantiate cleanly and load empty state."""

    def test_init_no_analysis_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ml, "ANALYSIS_FILE", tmp_path / "nonexistent.json")
        m = MetaLearner()
        assert m._analysis["last_run"] is None
        assert m._analysis["run_count"] == 0

    def test_init_with_existing_analysis(self, tmp_path, monkeypatch):
        af = tmp_path / "analysis.json"
        af.write_text(json.dumps({"last_run": "2026-04-01", "run_count": 5,
                                   "strategies": {}, "learning_speeds": {},
                                   "failure_clusters": {}, "retrieval_patterns": {},
                                   "recommendations": []}))
        monkeypatch.setattr(ml, "ANALYSIS_FILE", af)
        m = MetaLearner()
        assert m._analysis["run_count"] == 5

    def test_init_corrupted_json(self, tmp_path, monkeypatch):
        af = tmp_path / "bad.json"
        af.write_text("{corrupted")
        monkeypatch.setattr(ml, "ANALYSIS_FILE", af)
        m = MetaLearner()
        assert m._analysis["last_run"] is None


class TestStrategyEffectiveness:
    def test_returns_strategies(self, learner):
        strats = learner.analyze_strategy_effectiveness()
        assert isinstance(strats, dict)
        assert len(strats) > 0
        # "build" appears in our sample episodes
        assert "build" in strats
        assert 0 <= strats["build"]["success_rate"] <= 1

    def test_empty_episodes(self, learner, monkeypatch):
        monkeypatch.setattr(ml, "EPISODES_FILE", Path("/nonexistent"))
        result = learner.analyze_strategy_effectiveness()
        assert result == {}


class TestLearningSpeed:
    def test_returns_domains(self, learner):
        speeds = learner.analyze_learning_speed()
        assert isinstance(speeds, dict)
        # With our sample capability history, should have domains
        assert len(speeds) >= 1

    def test_insufficient_history(self, learner, monkeypatch):
        monkeypatch.setattr(ml, "CAPABILITY_HISTORY_FILE", Path("/nonexistent"))
        result = learner.analyze_learning_speed()
        assert result == {}


class TestFailurePatterns:
    def test_finds_failure_clusters(self, learner):
        patterns = learner.mine_failure_patterns()
        assert isinstance(patterns, dict)
        # We have an ImportError and a timeout in sample data
        assert "import_error" in patterns or "timeout" in patterns

    def test_no_failures(self, learner, monkeypatch):
        ep_file = ml.EPISODES_FILE.parent / "success_only.json"
        ep_file.write_text(json.dumps([
            {"task": "build X", "outcome": "success", "duration_s": 100,
             "timestamp": "2026-04-01", "error": ""}
        ]))
        monkeypatch.setattr(ml, "EPISODES_FILE", ep_file)
        result = learner.mine_failure_patterns()
        assert result == {}


class TestRecommendations:
    def test_generate_recommendations(self, learner):
        strats = learner.analyze_strategy_effectiveness()
        speeds = learner.analyze_learning_speed()
        failures = learner.mine_failure_patterns()
        retrieval = learner.analyze_retrieval_effectiveness()
        consolidation = learner.analyze_consolidation_timing()

        recs = learner.generate_recommendations(
            strats, speeds, failures, retrieval, consolidation
        )
        assert isinstance(recs, list)
        for rec in recs:
            assert "priority" in rec
            assert "category" in rec
            assert "action" in rec

    def test_empty_inputs(self, learner):
        recs = learner.generate_recommendations({}, {}, {}, {}, {})
        assert recs == []


class TestTaskAdvice:
    def test_advice_neutral_default(self, learner):
        advice = learner.get_task_advice("do something random")
        assert advice["strategy_score"] == 0.5
        assert isinstance(advice["warnings"], list)

    def test_advice_with_known_strategy(self, learner):
        # Pre-populate analysis with a strategy
        learner._analysis["strategies"] = {
            "build": {"success_rate": 0.3, "count": 5, "trend": -0.1}
        }
        advice = learner.get_task_advice("build a new dashboard widget")
        assert advice["strategy_score"] == 0.3
        assert len(advice["warnings"]) >= 1

    def test_advice_with_failure_pattern(self, learner):
        learner._analysis["failure_clusters"] = {
            "import_error": {
                "count": 5,
                "common_context": ["brain", "module"],
                "avoidance_hint": "Check imports first.",
            }
        }
        advice = learner.get_task_advice("fix brain module wiring")
        assert len(advice["warnings"]) >= 1


class TestGiniCoefficient:
    def test_equal_distribution(self):
        assert MetaLearner._gini_coefficient([1, 1, 1, 1]) == 0.0

    def test_empty(self):
        assert MetaLearner._gini_coefficient([]) == 0.0

    def test_single_value(self):
        assert MetaLearner._gini_coefficient([42]) == 0.0

    def test_unequal(self):
        g = MetaLearner._gini_coefficient([0, 0, 0, 10])
        assert 0.5 < g <= 1.0


class TestFullAnalyze:
    def test_analyze_runs_without_crash(self, learner):
        """Full analysis cycle with synthetic data — no brain storage."""
        with patch.object(ml.brain, "store", return_value="fake-id"):
            result = learner.analyze()

        assert "strategies" in result
        assert "learning_speeds" in result
        assert "failure_patterns" in result
        assert "recommendations" in result
        assert "summary" in result
        assert result["summary"]["strategy_count"] >= 1

    def test_analyze_persists_state(self, learner):
        with patch.object(ml.brain, "store", return_value="fake-id"):
            learner.analyze()

        assert ml.ANALYSIS_FILE.exists()
        data = json.loads(ml.ANALYSIS_FILE.read_text())
        assert data["run_count"] == 1


class TestGetMetaLearner:
    def test_singleton(self, monkeypatch):
        monkeypatch.setattr(ml, "_meta_learner", None)
        m1 = ml.get_meta_learner()
        m2 = ml.get_meta_learner()
        assert m1 is m2
        # Reset
        monkeypatch.setattr(ml, "_meta_learner", None)

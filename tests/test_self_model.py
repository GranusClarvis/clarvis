"""Tests for clarvis/metrics/self_model.py — covers core model I/O,
meta-cognition, assess_all_capabilities, and remediation logic."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Patch brain before importing self_model to avoid ChromaDB init
_mock_brain = MagicMock()
_mock_brain.stats.return_value = {"total_memories": 100, "graph_edges": 50, "collections": {"a": 10}}
_mock_brain.recall.return_value = [{"distance": 0.5, "document": "test"}]
_mock_brain.store.return_value = {"id": "test-id"}

with patch.dict("sys.modules", {"clarvis.brain": MagicMock(brain=_mock_brain)}):
    with patch("clarvis.metrics.self_model.brain", _mock_brain):
        from clarvis.metrics import self_model


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Redirect all data files to a temp directory."""
    data_file = str(tmp_path / "self_model.json")
    meta_file = str(tmp_path / "meta_cognition.json")
    history_file = str(tmp_path / "capability_history.json")
    with patch.object(self_model, "DATA_FILE", data_file), \
         patch.object(self_model, "META_FILE", meta_file), \
         patch.object(self_model, "CAPABILITY_HISTORY_FILE", history_file):
        yield tmp_path


# --- Model I/O ---

class TestModelIO:
    def test_load_model_default(self, tmp_data_dir):
        model = self_model.load_model()
        assert "capabilities" in model
        assert "strengths" in model
        assert model["last_updated"] is None

    def test_save_and_load_roundtrip(self, tmp_data_dir):
        model = {"capabilities": ["test"], "strengths": [], "weaknesses": [],
                 "trajectory": [], "last_updated": "2026-04-18"}
        self_model.save_model(model)
        loaded = self_model.load_model()
        assert loaded["capabilities"] == ["test"]
        assert loaded["last_updated"] == "2026-04-18"

    def test_load_meta_default(self, tmp_data_dir):
        meta = self_model.load_meta()
        assert meta["awareness_level"] == "operational"
        assert meta["cognitive_state"] == "active"
        assert meta["working_memory"] == []

    def test_save_and_load_meta_roundtrip(self, tmp_data_dir):
        meta = self_model.load_meta()
        meta["awareness_level"] = "reflective"
        self_model.save_meta(meta)
        loaded = self_model.load_meta()
        assert loaded["awareness_level"] == "reflective"


# --- Meta-Cognition ---

class TestMetaCognition:
    def test_think_about_thinking_appends(self, tmp_data_dir):
        self_model.think_about_thinking("Am I aware of my limitations?")
        meta = self_model.load_meta()
        assert len(meta["meta_thoughts"]) == 1
        assert "limitations" in meta["meta_thoughts"][0]["thought"]
        assert "timestamp" in meta["meta_thoughts"][0]

    def test_think_about_thinking_caps_at_20(self, tmp_data_dir):
        for i in range(25):
            self_model.think_about_thinking(f"Thought {i}")
        meta = self_model.load_meta()
        assert len(meta["meta_thoughts"]) == 20
        # Most recent should be thought 24
        assert "Thought 24" in meta["meta_thoughts"][-1]["thought"]

    def test_get_set_awareness_level(self, tmp_data_dir):
        assert self_model.get_awareness_level() == "operational"
        self_model.set_awareness_level("meta")
        assert self_model.get_awareness_level() == "meta"

    def test_set_awareness_level_rejects_invalid(self, tmp_data_dir):
        self_model.set_awareness_level("invalid_level")
        assert self_model.get_awareness_level() == "operational"

    def test_working_memory_lifecycle(self, tmp_data_dir):
        assert self_model.get_working_memory() == []
        self_model.set_working_memory("current task: tests")
        wm = self_model.get_working_memory()
        assert len(wm) == 1
        assert wm[0]["item"] == "current task: tests"
        self_model.clear_working_memory()
        assert self_model.get_working_memory() == []

    def test_working_memory_caps_at_5(self, tmp_data_dir):
        for i in range(8):
            self_model.set_working_memory(f"item {i}")
        wm = self_model.get_working_memory()
        assert len(wm) == 5
        assert wm[-1]["item"] == "item 7"

    def test_cognitive_state_lifecycle(self, tmp_data_dir):
        assert self_model.get_cognitive_state() == "active"
        self_model.set_cognitive_state("reflective")
        assert self_model.get_cognitive_state() == "reflective"

    def test_set_cognitive_state_rejects_invalid(self, tmp_data_dir):
        self_model.set_cognitive_state("dreaming")
        assert self_model.get_cognitive_state() == "active"


# --- CAPABILITY_DOMAINS ---

class TestCapabilityDomains:
    def test_all_7_domains_present(self):
        assert len(self_model.CAPABILITY_DOMAINS) == 7
        expected = {"memory_system", "autonomous_execution", "code_generation",
                    "self_reflection", "reasoning_chains", "learning_feedback",
                    "consciousness_metrics"}
        assert set(self_model.CAPABILITY_DOMAINS.keys()) == expected

    def test_each_domain_has_label_and_description(self):
        for name, info in self_model.CAPABILITY_DOMAINS.items():
            assert "label" in info, f"{name} missing label"
            assert "description" in info, f"{name} missing description"

    def test_assessors_match_domains(self):
        assert set(self_model.ASSESSORS.keys()) == set(self_model.CAPABILITY_DOMAINS.keys())


# --- assess_all_capabilities ---

class TestAssessAllCapabilities:
    def test_returns_all_7_domains(self, tmp_data_dir):
        with patch.object(self_model, "ASSESSORS", {
            k: lambda: (0.5, ["mock evidence"])
            for k in self_model.CAPABILITY_DOMAINS
        }):
            results = self_model.assess_all_capabilities()
        assert len(results) == 7
        for domain, data in results.items():
            assert "score" in data
            assert "evidence" in data
            assert "label" in data
            assert 0.0 <= data["score"] <= 1.0

    def test_scores_are_rounded(self, tmp_data_dir):
        with patch.object(self_model, "ASSESSORS", {
            k: lambda: (0.33333, ["test"])
            for k in self_model.CAPABILITY_DOMAINS
        }):
            results = self_model.assess_all_capabilities()
        for data in results.values():
            assert data["score"] == 0.33


# --- generate_remediation_tasks ---

class TestRemediation:
    def test_generates_task_below_threshold(self):
        scores = {
            "memory_system": {"score": 0.2, "evidence": [], "label": "Memory"},
        }
        tasks = self_model.generate_remediation_tasks(scores, None)
        assert len(tasks) == 1
        assert "memory system" in tasks[0].lower()
        assert "0.20" in tasks[0]

    def test_no_task_above_threshold(self):
        scores = {
            "memory_system": {"score": 0.8, "evidence": [], "label": "Memory"},
        }
        tasks = self_model.generate_remediation_tasks(scores, None)
        assert len(tasks) == 0

    def test_skips_duplicate_if_already_below(self):
        scores = {
            "memory_system": {"score": 0.2, "evidence": [], "label": "Memory"},
        }
        prev = {"scores": {"memory_system": 0.3}}  # was already below
        tasks = self_model.generate_remediation_tasks(scores, prev)
        assert len(tasks) == 0

    def test_generates_if_newly_dropped(self):
        scores = {
            "memory_system": {"score": 0.2, "evidence": [], "label": "Memory"},
        }
        prev = {"scores": {"memory_system": 0.6}}  # was above, now dropped
        tasks = self_model.generate_remediation_tasks(scores, prev)
        assert len(tasks) == 1


# --- check_weekly_regression ---

class TestWeeklyRegression:
    def _make_history(self, days_ago, scores):
        """Build a history dict with two snapshots (function requires >=2)."""
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=days_ago + 7)).isoformat()
        return {
            "snapshots": [
                {"timestamp": old_ts, "scores": scores, "scoring_version": 2},
                {"timestamp": ts, "scores": scores, "scoring_version": 2},
            ]
        }

    def test_detects_regression(self):
        current = {
            "memory_system": {"score": 0.3, "evidence": [], "label": "Memory"},
        }
        history = self._make_history(7, {"memory_system": 0.7})
        result = self_model.check_weekly_regression(current, history)
        assert "alerts" in result
        # Should detect the 0.7 -> 0.3 drop (>10%)
        assert len(result["alerts"]) > 0

    def test_no_regression_stable(self):
        current = {
            "memory_system": {"score": 0.7, "evidence": [], "label": "Memory"},
        }
        history = self._make_history(7, {"memory_system": 0.7})
        result = self_model.check_weekly_regression(current, history)
        assert len(result.get("alerts", [])) == 0

    def test_empty_history_no_crash(self):
        current = {
            "memory_system": {"score": 0.5, "evidence": [], "label": "Memory"},
        }
        result = self_model.check_weekly_regression(current, {"snapshots": []})
        assert "alerts" in result
        assert len(result["alerts"]) == 0


# --- update_model ---

class TestUpdateModel:
    def test_adds_capability(self, tmp_data_dir):
        # Init model first
        self_model.save_model({
            "capabilities": ["existing"],
            "strengths": [],
            "weaknesses": [],
            "trajectory": [],
            "last_updated": None,
        })
        self_model.update_model(capability_change="new_cap")
        model = self_model.load_model()
        assert "new_cap" in model["capabilities"]
        assert "existing" in model["capabilities"]

    def test_no_duplicate_capability(self, tmp_data_dir):
        self_model.save_model({
            "capabilities": ["existing"],
            "strengths": [],
            "weaknesses": [],
            "trajectory": [],
            "last_updated": None,
        })
        self_model.update_model(capability_change="existing")
        model = self_model.load_model()
        assert model["capabilities"].count("existing") == 1

    def test_adds_trajectory_event(self, tmp_data_dir):
        self_model.save_model({
            "capabilities": [],
            "strengths": [],
            "weaknesses": [],
            "trajectory": [],
            "last_updated": None,
        })
        self_model.update_model(trajectory_event="Test event happened")
        model = self_model.load_model()
        assert len(model["trajectory"]) == 1
        assert model["trajectory"][0]["event"] == "Test event happened"
        assert model["last_updated"] is not None

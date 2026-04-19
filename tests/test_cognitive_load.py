"""Tests for clarvis.cognition.cognitive_load — homeostatic regulation."""

import json
import re
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import pytest

from clarvis.cognition.cognitive_load import (
    compute_load,
    measure_failure_rate,
    measure_queue_velocity,
    measure_cron_times,
    measure_capability_degradation,
    should_defer_task,
    estimate_task_complexity,
    OVERLOAD_THRESHOLD,
    CAUTION_THRESHOLD,
    W_FAILURE,
    W_QUEUE,
    W_CRON_TIME,
    W_CAPABILITY,
)


class TestMeasureFailureRate:
    def test_no_log_file(self, tmp_path):
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_failure_rate() == 0.0

    def test_empty_log(self, tmp_path):
        (tmp_path / "watchdog.log").write_text("")
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_failure_rate() == 0.0

    def test_recent_failures(self, tmp_path):
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S")
        log = f"[{ts}] Watchdog check: 5 failures\n"
        (tmp_path / "watchdog.log").write_text(log)
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            rate = measure_failure_rate()
            assert 0.0 < rate <= 1.0

    def test_old_failures_ignored(self, tmp_path):
        old = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
        log = f"[{old}] Watchdog check: 10 failures\n"
        (tmp_path / "watchdog.log").write_text(log)
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_failure_rate() == 0.0

    def test_zero_failures(self, tmp_path):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        log = f"[{now}] Watchdog check: 0 failures\n"
        (tmp_path / "watchdog.log").write_text(log)
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_failure_rate() == 0.0


class TestMeasureQueueVelocity:
    def test_no_queue_file(self, tmp_path):
        with patch("clarvis.cognition.cognitive_load.QUEUE_PATH", tmp_path / "QUEUE.md"):
            assert measure_queue_velocity() == 0.0

    def test_all_completed(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("- [x] Task A\n- [x] Task B\n- [x] Task C\n")
        with patch("clarvis.cognition.cognitive_load.QUEUE_PATH", q):
            assert measure_queue_velocity() == 0.0

    def test_all_pending(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("- [ ] Task A\n- [ ] Task B\n")
        with patch("clarvis.cognition.cognitive_load.QUEUE_PATH", q):
            assert measure_queue_velocity() == 1.0

    def test_mixed(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("- [x] Done\n- [ ] Pending\n")
        with patch("clarvis.cognition.cognitive_load.QUEUE_PATH", q):
            assert measure_queue_velocity() == 0.5


class TestMeasureCronTimes:
    def test_no_log_file(self, tmp_path):
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_cron_times() == 0.0

    def test_empty_log(self, tmp_path):
        (tmp_path / "autonomous.log").write_text("")
        with patch("clarvis.cognition.cognitive_load.CRON_LOG_DIR", tmp_path):
            assert measure_cron_times() == 0.0


class TestMeasureCapabilityDegradation:
    def test_no_history_file(self, tmp_path):
        with patch("clarvis.cognition.cognitive_load.CAPABILITY_HISTORY", tmp_path / "cap.json"):
            assert measure_capability_degradation() == 0.0

    def test_single_snapshot(self, tmp_path):
        f = tmp_path / "cap.json"
        f.write_text(json.dumps([{"scores": {"brain": 0.8}}]))
        with patch("clarvis.cognition.cognitive_load.CAPABILITY_HISTORY", f):
            assert measure_capability_degradation() == 0.0

    def test_no_degradation(self, tmp_path):
        f = tmp_path / "cap.json"
        f.write_text(json.dumps([
            {"scores": {"brain": 0.7, "speed": 0.6}},
            {"scores": {"brain": 0.8, "speed": 0.7}},
        ]))
        with patch("clarvis.cognition.cognitive_load.CAPABILITY_HISTORY", f):
            assert measure_capability_degradation() == 0.0

    def test_degradation_detected(self, tmp_path):
        f = tmp_path / "cap.json"
        f.write_text(json.dumps([
            {"scores": {"brain": 0.9, "speed": 0.8, "accuracy": 0.9}},
            {"scores": {"brain": 0.3, "speed": 0.2, "accuracy": 0.3}},
        ]))
        with patch("clarvis.cognition.cognitive_load.CAPABILITY_HISTORY", f):
            d = measure_capability_degradation()
            assert d > 0.0


class TestComputeLoad:
    @patch("clarvis.cognition.cognitive_load.measure_failure_rate", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_queue_velocity", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_cron_times", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_capability_degradation", return_value=0.0)
    def test_healthy_system(self, *mocks):
        result = compute_load()
        assert result["score"] == 0.0
        assert result["status"] == "HEALTHY"
        assert result["action"] == "proceed"

    @patch("clarvis.cognition.cognitive_load.measure_failure_rate", return_value=1.0)
    @patch("clarvis.cognition.cognitive_load.measure_queue_velocity", return_value=1.0)
    @patch("clarvis.cognition.cognitive_load.measure_cron_times", return_value=1.0)
    @patch("clarvis.cognition.cognitive_load.measure_capability_degradation", return_value=1.0)
    def test_overloaded_system(self, *mocks):
        result = compute_load()
        assert result["score"] == 1.0
        assert result["status"] == "OVERLOADED"
        assert result["action"] == "defer_all_non_recovery"

    @patch("clarvis.cognition.cognitive_load.measure_failure_rate", return_value=0.5)
    @patch("clarvis.cognition.cognitive_load.measure_queue_velocity", return_value=0.5)
    @patch("clarvis.cognition.cognitive_load.measure_cron_times", return_value=0.5)
    @patch("clarvis.cognition.cognitive_load.measure_capability_degradation", return_value=0.5)
    def test_caution_zone(self, *mocks):
        result = compute_load()
        assert result["score"] == 0.5
        assert result["status"] == "CAUTION"
        assert result["action"] == "defer_p2"

    @patch("clarvis.cognition.cognitive_load.measure_failure_rate", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_queue_velocity", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_cron_times", return_value=0.0)
    @patch("clarvis.cognition.cognitive_load.measure_capability_degradation", return_value=0.0)
    def test_result_structure(self, *mocks):
        result = compute_load()
        assert "score" in result
        assert "status" in result
        assert "action" in result
        assert "components" in result
        assert "weights" in result
        assert "thresholds" in result
        assert "timestamp" in result

    def test_weights_sum_to_one(self):
        total = W_FAILURE + W_QUEUE + W_CRON_TIME + W_CAPABILITY
        assert abs(total - 1.0) < 0.001


class TestShouldDeferTask:
    @patch("clarvis.cognition.cognitive_load.compute_load")
    def test_p0_never_deferred_when_healthy(self, mock_load):
        mock_load.return_value = {"score": 0.3, "status": "HEALTHY"}
        defer, reason = should_defer_task("P0")
        assert defer is False

    @patch("clarvis.cognition.cognitive_load.compute_load")
    def test_p0_deferred_when_overloaded(self, mock_load):
        mock_load.return_value = {"score": 0.9, "status": "OVERLOADED"}
        defer, reason = should_defer_task("P0")
        assert defer is True

    @patch("clarvis.cognition.cognitive_load.compute_load")
    def test_p2_deferred_on_caution(self, mock_load):
        mock_load.return_value = {"score": 0.6, "status": "CAUTION"}
        defer, reason = should_defer_task("P2")
        assert defer is True

    @patch("clarvis.cognition.cognitive_load.compute_load")
    def test_p1_not_deferred_on_caution(self, mock_load):
        mock_load.return_value = {"score": 0.6, "status": "CAUTION"}
        defer, reason = should_defer_task("P1")
        assert defer is False


class TestEstimateTaskComplexity:
    def test_simple_task(self):
        result = estimate_task_complexity("Fix typo in README")
        assert result["complexity"] in ("simple", "medium")

    def test_complex_task(self):
        result = estimate_task_complexity(
            "Implement a comprehensive multi-step benchmark suite "
            "that runs a full audit with migration and refactor"
        )
        assert result["complexity"] in ("medium", "complex", "oversized")
        assert result["score"] > 0

    def test_returns_required_fields(self):
        result = estimate_task_complexity("Add a test")
        assert "complexity" in result
        assert "score" in result
        assert "recommendation" in result

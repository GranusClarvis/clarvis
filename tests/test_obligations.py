"""Tests for clarvis.cognition.obligations — durable obligation enforcement."""

import json
import os
from pathlib import Path

import pytest

from clarvis.cognition.obligations import ObligationTracker


@pytest.fixture
def tracker(tmp_path):
    filepath = str(tmp_path / "obligations.json")
    with pytest.MonkeyPatch.context() as m:
        m.setattr("clarvis.cognition.obligations.OBLIGATIONS_LOG",
                   str(tmp_path / "log.jsonl"))
        t = ObligationTracker(filepath=filepath)
        yield t


class TestObligationCrud:
    def test_record_and_get(self, tracker):
        ob = tracker.record_obligation("test-label", "test description")
        assert ob["label"] == "test-label"
        assert ob["state"]["status"] == "active"
        retrieved = tracker.get(ob["id"])
        assert retrieved is not None
        assert retrieved["id"] == ob["id"]

    def test_list_all(self, tracker):
        tracker.record_obligation("a", "first")
        tracker.record_obligation("b", "second")
        assert len(tracker.list_all()) == 2

    def test_list_active_excludes_retired(self, tracker):
        ob = tracker.record_obligation("retire-me", "will retire")
        tracker.retire(ob["id"], "no longer needed")
        active = tracker.list_active()
        assert len(active) == 0

    def test_retire(self, tracker):
        ob = tracker.record_obligation("temp", "temporary")
        tracker.retire(ob["id"], "done")
        ob_after = tracker.get(ob["id"])
        assert ob_after["state"]["status"] == "retired"

    def test_get_nonexistent(self, tracker):
        assert tracker.get("nonexistent_id") is None


class TestObligationChecking:
    def test_check_obligation_satisfied(self, tracker):
        ob = tracker.record_obligation(
            "echo-test", "runs echo",
            check_command="echo ok",
        )
        result = tracker.check_obligation(ob)
        assert result["satisfied"] is True
        assert ob["state"]["satisfied_count"] == 1
        assert ob["state"]["consecutive_violations"] == 0

    def test_check_obligation_violated(self, tracker):
        ob = tracker.record_obligation(
            "false-test", "always fails",
            check_command="false",
        )
        result = tracker.check_obligation(ob)
        assert result["satisfied"] is False
        assert ob["state"]["violated_count"] == 1
        assert ob["state"]["consecutive_violations"] == 1

    def test_escalation_after_repeated_violations(self, tracker):
        ob = tracker.record_obligation(
            "failing", "always fails",
            check_command="false",
        )
        for _ in range(3):
            tracker.check_obligation(ob)
        assert ob["state"]["consecutive_violations"] == 3
        assert ob["state"]["escalation_level"] >= 1

    def test_escalation_resets_on_satisfaction(self, tracker):
        ob = tracker.record_obligation(
            "flaky", "sometimes fails",
            check_command="false",
        )
        for _ in range(3):
            tracker.check_obligation(ob)
        assert ob["state"]["escalation_level"] >= 1
        ob["check_command"] = "true"
        tracker.check_obligation(ob)
        assert ob["state"]["consecutive_violations"] == 0

    def test_no_check_mechanism_assumed_satisfied(self, tracker):
        ob = tracker.record_obligation("passive", "no check")
        result = tracker.check_obligation(ob)
        assert result["satisfied"] is True

    def test_check_all_returns_results(self, tracker):
        tracker.record_obligation("a", "first", check_command="true")
        tracker.record_obligation("b", "second", check_command="true")
        results = tracker.check_all()
        assert len(results) == 2
        assert all(r["satisfied"] for r in results)


class TestObligationPersistence:
    def test_save_and_reload(self, tmp_path):
        filepath = str(tmp_path / "obs.json")
        log_path = str(tmp_path / "log.jsonl")
        with pytest.MonkeyPatch.context() as m:
            m.setattr("clarvis.cognition.obligations.OBLIGATIONS_LOG", log_path)
            t1 = ObligationTracker(filepath=filepath)
            t1.record_obligation("persist-test", "should survive reload")

        with pytest.MonkeyPatch.context() as m:
            m.setattr("clarvis.cognition.obligations.OBLIGATIONS_LOG", log_path)
            t2 = ObligationTracker(filepath=filepath)
            assert len(t2.list_all()) == 1
            assert t2.list_all()[0]["label"] == "persist-test"

    def test_corrupt_file_creates_fresh(self, tmp_path):
        filepath = str(tmp_path / "bad.json")
        with open(filepath, "w") as f:
            f.write("{broken json")
        log_path = str(tmp_path / "log.jsonl")
        with pytest.MonkeyPatch.context() as m:
            m.setattr("clarvis.cognition.obligations.OBLIGATIONS_LOG", log_path)
            t = ObligationTracker(filepath=filepath)
            assert t.data == {"obligations": [], "version": 1}


class TestIsDue:
    def test_never_checked_is_due(self, tracker):
        ob = tracker.record_obligation("due-test", "should be due")
        assert tracker._is_due(ob) is True

    def test_recently_checked_not_due(self, tracker):
        ob = tracker.record_obligation("recent", "just checked", frequency="daily")
        tracker.check_obligation(ob)
        assert tracker._is_due(ob) is False

    def test_retired_never_due(self, tracker):
        ob = tracker.record_obligation("retired", "done")
        tracker.retire(ob["id"])
        ob_after = tracker.get(ob["id"])
        assert tracker._is_due(ob_after) is False

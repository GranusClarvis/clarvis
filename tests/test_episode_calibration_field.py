"""Regression test for episode calibration field wiring.

Verifies:
- `calibration_score` and `confidence_band` are written to the episode dict
  when a `conf_outcome_result` is supplied to `episode_encode`.
- Both fields are skipped (and the skip is logged) when `conf_outcome_result`
  is None or missing required keys.
- `_derive_calibration` computes the Brier-style score correctly.
- `_confidence_band` buckets confidence into low|medium|high.
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from clarvis.heartbeat.episode_encoder import (
    _confidence_band,
    _derive_calibration,
    episode_encode,
)


class FakeEpisodicMemory:
    """In-memory stand-in for EpisodicMemory that captures encode kwargs."""

    instances = []

    def __init__(self):
        self.calls = []
        self.episodes = []
        FakeEpisodicMemory.instances.append(self)

    def encode(self, task_text, section, salience, outcome,
               duration_s=0, error_msg=None, steps_taken=None,
               failure_type=None, output_text=None,
               calibration_score=None, confidence_band=None):
        ep = {
            "task": task_text,
            "outcome": outcome,
            "duration_s": duration_s,
        }
        if calibration_score is not None:
            ep["calibration_score"] = calibration_score
        if confidence_band is not None:
            ep["confidence_band"] = confidence_band
        self.calls.append({
            "calibration_score": calibration_score,
            "confidence_band": confidence_band,
        })
        self.episodes.append(ep)
        return ep


@pytest.fixture(autouse=True)
def _reset_fake_em():
    FakeEpisodicMemory.instances = []
    yield


# ---------------------------------------------------------------------------
# Pure-helper tests
# ---------------------------------------------------------------------------

class TestConfidenceBand:
    def test_low(self):
        assert _confidence_band(0.0) == "low"
        assert _confidence_band(0.49) == "low"

    def test_medium(self):
        assert _confidence_band(0.5) == "medium"
        assert _confidence_band(0.79) == "medium"

    def test_high(self):
        assert _confidence_band(0.8) == "high"
        assert _confidence_band(1.0) == "high"

    def test_invalid_returns_none(self):
        assert _confidence_band(None) is None
        assert _confidence_band("x") is None
        assert _confidence_band(1.5) is None
        assert _confidence_band(-0.1) is None


class TestDeriveCalibration:
    def test_correct_high_confidence(self):
        cal, band, reason = _derive_calibration(
            {"confidence": 0.9, "correct": True}, log=lambda m: None)
        # Brier: 1 - (0.9 - 1)**2 = 0.99
        assert cal == 0.99
        assert band == "high"
        assert reason is None

    def test_wrong_high_confidence(self):
        cal, band, _ = _derive_calibration(
            {"confidence": 0.9, "correct": False}, log=lambda m: None)
        # Brier: 1 - (0.9 - 0)**2 = 0.19
        assert cal == 0.19
        assert band == "high"

    def test_perfect_calibration(self):
        cal, band, _ = _derive_calibration(
            {"confidence": 1.0, "correct": True}, log=lambda m: None)
        assert cal == 1.0
        assert band == "high"

    def test_none_input_returns_skip_reason(self):
        cal, band, reason = _derive_calibration(None, log=lambda m: None)
        assert cal is None
        assert band is None
        assert "None" in reason

    def test_missing_keys(self):
        cal, band, reason = _derive_calibration(
            {"confidence": 0.7}, log=lambda m: None)
        assert cal is None and band is None
        assert "missing" in reason

    def test_bad_type(self):
        cal, band, reason = _derive_calibration(
            "not a dict", log=lambda m: None)
        assert cal is None and band is None
        assert "bad type" in reason


# ---------------------------------------------------------------------------
# Integration: episode_encode wires calibration into em.encode()
# ---------------------------------------------------------------------------

class TestEpisodeEncodeWiring:
    def test_field_written_when_conf_outcome_available(self):
        logged = []
        _pf_errors = []
        result = episode_encode(
            task="test task",
            task_section="TEST",
            best_salience=0.5,
            task_status="success",
            task_duration=1.2,
            error_type=None,
            output_text="RESULT: ok",
            preflight_data={},
            _pf_errors=_pf_errors,
            EpisodicMemory=FakeEpisodicMemory,
            record_trajectory_event=None,
            log=logged.append,
            conf_outcome_result={"confidence": 0.85, "correct": True},
        )

        assert FakeEpisodicMemory.instances, "EpisodicMemory was not instantiated"
        em = FakeEpisodicMemory.instances[-1]
        assert em.calls, "encode() was not called"
        call = em.calls[-1]
        # 1 - (0.85 - 1)**2 = 0.9775
        assert call["calibration_score"] == 0.9775
        assert call["confidence_band"] == "high"

        # Ensure the persisted episode dict carries the fields
        ep = em.episodes[-1]
        assert ep["calibration_score"] == 0.9775
        assert ep["confidence_band"] == "high"

        # No pf_errors expected on a clean run
        assert _pf_errors == []
        assert "episodic" in result  # timing dict returned

    def test_skipped_when_conf_outcome_is_none_with_log(self):
        logged = []
        _pf_errors = []
        episode_encode(
            task="test task",
            task_section="TEST",
            best_salience=0.5,
            task_status="failure",
            task_duration=2.0,
            error_type="action",
            output_text="RESULT: fail",
            preflight_data={},
            _pf_errors=_pf_errors,
            EpisodicMemory=FakeEpisodicMemory,
            record_trajectory_event=None,
            log=logged.append,
            conf_outcome_result=None,
        )

        em = FakeEpisodicMemory.instances[-1]
        call = em.calls[-1]
        assert call["calibration_score"] is None
        assert call["confidence_band"] is None

        ep = em.episodes[-1]
        assert "calibration_score" not in ep
        assert "confidence_band" not in ep

        # Skip reason was logged
        skip_logs = [m for m in logged if "Calibration field skipped" in m]
        assert skip_logs, f"Expected a skip-reason log line, got: {logged}"
        assert "None" in skip_logs[0]

    def test_skipped_when_conf_outcome_missing_keys(self):
        logged = []
        _pf_errors = []
        episode_encode(
            task="t",
            task_section="X",
            best_salience=0.1,
            task_status="success",
            task_duration=0.1,
            error_type=None,
            output_text=None,
            preflight_data={},
            _pf_errors=_pf_errors,
            EpisodicMemory=FakeEpisodicMemory,
            record_trajectory_event=None,
            log=logged.append,
            conf_outcome_result={"confidence": 0.5},  # missing 'correct'
        )
        em = FakeEpisodicMemory.instances[-1]
        assert em.calls[-1]["calibration_score"] is None
        assert any("Calibration field skipped" in m for m in logged)

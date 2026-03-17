"""Unit tests for performance_gate trajectory gate behavior."""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import performance_gate  # noqa: E402


def test_trajectory_gate_warmup(monkeypatch):
    fake = types.SimpleNamespace(
        GATE_THRESHOLDS={"min_episodes": 5},
        load_trajectory_events=lambda hours=24: [{"x": 1}],
        summarize_trajectory=lambda events: {
            "episodes": 1,
            "avg_score": 0.9,
            "pass_rate": 1.0,
            "gate": {"pass": False, "failures": ["episodes<5"]},
        },
    )
    monkeypatch.setitem(sys.modules, "clarvis.metrics.trajectory", fake)
    result = performance_gate.gate_trajectory_eval(verbose=False)
    assert result["passed"] is True
    assert result["detail"]["status"] == "warmup"


def test_trajectory_gate_active_failure(monkeypatch):
    fake = types.SimpleNamespace(
        GATE_THRESHOLDS={"min_episodes": 5},
        load_trajectory_events=lambda hours=24: [{"x": 1}] * 7,
        summarize_trajectory=lambda events: {
            "episodes": 7,
            "avg_score": 0.41,
            "pass_rate": 0.4,
            "gate": {"pass": False, "failures": ["avg_score too low"]},
        },
    )
    monkeypatch.setitem(sys.modules, "clarvis.metrics.trajectory", fake)
    result = performance_gate.gate_trajectory_eval(verbose=False)
    assert result["passed"] is False
    assert result["detail"]["status"] == "active"
    assert "avg_score too low" in result["detail"]["gate_failures"]

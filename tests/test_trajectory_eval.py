"""Trajectory evaluation harness tests."""

import importlib


def _load_module(monkeypatch, tmp_path):
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(tmp_path))
    import clarvis.metrics.trajectory as trajectory
    return importlib.reload(trajectory)


def test_score_episode_success_high(monkeypatch, tmp_path):
    tr = _load_module(monkeypatch, tmp_path)
    scored = tr.score_trajectory_episode(
        {
            "task_outcome": "success",
            "duration_s": 120,
            "code_validation_errors": 0,
            "retrieval_verdict": "CORRECT",
            "tool_call_count": 6,
        }
    )
    assert scored["trajectory_score"] >= 0.9
    assert scored["trajectory_components"]["completion"] == 1.0


def test_trajectory_gate_fails_when_insufficient_episodes(monkeypatch, tmp_path):
    tr = _load_module(monkeypatch, tmp_path)
    events = [
        {"task_outcome": "success", "duration_s": 90, "code_validation_errors": 0}
        for _ in range(2)
    ]
    summary = tr.summarize_trajectory(events)
    assert summary["gate"]["pass"] is False
    assert any("episodes=" in f for f in summary["gate"]["failures"])


def test_record_and_load_events(monkeypatch, tmp_path):
    tr = _load_module(monkeypatch, tmp_path)
    for _ in range(5):
        tr.record_trajectory_event(
            {
                "task": "Test trajectory",
                "task_outcome": "success",
                "duration_s": 180,
                "code_validation_errors": 0,
                "retrieval_verdict": "CORRECT",
                "tool_call_count": 5,
            }
        )
    events = tr.load_trajectory_events(hours=24)
    assert len(events) == 5
    summary = tr.summarize_trajectory(events)
    assert summary["gate"]["pass"] is True
    assert summary["avg_score"] >= tr.GATE_THRESHOLDS["min_avg_score"]

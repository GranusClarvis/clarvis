"""Unit tests for the PI anomaly guard in performance_benchmark.py.

The guard prevents a single bad measurement (e.g., EpisodicMemory init failure
returning 0.0) from collapsing PI by retaining the previous value when a core
metric drops >50%.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
try:
    import _paths  # noqa: F401,E402
except ImportError:
    pass

import importlib.util

import pytest

_pb_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "metrics", "performance_benchmark.py")

def _load_pb():
    """Load performance_benchmark by file path to avoid namespace package issues."""
    if "scripts.metrics.performance_benchmark" in sys.modules:
        return sys.modules["scripts.metrics.performance_benchmark"]
    spec = importlib.util.spec_from_file_location("scripts.metrics.performance_benchmark", _pb_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scripts.metrics.performance_benchmark"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def metrics_dir(tmp_path, monkeypatch):
    """Set up a temp dir for metrics files and patch METRICS_FILE."""
    metrics_file = str(tmp_path / "performance_metrics.json")
    alerts_file = str(tmp_path / "performance_alerts.jsonl")
    history_file = str(tmp_path / "performance_history.jsonl")
    pb = _load_pb()
    monkeypatch.setattr(pb, "METRICS_FILE", metrics_file)
    monkeypatch.setattr(pb, "ALERTS_FILE", alerts_file)
    monkeypatch.setattr(pb, "HISTORY_FILE", history_file)
    return tmp_path, metrics_file, alerts_file


def _write_prev_metrics(metrics_file, metrics):
    """Write a fake previous metrics file."""
    data = {
        "timestamp": "2026-04-10T05:45:00+00:00",
        "metrics": metrics,
        "details": {},
        "pi": {"pi": 0.999},
        "summary": {},
    }
    with open(metrics_file, "w") as f:
        json.dump(data, f)


def test_guard_blocks_catastrophic_drop(metrics_dir, monkeypatch):
    """Core metric dropping from 0.94 to 0.0 should be blocked."""
    pb = _load_pb()

    _, metrics_file, alerts_file = metrics_dir
    prev = {
        "episode_success_rate": 0.941,
        "action_accuracy": 0.967,
        "phi": 0.741,
        "task_quality_score": 0.865,
        "retrieval_hit_rate": 1.0,
        "brain_query_avg_ms": 272.0,
        "brain_query_p95_ms": 323.0,
        "graph_density": 30.0,
        "brain_total_memories": 2955,
        "bloat_score": 0.0,
        "context_relevance": 0.945,
        "code_quality_score": 0.786,
    }
    _write_prev_metrics(metrics_file, prev)

    # Stub benchmarks to return catastrophic values
    monkeypatch.setattr(pb, "benchmark_brain_speed", lambda: {"avg_ms": 280, "p95_ms": 330})
    monkeypatch.setattr(pb, "benchmark_brain_stats", lambda: {"graph_density": 30, "total_memories": 2955, "bloat_score": 0.0})
    monkeypatch.setattr(pb, "benchmark_episodes", lambda: {"success_rate": 0.0, "action_accuracy": 0.0})
    monkeypatch.setattr(pb, "benchmark_quality", lambda: {"task_quality_score": 0.0, "code_quality_score": 0.0})

    # Stub context_relevance refresh
    monkeypatch.setattr(pb, "_safe_bench", lambda fn, name: fn())

    report = pb.run_refresh_benchmark()

    # Guard should have retained previous values
    assert report["metrics"]["episode_success_rate"] == 0.941
    assert report["metrics"]["action_accuracy"] == 0.967
    assert report["metrics"]["task_quality_score"] == 0.865

    # Anomalies should be recorded in details
    assert "pi_anomalies" in report["details"]
    assert len(report["details"]["pi_anomalies"]) >= 3

    # Alerts file should have the anomaly record
    assert os.path.exists(alerts_file)
    with open(alerts_file) as f:
        alert = json.loads(f.readline())
    assert alert["type"] == "PI_ANOMALY"


def test_guard_allows_normal_fluctuation(metrics_dir, monkeypatch):
    """Small drops (< 50%) should NOT be blocked."""
    pb = _load_pb()

    _, metrics_file, alerts_file = metrics_dir
    prev = {
        "episode_success_rate": 0.941,
        "action_accuracy": 0.967,
        "phi": 0.741,
        "task_quality_score": 0.865,
        "retrieval_hit_rate": 1.0,
        "brain_query_avg_ms": 272.0,
        "brain_query_p95_ms": 323.0,
        "graph_density": 30.0,
        "brain_total_memories": 2955,
        "bloat_score": 0.0,
        "context_relevance": 0.945,
        "code_quality_score": 0.786,
    }
    _write_prev_metrics(metrics_file, prev)

    # Small drops: 0.941 -> 0.90 (4.4% drop) — should be allowed
    monkeypatch.setattr(pb, "benchmark_brain_speed", lambda: {"avg_ms": 280, "p95_ms": 330})
    monkeypatch.setattr(pb, "benchmark_brain_stats", lambda: {"graph_density": 30, "total_memories": 2955, "bloat_score": 0.0})
    monkeypatch.setattr(pb, "benchmark_episodes", lambda: {"success_rate": 0.90, "action_accuracy": 0.93})
    monkeypatch.setattr(pb, "benchmark_quality", lambda: {"task_quality_score": 0.80, "code_quality_score": 0.75})
    monkeypatch.setattr(pb, "_safe_bench", lambda fn, name: fn())

    report = pb.run_refresh_benchmark()

    # Values should reflect the actual (slightly lower) measurements
    assert report["metrics"]["episode_success_rate"] == 0.90
    assert report["metrics"]["action_accuracy"] == 0.93
    assert "pi_anomalies" not in report["details"]


def test_guard_skips_low_prev_values(metrics_dir, monkeypatch):
    """If previous value was already very low (< 0.1), guard should not trigger."""
    pb = _load_pb()

    _, metrics_file, _ = metrics_dir
    prev = {
        "episode_success_rate": 0.05,  # Already very low
        "action_accuracy": 0.967,
        "phi": 0.741,
        "task_quality_score": 0.865,
        "retrieval_hit_rate": 1.0,
        "brain_query_avg_ms": 272.0,
        "brain_query_p95_ms": 323.0,
        "graph_density": 30.0,
        "brain_total_memories": 2955,
        "bloat_score": 0.0,
        "context_relevance": 0.945,
        "code_quality_score": 0.786,
    }
    _write_prev_metrics(metrics_file, prev)

    monkeypatch.setattr(pb, "benchmark_brain_speed", lambda: {"avg_ms": 280, "p95_ms": 330})
    monkeypatch.setattr(pb, "benchmark_brain_stats", lambda: {"graph_density": 30, "total_memories": 2955, "bloat_score": 0.0})
    monkeypatch.setattr(pb, "benchmark_episodes", lambda: {"success_rate": 0.0, "action_accuracy": 0.95})
    monkeypatch.setattr(pb, "benchmark_quality", lambda: {"task_quality_score": 0.85, "code_quality_score": 0.75})
    monkeypatch.setattr(pb, "_safe_bench", lambda fn, name: fn())

    report = pb.run_refresh_benchmark()

    # episode_success_rate was already 0.05, so dropping to 0.0 should NOT be guarded
    # (prev_val <= 0.1 threshold)
    assert report["metrics"]["episode_success_rate"] == 0.0

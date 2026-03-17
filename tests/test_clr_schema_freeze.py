"""CLR schema freeze contract tests."""

from clarvis.metrics import clr


def test_clr_schema_version_frozen():
    assert clr.CLR_SCHEMA_VERSION == "1.0"


def test_clr_weights_frozen_and_sum_to_one():
    expected = {
        "memory_quality": 0.20,
        "retrieval_precision": 0.20,
        "prompt_context": 0.15,
        "task_success": 0.20,
        "autonomy": 0.15,
        "efficiency": 0.10,
    }
    assert clr.WEIGHTS == expected
    valid, total = clr.validate_weights()
    assert valid is True
    assert abs(total - 1.0) <= 1e-6


def test_clr_gate_thresholds_frozen():
    thresholds = clr.GATE_THRESHOLDS
    assert thresholds["min_clr"] == 0.40
    assert thresholds["min_value_add"] == 0.05
    assert thresholds["min_dimensions"] == {
        "memory_quality": 0.25,
        "retrieval_precision": 0.25,
        "prompt_context": 0.20,
        "task_success": 0.35,
    }


def test_clr_baseline_keys_match_weights():
    assert set(clr.BASELINE.keys()) == set(clr.WEIGHTS.keys())

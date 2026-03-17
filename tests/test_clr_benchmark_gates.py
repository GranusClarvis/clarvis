"""CLR benchmark gate tests."""

from clarvis.metrics.clr import evaluate_clr_gates, validate_weights


def test_validate_weights_sum_to_one():
    valid, total = validate_weights({"a": 0.5, "b": 0.5})
    assert valid is True
    assert total == 1.0


def test_evaluate_clr_gates_pass_case():
    result = {
        "clr": 0.65,
        "value_add": 0.20,
        "dimensions": {
            "memory_quality": {"score": 0.40},
            "retrieval_precision": {"score": 0.41},
            "prompt_context": {"score": 0.35},
            "task_success": {"score": 0.60},
            "autonomy": {"score": 0.55},
            "efficiency": {"score": 0.70},
        },
    }
    gate = evaluate_clr_gates(result)
    assert gate["pass"] is True
    assert gate["failures"] == []


def test_evaluate_clr_gates_fail_case():
    result = {
        "clr": 0.20,
        "value_add": -0.01,
        "dimensions": {
            "memory_quality": {"score": 0.10},
            "retrieval_precision": {"score": 0.05},
            "prompt_context": {"score": 0.10},
            "task_success": {"score": 0.20},
            "autonomy": {"score": 0.30},
            "efficiency": {"score": 0.40},
        },
    }
    gate = evaluate_clr_gates(result)
    assert gate["pass"] is False
    assert any("clr<" in f for f in gate["failures"])
    assert any("value_add<" in f for f in gate["failures"])

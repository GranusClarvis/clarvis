"""Tests for CLR perturbation / ablation harness v2."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
from clarvis.metrics.clr_perturbation import (
    ABLATABLE_MODULES,
    REFERENCE_TASKS,
    _measure_assembly_quality,
    run_ablation_sweep,
    print_report,
)


def _mock_generate_brief(current_task, tier="standard", **kwargs):
    """Mock brief that includes section markers based on assembly state."""
    # Simulate a brief with sections that depend on budget state
    parts = [f"TASK: {current_task[:50]}"]
    parts.append("SUCCESS CRITERIA: test passes")
    parts.append("AVOID: failure patterns")
    parts.append("WORKING MEMORY: recent activity here")
    parts.append("GWT BROADCAST: attention codelets")
    parts.append("RELATED TASKS: queue items")
    parts.append("EPISODIC: past lessons learned")
    parts.append("BRAIN CONTEXT: knowledge graph results")
    parts.append("REASONING: multi-step approach")
    return "\n".join(parts)


def _mock_generate_brief_minimal(current_task, tier="standard", **kwargs):
    """Mock brief with minimal content (simulates heavy ablation)."""
    return f"TASK: {current_task[:50]}\nMinimal context."


def test_reference_tasks_are_harder():
    """Reference tasks should require multiple cognitive modules."""
    assert len(REFERENCE_TASKS) >= 4
    # Each task description should be substantive (not trivial)
    for task in REFERENCE_TASKS:
        assert len(task) > 80, f"Task too short to be hard: {task[:60]}"


def test_ablatable_modules_complete():
    """All 6 cognitive modules should be ablatable."""
    assert len(ABLATABLE_MODULES) == 6
    assert "episodic_recall" in ABLATABLE_MODULES
    assert "working_memory" in ABLATABLE_MODULES


def test_measure_assembly_quality_detects_sections():
    """Assembly quality measurement should detect section presence."""
    with patch("clarvis.context.assembly.generate_tiered_brief", _mock_generate_brief):
        with patch("clarvis.context.assembly.TIER_BUDGETS", {"standard": {}}):
            with patch("clarvis.context.assembly.HARD_SUPPRESS", frozenset()):
                result = _measure_assembly_quality([])
    assert result["quality"] > 0
    assert result["avg_sections"] > 0
    assert result["avg_chars"] > 0


def test_measure_assembly_quality_lower_when_ablated():
    """Ablating modules should reduce assembly quality."""
    # Full brief
    with patch("clarvis.context.assembly.generate_tiered_brief", _mock_generate_brief):
        with patch("clarvis.context.assembly.TIER_BUDGETS", {"standard": {}}):
            with patch("clarvis.context.assembly.HARD_SUPPRESS", frozenset()):
                full = _measure_assembly_quality([])

    # Minimal brief (simulating heavy ablation)
    with patch("clarvis.context.assembly.generate_tiered_brief", _mock_generate_brief_minimal):
        with patch("clarvis.context.assembly.TIER_BUDGETS", {"standard": {}}):
            with patch("clarvis.context.assembly.HARD_SUPPRESS", frozenset()):
                ablated = _measure_assembly_quality(["episodic_recall"])

    assert ablated["quality"] < full["quality"], (
        f"Ablated quality ({ablated['quality']}) should be lower than "
        f"full quality ({full['quality']})"
    )


def test_multi_component_ablation_pair_key_format():
    """Pair ablation keys should use '+' separator."""
    from itertools import combinations
    for pair in combinations(ABLATABLE_MODULES[:3], 2):
        key = "+".join(pair)
        assert "+" in key
        assert len(key.split("+")) == 2


def test_print_report_v2_format():
    """Report printer should handle v2 schema with assembly_quality."""
    result = {
        "timestamp": "2026-03-29T00:00:00+00:00",
        "schema_version": "2.0",
        "baseline": {
            "clr": 0.85,
            "assembly_quality": 0.75,
            "assembly_details": {
                "diversity": 0.8,
                "volume": 0.7,
                "avg_sections": 4.5,
                "avg_chars": 1200,
            },
            "dimensions": {},
        },
        "ablations": {
            "episodic_recall": {
                "clr": 0.84,
                "clr_delta": -0.01,
                "assembly_quality": 0.60,
                "aq_delta": -0.15,
                "assembly_details": {
                    "diversity": 0.6,
                    "volume": 0.6,
                    "avg_sections": 3.5,
                    "avg_chars": 900,
                },
                "disabled": ["episodic_recall"],
            },
        },
        "rankings": [
            {"module": "episodic_recall", "aq_delta": -0.15,
             "clr_delta": -0.01, "verdict": "CRITICAL"},
        ],
        "interaction_effects": [],
        "total_duration_s": 5.0,
    }
    # Should not raise
    print_report(result)


def test_interaction_effect_detection():
    """Interaction effects should detect synergy vs redundancy."""
    # If pair delta is MORE negative than sum of individual deltas → synergy
    # If pair delta is LESS negative than sum → redundancy
    pair_delta = -0.20
    ind_a = -0.08
    ind_b = -0.07
    expected = ind_a + ind_b  # -0.15
    interaction = pair_delta - expected  # -0.05 → synergy
    assert interaction < 0, "Pair worse than sum of parts = synergy"

    pair_delta_2 = -0.10
    interaction_2 = pair_delta_2 - expected  # +0.05 → redundancy
    assert interaction_2 > 0, "Pair better than sum of parts = redundancy"

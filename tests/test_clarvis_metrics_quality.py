"""Tests for clarvis.metrics.quality module.

Tests that call production quality functions (git log scanning, file I/O) are
marked slow — they exceed the 15s per-test budget in the postflight self-test.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

from clarvis.metrics.quality import (
    compute_task_quality_score,
    compute_code_quality_score,
    compute_semantic_depth,
    compute_efficiency_score,
    get_all_quality_metrics,
    structural_complexity_risk,
)


@pytest.mark.slow
class TestComputeTaskQualityScore:
    """Tests for compute_task_quality_score function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = compute_task_quality_score(days=1)
        assert isinstance(result, dict)

    def test_contains_expected_keys_or_error(self):
        """Test that result contains expected metric keys or error."""
        result = compute_task_quality_score(days=1)
        # Either has quality_score or has error (episodic_memory missing)
        assert 'quality_score' in result or 'error' in result

    def test_score_in_range(self):
        """Test that score is between 0 and 1."""
        result = compute_task_quality_score(days=7)
        score = result.get('quality_score', result.get('score', None))
        if score is not None:
            assert 0 <= score <= 1, f"Score {score} out of range"


@pytest.mark.slow
class TestComputeCodeQualityScore:
    """Tests for compute_code_quality_score function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = compute_code_quality_score(days=1)
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that result contains expected metric keys."""
        result = compute_code_quality_score(days=1)
        # Has quality_score and either sample_size or files_checked
        assert 'quality_score' in result
        assert 'components' in result

    def test_score_in_range(self):
        """Test that score is between 0 and 1."""
        result = compute_code_quality_score(days=7)
        score = result.get('quality_score', result.get('score', None))
        if score is not None:
            assert 0 <= score <= 1, f"Score {score} out of range"

    def test_components_tracked(self):
        """Test that components are tracked in result."""
        result = compute_code_quality_score(days=7)
        components = result.get('components', {})
        assert isinstance(components, dict)


@pytest.mark.slow
class TestComputeSemanticDepth:
    """Tests for compute_semantic_depth function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = compute_semantic_depth()
        assert isinstance(result, dict)

    def test_contains_depth_score(self):
        """Test that result contains depth score."""
        result = compute_semantic_depth()
        assert 'depth_score' in result or 'score' in result


@pytest.mark.slow
class TestComputeEfficiencyScore:
    """Tests for compute_efficiency_score function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = compute_efficiency_score()
        assert isinstance(result, dict)

    def test_contains_efficiency_metrics(self):
        """Test that result contains efficiency-related metrics."""
        result = compute_efficiency_score()
        assert 'efficiency_score' in result or 'score' in result


@pytest.mark.slow
class TestGetAllQualityMetrics:
    """Tests for get_all_quality_metrics function."""

    def test_returns_comprehensive_dict(self):
        """Test that function returns all quality metrics."""
        result = get_all_quality_metrics()
        assert isinstance(result, dict)

    def test_contains_task_and_code_metrics(self):
        """Test that both task and code quality are included."""
        result = get_all_quality_metrics()
        assert 'task_quality' in result or 'task' in result
        assert 'code_quality' in result or 'code' in result

    def test_all_scores_in_range(self):
        """Test that all scores are between 0 and 1."""
        result = get_all_quality_metrics()
        for key, value in result.items():
            if isinstance(value, dict):
                score = value.get('quality_score', value.get('score', None))
                if score is not None:
                    assert 0 <= score <= 1, f"{key} score {score} out of range"


class TestStructuralComplexityRisk:
    """Tests for the advisory structural_complexity_risk function."""

    def test_returns_expected_shape(self, tmp_path):
        """Test that output has the required keys."""
        f = tmp_path / "sample.py"
        f.write_text("def foo():\n    pass\n")
        result = structural_complexity_risk(str(f))
        assert "file" in result
        assert "risk" in result
        assert "candidates" in result
        assert result["risk"] in ("low", "medium", "high")

    def test_short_functions_are_low_risk(self, tmp_path):
        """Short functions should never be flagged."""
        f = tmp_path / "short.py"
        f.write_text("def a():\n" + "    x = 1\n" * 50 + "    return x\n")
        result = structural_complexity_risk(str(f))
        assert result["risk"] == "low"
        assert result["candidates"] == []

    def test_very_long_function_is_flagged(self, tmp_path):
        """A 300-line function should be flagged as high risk."""
        f = tmp_path / "long.py"
        f.write_text("def giant():\n" + "    x = 1\n" * 300 + "    return x\n")
        result = structural_complexity_risk(str(f))
        assert result["risk"] == "high"
        assert len(result["candidates"]) >= 1
        assert result["candidates"][0]["function"] == "giant"

    def test_firewall_not_in_get_all_quality_metrics(self):
        """FIREWALL: structural_complexity_risk must NOT appear in get_all_quality_metrics.

        This test enforces the invariant from the Decomposition Remediation plan:
        structural risk scores must never feed PI, code-quality score, or any
        autonomous optimization loop.
        """
        import inspect
        source = inspect.getsource(get_all_quality_metrics)
        assert "structural_complexity_risk" not in source, \
            "FIREWALL VIOLATION: structural_complexity_risk must not feed quality metrics"

    def test_firewall_not_in_code_quality_score(self):
        """FIREWALL: structural_complexity_risk must NOT be called by compute_code_quality_score."""
        import inspect
        source = inspect.getsource(compute_code_quality_score)
        assert "structural_complexity_risk" not in source, \
            "FIREWALL VIOLATION: structural_complexity_risk must not feed code quality score"
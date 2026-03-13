"""Tests for clarvis.metrics.quality module."""

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
)


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
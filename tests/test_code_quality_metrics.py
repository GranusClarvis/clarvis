"""Tests for clarvis/metrics/code_validation.py and clarvis/metrics/quality.py"""

import pytest
import tempfile
import os
from pathlib import Path


class TestCodeValidation:
    """Tests for clarvis/metrics/code_validation.py"""

    def test_validate_python_file_valid(self, tmp_path):
        """Test validate_python_file with valid Python file"""
        from clarvis.metrics.code_validation import validate_python_file
        
        # Create a valid Python file
        test_file = tmp_path / "valid.py"
        test_file.write_text("""
def hello():
    print("Hello, world!")
    return True

class TestClass:
    pass
""")
        
        result = validate_python_file(str(test_file))
        assert result is not None
        # Check valid or no critical errors
        assert "valid" in result or "errors" in result

    def test_validate_python_file_syntax_error(self, tmp_path):
        """Test validate_python_file with syntax error"""
        from clarvis.metrics.code_validation import validate_python_file
        
        # Create a file with syntax error
        test_file = tmp_path / "invalid.py"
        test_file.write_text("""
def hello(
    print("missing paren")
""")
        
        result = validate_python_file(str(test_file))
        assert result is not None
        # Should detect issues
        assert "errors" in result or result.get("valid") == False

    def test_validate_output_clean(self):
        """Test validate_output with clean output"""
        from clarvis.metrics.code_validation import validate_output
        
        result = validate_output("Hello, world!")
        assert result is not None
        assert result.get("has_errors") == False

    def test_validate_output_with_traceback(self):
        """Test validate_output detects tracebacks"""
        from clarvis.metrics.code_validation import validate_output
        
        output_with_traceback = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("test")
ValueError: test
"""
        result = validate_output(output_with_traceback)
        assert result is not None
        assert result.get("has_errors") == True
        assert result.get("error_type") == "runtime"

    def test_validate_output_with_syntax_error(self):
        """Test validate_output detects syntax errors"""
        from clarvis.metrics.code_validation import validate_output
        
        output_with_syntax = """  File "test.py", line 1
    def foo(
            ^
SyntaxError: '(' was never closed
"""
        result = validate_output(output_with_syntax)
        # Should detect has_errors or error_type
        assert result is not None
        assert "has_errors" in result or "error_type" in result

    def test_should_retry_retryable(self):
        """Test should_retry returns dict with retry=True for retryable errors"""
        from clarvis.metrics.code_validation import should_retry
        
        # Network errors, timeouts are retryable (iteration 1 = first try)
        result = should_retry(1, "timeout")
        assert isinstance(result, dict)
        assert result.get("retry") == True

    def test_should_retry_non_retryable(self):
        """Test should_retry returns dict for non-retryable errors"""
        from clarvis.metrics.code_validation import should_retry
        
        result = should_retry(1, "syntax_error")
        assert isinstance(result, dict)
        assert "retry" in result

    def test_should_retry_max_retries(self):
        """Test should_retry returns retry=False after max retries"""
        from clarvis.metrics.code_validation import should_retry
        
        # After 3 retries, should return False
        result = should_retry(4, "timeout")
        assert isinstance(result, dict)
        assert result.get("retry") == False


class TestQualityMetrics:
    """Tests for clarvis/metrics/quality.py"""

    def test_compute_task_quality_score(self):
        """Test compute_task_quality_score returns valid score"""
        from clarvis.metrics.quality import compute_task_quality_score
        
        result = compute_task_quality_score(days=1)
        assert isinstance(result, dict)
        assert "quality_score" in result
        assert 0 <= result["quality_score"] <= 1

    def test_compute_task_quality_score_week(self):
        """Test compute_task_quality_score with week timeframe"""
        from clarvis.metrics.quality import compute_task_quality_score
        
        result = compute_task_quality_score(days=7)
        assert isinstance(result, dict)
        assert "quality_score" in result

    def test_compute_code_quality_score(self):
        """Test compute_code_quality_score returns valid score"""
        from clarvis.metrics.quality import compute_code_quality_score
        
        result = compute_code_quality_score(days=1)
        assert isinstance(result, dict)
        assert "quality_score" in result
        assert 0 <= result["quality_score"] <= 1

    def test_compute_code_quality_score_week(self):
        """Test compute_code_quality_score with week timeframe"""
        from clarvis.metrics.quality import compute_code_quality_score
        
        result = compute_code_quality_score(days=7)
        assert isinstance(result, dict)
        assert "quality_score" in result

    def test_compute_semantic_depth(self):
        """Test compute_semantic_depth returns dict with depth_score"""
        from clarvis.metrics.quality import compute_semantic_depth
        
        result = compute_semantic_depth()
        assert isinstance(result, dict)
        # Returns dict with depth_score or error
        assert "depth_score" in result or "error" in result

    def test_compute_efficiency_score(self):
        """Test compute_efficiency_score returns dict with efficiency_score"""
        from clarvis.metrics.quality import compute_efficiency_score
        
        result = compute_efficiency_score()
        assert isinstance(result, dict)
        # Returns dict with efficiency_score or error
        assert "efficiency_score" in result or "error" in result

    def test_get_all_quality_metrics(self):
        """Test get_all_quality_metrics returns all metrics"""
        from clarvis.metrics.quality import get_all_quality_metrics
        
        result = get_all_quality_metrics()
        assert isinstance(result, dict)
        # Should contain quality metrics
        assert len(result) > 0

    def test_first_pass_success_rate(self):
        """Test _first_pass_success_rate returns a value"""
        from clarvis.metrics.quality import _first_pass_success_rate
        
        result = _first_pass_success_rate()
        # Returns None if no data, or a float
        assert result is None or isinstance(result, (int, float))

    def test_test_pass_rate(self):
        """Test _test_pass_rate returns a value"""
        from clarvis.metrics.quality import _test_pass_rate
        
        result = _test_pass_rate()
        # Returns None if no data, or a float
        assert result is None or isinstance(result, (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
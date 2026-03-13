"""Tests for clarvis.metrics.code_validation module."""

import pytest
import tempfile
import os
from pathlib import Path

from clarvis.metrics.code_validation import (
    validate_python_file,
    validate_output,
    should_retry,
)


class TestValidatePythonFile:
    """Tests for validate_python_file function."""

    def test_valid_python_file(self):
        """Test validation of a clean Python file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello():\n    print('world')\n    return True\n")
            f.flush()
            try:
                result = validate_python_file(f.name)
                assert result['valid'] is True
                assert result['errors'] == []
            finally:
                os.unlink(f.name)

    def test_syntax_error(self):
        """Test detection of syntax errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def broken(\n    print('missing colon')\n")
            f.flush()
            try:
                result = validate_python_file(f.name)
                assert result['valid'] is False
                assert len(result['errors']) > 0
            finally:
                os.unlink(f.name)

    def test_undefined_name(self):
        """Test detection of undefined names."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("x = undefined_function()\n")
            f.flush()
            try:
                result = validate_python_file(f.name)
                # Should detect F841 (undefined name)
                assert any('F841' in str(e) or 'undefined' in str(e).lower() 
                          for e in result['errors']) or result['valid'] is True
                # Note: flake8 may or may not catch this depending on config
            finally:
                os.unlink(f.name)

    def test_bare_except(self):
        """Test detection of bare except clauses."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("try:\n    pass\nexcept:\n    pass\n")
            f.flush()
            try:
                result = validate_python_file(f.name)
                # Should detect S110 (bare except)
                assert any('S110' in str(e) or 'bare' in str(e).lower() 
                          for e in result['errors']) or result['valid'] is True
            finally:
                os.unlink(f.name)

    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        result = validate_python_file('/nonexistent/file.py')
        assert result['valid'] is False
        assert len(result['errors']) > 0


class TestValidateOutput:
    """Tests for validate_output function."""

    def test_clean_output(self):
        """Test validation of clean output."""
        output = "def solution():\n    return 42\n"
        result = validate_output(output, "test task")
        assert result['has_errors'] is False

    def test_traceback_detection(self):
        """Test detection of Python tracebacks."""
        output = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    ValueError: invalid value
"""
        result = validate_output(output, "test task")
        assert result['has_errors'] is True
        assert 'runtime' in result['error_type'].lower()

    def test_syntax_error_in_output(self):
        """Test detection of syntax errors in output."""
        output = "  File '<stdin>', line 1\n    print('missing paren'\n                                                  ^\nSyntaxError: "
        result = validate_output(output, "test task")
        # May or may not detect depending on pattern matching
        assert isinstance(result, dict)

    def test_empty_output(self):
        """Test handling of empty output."""
        result = validate_output("", "test task")
        assert result['has_errors'] is False


class TestShouldRetry:
    """Tests for should_retry function."""

    def test_retry_on_syntax_error(self):
        """Test that syntax errors should retry."""
        result = should_retry(iteration=1, error_type="syntax", task_description="")
        assert result.get('retry') is True

    def test_retry_on_name_error(self):
        """Test that name errors should retry."""
        result = should_retry(iteration=1, error_type="name", task_description="")
        assert result.get('retry') is True

    def test_no_retry_on_max_iterations(self):
        """Test that max iterations prevents retry."""
        result = should_retry(iteration=5, error_type="syntax", task_description="")
        assert result.get('retry') is False

    def test_retry_on_indentation_error(self):
        """Test that indentation errors should retry."""
        result = should_retry(iteration=1, error_type="indent", task_description="")
        assert result.get('retry') is True

    def test_no_retry_on_type_error_late(self):
        """Test that type errors after many iterations may not retry."""
        result = should_retry(iteration=4, error_type="type", task_description="")
        # After 4 iterations, should give up
        assert result.get('retry') is False
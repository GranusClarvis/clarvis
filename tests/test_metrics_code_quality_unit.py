"""Unit tests for clarvis.metrics.quality — compute_code_quality_score with controlled inputs.

These tests use a temp workspace so they're fast and deterministic.
"""

import json
import os
import pytest
import tempfile
from unittest.mock import patch

from clarvis.metrics.quality import (
    compute_code_quality_score,
    _ast_structural_checks,
    _test_pass_rate,
)


class TestAstStructuralChecks:
    """Deterministic checks on the AST structural validator."""

    def test_clean_file(self):
        import ast
        code = "def foo():\n    return 1\n"
        tree = ast.parse(code)
        result = _ast_structural_checks(tree, code)
        assert result["no_bare_except"] is True
        assert result["no_star_imports"] is True
        assert result["reasonable_function_length"] is True

    def test_bare_except_detected(self):
        import ast
        code = "try:\n    pass\nexcept:\n    pass\n"
        tree = ast.parse(code)
        result = _ast_structural_checks(tree, code)
        assert result["no_bare_except"] is False

    def test_star_import_detected(self):
        import ast
        code = "from os import *\n"
        tree = ast.parse(code)
        result = _ast_structural_checks(tree, code)
        assert result["no_star_imports"] is False

    def test_io_without_try_flagged(self):
        import ast
        code = "import os\nf = open('x')\n"
        tree = ast.parse(code)
        result = _ast_structural_checks(tree, code)
        assert result["has_error_handling"] is False

    def test_io_with_try_ok(self):
        import ast
        code = "try:\n    f = open('x')\nexcept IOError:\n    pass\n"
        tree = ast.parse(code)
        result = _ast_structural_checks(tree, code)
        assert result["has_error_handling"] is True


class TestComputeCodeQualityScoreUnit:
    """Test compute_code_quality_score with a controlled temp workspace."""

    def _make_workspace(self, tmp_path, files):
        """Create a temp workspace with given {relative_path: content} files."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for name, content in files.items():
            fp = scripts_dir / name
            fp.write_text(content)
        return str(tmp_path)

    def test_clean_python_files(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "clean.py": "def hello():\n    return 'world'\n",
            "also_clean.py": "import os\ntry:\n    x = open('f')\nexcept IOError:\n    pass\n",
        })
        with patch("clarvis.metrics.quality.WORKSPACE", ws):
            result = compute_code_quality_score(days=9999)
        assert result["quality_score"] > 0.5
        assert result["files_checked"] == 2

    def test_syntax_error_file(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "broken.py": "def oops(\n    return",
        })
        with patch("clarvis.metrics.quality.WORKSPACE", ws):
            result = compute_code_quality_score(days=9999)
        # Syntax error → lint fails → lower score
        assert result["files_checked"] == 1

    def test_no_python_files(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "readme.json": '{"key": "val"}',  # .json is a code ext but not .py
        })
        with patch("clarvis.metrics.quality.WORKSPACE", ws):
            result = compute_code_quality_score(days=9999)
        assert result["quality_score"] == 0.7
        assert result.get("reason") == "no_python_files"

    def test_no_recent_files(self, tmp_path):
        ws = self._make_workspace(tmp_path, {})
        with patch("clarvis.metrics.quality.WORKSPACE", ws):
            result = compute_code_quality_score(days=0)
        assert result.get("reason") in ("no_recent_code", "no_python_files", None)


class TestTestPassRate:

    def test_from_json(self, tmp_path):
        results_file = tmp_path / "data" / "test_results.json"
        results_file.parent.mkdir(parents=True)
        results_file.write_text(json.dumps({"passed": 9, "failed": 1}))
        with patch("clarvis.metrics.quality.WORKSPACE", str(tmp_path)):
            rate = _test_pass_rate()
        assert rate == 0.9

    def test_missing_file_returns_none(self, tmp_path):
        with patch("clarvis.metrics.quality.WORKSPACE", str(tmp_path)):
            rate = _test_pass_rate()
        assert rate is None

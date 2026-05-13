"""Tests for ESR_STRUCTURE_RULE_NOT_FAILURE — code_validation errors vs advisories split.

Acceptance criteria (from QUEUE.md):
  (a) >100-line function alone → outcome=success + advisories=["function_too_long"]
  (b) >100-line function + ruff F-code → outcome=partial_success (errors present)
  (c) clean code → outcome=success

Verifies the postflight downgrade chain is broken for advisory-only files.
"""

import os
import tempfile

import pytest

from clarvis.metrics.code_validation import validate_python_file
from clarvis.cognition.metacognition import reclassify_agent_reported_success


def _write_tmp_py(content):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    f.write(content)
    f.flush()
    f.close()
    return f.name


def _long_function(n_lines=120):
    body = "\n".join([f"    x{i} = {i}" for i in range(n_lines)])
    return f"def too_long():\n{body}\n    return 0\n"


def _ruff_f_error_snippet():
    # Star import — caught by static analyzer as an `import` error type.
    return "from os import *\n\ndef ok():\n    return 1\n"


@pytest.fixture(autouse=True)
def _enable_advisory_flag(monkeypatch):
    monkeypatch.setenv("STRUCTURE_RULE_ADVISORY", "1")


# --- Case (a): long function alone -> success + advisories=[function_too_long] ---

def test_long_function_alone_is_advisory_not_error():
    src = _long_function(120)
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is True, (
            f"Long function alone must NOT mark file invalid; got errors={result['errors']}"
        )
        assert result["errors"] == []
        advisory_subtypes = [a.get("subtype") for a in result["advisories"]]
        assert "function_too_long" in advisory_subtypes
    finally:
        os.unlink(path)


def test_long_function_alone_does_not_block_success_override():
    """Episode tagged code_validation:pass (advisory-only) is rescuable."""
    # Agent self-reports success with structured reply
    output = (
        '{"tests_passed": true, "error": null, "pr_class": "A"}\n'
        "RESULT: success — feature shipped"
    )
    override, signals = reclassify_agent_reported_success(
        error_text=None,
        output_text=output,
        failure_type=None,
        tags=["code_validation:pass", "code_validation:advisory:function_too_long"],
        exit_code=0,
    )
    assert override is True, f"advisory-only must allow override; signals={signals}"
    assert signals.get("blocked_by") is None


# --- Case (b): long function + hard error -> not valid (errors present) ---

def test_long_function_plus_hard_error_marks_invalid():
    src = _long_function(120) + "\n" + _ruff_f_error_snippet()
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is False, (
            "Hard error (star import) must mark invalid even with advisory present"
        )
        assert any(e["type"] == "import" for e in result["errors"])
        advisory_subtypes = [a.get("subtype") for a in result["advisories"]]
        assert "function_too_long" in advisory_subtypes
    finally:
        os.unlink(path)


def test_long_function_plus_hard_error_blocks_success_override():
    """Episode tagged code_validation:fail (hard errors) blocks rescue."""
    output = '{"tests_passed": true, "error": null, "pr_class": "A"}'
    override, signals = reclassify_agent_reported_success(
        error_text=None,
        output_text=output,
        failure_type=None,
        tags=["code_validation:fail"],
        exit_code=0,
    )
    assert override is False
    assert signals["blocked_by"] == "tag:code_validation:fail"


# --- Case (c): clean code -> success ---

def test_clean_code_is_valid_no_advisories():
    src = "def small():\n    return 1\n"
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["advisories"] == []
    finally:
        os.unlink(path)


# --- Flag-off (legacy) behavior preserved ---

def test_flag_off_keeps_long_function_as_error(monkeypatch):
    monkeypatch.setenv("STRUCTURE_RULE_ADVISORY", "0")
    src = _long_function(120)
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        # Legacy: structure issue still in errors
        assert result["valid"] is False
        assert any(
            e.get("subtype") == "function_too_long" or "function_too_long" in str(e)
            for e in result["errors"]
        )
        assert result["advisories"] == []
    finally:
        os.unlink(path)


# --- 100/101 boundary regression (CV_FUNCTION_LENGTH_OFF_BY_ONE) ---

def _function_with_total_lines(total_lines):
    """Build a function whose total line count (def + body + return) equals total_lines.

    Layout: 1 def line + (total_lines - 2) body lines + 1 return line.
    """
    assert total_lines >= 3, "function needs at least def + 1 body + return"
    body = "\n".join([f"    x{i} = {i}" for i in range(total_lines - 2)])
    return f"def f():\n{body}\n    return 0\n"


def test_function_exactly_100_lines_is_not_flagged():
    """A function exactly 100 lines long must NOT trip the >100 gate."""
    src = _function_with_total_lines(100)
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is True
        assert result["errors"] == []
        advisory_subtypes = [a.get("subtype") for a in result["advisories"]]
        assert "function_too_long" not in advisory_subtypes, (
            f"100-line function must not be flagged; advisories={result['advisories']}"
        )
    finally:
        os.unlink(path)


def test_function_exactly_101_lines_is_flagged_as_advisory():
    """Regression: a 101-line function must trigger the advisory.

    Before the fix, length was computed as `end_lineno - lineno` (exclusive),
    so a 101-line function reported as 100 and escaped the >100 gate.
    """
    src = _function_with_total_lines(101)
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is True  # advisory mode — still valid
        advisory_subtypes = [a.get("subtype") for a in result["advisories"]]
        assert "function_too_long" in advisory_subtypes, (
            f"101-line function must be flagged; advisories={result['advisories']}"
        )
        msg = next(
            a["message"] for a in result["advisories"]
            if a.get("subtype") == "function_too_long"
        )
        assert "101" in msg, f"reported length should be 101, got: {msg}"
    finally:
        os.unlink(path)


# --- Bare-except still a hard error (correctness-impacting) ---

def test_bare_except_still_hard_error_even_with_flag():
    src = "def f():\n    try:\n        pass\n    except:\n        pass\n"
    path = _write_tmp_py(src)
    try:
        result = validate_python_file(path)
        assert result["valid"] is False
        assert any(e.get("subtype") == "bare_except" for e in result["errors"])
    finally:
        os.unlink(path)

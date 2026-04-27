"""Regression test for absolute_zero abductive prompt error fallback.

Guards against regressing the ep.get("error") or "no error message recorded"
fix in scripts/cognition/absolute_zero.py:propose_abduction. Previously, the
default-arg form (`ep.get("error", "no error message recorded")`) treated
explicit None and "" as valid values, causing failure-diagnosis prompts to
render with a blank Error: line.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401 — registers all script subdirs on sys.path

from cognition import absolute_zero


_FALLBACK = "no error message recorded"


def _failure_episode(error_value):
    return {
        "id": "ep-test",
        "task": "synthetic failure for fallback test",
        "outcome": "failure",
        "error": error_value,
        "duration_s": 3,
    }


@pytest.mark.parametrize("error_value", [None, ""])
def test_propose_abduction_uses_fallback_for_blank_error(error_value):
    """Both None and "" must fall back to the placeholder string."""
    result = absolute_zero.propose_abduction([_failure_episode(error_value)])
    assert result is not None
    assert result["type"] == "abduction"
    prompt = result["prompt"]
    assert f"Error: {_FALLBACK}" in prompt
    assert "Error: \n" not in prompt  # never render blank


def test_propose_abduction_preserves_real_error_message():
    """A non-empty error must pass through verbatim (truncated to 200 chars)."""
    msg = "ImportError: no module named foo"
    result = absolute_zero.propose_abduction([_failure_episode(msg)])
    assert result is not None
    assert f"Error: {msg}" in result["prompt"]
    assert _FALLBACK not in result["prompt"]

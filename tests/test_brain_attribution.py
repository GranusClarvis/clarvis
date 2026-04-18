"""Smoke tests for scripts/audit/brain_attribution.py."""

import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "audit"))
import brain_attribution as ba


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_tokens_filters_stopwords():
    tokens = ba._tokens("the quick brown fox is running fast")
    assert "the" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens
    assert "running" in tokens


def test_jaccard_identical():
    s = {"alpha", "beta", "gamma"}
    assert ba._jaccard(s, s) == 1.0


def test_jaccard_disjoint():
    assert ba._jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_empty():
    assert ba._jaccard(set(), {"a"}) == 0.0


def test_overlap_full():
    assert ba._overlap({"a", "b"}, {"a", "b", "c"}) == 1.0


def test_overlap_partial():
    assert ba._overlap({"a", "b"}, {"b", "c"}) == 0.5


# ---------------------------------------------------------------------------
# Per-trace attribution
# ---------------------------------------------------------------------------

def test_attribute_trace_empty():
    """An empty trace should not crash."""
    row = ba.attribute_trace({})
    assert row["block_count"] == 0
    assert row["collections"] == {}


def test_score_block_memory_id_match():
    block = {"text": "some text about testing", "memory_id": "clarvis-learnings_abc123"}
    response = "blah blah clarvis-learnings_abc123 blah"
    result = ba._score_block(block, response)
    assert result["attributed"] is True
    assert "memory_id" in result["hits"]


def test_score_block_no_match():
    block = {"text": "completely unrelated topic", "memory_id": ""}
    response = "something else entirely different domain"
    result = ba._score_block(block, response)
    assert result["score"] == 0.0


# ---------------------------------------------------------------------------
# CLI smoke tests (parse once, dispatch once)
# ---------------------------------------------------------------------------

def test_main_parses_once():
    """Verify main() calls parse_args exactly once, not twice."""
    call_count = 0
    original_build = ba.build_parser

    def counting_build():
        nonlocal call_count
        p = original_build()
        orig_parse = p.parse_args

        def counting_parse(*a, **kw):
            nonlocal call_count
            call_count += 1
            return orig_parse(*a, **kw)

        p.parse_args = counting_parse
        return p

    with patch.object(ba, "build_parser", side_effect=counting_build):
        with patch.object(ba, "cmd_summary", return_value=0) as mock_cmd:
            with patch("sys.argv", ["brain_attribution", "summary"]):
                rc = ba.main()

    assert rc == 0
    assert call_count == 1, f"parse_args called {call_count} times, expected 1"


def test_cmd_run_smoke(tmp_path):
    """cmd_run should succeed with no traces, producing empty output files."""
    attrib = tmp_path / "brain_attribution.jsonl"
    scorecard = tmp_path / "brain_collection_scorecard.json"

    with patch.object(ba, "WORKSPACE", tmp_path), \
         patch.object(ba, "TRACES_DIR", tmp_path / "traces"), \
         patch.object(ba, "ATTRIB_JSONL", attrib), \
         patch.object(ba, "SCORECARD_JSON", scorecard), \
         patch.object(ba, "EVENTS_FILE", tmp_path / "events.jsonl"), \
         patch.object(ba, "BRAIN_EVAL_LATEST", tmp_path / "latest.json"), \
         patch.object(ba, "RECALL_PRECISION_FILE", tmp_path / "rp.json"), \
         patch.object(ba, "EFFECTIVENESS_HISTORY", tmp_path / "eff.jsonl"), \
         patch.object(ba, "REPORT_FILE", tmp_path / "report.json"):
        args = types.SimpleNamespace(days=30)
        rc = ba.cmd_run(args)

    assert rc == 0
    assert attrib.exists()
    data = json.loads(scorecard.read_text())
    assert "headline" in data
    assert data["headline"]["eligible_traces"] == 0


def test_cmd_summary_no_scorecard(tmp_path):
    """cmd_summary should return 2 when no scorecard exists."""
    with patch.object(ba, "SCORECARD_JSON", tmp_path / "missing.json"):
        args = types.SimpleNamespace()
        rc = ba.cmd_summary(args)
    assert rc == 2


def test_cmd_gate_no_scorecard(tmp_path):
    """cmd_gate should return 2 when no scorecard exists."""
    with patch.object(ba, "SCORECARD_JSON", tmp_path / "missing.json"):
        args = types.SimpleNamespace()
        rc = ba.cmd_gate(args)
    assert rc == 2

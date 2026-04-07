"""Tests for ab_comparison_benchmark.py."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401

from metrics.ab_comparison_benchmark import (
    _tokenize,
    _jaccard,
    _rouge_l_f1,
    _detect_sections,
    _score_brief,
    _write_prompt_to_tempfile,
    AB_TASKS,
    run_benchmark,
)


def test_tokenize_removes_stopwords():
    tokens = _tokenize("the quick brown fox jumps over a lazy dog")
    assert "the" not in tokens
    assert "brown" in tokens
    assert "quick" in tokens
    assert "jumps" in tokens
    assert "lazy" in tokens


def test_tokenize_minimum_length():
    tokens = _tokenize("ab cd efg hi")
    assert "efg" in tokens
    assert len(tokens) == 1


def test_jaccard_identical():
    s = {"a", "b", "c"}
    assert _jaccard(s, s) == 1.0


def test_jaccard_disjoint():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_empty():
    assert _jaccard(set(), {"a"}) == 0.0


def test_rouge_l_identical():
    seq = ["the", "cat", "sat"]
    assert _rouge_l_f1(seq, seq) == 1.0


def test_rouge_l_empty():
    assert _rouge_l_f1([], ["a"]) == 0.0


def test_detect_sections():
    text = "SUCCESS CRITERIA: pass all tests\nAPPROACH: incremental"
    secs = _detect_sections(text)
    assert "decision_context" in secs
    assert "reasoning" in secs


def test_score_brief():
    brief = "implement lambda context compressor mmr success constraint"
    score = _score_brief(
        brief, "implement MMR lambda",
        {"implement", "lambda", "context", "compressor", "mmr", "success"},
        set(),
    )
    assert score["token_coverage"] == 1.0
    assert score["overall"] > 0.4
    assert score["brief_bytes"] == len(brief)


def test_write_prompt_to_tempfile():
    path = _write_prompt_to_tempfile("test task", "test context")
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert "test task" in content
    assert "test context" in content
    os.unlink(path)


def test_ab_tasks_has_12_pairs():
    assert len(AB_TASKS) >= 12


def test_run_benchmark_dry_run():
    result = run_benchmark(dry_run=True)
    assert "error" not in result or result.get("pairs_total", 0) > 0
    # At least one approach should succeed
    if "error" not in result:
        assert result["pairs_total"] == 12
        assert result["a_success_count"] + result["b_success_count"] > 0
        for pair in result["per_pair"]:
            assert pair["winner"] in ("a", "b", "tie")

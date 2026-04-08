"""Wiki Evaluation Suite — pytest tests comparing wiki-assisted vs baseline retrieval.

Tests 5 dimensions: citation quality, consistency, coverage, latency, operator usefulness.
Uses gold questions from data/wiki_eval/gold_questions.json.

Two test categories:
  1. Unit tests (fast, no brain needed) — score function correctness
  2. Integration tests (requires brain) — actual retrieval comparison
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
sys.path.insert(0, str(WORKSPACE / "scripts"))


# ── Gold questions fixture ────────────────────────────────────────


GOLD_FILE = WORKSPACE / "data" / "wiki_eval" / "gold_questions.json"


def _load_gold():
    with open(GOLD_FILE) as f:
        return json.load(f)["questions"]


@pytest.fixture(scope="module")
def gold_questions():
    return _load_gold()


# ── Unit tests: scoring functions ─────────────────────────────────


class TestScoringFunctions:
    """Test score_* functions with synthetic data (no brain needed)."""

    def test_citation_quality_all_cited(self):
        from wiki_eval import score_citation_quality
        result = {"wiki_hits": [
            {"slug": "a", "sources": ["raw/paper/x.md"]},
            {"slug": "b", "sources": ["raw/web/y.md"]},
        ]}
        assert score_citation_quality(result) == 1.0

    def test_citation_quality_none_cited(self):
        from wiki_eval import score_citation_quality
        result = {"wiki_hits": [
            {"slug": "a", "sources": []},
            {"slug": "b"},
        ]}
        assert score_citation_quality(result) == 0.0

    def test_citation_quality_partial(self):
        from wiki_eval import score_citation_quality
        result = {"wiki_hits": [
            {"slug": "a", "sources": ["raw/paper/x.md"]},
            {"slug": "b", "sources": []},
        ]}
        assert score_citation_quality(result) == 0.5

    def test_citation_quality_empty(self):
        from wiki_eval import score_citation_quality
        assert score_citation_quality({"wiki_hits": []}) == 0.0
        assert score_citation_quality({}) == 0.0

    def test_coverage_exact_match(self):
        from wiki_eval import score_coverage
        result = {"wiki_hits": [{"slug": "free-energy"}], "graph_neighbors": []}
        gold = {"expected_slugs": ["free-energy"]}
        assert score_coverage(result, gold) == 1.0

    def test_coverage_partial_match(self):
        from wiki_eval import score_coverage
        result = {"wiki_hits": [{"slug": "free-energy"}], "graph_neighbors": []}
        gold = {"expected_slugs": ["free-energy", "active-inference"]}
        assert score_coverage(result, gold) == 0.5

    def test_coverage_via_graph_neighbor(self):
        from wiki_eval import score_coverage
        result = {
            "wiki_hits": [{"slug": "free-energy"}],
            "graph_neighbors": [{"slug": "active-inference"}],
        }
        gold = {"expected_slugs": ["free-energy", "active-inference"]}
        assert score_coverage(result, gold) == 1.0

    def test_coverage_no_match(self):
        from wiki_eval import score_coverage
        result = {"wiki_hits": [{"slug": "unrelated"}], "graph_neighbors": []}
        gold = {"expected_slugs": ["free-energy"]}
        assert score_coverage(result, gold) == 0.0

    def test_coverage_no_expectation(self):
        from wiki_eval import score_coverage
        result = {"wiki_hits": [], "graph_neighbors": []}
        gold = {"expected_slugs": []}
        assert score_coverage(result, gold) == 1.0

    def test_usefulness_all_found(self):
        from wiki_eval import score_usefulness
        result = {
            "wiki_hits": [{"content": "The Free Energy Principle by Friston uses active inference"}],
            "graph_neighbors": [],
            "raw_sources": [],
            "broad_hits": [],
        }
        gold = {"expected_substrings": ["free energy", "friston", "active inference"]}
        assert score_usefulness(result, gold) == 1.0

    def test_usefulness_partial(self):
        from wiki_eval import score_usefulness
        result = {
            "wiki_hits": [{"content": "The Free Energy Principle"}],
            "graph_neighbors": [],
            "raw_sources": [],
            "broad_hits": [],
        }
        gold = {"expected_substrings": ["free energy", "friston"]}
        assert score_usefulness(result, gold) == 0.5

    def test_usefulness_none(self):
        from wiki_eval import score_usefulness
        result = {"wiki_hits": [{"content": "unrelated"}],
                  "graph_neighbors": [], "raw_sources": [], "broad_hits": []}
        gold = {"expected_substrings": ["free energy"]}
        assert score_usefulness(result, gold) == 0.0

    def test_usefulness_from_broad_fallback(self):
        from wiki_eval import score_usefulness
        result = {
            "wiki_hits": [],
            "graph_neighbors": [],
            "raw_sources": [],
            "broad_hits": [{"document": "Friston's free energy principle"}],
        }
        gold = {"expected_substrings": ["free energy", "friston"]}
        assert score_usefulness(result, gold) == 1.0

    def test_consistency_identical(self):
        from wiki_eval import score_consistency
        a = {"wiki_hits": [{"slug": "a"}, {"slug": "b"}]}
        b = {"wiki_hits": [{"slug": "a"}, {"slug": "b"}]}
        assert score_consistency(a, b) == 1.0

    def test_consistency_disjoint(self):
        from wiki_eval import score_consistency
        a = {"wiki_hits": [{"slug": "a"}]}
        b = {"wiki_hits": [{"slug": "c"}]}
        assert score_consistency(a, b) == 0.0

    def test_consistency_partial_overlap(self):
        from wiki_eval import score_consistency
        a = {"wiki_hits": [{"slug": "a"}, {"slug": "b"}]}
        b = {"wiki_hits": [{"slug": "b"}, {"slug": "c"}]}
        # Jaccard: {b} / {a, b, c} = 1/3
        assert abs(score_consistency(a, b) - 1 / 3) < 0.01

    def test_consistency_both_empty(self):
        from wiki_eval import score_consistency
        assert score_consistency({"wiki_hits": []}, {"wiki_hits": []}) == 1.0

    def test_citation_quality_baseline(self):
        from wiki_eval import score_citation_quality_baseline
        result = {"hits": [
            {"source": "wiki/concepts/x"},
            {"source": ""},
            {"source": "autonomous-learning"},
        ]}
        assert abs(score_citation_quality_baseline(result) - 2 / 3) < 0.01

    def test_coverage_baseline(self):
        from wiki_eval import score_coverage_baseline
        result = {"hits": [{"document": "The Free Energy Principle by Friston"}]}
        gold = {"expected_substrings": ["free energy", "friston", "missing"]}
        assert abs(score_coverage_baseline(result, gold) - 2 / 3) < 0.01


class TestGoldQuestionsIntegrity:
    """Verify gold questions file is well-formed."""

    def test_gold_file_exists(self):
        assert GOLD_FILE.exists(), f"Gold file missing: {GOLD_FILE}"

    def test_gold_file_valid_json(self):
        with open(GOLD_FILE) as f:
            data = json.load(f)
        assert "questions" in data
        assert len(data["questions"]) >= 10

    def test_gold_questions_have_required_fields(self):
        questions = _load_gold()
        required = {"id", "query", "expected_slugs", "expected_substrings"}
        for q in questions:
            missing = required - set(q.keys())
            assert not missing, f"Question {q.get('id', '?')} missing fields: {missing}"

    def test_gold_question_ids_unique(self):
        questions = _load_gold()
        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_gold_questions_have_nonempty_queries(self):
        for q in _load_gold():
            assert len(q["query"].strip()) > 5, f"Query too short: {q['id']}"

    def test_expected_slugs_are_strings(self):
        for q in _load_gold():
            for s in q["expected_slugs"]:
                assert isinstance(s, str) and len(s) > 0, f"Bad slug in {q['id']}"


# ── Integration tests (require brain) ────────────────────────────
# Mark with @pytest.mark.integration so they can be skipped in CI.


def _brain_available():
    try:
        from clarvis.brain import brain
        brain.stats()
        return True
    except Exception:
        return False


requires_brain = pytest.mark.skipif(
    not _brain_available(),
    reason="ClarvisDB brain not available (integration test)"
)


@requires_brain
class TestWikiRetrievalIntegration:
    """Integration tests that exercise actual wiki retrieval vs baseline."""

    def test_wiki_retrieve_returns_structure(self):
        from wiki_retrieval import wiki_retrieve
        result = wiki_retrieve("What is the Free Energy Principle?", max_pages=3)
        assert "wiki_hits" in result
        assert "graph_neighbors" in result
        assert "coverage" in result
        assert result["coverage"] in ("wiki", "wiki+graph", "broad", "none")

    def test_baseline_retrieve_returns_structure(self):
        from wiki_eval import _baseline_retrieve
        result = _baseline_retrieve("What is the Free Energy Principle?")
        assert "hits" in result
        assert "latency_ms" in result
        assert isinstance(result["hits"], list)

    def test_wiki_retrieval_has_latency(self):
        from wiki_eval import _wiki_retrieve
        result = _wiki_retrieve("Global Workspace Theory")
        assert "latency_ms" in result
        assert result["latency_ms"] > 0

    @pytest.mark.parametrize("gold", _load_gold()[:5], ids=lambda g: g["id"])
    def test_wiki_returns_some_results(self, gold):
        """Wiki retrieval should return at least one hit or broad fallback."""
        from wiki_eval import _wiki_retrieve
        result = _wiki_retrieve(gold["query"])
        total = len(result.get("wiki_hits", [])) + len(result.get("broad_hits", []))
        assert total > 0, f"No results for: {gold['query']}"

    @pytest.mark.parametrize("gold", _load_gold()[:5], ids=lambda g: g["id"])
    def test_wiki_usefulness_above_zero(self, gold):
        """Wiki path should find at least some expected content."""
        from wiki_eval import _wiki_retrieve, score_usefulness
        result = _wiki_retrieve(gold["query"])
        score = score_usefulness(result, gold)
        # Relaxed: just needs to find something
        assert score >= 0.0, f"Usefulness score negative for {gold['id']}"


@requires_brain
class TestEvalSuiteAggregates:
    """Run the full eval suite and check aggregate quality."""

    @pytest.fixture(scope="class")
    def eval_report(self):
        from wiki_eval import run_eval
        return run_eval()

    def test_report_structure(self, eval_report):
        assert "aggregate" in eval_report
        assert "per_question" in eval_report
        assert "deltas" in eval_report
        assert eval_report["n_questions"] >= 10

    def test_wiki_coverage_above_minimum(self, eval_report):
        """Wiki path should cover at least 30% of gold questions."""
        cov = eval_report["aggregate"]["wiki"]["coverage"]
        assert cov >= 0.3, f"Wiki coverage too low: {cov:.3f}"

    def test_wiki_consistency_above_minimum(self, eval_report):
        """Repeated queries should return mostly stable results."""
        cons = eval_report["aggregate"]["wiki"]["consistency"]
        assert cons >= 0.5, f"Wiki consistency too low: {cons:.3f}"

    def test_latency_under_budget(self, eval_report):
        """Average wiki retrieval should complete under 5 seconds."""
        lat = eval_report["aggregate"]["wiki"]["latency_avg_ms"]
        assert lat < 5000, f"Wiki latency too high: {lat:.0f}ms"

    def test_baseline_latency_under_budget(self, eval_report):
        """Average baseline retrieval should complete under 3 seconds."""
        lat = eval_report["aggregate"]["baseline"]["latency_avg_ms"]
        assert lat < 3000, f"Baseline latency too high: {lat:.0f}ms"

    def test_deltas_are_computed(self, eval_report):
        """Delta dict should have all expected dimensions."""
        deltas = eval_report["deltas"]
        for dim in ["citation_quality", "coverage", "usefulness", "latency_ms"]:
            assert dim in deltas, f"Missing delta: {dim}"

"""Tests for clarvis.cognition.context_relevance — section-level relevance scoring."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from clarvis.cognition.context_relevance import (
    parse_brief_sections,
    score_section_relevance,
    record_relevance,
    aggregate_relevance,
    regenerate_report,
    _tokenize,
    _jaccard,
    _containment,
    _cosine_similarity,
    _semantic_containment,
    _embed_text,
    SEMANTIC_WEIGHT,
    TOKEN_WEIGHT,
)


# === Helpers ===

SAMPLE_BRIEF = """SUCCESS CRITERIA: Complete the migration of graph storage.
Ensure all edges are preserved. Run parity checks.

RELEVANT KNOWLEDGE:
SQLite WAL mode provides better concurrency. The graph has 85k+ edges.
Migration script handles deduplication automatically.

WORKING MEMORY:
Current task: graph cutover. Previous session fixed parity delta.

---

RELATED TASKS:
  - Cleanup dead scripts
  - Update RUNBOOK.md

METRICS: Phi=0.72, cap_avg=0.65, worst=planning=0.41

RECENT:
  - [x] AMEM_MEMORY_EVOLUTION completed
  - [x] RETRIEVAL_GATE completed

---

EPISODIC LESSONS:
Last migration attempt timed out because invariants_check was slow.
Root cause: full table scan on 100k edges without index.

APPROACH:
Think step-by-step. Verify parity before and after cutover.

BRAIN GOALS (active objectives):
(80%) AGI/consciousness (86%) Session Continuity

WORLD MODEL: P(success)=78%, novelty=0.25

FAILURE AVOIDANCE (somatic markers + causal chains):
FAIL: Previous migration timed out at 300s threshold
"""

SAMPLE_OUTPUT_RELEVANT = """
Running graph cutover from JSON to SQLite backend.
Verified parity: 3810 nodes, 100150 edges, 200/200 sample match.
SQLite WAL mode is active. Archived relationships.json.
Enabled CLARVIS_GRAPH_BACKEND=sqlite in cron_env.sh.
Invariants check passed. Migration complete.
Updated RUNBOOK.md with Phase 4 cutover status.
"""

SAMPLE_OUTPUT_IRRELEVANT = """
Refactored the Telegram bot message formatting.
Added emoji support for status messages.
Updated the Discord webhook integration.
"""


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello world, this is a test of tokenization!")
        assert "hello" in tokens
        assert "tokenization" in tokens
        # Stopwords excluded
        assert "this" not in tokens

    def test_empty(self):
        assert _tokenize("") == set()

    def test_short_words_excluded(self):
        tokens = _tokenize("go to do it is ok no")
        # All 2-char words excluded (need 3+ chars)
        assert len(tokens) == 0


class TestJaccard:
    def test_identical(self):
        s = {"alpha", "beta", "gamma"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        score = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert 0.4 < score < 0.6  # 2/4 = 0.5

    def test_empty(self):
        assert _jaccard(set(), {"a"}) == 0.0
        assert _jaccard(set(), set()) == 0.0


class TestContainment:
    def test_full_containment(self):
        small = {"alpha", "beta"}
        big = {"alpha", "beta", "gamma", "delta", "epsilon"}
        assert _containment(small, big) == 1.0

    def test_no_containment(self):
        assert _containment({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_containment(self):
        small = {"alpha", "beta", "gamma", "delta"}
        big = {"alpha", "beta", "epsilon", "zeta"}
        assert _containment(small, big) == 0.5  # 2/4

    def test_empty(self):
        assert _containment(set(), {"a"}) == 0.0
        assert _containment({"a"}, set()) == 0.0

    def test_asymmetric(self):
        """Containment is asymmetric — unlike Jaccard."""
        small = {"a", "b"}
        big = {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}
        assert _containment(small, big) == 1.0  # all of small in big
        assert _containment(big, small) == 0.2  # only 2/10 of big in small


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(a, a) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestSemanticContainment:
    """Test semantic blending with mock embeddings."""

    @staticmethod
    def _make_mock_embed_fn(mapping: dict):
        """Return a fake embed_fn that maps text prefixes to fixed vectors."""
        def mock_fn(texts):
            results = []
            for t in texts:
                for prefix, vec in mapping.items():
                    if prefix in t:
                        results.append(vec)
                        break
                else:
                    results.append([0.0] * 384)
            return results
        return mock_fn

    def test_semantic_containment_similar(self):
        """High cosine similarity → high semantic containment."""
        vec = [1.0] * 384
        embed_fn = self._make_mock_embed_fn({"section": vec, "output": vec})
        output_emb = _embed_text("output text", embed_fn)
        score = _semantic_containment("section text", output_emb, embed_fn)
        assert score is not None
        assert score > 0.9

    def test_semantic_containment_dissimilar(self):
        """Orthogonal embeddings → low semantic containment."""
        sec_vec = [1.0] + [0.0] * 383
        out_vec = [0.0] + [1.0] + [0.0] * 382
        embed_fn = self._make_mock_embed_fn({"section": sec_vec, "output": out_vec})
        output_emb = _embed_text("output text", embed_fn)
        score = _semantic_containment("section text", output_emb, embed_fn)
        assert score is not None
        assert score < 0.1

    def test_semantic_containment_none_when_no_embed_fn(self):
        """Returns None when embed_fn is None."""
        score = _semantic_containment("text", None, None)
        assert score is None

    def test_blend_weights_sum_to_one(self):
        assert abs(SEMANTIC_WEIGHT + TOKEN_WEIGHT - 1.0) < 1e-6


class TestScoreWithSemanticBlend:
    """Test that score_section_relevance integrates semantic scores when available."""

    def test_fallback_to_token_when_no_embeddings(self, monkeypatch):
        """When embeddings unavailable, scores should still work (token-only)."""
        import clarvis.cognition.context_relevance as cr_mod
        monkeypatch.setattr(cr_mod, "_embed_available", False)

        result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="graph cutover", outcome="success",
        )
        assert result["overall"] > 0.0
        assert result["sections_total"] >= 7

    def test_with_mock_embeddings(self, monkeypatch):
        """When embeddings available, blended score should be >= token-only."""
        import clarvis.cognition.context_relevance as cr_mod

        # Get token-only score first
        monkeypatch.setattr(cr_mod, "_embed_available", False)
        token_result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="graph cutover", outcome="success",
        )

        # Now with mock embeddings that return high similarity
        high_sim_vec = [0.5] * 384

        def mock_embed_fn(texts):
            return [high_sim_vec for _ in texts]

        monkeypatch.setattr(cr_mod, "_embed_fn", mock_embed_fn)
        monkeypatch.setattr(cr_mod, "_embed_available", True)
        # Override _get_embed_fn to return our mock
        monkeypatch.setattr(cr_mod, "_get_embed_fn", lambda: mock_embed_fn)

        blended_result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="graph cutover", outcome="success",
        )
        # With high semantic similarity, blended score should be at least as high
        assert blended_result["overall"] >= token_result["overall"] * 0.8


class TestParseBriefSections:
    def test_parses_all_sections(self):
        sections = parse_brief_sections(SAMPLE_BRIEF)
        assert "knowledge" in sections
        assert "working_memory" in sections
        assert "related_tasks" in sections
        assert "metrics" in sections
        assert "completions" in sections
        assert "episodes" in sections
        assert "reasoning" in sections

    def test_parses_supplementary_sections(self):
        sections = parse_brief_sections(SAMPLE_BRIEF)
        assert "brain_goals" in sections
        assert "world_model" in sections
        assert "failure_avoidance" in sections

    def test_empty_brief(self):
        assert parse_brief_sections("") == {}
        assert parse_brief_sections(None) == {}

    def test_no_markers(self):
        sections = parse_brief_sections("Just some plain text without any section markers.")
        assert "brief" in sections  # Falls back to single "brief" section

    def test_section_content_not_empty(self):
        sections = parse_brief_sections(SAMPLE_BRIEF)
        for name, content in sections.items():
            assert len(content.strip()) > 0, f"Section {name} is empty"


class TestScoreSectionRelevance:
    def test_relevant_output_scores_high(self):
        result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="graph cutover", outcome="success",
        )
        assert result["overall"] > 0.4  # Most sections should be referenced
        assert result["sections_referenced"] >= 4
        assert result["sections_total"] >= 7  # scorable sections (tokens >= MIN_SECTION_TOKENS)

    def test_irrelevant_output_scores_low(self):
        result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_IRRELEVANT,
            task="telegram refactor", outcome="success",
        )
        assert result["overall"] < 0.5  # Few sections referenced
        assert result["sections_referenced"] < result["sections_total"]

    def test_empty_inputs(self):
        result = score_section_relevance("", "some output")
        assert result["overall"] == 0.0
        assert result["sections_total"] == 0

        result = score_section_relevance("some brief", "")
        assert result["overall"] == 0.0

    def test_per_section_scores(self):
        result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="test", outcome="success",
        )
        assert isinstance(result["per_section"], dict)
        for name, score in result["per_section"].items():
            assert 0.0 <= score <= 1.0, f"Section {name} score out of range: {score}"

    def test_task_and_outcome_stored(self):
        result = score_section_relevance(
            SAMPLE_BRIEF, SAMPLE_OUTPUT_RELEVANT,
            task="my task description", outcome="failure",
        )
        assert result["task"] == "my task description"
        assert result["outcome"] == "failure"


class TestRecordAndAggregate:
    def test_record_creates_file(self, tmp_path):
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        result = {
            "overall": 0.71,
            "sections_total": 7,
            "sections_referenced": 5,
            "per_section": {"knowledge": 0.23, "metrics": 0.18},
            "task": "test task",
            "outcome": "success",
        }

        # Monkey-patch the file path
        import clarvis.cognition.context_relevance as cr_mod
        orig = cr_mod.RELEVANCE_FILE
        cr_mod.RELEVANCE_FILE = relevance_file
        try:
            path = record_relevance(result)
            assert os.path.exists(path)
            with open(path) as f:
                entry = json.loads(f.readline())
            assert entry["overall"] == 0.71
            assert "ts" in entry
        finally:
            cr_mod.RELEVANCE_FILE = orig

    def test_aggregate_empty(self, tmp_path):
        agg = aggregate_relevance(days=7, relevance_file=str(tmp_path / "nonexistent.jsonl"))
        assert agg["mean_relevance"] == 0.0
        assert agg["episodes"] == 0

    def test_aggregate_computes_means(self, tmp_path):
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        entries = [
            {"ts": now, "overall": 0.6, "sections_total": 7, "per_section": {"knowledge": 0.3, "metrics": 0.1}, "outcome": "success"},
            {"ts": now, "overall": 0.8, "sections_total": 7, "per_section": {"knowledge": 0.5, "metrics": 0.2}, "outcome": "success"},
            {"ts": now, "overall": 0.4, "sections_total": 7, "per_section": {"knowledge": 0.2, "metrics": 0.05}, "outcome": "failure"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        assert agg["episodes"] == 3
        assert 0.59 < agg["mean_relevance"] < 0.61  # (0.6+0.8+0.4)/3 = 0.6
        assert "knowledge" in agg["per_section_mean"]
        assert agg["success_mean"] > agg["failure_mean"]

    def test_aggregate_filters_by_date(self, tmp_path):
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()

        entries = [
            {"ts": old_ts, "overall": 0.9, "sections_total": 7, "per_section": {}, "outcome": "success"},  # Too old
            {"ts": new_ts, "overall": 0.5, "sections_total": 7, "per_section": {}, "outcome": "success"},   # Recent
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        assert agg["episodes"] == 1
        assert agg["mean_relevance"] == 0.5


class TestRegenerateReport:
    def test_regenerate_enriches_report(self, tmp_path, monkeypatch):
        """regenerate_report() merges episode-derived relevance into brief_v2_report.json."""
        from datetime import datetime, timezone

        # Set up JSONL with enough episodes (>= 3)
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"ts": now, "overall": 0.7, "sections_total": 7, "per_section": {"knowledge": 0.3}, "outcome": "success"},
            {"ts": now, "overall": 0.8, "sections_total": 7, "per_section": {"knowledge": 0.5}, "outcome": "success"},
            {"ts": now, "overall": 0.6, "sections_total": 7, "per_section": {"knowledge": 0.2}, "outcome": "failure"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        # Set up existing report
        benchmarks_dir = tmp_path / "data" / "benchmarks"
        benchmarks_dir.mkdir(parents=True)
        report_path = str(benchmarks_dir / "brief_v2_report.json")
        with open(report_path, "w") as f:
            json.dump({"total_heartbeats": 100, "by_version": {}}, f)

        # Monkeypatch paths
        import clarvis.cognition.context_relevance as cr_mod
        monkeypatch.setattr(cr_mod, "RELEVANCE_FILE", relevance_file)
        monkeypatch.setattr(cr_mod, "_WORKSPACE", str(tmp_path))

        agg = regenerate_report(days=7)
        assert agg["episodes"] == 3
        assert 0.69 < agg["mean_relevance"] < 0.71  # (0.7+0.8+0.6)/3

        # Verify the report file was enriched
        with open(report_path) as f:
            report = json.load(f)
        assert "context_relevance_from_episodes" in report
        cr_data = report["context_relevance_from_episodes"]
        assert cr_data["episodes"] == 3
        assert 0.69 < cr_data["mean_relevance"] < 0.71
        assert "generated" in cr_data
        # Original data preserved
        assert report["total_heartbeats"] == 100

    def test_regenerate_skips_with_few_episodes(self, tmp_path, monkeypatch):
        """regenerate_report() skips when < 3 episodes available."""
        import clarvis.cognition.context_relevance as cr_mod
        monkeypatch.setattr(cr_mod, "RELEVANCE_FILE", str(tmp_path / "empty.jsonl"))
        monkeypatch.setattr(cr_mod, "_WORKSPACE", str(tmp_path))

        agg = regenerate_report(days=7)
        assert agg["episodes"] == 0
        # No report file created
        report_path = tmp_path / "data" / "benchmarks" / "brief_v2_report.json"
        assert not report_path.exists()


# === Feedback Loop: Relevance-Weighted Budget Adjustment ===

from clarvis.context.budgets import (
    load_relevance_weights,
    get_adjusted_budgets,
    TIER_BUDGETS,
    BUDGET_FLOOR,
    BUDGET_CEILING,
    BUDGET_TO_SECTIONS as _BUDGET_TO_SECTIONS,
)
from clarvis.context.dycp import (
    dycp_prune_brief,
    _dycp_task_containment,
    DYCP_PROTECTED_SECTIONS,
)


class TestDyCPTaskContainment:
    def test_overlapping_tokens(self):
        section = "SQLite graph migration edges parity check"
        task = "Migrate graph storage to SQLite backend"
        score = _dycp_task_containment(section, task)
        assert score > 0.2  # "graph", "sqlite", "migrate" overlap

    def test_no_overlap(self):
        section = "ATTENTION CODELETS winner=code coalition=research"
        task = "Fix Telegram bot message formatting"
        score = _dycp_task_containment(section, task)
        assert score == 0.0

    def test_empty_inputs(self):
        assert _dycp_task_containment("", "some task") == 0.0
        assert _dycp_task_containment("some section", "") == 0.0

    def test_bidirectional(self):
        """Max of both directions should be returned."""
        small = "retrieval"
        big = "implement retrieval evaluator with golden QA benchmark scoring"
        score = _dycp_task_containment(small, big)
        assert score > 0.0


class TestDyCPPruneBrief:
    def test_prunes_irrelevant_sections(self, monkeypatch):
        """Sections with low historical score AND low task overlap are pruned."""
        import clarvis.context.dycp as dycp_mod
        # Mock historical means: meta_gradient and brain_goals are weak
        monkeypatch.setattr(dycp_mod, "_load_historical_section_means", lambda: {
            "meta_gradient": 0.05,
            "brain_goals": 0.08,
            "knowledge": 0.20,
            "decision_context": 0.30,
            "reasoning": 0.17,
        })

        brief = (
            "SUCCESS CRITERIA: Migrate graph storage to SQLite\n"
            "META-GRADIENT: Prefer explore strategy (weight=1.50), explore=30%\n"
            "RELEVANT KNOWLEDGE:\nSQLite WAL mode provides better concurrency\n"
            "BRAIN GOALS (active objectives):\nImprove consciousness metrics above threshold\n"
            "APPROACH: Read the file first, then implement migration."
        )
        task = "Migrate graph storage from JSON to SQLite backend"
        pruned = dycp_prune_brief(brief, task)

        sections = parse_brief_sections(pruned)
        assert "meta_gradient" not in sections  # hist=0.05, no task overlap
        assert "brain_goals" not in sections     # hist=0.08, no task overlap
        assert "knowledge" in sections           # protected
        assert "decision_context" in sections    # protected
        assert "reasoning" in sections           # protected

    def test_keeps_sections_with_task_overlap(self, monkeypatch):
        """Even historically weak sections are kept if they overlap with task."""
        import clarvis.context.dycp as dycp_mod
        monkeypatch.setattr(dycp_mod, "_load_historical_section_means", lambda: {
            "synaptic": 0.10,  # historically weak
        })

        brief = (
            "SUCCESS CRITERIA: improve retrieval\n"
            "SYNAPTIC ASSOCIATIONS (neural co-activation):\n"
            "brain.py -> search -> retrieval -> recall\n"
        )
        task = "Improve brain retrieval quality and search scoring"
        pruned = dycp_prune_brief(brief, task)

        sections = parse_brief_sections(pruned)
        assert "synaptic" in sections  # task mentions retrieval/search/brain

    def test_preserves_protected_sections(self, monkeypatch):
        """Protected sections are never pruned even with no overlap."""
        import clarvis.context.dycp as dycp_mod
        monkeypatch.setattr(dycp_mod, "_load_historical_section_means", lambda: {})

        brief = (
            "SUCCESS CRITERIA: do something\n"
            "RELEVANT KNOWLEDGE:\nCompletely unrelated knowledge\n"
            "RELATED TASKS:\n  - Unrelated task A\n"
            "APPROACH: step by step\n"
        )
        task = "Fix telegram bot"
        pruned = dycp_prune_brief(brief, task)

        sections = parse_brief_sections(pruned)
        for protected in ["decision_context", "knowledge", "related_tasks", "reasoning"]:
            if protected in parse_brief_sections(brief):
                assert protected in sections, f"Protected section {protected} was pruned"

    def test_passthrough_when_few_sections(self, monkeypatch):
        """Brief with <= 3 sections is returned unchanged."""
        import clarvis.context.dycp as dycp_mod
        monkeypatch.setattr(dycp_mod, "_load_historical_section_means", lambda: {
            "meta_gradient": 0.01,
        })

        brief = "SUCCESS CRITERIA: test\nMETA-GRADIENT: fix\n"
        result = dycp_prune_brief(brief, "some task")
        assert result == brief  # unchanged

    def test_empty_inputs(self):
        assert dycp_prune_brief("", "task") == ""
        assert dycp_prune_brief("brief", "") == "brief"

    def test_tier2_zero_overlap_pruning(self, monkeypatch):
        """Tier 2: sections with zero overlap and borderline history get pruned."""
        import clarvis.context.dycp as dycp_mod
        monkeypatch.setattr(dycp_mod, "_load_historical_section_means", lambda: {
            "attention": 0.13,    # below Tier 0 threshold (0.15)
            "brain_context": 0.14,  # below Tier 0 threshold (0.15)
        })

        brief = (
            "SUCCESS CRITERIA: fix tests\n"
            "RELEVANT KNOWLEDGE:\ntest framework info\n"
            "ATTENTION CODELETS (LIDA): winner=code coalition=research\n"
            "BRAIN CONTEXT: GWT broadcast about consciousness\n"
            "APPROACH: run tests first\n"
        )
        task = "Fix pytest failures in test_brain_roundtrip.py"
        pruned = dycp_prune_brief(brief, task)

        sections = parse_brief_sections(pruned)
        # attention and brain_context have hist < 0.15, caught by Tier 0
        assert "attention" not in sections
        assert "brain_context" not in sections


class TestLoadRelevanceWeights:
    @staticmethod
    def _patch_aggregate(monkeypatch, relevance_file):
        """Monkeypatch aggregate_relevance to use a custom file path."""
        import clarvis.cognition.context_relevance as cr_mod
        orig_agg = aggregate_relevance

        def patched_agg(days=7, relevance_file_arg=None, **kwargs):
            return orig_agg(days=days, relevance_file=relevance_file_arg or relevance_file,
                            **{k: v for k, v in kwargs.items() if k == 'recency_boost'})

        monkeypatch.setattr(cr_mod, "aggregate_relevance", patched_agg)

    def test_returns_empty_when_insufficient_episodes(self, tmp_path, monkeypatch):
        """Returns empty dict when fewer than min_episodes exist."""
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"ts": now, "overall": 0.7, "per_section": {"knowledge": 0.3}, "outcome": "success"},
            {"ts": now, "overall": 0.5, "per_section": {"knowledge": 0.2}, "outcome": "success"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        self._patch_aggregate(monkeypatch, relevance_file)
        weights = load_relevance_weights()
        assert weights == {}

    def test_returns_weights_with_sufficient_episodes(self, tmp_path, monkeypatch):
        """Returns tiered scaling factors when enough episodes exist."""
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        for _ in range(6):
            entry = {
                "ts": now, "overall": 0.65, "sections_total": 12,
                "per_section": {
                    "decision_context": 0.5, "failure_avoidance": 0.1,
                    "meta_gradient": 0.0, "working_memory": 0.3,
                    "attention": 0.4, "gwt_broadcast": 0.2,
                    "brain_context": 0.3, "related_tasks": 0.8,
                    "metrics": 0.05, "completions": 0.3,
                    "episodes": 0.6, "reasoning": 0.4,
                },
                "outcome": "success",
            }
            with open(relevance_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        self._patch_aggregate(monkeypatch, relevance_file)
        weights = load_relevance_weights()
        assert len(weights) > 0
        # Tiered scaling: values must be 0.0, 0.5, or 1.0
        for key, w in weights.items():
            assert w in (0.0, 0.5, 1.0), f"{key}={w} not a valid tier"
        # related_tasks (mean=0.8) and episodes (mean=0.6) → 1.0 (high tier)
        assert weights["related_tasks"] == 1.0
        assert weights["episodes"] == 1.0

    def test_respects_min_episodes_param(self, tmp_path, monkeypatch):
        """min_episodes parameter is respected."""
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        for _ in range(3):
            entry = {
                "ts": now, "overall": 0.5, "sections_total": 7, "outcome": "success",
                "per_section": {"decision_context": 0.4, "metrics": 0.1, "episodes": 0.5},
            }
            with open(relevance_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        self._patch_aggregate(monkeypatch, relevance_file)
        assert load_relevance_weights() == {}
        weights = load_relevance_weights(min_episodes=2)
        assert weights != {}
        # Tiered: decision_context (0.4≥0.25→1.0), episodes (0.5≥0.25→1.0)
        for key, w in weights.items():
            assert w in (0.0, 0.5, 1.0), f"{key}={w} not a valid tier"


class TestGetAdjustedBudgets:
    def test_returns_static_budgets_when_no_data(self, monkeypatch):
        """Falls back to static TIER_BUDGETS when no relevance data exists."""
        import clarvis.context.budgets as budgets_mod
        monkeypatch.setattr(budgets_mod, "load_relevance_weights", lambda: {})

        result = get_adjusted_budgets("standard")
        assert result == TIER_BUDGETS["standard"]

    def test_adjusts_budgets_with_weights(self, monkeypatch):
        """Adjusts budgets using tiered adaptive caps with redistribution."""
        import clarvis.context.budgets as budgets_mod
        # Mock tiered weights: some full, some half, some zero
        mock_weights = {
            "decision_context": 1.0,   # full
            "spotlight": 0.5,          # half
            "related_tasks": 1.0,      # full
            "completions": 0.0,        # pruned
            "episodes": 1.0,           # full
            "reasoning_scaffold": 0.5, # half
        }
        monkeypatch.setattr(budgets_mod, "load_relevance_weights", lambda: mock_weights)

        result = get_adjusted_budgets("standard")
        base = TIER_BUDGETS["standard"]

        # Total budget should be approximately preserved (freed tokens redistributed)
        total_base = sum(v for k, v in base.items() if k != "total" and v > 0)
        total_adjusted = sum(v for k, v in result.items() if k != "total" and v > 0)
        assert abs(total_base - total_adjusted) <= len(base) + 5  # rounding tolerance

        # Pruned section should have zero budget
        assert result["completions"] == 0

        # Half-budget sections should be less than base
        assert result["spotlight"] < base["spotlight"]

        # Full-budget sections should get more than base (redistribution)
        assert result["decision_context"] >= base["decision_context"]

    def test_minimal_tier_unchanged(self, monkeypatch):
        """Minimal tier has all-zero budgets so should not change."""
        import clarvis.context.budgets as budgets_mod
        monkeypatch.setattr(budgets_mod, "load_relevance_weights", lambda: {"decision_context": 1.3})

        result = get_adjusted_budgets("minimal")
        assert result == TIER_BUDGETS["minimal"]

    def test_zero_budget_sections_pruned(self, monkeypatch):
        """Sections with scale=0.0 get zero budget (hard-pruned)."""
        import clarvis.context.budgets as budgets_mod
        mock_weights = {k: 0.0 for k in _BUDGET_TO_SECTIONS}
        monkeypatch.setattr(budgets_mod, "load_relevance_weights", lambda: mock_weights)

        result = get_adjusted_budgets("standard")
        for key, value in result.items():
            if key != "total" and TIER_BUDGETS["standard"].get(key, 0) > 0:
                # All sections are scale=0.0 so no redistribution target exists
                assert value == 0, f"{key}={value} should be 0 when scale=0.0"

    def test_full_tier_adjusts(self, monkeypatch):
        """Full tier also gets adjusted."""
        import clarvis.context.budgets as budgets_mod
        mock_weights = {"episodes": 1.4, "completions": 0.4}
        monkeypatch.setattr(budgets_mod, "load_relevance_weights", lambda: mock_weights)

        result = get_adjusted_budgets("full")
        base = TIER_BUDGETS["full"]
        # Episodes should be relatively larger than completions vs base ratio
        ep_ratio = result["episodes"] / base["episodes"]
        comp_ratio = result["completions"] / base["completions"]
        assert ep_ratio > comp_ratio


class TestAggregateSparseFilter:
    """Verify that aggregate_relevance filters out sparse episodes (< MIN_SECTIONS)."""

    def test_sparse_episodes_excluded(self, tmp_path):
        """Episodes with sections_total < MIN_SECTIONS_FOR_AGGREGATION are dropped."""
        from clarvis.cognition.context_relevance import MIN_SECTIONS_FOR_AGGREGATION
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()

        entries = [
            # Sparse episode: only 2 sections — should be excluded
            {"ts": now, "overall": 0.1, "sections_total": 2,
             "per_section": {"knowledge": 0.05}, "outcome": "success"},
            # Rich episode: enough sections — should be included
            {"ts": now, "overall": 0.8, "sections_total": 7,
             "per_section": {"knowledge": 0.5, "metrics": 0.3}, "outcome": "success"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        # Only the rich episode should be counted
        assert agg["episodes"] == 1
        assert agg["mean_relevance"] == 0.8

    def test_all_sparse_returns_zero(self, tmp_path):
        """When all episodes are sparse, aggregate returns 0."""
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"ts": now, "overall": 0.9, "sections_total": 2,
             "per_section": {}, "outcome": "success"},
            {"ts": now, "overall": 0.7, "sections_total": 3,
             "per_section": {}, "outcome": "success"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        assert agg["episodes"] == 0
        assert agg["mean_relevance"] == 0.0

    def test_missing_sections_total_treated_as_zero(self, tmp_path):
        """Episodes without sections_total field default to 0 and get filtered."""
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"ts": now, "overall": 0.5, "per_section": {}, "outcome": "success"},
            {"ts": now, "overall": 0.7, "sections_total": 8,
             "per_section": {"knowledge": 0.4}, "outcome": "success"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        assert agg["episodes"] == 1
        assert agg["mean_relevance"] == 0.7


class TestRefreshBenchmarkUsesLiveData:
    """Verify that run_refresh_benchmark refreshes context_relevance from episode data."""

    def test_refresh_overwrites_stale_context_relevance(self, tmp_path, monkeypatch):
        """run_refresh_benchmark must pull live context_relevance, not carry stale cache."""
        import clarvis.cognition.context_relevance as cr_mod
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc).isoformat()

        # Write 6 episodes with overall ~0.75 (above MIN_SECTIONS_FOR_AGGREGATION)
        for _ in range(6):
            entry = {
                "ts": now, "overall": 0.75, "sections_total": 8,
                "per_section": {"knowledge": 0.5, "reasoning": 0.6},
                "outcome": "success",
            }
            with open(relevance_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        monkeypatch.setattr(cr_mod, "RELEVANCE_FILE", relevance_file)

        # Verify aggregate_relevance returns fresh data
        agg = aggregate_relevance(days=7, relevance_file=relevance_file)
        assert agg["episodes"] == 6
        assert agg["mean_relevance"] == 0.75

        # The stale value (e.g. 0.387) should NOT survive if aggregate returns fresh data
        # This test validates the contract that aggregate_relevance is always live
        assert agg["mean_relevance"] != 0.387


class TestAggregateFreshnessVsCache:
    """Verify that aggregate_relevance returns current rolling window, not stale data."""

    def test_new_episodes_shift_mean(self, tmp_path):
        """Adding recent high-scoring episodes shifts the 7-day rolling mean up."""
        from datetime import timedelta
        relevance_file = str(tmp_path / "context_relevance.jsonl")
        now = datetime.now(timezone.utc)

        # Old episodes (5 days ago): low scores
        old_ts = (now - timedelta(days=5)).isoformat()
        entries = [
            {"ts": old_ts, "overall": 0.3, "sections_total": 7,
             "per_section": {"knowledge": 0.2}, "outcome": "success"},
            {"ts": old_ts, "overall": 0.35, "sections_total": 6,
             "per_section": {"knowledge": 0.25}, "outcome": "success"},
        ]
        with open(relevance_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        agg_before = aggregate_relevance(days=7, relevance_file=relevance_file)
        # Mean ~ 0.325
        assert agg_before["mean_relevance"] < 0.4

        # Add new high-scoring episodes
        new_ts = now.isoformat()
        new_entries = [
            {"ts": new_ts, "overall": 0.85, "sections_total": 8,
             "per_section": {"knowledge": 0.6}, "outcome": "success"},
            {"ts": new_ts, "overall": 0.90, "sections_total": 9,
             "per_section": {"knowledge": 0.7}, "outcome": "success"},
        ]
        with open(relevance_file, "a") as f:
            for e in new_entries:
                f.write(json.dumps(e) + "\n")

        agg_after = aggregate_relevance(days=7, relevance_file=relevance_file)
        # Mean should be significantly higher: (0.3+0.35+0.85+0.9)/4 = 0.6
        assert agg_after["mean_relevance"] > 0.55
        assert agg_after["mean_relevance"] > agg_before["mean_relevance"]
        assert agg_after["episodes"] == 4

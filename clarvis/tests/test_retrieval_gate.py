"""Tests for clarvis.brain.retrieval_gate — Heuristic 3-tier retrieval routing.

Covers: keyword matching, tag classification, tier thresholds, edge cases,
        dry_run helper, and RetrievalTier dataclass.
"""

import pytest
from clarvis.brain.retrieval_gate import (
    classify_retrieval,
    dry_run,
    RetrievalTier,
    _extract_tag,
    _LIGHT_COLLECTIONS,
    _DEEP_COLLECTIONS,
)


# ---------------------------------------------------------------------------
# RetrievalTier dataclass
# ---------------------------------------------------------------------------

class TestRetrievalTier:
    def test_to_dict_fields(self):
        tier = RetrievalTier(
            tier="LIGHT_RETRIEVAL", reason="test",
            collections=["a", "b"], n_results=3, graph_expand=False,
        )
        d = tier.to_dict()
        assert d == {
            "tier": "LIGHT_RETRIEVAL",
            "reason": "test",
            "collections": ["a", "b"],
            "n_results": 3,
            "graph_expand": False,
        }

    def test_defaults(self):
        tier = RetrievalTier(tier="NO_RETRIEVAL", reason="x")
        assert tier.collections == []
        assert tier.n_results == 0
        assert tier.graph_expand is False


# ---------------------------------------------------------------------------
# _extract_tag helper
# ---------------------------------------------------------------------------

class TestExtractTag:
    def test_extracts_tag(self):
        assert _extract_tag("[BACKUP] Run daily backup") == "BACKUP"

    def test_no_tag(self):
        assert _extract_tag("Fix the cron job") is None

    def test_tag_with_leading_whitespace(self):
        assert _extract_tag("  [CLEANUP] Sweep old logs") == "CLEANUP"

    def test_lowercase_not_matched(self):
        # Tags must be uppercase + digits + underscores
        assert _extract_tag("[lowercase] task") is None

    def test_tag_with_numbers(self):
        assert _extract_tag("[PHASE2_TASK] something") == "PHASE2_TASK"


# ---------------------------------------------------------------------------
# NO_RETRIEVAL classification
# ---------------------------------------------------------------------------

class TestNoRetrieval:
    """Tasks that should be classified as NO_RETRIEVAL."""

    def test_empty_string(self):
        result = classify_retrieval("")
        assert result.tier == "NO_RETRIEVAL"
        assert result.reason == "empty task"
        assert result.collections == []
        assert result.n_results == 0

    def test_none_input(self):
        result = classify_retrieval(None)
        assert result.tier == "NO_RETRIEVAL"
        assert result.reason == "empty task"

    def test_whitespace_only(self):
        result = classify_retrieval("   \n\t  ")
        assert result.tier == "NO_RETRIEVAL"
        assert result.reason == "empty task"

    @pytest.mark.parametrize("task", [
        "[BACKUP] Run backup_daily.sh and verify",
        "[CLEANUP] Rotate old logs",
        "[GRAPH_COMPACTION] Run weekly compaction",
        "[WATCHDOG] Check stale processes",
        "[HEALTH] Quick health check",
        "[CRON_SHELLCHECK_AUDIT] Run ShellCheck on cron scripts",
    ])
    def test_no_retrieval_tags(self, task):
        result = classify_retrieval(task)
        assert result.tier == "NO_RETRIEVAL"
        assert "maintenance tag:" in result.reason

    @pytest.mark.parametrize("task,expected_keyword", [
        ("Run backup for today's data", "backup"),
        ("cleanup old temp files", "cleanup"),
        ("vacuum the chromadb collections", "vacuum"),
        ("Run graph compaction on data/", "graph compaction"),
        ("Fix log rot issue in cron", "log rot"),
        ("Fix cron_watchdog.sh timeout", "watchdog"),
        ("Execute health_monitor checks", "health_monitor"),
        ("Run shellcheck on scripts", "shellcheck"),
        ("Dead script sweep", "dead script"),
        ("Fix dream_engine crash", "dream_engine"),
        ("Run garbage collect task", "garbage collect"),
        ("Checkpoint the graph", "checkpoint"),
        ("Format code style properly", "format"),
    ])
    def test_no_retrieval_keywords(self, task, expected_keyword):
        result = classify_retrieval(task)
        assert result.tier == "NO_RETRIEVAL", f"Expected NO_RETRIEVAL for: {task}"
        assert "maintenance keyword:" in result.reason

    def test_no_retrieval_case_insensitive(self):
        result = classify_retrieval("BACKUP daily data NOW")
        assert result.tier == "NO_RETRIEVAL"

    def test_no_retrieval_has_zero_collections(self):
        result = classify_retrieval("[BACKUP] test")
        assert result.collections == []
        assert result.n_results == 0
        assert result.graph_expand is False


# ---------------------------------------------------------------------------
# DEEP_RETRIEVAL classification
# ---------------------------------------------------------------------------

class TestDeepRetrieval:
    """Tasks that should be classified as DEEP_RETRIEVAL."""

    @pytest.mark.parametrize("task", [
        "[RESEARCH_DISCOVERY] Research: MemOS paper review",
        "[STRATEGIC_AUDIT] Quarterly strategy audit",
        "[EVOLUTION_ANALYSIS] Analyze heartbeat evolution",
        "[AUTONOMY_SCORE_INVESTIGATION] Investigate autonomy dip",
        "[SEMANTIC_BRIDGE] Cross-collection bridging",
    ])
    def test_deep_retrieval_tags(self, task):
        result = classify_retrieval(task)
        assert result.tier == "DEEP_RETRIEVAL"
        assert "research/design tag:" in result.reason
        assert result.collections == _DEEP_COLLECTIONS
        assert result.n_results == 10
        assert result.graph_expand is True

    def test_deep_single_keyword(self):
        """Single deep keyword → DEEP with n_results=7, no graph expand."""
        result = classify_retrieval("Investigate the API timeout issue")
        assert result.tier == "DEEP_RETRIEVAL"
        assert "deep keyword:" in result.reason
        assert result.n_results == 7
        assert result.graph_expand is False
        assert result.collections == _DEEP_COLLECTIONS

    def test_deep_multi_keyword(self):
        """Two or more deep keywords → DEEP with n_results=10, graph expand."""
        result = classify_retrieval("Research and design a new architecture for caching")
        assert result.tier == "DEEP_RETRIEVAL"
        assert "multi-signal deep:" in result.reason
        assert result.n_results == 10
        assert result.graph_expand is True

    @pytest.mark.parametrize("task", [
        "Research the arXiv paper on consciousness",
        "Analyze root cause of regression in brain recall",
        "Design strategy for multi-hop retrieval",
        "Survey literature on AGI self-model approaches",
    ])
    def test_deep_multi_signal_examples(self, task):
        result = classify_retrieval(task)
        assert result.tier == "DEEP_RETRIEVAL"
        assert result.n_results >= 7

    def test_deep_has_all_ten_collections(self):
        result = classify_retrieval("[RESEARCH_DISCOVERY] Paper review")
        assert len(result.collections) == 10

    def test_consciousness_keyword(self):
        result = classify_retrieval("Improve phi consciousness metric")
        assert result.tier == "DEEP_RETRIEVAL"

    def test_agi_keyword(self):
        result = classify_retrieval("AGI readiness assessment")
        assert result.tier == "DEEP_RETRIEVAL"


# ---------------------------------------------------------------------------
# LIGHT_RETRIEVAL classification (default tier)
# ---------------------------------------------------------------------------

class TestLightRetrieval:
    """Tasks that fall through to the default LIGHT_RETRIEVAL tier."""

    @pytest.mark.parametrize("task", [
        "Fix the login button CSS",
        "Add type annotations to brain.py",
        "Wire up the new endpoint",
        "Refactor the cost tracker output",
        "[SOME_UNKNOWN_TAG] Implement feature X",
        "Update the Telegram bot message handler",
    ])
    def test_light_retrieval_default(self, task):
        result = classify_retrieval(task)
        assert result.tier == "LIGHT_RETRIEVAL", f"Expected LIGHT for: {task}"
        assert result.reason == "default: scoped implementation"
        assert result.collections == _LIGHT_COLLECTIONS
        assert result.n_results == 3
        assert result.graph_expand is False

    def test_light_has_three_collections(self):
        result = classify_retrieval("Add a new test file")
        assert len(result.collections) == 3
        assert "clarvis-learnings" in result.collections
        assert "clarvis-procedures" in result.collections
        assert "clarvis-episodes" in result.collections


# ---------------------------------------------------------------------------
# Priority: NO_RETRIEVAL overrides DEEP keywords
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    """NO_RETRIEVAL check runs before DEEP, so maintenance + deep signals → NO_RETRIEVAL."""

    def test_maintenance_tag_overrides_deep_keywords(self):
        # Has BACKUP tag (NO_RETRIEVAL) AND "research" keyword (DEEP)
        result = classify_retrieval("[BACKUP] Research-related backup task")
        assert result.tier == "NO_RETRIEVAL"

    def test_maintenance_keyword_overrides_deep(self):
        # "cleanup" triggers NO_RETRIEVAL before "design" triggers DEEP
        result = classify_retrieval("Cleanup old research design docs")
        assert result.tier == "NO_RETRIEVAL"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_very_long_query(self):
        """Very long task text should still classify without error."""
        long_text = "Implement " + "feature " * 5000
        result = classify_retrieval(long_text)
        assert result.tier in ("NO_RETRIEVAL", "LIGHT_RETRIEVAL", "DEEP_RETRIEVAL")

    def test_special_characters(self):
        result = classify_retrieval("Fix bug #1234 — unicode: àéîõü 中文 🚀")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_newlines_in_task(self):
        result = classify_retrieval("Fix the bug\nthat causes\ncrashes")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_only_tag_no_description(self):
        result = classify_retrieval("[BACKUP]")
        assert result.tier == "NO_RETRIEVAL"

    def test_word_boundary_prevents_partial_match(self):
        """'garbage collection' has no \\b after 'collect' → not NO_RETRIEVAL."""
        result = classify_retrieval("Run garbage collection")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_word_boundary_log_rotation(self):
        """'Log rotation' has no \\b after 'rot' → not NO_RETRIEVAL."""
        result = classify_retrieval("Log rotation needed")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_format_keyword_triggers_no_retrieval(self):
        """'format' is a NO_RETRIEVAL keyword."""
        result = classify_retrieval("Format the output nicely")
        assert result.tier == "NO_RETRIEVAL"

    def test_single_word(self):
        result = classify_retrieval("test")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_deep_tag_exact_match_required(self):
        """Partial tag match should not trigger deep retrieval tag path."""
        result = classify_retrieval("[RESEARCH] some task")
        # "RESEARCH" is not in _DEEP_RETRIEVAL_TAGS (it's RESEARCH_DISCOVERY)
        # but "research" IS a deep keyword pattern
        assert result.tier == "DEEP_RETRIEVAL"
        assert "deep keyword:" in result.reason  # keyword path, not tag path


# ---------------------------------------------------------------------------
# dry_run helper
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_returns_list(self):
        tasks = [
            "[BACKUP] Run backup",
            "Fix the login flow",
            "[RESEARCH_DISCOVERY] Paper review",
        ]
        results = dry_run(tasks)
        assert len(results) == 3

    def test_dry_run_structure(self):
        results = dry_run(["test task"])
        r = results[0]
        assert "task" in r
        assert "tier" in r
        assert "reason" in r
        assert "n_results" in r
        assert "collections" in r  # count, not list
        assert "graph_expand" in r

    def test_dry_run_truncates_task(self):
        long_task = "x" * 200
        results = dry_run([long_task])
        assert len(results[0]["task"]) == 80

    def test_dry_run_empty_list(self):
        assert dry_run([]) == []

    def test_dry_run_classifies_correctly(self):
        results = dry_run(["[BACKUP] test", "[RESEARCH_DISCOVERY] test", "fix bug"])
        assert results[0]["tier"] == "NO_RETRIEVAL"
        assert results[1]["tier"] == "DEEP_RETRIEVAL"
        assert results[2]["tier"] == "LIGHT_RETRIEVAL"

    def test_dry_run_collections_is_count(self):
        results = dry_run(["[RESEARCH_DISCOVERY] test"])
        assert results[0]["collections"] == 10  # len(_DEEP_COLLECTIONS)

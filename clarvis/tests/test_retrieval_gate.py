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
    """Tag-based NO_RETRIEVAL is authoritative; keyword conflicts escalate to LIGHT."""

    def test_maintenance_tag_overrides_deep_keywords(self):
        # Tag is authoritative — [BACKUP] tag wins even with "research" keyword
        result = classify_retrieval("[BACKUP] Research-related backup task")
        assert result.tier == "NO_RETRIEVAL"
        assert "maintenance tag:" in result.reason

    def test_maintenance_keyword_plus_deep_keyword_escalates(self):
        # Keyword conflict: "cleanup" (NO) + "research"/"design" (DEEP) → LIGHT
        result = classify_retrieval("Cleanup old research design docs")
        assert result.tier == "LIGHT_RETRIEVAL"
        assert "conflict:" in result.reason

    def test_pure_maintenance_keyword_no_deep(self):
        # No deep signal → still NO_RETRIEVAL
        result = classify_retrieval("Cleanup old temp files from /tmp")
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
# Conflict resolution: maintenance keyword + deep signal → LIGHT
# ---------------------------------------------------------------------------

class TestConflictResolution:
    """When maintenance keywords co-occur with deep signals, escalate to LIGHT."""

    @pytest.mark.parametrize("task", [
        "Research why the health_monitor is failing",
        "Investigate health check failures in production",
        "Analyze the backup failure root cause",
        "Design a format for the API response",
        "Investigate why cleanup is timing out",
        "Research the dream_engine architecture for redesign",
        "Diagnose the watchdog false alarms",
    ])
    def test_maintenance_keyword_with_deep_signal_escalates(self, task):
        result = classify_retrieval(task)
        assert result.tier == "LIGHT_RETRIEVAL", (
            f"Expected LIGHT (conflict resolution) for: {task}, got {result.tier}: {result.reason}"
        )
        assert "conflict:" in result.reason

    @pytest.mark.parametrize("task", [
        "Run backup for today's data",
        "Execute health_monitor checks",
        "Run shellcheck on scripts",
        "cleanup old temp files",
        "vacuum the chromadb collections",
    ])
    def test_pure_maintenance_stays_no_retrieval(self, task):
        """Maintenance keyword WITHOUT deep signal → NO_RETRIEVAL (unchanged)."""
        result = classify_retrieval(task)
        assert result.tier == "NO_RETRIEVAL", (
            f"Expected NO_RETRIEVAL for pure maintenance: {task}, got {result.tier}"
        )

    def test_tag_overrides_even_with_deep_keywords(self):
        """Tag-based NO_RETRIEVAL is authoritative, even with deep keywords."""
        result = classify_retrieval("[BACKUP] Research and analyze backup strategy")
        assert result.tier == "NO_RETRIEVAL"
        assert "maintenance tag:" in result.reason


# ---------------------------------------------------------------------------
# Adversarial / ambiguous inputs
# ---------------------------------------------------------------------------

class TestAdversarialInputs:
    """Adversarial and tricky inputs that could confuse the classifier."""

    def test_all_keywords_mixed(self):
        """Task with both maintenance AND deep keywords everywhere."""
        task = "Research backup strategy, design cleanup plan, investigate lint audit"
        result = classify_retrieval(task)
        # "backup" matches NO, but "research"+"design"+"investigate"+"audit" are DEEP
        assert result.tier == "LIGHT_RETRIEVAL"
        assert "conflict:" in result.reason

    def test_maintenance_keyword_in_quotes(self):
        """Keyword inside quoted string should still match (regex doesn't know quotes)."""
        result = classify_retrieval('Fix the error message: "backup failed"')
        assert result.tier == "NO_RETRIEVAL"

    def test_keyword_as_variable_name(self):
        """Keyword that's actually a variable name in code context."""
        result = classify_retrieval("Rename the `format` variable to `formatter`")
        assert result.tier == "NO_RETRIEVAL"  # "format" matches

    def test_negated_keyword(self):
        """'no backup needed' still matches 'backup' — regex can't parse negation."""
        result = classify_retrieval("This task needs no backup at all")
        assert result.tier == "NO_RETRIEVAL"  # known limitation

    def test_tag_case_sensitivity(self):
        """Tags must be uppercase; lowercase tag falls through to keyword matching."""
        result = classify_retrieval("[backup] run the backup")
        # [backup] is lowercase → _extract_tag returns None
        # but "backup" keyword still matches
        assert result.tier == "NO_RETRIEVAL"
        assert "maintenance keyword:" in result.reason

    def test_multiple_tags_only_first_extracted(self):
        """Only the first [TAG] is extracted."""
        result = classify_retrieval("[RESEARCH_DISCOVERY] [BACKUP] mixed signals")
        assert result.tier == "DEEP_RETRIEVAL"
        assert "research/design tag:" in result.reason

    def test_tag_in_middle_of_text_ignored(self):
        """Tags only match at start of text (after stripping)."""
        result = classify_retrieval("Fix the [BACKUP] related issue")
        # No tag extracted (not at start), "backup" keyword matches but
        # no deep signals → NO_RETRIEVAL
        assert result.tier == "NO_RETRIEVAL"

    def test_empty_tag_brackets(self):
        """Empty brackets should not extract a tag."""
        result = classify_retrieval("[] Fix something")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_regex_special_chars_in_input(self):
        """Input with regex metacharacters should not cause errors."""
        result = classify_retrieval("Fix regex: (foo|bar)+ [a-z]* (?:test)")
        assert result.tier == "LIGHT_RETRIEVAL"

    def test_very_short_ambiguous(self):
        """Single ambiguous word."""
        result = classify_retrieval("plan")
        assert result.tier == "DEEP_RETRIEVAL"
        assert "deep keyword: plan" in result.reason

    def test_why_question_is_deep(self):
        """'why' triggers investigation/deep retrieval."""
        result = classify_retrieval("Why does the test fail?")
        assert result.tier == "DEEP_RETRIEVAL"

    def test_audit_without_maintenance_context(self):
        """'audit' alone triggers DEEP, not NO_RETRIEVAL."""
        result = classify_retrieval("Audit the API permissions model")
        assert result.tier == "DEEP_RETRIEVAL"

    def test_shellcheck_audit_conflict(self):
        """'shellcheck' (NO) + 'audit' (DEEP) → conflict → LIGHT."""
        result = classify_retrieval("Run shellcheck audit on all scripts")
        assert result.tier == "LIGHT_RETRIEVAL"
        assert "conflict:" in result.reason


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

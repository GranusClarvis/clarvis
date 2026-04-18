"""Unit tests for clarvis.heartbeat.error_classifier.

Covers: classify_error(), _match_keywords(), ERROR_RULES coverage.
No external I/O — pure logic tests.
"""

import pytest
from clarvis.heartbeat.error_classifier import classify_error, _match_keywords, ERROR_RULES


# ---------------------------------------------------------------------------
# _match_keywords
# ---------------------------------------------------------------------------

class TestMatchKeywords:
    def test_returns_hit_count_when_above_threshold(self):
        assert _match_keywords("importerror in module foo", ["importerror"], 1) == 1

    def test_returns_zero_when_below_threshold(self):
        assert _match_keywords("importerror in module foo", ["importerror", "dll load failed"], 2) == 0

    def test_counts_multiple_hits(self):
        text = "importerror: no module named foo, cannot import name bar"
        assert _match_keywords(text, ["importerror", "no module named", "cannot import name"], 1) == 3

    def test_no_hits_returns_zero(self):
        assert _match_keywords("everything is fine", ["importerror", "dll load failed"], 1) == 0

    def test_empty_text(self):
        assert _match_keywords("", ["importerror"], 1) == 0

    def test_empty_keywords(self):
        assert _match_keywords("importerror", [], 1) == 0

    def test_threshold_two_with_two_hits(self):
        text = "chromadb embedding failure"
        assert _match_keywords(text, ["chromadb", "embedding", "brain.store"], 2) == 2

    def test_threshold_two_with_one_hit(self):
        text = "chromadb is fine"
        assert _match_keywords(text, ["chromadb", "embedding", "brain.store"], 2) == 0


# ---------------------------------------------------------------------------
# classify_error — timeout
# ---------------------------------------------------------------------------

class TestClassifyErrorTimeout:
    def test_exit_code_124_returns_timeout(self):
        err_type, evidence = classify_error(124, "some output")
        assert err_type == "timeout"
        assert "124" in evidence

    def test_exit_code_124_ignores_output(self):
        err_type, _ = classify_error(124, "importerror traceback here")
        assert err_type == "timeout"


# ---------------------------------------------------------------------------
# classify_error — import_error
# ---------------------------------------------------------------------------

class TestClassifyErrorImportError:
    def test_importerror_keyword(self):
        err_type, evidence = classify_error(1, "ImportError: No module named 'foo'")
        assert err_type == "import_error"

    def test_modulenotfounderror(self):
        err_type, _ = classify_error(1, "ModuleNotFoundError: No module named 'bar'")
        assert err_type == "import_error"

    def test_cannot_import_name(self):
        err_type, _ = classify_error(1, "cannot import name 'Baz' from 'qux'")
        assert err_type == "import_error"

    def test_dll_load_failed(self):
        err_type, _ = classify_error(1, "DLL load failed while importing _ssl")
        assert err_type == "import_error"


# ---------------------------------------------------------------------------
# classify_error — data_missing
# ---------------------------------------------------------------------------

class TestClassifyErrorDataMissing:
    def test_single_keyword_below_threshold(self):
        # data_missing requires min_hits=2, so a single keyword doesn't match
        err_type, _ = classify_error(1, "FileNotFoundError: config.json")
        assert err_type == "action"  # falls through — only 1 keyword hit

    def test_two_keywords_match(self):
        err_type, _ = classify_error(1, "FileNotFoundError: no such file or directory")
        assert err_type == "data_missing"  # "filenotfounderror" + "no such file" = 2 hits

    def test_json_and_file_not_found(self):
        err_type, _ = classify_error(1, "json.decoder.JSONDecodeError: file not found in data")
        assert err_type == "data_missing"

    def test_keyerror_with_data_not_found(self):
        err_type, _ = classify_error(1, "KeyError: 'field' — data not found in collection")
        assert err_type == "data_missing"

    def test_filenotfounderror_no_such_file(self):
        # "filenotfounderror" + "no such file" = 2 hits
        err_type, _ = classify_error(1, "filenotfounderror: no such file")
        assert err_type == "data_missing"


# ---------------------------------------------------------------------------
# classify_error — external_dep
# ---------------------------------------------------------------------------

class TestClassifyErrorExternalDep:
    def test_connection_error(self):
        err_type, _ = classify_error(1, "requests.exceptions.ConnectionError: Failed to connect\nurllib error")
        assert err_type == "external_dep"

    def test_http_429(self):
        err_type, _ = classify_error(1, "HTTP 429 rate limit exceeded, retry after 60s")
        assert err_type == "external_dep"

    def test_ssl_certificate(self):
        err_type, _ = classify_error(1, "ssl certificate verify failed, certificate expired")
        assert err_type == "external_dep"


# ---------------------------------------------------------------------------
# classify_error — memory (brain/chromadb)
# ---------------------------------------------------------------------------

class TestClassifyErrorMemory:
    def test_chromadb_embedding(self):
        err_type, _ = classify_error(1, "chromadb error: embedding dimension mismatch")
        assert err_type == "memory"

    def test_brain_store(self):
        err_type, _ = classify_error(1, "brain.store failed: collection 'clarvis-learnings' error")
        assert err_type == "memory"

    def test_recall_failed(self):
        err_type, _ = classify_error(1, "recall failed: vector search returned empty, onnx error")
        assert err_type == "memory"


# ---------------------------------------------------------------------------
# classify_error — planning
# ---------------------------------------------------------------------------

class TestClassifyErrorPlanning:
    def test_task_selector_queue(self):
        err_type, _ = classify_error(1, "task_selector: queue.md parse error")
        assert err_type == "planning"

    def test_no_tasks(self):
        err_type, _ = classify_error(1, "preflight: no tasks available, queue empty today")
        assert err_type == "planning"


# ---------------------------------------------------------------------------
# classify_error — logic_bug
# ---------------------------------------------------------------------------

class TestClassifyErrorLogicBug:
    def test_assertion_error(self):
        err_type, _ = classify_error(1, "AssertionError: expected 5 but got 3")
        assert err_type == "logic_bug"

    def test_type_error(self):
        err_type, _ = classify_error(1, "TypeError: unsupported operand type(s)")
        assert err_type == "logic_bug"

    def test_index_error(self):
        err_type, _ = classify_error(1, "IndexError: list index out of range")
        assert err_type == "logic_bug"


# ---------------------------------------------------------------------------
# classify_error — system
# ---------------------------------------------------------------------------

class TestClassifyErrorSystem:
    def test_permission_denied(self):
        err_type, _ = classify_error(1, "Permission denied: /etc/shadow")
        assert err_type == "system"

    def test_oom_killed(self):
        err_type, _ = classify_error(1, "Process killed: OOM killer invoked")
        assert err_type == "system"

    def test_command_not_found(self):
        err_type, _ = classify_error(1, "bash: foobar: command not found")
        assert err_type == "system"


# ---------------------------------------------------------------------------
# classify_error — action sub-types
# ---------------------------------------------------------------------------

class TestClassifyErrorActionSubtypes:
    def test_validation_error(self):
        err_type, _ = classify_error(1, "validation error: invalid schema, pydantic error")
        assert err_type == "action.validation"

    def test_param_missing(self):
        err_type, _ = classify_error(1, "TypeError: foo() missing required positional argument: 'bar'")
        # logic_bug matches first because "typeerror" is in logic_bug with min_hits=1
        assert err_type == "logic_bug"

    def test_param_missing_pure(self):
        err_type, _ = classify_error(1, "missing required argument: 'bar'")
        assert err_type == "action.param_missing"

    def test_api_error(self):
        err_type, _ = classify_error(1, "api error: bad request from openrouter endpoint")
        assert err_type == "action.api_error"

    def test_race_condition(self):
        err_type, _ = classify_error(1, "lock file exists, resource busy, try again later, stale lock")
        assert err_type == "action.race_condition"


# ---------------------------------------------------------------------------
# classify_error — default fallback
# ---------------------------------------------------------------------------

class TestClassifyErrorDefault:
    def test_unknown_error_returns_action(self):
        err_type, evidence = classify_error(1, "something completely unknown happened")
        assert err_type == "action"
        assert "default" in evidence

    def test_none_output(self):
        err_type, evidence = classify_error(1, None)
        assert err_type == "action"
        assert "default" in evidence

    def test_empty_output(self):
        err_type, evidence = classify_error(1, "")
        assert err_type == "action"
        assert "default" in evidence

    def test_exit_code_zero_with_no_keywords(self):
        # Unusual: exit 0 but classify_error called anyway
        err_type, _ = classify_error(0, "all good")
        assert err_type == "action"


# ---------------------------------------------------------------------------
# classify_error — text truncation
# ---------------------------------------------------------------------------

class TestClassifyErrorTruncation:
    def test_only_last_3000_chars_checked(self):
        # Put keyword at the start (beyond 3000-char window), padding after
        padding = "x" * 4000
        text = "importerror at startup" + padding
        # "importerror" is in the first 22 chars, but the function takes [-3000:]
        # so it will be truncated away
        err_type, _ = classify_error(1, text)
        assert err_type == "action"  # keyword was truncated

    def test_keyword_in_last_3000_chars_matches(self):
        padding = "x" * 4000
        text = padding + "importerror at startup"
        err_type, _ = classify_error(1, text)
        assert err_type == "import_error"


# ---------------------------------------------------------------------------
# ERROR_RULES structure validation
# ---------------------------------------------------------------------------

class TestErrorRulesStructure:
    def test_all_rules_have_three_elements(self):
        for rule in ERROR_RULES:
            assert len(rule) == 3, f"Rule {rule[0]} should have 3 elements"

    def test_all_categories_are_strings(self):
        for category, keywords, min_hits in ERROR_RULES:
            assert isinstance(category, str)
            assert isinstance(keywords, list)
            assert isinstance(min_hits, int)
            assert min_hits >= 1

    def test_all_keywords_are_lowercase(self):
        for category, keywords, _ in ERROR_RULES:
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' in {category} should be lowercase"

    def test_no_duplicate_categories(self):
        categories = [r[0] for r in ERROR_RULES]
        assert len(categories) == len(set(categories)), "Duplicate category names found"

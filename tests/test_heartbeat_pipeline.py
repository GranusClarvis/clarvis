"""Tests for heartbeat_preflight.py and heartbeat_postflight.py.

Covers: attention scoring helpers, task verification, episode encoding helpers,
confidence recording helpers, error classification, and completeness computation.
All external I/O (brain, episodic memory, file system) is mocked.
"""

import json
import os
import sys
import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(
    os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
    "scripts",
))


# ---------------------------------------------------------------------------
# Preflight tests
# ---------------------------------------------------------------------------

class TestMakePreflightResult:
    """_make_preflight_result returns a well-formed default dict."""

    def test_returns_dict_with_required_keys(self):
        from heartbeat_preflight import _make_preflight_result
        result = _make_preflight_result()
        assert isinstance(result, dict)
        for key in ("status", "task", "task_section", "task_salience",
                     "context_brief", "confidence_tier", "chain_id", "timings"):
            assert key in result, f"Missing key: {key}"

    def test_default_values_are_sane(self):
        from heartbeat_preflight import _make_preflight_result
        result = _make_preflight_result()
        assert result["status"] == "ok"
        assert result["task"] is None
        assert result["task_salience"] == 0.0
        assert result["confidence_tier"] == "HIGH"
        assert result["timings"] == {}


class TestVerifyTaskExecutable:
    """_verify_task_executable validates task format, file refs, and locks."""

    def test_well_formed_tagged_task_passes_format(self, monkeypatch):
        from heartbeat_preflight import _verify_task_executable
        # Disable lock check
        monkeypatch.setattr(
            "heartbeat_preflight._check_lock_conflict", lambda: []
        )
        result = _verify_task_executable(
            "[REFACTOR_FOO] Refactor the foo module to improve readability and reduce complexity"
        )
        assert result["checks_passed"] >= 2  # format + lock pass (file refs = 0, so that passes too)
        assert result["passed"] is True

    def test_short_task_fails_format(self, monkeypatch):
        from heartbeat_preflight import _verify_task_executable
        monkeypatch.setattr(
            "heartbeat_preflight._check_lock_conflict", lambda: []
        )
        result = _verify_task_executable("fix it")
        assert result["passed"] is False
        assert "too short" in result["reason"]

    def test_missing_file_refs_detected(self, monkeypatch):
        from heartbeat_preflight import _verify_task_executable
        monkeypatch.setattr(
            "heartbeat_preflight._check_lock_conflict", lambda: []
        )
        result = _verify_task_executable(
            "[FIX] Fix bug in scripts/nonexistent_script_xyz.py that causes crash"
        )
        assert "nonexistent_script_xyz.py" in str(result["missing_files"])


class TestFormatProcHint:
    """format_proc_hint formats procedure matches for prompt injection."""

    def test_formats_steps_with_success_rate(self):
        from heartbeat_preflight import format_proc_hint
        proc = {
            "steps": ["Read the file", "Edit the function", "Run tests"],
            "success_rate": 0.85,
        }
        hint = format_proc_hint(proc)
        assert "PROCEDURAL MEMORY HIT" in hint
        assert "85%" in hint
        assert "1. Read the file" in hint
        assert "2. Edit the function" in hint
        assert "3. Run tests" in hint

    def test_returns_empty_for_none(self):
        from heartbeat_preflight import format_proc_hint
        assert format_proc_hint(None) == ""

    def test_returns_empty_for_no_steps(self):
        from heartbeat_preflight import format_proc_hint
        assert format_proc_hint({"steps": []}) == ""


class TestFormatMemoryHint:
    """_format_memory_hint tags hints correctly based on metadata."""

    def test_dream_tag(self):
        from heartbeat_preflight import _format_memory_hint
        mem = {"document": "counterfactual scenario", "metadata": {"tags": "dream"}, "collection": ""}
        assert "[DREAM]" in _format_memory_hint(mem)

    def test_research_tag(self):
        from heartbeat_preflight import _format_memory_hint
        mem = {"document": "paper findings", "metadata": {"source": "research_session"}, "collection": ""}
        assert "[RESEARCH]" in _format_memory_hint(mem)

    def test_episode_tag(self):
        from heartbeat_preflight import _format_memory_hint
        mem = {"document": "task outcome", "metadata": {}, "collection": "clarvis-episodes"}
        assert "[EPISODE]" in _format_memory_hint(mem)

    def test_default_learning_tag(self):
        from heartbeat_preflight import _format_memory_hint
        mem = {"document": "general insight", "metadata": {}, "collection": "clarvis-learnings"}
        assert "[LEARNING]" in _format_memory_hint(mem)

    def test_truncates_long_documents(self):
        from heartbeat_preflight import _format_memory_hint
        mem = {"document": "x" * 200, "metadata": {}, "collection": ""}
        hint = _format_memory_hint(mem)
        # Document is truncated to 120 chars
        assert len(hint) < 200


# ---------------------------------------------------------------------------
# Postflight tests
# ---------------------------------------------------------------------------

class TestClassifyError:
    """classify_error maps exit codes and output text to error categories."""

    def test_timeout_exit_code(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(124, "")
        assert etype == "timeout"
        assert "124" in evidence

    def test_import_error_detected(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(1, "ModuleNotFoundError: No module named 'foo'")
        assert etype == "import_error"

    def test_data_missing_detected(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(1, "FileNotFoundError: No such file or directory: '/tmp/data.json'")
        assert etype == "data_missing"

    def test_logic_bug_detected(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(1, "TypeError: unsupported operand type(s) for +: 'int' and 'str'")
        assert etype == "logic_bug"

    def test_external_dep_detected(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(1, "ConnectionError: Failed to connect\nHTTPError: 502 Bad Gateway")
        assert etype == "external_dep"

    def test_default_action_when_no_match(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, evidence = classify_error(1, "something went wrong but no keywords match")
        assert etype == "action"
        assert "default" in evidence

    def test_memory_error_detected(self):
        from clarvis.heartbeat.error_classifier import classify_error
        etype, _ = classify_error(1, "ChromaDB collection error: embedding dimension mismatch\nchroma failed")
        assert etype == "memory"

    def test_priority_order_import_before_logic(self):
        """import_error comes before logic_bug in priority order."""
        from clarvis.heartbeat.error_classifier import classify_error
        # Both import and logic keywords present — import should win (checked first)
        output = "ImportError: cannot import name 'foo'\nTypeError: bad operand"
        etype, _ = classify_error(1, output)
        assert etype == "import_error"


class TestComputeCompleteness:
    """_compute_completeness calculates postflight stage completion ratio."""

    def test_all_stages_ok(self):
        from heartbeat_postflight import _compute_completeness
        timings = {"confidence": 0.1, "reasoning": 0.2, "episode": 0.3, "total": 0.6}
        attempted, ok, failed, completeness = _compute_completeness(timings, [])
        assert attempted == 3  # excludes "total"
        assert ok == 3
        assert failed == 0
        assert completeness == 1.0

    def test_some_stages_failed(self):
        from heartbeat_postflight import _compute_completeness
        timings = {"confidence": 0.1, "reasoning": 0.2, "episode": 0.3}
        errors = ["confidence", "episode"]
        attempted, ok, failed, completeness = _compute_completeness(timings, errors)
        assert attempted == 3
        assert failed == 2
        assert ok == 1
        assert abs(completeness - 1 / 3) < 0.01

    def test_empty_timings(self):
        from heartbeat_postflight import _compute_completeness
        _, _, _, completeness = _compute_completeness({}, [])
        assert completeness == 1.0  # 0/0 → 1.0 by convention


class TestComputePromptQuality:
    """_compute_prompt_quality scores prompt output quality heuristically."""

    def test_success_with_tests_passing(self):
        from heartbeat_postflight import _compute_prompt_quality
        output = "Running tests...\n32 passed in 1.44s\nAll tests pass successfully!"
        q = _compute_prompt_quality("success", output, 120)
        assert q is not None
        assert q >= 0.7  # base 0.5 + len bonus + pass keyword + test+pass bonus

    def test_success_with_errors(self):
        from heartbeat_postflight import _compute_prompt_quality
        output = "Done but error in secondary check\nTraceback (most recent call last):"
        q = _compute_prompt_quality("success", output, 60)
        assert q is not None
        assert q < 0.6  # penalty for error/traceback

    def test_timeout_returns_low(self):
        from heartbeat_postflight import _compute_prompt_quality
        assert _compute_prompt_quality("timeout", "", 300) == 0.1

    def test_failure_returns_zero(self):
        from heartbeat_postflight import _compute_prompt_quality
        assert _compute_prompt_quality("failure", "crash", 10) == 0.0


class TestBuildPostflightCtx:
    """_build_postflight_ctx builds shared context from execution results."""

    def test_success_exit_code_zero(self, tmp_path):
        from heartbeat_postflight import _build_postflight_ctx
        output_file = str(tmp_path / "output.txt")
        with open(output_file, "w") as f:
            f.write("Task completed successfully")
        preflight = {"task": "Fix the bug", "task_section": "P1", "task_salience": 0.8}
        ctx = _build_postflight_ctx(0, output_file, preflight, 120)
        assert ctx["task_status"] == "success"
        assert ctx["error_type"] is None
        assert "successfully" in ctx["output_text"]

    def test_timeout_exit_code_124(self, tmp_path):
        from heartbeat_postflight import _build_postflight_ctx
        output_file = str(tmp_path / "output.txt")
        with open(output_file, "w") as f:
            f.write("timed out")
        preflight = {"task": "Long task", "task_section": "P1"}
        ctx = _build_postflight_ctx(124, output_file, preflight, 600)
        assert ctx["task_status"] == "timeout"
        assert ctx["error_type"] == "timeout"

    def test_failure_with_classification(self, tmp_path):
        from heartbeat_postflight import _build_postflight_ctx
        output_file = str(tmp_path / "output.txt")
        with open(output_file, "w") as f:
            f.write("ModuleNotFoundError: No module named 'missing_lib'")
        preflight = {"task": "Import task", "task_section": "P1"}
        ctx = _build_postflight_ctx(1, output_file, preflight, 30)
        assert ctx["task_status"] == "failure"
        assert ctx["error_type"] == "import_error"

    def test_crash_guard(self, tmp_path):
        from heartbeat_postflight import _build_postflight_ctx
        output_file = str(tmp_path / "output.txt")
        with open(output_file, "w") as f:
            f.write("segfault")
        preflight = {"task": "Crash task", "crash_guard": True, "crash_duration": 3}
        ctx = _build_postflight_ctx(1, output_file, preflight, 3)
        assert ctx["task_status"] == "crash"
        assert ctx["error_type"] == "crash"


class TestMatchKeywords:
    """_match_keywords counts keyword hits against threshold."""

    def test_single_hit_sufficient(self):
        from clarvis.heartbeat.error_classifier import _match_keywords
        hits = _match_keywords("importerror: no module named foo", ["importerror"], 1)
        assert hits >= 1

    def test_below_threshold_returns_zero(self):
        from clarvis.heartbeat.error_classifier import _match_keywords
        hits = _match_keywords("some text", ["importerror", "modulenotfounderror"], 2)
        assert hits == 0

    def test_multiple_hits(self):
        from clarvis.heartbeat.error_classifier import _match_keywords
        text = "chromadb embedding error: chroma collection failed"
        hits = _match_keywords(text, ["chromadb", "chroma", "embedding", "collection"], 2)
        assert hits >= 2

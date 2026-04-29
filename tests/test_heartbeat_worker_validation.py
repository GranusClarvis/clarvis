"""Unit tests for clarvis.heartbeat.worker_validation.

Covers: classify_worker_type(), validate_worker_output(),
and the per-type validators (_check_research/implementation/maintenance_output).
No external I/O — pure logic tests.
"""

import pytest
from clarvis.heartbeat.worker_validation import (
    classify_worker_type,
    validate_worker_output,
    porcelain_delta_paths,
    _check_research_output,
    _check_implementation_output,
    _check_maintenance_output,
    RESEARCH,
    IMPLEMENTATION,
    MAINTENANCE,
    GENERAL,
    _get_compiled,
    _WORKER_PATTERNS,
)


# ---------------------------------------------------------------------------
# classify_worker_type — tag-based (Signal 1)
# ---------------------------------------------------------------------------

class TestClassifyWorkerTypeByTag:
    def test_research_tag(self):
        assert classify_worker_type("do something", task_tag="RESEARCH 2026-04-02") == RESEARCH

    def test_impl_tag(self):
        assert classify_worker_type("do something", task_tag="IMPL sprint-7") == IMPLEMENTATION

    def test_maintenance_tag(self):
        assert classify_worker_type("do something", task_tag="MAINT cleanup") == MAINTENANCE

    def test_tag_case_insensitive(self):
        assert classify_worker_type("x", task_tag="research") == RESEARCH
        assert classify_worker_type("x", task_tag="Impl") == IMPLEMENTATION
        assert classify_worker_type("x", task_tag="maint") == MAINTENANCE

    def test_tag_takes_priority_over_text(self):
        # Tag says research, text says implement
        assert classify_worker_type("implement the feature", task_tag="RESEARCH") == RESEARCH

    def test_unrecognized_tag_falls_through(self):
        # Tag doesn't match any known type — should fall through to text matching
        result = classify_worker_type("implement the fix", task_tag="BUGFIX")
        assert result == IMPLEMENTATION  # matched by regex


# ---------------------------------------------------------------------------
# classify_worker_type — prompt_variant (Signal 2)
# ---------------------------------------------------------------------------

class TestClassifyWorkerTypeByPromptVariant:
    def test_research_variant(self):
        assert classify_worker_type("x", prompt_variant_task_type="research") == RESEARCH

    def test_implementation_variant(self):
        assert classify_worker_type("x", prompt_variant_task_type="implementation") == IMPLEMENTATION

    def test_bugfix_variant(self):
        assert classify_worker_type("x", prompt_variant_task_type="bugfix") == IMPLEMENTATION

    def test_refactoring_variant(self):
        assert classify_worker_type("x", prompt_variant_task_type="refactoring") == IMPLEMENTATION

    def test_optimization_variant(self):
        assert classify_worker_type("x", prompt_variant_task_type="optimization") == IMPLEMENTATION

    def test_tag_overrides_variant(self):
        assert classify_worker_type("x", task_tag="RESEARCH", prompt_variant_task_type="implementation") == RESEARCH

    def test_unknown_variant_falls_through(self):
        result = classify_worker_type("cleanup old logs", prompt_variant_task_type="unknown")
        assert result == MAINTENANCE  # matched by regex


# ---------------------------------------------------------------------------
# classify_worker_type — regex (Signal 3)
# ---------------------------------------------------------------------------

class TestClassifyWorkerTypeByRegex:
    def test_research_deep_dive(self):
        assert classify_worker_type("deep dive into attention mechanisms") == RESEARCH

    def test_research_paper_study(self):
        assert classify_worker_type("research paper on GWT architecture") == RESEARCH

    def test_research_lit_review(self):
        assert classify_worker_type("literature review of memory systems") == RESEARCH

    def test_implement_keyword(self):
        assert classify_worker_type("implement the new cost tracker") == IMPLEMENTATION

    def test_fix_bug(self):
        assert classify_worker_type("fix bug in heartbeat postflight") == IMPLEMENTATION

    def test_refactor(self):
        assert classify_worker_type("refactor the brain module") == IMPLEMENTATION

    def test_add_function(self):
        assert classify_worker_type("add function to parse QUEUE.md") == IMPLEMENTATION

    def test_cleanup(self):
        assert classify_worker_type("cleanup old log files") == MAINTENANCE

    def test_health_check(self):
        assert classify_worker_type("health check on brain and cron") == MAINTENANCE

    def test_vacuum(self):
        assert classify_worker_type("vacuum chromadb collections") == MAINTENANCE

    def test_backup_data(self):
        # "migration" matches implementation regex before maintenance can match
        assert classify_worker_type("backup database and verify integrity") == MAINTENANCE

    def test_dead_code_audit(self):
        assert classify_worker_type("dead code audit and remove unused scripts") == MAINTENANCE

    def test_general_fallback(self):
        assert classify_worker_type("update the QUEUE.md file") == GENERAL

    def test_empty_text(self):
        assert classify_worker_type("") == GENERAL

    def test_none_text(self):
        assert classify_worker_type(None) == GENERAL


# ---------------------------------------------------------------------------
# _get_compiled — pattern compilation
# ---------------------------------------------------------------------------

class TestGetCompiled:
    def test_returns_compiled_patterns(self):
        compiled = _get_compiled()
        assert RESEARCH in compiled
        assert IMPLEMENTATION in compiled
        assert MAINTENANCE in compiled

    def test_pattern_count_matches_source(self):
        compiled = _get_compiled()
        for wtype in (RESEARCH, IMPLEMENTATION, MAINTENANCE):
            assert len(compiled[wtype]) == len(_WORKER_PATTERNS[wtype])


# ---------------------------------------------------------------------------
# _check_research_output
# ---------------------------------------------------------------------------

class TestCheckResearchOutput:
    def test_good_research_output(self):
        output = """## Findings
Key insight: GWT attention correlates with task success.
Stored 3 brain memories via remember() with importance=0.8.
"""
        passed, reasons, checks = _check_research_output(output)
        assert passed is True
        assert checks["has_findings"] is True
        assert checks["has_brain_storage"] is True
        assert checks["has_structure"] is True

    def test_research_result_block(self):
        output = "RESEARCH_RESULT:\n  TOPIC: GWT\n  stored brain memories"
        passed, reasons, checks = _check_research_output(output)
        assert passed is True
        assert checks["has_findings"] is True

    def test_no_output(self):
        passed, reasons, checks = _check_research_output(None)
        assert passed is False
        assert "no output text" in reasons

    def test_empty_output(self):
        passed, reasons, checks = _check_research_output("")
        assert passed is False

    def test_unstructured_output(self):
        output = "I did some research and it was interesting."
        passed, reasons, checks = _check_research_output(output)
        assert passed is False
        assert not checks["has_findings"]
        assert not checks["has_brain_storage"]
        assert not checks["has_structure"]

    def test_partial_pass_two_of_three(self):
        output = "## Summary\nI learned that attention is important.\nstored results"
        passed, reasons, checks = _check_research_output(output)
        assert passed is True  # 2 of 3 checks pass

    def test_bullet_list_counts_as_structure(self):
        output = "- item one\n- item two\nlearned that X"
        passed, reasons, checks = _check_research_output(output)
        assert checks["has_structure"] is True


# ---------------------------------------------------------------------------
# _check_implementation_output
# ---------------------------------------------------------------------------

class TestCheckImplementationOutput:
    def test_good_implementation_output(self):
        output = """Edited clarvis/brain/store.py
def new_function():
    pass
pytest tests/ - 5 passed, 0 failed
"""
        passed, reasons, checks = _check_implementation_output(output)
        assert passed is True
        assert checks["has_file_changes"] is True
        assert checks["has_tests"] is True
        assert checks["has_code"] is True

    def test_file_changes_required(self):
        output = "def foo():\n    pass\npytest passed"
        passed, reasons, checks = _check_implementation_output(output)
        assert passed is False
        assert "no file changes detected" in reasons

    def test_no_output(self):
        passed, reasons, checks = _check_implementation_output(None)
        assert passed is False
        assert "no output text" in reasons

    def test_empty_output(self):
        passed, reasons, checks = _check_implementation_output("")
        assert passed is False

    def test_file_changes_only_passes(self):
        output = "Edited the config file, wrote to /tmp/output.json, modified 3 files"
        passed, reasons, checks = _check_implementation_output(output)
        assert passed is True
        assert checks["has_file_changes"] is True

    def test_write_tool_pattern(self):
        output = 'Write(file_path="/tmp/test.py")\ncreated new file'
        passed, reasons, checks = _check_implementation_output(output)
        assert passed is True

    def test_import_counts_as_code(self):
        output = "edited file\nimport json\nfrom pathlib import Path"
        passed, reasons, checks = _check_implementation_output(output)
        assert checks["has_code"] is True


# ---------------------------------------------------------------------------
# _check_maintenance_output
# ---------------------------------------------------------------------------

class TestCheckMaintenanceOutput:
    def test_good_maintenance_output(self):
        output = "Health check: all systems OK. Cleaned 15 old log files. Disk usage: 42%."
        passed, reasons, checks = _check_maintenance_output(output)
        assert passed is True
        assert checks["has_status"] is True
        assert checks["has_actions"] is True

    def test_status_only_passes(self):
        output = "Health check report: all metrics within normal range."
        passed, reasons, checks = _check_maintenance_output(output)
        assert passed is True
        assert checks["has_status"] is True

    def test_actions_only_passes(self):
        output = "Pruned 200 stale entries. Archived old sessions. Compressed logs."
        passed, reasons, checks = _check_maintenance_output(output)
        assert passed is True
        assert checks["has_actions"] is True

    def test_no_action_needed_passes(self):
        output = "Everything all healthy, no action needed."
        passed, reasons, checks = _check_maintenance_output(output)
        assert passed is True

    def test_no_output(self):
        passed, reasons, checks = _check_maintenance_output(None)
        assert passed is False

    def test_empty_output(self):
        passed, reasons, checks = _check_maintenance_output("")
        assert passed is False

    def test_unrelated_output(self):
        output = "The sky is blue and water is wet."
        passed, reasons, checks = _check_maintenance_output(output)
        assert passed is False


# ---------------------------------------------------------------------------
# validate_worker_output
# ---------------------------------------------------------------------------

class TestValidateWorkerOutput:
    def test_success_research_good_output(self):
        output = "## Findings\nKey insight found.\nStored in brain via remember()."
        result = validate_worker_output(RESEARCH, output, "success")
        assert result["validated"] is True
        assert result["downgrade"] is False
        assert result["worker_type"] == RESEARCH

    def test_success_research_bad_output_downgrades(self):
        output = "I looked at stuff."
        result = validate_worker_output(RESEARCH, output, "success")
        assert result["validated"] is False
        assert result["downgrade"] is True

    def test_failure_status_skips_validation(self):
        result = validate_worker_output(RESEARCH, "", "failure")
        assert result["validated"] is True
        assert result["downgrade"] is False

    def test_timeout_status_skips_validation(self):
        result = validate_worker_output(IMPLEMENTATION, "", "timeout")
        assert result["validated"] is True
        assert result["downgrade"] is False

    def test_general_type_skips_validation(self):
        result = validate_worker_output(GENERAL, "", "success")
        assert result["validated"] is True
        assert result["downgrade"] is False

    def test_success_implementation_no_files_downgrades(self):
        output = "I thought about the code but didn't change anything."
        result = validate_worker_output(IMPLEMENTATION, output, "success")
        assert result["downgrade"] is True

    def test_success_implementation_with_files_passes(self):
        output = "Edited foo.py, wrote tests. pytest 3 passed."
        result = validate_worker_output(IMPLEMENTATION, output, "success")
        assert result["validated"] is True
        assert result["downgrade"] is False

    def test_success_maintenance_with_status_passes(self):
        output = "Health check passed. All systems OK."
        result = validate_worker_output(MAINTENANCE, output, "success")
        assert result["validated"] is True

    def test_result_has_expected_keys(self):
        result = validate_worker_output(GENERAL, "x", "success")
        assert "validated" in result
        assert "worker_type" in result
        assert "downgrade" in result
        assert "reasons" in result
        assert "checks" in result

    def test_partial_success_is_not_revalidated(self):
        # partial_success != "success", so validation is skipped
        result = validate_worker_output(RESEARCH, "", "partial_success")
        assert result["validated"] is True
        assert result["downgrade"] is False


# ---------------------------------------------------------------------------
# Git-evidence false-partial fix (AUTONOMOUS_OUTPUT_VALIDATION_FALSE_PARTIAL_AUDIT)
# ---------------------------------------------------------------------------

class TestGitEvidenceOverridesTextHeuristic:
    """The false-partial pattern: real file changes happened, but the Claude
    Code summary output didn't echo Edit/Write tool-call markers, so the
    text-only validator wrongly downgraded shipped work to partial_success.
    Real filesystem evidence must override the text heuristic."""

    def test_implementation_summary_output_with_real_diff_passes(self):
        # Reproduces the actual SEMANTIC_OVERLAP_BOOST / PHI_SEMANTIC_SAMPLING_FIX
        # case: a short summary output that has none of the tool-call markers
        # the regex looks for, but a real diff exists.
        summary_only = "Implemented the fix, see commit. All tests green."
        diff = (
            "clarvis/metrics/phi.py            | 24 ++++++++++++++-------\n"
            "data/phi_regression_baseline.json | 10 ++++-----\n"
            "memory/evolution/QUEUE.md         |  2 +-\n"
            "3 files changed, 24 insertions(+), 12 deletions(-)"
        )
        result = validate_worker_output(
            IMPLEMENTATION, summary_only, "success",
            git_diff_stat=diff, task_made_commit=True,
        )
        assert result["validated"] is True
        assert result["downgrade"] is False
        assert result["checks"]["has_file_changes"] is True
        assert result["checks"]["has_code"] is True

    def test_implementation_test_file_in_diff_credits_has_tests(self):
        diff = (
            "clarvis/metrics/self_model.py            | 21 +++--\n"
            "tests/clarvis/test_self_model.py         | 38 +++++++\n"
            "2 files changed, 56 insertions(+), 3 deletions(-)"
        )
        result = validate_worker_output(
            IMPLEMENTATION, "Done.", "success",
            git_diff_stat=diff, task_made_commit=True,
        )
        assert result["validated"] is True
        assert result["checks"]["has_tests"] is True
        assert result["checks"]["has_code"] is True

    def test_implementation_bookkeeping_only_diff_still_downgrades(self):
        # Diff shows ONLY QUEUE.md / SWO_TRACKER.md / status.json — these are
        # housekeeping, not actual delivery. Should still be downgraded.
        diff = (
            "memory/evolution/QUEUE.md       |  4 +-\n"
            "memory/evolution/SWO_TRACKER.md |  3 +-\n"
            "website/static/status.json      | 36 ++++++++--\n"
            "3 files changed, 41 insertions(+), 2 deletions(-)"
        )
        result = validate_worker_output(
            IMPLEMENTATION, "Updated tracker.", "success",
            git_diff_stat=diff, task_made_commit=True,
        )
        assert result["validated"] is False
        assert result["downgrade"] is True
        assert "no file changes detected" in result["reasons"]

    def test_implementation_no_diff_no_text_evidence_downgrades(self):
        # No diff captured AND output_text has no markers — true partial.
        result = validate_worker_output(
            IMPLEMENTATION, "Thought about it.", "success",
            git_diff_stat="", task_made_commit=False,
        )
        assert result["validated"] is False
        assert result["downgrade"] is True

    def test_maintenance_real_diff_credits_has_actions(self):
        diff = (
            "scripts/cron/cron_doctor.py | 12 ++++++++++--\n"
            "1 file changed, 10 insertions(+), 2 deletions(-)"
        )
        result = validate_worker_output(
            MAINTENANCE, "Fixed the doctor.", "success",
            git_diff_stat=diff, task_made_commit=True,
        )
        assert result["validated"] is True
        assert result["checks"]["has_actions"] is True

    def test_research_unaffected_by_git_signal(self):
        # Research validator is unchanged: a code diff doesn't substitute for
        # findings/brain storage/structure.
        diff = "some/file.py | 1 +\n1 file changed, 1 insertion(+)"
        result = validate_worker_output(
            RESEARCH, "I looked at stuff.", "success",
            git_diff_stat=diff, task_made_commit=True,
        )
        assert result["validated"] is False
        assert result["downgrade"] is True

    def test_back_compat_default_args(self):
        # Older callers that don't pass git args still work.
        out = "Edited foo.py\ndef bar(): pass"
        result = validate_worker_output(IMPLEMENTATION, out, "success")
        assert result["validated"] is True


# ---------------------------------------------------------------------------
# Porcelain-delta uncommitted-edit credit
# (WORKER_VALIDATION_UNCOMMITTED_DIFF_CREDIT)
# ---------------------------------------------------------------------------

class TestPorcelainDeltaPaths:
    """porcelain_delta_paths() should surface paths newly dirty/untracked."""

    def test_new_untracked_file(self):
        pre = ""
        post = "?? scripts/new_thing.py"
        assert porcelain_delta_paths(pre, post) == ["scripts/new_thing.py"]

    def test_new_modified_file(self):
        pre = ""
        post = " M clarvis/brain/store.py"
        assert porcelain_delta_paths(pre, post) == ["clarvis/brain/store.py"]

    def test_paths_present_in_pre_are_excluded(self):
        # File was already dirty before the task — not the task's work.
        pre = " M scripts/old_dirty.py"
        post = " M scripts/old_dirty.py\n?? tests/new_test.py"
        assert porcelain_delta_paths(pre, post) == ["tests/new_test.py"]

    def test_handles_rename_destination(self):
        pre = ""
        post = "R  old/path.py -> new/path.py"
        assert porcelain_delta_paths(pre, post) == ["new/path.py"]

    def test_empty_inputs(self):
        assert porcelain_delta_paths("", "") == []
        assert porcelain_delta_paths(None, None) == []

    def test_multiple_new_paths_sorted(self):
        post = "?? b.py\n?? a.py"
        assert porcelain_delta_paths("", post) == ["a.py", "b.py"]


class TestUncommittedEditCredit:
    """Uncommitted edits (porcelain delta) should be credited as evidence,
    matching the contract for committed diffs. This fixes the false-partial
    downgrade where validate_worker_output() previously only saw committed
    diff stats even though postflight captured working-tree porcelain."""

    def test_implementation_uncommitted_edit_passes(self):
        # No commit, no diff stat, but the working tree shows real edits to
        # source + tests. Validator must credit them.
        out = "Done."
        delta = ["clarvis/brain/store.py", "tests/test_store.py"]
        result = validate_worker_output(
            IMPLEMENTATION, out, "success",
            git_diff_stat="", task_made_commit=False,
            porcelain_delta=delta,
        )
        assert result["validated"] is True
        assert result["downgrade"] is False
        assert result["checks"]["has_file_changes"] is True
        assert result["checks"]["has_tests"] is True
        assert result["checks"]["has_code"] is True

    def test_implementation_committed_diff_still_works(self):
        # Pre-existing path: committed-only edits remain credited (regression
        # guard for the fix).
        diff = (
            "scripts/cron/cron_doctor.py | 12 ++++++++++--\n"
            "1 file changed, 10 insertions(+), 2 deletions(-)"
        )
        result = validate_worker_output(
            IMPLEMENTATION, "Done.", "success",
            git_diff_stat=diff, task_made_commit=True,
            porcelain_delta=[],
        )
        assert result["validated"] is True
        assert result["checks"]["has_file_changes"] is True
        assert result["checks"]["has_code"] is True

    def test_implementation_mixed_committed_and_uncommitted(self):
        # Some files committed, others left dirty — both should count.
        diff = (
            "clarvis/brain/store.py | 4 +++-\n"
            "1 file changed, 3 insertions(+), 1 deletion(-)"
        )
        delta = ["tests/test_store.py"]
        result = validate_worker_output(
            IMPLEMENTATION, "shipped", "success",
            git_diff_stat=diff, task_made_commit=True,
            porcelain_delta=delta,
        )
        assert result["validated"] is True
        assert result["checks"]["has_file_changes"] is True
        assert result["checks"]["has_tests"] is True  # from porcelain delta
        assert result["checks"]["has_code"] is True   # from committed diff

    def test_implementation_bookkeeping_only_porcelain_still_downgrades(self):
        # Working tree shows ONLY journaling files dirty — same exclusion
        # rule as committed diffs.
        delta = [
            "memory/evolution/QUEUE.md",
            "memory/evolution/SWO_TRACKER.md",
            "website/static/status.json",
        ]
        result = validate_worker_output(
            IMPLEMENTATION, "Updated tracker.", "success",
            git_diff_stat="", task_made_commit=False,
            porcelain_delta=delta,
        )
        assert result["validated"] is False
        assert result["downgrade"] is True
        assert "no file changes detected" in result["reasons"]

    def test_maintenance_uncommitted_edit_credits_action(self):
        # Maintenance task that edited a script without committing.
        delta = ["scripts/cron/cron_doctor.py"]
        result = validate_worker_output(
            MAINTENANCE, "Fixed the doctor.", "success",
            git_diff_stat="", task_made_commit=False,
            porcelain_delta=delta,
        )
        assert result["validated"] is True
        assert result["checks"]["has_actions"] is True

    def test_implementation_no_commit_no_delta_still_downgrades(self):
        # No commit, no working-tree changes, no text evidence — true partial.
        result = validate_worker_output(
            IMPLEMENTATION, "Thought about it.", "success",
            git_diff_stat="", task_made_commit=False,
            porcelain_delta=[],
        )
        assert result["validated"] is False
        assert result["downgrade"] is True

    def test_research_unaffected_by_porcelain_delta(self):
        # Research validator stays text-only — code paths in delta don't
        # substitute for findings/storage/structure.
        result = validate_worker_output(
            RESEARCH, "I looked at stuff.", "success",
            git_diff_stat="", task_made_commit=False,
            porcelain_delta=["some/file.py"],
        )
        assert result["validated"] is False
        assert result["downgrade"] is True

    def test_back_compat_no_porcelain_arg(self):
        # Callers that don't pass porcelain_delta keep working.
        out = "Edited foo.py\ndef bar(): pass"
        result = validate_worker_output(IMPLEMENTATION, out, "success")
        assert result["validated"] is True

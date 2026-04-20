"""Tests for clarvis.heartbeat.delivery_validator — PR delivery enforcement for project tasks."""

import pytest
from clarvis.heartbeat.delivery_validator import (
    is_project_task,
    extract_pr_urls,
    has_pr_evidence,
    validate_project_delivery,
)


class TestIsProjectTask:
    def test_project_swo_tag(self):
        assert is_project_task("[PROJECT:SWO] Fix the login page")

    def test_project_other_tag(self):
        assert is_project_task("[PROJECT:WEBAPP] Add dark mode")

    def test_swo_parens(self):
        assert is_project_task("(SWO) Deploy new auth flow")

    def test_swo_brackets(self):
        assert is_project_task("[SWO] Update CI pipeline")

    def test_non_project_task(self):
        assert not is_project_task("[RESEARCH] Study attention mechanisms")

    def test_non_project_impl(self):
        assert not is_project_task("[IMPL] Add brain dedup")

    def test_task_tag_override(self):
        assert is_project_task("Fix login page", task_tag="PROJECT:SWO")

    def test_empty(self):
        assert not is_project_task("")

    def test_case_insensitive(self):
        assert is_project_task("[project:swo] lowercase tag")


class TestExtractPrUrls:
    def test_single_url(self):
        text = "Created PR: https://github.com/InverseAltruism/Star-World-Order/pull/183"
        urls = extract_pr_urls(text)
        assert urls == ["https://github.com/InverseAltruism/Star-World-Order/pull/183"]

    def test_multiple_urls(self):
        text = (
            "PR 1: https://github.com/owner/repo/pull/1\n"
            "PR 2: https://github.com/owner/repo/pull/2"
        )
        urls = extract_pr_urls(text)
        assert len(urls) == 2

    def test_no_urls(self):
        assert extract_pr_urls("No PR here, just code changes.") == []

    def test_empty(self):
        assert extract_pr_urls("") == []

    def test_none(self):
        assert extract_pr_urls(None) == []


class TestHasPrEvidence:
    def test_strong_with_url(self):
        text = "Created https://github.com/org/repo/pull/42"
        result = has_pr_evidence(text)
        assert result["has_pr_url"]
        assert result["evidence_level"] == "strong"
        assert result["pr_urls"] == ["https://github.com/org/repo/pull/42"]

    def test_moderate_with_ref(self):
        text = "Opened PR #42 for the auth fix"
        result = has_pr_evidence(text)
        assert result["has_pr_ref"]
        assert result["evidence_level"] == "moderate"

    def test_moderate_with_gh_create(self):
        text = "Ran gh pr create to submit the changes"
        result = has_pr_evidence(text)
        assert result["has_pr_creation"]
        assert result["evidence_level"] == "moderate"

    def test_weak_push_only(self):
        text = "pushed to origin feature branch"
        result = has_pr_evidence(text)
        assert result["has_git_push"]
        assert result["evidence_level"] == "weak"

    def test_none(self):
        text = "Made some code changes and ran tests."
        result = has_pr_evidence(text)
        assert result["evidence_level"] == "none"

    def test_empty(self):
        result = has_pr_evidence("")
        assert result["evidence_level"] == "none"


class TestValidateProjectDelivery:
    def test_non_project_passes_through(self):
        result = validate_project_delivery(
            "[IMPL] Fix brain dedup",
            "edited files, ran tests, all passed",
            "success",
        )
        assert not result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]

    def test_project_with_pr_url_passes(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Fixed the login page. Created https://github.com/org/repo/pull/42",
            "success",
        )
        assert result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]
        assert result["evidence"]["evidence_level"] == "strong"

    def test_project_with_pr_ref_passes(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Fixed the login page. Opened PR #42 with the changes.",
            "success",
        )
        assert result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]

    def test_project_without_pr_downgrades(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Fixed the login page. Edited auth.tsx and ran tests.",
            "success",
        )
        assert result["is_project"]
        assert not result["validated"]
        assert result["downgrade"]
        assert result["downgrade_reason"] == "no_pr_delivery"

    def test_project_push_only_downgrades(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Fixed login page. git push origin feature-branch. Tests pass.",
            "success",
        )
        assert result["is_project"]
        assert result["downgrade"]
        assert result["evidence"]["evidence_level"] == "weak"
        assert "branch pushed but PR not created" in result["reasons"][0]

    def test_project_failure_not_downgraded(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Build failed: syntax error in auth.tsx",
            "failure",
        )
        assert result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]

    def test_project_partial_not_downgraded(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Fix login page",
            "Partial work done, blocked by CI.",
            "partial_success",
        )
        assert result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]

    def test_swo_parens_detected(self):
        result = validate_project_delivery(
            "(SWO) Deploy new auth flow",
            "Deployed. No PR though.",
            "success",
        )
        assert result["is_project"]
        assert result["downgrade"]

    def test_tag_detection_via_task_tag(self):
        result = validate_project_delivery(
            "Fix login page",
            "Fixed it, no PR.",
            "success",
            task_tag="PROJECT:SWO",
        )
        assert result["is_project"]
        assert result["downgrade"]

    def test_gh_pr_create_moderate_evidence(self):
        result = validate_project_delivery(
            "[PROJECT:SWO] Add tests",
            "Created pull request for test additions via gh pr create.",
            "success",
        )
        assert result["is_project"]
        assert result["validated"]
        assert not result["downgrade"]

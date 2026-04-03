"""Tests for clone_test_verify.py — ROADMAP Phase 3.2."""

import json
import os
import subprocess
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from clone_test_verify import CloneTestVerify, WORKSPACE


@pytest.fixture
def ctv():
    return CloneTestVerify()


class TestParseTestOutput:
    """Test the output parser without running actual tests."""

    def test_parse_import_check_pass(self, ctv):
        proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="brain OK\n", stderr="")
        passed, failed, errors = ctv._parse_test_output("import_check", proc)
        assert passed == 1 and failed == 0 and errors == 0

    def test_parse_import_check_fail(self, ctv):
        proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="ImportError")
        passed, failed, errors = ctv._parse_test_output("import_check", proc)
        assert passed == 0 and failed == 1 and errors == 0

    def test_parse_pytest_summary(self, ctv):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="45 passed, 2 failed, 1 error in 12.34s\n",
            stderr="",
        )
        passed, failed, errors = ctv._parse_test_output("pytest", proc)
        assert passed == 45
        assert failed == 2
        assert errors == 1

    def test_parse_pytest_all_pass(self, ctv):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="32 passed in 8.21s\n",
            stderr="",
        )
        passed, failed, errors = ctv._parse_test_output("pytest", proc)
        assert passed == 32
        assert failed == 0
        assert errors == 0

    def test_parse_pytest_empty_failure(self, ctv):
        proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        passed, failed, errors = ctv._parse_test_output("pytest", proc)
        assert errors == 1  # Non-zero exit with no parse = 1 error

    def test_parse_ruff_pass(self, ctv):
        proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        passed, failed, errors = ctv._parse_test_output("ruff", proc)
        assert passed == 1 and failed == 0

    def test_parse_ruff_fail(self, ctv):
        proc = subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout="scripts/foo.py:10:1: F821 undefined name\nscripts/bar.py:5:1: E999 syntax error\n",
            stderr="",
        )
        passed, failed, errors = ctv._parse_test_output("ruff", proc)
        assert passed == 0
        assert failed == 2


class TestWorktreeLifecycle:
    """Test worktree create/list/cleanup without modifying main."""

    def test_create_and_cleanup(self, ctv):
        """Create a worktree, verify it exists, then clean it up."""
        result = ctv.create_worktree()
        assert result["status"] == "created"
        assert result["path"] is not None

        wt_path = result["path"]
        branch = result["branch"]
        assert os.path.isdir(wt_path)

        # List should include it
        wts = ctv.list_worktrees()
        paths = [w["path"] for w in wts]
        assert wt_path in paths

        # Rollback (cleanup)
        rb = ctv.rollback_worktree(wt_path)
        assert rb["status"] == "rolled_back"
        assert not os.path.exists(wt_path)

    def test_list_worktrees(self, ctv):
        """List worktrees returns list (may be empty)."""
        wts = ctv.list_worktrees()
        assert isinstance(wts, list)


class TestRunTestsMainWorkspace:
    """Run tests against the main workspace (read-only, no worktree)."""

    def test_run_tests_main_workspace(self, ctv):
        """Verify the test runner works against main workspace."""
        result = ctv.run_tests(str(WORKSPACE))
        assert "status" in result
        assert "tests_passed" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) > 0
        # import_check should always pass in main workspace
        import_result = next((r for r in result["results"] if r["name"] == "import_check"), None)
        assert import_result is not None
        assert import_result["exit_code"] == 0


class TestVerify:
    """Test the full verify flow."""

    def test_verify_main_workspace(self, ctv):
        """Verify against main workspace returns recommendation."""
        result = ctv.verify(str(WORKSPACE))
        assert "recommendation" in result
        assert result["recommendation"].startswith("PROMOTE") or result["recommendation"].startswith("REJECT")

    def test_verify_nonexistent_path(self, ctv):
        result = ctv.verify("/nonexistent/path/xyz")
        assert result["status"] == "error"

    def test_verify_worktree_baseline_comparison(self, ctv):
        """Create a worktree and verify with baseline comparison."""
        wt = ctv.create_worktree()
        assert wt["status"] == "created"
        try:
            result = ctv.verify(wt["path"], baseline_comparison=True)
            assert "recommendation" in result
            # Worktree from HEAD with no changes should have same failures as baseline
            if result.get("new_failures") is not None:
                assert len(result["new_failures"]) == 0
                assert result["safe_to_promote"] is True
        finally:
            ctv.rollback_worktree(wt["path"])

    def test_verify_no_baseline(self, ctv):
        """Verify without baseline comparison."""
        result = ctv.verify(str(WORKSPACE), baseline_comparison=False)
        assert "recommendation" in result
        # Should not have baseline_failures key when baseline is off
        assert "baseline_failures" not in result


class TestCLI:
    """Test CLI invocations."""

    def test_cli_status(self):
        proc = subprocess.run(
            ["python3", "scripts/clone_test_verify.py", "status"],
            capture_output=True, text=True, timeout=15,
            cwd=str(WORKSPACE),
        )
        assert proc.returncode == 0

    def test_cli_unknown_command(self):
        proc = subprocess.run(
            ["python3", "scripts/clone_test_verify.py", "bogus"],
            capture_output=True, text=True, timeout=10,
            cwd=str(WORKSPACE),
        )
        assert proc.returncode == 1

    def test_cli_help(self):
        proc = subprocess.run(
            ["python3", "scripts/clone_test_verify.py"],
            capture_output=True, text=True, timeout=10,
            cwd=str(WORKSPACE),
        )
        assert proc.returncode == 1
        assert "Clone" in proc.stdout or "clone" in proc.stdout.lower()

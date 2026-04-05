#!/usr/bin/env python3
"""Smoke tests for clarvis_reflection.py — path construction and basic logic."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "cognition"))

from clarvis_reflection import get_today_memory, extract_lessons, count_pending_tasks


class TestGetTodayMemory:
    """Regression tests for get_today_memory path construction."""

    def test_returns_string_or_none(self):
        """get_today_memory should return str content or None, never raise."""
        result = get_today_memory()
        assert result is None or isinstance(result, str)

    def test_path_uses_fstring_interpolation(self):
        """Regression: path must use f-string, not literal '{today}'."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake memory file for today
            mem_dir = os.path.join(tmpdir, "memory")
            os.makedirs(mem_dir)
            today_file = os.path.join(mem_dir, f"{today}.md")
            with open(today_file, "w") as f:
                f.write("# Test memory\nCompleted smoke test.\n")

            old_ws = os.environ.get("CLARVIS_WORKSPACE")
            try:
                os.environ["CLARVIS_WORKSPACE"] = tmpdir
                result = get_today_memory()
                assert result is not None, "Should find today's memory file"
                assert "Test memory" in result
            finally:
                if old_ws is not None:
                    os.environ["CLARVIS_WORKSPACE"] = old_ws
                elif "CLARVIS_WORKSPACE" in os.environ:
                    del os.environ["CLARVIS_WORKSPACE"]

    def test_no_literal_braces_in_path(self):
        """Regression: the path must not contain literal '{today}'."""
        import inspect
        source = inspect.getsource(get_today_memory)
        assert 'f"memory/{today}.md"' in source or "f'memory/{today}.md'" in source, \
            "Path should use f-string interpolation, not a plain string"
        assert '"memory/{today}.md"' not in source.replace('f"memory/{today}.md"', ''), \
            "Found non-f-string 'memory/{today}.md' — this is the regression"

    def test_missing_file_returns_none(self):
        """Should return None when today's memory file does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "memory"))
            old_ws = os.environ.get("CLARVIS_WORKSPACE")
            try:
                os.environ["CLARVIS_WORKSPACE"] = tmpdir
                result = get_today_memory()
                assert result is None
            finally:
                if old_ws is not None:
                    os.environ["CLARVIS_WORKSPACE"] = old_ws
                elif "CLARVIS_WORKSPACE" in os.environ:
                    del os.environ["CLARVIS_WORKSPACE"]


class TestExtractLessons:
    def test_extracts_completed_lines(self):
        content = "# Day\n- Completed the brain migration task successfully\n- Nothing here\n"
        lessons = extract_lessons(content)
        assert len(lessons) >= 1
        assert any("Completed" in l for l in lessons)

    def test_max_five(self):
        lines = "\n".join(f"- Completed task {i} with great results and details" for i in range(10))
        lessons = extract_lessons(lines)
        assert len(lessons) <= 5


class TestCountPendingTasks:
    def test_counts_unchecked(self):
        """count_pending_tasks should work against real QUEUE.md."""
        count = count_pending_tasks()
        assert isinstance(count, int)
        assert count >= 0


class TestCronDoctorHomeExpansion:
    """Regression: cron_doctor must not pass HOME='~' to subprocesses."""

    def test_home_not_literal_tilde(self):
        """The env dict in _rerun_job must expand ~ to actual path."""
        import inspect
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "cron"))
        from cron_doctor import _rerun_job
        source = inspect.getsource(_rerun_job)
        # Must not have "HOME": "~" (literal tilde assignment)
        assert '"HOME": "~"' not in source, \
            "HOME must not be literal '~' — use os.path.expanduser"
        # If HOME is set, it should use expanduser
        if '"HOME"' in source:
            assert 'expanduser' in source, \
                "If HOME is set in env, it must use expanduser"

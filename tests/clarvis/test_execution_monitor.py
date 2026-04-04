"""Tests for execution_monitor.py checkpoint detection."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import _paths  # noqa: F401,E402

from execution_monitor import count_checkpoints


class TestCountCheckpoints:
    """Test checkpoint detection in execution output."""

    def test_no_checkpoints(self):
        result = count_checkpoints("Hello world\nsome random text")
        assert result["checkpoint_count"] == 0
        assert result["progress_score"] == 0.0

    def test_empty_text(self):
        result = count_checkpoints("")
        assert result["checkpoint_count"] == 0
        assert result["progress_score"] == 0.0

    def test_todo_completion(self):
        text = "1. [completed] Run tests\n2. [completed] Fix bug"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 2

    def test_result_line(self):
        text = "RESULT: success — tests all pass"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_queue_mark(self):
        text = "marked [x] in QUEUE.md"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_mark_variant(self):
        text = "mark task [x] with note"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_pytest_pass(self):
        text = "360 passed in 5.64s"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_test_pass_mention(self):
        text = "All tests pass. No regressions."
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_multiple_checkpoints(self):
        text = (
            "1. [completed] Read files\n"
            "2. [completed] Run tests\n"
            "360 passed in 5s\n"
            "marked [x] in QUEUE.md\n"
            "RESULT: success — done\n"
        )
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 5
        assert result["progress_score"] == 1.0

    def test_progress_score_scales(self):
        # 1 checkpoint = 0.2
        text = "RESULT: success"
        result = count_checkpoints(text)
        assert result["progress_score"] == 0.2

    def test_progress_score_caps_at_one(self):
        text = "\n".join(f"{i}. [completed] task {i}" for i in range(10))
        result = count_checkpoints(text)
        assert result["progress_score"] == 1.0

    def test_returns_details_dict(self):
        text = "RESULT: partial\n360 passed in 5s"
        result = count_checkpoints(text)
        assert isinstance(result["checkpoint_details"], dict)
        assert len(result["checkpoint_details"]) >= 1

    def test_edit_tool_checkpoint(self):
        text = "Using Edit tool to modify file"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_write_tool_checkpoint(self):
        text = "Using Write tool to create file"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_case_insensitive_marks(self):
        text = "Marked task [x] in queue"
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 1

    def test_realistic_heartbeat_output(self):
        """Simulate a real heartbeat output with mixed content."""
        text = """
Starting task analysis...
Reading QUEUE.md for tasks.
1. [in_progress] Running tests
Running pytest...
360 passed, 280 warnings in 5.64s
All tests pass, no regressions.
1. [completed] Run tests
2. [in_progress] Update QUEUE.md
Edit tool applied to QUEUE.md
marked [x] HEARTBEAT_DOC_REFRESH_4
2. [completed] Update QUEUE.md
RESULT: success — 385 tests pass, no regressions
NEXT: none
"""
        result = count_checkpoints(text)
        assert result["checkpoint_count"] >= 5
        assert result["progress_score"] >= 0.8

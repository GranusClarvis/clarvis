"""
Unit tests for dashboard_server.py — data readers and state building.

Run: python3 -m pytest scripts/tests/test_dashboard_server.py -v
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
import _paths  # noqa: F401,E402

from dashboard_server import parse_queue, read_locks, build_state


class TestParseQueue:
    def test_parses_pending_task(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("## P0\n- [ ] [MY_TASK] Do something cool\n")
        tasks = parse_queue(q)
        assert len(tasks) == 1
        assert tasks[0]["tag"] == "MY_TASK"
        assert tasks[0]["status"] == "pending"
        assert tasks[0]["section"] == "P0"

    def test_parses_done_task(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("## Done\n- [x] [FINISHED] Was done\n")
        tasks = parse_queue(q)
        assert tasks[0]["status"] == "done"

    def test_parses_in_progress(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("## Active\n- [~] [WIP_TASK] Working on it\n")
        tasks = parse_queue(q)
        assert tasks[0]["status"] == "in_progress"

    def test_multiple_sections(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text(
            "## P0\n"
            "- [ ] [TASK_A] First\n"
            "## P1\n"
            "- [ ] [TASK_B] Second\n"
            "- [x] [TASK_C] Third\n"
        )
        tasks = parse_queue(q)
        assert len(tasks) == 3
        assert tasks[0]["section"] == "P0"
        assert tasks[1]["section"] == "P1"
        assert tasks[2]["section"] == "P1"

    def test_missing_file(self, tmp_path):
        tasks = parse_queue(tmp_path / "nonexistent.md")
        assert tasks == []

    def test_no_tasks(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("# Queue\nJust some text, no tasks.\n")
        tasks = parse_queue(q)
        assert tasks == []

    def test_nested_task_parsed(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        q.write_text("## P0\n  - [ ] [SUB_TASK] Nested with indent\n")
        tasks = parse_queue(q)
        # Nested tasks (with leading spaces) are not matched by regex
        # This is expected behavior — only top-level tasks count
        assert len(tasks) == 0

    def test_description_truncated(self, tmp_path):
        q = tmp_path / "QUEUE.md"
        long_desc = "A" * 200
        q.write_text(f"## P0\n- [ ] [LONG] {long_desc}\n")
        tasks = parse_queue(q)
        assert len(tasks[0]["description"]) <= 120


class TestReadLocks:
    def test_reads_lock_with_pid(self, tmp_path):
        lock = tmp_path / "clarvis_test.lock"
        lock.write_text("12345")
        with patch("dashboard_server.LOCK_DIR", tmp_path):
            locks = read_locks()
        assert len(locks) == 1
        assert locks[0]["name"] == "test"
        assert locks[0]["pid"] == "12345"

    def test_no_locks(self, tmp_path):
        with patch("dashboard_server.LOCK_DIR", tmp_path):
            locks = read_locks()
        assert locks == []

    def test_multiple_locks(self, tmp_path):
        (tmp_path / "clarvis_a.lock").write_text("111")
        (tmp_path / "clarvis_b.lock").write_text("222")
        (tmp_path / "other.lock").write_text("333")  # not clarvis_*
        with patch("dashboard_server.LOCK_DIR", tmp_path):
            locks = read_locks()
        assert len(locks) == 2
        names = {l["name"] for l in locks}
        assert names == {"a", "b"}


class TestBuildState:
    def test_returns_all_keys(self):
        """build_state returns dict with all expected keys."""
        s = build_state()
        expected_keys = {"queue", "agents", "locks", "recent_events",
                        "prs", "digest_lines", "scoreboard", "updated_at"}
        assert set(s.keys()) == expected_keys

    def test_queue_has_items(self):
        """Real QUEUE.md should have items."""
        s = build_state()
        assert len(s["queue"]) > 0

    def test_agents_have_expected_fields(self):
        """Agent entries should have standard fields."""
        s = build_state()
        if s["agents"]:
            a = s["agents"][0]
            assert "name" in a
            assert "status" in a
            assert "trust_score" in a

    def test_state_is_json_serializable(self):
        """Full state must be JSON serializable for SSE."""
        s = build_state()
        # Should not raise
        json.dumps(s, default=str)

"""
Unit tests for dashboard_events.py — event publishing + reading.

Run: python3 -m pytest scripts/tests/test_dashboard_events.py -v
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
import _paths  # noqa: F401,E402

import dashboard_events


@pytest.fixture
def tmp_events(tmp_path):
    """Redirect events to a temp directory."""
    events_file = tmp_path / "events.jsonl"
    with patch.object(dashboard_events, "DASHBOARD_DIR", tmp_path), \
         patch.object(dashboard_events, "EVENTS_FILE", events_file):
        yield events_file


class TestEmitEvent:
    def test_emits_basic_event(self, tmp_events):
        ev = dashboard_events.emit_event("task_started", task_name="Test task")
        assert ev["type"] == "task_started"
        assert ev["task_name"] == "Test task"
        assert "ts" in ev

    def test_writes_to_file(self, tmp_events):
        dashboard_events.emit_event("task_completed", status="success")
        lines = tmp_events.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["type"] == "task_completed"
        assert data["status"] == "success"

    def test_multiple_events_append(self, tmp_events):
        dashboard_events.emit_event("task_started", task_name="A")
        dashboard_events.emit_event("task_completed", task_name="A")
        dashboard_events.emit_event("pr_created", pr_url="https://example.com")
        lines = tmp_events.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_unknown_event_type_still_works(self, tmp_events):
        ev = dashboard_events.emit_event("unknown_type", data="test")
        assert ev["type"] == "unknown_type"
        assert tmp_events.exists()

    def test_extra_fields_included(self, tmp_events):
        ev = dashboard_events.emit_event("agent_spawned",
                                          agent="star-world-order",
                                          task_id="t123",
                                          branch="clarvis/swo/t123")
        assert ev["agent"] == "star-world-order"
        assert ev["task_id"] == "t123"
        assert ev["branch"] == "clarvis/swo/t123"

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        events_file = nested / "events.jsonl"
        with patch.object(dashboard_events, "DASHBOARD_DIR", nested), \
             patch.object(dashboard_events, "EVENTS_FILE", events_file):
            dashboard_events.emit_event("health_check", status="ok")
        assert events_file.exists()


class TestReadEvents:
    def test_reads_last_n(self, tmp_events):
        for i in range(10):
            dashboard_events.emit_event("task_started", idx=i)
        events = dashboard_events.read_events(3)
        assert len(events) == 3
        assert events[0]["idx"] == 7
        assert events[2]["idx"] == 9

    def test_empty_file(self, tmp_events):
        events = dashboard_events.read_events()
        assert events == []

    def test_all_events(self, tmp_events):
        dashboard_events.emit_event("task_started", n=1)
        dashboard_events.emit_event("task_completed", n=2)
        events = dashboard_events.read_events(100)
        assert len(events) == 2


class TestEventStats:
    def test_counts_by_type(self, tmp_events):
        dashboard_events.emit_event("task_started")
        dashboard_events.emit_event("task_started")
        dashboard_events.emit_event("task_completed")
        dashboard_events.emit_event("pr_created")
        stats = dashboard_events.event_stats()
        assert stats["task_started"] == 2
        assert stats["task_completed"] == 1
        assert stats["pr_created"] == 1

    def test_empty_stats(self, tmp_events):
        stats = dashboard_events.event_stats()
        assert stats == {}


class TestMaybeTrim:
    def test_trims_large_file(self, tmp_events):
        """_maybe_trim reduces lines when file exceeds size threshold."""
        with patch.object(dashboard_events, "MAX_EVENTS", 10):
            # Write 15 lines, each padded to exceed the 500KB size check
            padding = "x" * 40000  # ~40KB per line -> 15*40KB = ~600KB > 500KB
            for i in range(15):
                dashboard_events.emit_event("task_started", idx=i, pad=padding)
            lines = tmp_events.read_text().strip().splitlines()
            # Should trim to 80% of MAX_EVENTS = 8
            assert len(lines) <= 10

    def test_no_trim_small_file(self, tmp_events):
        """Small files are not trimmed (avoids unnecessary I/O)."""
        with patch.object(dashboard_events, "MAX_EVENTS", 5):
            for i in range(8):
                dashboard_events.emit_event("task_started", idx=i)
            lines = tmp_events.read_text().strip().splitlines()
            # File is tiny, won't hit size threshold — all 8 remain
            assert len(lines) == 8

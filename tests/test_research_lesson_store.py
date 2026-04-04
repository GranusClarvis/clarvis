#!/usr/bin/env python3
"""Tests for research_lesson_store.py — cross-run research lesson tracking."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402
from research_lesson_store import ResearchLessonStore, ResearchLesson


def _make_store(tmp_dir):
    path = os.path.join(tmp_dir, "test_lessons.jsonl")
    return ResearchLessonStore(path)


def test_record_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        lesson = store.record(
            topic="GWT broadcast",
            decision="APPLY",
            findings="Global workspace theory enables selective attention",
            queue_items=["Implement GWT module", "Add attention filter"],
            outcome="pending",
        )
        assert lesson.topic == "GWT broadcast"
        assert lesson.decision == "APPLY"
        assert len(lesson.queue_items) == 2

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].topic == "GWT broadcast"
        assert loaded[0].queue_items == ["Implement GWT module", "Add attention filter"]


def test_multiple_records():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("Topic A", "APPLY", "Findings A", ["item1"])
        store.record("Topic B", "ARCHIVE", "Findings B")
        store.record("Topic C", "DISCARD", "Findings C")

        loaded = store.load_all()
        assert len(loaded) == 3
        assert loaded[0].decision == "APPLY"
        assert loaded[1].decision == "ARCHIVE"
        assert loaded[2].decision == "DISCARD"


def test_update_outcome():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("Topic X", "APPLY", "Some findings", outcome="pending")
        store.record("Topic Y", "APPLY", "Other findings", outcome="pending")

        ok = store.update_outcome("Topic X", "success")
        assert ok

        loaded = store.load_all()
        assert loaded[0].outcome == "success"
        assert loaded[1].outcome == "pending"


def test_update_outcome_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("Topic A", "APPLY", "Findings")
        ok = store.update_outcome("nonexistent", "failure")
        assert not ok


def test_get_recent_lessons():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        for i in range(10):
            store.record(f"Topic {i}", "ARCHIVE", f"Findings {i}")

        recent = store.get_recent_lessons(3)
        assert len(recent) == 3
        assert recent[0].topic == "Topic 7"
        assert recent[2].topic == "Topic 9"


def test_inject_prompt_context_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        text = store.inject_prompt_context()
        assert text == ""


def test_inject_prompt_context():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("Successful topic", "APPLY", "Great findings", outcome="success")
        store.record("Failed topic", "APPLY", "Bad findings", outcome="failure")
        store.record("Skipped topic", "DISCARD", "Not relevant")

        text = store.inject_prompt_context()
        assert "PAST RESEARCH LESSONS" in text
        assert "Successful" in text
        assert "Failed" in text
        assert "AVOID similar" in text
        assert "Discarded" in text


def test_stats():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("A", "APPLY", "f", outcome="success")
        store.record("B", "APPLY", "f", outcome="failure")
        store.record("C", "ARCHIVE", "f")
        store.record("D", "APPLY", "f", ["q1", "q2"], outcome="success")

        s = store.stats()
        assert s["total"] == 4
        assert s["by_decision"]["APPLY"] == 3
        assert s["by_decision"]["ARCHIVE"] == 1
        assert s["apply_success_rate"] == 0.67  # 2/3
        assert s["total_queue_items"] == 2


def test_stats_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        s = store.stats()
        assert s["total"] == 0


def test_invalid_decision():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        try:
            store.record("Topic", "INVALID", "Findings")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


def test_findings_truncation():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        long_findings = "x" * 1000
        lesson = store.record("Topic", "ARCHIVE", long_findings)
        assert len(lesson.findings_summary) == 500


def test_corrupt_jsonl_line():
    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.record("Good", "APPLY", "findings")
        # Append corrupt line
        with open(store._path, "a") as f:
            f.write("THIS IS NOT JSON\n")
        store.record("Also good", "ARCHIVE", "more findings")

        loaded = store.load_all()
        assert len(loaded) == 2  # Corrupt line skipped


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")

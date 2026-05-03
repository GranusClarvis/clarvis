"""Tests for clarvis.queue.lane_autofill — `[QUEUE_LANE_MINIMUM_AUTOFILL]`.

Acceptance contract from QUEUE.md:
  - When both lanes are saturated, no autofill task spawns.
  - When one is empty, exactly one `[<LANE>_LANE_REFILL]` lands per scan.
  - Idempotent — does not stack if previous refill is still pending.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.queue import lane_autofill


class _FakeView:
    def __init__(self, lane_health):
        self.lane_health = lane_health


def _lh(lane: str, in_queue: int) -> dict:
    return {"lane": lane, "in_queue": in_queue, "eligible": 0, "blocked": 0}


@pytest.fixture
def tmp_queue(tmp_path):
    """Provide a temp QUEUE.md path that lane_autofill can read."""
    q = tmp_path / "QUEUE.md"
    q.write_text(
        "# Evolution Queue\n"
        "\n## P0 — Current Sprint\n"
        "\n## P1 — This Week\n"
        "\n### Some lane\n"
        "- [ ] **[OTHER_TASK]** unrelated work (PROJECT:CLARVIS)\n"
    )
    return q


def test_no_empty_lanes_no_spawn(tmp_queue, monkeypatch):
    """When every active lane has tasks, autofill spawns nothing."""
    fake = _FakeView([_lh("SWO", 5), _lh("BUNNYBAGZ", 3)])
    added_calls = []

    def _add_task(text, priority="P1", source="unknown"):
        added_calls.append((text, priority, source))
        return True

    monkeypatch.setattr(lane_autofill, "runnable_view", lambda: fake)
    monkeypatch.setattr(lane_autofill, "add_task", _add_task)
    monkeypatch.setattr(lane_autofill, "QUEUE_FILE", str(tmp_queue))

    spawned = lane_autofill.autofill_empty_lanes(queue_path=str(tmp_queue))
    assert spawned == []
    assert added_calls == []


def test_one_empty_lane_spawns_one_refill(tmp_queue, monkeypatch):
    """When BB is empty and SWO has tasks, exactly one refill lands."""
    fake = _FakeView([_lh("SWO", 5), _lh("BUNNYBAGZ", 0)])
    added_calls = []

    def _add_task(text, priority="P1", source="unknown"):
        added_calls.append((text, priority, source))
        return True

    monkeypatch.setattr(lane_autofill, "runnable_view", lambda: fake)
    monkeypatch.setattr(lane_autofill, "add_task", _add_task)

    spawned = lane_autofill.autofill_empty_lanes(queue_path=str(tmp_queue))
    assert spawned == ["BUNNYBAGZ"]
    assert len(added_calls) == 1
    text, priority, source = added_calls[0]
    assert "[BUNNYBAGZ_LANE_REFILL]" in text
    assert "(PROJECT:BUNNYBAGZ)" in text
    assert priority == "P1"
    assert source == "lane_autofill"


def test_idempotent_when_refill_already_pending(tmp_queue, monkeypatch):
    """If a `[<LANE>_LANE_REFILL]` is unchecked in QUEUE.md, do not stack."""
    # Pre-seed a pending refill task in the temp QUEUE.md
    tmp_queue.write_text(
        tmp_queue.read_text()
        + "- [ ] **[BUNNYBAGZ_LANE_REFILL]** earlier autofill (PROJECT:BUNNYBAGZ)\n"
    )

    fake = _FakeView([_lh("SWO", 5), _lh("BUNNYBAGZ", 0)])
    added_calls = []

    def _add_task(text, priority="P1", source="unknown"):
        added_calls.append((text, priority, source))
        return True

    monkeypatch.setattr(lane_autofill, "runnable_view", lambda: fake)
    monkeypatch.setattr(lane_autofill, "add_task", _add_task)

    spawned = lane_autofill.autofill_empty_lanes(queue_path=str(tmp_queue))
    assert spawned == []
    assert added_calls == []


def test_completed_refill_does_not_block_new_one(tmp_queue, monkeypatch):
    """A `[x]`-checked refill (already done) must not block a fresh spawn."""
    tmp_queue.write_text(
        tmp_queue.read_text()
        + "- [x] **[BUNNYBAGZ_LANE_REFILL]** previous autofill — done\n"
    )

    fake = _FakeView([_lh("BUNNYBAGZ", 0)])
    added_calls = []

    def _add_task(text, priority="P1", source="unknown"):
        added_calls.append((text, priority, source))
        return True

    monkeypatch.setattr(lane_autofill, "runnable_view", lambda: fake)
    monkeypatch.setattr(lane_autofill, "add_task", _add_task)

    spawned = lane_autofill.autofill_empty_lanes(queue_path=str(tmp_queue))
    assert spawned == ["BUNNYBAGZ"]
    assert len(added_calls) == 1


def test_both_lanes_empty_spawns_both(tmp_queue, monkeypatch):
    """If both active lanes are empty, both get a refill (one per lane)."""
    fake = _FakeView([_lh("SWO", 0), _lh("BUNNYBAGZ", 0)])
    added_calls = []

    def _add_task(text, priority="P1", source="unknown"):
        added_calls.append((text, priority, source))
        return True

    monkeypatch.setattr(lane_autofill, "runnable_view", lambda: fake)
    monkeypatch.setattr(lane_autofill, "add_task", _add_task)

    spawned = lane_autofill.autofill_empty_lanes(queue_path=str(tmp_queue))
    assert sorted(spawned) == ["BUNNYBAGZ", "SWO"]
    assert len(added_calls) == 2


def test_refill_task_text_references_status_doc():
    """The refill task body must reference the lane's status doc path."""
    text = lane_autofill._refill_task_text("BUNNYBAGZ")
    assert "memory/cron/bunnybagz_phase" in text
    assert "[BUNNYBAGZ_LANE_REFILL]" in text
    assert "(PROJECT:BUNNYBAGZ)" in text
    # Acceptance items (a) (b) (c) (d) referenced
    assert "(a)" in text and "(b)" in text and "(c)" in text and "(d)" in text


def test_refill_already_pending_detection(tmp_path):
    """`_refill_already_pending` matches only unchecked `[ ]` refill lines."""
    q = tmp_path / "QUEUE.md"
    q.write_text(
        "- [x] **[FOO_LANE_REFILL]** old (done)\n"
        "- [ ] **[BAR_LANE_REFILL]** still pending\n"
    )
    assert lane_autofill._refill_already_pending("BAR", queue_path=str(q)) is True
    assert lane_autofill._refill_already_pending("FOO", queue_path=str(q)) is False
    assert lane_autofill._refill_already_pending("BAZ", queue_path=str(q)) is False

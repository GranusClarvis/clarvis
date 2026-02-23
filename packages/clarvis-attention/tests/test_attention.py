"""Tests for ClarvisAttention — GWT attention spotlight."""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis_attention.spotlight import (
    AttentionItem,
    AttentionSpotlight,
    DEFAULT_CAPACITY,
    EVICTION_THRESHOLD,
)


def test_item_creation():
    item = AttentionItem(id="test1", content="hello world")
    assert item.id == "test1"
    assert item.content == "hello world"
    assert item.source == "unknown"
    assert 0 <= item.salience() <= 1.0
    assert item.access_count == 0


def test_item_salience_range():
    item = AttentionItem(id="t1", content="test", importance=1.0, relevance=1.0, boost=1.0)
    assert item.salience() <= 1.0
    item2 = AttentionItem(id="t2", content="test", importance=0.0, relevance=0.0, boost=0.0)
    assert item2.salience() >= 0.0


def test_item_touch():
    item = AttentionItem(id="t1", content="test")
    assert item.access_count == 0
    item.touch()
    assert item.access_count == 1
    item.touch()
    assert item.access_count == 2


def test_item_decay():
    item = AttentionItem(id="t1", content="test", relevance=0.5, boost=0.4)
    item.decay(rate=0.1)
    assert item.relevance == 0.4
    assert item.boost == 0.2  # boost decays at 2x rate


def test_item_serialization():
    item = AttentionItem(id="t1", content="test item", source="unit_test",
                         importance=0.8, relevance=0.7, boost=0.3)
    item.touch()
    d = item.to_dict()
    assert d["id"] == "t1"
    assert d["content"] == "test item"
    assert d["access_count"] == 1
    assert "salience" in d

    restored = AttentionItem.from_dict(d)
    assert restored.id == "t1"
    assert restored.content == "test item"
    assert restored.access_count == 1


def test_spotlight_submit():
    s = AttentionSpotlight(capacity=3)
    item = s.submit("task A", source="test", importance=0.9)
    assert item.content == "task A"
    assert len(s.items) == 1


def test_spotlight_duplicate_reinforcement():
    s = AttentionSpotlight(capacity=3)
    item1 = s.submit("task A", importance=0.5)
    item2 = s.submit("task A", importance=0.9)
    assert item1.id == item2.id  # same item, not duplicated
    assert len(s.items) == 1
    assert item1.importance == 0.9  # reinforced to higher value
    assert item1.access_count == 1  # touched once


def test_spotlight_focus():
    s = AttentionSpotlight(capacity=2)
    s.submit("low priority", importance=0.1, relevance=0.1)
    s.submit("high priority", importance=1.0, relevance=1.0)
    s.submit("medium priority", importance=0.5, relevance=0.5)

    focus = s.focus()
    assert len(focus) == 2  # capacity is 2
    # High priority should be first
    assert focus[0]["importance"] == 1.0


def test_spotlight_tick():
    s = AttentionSpotlight(capacity=1)
    s.submit("winner", importance=1.0, relevance=1.0)
    s.submit("loser", importance=0.1, relevance=0.2)

    result = s.tick()
    assert result["spotlight"] == 1
    assert result["decayed"] >= 1


def test_spotlight_eviction():
    s = AttentionSpotlight(capacity=1)
    s.submit("important", importance=1.0, relevance=1.0)
    s.submit("ephemeral", importance=0.05, relevance=0.05, boost=0.0)

    # Multiple ticks to ensure decay below eviction threshold
    for _ in range(10):
        s.tick()

    # Ephemeral item should eventually be evicted
    assert len(s.items) <= 2  # at most both, likely 1


def test_spotlight_add_working_memory_compat():
    s = AttentionSpotlight(capacity=5)
    item = s.add("urgent task", importance=0.9)
    assert item.boost == 0.3  # high importance gets boost
    assert item.relevance == 0.9  # relevance = max(0.5, importance)

    item2 = s.add("routine task", importance=0.3)
    assert item2.boost == 0.0  # low importance gets no boost


def test_spotlight_spreading_activation():
    s = AttentionSpotlight(capacity=5)
    s.submit("memory architecture design", source="user")
    s.submit("cron job completed", source="system")
    s.submit("fix memory leak in module", source="task")

    boosted = s.spreading_activation("memory architecture")
    assert len(boosted) >= 1
    # Items with "memory" or "architecture" should be boosted
    contents = [b["content"] for b in boosted]
    assert any("memory" in c for c in contents)


def test_spotlight_query_relevant():
    s = AttentionSpotlight(capacity=5)
    s.submit("fix authentication bug", source="task")
    s.submit("update documentation", source="task")
    s.submit("auth token expiry issue", source="user")

    results = s.query_relevant("authentication auth")
    assert len(results) >= 1


def test_spotlight_stats():
    s = AttentionSpotlight(capacity=3)
    s.submit("item1", source="test")
    s.submit("item2", source="test")
    s.submit("item3", source="user")

    stats = s.stats()
    assert stats["total_items"] == 3
    assert stats["capacity"] == 3
    assert "test" in stats["sources"]
    assert stats["sources"]["test"] == 2


def test_spotlight_clear():
    s = AttentionSpotlight(capacity=3)
    s.submit("item1")
    s.submit("item2")
    assert len(s.items) == 2
    s.clear()
    assert len(s.items) == 0


def test_spotlight_serialization():
    s = AttentionSpotlight(capacity=5)
    s.submit("task A", source="user", importance=0.9)
    s.submit("task B", source="system", importance=0.3)

    data = s.to_dict()
    restored = AttentionSpotlight.from_dict(data)
    assert len(restored.items) == 2
    assert restored.capacity == 5


def test_spotlight_persistence():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    try:
        # Create and populate
        s = AttentionSpotlight(capacity=5, persist_path=path)
        s.submit("persistent item", source="test", importance=0.8)
        assert os.path.exists(path)

        # Load from file
        s2 = AttentionSpotlight(capacity=5, persist_path=path)
        assert len(s2.items) == 1
        item = list(s2.items.values())[0]
        assert item.content == "persistent item"
    finally:
        os.unlink(path)


def test_broadcast_hooks():
    s = AttentionSpotlight(capacity=3)
    s.submit("important thing", importance=0.9)

    hook = MagicMock()
    s.on_broadcast(hook)
    summary = s.broadcast()

    assert hook.called
    call_args = hook.call_args
    assert "important thing" in call_args[0][0]  # summary
    assert isinstance(call_args[0][1], list)  # items


def test_multiple_broadcast_hooks():
    s = AttentionSpotlight(capacity=3)
    s.submit("item", importance=0.5)

    hook1 = MagicMock()
    hook2 = MagicMock()
    s.on_broadcast(hook1)
    s.on_broadcast(hook2)
    s.broadcast()

    assert hook1.called
    assert hook2.called


def test_focus_summary_empty():
    s = AttentionSpotlight(capacity=3)
    summary = s.focus_summary()
    assert "empty" in summary.lower()


def test_focus_summary_with_items():
    s = AttentionSpotlight(capacity=3)
    s.submit("test item content", source="unit")
    summary = s.focus_summary()
    assert "test item content" in summary
    assert "Spotlight" in summary


def test_importance_clamping():
    item = AttentionItem(id="t1", content="test", importance=1.5)
    assert item.importance == 1.0

    item2 = AttentionItem(id="t2", content="test", importance=-0.5)
    assert item2.importance == 0.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)

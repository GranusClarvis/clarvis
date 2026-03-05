"""Brain store→recall roundtrip tests."""

import pytest
from clarvis.brain.constants import LEARNINGS, MEMORIES, GOALS


def test_store_and_recall(tmp_brain):
    """Store a memory, recall it by semantic query, verify content."""
    text = "The quick brown fox jumped over the lazy dog"
    mem_id = tmp_brain.store(text, collection=LEARNINGS, importance=0.8)
    assert mem_id is not None

    results = tmp_brain.recall("fox jumped", n=3)
    assert len(results) >= 1
    assert any(text in r["document"] for r in results)


def test_store_multiple_collections(tmp_brain):
    """Store in different collections, recall from each."""
    tmp_brain.store("Goal: reach Phi above 0.80", collection=GOALS, importance=0.9)
    tmp_brain.store("Learned: always test before commit", collection=LEARNINGS, importance=0.7)
    tmp_brain.store("Random memory about weather", collection=MEMORIES, importance=0.5)

    goal_results = tmp_brain.recall("Phi target", n=3, collections=[GOALS])
    assert len(goal_results) >= 1
    assert "Phi" in goal_results[0]["document"]

    learning_results = tmp_brain.recall("test before commit", n=3, collections=[LEARNINGS])
    assert len(learning_results) >= 1


def test_store_with_tags(tmp_brain):
    """Store with tags, verify metadata preserved."""
    mem_id = tmp_brain.store(
        "Critical bug in authentication module",
        collection=LEARNINGS,
        importance=0.95,
        tags=["bug", "security"],
        source="test",
    )
    results = tmp_brain.recall("authentication bug", n=1)
    assert len(results) == 1
    meta = results[0]["metadata"]
    assert meta.get("importance") == 0.95
    assert "bug" in meta.get("tags", "")


def test_stats(tmp_brain):
    """Verify stats reflect stored memories."""
    tmp_brain.store("test memory for stats", collection=MEMORIES, importance=0.5)
    stats = tmp_brain.stats()
    assert stats["total_memories"] >= 1
    assert isinstance(stats["collections"], dict)


def test_health_check(tmp_brain):
    """Health check passes on fresh brain."""
    hc = tmp_brain.health_check()
    assert hc["status"] == "healthy"

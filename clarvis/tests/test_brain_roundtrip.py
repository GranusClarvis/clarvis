"""Brain store→recall roundtrip tests."""

import json
import time
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


def test_parallel_recall_performance(tmp_brain):
    """Recall across multiple collections completes within p95 target (< 2s)."""
    import time

    # Seed multiple collections with data
    for col in [LEARNINGS, MEMORIES, GOALS]:
        for i in range(10):
            tmp_brain.store(f"Test memory {i} about topic {col}", collection=col, importance=0.5 + i * 0.04)

    # Register a slow mock observer to verify it doesn't block recall
    call_log = []

    def slow_observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
        time.sleep(0.5)
        call_log.append(query)

    tmp_brain.register_recall_observer(slow_observer)

    # Recall should return fast despite slow observer
    start = time.time()
    results = tmp_brain.recall("topic about test memory", n=5)
    elapsed = time.time() - start

    assert len(results) >= 1
    assert elapsed < 2.0, f"Recall took {elapsed:.2f}s, expected < 2.0s (p95 target)"

    # Give observer time to complete in background
    time.sleep(1.0)
    assert len(call_log) >= 1, "Observer should have fired asynchronously"


def test_recall_observer_does_not_mutate_caller_results(tmp_brain):
    """Observers get a deep copy, so mutations don't affect caller's results."""
    tmp_brain.store("important fact about testing", collection=LEARNINGS, importance=0.9)

    mutations = []

    def mutating_observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
        for r in results:
            r["document"] = "MUTATED"
        mutations.append(True)

    tmp_brain.register_recall_observer(mutating_observer)

    results = tmp_brain.recall("important fact", n=3)
    import time
    time.sleep(0.5)

    # Original results should be unaffected
    assert any("important" in r["document"] for r in results), "Observer mutation leaked to caller"


def test_actr_scorer_boosts_recent_and_frequent(tmp_brain):
    """ACT-R scorer: test core invariants with above-threshold activations.

    Uses 3+ accesses per memory so base-level activation exceeds
    RETRIEVAL_TAU (-2.0). Tests frequency, recency, and hook wiring.
    Note: memories with <3 accesses fall below threshold and get clipped
    to the same floor score — this is a known calibration gap (subtask _4).
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    from actr_activation import actr_score

    now_ts = time.time()
    hour = 3600
    day = 86400

    def make_result(rid, access_times_list):
        return {
            "id": rid,
            "document": f"memory {rid}",
            "collection": LEARNINGS,
            "distance": 0.5,
            "metadata": {
                "importance": 0.5,
                "access_times": json.dumps(access_times_list),
            },
            "related": [],
        }

    # FREQUENCY: 5 spaced accesses > 3 spaced accesses (same recency window)
    freq_5 = make_result("freq-5", [
        now_ts - 10 * day, now_ts - 8 * day, now_ts - 6 * day,
        now_ts - 4 * day, now_ts - 2 * day,
    ])
    freq_3 = make_result("freq-3", [
        now_ts - 6 * day, now_ts - 4 * day, now_ts - 2 * day,
    ])
    s5 = actr_score(freq_5)
    s3 = actr_score(freq_3)
    assert s5 > s3, \
        f"Frequency: 5 accesses ({s5:.4f}) should beat 3 accesses ({s3:.4f})"

    # RECENCY: 3 recent accesses > 3 old accesses (same count + spacing ratio)
    recent_3 = make_result("recent-3", [
        now_ts - 6 * hour, now_ts - 3 * hour, now_ts - 1 * hour,
    ])
    old_3 = make_result("old-3", [
        now_ts - 60 * day, now_ts - 30 * day, now_ts - 10 * day,
    ])
    sr = actr_score(recent_3)
    so = actr_score(old_3)
    assert sr > so, \
        f"Recency: recent 3 ({sr:.4f}) should beat old 3 ({so:.4f})"

    # ACCESSED > NEVER: 3 accesses beats reconstructed-from-metadata
    never = {
        "id": "never", "document": "never accessed", "collection": LEARNINGS,
        "distance": 0.5,
        "metadata": {"importance": 0.5, "created_at": "2025-12-01T00:00:00+00:00"},
        "related": [],
    }
    sn = actr_score(never)
    assert s3 > sn, \
        f"Accessed ({s3:.4f}) should beat never-accessed ({sn:.4f})"

    # Hook wiring: register scorer and verify reranking through brain
    def actr_scorer_hook(results):
        for r in results:
            boost = r["metadata"].get("_attention_boost", 0)
            r["_actr_score"] = actr_score(r) + boost * 0.15

    tmp_brain.register_recall_scorer(actr_scorer_hook)

    for r in [freq_5, freq_3, never]:
        col = tmp_brain.collections[LEARNINGS]
        col.add(ids=[r["id"]], documents=[r["document"]], metadatas=[r["metadata"]])

    results = tmp_brain.recall("memory", n=3, collections=[LEARNINGS])
    time.sleep(0.5)

    assert len(results) == 3
    assert results[0]["id"] == "freq-5", \
        f"Expected freq-5 first, got {results[0]['id']}"
    assert results[-1]["id"] == "never", \
        f"Expected never last, got {results[-1]['id']}"

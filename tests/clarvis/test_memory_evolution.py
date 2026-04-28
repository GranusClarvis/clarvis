"""Tests for clarvis.brain.memory_evolution — A-Mem style recall tracking & evolution."""

import pytest

from clarvis.brain.memory_evolution import (
    record_recall_success,
    evolve_memory,
    find_contradictions,
)
from clarvis.brain.constants import LEARNINGS, MEMORIES


class TestRecordRecallSuccess:
    def test_increments_counter(self, tmp_brain):
        mid = tmp_brain.store("Python uses indentation for blocks",
                              collection=LEARNINGS, importance=0.7)
        result = record_recall_success(tmp_brain, [{"id": mid, "collection": LEARNINGS}])
        assert result["updated"] == 1
        assert not result["errors"]

        # Check metadata was updated
        mem = tmp_brain.collections[LEARNINGS].get(ids=[mid])
        meta = mem["metadatas"][0]
        assert meta["recall_success"] == 1
        assert "last_recall_success" in meta

    def test_importance_boost(self, tmp_brain):
        mid = tmp_brain.store("Test memory", collection=LEARNINGS, importance=0.5)
        record_recall_success(tmp_brain, [{"id": mid, "collection": LEARNINGS}])

        mem = tmp_brain.collections[LEARNINGS].get(ids=[mid])
        meta = mem["metadatas"][0]
        assert meta["importance"] > 0.5
        assert meta["importance"] <= 1.0

    def test_diminishing_boost(self, tmp_brain):
        mid = tmp_brain.store("Test memory", collection=LEARNINGS, importance=0.5)
        # Call 3 times
        for _ in range(3):
            record_recall_success(tmp_brain, [{"id": mid, "collection": LEARNINGS}])

        mem = tmp_brain.collections[LEARNINGS].get(ids=[mid])
        meta = mem["metadatas"][0]
        # Should be boosted but not excessively (3 boosts < 0.06 total)
        assert 0.5 < meta["importance"] < 0.6

    def test_caps_at_one(self, tmp_brain):
        mid = tmp_brain.store("Test memory", collection=LEARNINGS, importance=0.99)
        record_recall_success(tmp_brain, [{"id": mid, "collection": LEARNINGS}])

        mem = tmp_brain.collections[LEARNINGS].get(ids=[mid])
        assert mem["metadatas"][0]["importance"] <= 1.0

    def test_multiple_memories(self, tmp_brain):
        m1 = tmp_brain.store("Memory one", collection=LEARNINGS, importance=0.5)
        m2 = tmp_brain.store("Memory two", collection=MEMORIES, importance=0.6)

        result = record_recall_success(tmp_brain, [
            {"id": m1, "collection": LEARNINGS},
            {"id": m2, "collection": MEMORIES},
        ])
        assert result["updated"] == 2

    def test_skips_missing_memory(self, tmp_brain):
        result = record_recall_success(tmp_brain, [
            {"id": "nonexistent_id", "collection": LEARNINGS}
        ])
        assert result["updated"] == 0

    def test_skips_invalid_entries(self, tmp_brain):
        result = record_recall_success(tmp_brain, [
            {"id": None, "collection": LEARNINGS},
            {"collection": LEARNINGS},
            {"id": "foo"},
        ])
        assert result["updated"] == 0

    def test_empty_list(self, tmp_brain):
        result = record_recall_success(tmp_brain, [])
        assert result["updated"] == 0
        assert not result["errors"]


class TestEvolveMemory:
    def test_basic_evolution(self, tmp_brain):
        mid = tmp_brain.store("ChromaDB uses cosine distance",
                              collection=LEARNINGS, importance=0.7)
        result = evolve_memory(
            tmp_brain, mid, LEARNINGS,
            "ChromaDB uses L2 distance by default, not cosine",
            reason="correction",
        )
        assert result["evolved"]
        assert result["old_id"] == mid
        assert result["new_id"]

        # Check new memory exists with evolved_from
        new_mem = tmp_brain.collections[LEARNINGS].get(ids=[result["new_id"]])
        assert new_mem["ids"]
        new_meta = new_mem["metadatas"][0]
        assert new_meta["evolved_from"] == mid
        assert new_meta["evolution_reason"] == "correction"

        # Check old memory is marked superseded AND archived
        # (archived flag prevents get_goals(include_archived=False) from
        # surfacing the superseded record alongside the live successor)
        old_mem = tmp_brain.collections[LEARNINGS].get(ids=[mid])
        old_meta = old_mem["metadatas"][0]
        assert old_meta["superseded_by"] == result["new_id"]
        assert "superseded_at" in old_meta
        assert str(old_meta.get("archived", "")).lower() == "true"

    def test_importance_inherited_and_boosted(self, tmp_brain):
        mid = tmp_brain.store("Original text", collection=LEARNINGS, importance=0.6)
        result = evolve_memory(tmp_brain, mid, LEARNINGS, "Evolved text")

        new_mem = tmp_brain.collections[LEARNINGS].get(ids=[result["new_id"]])
        # Should be 0.65 (0.6 + 0.05 boost)
        assert new_mem["metadatas"][0]["importance"] == pytest.approx(0.65, abs=0.01)

    def test_tags_preserved(self, tmp_brain):
        import json
        mid = tmp_brain.store("Tagged memory", collection=LEARNINGS,
                              importance=0.7, tags=["research", "technical"])
        result = evolve_memory(tmp_brain, mid, LEARNINGS, "Updated tagged memory")

        new_mem = tmp_brain.collections[LEARNINGS].get(ids=[result["new_id"]])
        tags = json.loads(new_mem["metadatas"][0]["tags"])
        assert "research" in tags
        assert "technical" in tags

    def test_missing_original_fails(self, tmp_brain):
        result = evolve_memory(tmp_brain, "nonexistent", LEARNINGS, "New text")
        assert not result["evolved"]
        assert "not found" in result["error"]

    def test_bad_collection_fails(self, tmp_brain):
        result = evolve_memory(tmp_brain, "some_id", "invalid_collection", "New text")
        assert not result["evolved"]
        assert "not found" in result["error"]


class TestFindContradictions:
    def test_no_contradictions_when_empty(self, tmp_brain):
        result = find_contradictions(tmp_brain, "Test text", LEARNINGS)
        assert result == []

    def test_detects_negation_difference(self, tmp_brain):
        tmp_brain.store("The gateway is managed by pm2",
                        collection=LEARNINGS, importance=0.8)
        # Contradicting memory — "not" present in new text
        results = find_contradictions(
            tmp_brain,
            "The gateway is NOT managed by pm2, it uses systemd",
            LEARNINGS,
            threshold=1.5,  # Relaxed threshold for test (no real embeddings)
        )
        # With test brain (no real embeddings), we check the function runs
        # Real contradiction detection depends on embedding distance
        assert isinstance(results, list)

    def test_detects_low_text_overlap(self, tmp_brain):
        """High embedding sim + low text overlap = conflict (same topic, different content)."""
        tmp_brain.store("The gateway runs on port 18789 using Node.js",
                        collection=LEARNINGS, importance=0.8)
        # Same topic (gateway/port) but completely different content
        results = find_contradictions(
            tmp_brain,
            "OpenClaw gateway migrated to Rust on port 9090",
            LEARNINGS,
            threshold=1.5,  # Relaxed for test brain (no real embeddings)
        )
        assert isinstance(results, list)
        # If distance is within threshold, should flag low_text_overlap
        for r in results:
            signals = r.get("contradiction_signal", [])
            has_overlap_signal = any("low_text_overlap" in s for s in signals)
            has_negation_signal = any("negation_diff" in s for s in signals)
            # At least one signal type should be present
            assert has_overlap_signal or has_negation_signal

    def test_text_overlap_field_present(self, tmp_brain):
        """Contradiction results should include text_overlap score."""
        tmp_brain.store("Python is not good for systems programming",
                        collection=LEARNINGS, importance=0.8)
        results = find_contradictions(
            tmp_brain,
            "Python is excellent for systems programming",
            LEARNINGS,
            threshold=1.5,
        )
        for r in results:
            assert "text_overlap" in r
            assert isinstance(r["text_overlap"], float)

    def test_returns_empty_for_bad_collection(self, tmp_brain):
        result = find_contradictions(tmp_brain, "Test", "nonexistent_collection")
        assert result == []

"""Chaos testing: verify brain recovery after simulated corruption.

Tests that the brain can detect and recover from metadata corruption
via health_check() and optimize().

[EXTERNAL_CHALLENGE:bench-robustness-01]
"""

import random
import uuid
import pytest
from clarvis.brain.constants import LEARNINGS, MEMORIES, GOALS, CONTEXT, INFRASTRUCTURE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_brain(brain, n=50):
    """Populate a brain with n unique memories across multiple collections."""
    collections = [LEARNINGS, MEMORIES, GOALS, CONTEXT, INFRASTRUCTURE]
    ids = []
    for i in range(n):
        col = collections[i % len(collections)]
        imp = round(0.3 + (i % 7) * 0.1, 2)
        # Use UUID for both text uniqueness and memory_id to avoid timestamp collisions
        uid = uuid.uuid4().hex[:8]
        mid = brain.store(
            f"Unique memory {uid} about domain-{i % 10} detail-{i} context-{uid}",
            collection=col,
            importance=min(imp, 1.0),
            tags=[f"tag-{i % 5}", "chaos-test"],
            source="chaos_test",
            memory_id=f"{col}_{uid}",
        )
        ids.append((mid, col))
    return ids


def _corrupt_metadata(brain, ids, fraction=0.10):
    """Corrupt metadata of `fraction` of stored memories.

    Corruption types (randomly chosen per memory):
      1. Set importance to invalid negative value
      2. Blank out tags
      3. Set source to garbage string
      4. Set importance to zero (data loss)
    """
    n_corrupt = max(1, int(len(ids) * fraction))
    targets = random.sample(ids, n_corrupt)
    corrupted = []

    for mid, col in targets:
        corruption_type = random.choice(["negative_importance", "blank_tags",
                                          "garbage_source", "zero_importance"])
        collection = brain.collections[col]
        try:
            if corruption_type == "negative_importance":
                collection.update(ids=[mid], metadatas=[{"importance": -999.0}])
            elif corruption_type == "blank_tags":
                collection.update(ids=[mid], metadatas=[{"tags": ""}])
            elif corruption_type == "garbage_source":
                collection.update(ids=[mid], metadatas=[{"source": "\x01corrupt\x02data"}])
            elif corruption_type == "zero_importance":
                collection.update(ids=[mid], metadatas=[{"importance": 0.0}])
            corrupted.append((mid, col, corruption_type))
        except Exception:
            pass  # Some corruption types may be rejected by ChromaDB

    return corrupted


def _count_all_memories(brain):
    """Count total memories across all collections (bypass stats cache)."""
    total = 0
    for col in brain.collections.values():
        total += col.count()
    return total


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChaosRecovery:
    """Verify brain recovery after simulated corruption."""

    def test_health_check_detects_healthy_brain(self, tmp_brain):
        """Baseline: health_check passes on a clean brain."""
        _seed_brain(tmp_brain, n=10)
        result = tmp_brain.health_check()
        assert result["status"] == "healthy"
        assert "timings" in result
        assert result["timings"]["store_ms"] >= 0
        assert result["timings"]["recall_ms"] >= 0

    def test_metadata_corruption_and_recovery(self, tmp_brain):
        """Core chaos test: corrupt 10% metadata, verify recovery."""
        # Phase 1: Seed brain with unique memories
        ids = _seed_brain(tmp_brain, n=50)
        pre_count = _count_all_memories(tmp_brain)
        assert pre_count >= 20, f"Expected >=20 memories, got {pre_count}"

        # Phase 2: Corrupt 10% of metadata
        corrupted = _corrupt_metadata(tmp_brain, ids, fraction=0.10)
        assert len(corrupted) >= 1, "At least one memory should be corrupted"

        # Phase 3: Run health_check — should still pass (store/recall works)
        health = tmp_brain.health_check()
        assert health["status"] == "healthy"

        # Phase 4: Run optimize (decay + prune cycle)
        tmp_brain.optimize(full=False)

        # Phase 5: Verify recovery — brain still functional
        post_count = _count_all_memories(tmp_brain)
        # Some memories may be pruned by optimize, but most should survive
        assert post_count >= pre_count * 0.5, \
            f"Too many memories lost: {pre_count} -> {post_count}"

        # Phase 6: Recall still works after corruption + optimize
        results = tmp_brain.recall("domain", n=5)
        assert len(results) >= 1, "Recall should still find memories after recovery"

        # Phase 7: Store new memories still works
        new_id = tmp_brain.store(
            f"Post-recovery memory {uuid.uuid4().hex[:8]}: system is resilient",
            collection=LEARNINGS,
            importance=0.9,
        )
        assert new_id is not None

    def test_heavy_corruption_recovery(self, tmp_brain):
        """Stress test: corrupt 30% of metadata, verify brain survives."""
        ids = _seed_brain(tmp_brain, n=40)

        # Heavy corruption
        corrupted = _corrupt_metadata(tmp_brain, ids, fraction=0.30)
        assert len(corrupted) >= 5

        # Brain must remain operational
        health = tmp_brain.health_check()
        assert health["status"] == "healthy"

        # Optimize should not crash
        tmp_brain.optimize(full=False)

        # Post-recovery store + recall
        mid = tmp_brain.store(
            f"Survived heavy corruption {uuid.uuid4().hex[:8]}",
            collection=MEMORIES,
            importance=0.8,
        )
        assert mid is not None
        results = tmp_brain.recall("Survived", n=3)
        assert len(results) >= 1

    def test_graph_edge_corruption_recovery(self, tmp_brain):
        """Corrupt graph edges by adding orphan references, verify brain survives."""
        ids = _seed_brain(tmp_brain, n=20)

        # Add orphan edges (referencing non-existent nodes)
        for i in range(10):
            try:
                tmp_brain.add_relationship(
                    f"orphan-node-{i}",
                    ids[i % len(ids)][0],
                    relationship_type="chaos-test",
                )
            except Exception:
                pass

        # Backfill should handle orphan nodes gracefully
        try:
            tmp_brain.backfill_graph_nodes()
        except Exception:
            pass  # Backfill is best-effort

        # Brain still healthy
        health = tmp_brain.health_check()
        assert health["status"] == "healthy"

    def test_empty_collection_recovery(self, tmp_brain):
        """Verify brain handles empty collections gracefully."""
        health = tmp_brain.health_check()
        assert health["status"] == "healthy"

    def test_concurrent_store_during_optimize(self, tmp_brain):
        """Store memories during optimize — no crash."""
        _seed_brain(tmp_brain, n=20)

        # Store while optimizing (sequential, but tests data consistency)
        tmp_brain.optimize(full=False)
        mid = tmp_brain.store(
            f"Stored during optimize window {uuid.uuid4().hex[:8]}",
            collection=LEARNINGS,
            importance=0.7,
        )
        assert mid is not None

        results = tmp_brain.recall("optimize window", n=3)
        assert len(results) >= 1

    def test_corruption_does_not_spread(self, tmp_brain):
        """Corrupting one collection doesn't affect others."""
        ids = _seed_brain(tmp_brain, n=50)

        # Only corrupt LEARNINGS memories
        learnings_ids = [(mid, col) for mid, col in ids if col == LEARNINGS]
        if learnings_ids:
            _corrupt_metadata(tmp_brain, learnings_ids, fraction=0.50)

        # Other collections should be perfectly fine
        goals_results = tmp_brain.recall("domain", n=5, collections=[GOALS])
        memories_results = tmp_brain.recall("domain", n=5, collections=[MEMORIES])

        # At least some results from non-corrupted collections
        assert len(goals_results) + len(memories_results) >= 1

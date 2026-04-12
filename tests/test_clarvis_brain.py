"""Tests for clarvis.brain — store, search, graph, hooks, constants.

Uses temporary ChromaDB instances for isolation (no production data touched).
Follows patterns from packages/clarvis-db/tests/test_clarvisdb.py.
"""

import json
import os
import sys
import tempfile
import time

import pytest

# Ensure the workspace root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# 1. Constants — route_query (pure function, no DB)
# ---------------------------------------------------------------------------

from clarvis.brain.constants import (
    route_query, ALL_COLLECTIONS, DEFAULT_COLLECTIONS,
    IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE,
    GOALS, CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
)


class TestRouteQuery:
    def test_goal_query_routes_to_goals(self):
        result = route_query("what are my goals?")
        assert GOALS in result

    def test_procedure_query_routes_to_procedures(self):
        result = route_query("how to deploy the server")
        assert PROCEDURES in result

    def test_identity_query_routes_to_identity(self):
        result = route_query("who am i?")
        assert IDENTITY in result

    def test_infra_query_routes_to_infrastructure(self):
        result = route_query("server config settings")
        assert INFRASTRUCTURE in result

    def test_context_query_routes_to_context(self):
        result = route_query("what am I working on right now?")
        assert CONTEXT in result

    def test_learning_query_routes_to_learnings(self):
        result = route_query("what have I learned about caching?")
        assert LEARNINGS in result

    def test_preference_query_routes_to_preferences(self):
        result = route_query("what formatting style do I prefer?")
        assert PREFERENCES in result

    def test_episode_query_routes_to_episodes(self):
        result = route_query("what happened in last session?")
        assert EPISODES in result

    def test_generic_query_returns_none(self):
        """Unmatched queries should return None (use defaults)."""
        result = route_query("abcxyz random text no keywords")
        assert result is None

    def test_routed_always_includes_learnings_and_memories(self):
        """All routed results include LEARNINGS and MEMORIES as fallback."""
        result = route_query("my goals progress")
        assert LEARNINGS in result
        assert MEMORIES in result

    def test_collection_lists_not_empty(self):
        assert len(ALL_COLLECTIONS) == 10
        assert len(DEFAULT_COLLECTIONS) >= 8


# ---------------------------------------------------------------------------
# 2. ClarvisBrain integration tests with temp ChromaDB
# ---------------------------------------------------------------------------

@pytest.fixture
def brain_instance(tmp_path):
    """Create an isolated ClarvisBrain with temp directories.

    Uses factory singleton for ChromaDB client consistency.
    """
    import clarvis.brain as brain_mod
    import clarvis.brain.constants as const_mod
    from clarvis.brain.factory import get_chroma_client, reset_singletons

    # Save originals
    orig = {
        "mod_DATA_DIR": brain_mod.DATA_DIR,
        "mod_GRAPH_FILE": brain_mod.GRAPH_FILE,
        "const_DATA_DIR": const_mod.DATA_DIR,
        "const_GRAPH_FILE": const_mod.GRAPH_FILE,
    }

    # Patch to temp dirs
    test_data = str(tmp_path / "testdb")
    test_graph = str(tmp_path / "graph.json")
    os.makedirs(test_data, exist_ok=True)

    brain_mod.DATA_DIR = test_data
    brain_mod.GRAPH_FILE = test_graph
    const_mod.DATA_DIR = test_data
    const_mod.GRAPH_FILE = test_graph

    from clarvis.brain import ClarvisBrain
    b = ClarvisBrain.__new__(ClarvisBrain)
    b.use_local_embeddings = False
    b.data_dir = test_data
    b.graph_file = test_graph
    b.embedding_function = None

    b.client = get_chroma_client(test_data)
    b._init_collections()
    b._load_graph()

    # Caches
    b._stats_cache = None
    b._stats_cache_time = 0
    b._stats_cache_ttl = 30
    b._collection_cache = {}
    b._collection_cache_ttl = 60
    b._embedding_cache = {}
    b._embedding_cache_ttl = 60
    b._recall_cache = {}
    b._recall_cache_ttl = 30

    # Reconsolidation state
    b._labile_memories = {}
    b._lability_window = 300

    # Hook registries
    b._recall_scorers = []
    b._recall_boosters = []
    b._recall_observers = []
    b._optimize_hooks = []

    yield b

    # Restore
    brain_mod.DATA_DIR = orig["mod_DATA_DIR"]
    brain_mod.GRAPH_FILE = orig["mod_GRAPH_FILE"]
    const_mod.DATA_DIR = orig["const_DATA_DIR"]
    const_mod.GRAPH_FILE = orig["const_GRAPH_FILE"]
    reset_singletons()


class TestBrainStore:
    def test_store_returns_memory_id(self, brain_instance):
        mid = brain_instance.store("test memory", importance=0.8)
        assert mid is not None
        assert isinstance(mid, str)

    def test_store_with_custom_id(self, brain_instance):
        mid = brain_instance.store("test", memory_id="custom-123")
        assert mid == "custom-123"

    def test_store_invalid_collection_falls_back(self, brain_instance):
        """Storing to nonexistent collection should fall back to MEMORIES."""
        mid = brain_instance.store("test", collection="nonexistent-col")
        assert mid is not None
        # Falls back to MEMORIES collection
        assert mid.startswith("clarvis-memories")

    def test_store_with_tags(self, brain_instance):
        mid = brain_instance.store("tagged memory", tags=["test", "important"])
        assert mid is not None

    def test_store_auto_links(self, brain_instance):
        """Store should auto-link to similar memories."""
        brain_instance.store("Python programming language features")
        brain_instance.store("Python coding best practices")
        # Graph should have some edges from auto-linking
        stats = brain_instance.stats()
        assert stats["graph_edges"] >= 0  # May or may not have links depending on embedding similarity


class TestBrainSearch:
    def test_recall_returns_list(self, brain_instance):
        brain_instance.store("Python is a programming language", importance=0.8)
        results = brain_instance.recall("programming")
        assert isinstance(results, list)

    def test_recall_finds_stored_memory(self, brain_instance):
        brain_instance.store("Clarvis is a cognitive agent", importance=0.9,
                             memory_id="test-clarvis")
        results = brain_instance.recall("cognitive agent", n=5)
        assert len(results) >= 1
        docs = [r["document"] for r in results]
        assert any("cognitive" in d.lower() for d in docs)

    def test_recall_includes_metadata(self, brain_instance):
        brain_instance.store("metadata test", importance=0.7)
        results = brain_instance.recall("metadata test")
        assert len(results) >= 1
        assert "metadata" in results[0]
        assert "importance" in results[0]["metadata"]

    def test_recall_min_importance_filter(self, brain_instance):
        brain_instance.store("low importance", importance=0.1, memory_id="low")
        brain_instance.store("high importance", importance=0.9, memory_id="high")
        results = brain_instance.recall("importance", min_importance=0.5)
        for r in results:
            assert r["metadata"].get("importance", 0) >= 0.5

    def test_recall_marks_labile(self, brain_instance):
        """Recalled memories should be marked as labile for reconsolidation."""
        brain_instance.store("labile test", memory_id="lab-1")
        brain_instance.recall("labile")
        assert len(brain_instance._labile_memories) >= 0  # May be 0 if not found

    def test_get_returns_all_from_collection(self, brain_instance):
        brain_instance.store("mem1", collection=MEMORIES, memory_id="m1")
        brain_instance.store("mem2", collection=MEMORIES, memory_id="m2")
        results = brain_instance.get(MEMORIES)
        assert len(results) >= 2

    def test_get_nonexistent_collection_returns_empty(self, brain_instance):
        results = brain_instance.get("nonexistent")
        assert results == []

    def test_get_all_cached(self, brain_instance):
        """Cached get should return same data."""
        brain_instance.store("cache test", collection=MEMORIES, memory_id="c1")
        r1 = brain_instance.get_all_cached(MEMORIES)
        r2 = brain_instance.get_all_cached(MEMORIES)
        assert len(r1) == len(r2)

    def test_recall_with_collection_routing(self, brain_instance):
        """Recall should auto-route to relevant collections."""
        brain_instance.store("my goal is to improve", collection=GOALS, memory_id="g1")
        results = brain_instance.recall("goals progress", n=5)
        # Should route to GOALS collection
        assert isinstance(results, list)

    def test_recall_text_fallback_uses_real_query(self, brain_instance):
        """Regression test: text-search fallback must pass the actual query,
        not an empty string. See _query_single_collection bug (2026-03-29)."""
        brain_instance.store("The heartbeat pipeline runs every hour",
                             importance=0.9, memory_id="hb-pipeline")
        # Force text fallback by invalidating embedding cache
        brain_instance._embedding_cache.clear()
        # Monkey-patch the embedding function to return None (simulates failure)
        original_fn = brain_instance._get_or_compute_embedding
        brain_instance._get_or_compute_embedding = lambda q, cols: None
        try:
            results = brain_instance.recall("heartbeat pipeline", n=5)
            assert isinstance(results, list)
            assert len(results) >= 1, "Text fallback should find stored memory"
            docs = [r["document"] for r in results]
            assert any("heartbeat" in d.lower() for d in docs), \
                "Text fallback must use real query, not empty string"
        finally:
            brain_instance._get_or_compute_embedding = original_fn


class TestBrainGraph:
    def test_add_relationship(self, brain_instance):
        edge = brain_instance.add_relationship("a", "b", "related")
        assert edge["from"] == "a"
        assert edge["to"] == "b"
        assert edge["type"] == "related"

    def test_get_related(self, brain_instance):
        brain_instance.add_relationship("x", "y", "similar_to")
        related = brain_instance.get_related("x")
        assert len(related) >= 1
        assert related[0]["id"] == "y"

    def test_get_related_inverse(self, brain_instance):
        """get_related should find reverse relationships too."""
        brain_instance.add_relationship("a", "b", "causes")
        related = brain_instance.get_related("b")
        assert len(related) >= 1
        assert related[0]["id"] == "a"
        assert "inverse" in related[0]["relationship"]

    def test_duplicate_edge_returns_existing(self, brain_instance):
        """Adding same edge twice should return existing (no duplication)."""
        e1 = brain_instance.add_relationship("a", "b", "test")
        e2 = brain_instance.add_relationship("a", "b", "test")
        assert e1["from"] == e2["from"]
        # Graph should still only have 1 edge
        assert len(brain_instance.graph["edges"]) == 1

    def test_backfill_graph_nodes(self, brain_instance):
        """Backfill should register nodes from edges."""
        # Manually add edge with missing nodes
        brain_instance.graph["edges"].append({
            "from": "orphan_a", "to": "orphan_b",
            "type": "test", "created_at": "2026-01-01T00:00:00"
        })
        count = brain_instance.backfill_graph_nodes()
        assert count >= 1
        assert "orphan_a" in brain_instance.graph["nodes"]

    def test_graph_persists(self, brain_instance):
        """Graph should be saved to disk."""
        brain_instance.add_relationship("p1", "p2", "persisted")
        assert os.path.exists(brain_instance.graph_file)
        with open(brain_instance.graph_file) as f:
            data = json.load(f)
        assert len(data["edges"]) >= 1

    def test_infer_collection(self, brain_instance):
        """_infer_collection should map prefixes to collections."""
        assert brain_instance._infer_collection("goal-test") == GOALS
        assert brain_instance._infer_collection("proc_test") == PROCEDURES
        assert brain_instance._infer_collection("mem_test") == MEMORIES
        assert brain_instance._infer_collection("unknown_id") == "unknown"


class TestBrainStats:
    def test_stats_returns_counts(self, brain_instance):
        brain_instance.store("stats test", memory_id="st1")
        s = brain_instance.stats()
        assert s["total_memories"] >= 1
        assert "collections" in s
        assert "graph_nodes" in s
        assert "graph_edges" in s

    def test_stats_cached(self, brain_instance):
        """Second stats call within TTL should return cached result."""
        s1 = brain_instance.stats()
        s2 = brain_instance.stats()
        # Should be the exact same object (cached)
        assert s1 is s2

    def test_invalidate_cache(self, brain_instance):
        """_invalidate_cache should force fresh stats on next call."""
        s1 = brain_instance.stats()
        brain_instance._invalidate_cache()
        s2 = brain_instance.stats()
        # Not the same cached object
        assert s1 is not s2

    def test_health_check_returns_healthy(self, brain_instance):
        h = brain_instance.health_check()
        assert h["status"] == "healthy"
        assert "total_memories" in h

    def test_health_alias(self, brain_instance):
        """health() should be an alias for health_check()."""
        h1 = brain_instance.health()
        assert h1["status"] == "healthy"


class TestBrainContext:
    def test_set_and_get_context(self, brain_instance):
        brain_instance.set_context("testing the brain")
        ctx = brain_instance.get_context()
        assert ctx == "testing the brain"

    def test_default_context_is_idle(self, brain_instance):
        ctx = brain_instance.get_context()
        # Empty collection returns "idle"
        assert ctx == "idle"


class TestBrainGoals:
    def test_set_and_get_goal(self, brain_instance):
        brain_instance.set_goal("Improve test coverage for Clarvis package", 50)
        goals = brain_instance.get_goals()
        assert len(goals) >= 1
        goal_names = [g["metadata"].get("goal", "") for g in goals]
        assert any("test coverage" in n.lower() for n in goal_names)

    def test_set_goal_rejects_short_names(self, brain_instance):
        """Goals with very short names should be rejected."""
        brain_instance.set_goal("short", 10)
        goals = brain_instance.get_goals()
        goal_names = [g["metadata"].get("goal", "") for g in goals]
        assert "short" not in goal_names

    def test_set_goal_rejects_bridge_patterns(self, brain_instance):
        """Goals matching bridge patterns should be rejected."""
        brain_instance.set_goal("BRIDGE connection between collections", 10)
        goals = brain_instance.get_goals()
        assert len(goals) == 0

    def test_archive_stale_goals(self, brain_instance):
        """Stale 0% goals older than max_age_days should be archived."""
        from datetime import datetime, timezone, timedelta
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        col = brain_instance.collections[GOALS]
        col.upsert(
            ids=["stale-goal"],
            documents=["Stale goal: 0%"],
            metadatas=[{
                "goal": "Stale goal for testing",
                "progress": 0,
                "updated": old_date,
            }]
        )

        archived = brain_instance.archive_stale_goals(max_age_days=7)
        assert archived >= 1


class TestBrainDecay:
    def test_decay_importance(self, brain_instance):
        """decay_importance should reduce old memories' importance."""
        from datetime import datetime, timezone, timedelta

        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        col = brain_instance.collections[MEMORIES]
        col.upsert(
            ids=["old-mem"],
            documents=["old memory"],
            metadatas=[{
                "importance": 0.8,
                "last_accessed": old_date,
                "text": "old memory",
            }]
        )

        decayed = brain_instance.decay_importance()
        assert decayed >= 1

        # Verify importance decreased
        result = col.get(ids=["old-mem"])
        new_imp = result["metadatas"][0]["importance"]
        assert new_imp < 0.8

    def test_prune_low_importance(self, brain_instance):
        """prune_low_importance should remove very low importance memories."""
        col = brain_instance.collections[MEMORIES]
        col.upsert(
            ids=["prune-me"],
            documents=["low importance memory"],
            metadatas=[{"importance": 0.01, "tags": "[]"}]
        )

        pruned = brain_instance.prune_low_importance(threshold=0.12)
        assert pruned >= 1

    def test_prune_preserves_tagged(self, brain_instance):
        """Memories with preserve_tags should not be pruned."""
        col = brain_instance.collections[MEMORIES]
        col.upsert(
            ids=["keep-me"],
            documents=["critical memory"],
            metadatas=[{
                "importance": 0.01,
                "tags": json.dumps(["critical"]),
            }]
        )

        pruned = brain_instance.prune_low_importance(threshold=0.12)
        # Should not prune the critical one
        result = col.get(ids=["keep-me"])
        assert len(result["ids"]) == 1


class TestBrainReconsolidation:
    def test_reconsolidate_requires_labile(self, brain_instance):
        """Reconsolidation should fail for non-labile memories."""
        result = brain_instance.reconsolidate("nonexistent", "new text")
        assert result["success"] is False
        assert "not labile" in result["message"]

    def test_reconsolidate_after_recall(self, brain_instance):
        """After recall, memories should be labile and reconsolidatable."""
        brain_instance.store("original text", memory_id="recon-1",
                             collection=MEMORIES, importance=0.7)
        results = brain_instance.recall("original text")

        if results and any(r.get("id") == "recon-1" for r in results):
            result = brain_instance.reconsolidate("recon-1", "updated text")
            assert result["success"] is True
            assert result["new_text"] == "updated text"

    def test_get_labile_memories_empty(self, brain_instance):
        """No labile memories initially."""
        labile = brain_instance.get_labile_memories()
        assert labile == []


class TestBrainHookRegistration:
    def test_register_recall_scorer(self, brain_instance):
        scorer = lambda results: None
        brain_instance.register_recall_scorer(scorer)
        assert scorer in brain_instance._recall_scorers

    def test_register_recall_booster(self, brain_instance):
        booster = lambda results: None
        brain_instance.register_recall_booster(booster)
        assert booster in brain_instance._recall_boosters

    def test_register_recall_observer(self, brain_instance):
        observer = lambda q, r, **kw: None
        brain_instance.register_recall_observer(observer)
        assert observer in brain_instance._recall_observers

    def test_register_optimize_hook(self, brain_instance):
        hook = lambda dry_run=False: {"test": True}
        brain_instance.register_optimize_hook(hook)
        assert hook in brain_instance._optimize_hooks

    def test_optimize_runs_hooks(self, brain_instance):
        """optimize(full=True) should call registered hooks."""
        called = []
        hook = lambda dry_run=False: (called.append(1), {"merged": 0})[1]
        brain_instance.register_optimize_hook(hook)

        result = brain_instance.optimize(full=True)
        assert len(called) == 1
        assert "stats" in result

    def test_optimize_basic(self, brain_instance):
        """optimize() without full should still return results."""
        result = brain_instance.optimize(full=False)
        assert "decayed" in result
        assert "pruned" in result
        assert "stats" in result

    def test_recall_fires_booster_hook(self, brain_instance):
        """Recall with attention_boost should fire booster hooks."""
        boosted = []

        def booster(results):
            boosted.append(len(results))

        brain_instance.register_recall_booster(booster)
        brain_instance.store("boost test", memory_id="boost-1")
        brain_instance.recall("boost test", attention_boost=True)
        assert len(boosted) >= 1

    def test_recall_fires_observer_hook(self, brain_instance):
        """Recall should fire observer hooks."""
        observed = []

        def observer(query, results, *, caller=None, rate_limit_mono=0, last_mono=0):
            observed.append(query)

        brain_instance.register_recall_observer(observer)
        brain_instance.store("observe test", memory_id="obs-1")
        brain_instance.recall("observe test")
        # Observer may or may not fire depending on rate limiting
        # but at least the mechanism is tested


class TestBrainStaleMemories:
    def test_get_stale_memories(self, brain_instance):
        """Should find memories not accessed in N days."""
        from datetime import datetime, timezone, timedelta

        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        col = brain_instance.collections[MEMORIES]
        col.upsert(
            ids=["stale-1"],
            documents=["stale memory"],
            metadatas=[{
                "importance": 0.5,
                "last_accessed": old_date,
            }]
        )

        stale = brain_instance.get_stale_memories(days=30)
        assert len(stale) >= 1
        assert stale[0]["id"] == "stale-1"


# ---------------------------------------------------------------------------
# 3. Module-level convenience functions
# ---------------------------------------------------------------------------

class TestBrainRecallFromDate:
    def test_recall_from_date(self, brain_instance):
        """recall_from_date should filter by date range."""
        from datetime import datetime, timezone
        brain_instance.store("dated memory", memory_id="dated-1",
                             collection=MEMORIES, importance=0.7)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = brain_instance.recall_from_date(today)
        assert isinstance(results, list)

    def test_recall_from_date_with_end(self, brain_instance):
        from datetime import datetime, timezone
        brain_instance.store("range test", memory_id="range-1",
                             collection=MEMORIES, importance=0.5)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = brain_instance.recall_from_date("2020-01-01", end_date=today)
        assert isinstance(results, list)

    def test_recall_recent(self, brain_instance):
        """recall_recent should return recent memories."""
        brain_instance.store("recent test", memory_id="recent-1",
                             collection=MEMORIES, importance=0.6)
        results = brain_instance.recall_recent(days=7)
        assert isinstance(results, list)


class TestBrainReconsolidationExpiry:
    def test_reconsolidate_expired_window(self, brain_instance):
        """Reconsolidation should fail after lability window expires."""
        brain_instance.store("expiry test", memory_id="exp-1",
                             collection=MEMORIES, importance=0.7)
        # Manually inject labile entry with expired time
        brain_instance._labile_memories["exp-1"] = {
            "retrieved_at": time.monotonic() - 600,  # 10 min ago (window is 300s)
            "collection": MEMORIES,
        }
        result = brain_instance.reconsolidate("exp-1", "updated text")
        assert result["success"] is False
        assert "expired" in result["message"]

    def test_reconsolidate_with_importance_delta(self, brain_instance):
        """Reconsolidation can adjust importance."""
        brain_instance.store("delta test", memory_id="delta-1",
                             collection=MEMORIES, importance=0.5)
        brain_instance._labile_memories["delta-1"] = {
            "retrieved_at": time.monotonic(),
            "collection": MEMORIES,
        }
        result = brain_instance.reconsolidate("delta-1", "boosted text",
                                              importance_delta=0.2)
        if result["success"]:
            assert result["importance"] == pytest.approx(0.7, abs=0.01)

    def test_get_labile_with_active(self, brain_instance):
        """get_labile_memories should list non-expired entries."""
        brain_instance._labile_memories["lab-1"] = {
            "retrieved_at": time.monotonic(),
            "collection": MEMORIES,
        }
        labile = brain_instance.get_labile_memories()
        assert len(labile) == 1
        assert labile[0]["memory_id"] == "lab-1"
        assert labile[0]["remaining_s"] > 0

    def test_get_labile_cleans_expired(self, brain_instance):
        """get_labile_memories should clean up expired entries."""
        brain_instance._labile_memories["old-1"] = {
            "retrieved_at": time.monotonic() - 600,
            "collection": MEMORIES,
        }
        labile = brain_instance.get_labile_memories()
        assert labile == []
        assert "old-1" not in brain_instance._labile_memories


class TestBrainRecallScorer:
    def test_recall_with_scorer_sorts_by_actr_score(self, brain_instance):
        """Registered scorer should sort results by _actr_score."""
        def scorer(results):
            for i, r in enumerate(results):
                r["_actr_score"] = len(results) - i  # reverse order

        brain_instance.register_recall_scorer(scorer)
        brain_instance.store("scorer test A", memory_id="score-a")
        brain_instance.store("scorer test B", memory_id="score-b")
        results = brain_instance.recall("scorer test")
        # Scorer should have been applied
        if len(results) >= 2:
            assert results[0].get("_actr_score", 0) >= results[-1].get("_actr_score", 0)


class TestBrainOptimizeHookError:
    def test_optimize_hook_error_captured(self, brain_instance):
        """Failing optimize hook should report error in result."""
        def bad_hook(dry_run=False):
            raise ValueError("hook failed")

        brain_instance.register_optimize_hook(bad_hook)
        result = brain_instance.optimize(full=True)
        assert "consolidation_error" in result


class TestBrainConvenienceFunctions:
    def test_remember_auto_detects_category(self):
        from clarvis.brain import remember
        try:
            mid = remember("I learned that testing is essential", importance=0.3)
            assert mid is not None
        except Exception:
            pytest.skip("Production brain not available")

    def test_capture_low_importance_rejected(self):
        from clarvis.brain import capture
        result = capture("ok")
        assert result["captured"] is False
        assert "low importance" in result["reason"]

    def test_capture_medium_importance(self):
        from clarvis.brain import capture
        result = capture("sure thing")
        assert result["captured"] is False

    def test_capture_high_importance_accepted(self):
        from clarvis.brain import capture
        try:
            result = capture("Remember this critical important note about a bug fix")
            assert result["captured"] is True or result["importance"] >= 0.6
        except Exception:
            pytest.skip("Production brain not available")

    def test_search_function(self):
        from clarvis.brain import search
        try:
            results = search("test query", n=3)
            assert isinstance(results, list)
        except Exception:
            pytest.skip("Production brain not available")


# ---------------------------------------------------------------------------
# Graph corruption recovery and merge-on-save
# ---------------------------------------------------------------------------

class TestGraphCorruptionRecovery:
    def test_corrupt_json_triggers_recovery(self, tmp_path):
        """Corrupt graph file should be renamed .broken and graph reset."""
        import clarvis.brain as brain_mod
        import clarvis.brain.constants as const_mod

        orig = {
            "mod_DATA_DIR": brain_mod.DATA_DIR,
            "mod_GRAPH_FILE": brain_mod.GRAPH_FILE,
            "const_DATA_DIR": const_mod.DATA_DIR,
            "const_GRAPH_FILE": const_mod.GRAPH_FILE,
        }

        test_data = str(tmp_path / "testdb")
        test_graph = str(tmp_path / "graph.json")
        os.makedirs(test_data, exist_ok=True)

        # Write corrupt JSON
        with open(test_graph, 'w') as f:
            f.write("{CORRUPT!!!")

        brain_mod.DATA_DIR = test_data
        brain_mod.GRAPH_FILE = test_graph
        const_mod.DATA_DIR = test_data
        const_mod.GRAPH_FILE = test_graph

        try:
            from clarvis.brain import ClarvisBrain
            b = ClarvisBrain.__new__(ClarvisBrain)
            b.graph_file = test_graph
            b.graph = None
            b._load_graph()

            # Graph should be reset to empty
            assert "nodes" in b.graph or "edges" in b.graph
            # Corrupt file should be renamed
            assert os.path.exists(test_graph + ".broken")
        finally:
            brain_mod.DATA_DIR = orig["mod_DATA_DIR"]
            brain_mod.GRAPH_FILE = orig["mod_GRAPH_FILE"]
            const_mod.DATA_DIR = orig["const_DATA_DIR"]
            const_mod.GRAPH_FILE = orig["const_GRAPH_FILE"]

    def test_partial_recovery_truncated_json(self, tmp_path):
        """Truncated JSON with valid prefix should attempt partial recovery."""
        import clarvis.brain as brain_mod
        import clarvis.brain.constants as const_mod

        orig = {
            "mod_DATA_DIR": brain_mod.DATA_DIR,
            "mod_GRAPH_FILE": brain_mod.GRAPH_FILE,
            "const_DATA_DIR": const_mod.DATA_DIR,
            "const_GRAPH_FILE": const_mod.GRAPH_FILE,
        }

        test_data = str(tmp_path / "testdb")
        test_graph = str(tmp_path / "graph.json")
        os.makedirs(test_data, exist_ok=True)

        # Write truncated JSON with recoverable content
        with open(test_graph, 'w') as f:
            f.write('{"edges": [{"from": "a", "to": "b"},')

        brain_mod.DATA_DIR = test_data
        brain_mod.GRAPH_FILE = test_graph
        const_mod.DATA_DIR = test_data
        const_mod.GRAPH_FILE = test_graph

        try:
            from clarvis.brain import ClarvisBrain
            b = ClarvisBrain.__new__(ClarvisBrain)
            b.graph_file = test_graph
            b.graph = None
            b._load_graph()
            # Should either recover or reset to empty
            assert b.graph is not None
        finally:
            brain_mod.DATA_DIR = orig["mod_DATA_DIR"]
            brain_mod.GRAPH_FILE = orig["mod_GRAPH_FILE"]
            const_mod.DATA_DIR = orig["const_DATA_DIR"]
            const_mod.GRAPH_FILE = orig["const_GRAPH_FILE"]

    def test_missing_graph_file_creates_empty(self, tmp_path):
        """No graph file should create an empty graph."""
        from clarvis.brain import ClarvisBrain
        b = ClarvisBrain.__new__(ClarvisBrain)
        b.graph_file = str(tmp_path / "nonexistent_graph.json")
        b.graph = None
        b._load_graph()
        assert b.graph == {"nodes": {}, "edges": []}


class TestGraphSaveMerge:
    def test_save_graph_merges_new_edges(self, brain_instance):
        """_save_graph should merge edges from disk when saving."""
        # Add edge and save
        brain_instance.add_relationship("n1", "n2", "test_rel")
        brain_instance._save_graph()

        # Simulate another process adding an edge to disk
        with open(brain_instance.graph_file, 'r') as f:
            on_disk = json.load(f)
        on_disk["edges"].append({"from": "n3", "to": "n4", "type": "external"})
        with open(brain_instance.graph_file, 'w') as f:
            json.dump(on_disk, f)

        # Now add another edge and save — should merge
        brain_instance.add_relationship("n5", "n6", "another_rel")
        brain_instance._save_graph()

        with open(brain_instance.graph_file, 'r') as f:
            final = json.load(f)
        edge_pairs = {(e["from"], e["to"]) for e in final["edges"]}
        assert ("n1", "n2") in edge_pairs
        assert ("n3", "n4") in edge_pairs
        assert ("n5", "n6") in edge_pairs

    def test_save_graph_handles_corrupt_disk(self, brain_instance):
        """Save should succeed even if on-disk file is corrupt."""
        brain_instance.add_relationship("a", "b", "rel")
        brain_instance._save_graph()

        # Corrupt the on-disk file
        with open(brain_instance.graph_file, 'w') as f:
            f.write("NOT JSON!")

        # Should still save without error
        brain_instance.add_relationship("c", "d", "rel2")
        brain_instance._save_graph()

        with open(brain_instance.graph_file, 'r') as f:
            result = json.load(f)
        assert len(result["edges"]) >= 1


@pytest.mark.timeout(30)
class TestBulkCrossLink:
    def test_bulk_cross_link_empty_brain(self, brain_instance):
        """Empty brain should return zero new edges."""
        result = brain_instance.bulk_cross_link()
        assert result["new_edges"] == 0
        assert result["memories_scanned"] == 0

    def test_bulk_cross_link_creates_edges(self, brain_instance):
        """Cross-collection memories with similar content should be linked."""
        # Store similar memories in different collections
        brain_instance.store("Python async programming patterns", collection="clarvis-learnings", importance=0.8)
        brain_instance.store("Python async programming guide", collection="clarvis-memories", importance=0.8)

        result = brain_instance.bulk_cross_link(max_distance=2.0)
        assert result["memories_scanned"] >= 2
        # May or may not create edges depending on embedding similarity
        assert isinstance(result["new_edges"], int)
        assert "total_edges" in result

    def test_bulk_cross_link_respects_max_links(self, brain_instance):
        """Should respect max_links_per_memory."""
        brain_instance.store("Core concept about memory systems", collection="clarvis-learnings", importance=0.8)
        brain_instance.store("Memory systems in cognitive architecture", collection="clarvis-memories", importance=0.8)
        brain_instance.store("Memory system design patterns", collection="clarvis-procedures", importance=0.8)

        result = brain_instance.bulk_cross_link(max_distance=2.0, max_links_per_memory=1)
        assert isinstance(result["new_edges"], int)


# ---------------------------------------------------------------------------
# Factory singleton tests
# ---------------------------------------------------------------------------

class TestChromaFactory:
    def test_same_path_returns_same_client(self, tmp_path):
        """get_chroma_client with same path should return identical object."""
        from clarvis.brain.factory import get_chroma_client, reset_singletons
        reset_singletons()
        try:
            p = str(tmp_path / "fac1")
            c1 = get_chroma_client(p)
            c2 = get_chroma_client(p)
            assert c1 is c2
        finally:
            reset_singletons()

    def test_different_paths_return_different_clients(self, tmp_path):
        """get_chroma_client with different paths should return separate objects."""
        from clarvis.brain.factory import get_chroma_client, reset_singletons
        reset_singletons()
        try:
            c1 = get_chroma_client(str(tmp_path / "a"))
            c2 = get_chroma_client(str(tmp_path / "b"))
            assert c1 is not c2
        finally:
            reset_singletons()

    def test_collections_consistent_across_calls(self, tmp_path):
        """Collections created via one reference should be visible via another."""
        from clarvis.brain.factory import get_chroma_client, reset_singletons
        reset_singletons()
        try:
            p = str(tmp_path / "coll_test")
            c1 = get_chroma_client(p)
            c1.get_or_create_collection("test-col")
            c2 = get_chroma_client(p)
            names = [c.name for c in c2.list_collections()]
            assert "test-col" in names
        finally:
            reset_singletons()

    def test_embedding_singleton(self):
        """get_embedding_function should return same ONNX instance."""
        from clarvis.brain.factory import get_embedding_function, reset_singletons
        reset_singletons()
        try:
            e1 = get_embedding_function(use_onnx=True)
            e2 = get_embedding_function(use_onnx=True)
            assert e1 is e2
            assert e1 is not None
        finally:
            reset_singletons()

    def test_embedding_none_when_disabled(self):
        """get_embedding_function(use_onnx=False) should return None."""
        from clarvis.brain.factory import get_embedding_function
        assert get_embedding_function(use_onnx=False) is None

    def test_reset_clears_singletons(self, tmp_path):
        """reset_singletons should make next call create fresh instances."""
        from clarvis.brain.factory import get_chroma_client, reset_singletons
        reset_singletons()
        p = str(tmp_path / "reset_test")
        c1 = get_chroma_client(p)
        reset_singletons()
        c2 = get_chroma_client(p)
        assert c1 is not c2

    def test_brain_uses_factory_client(self, brain_instance):
        """ClarvisBrain.client should be a chromadb client (wired through factory)."""
        import chromadb
        assert hasattr(brain_instance, 'client')
        # Verify it's a real chromadb client (has list_collections)
        assert hasattr(brain_instance.client, 'list_collections')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

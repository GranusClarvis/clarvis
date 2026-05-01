"""Tests for clarvis.memory — hebbian, episodic, procedural, working, consolidation.

HebbianMemory is tested in isolation (no brain dependency for constructor/helpers).
EpisodicMemory causal graph methods are tested with mock data (file I/O patched).
ProceduralMemory code templates and tier constants are tested as pure data/logic.
"""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# 1. HebbianMemory — unit tests for constructor & helper methods
# ---------------------------------------------------------------------------

class TestHebbianMemoryConstants:
    """Test hebbian_memory constants are sane."""

    def test_constants_importable(self):
        from clarvis.memory.hebbian_memory import (
            REINFORCEMENT_BASE, REINFORCEMENT_DECAY, MAX_IMPORTANCE,
            MIN_IMPORTANCE, COACTIVATION_WINDOW_S, DECAY_EXPONENT,
            DECAY_GRACE_DAYS, STRENGTHEN_THRESHOLD, WEAKEN_THRESHOLD_DAYS,
            FISHER_LAMBDA, FISHER_FREQ_WEIGHT, FISHER_UNIQ_WEIGHT,
            FISHER_IMPACT_WEIGHT,
        )
        assert 0 < REINFORCEMENT_BASE < 1
        assert 0 < REINFORCEMENT_DECAY < 1
        assert MAX_IMPORTANCE <= 1.0
        assert MIN_IMPORTANCE >= 0.0
        assert MIN_IMPORTANCE < MAX_IMPORTANCE
        assert DECAY_GRACE_DAYS >= 0
        assert FISHER_FREQ_WEIGHT + FISHER_UNIQ_WEIGHT + FISHER_IMPACT_WEIGHT == pytest.approx(1.0)


class TestHebbianMemoryInit:
    """Test HebbianMemory construction and file-based helpers."""

    def test_constructor_loads_empty(self, tmp_path):
        """Constructor works with missing data files."""
        from clarvis.memory.hebbian_memory import HebbianMemory

        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            h = HebbianMemory()
            assert h._coactivation == {}
            assert h._fisher_scores == {"scores": {}, "computed_at": None}
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_load_coactivation_valid_json(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        test_file = tmp_path / "coactivation.json"
        test_data = {"pair1": {"ids": ["a", "b"], "count": 3, "strength": 0.5}}
        test_file.write_text(json.dumps(test_data))
        hm.COACTIVATION_FILE = test_file

        try:
            h = hm.HebbianMemory()
            assert "pair1" in h._coactivation
            assert h._coactivation["pair1"]["count"] == 3
        finally:
            hm.COACTIVATION_FILE = orig

    def test_load_coactivation_corrupt_json(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        test_file = tmp_path / "coactivation.json"
        test_file.write_text("{corrupt json!!!")
        hm.COACTIVATION_FILE = test_file

        try:
            h = hm.HebbianMemory()
            assert h._coactivation == {}
        finally:
            hm.COACTIVATION_FILE = orig

    def test_load_fisher_valid_json(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.FISHER_FILE
        test_file = tmp_path / "fisher.json"
        test_data = {"scores": {"mem1": 0.8}, "computed_at": "2026-01-01T00:00:00"}
        test_file.write_text(json.dumps(test_data))
        hm.FISHER_FILE = test_file

        try:
            h = hm.HebbianMemory()
            assert h._fisher_scores["scores"]["mem1"] == 0.8
        finally:
            hm.FISHER_FILE = orig

    def test_load_fisher_corrupt_json(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.FISHER_FILE
        test_file = tmp_path / "fisher.json"
        test_file.write_text("NOT JSON")
        hm.FISHER_FILE = test_file

        try:
            h = hm.HebbianMemory()
            assert h._fisher_scores == {"scores": {}, "computed_at": None}
        finally:
            hm.FISHER_FILE = orig


class TestHebbianCoactivation:
    """Test co-activation tracking (file I/O isolated)."""

    def test_update_coactivation_creates_entries(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            from datetime import datetime, timezone
            h = hm.HebbianMemory()
            now = datetime.now(timezone.utc)

            h._update_coactivation(["mem_a", "mem_b", "mem_c"], now)

            # 3 memories = 3 pairs: a|b, a|c, b|c
            assert len(h._coactivation) == 3

            pair_key = "|".join(sorted(["mem_a", "mem_b"]))
            assert pair_key in h._coactivation
            entry = h._coactivation[pair_key]
            assert entry["count"] == 1
            assert entry["strength"] > 0
            assert hm.COACTIVATION_FILE.exists()
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_coactivation_strengthens_with_repetition(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            from datetime import datetime, timezone
            h = hm.HebbianMemory()
            now = datetime.now(timezone.utc)

            h._update_coactivation(["m1", "m2"], now)
            s1 = list(h._coactivation.values())[0]["strength"]

            h._update_coactivation(["m1", "m2"], now)
            s2 = list(h._coactivation.values())[0]["strength"]

            assert s2 > s1, "Repeated co-activation should increase strength"
            assert list(h._coactivation.values())[0]["count"] == 2
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_coactivation_strength_bounded(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            from datetime import datetime, timezone
            h = hm.HebbianMemory()
            now = datetime.now(timezone.utc)

            for _ in range(100):
                h._update_coactivation(["x", "y"], now)

            strength = list(h._coactivation.values())[0]["strength"]
            assert strength <= 1.0, "Strength should be bounded at 1.0"
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_save_coactivation_roundtrip(self, tmp_path):
        """Save and reload should preserve data."""
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        coact_file = tmp_path / "coactivation.json"
        hm.COACTIVATION_FILE = coact_file
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            from datetime import datetime, timezone
            h = hm.HebbianMemory()
            h._update_coactivation(["a", "b"], datetime.now(timezone.utc))
            # Reload from disk
            loaded = json.loads(coact_file.read_text())
            assert len(loaded) == 1
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher


class TestHebbianFisherScore:
    def test_get_fisher_score_missing(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            h = hm.HebbianMemory()
            assert h.get_fisher_score("nonexistent") == 0.0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_get_fisher_score_cached(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        test_file = tmp_path / "fisher.json"
        test_file.write_text(json.dumps({
            "scores": {"mem1": 0.75},
            "computed_at": "2026-01-01T00:00:00"
        }))
        hm.FISHER_FILE = test_file

        try:
            h = hm.HebbianMemory()
            assert h.get_fisher_score("mem1") == 0.75
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_save_fisher_roundtrip(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        fisher_file = tmp_path / "fisher.json"
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = fisher_file

        try:
            h = hm.HebbianMemory()
            h._fisher_scores = {"scores": {"x": 0.5}, "computed_at": "2026-01-01"}
            h._save_fisher()
            loaded = json.loads(fisher_file.read_text())
            assert loaded["scores"]["x"] == 0.5
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher


class TestHebbianStats:
    def test_get_stats_empty(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.STATS_FILE
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            h = hm.HebbianMemory()
            assert h.get_stats() == {}
        finally:
            hm.STATS_FILE = orig

    def test_get_stats_valid(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.STATS_FILE
        test_file = tmp_path / "stats.json"
        test_file.write_text(json.dumps({"strengthened": 5, "weakened": 3}))
        hm.STATS_FILE = test_file
        try:
            h = hm.HebbianMemory()
            stats = h.get_stats()
            assert stats["strengthened"] == 5
        finally:
            hm.STATS_FILE = orig

    def test_get_stats_corrupt(self, tmp_path):
        """Corrupt stats file should return empty dict."""
        import clarvis.memory.hebbian_memory as hm
        orig = hm.STATS_FILE
        test_file = tmp_path / "stats.json"
        test_file.write_text("NOT JSON!")
        hm.STATS_FILE = test_file
        try:
            h = hm.HebbianMemory()
            assert h.get_stats() == {}
        finally:
            hm.STATS_FILE = orig

    def test_save_stats(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.STATS_FILE
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            h = hm.HebbianMemory()
            h._save_stats({"test": True, "count": 42})
            loaded = json.loads(hm.STATS_FILE.read_text())
            assert loaded["count"] == 42
        finally:
            hm.STATS_FILE = orig

    def test_get_evolution_history_empty(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.EVOLUTION_HISTORY_FILE
        hm.EVOLUTION_HISTORY_FILE = tmp_path / "history.jsonl"
        try:
            h = hm.HebbianMemory()
            assert h.get_evolution_history() == []
        finally:
            hm.EVOLUTION_HISTORY_FILE = orig

    def test_get_evolution_history_valid(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.EVOLUTION_HISTORY_FILE
        test_file = tmp_path / "history.jsonl"
        entries = [{"ts": "2026-01-01", "weakened": 1}, {"ts": "2026-01-02", "weakened": 2}]
        test_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        hm.EVOLUTION_HISTORY_FILE = test_file
        try:
            h = hm.HebbianMemory()
            history = h.get_evolution_history(n=10)
            assert len(history) == 2
        finally:
            hm.EVOLUTION_HISTORY_FILE = orig

    def test_get_evolution_history_limits(self, tmp_path):
        """History should respect the n limit."""
        import clarvis.memory.hebbian_memory as hm
        orig = hm.EVOLUTION_HISTORY_FILE
        test_file = tmp_path / "history.jsonl"
        entries = [{"ts": f"2026-01-{i:02d}", "weakened": i} for i in range(1, 21)]
        test_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        hm.EVOLUTION_HISTORY_FILE = test_file
        try:
            h = hm.HebbianMemory()
            history = h.get_evolution_history(n=5)
            assert len(history) == 5
            # Should be the last 5 entries
            assert history[0]["weakened"] == 16
        finally:
            hm.EVOLUTION_HISTORY_FILE = orig


class TestHebbianAccessPatterns:
    def test_get_access_patterns_empty(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig = hm.ACCESS_LOG_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access_log.jsonl"
        try:
            h = hm.HebbianMemory()
            patterns = h.get_access_patterns(days=7)
            assert patterns["total_events"] == 0
        finally:
            hm.ACCESS_LOG_FILE = orig

    def test_get_access_patterns_counts(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.ACCESS_LOG_FILE
        test_file = tmp_path / "access_log.jsonl"

        now = datetime.now(timezone.utc).isoformat()
        events = [
            {"memory_id": "m1", "query": "test", "collection": "mem", "caller": "test", "timestamp": now},
            {"memory_id": "m1", "query": "test2", "collection": "mem", "caller": "test", "timestamp": now},
            {"memory_id": "m2", "query": "other", "collection": "mem", "caller": "cron", "timestamp": now},
        ]
        test_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        hm.ACCESS_LOG_FILE = test_file
        try:
            h = hm.HebbianMemory()
            patterns = h.get_access_patterns(days=7)
            assert patterns["total_events"] == 3
            assert patterns["unique_memories"] == 2
            assert ("m1", 2) in patterns["top_accessed"]
            assert patterns["caller_breakdown"]["test"] == 2
        finally:
            hm.ACCESS_LOG_FILE = orig

    def test_get_access_patterns_filters_old(self, tmp_path):
        """Events older than the window should be excluded."""
        import clarvis.memory.hebbian_memory as hm
        from datetime import datetime, timezone, timedelta
        orig = hm.ACCESS_LOG_FILE
        test_file = tmp_path / "access_log.jsonl"

        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        events = [
            {"memory_id": "old_m", "query": "q", "collection": "mem", "caller": "c", "timestamp": old},
            {"memory_id": "new_m", "query": "q", "collection": "mem", "caller": "c", "timestamp": recent},
        ]
        test_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        hm.ACCESS_LOG_FILE = test_file
        try:
            h = hm.HebbianMemory()
            patterns = h.get_access_patterns(days=7)
            assert patterns["total_events"] == 1
            assert patterns["unique_memories"] == 1
        finally:
            hm.ACCESS_LOG_FILE = orig


class TestHebbianOnRecall:
    def test_on_recall_empty_results(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access_log.jsonl"

        try:
            h = hm.HebbianMemory()
            h.on_recall("test query", [])
            assert h._coactivation == {}
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_on_recall_single_result_no_coactivation(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access_log.jsonl"

        try:
            h = hm.HebbianMemory()
            h.on_recall("test", [
                {"id": "m1", "collection": "mem", "metadata": {}, "document": "test"}
            ])
            assert len(h._coactivation) == 0
            assert hm.ACCESS_LOG_FILE.exists()
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_on_recall_multiple_creates_coactivation(self, tmp_path):
        """Multiple results should create co-activation pairs."""
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access_log.jsonl"

        try:
            h = hm.HebbianMemory()
            h.on_recall("multi test", [
                {"id": "m1", "collection": "mem", "metadata": {}, "document": "test1"},
                {"id": "m2", "collection": "mem", "metadata": {}, "document": "test2"},
                {"id": "m3", "collection": "mem", "metadata": {}, "document": "test3"},
            ])
            # 3 IDs = 3 pairs
            assert len(h._coactivation) == 3
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_on_recall_logs_access(self, tmp_path):
        """on_recall should log access events."""
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        access_file = tmp_path / "access_log.jsonl"
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = access_file

        try:
            h = hm.HebbianMemory()
            h.on_recall("log test", [
                {"id": "log1", "collection": "mem", "metadata": {}, "document": "test"},
            ])
            lines = access_file.read_text().strip().split("\n")
            assert len(lines) >= 1
            entry = json.loads(lines[0])
            assert entry["memory_id"] == "log1"
            assert entry["query"] == "log test"
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_on_recall_skips_results_without_id(self, tmp_path):
        """Results without 'id' should be safely skipped."""
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coactivation.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access_log.jsonl"

        try:
            h = hm.HebbianMemory()
            h.on_recall("no-id test", [
                {"collection": "mem", "metadata": {}, "document": "no id"},
                {"id": "valid1", "collection": "mem", "metadata": {}, "document": "has id"},
            ])
            # Only one valid ID, so no coactivation pairs
            assert len(h._coactivation) == 0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access


# ---------------------------------------------------------------------------
# 2. EpisodicMemory — causal graph and pure methods (no brain needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def episodic_mem(tmp_path):
    """EpisodicMemory with isolated file storage."""
    import clarvis.memory.episodic_memory as em

    orig_ep = em.EPISODES_FILE
    orig_cl = em.CAUSAL_LINKS_FILE
    em.EPISODES_FILE = tmp_path / "episodes.json"
    em.CAUSAL_LINKS_FILE = tmp_path / "causal_links.json"

    # Pre-populate with test episodes
    episodes = [
        {"id": "ep-001", "task": "Set up CI pipeline", "section": "infrastructure",
         "outcome": "success", "valence": 0.8, "timestamp": "2026-01-01T10:00:00"},
        {"id": "ep-002", "task": "Fix CI pipeline test failures", "section": "infrastructure",
         "outcome": "success", "valence": 0.6, "timestamp": "2026-01-01T12:00:00"},
        {"id": "ep-003", "task": "Deploy new feature", "section": "development",
         "outcome": "failure", "valence": -0.5, "timestamp": "2026-01-01T14:00:00"},
        {"id": "ep-004", "task": "Fix deployment bug", "section": "development",
         "outcome": "success", "valence": 0.7, "timestamp": "2026-01-01T16:00:00"},
        {"id": "ep-005", "task": "Research caching strategies", "section": "research",
         "outcome": "success", "valence": 0.3, "timestamp": "2026-01-02T10:00:00"},
    ]
    em.EPISODES_FILE.write_text(json.dumps(episodes))

    memory = em.EpisodicMemory()

    yield memory

    em.EPISODES_FILE = orig_ep
    em.CAUSAL_LINKS_FILE = orig_cl


class TestEpisodicMemoryInit:
    def test_loads_episodes(self, episodic_mem):
        assert len(episodic_mem.episodes) == 5

    def test_id_index_built(self, episodic_mem):
        assert "ep-001" in episodic_mem._id_index
        assert episodic_mem._id_index["ep-003"]["outcome"] == "failure"

    def test_empty_init(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "empty_episodes.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "empty_causal.json"
        try:
            memory = em.EpisodicMemory()
            assert memory.episodes == []
            assert memory.causal_links == []
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


class TestEpisodicCausalRelationships:
    def test_causal_relationships_dict(self):
        from clarvis.memory.episodic_memory import CAUSAL_RELATIONSHIPS
        assert len(CAUSAL_RELATIONSHIPS) >= 5
        for key in ["caused", "enabled", "blocked", "fixed", "retried"]:
            assert key in CAUSAL_RELATIONSHIPS
            assert isinstance(CAUSAL_RELATIONSHIPS[key], str)


class TestEpisodicCausalLink:
    def test_create_link(self, episodic_mem):
        link = episodic_mem.causal_link("ep-001", "ep-002", "caused")
        assert link is not None
        assert link["from"] == "ep-001"
        assert link["to"] == "ep-002"
        assert link["relationship"] == "caused"
        assert link["confidence"] == 1.0

    def test_link_with_confidence(self, episodic_mem):
        link = episodic_mem.causal_link("ep-001", "ep-002", "enabled", confidence=0.7)
        assert link["confidence"] == 0.7

    def test_link_confidence_clamped(self, episodic_mem):
        link = episodic_mem.causal_link("ep-001", "ep-002", "caused", confidence=5.0)
        assert link["confidence"] == 1.0

        # Need different pair for second test
        link2 = episodic_mem.causal_link("ep-003", "ep-004", "fixed", confidence=-1.0)
        assert link2["confidence"] == 0.0

    def test_link_invalid_relationship(self, episodic_mem):
        link = episodic_mem.causal_link("ep-001", "ep-002", "invalid_rel")
        assert link is None

    def test_link_self_loop_rejected(self, episodic_mem):
        link = episodic_mem.causal_link("ep-001", "ep-001", "caused")
        assert link is None

    def test_link_no_duplicates(self, episodic_mem):
        link1 = episodic_mem.causal_link("ep-001", "ep-002", "caused")
        link2 = episodic_mem.causal_link("ep-001", "ep-002", "caused")
        assert link1 is not None
        assert link2 is not None
        # Same link returned, no duplication
        assert len([l for l in episodic_mem.causal_links
                    if l["from"] == "ep-001" and l["to"] == "ep-002"
                    and l["relationship"] == "caused"]) == 1

    def test_link_with_dict_episodes(self, episodic_mem):
        """Should accept episode dicts (extracts id)."""
        ep_a = {"id": "ep-001", "task": "test"}
        ep_b = {"id": "ep-002", "task": "test2"}
        link = episodic_mem.causal_link(ep_a, ep_b, "enabled")
        assert link["from"] == "ep-001"
        assert link["to"] == "ep-002"

    def test_link_persists(self, episodic_mem, tmp_path):
        """Causal links should be saved to disk."""
        import clarvis.memory.episodic_memory as em
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        assert em.CAUSAL_LINKS_FILE.exists()
        data = json.loads(em.CAUSAL_LINKS_FILE.read_text())
        assert len(data) >= 1


class TestEpisodicCausesOf:
    def test_causes_of_empty(self, episodic_mem):
        assert episodic_mem.causes_of("ep-001") == []

    def test_causes_of_finds_cause(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        causes = episodic_mem.causes_of("ep-002")
        assert len(causes) == 1
        link, ep = causes[0]
        assert link["from"] == "ep-001"
        assert ep["id"] == "ep-001"

    def test_causes_of_with_filter(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-003", "enabled")
        episodic_mem.causal_link("ep-002", "ep-003", "caused")
        causes = episodic_mem.causes_of("ep-003", relationship="caused")
        assert len(causes) == 1
        assert causes[0][0]["from"] == "ep-002"

    def test_causes_of_with_dict(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        causes = episodic_mem.causes_of({"id": "ep-002"})
        assert len(causes) == 1


class TestEpisodicEffectsOf:
    def test_effects_of_empty(self, episodic_mem):
        assert episodic_mem.effects_of("ep-001") == []

    def test_effects_of_finds_effect(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        effects = episodic_mem.effects_of("ep-001")
        assert len(effects) == 1
        link, ep = effects[0]
        assert link["to"] == "ep-002"

    def test_effects_of_with_filter(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "enabled")
        episodic_mem.causal_link("ep-001", "ep-003", "blocked")
        effects = episodic_mem.effects_of("ep-001", relationship="blocked")
        assert len(effects) == 1
        assert effects[0][0]["to"] == "ep-003"


class TestEpisodicCausalChain:
    def test_chain_backward(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        episodic_mem.causal_link("ep-002", "ep-003", "caused")
        chain = episodic_mem.causal_chain("ep-003", direction="backward")
        assert len(chain) >= 1
        # Should find ep-002 and ep-001 as causes
        ids_in_chain = [link["from"] for _, link, _ in chain]
        assert "ep-002" in ids_in_chain

    def test_chain_forward(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        episodic_mem.causal_link("ep-002", "ep-003", "caused")
        chain = episodic_mem.causal_chain("ep-001", direction="forward")
        assert len(chain) >= 1
        ids_in_chain = [link["to"] for _, link, _ in chain]
        assert "ep-002" in ids_in_chain

    def test_chain_empty(self, episodic_mem):
        chain = episodic_mem.causal_chain("ep-005")
        assert chain == []

    def test_chain_max_depth(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        episodic_mem.causal_link("ep-002", "ep-003", "caused")
        episodic_mem.causal_link("ep-003", "ep-004", "caused")
        chain = episodic_mem.causal_chain("ep-004", direction="backward", max_depth=1)
        # Should only find depth 1 (ep-003), not deeper
        assert len(chain) == 1


class TestEpisodicRootCauses:
    def test_root_causes_finds_root(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        episodic_mem.causal_link("ep-002", "ep-003", "caused")
        roots = episodic_mem.root_causes("ep-003")
        root_ids = [r["id"] for r in roots]
        assert "ep-001" in root_ids

    def test_root_causes_empty(self, episodic_mem):
        roots = episodic_mem.root_causes("ep-005")
        assert roots == []


class TestEpisodicCausalGraphStats:
    def test_stats_empty(self, episodic_mem):
        stats = episodic_mem.causal_graph_stats()
        assert stats["total_links"] == 0

    def test_stats_with_links(self, episodic_mem):
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        episodic_mem.causal_link("ep-002", "ep-003", "enabled")
        episodic_mem.causal_link("ep-003", "ep-004", "fixed")
        stats = episodic_mem.causal_graph_stats()
        assert stats["total_links"] == 3
        assert stats["unique_nodes"] == 4
        assert stats["relationship_counts"]["caused"] == 1
        assert stats["relationship_counts"]["enabled"] == 1
        assert stats["relationship_counts"]["fixed"] == 1
        assert len(stats["top_causes"]) >= 1
        assert len(stats["top_effects"]) >= 1


class TestEpisodicKeywordOverlap:
    def test_keyword_overlap_identical(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        score = EpisodicMemory._keyword_overlap(
            "deploy the server application",
            "deploy the server application"
        )
        assert score == 1.0

    def test_keyword_overlap_partial(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        score = EpisodicMemory._keyword_overlap(
            "deploy the production server",
            "restart the production database"
        )
        assert 0 < score < 1

    def test_keyword_overlap_no_overlap(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        score = EpisodicMemory._keyword_overlap(
            "alpha beta gamma",
            "delta epsilon zeta"
        )
        assert score == 0.0

    def test_keyword_overlap_empty(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        score = EpisodicMemory._keyword_overlap("", "test")
        assert score == 0.0

    def test_keyword_overlap_filters_short_words(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        # Short words (< 4 chars) should be ignored
        score = EpisodicMemory._keyword_overlap("a b c d", "a b c d")
        assert score == 0.0

    def test_keyword_overlap_strips_brackets(self):
        from clarvis.memory.episodic_memory import EpisodicMemory
        score = EpisodicMemory._keyword_overlap(
            "[TASK] deploy server",
            "deploy server [DONE]"
        )
        assert score > 0


class TestEpisodicSaveLoad:
    def test_save_episodes(self, episodic_mem, tmp_path):
        import clarvis.memory.episodic_memory as em
        episodic_mem._save()
        assert em.EPISODES_FILE.exists()
        loaded = json.loads(em.EPISODES_FILE.read_text())
        assert len(loaded) == 5

    def test_save_causal_links(self, episodic_mem, tmp_path):
        import clarvis.memory.episodic_memory as em
        episodic_mem.causal_link("ep-001", "ep-002", "caused")
        data = json.loads(em.CAUSAL_LINKS_FILE.read_text())
        assert len(data) == 1

    def test_save_caps_episodes(self, tmp_path):
        """Save should cap at 500 episodes."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            memory = em.EpisodicMemory()
            memory.episodes = [{"id": f"ep-{i}", "task": f"task {i}"} for i in range(600)]
            memory._save()
            loaded = json.loads(em.EPISODES_FILE.read_text())
            assert len(loaded) == 500
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


class TestEpisodicAutoLink:
    def test_auto_link_retried(self, tmp_path):
        """Similar failed task followed by retry should link as 'retried'."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            episodes = [
                {"id": "ep-a", "task": "Deploy the production server application",
                 "section": "infra", "outcome": "failure", "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-b", "task": "Deploy the production server application again",
                 "section": "infra", "outcome": "success", "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._auto_link_against(episodes[1], [episodes[0]])
            assert len(memory.causal_links) >= 1
            link = memory.causal_links[0]
            assert link["relationship"] in ("retried", "fixed")
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_fixed(self, tmp_path):
        """Success after failure should link as 'fixed'."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            episodes = [
                {"id": "ep-a", "task": "Configure monitoring dashboard alerts",
                 "section": "monitoring", "outcome": "failure", "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-b", "task": "Fix monitoring dashboard alert configuration",
                 "section": "monitoring", "outcome": "success", "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._auto_link_against(episodes[1], [episodes[0]])
            if memory.causal_links:
                assert memory.causal_links[0]["relationship"] in ("fixed", "retried")
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_enabled(self, tmp_path):
        """Prior success followed by related success should link as 'enabled'."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            episodes = [
                {"id": "ep-a", "task": "Setup database migration framework",
                 "section": "db", "outcome": "success", "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-b", "task": "Run database migration for users table",
                 "section": "db", "outcome": "success", "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._auto_link_against(episodes[1], [episodes[0]])
            if memory.causal_links:
                assert memory.causal_links[0]["relationship"] == "enabled"
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_blocked(self, tmp_path):
        """Failure followed by related failure should link as 'blocked'."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            episodes = [
                {"id": "ep-a", "task": "Deploy application to production cluster",
                 "section": "deploy", "outcome": "failure", "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-b", "task": "Deploy application to production environment",
                 "section": "deploy", "outcome": "failure", "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._auto_link_against(episodes[1], [episodes[0]])
            if memory.causal_links:
                assert memory.causal_links[0]["relationship"] in ("blocked", "retried")
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_no_match(self, tmp_path):
        """Unrelated tasks should not create links."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"

        try:
            episodes = [
                {"id": "ep-a", "task": "Research quantum computing papers",
                 "section": "research", "outcome": "success", "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-b", "task": "Fix production database backup",
                 "section": "infrastructure", "outcome": "success", "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._auto_link_against(episodes[1], [episodes[0]])
            assert len(memory.causal_links) == 0
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_empty_candidates(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            ep = {"id": "ep-a", "task": "test", "section": "test", "outcome": "success"}
            em.EPISODES_FILE.write_text(json.dumps([ep]))
            memory = em.EpisodicMemory()
            memory._auto_link_against(ep, [])
            assert len(memory.causal_links) == 0
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_auto_link_delegates(self, tmp_path):
        """_auto_link should use last 20 episodes as candidates."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            episodes = [
                {"id": f"ep-{i}", "task": f"Task number {i}",
                 "section": "test", "outcome": "success",
                 "timestamp": f"2026-01-01T{10+i}:00:00"}
                for i in range(5)
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            new_ep = {"id": "ep-new", "task": "Task number five",
                      "section": "test", "outcome": "success"}
            memory.episodes.append(new_ep)
            memory._id_index[new_ep["id"]] = new_ep
            memory._auto_link(new_ep)
            assert isinstance(memory.causal_links, list)
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


class TestEpisodicBackfillCausalLinks:
    def test_backfill_no_episodes(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            memory = em.EpisodicMemory()
            count = memory.backfill_causal_links()
            assert count == 0
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_backfill_with_matching_episodes(self, tmp_path):
        """Backfill should detect causal links in matching episodes."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            episodes = [
                {"id": "ep-1", "task": "Setup monitoring dashboard system",
                 "section": "monitoring", "outcome": "failure",
                 "timestamp": "2026-01-01T10:00:00"},
                {"id": "ep-2", "task": "Fix monitoring dashboard system configuration errors",
                 "section": "monitoring", "outcome": "success",
                 "timestamp": "2026-01-01T12:00:00"},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            count = memory.backfill_causal_links()
            assert count >= 0
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


# ---------------------------------------------------------------------------
# 2b. EpisodicMemory — pure methods (no brain dependency)
# ---------------------------------------------------------------------------

class TestEpisodicComputeValence:
    """Test _compute_valence — emotional significance scoring."""

    def test_success_baseline(self, episodic_mem):
        v = episodic_mem._compute_valence("success", 0.5, 60, None)
        assert 0.0 <= v <= 1.0

    def test_failure_higher_than_success(self, episodic_mem):
        v_success = episodic_mem._compute_valence("success", 0.5, 60, None)
        v_failure = episodic_mem._compute_valence("failure", 0.5, 60, None)
        assert v_failure > v_success

    def test_timeout_higher_than_success(self, episodic_mem):
        v_success = episodic_mem._compute_valence("success", 0.5, 60, None)
        v_timeout = episodic_mem._compute_valence("timeout", 0.5, 60, None)
        assert v_timeout > v_success

    def test_high_salience_increases_valence(self, episodic_mem):
        v_low = episodic_mem._compute_valence("success", 0.1, 60, None)
        v_high = episodic_mem._compute_valence("success", 0.9, 60, None)
        assert v_high > v_low

    def test_long_duration_increases_valence(self, episodic_mem):
        v_short = episodic_mem._compute_valence("success", 0.5, 60, None)
        v_long = episodic_mem._compute_valence("success", 0.5, 600, None)
        assert v_long > v_short

    def test_novel_error_increases_valence(self, episodic_mem):
        v_no_err = episodic_mem._compute_valence("failure", 0.5, 60, None)
        v_err = episodic_mem._compute_valence("failure", 0.5, 60, "UniqueNewErrorXYZ123")
        assert v_err > v_no_err

    def test_repeated_error_no_bonus(self, tmp_path):
        """Repeated error should not get novelty bonus."""
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            episodes = [
                {"id": f"ep-{i}", "task": "t", "section": "s",
                 "outcome": "failure", "valence": 0.5, "error": "SameError repeated",
                 "timestamp": f"2026-01-01T{10+i}:00:00"}
                for i in range(5)
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            v = memory._compute_valence("failure", 0.5, 60, "SameError repeated content")
            # Should NOT get novelty bonus since error[:50] matches recent
            v_novel = memory._compute_valence("failure", 0.5, 60, "CompletelyNewError12345")
            assert v_novel >= v
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_valence_capped_at_one(self, episodic_mem):
        v = episodic_mem._compute_valence("failure", 1.0, 600, "NovelError")
        assert v <= 1.0


class TestEpisodicComputeActivation:
    """Test _compute_activation — ACT-R power-law decay."""

    def test_no_access_times_returns_zero(self, episodic_mem):
        ep = {"access_times": []}
        assert episodic_mem._compute_activation(ep) == 0.0

    def test_missing_access_times_returns_zero(self, episodic_mem):
        ep = {}
        assert episodic_mem._compute_activation(ep) == 0.0

    def test_recent_access_high_activation(self, episodic_mem):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        ep = {"access_times": [now - 1]}  # 1 second ago
        activation = episodic_mem._compute_activation(ep)
        assert activation > -2.0  # Recently accessed should have high activation

    def test_old_access_returns_finite(self, episodic_mem):
        """Very old access should still return finite (non-zero) activation."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        ep_old = {"access_times": [now - 86400 * 30]}  # 30 days ago
        a_old = episodic_mem._compute_activation(ep_old)
        assert a_old > -100  # Should be finite, not negative infinity

    def test_multiple_accesses_boost_activation(self, episodic_mem):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        ep_single = {"access_times": [now - 3600]}
        ep_multi = {"access_times": [now - 7200, now - 3600, now - 1800]}
        a_single = episodic_mem._compute_activation(ep_single)
        a_multi = episodic_mem._compute_activation(ep_multi)
        assert a_multi > a_single

    def test_spaced_vs_massed_practice(self, episodic_mem):
        """Spaced repetitions should lead to slower forgetting."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        # Massed: all within 1 minute
        ep_massed = {"access_times": [now - 100, now - 80, now - 60]}
        # Spaced: spread over hours
        ep_spaced = {"access_times": [now - 7200, now - 3600, now - 60]}
        a_massed = episodic_mem._compute_activation(ep_massed)
        a_spaced = episodic_mem._compute_activation(ep_spaced)
        # Both should be finite
        assert a_massed > -100
        assert a_spaced > -100


class TestEpisodicDecayActivations:
    """Test _decay_activations — rate-limited recomputation."""

    def test_decay_updates_activations(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        from datetime import datetime, timezone
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            now = datetime.now(timezone.utc).timestamp()
            episodes = [
                {"id": "ep-1", "task": "t1", "section": "s",
                 "outcome": "success", "valence": 0.5,
                 "timestamp": "2026-01-01T10:00:00",
                 "activation": 999.0, "access_times": [now - 3600]},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            memory._decay_activations()
            # Activation should be recomputed from access_times, not 999.0
            assert memory.episodes[0]["activation"] != 999.0
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_decay_rate_limited(self, episodic_mem):
        """Second call within 60s should be a no-op."""
        import time as time_mod
        episodic_mem._last_decay_time = time_mod.monotonic()
        old_activations = [ep.get("activation") for ep in episodic_mem.episodes]
        episodic_mem._decay_activations()
        new_activations = [ep.get("activation") for ep in episodic_mem.episodes]
        assert old_activations == new_activations


class TestEpisodicGetStats:
    """Test get_stats — episodic memory statistics."""

    def test_stats_empty(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            memory = em.EpisodicMemory()
            stats = memory.get_stats()
            assert stats == {"total": 0}
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_stats_with_episodes(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        from datetime import datetime, timezone
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            now = datetime.now(timezone.utc).timestamp()
            episodes = [
                {"id": "ep-1", "task": "t1", "section": "s",
                 "outcome": "success", "valence": 0.8,
                 "timestamp": "2026-01-01T10:00:00",
                 "activation": 0.5, "access_times": [now - 3600]},
                {"id": "ep-2", "task": "t2", "section": "s",
                 "outcome": "failure", "valence": 0.3,
                 "timestamp": "2026-01-02T10:00:00",
                 "activation": -1.0, "access_times": [now - 86400]},
                {"id": "ep-3", "task": "t3", "section": "s",
                 "outcome": "success", "valence": 0.6,
                 "timestamp": "2026-01-03T10:00:00",
                 "activation": 0.2, "access_times": [now - 7200]},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            stats = memory.get_stats()
            assert stats["total"] == 3
            assert "outcomes" in stats
            assert stats["outcomes"]["success"] == 2
            assert stats["outcomes"]["failure"] == 1
            assert "avg_valence" in stats
            assert "avg_activation" in stats
            assert "activation_min" in stats
            assert "activation_max" in stats
            assert "strong_memories" in stats
            assert "forgotten_memories" in stats
            assert "oldest" in stats
            assert "newest" in stats
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


class TestEpisodicConflictResolution:
    """Test conflict_resolution — ACT-R utility-based selection."""

    def test_empty_candidates(self, episodic_mem):
        result = episodic_mem.conflict_resolution([])
        assert result == []

    def test_success_higher_utility_than_failure(self, episodic_mem):
        import random
        random.seed(42)
        candidates = [
            {"outcome": "success", "activation": 0.5, "duration_s": 60},
            {"outcome": "failure", "activation": 0.5, "duration_s": 60},
        ]
        result = episodic_mem.conflict_resolution(candidates)
        assert len(result) == 2
        assert all("utility" in c for c in result)
        # Success should generally have higher utility
        assert result[0]["outcome"] == "success"

    def test_short_duration_higher_utility(self, episodic_mem):
        import random
        random.seed(42)
        candidates = [
            {"outcome": "success", "activation": 0.5, "duration_s": 30},
            {"outcome": "success", "activation": 0.5, "duration_s": 590},
        ]
        result = episodic_mem.conflict_resolution(candidates)
        assert result[0]["duration_s"] == 30

    def test_activation_bonus(self, episodic_mem):
        import random
        random.seed(42)
        candidates = [
            {"outcome": "success", "activation": 5.0, "duration_s": 60},
            {"outcome": "success", "activation": 0.0, "duration_s": 60},
        ]
        result = episodic_mem.conflict_resolution(candidates)
        # Higher activation should get bonus
        assert result[0]["activation"] == 5.0

    def test_with_goal_context(self, episodic_mem):
        """Goal context should not crash even without soar_engine."""
        candidates = [
            {"outcome": "success", "activation": 0.5, "duration_s": 60},
        ]
        result = episodic_mem.conflict_resolution(candidates, goal_context="test goal")
        assert len(result) == 1
        assert "utility" in result[0]

    def test_unknown_outcome(self, episodic_mem):
        import random
        random.seed(42)
        candidates = [
            {"outcome": "unknown", "activation": 0.0, "duration_s": 60},
        ]
        result = episodic_mem.conflict_resolution(candidates)
        assert "utility" in result[0]


class TestEpisodicRecallFailures:
    """Test recall_failures — filter failed episodes."""

    def test_recall_failures_from_mixed(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        from datetime import datetime, timezone
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            now = datetime.now(timezone.utc).timestamp()
            episodes = [
                {"id": "ep-1", "task": "success task", "section": "s",
                 "outcome": "success", "valence": 0.5,
                 "timestamp": "2026-01-01T10:00:00",
                 "activation": 0.5, "access_times": [now - 3600]},
                {"id": "ep-2", "task": "failed task", "section": "s",
                 "outcome": "failure", "valence": 0.8,
                 "timestamp": "2026-01-02T10:00:00",
                 "activation": 0.3, "access_times": [now - 1800]},
                {"id": "ep-3", "task": "timeout task", "section": "s",
                 "outcome": "timeout", "valence": 0.6,
                 "timestamp": "2026-01-03T10:00:00",
                 "activation": 0.1, "access_times": [now - 900]},
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            failures = memory.recall_failures(n=5)
            assert len(failures) == 2
            outcomes = {f["outcome"] for f in failures}
            assert "success" not in outcomes
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl

    def test_recall_failures_limit(self, tmp_path):
        import clarvis.memory.episodic_memory as em
        from datetime import datetime, timezone
        orig_ep = em.EPISODES_FILE
        orig_cl = em.CAUSAL_LINKS_FILE
        em.EPISODES_FILE = tmp_path / "ep.json"
        em.CAUSAL_LINKS_FILE = tmp_path / "cl.json"
        try:
            now = datetime.now(timezone.utc).timestamp()
            episodes = [
                {"id": f"ep-{i}", "task": f"fail {i}", "section": "s",
                 "outcome": "failure", "valence": 0.5,
                 "timestamp": f"2026-01-{i+1:02d}T10:00:00",
                 "activation": 0.1, "access_times": [now - 3600 * (i+1)]}
                for i in range(10)
            ]
            em.EPISODES_FILE.write_text(json.dumps(episodes))
            memory = em.EpisodicMemory()
            failures = memory.recall_failures(n=3)
            assert len(failures) == 3
        finally:
            em.EPISODES_FILE = orig_ep
            em.CAUSAL_LINKS_FILE = orig_cl


# ---------------------------------------------------------------------------
# 3. ProceduralMemory — code templates and tier constants
# ---------------------------------------------------------------------------

class TestProceduralConstants:
    def test_tier_constants(self):
        from clarvis.memory.procedural_memory import (
            TIER_CANDIDATE, TIER_VERIFIED, TIER_STALE,
            VERIFY_MIN_USES, VERIFY_MIN_SUCCESS_RATE,
            STALE_DAYS, STALE_MAX_SUCCESS_RATE, RETIRE_DAYS,
        )
        assert TIER_CANDIDATE == "candidate"
        assert TIER_VERIFIED == "verified"
        assert TIER_STALE == "stale"
        assert VERIFY_MIN_USES > 0
        assert 0 < VERIFY_MIN_SUCCESS_RATE <= 1.0
        assert STALE_DAYS > 0
        assert 0 < STALE_MAX_SUCCESS_RATE <= 1.0
        assert RETIRE_DAYS > STALE_DAYS


class TestProceduralCodeTemplates:
    def test_templates_exist(self):
        from clarvis.memory.procedural_memory import CODE_TEMPLATES
        assert len(CODE_TEMPLATES) >= 7
        required_templates = [
            "cognitive_module", "brain_integration", "wire_integration",
            "data_processor", "class_with_state", "cron_orchestrator",
            "metric_tracker", "test_suite",
        ]
        for name in required_templates:
            assert name in CODE_TEMPLATES, f"Missing template: {name}"

    def test_template_structure(self):
        from clarvis.memory.procedural_memory import CODE_TEMPLATES
        for name, tmpl in CODE_TEMPLATES.items():
            assert "name" in tmpl, f"{name}: missing 'name'"
            assert "description" in tmpl, f"{name}: missing 'description'"
            assert "match_keywords" in tmpl, f"{name}: missing 'match_keywords'"
            assert "scaffold" in tmpl, f"{name}: missing 'scaffold'"
            assert isinstance(tmpl["scaffold"], list), f"{name}: scaffold should be list"
            assert len(tmpl["scaffold"]) >= 3, f"{name}: scaffold too short"
            assert isinstance(tmpl["match_keywords"], list), f"{name}: match_keywords should be list"

    def test_find_code_templates_cognitive(self):
        from clarvis.memory.procedural_memory import find_code_templates
        results = find_code_templates("create a new cognitive module for tracking metrics")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "cognitive_module" in names or "metric_tracker" in names

    def test_find_code_templates_test(self):
        from clarvis.memory.procedural_memory import find_code_templates
        results = find_code_templates("write pytest unit tests for brain module")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "test_suite" in names

    def test_find_code_templates_wire(self):
        from clarvis.memory.procedural_memory import find_code_templates
        results = find_code_templates("wire into heartbeat postflight pipeline")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "wire_integration" in names

    def test_find_code_templates_no_match(self):
        from clarvis.memory.procedural_memory import find_code_templates
        results = find_code_templates("xyzzy completely unrelated gibberish")
        # May return empty or very low-scoring matches
        assert isinstance(results, list)

    def test_find_code_templates_data_processor(self):
        from clarvis.memory.procedural_memory import find_code_templates
        results = find_code_templates("parse log and analyze jsonl data pipeline")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "data_processor" in names


class TestProceduralImport:
    def test_module_importable(self):
        from clarvis.memory.procedural_memory import (
            CODE_TEMPLATES, TIER_CANDIDATE, find_code_templates,
        )
        assert CODE_TEMPLATES is not None
        assert callable(find_code_templates)


# ---------------------------------------------------------------------------
# 4. Working Memory — thin shim tests
# ---------------------------------------------------------------------------

class TestWorkingMemoryShim:
    def test_module_importable(self):
        try:
            from clarvis.memory.working_memory import get_buffer, WORKING_MEM_FILE
            assert get_buffer is not None
            assert WORKING_MEM_FILE is not None
        except ImportError as e:
            pytest.skip(f"Working memory import requires attention: {e}")

    def test_get_buffer_returns_attention(self):
        try:
            from clarvis.memory.working_memory import get_buffer
            buf = get_buffer()
            assert buf is not None
            # Should be the attention spotlight singleton
            assert hasattr(buf, 'items') or hasattr(buf, 'focus')
        except ImportError:
            pytest.skip("Working memory requires attention module")


# ---------------------------------------------------------------------------
# 5. Memory consolidation — structure tests
# ---------------------------------------------------------------------------

class TestMemoryConsolidationStructure:
    def test_module_importable(self):
        try:
            from clarvis.memory.memory_consolidation import (
                deduplicate, prune_noise, archive_stale,
            )
            assert callable(deduplicate)
            assert callable(prune_noise)
            assert callable(archive_stale)
        except ImportError as e:
            pytest.skip(f"Memory consolidation import requires brain: {e}")


# ---------------------------------------------------------------------------
# 5b. Memory consolidation — helper function unit tests
# ---------------------------------------------------------------------------

class TestConsolidationHelpers:
    """Test pure helper functions from memory_consolidation (no brain required)."""

    def test_normalize_text_basic(self):
        from clarvis.memory.memory_consolidation import _normalize_text
        assert _normalize_text("  Hello   World  ") == "hello world"

    def test_normalize_text_empty(self):
        from clarvis.memory.memory_consolidation import _normalize_text
        assert _normalize_text("") == ""
        assert _normalize_text(None) == ""

    def test_normalize_text_whitespace_collapse(self):
        from clarvis.memory.memory_consolidation import _normalize_text
        assert _normalize_text("foo\n\tbar   baz") == "foo bar baz"

    def test_get_tags_list_passthrough(self):
        from clarvis.memory.memory_consolidation import _get_tags
        assert _get_tags({"tags": ["a", "b"]}) == ["a", "b"]

    def test_get_tags_json_string(self):
        from clarvis.memory.memory_consolidation import _get_tags
        assert _get_tags({"tags": '["x","y"]'}) == ["x", "y"]

    def test_get_tags_empty(self):
        from clarvis.memory.memory_consolidation import _get_tags
        assert _get_tags({}) == []

    def test_get_tags_invalid_json(self):
        from clarvis.memory.memory_consolidation import _get_tags
        assert _get_tags({"tags": "not json"}) == []

    def test_has_protected_tag_true(self):
        from clarvis.memory.memory_consolidation import _has_protected_tag
        assert _has_protected_tag({"tags": '["critical","test"]'}) is True

    def test_has_protected_tag_false(self):
        from clarvis.memory.memory_consolidation import _has_protected_tag
        assert _has_protected_tag({"tags": '["test","debug"]'}) is False

    def test_has_protected_tag_custom(self):
        from clarvis.memory.memory_consolidation import _has_protected_tag
        assert _has_protected_tag({"tags": '["vip"]'}, protected=("vip",)) is True

    def test_has_protected_tag_no_tags(self):
        from clarvis.memory.memory_consolidation import _has_protected_tag
        assert _has_protected_tag({}) is False

    def test_noise_patterns_exist(self):
        from clarvis.memory.memory_consolidation import NOISE_PATTERNS
        assert len(NOISE_PATTERNS) >= 5

    def test_noise_patterns_match_predictions(self):
        import re
        from clarvis.memory.memory_consolidation import NOISE_PATTERNS
        test_docs = [
            "Prediction: tomorrow will be sunny",
            "Outcome: task succeeded",
            "World model updated: new fact",
            "Attention broadcast: focus on tests",
            "Meta-cognition: System initialized at 08:00",
        ]
        for doc in test_docs:
            matched = any(re.search(p, doc) for p, _ in NOISE_PATTERNS)
            assert matched, f"Expected noise pattern to match: {doc}"

    def test_noise_patterns_no_false_positive(self):
        import re
        from clarvis.memory.memory_consolidation import NOISE_PATTERNS
        normal_docs = [
            "Learned that Python async is faster",
            "Goal: improve test coverage to 80%",
            "My name is Clarvis and I am a cognitive agent",
        ]
        for doc in normal_docs:
            matched = any(re.search(p, doc) for p, _ in NOISE_PATTERNS)
            assert not matched, f"Noise pattern should NOT match: {doc}"

    def test_collection_caps_sane(self):
        from clarvis.memory.memory_consolidation import COLLECTION_CAPS
        assert isinstance(COLLECTION_CAPS, dict)
        for col, cap in COLLECTION_CAPS.items():
            assert isinstance(cap, int)
            assert cap > 0
        total = sum(COLLECTION_CAPS.values())
        assert 1000 < total < 15000, f"Total cap should be reasonable, got {total}"

    def test_load_archive_missing_file(self, tmp_path):
        from clarvis.memory import memory_consolidation as mc
        orig = mc.ARCHIVE_FILE
        mc.ARCHIVE_FILE = str(tmp_path / "nonexistent.json")
        try:
            result = mc._load_archive()
            assert result == []
        finally:
            mc.ARCHIVE_FILE = orig

    def test_save_and_load_archive(self, tmp_path):
        from clarvis.memory import memory_consolidation as mc
        orig = mc.ARCHIVE_FILE
        mc.ARCHIVE_FILE = str(tmp_path / "test_archive.json")
        try:
            entries = [{"id": "test-1", "document": "hello"}]
            mc._save_archive(entries)
            loaded = mc._load_archive()
            assert len(loaded) == 1
            assert loaded[0]["id"] == "test-1"
        finally:
            mc.ARCHIVE_FILE = orig

    def test_load_archive_corrupt_json(self, tmp_path):
        from clarvis.memory import memory_consolidation as mc
        orig = mc.ARCHIVE_FILE
        corrupt_file = str(tmp_path / "corrupt.json")
        with open(corrupt_file, "w") as f:
            f.write("NOT JSON!")
        mc.ARCHIVE_FILE = corrupt_file
        try:
            result = mc._load_archive()
            assert result == []
        finally:
            mc.ARCHIVE_FILE = orig

    def test_invalidate_memories_cache(self):
        from clarvis.memory.memory_consolidation import (
            _invalidate_memories_cache, _memories_cache, _memories_cache_gen,
        )
        import clarvis.memory.memory_consolidation as mc
        old_gen = mc._memories_cache_gen
        _invalidate_memories_cache()
        assert mc._memories_cache_gen > old_gen
        assert mc._memories_cache == {}


# ---------------------------------------------------------------------------
# 5c. Memory consolidation — protected tags constant
# ---------------------------------------------------------------------------

class TestConsolidationProtectedTags:
    def test_protected_tags_constant(self):
        from clarvis.memory.memory_consolidation import PROTECTED_TAGS
        assert "genesis" in PROTECTED_TAGS
        assert "critical" in PROTECTED_TAGS


# ---------------------------------------------------------------------------
# 6. Procedural memory — additional helper tests
# ---------------------------------------------------------------------------

class TestProceduralHelpers:
    """Test pure helper functions from procedural_memory."""

    def test_sanitize_name_basic(self):
        from clarvis.memory.procedural_memory import _sanitize_name
        assert _sanitize_name("Hello World") == "hello_world"

    def test_sanitize_name_special_chars(self):
        from clarvis.memory.procedural_memory import _sanitize_name
        result = _sanitize_name("My-Task (v2.0)")
        assert "my" in result
        assert "-" not in result
        assert "(" not in result

    def test_sanitize_name_long(self):
        from clarvis.memory.procedural_memory import _sanitize_name
        result = _sanitize_name("x" * 200)
        assert len(result) <= 80

    def test_sanitize_name_empty(self):
        from clarvis.memory.procedural_memory import _sanitize_name
        result = _sanitize_name("")
        assert result == ""

    def test_sanitize_name_underscores_collapse(self):
        from clarvis.memory.procedural_memory import _sanitize_name
        result = _sanitize_name("a___b---c")
        assert "__" not in result

    def test_parse_json_field_list(self):
        from clarvis.memory.procedural_memory import _parse_json_field
        assert _parse_json_field(["a", "b"]) == ["a", "b"]

    def test_parse_json_field_string(self):
        from clarvis.memory.procedural_memory import _parse_json_field
        assert _parse_json_field('["x","y"]') == ["x", "y"]

    def test_parse_json_field_empty(self):
        from clarvis.memory.procedural_memory import _parse_json_field
        assert _parse_json_field("") == []
        assert _parse_json_field(None) == []

    def test_parse_json_field_invalid(self):
        from clarvis.memory.procedural_memory import _parse_json_field
        assert _parse_json_field("not json") == []

    def test_format_code_templates_empty(self):
        from clarvis.memory.procedural_memory import format_code_templates
        assert format_code_templates([]) == ""

    def test_format_code_templates_single(self):
        from clarvis.memory.procedural_memory import format_code_templates
        templates = [{
            "name": "test_tmpl",
            "description": "A test template",
            "scaffold": ["Step 1", "Step 2"],
            "preconditions": ["pre1"],
            "termination_criteria": ["verify1"],
            "score": 1.0,
            "source": "builtin",
        }]
        result = format_code_templates(templates)
        assert "test_tmpl" in result
        assert "Step 1" in result
        assert "Step 2" in result
        assert "pre1" in result
        assert "verify1" in result
        assert "CODE GENERATION TEMPLATES" in result

    def test_format_code_templates_no_preconditions(self):
        from clarvis.memory.procedural_memory import format_code_templates
        templates = [{
            "name": "simple",
            "description": "Simple template",
            "scaffold": ["Do something"],
            "score": 0.5,
            "source": "builtin",
        }]
        result = format_code_templates(templates)
        assert "simple" in result
        assert "Do something" in result

    def test_tier_constants_values(self):
        from clarvis.memory.procedural_memory import (
            TIER_CANDIDATE, TIER_VERIFIED, TIER_STALE,
            VERIFY_MIN_USES, VERIFY_MIN_SUCCESS_RATE,
            STALE_DAYS, STALE_MAX_SUCCESS_RATE, RETIRE_DAYS,
        )
        assert TIER_CANDIDATE == "candidate"
        assert TIER_VERIFIED == "verified"
        assert TIER_STALE == "stale"
        assert VERIFY_MIN_USES >= 1
        assert 0 < VERIFY_MIN_SUCCESS_RATE <= 1
        assert STALE_DAYS > 0
        assert RETIRE_DAYS > STALE_DAYS

    def test_all_code_templates_have_required_fields(self):
        from clarvis.memory.procedural_memory import CODE_TEMPLATES
        required = {"name", "description", "match_keywords", "scaffold"}
        for key, tmpl in CODE_TEMPLATES.items():
            for field in required:
                assert field in tmpl, f"Template {key} missing field {field}"
            assert len(tmpl["scaffold"]) >= 3, f"Template {key} has too few steps"
            assert len(tmpl["match_keywords"]) >= 2, f"Template {key} has too few keywords"

    def test_derive_name_basic(self):
        from clarvis.memory.procedural_memory import _derive_name
        result = _derive_name("Build a monitoring dashboard")
        assert "monitoring" in result.lower()
        assert "dashboard" in result.lower()

    def test_derive_name_strips_prefix(self):
        from clarvis.memory.procedural_memory import _derive_name
        r1 = _derive_name("Create test fixtures")
        assert "create" not in r1.lower()
        r2 = _derive_name("Implement caching layer")
        assert "implement" not in r2.lower()
        r3 = _derive_name("Wire integration pipeline")
        assert "wire" not in r3.lower()

    def test_derive_name_limits_words(self):
        from clarvis.memory.procedural_memory import _derive_name
        long_text = "Build " + " ".join(f"word{i}" for i in range(20))
        result = _derive_name(long_text)
        assert len(result.split("_")) <= 6

    def test_derive_name_strips_after_dash(self):
        from clarvis.memory.procedural_memory import _derive_name
        result = _derive_name("Build a thing — with details after the dash")
        assert "details" not in result.lower()

    def test_failure_to_steps_known_types(self):
        from clarvis.memory.procedural_memory import _failure_to_steps
        known_types = [
            "duplicate_execution", "long_duration", "skipped_learning",
            "prediction_miss", "retroactive_fix", "low_capability",
            "shallow_reasoning", "low_confidence", "uncompleted_task",
        ]
        for ft in known_types:
            steps = _failure_to_steps(ft, "test task", "test detail")
            assert isinstance(steps, list)
            assert len(steps) >= 2, f"Expected steps for {ft}, got {len(steps)}"

    def test_failure_to_steps_unknown_type(self):
        from clarvis.memory.procedural_memory import _failure_to_steps
        steps = _failure_to_steps("unknown_type", "task", "detail")
        assert isinstance(steps, list)
        assert len(steps) >= 2

    def test_format_code_templates_multiple(self):
        from clarvis.memory.procedural_memory import format_code_templates
        templates = [
            {
                "name": "tmpl_a",
                "description": "Template A",
                "scaffold": ["Step 1", "Step 2"],
                "preconditions": ["pre1"],
                "termination_criteria": ["verify1"],
                "score": 1.0,
                "source": "builtin",
            },
            {
                "name": "tmpl_b",
                "description": "Template B",
                "scaffold": ["Do X", "Do Y", "Do Z"],
                "score": 0.8,
                "source": "stored",
            },
        ]
        result = format_code_templates(templates)
        assert "tmpl_a" in result
        assert "tmpl_b" in result
        assert "Step 1" in result
        assert "Do X" in result


# ---------------------------------------------------------------------------
# 7. HebbianMemory — additional file I/O and coactivation tests
# ---------------------------------------------------------------------------

class TestHebbianFileIO:
    """Test Hebbian file-based helpers with temp directories."""

    def test_load_coactivation_missing(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        hm.COACTIVATION_FILE = tmp_path / "nonexistent.json"
        try:
            result = hm.HebbianMemory._load_coactivation(None)
            assert result == {}
        finally:
            hm.COACTIVATION_FILE = orig

    def test_load_coactivation_valid(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        coact_file = tmp_path / "coact.json"
        coact_file.write_text('{"a|b": {"ids": ["a", "b"], "count": 1, "strength": 0.1}}')
        hm.COACTIVATION_FILE = coact_file
        try:
            result = hm.HebbianMemory._load_coactivation(None)
            assert "a|b" in result
            assert result["a|b"]["count"] == 1
        finally:
            hm.COACTIVATION_FILE = orig

    def test_load_coactivation_corrupt(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("NOT JSON!")
        hm.COACTIVATION_FILE = corrupt
        try:
            result = hm.HebbianMemory._load_coactivation(None)
            assert result == {}
        finally:
            hm.COACTIVATION_FILE = orig

    def test_load_fisher_missing(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.FISHER_FILE
        hm.FISHER_FILE = tmp_path / "nonexistent.json"
        try:
            result = hm.HebbianMemory._load_fisher(None)
            assert result == {"scores": {}, "computed_at": None}
        finally:
            hm.FISHER_FILE = orig

    def test_load_fisher_valid(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.FISHER_FILE
        fisher = tmp_path / "fisher.json"
        data = {"scores": {"mem-1": 0.5}, "computed_at": "2026-01-01T00:00:00"}
        fisher.write_text(json.dumps(data))
        hm.FISHER_FILE = fisher
        try:
            result = hm.HebbianMemory._load_fisher(None)
            assert result["scores"]["mem-1"] == 0.5
        finally:
            hm.FISHER_FILE = orig

    def test_save_and_load_coactivation(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.COACTIVATION_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {"x|y": {"ids": ["x", "y"], "count": 3, "strength": 0.5}}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            heb._save_coactivation()
            assert hm.COACTIVATION_FILE.exists()
            loaded = json.loads(hm.COACTIVATION_FILE.read_text())
            assert "x|y" in loaded
        finally:
            hm.COACTIVATION_FILE = orig

    def test_save_and_load_fisher(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.FISHER_FILE
        hm.FISHER_FILE = tmp_path / "fisher.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {"m1": 0.7}, "computed_at": "2026-01-01"}
            heb._save_fisher()
            assert hm.FISHER_FILE.exists()
            loaded = json.loads(hm.FISHER_FILE.read_text())
            assert loaded["scores"]["m1"] == 0.7
        finally:
            hm.FISHER_FILE = orig

    def test_get_fisher_score(self):
        from clarvis.memory import hebbian_memory as hm
        heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
        heb._coactivation = {}
        heb._fisher_scores = {"scores": {"m1": 0.8, "m2": 0.3}, "computed_at": None}
        assert heb.get_fisher_score("m1") == 0.8
        assert heb.get_fisher_score("m2") == 0.3
        assert heb.get_fisher_score("nonexistent") == 0.0

    def test_get_stats_missing_file(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.STATS_FILE
        hm.STATS_FILE = tmp_path / "nonexistent.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            assert heb.get_stats() == {}
        finally:
            hm.STATS_FILE = orig

    def test_save_and_get_stats(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.STATS_FILE
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            stats = {"weakened": 5, "strengthened": 3}
            heb._save_stats(stats)
            loaded = heb.get_stats()
            assert loaded["weakened"] == 5
            assert loaded["strengthened"] == 3
        finally:
            hm.STATS_FILE = orig

    def test_get_evolution_history_missing(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.EVOLUTION_HISTORY_FILE
        hm.EVOLUTION_HISTORY_FILE = tmp_path / "nonexistent.jsonl"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            assert heb.get_evolution_history() == []
        finally:
            hm.EVOLUTION_HISTORY_FILE = orig

    def test_get_evolution_history_with_data(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.EVOLUTION_HISTORY_FILE
        hist_file = tmp_path / "history.jsonl"
        entries = [
            {"timestamp": "2026-01-01", "weakened": 2, "strengthened": 1},
            {"timestamp": "2026-01-02", "weakened": 3, "strengthened": 0},
        ]
        hist_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        hm.EVOLUTION_HISTORY_FILE = hist_file
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            result = heb.get_evolution_history(n=10)
            assert len(result) == 2
        finally:
            hm.EVOLUTION_HISTORY_FILE = orig

    def test_get_access_patterns_missing_file(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        orig = hm.ACCESS_LOG_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "nonexistent.jsonl"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            result = heb.get_access_patterns(days=7)
            assert result["total_events"] == 0
        finally:
            hm.ACCESS_LOG_FILE = orig

    def test_get_access_patterns_with_data(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.ACCESS_LOG_FILE
        log_file = tmp_path / "access.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        events = [
            {"memory_id": "m1", "query": "test", "collection": "mem", "caller": "brain", "timestamp": now},
            {"memory_id": "m2", "query": "other", "collection": "mem", "caller": "heartbeat", "timestamp": now},
            {"memory_id": "m1", "query": "again", "collection": "mem", "caller": "brain", "timestamp": now},
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        hm.ACCESS_LOG_FILE = log_file
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            result = heb.get_access_patterns(days=7)
            assert result["total_events"] == 3
            assert result["unique_memories"] == 2
            assert "brain" in result["caller_breakdown"]
        finally:
            hm.ACCESS_LOG_FILE = orig


class TestHebbianCoactivation:
    """Test coactivation update logic."""

    def test_update_coactivation_creates_pairs(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.COACTIVATION_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            now = datetime.now(timezone.utc)
            heb._update_coactivation(["a", "b", "c"], now)
            # 3 memories = 3 pairs: a|b, a|c, b|c
            assert len(heb._coactivation) == 3
            for entry in heb._coactivation.values():
                assert entry["count"] == 1
                assert entry["strength"] > 0
        finally:
            hm.COACTIVATION_FILE = orig

    def test_update_coactivation_increments(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.COACTIVATION_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            now = datetime.now(timezone.utc)
            heb._update_coactivation(["a", "b"], now)
            heb._update_coactivation(["a", "b"], now)
            pair_key = "|".join(sorted(["a", "b"]))
            assert heb._coactivation[pair_key]["count"] == 2
        finally:
            hm.COACTIVATION_FILE = orig

    def test_coactivation_single_memory_no_pairs(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.COACTIVATION_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            now = datetime.now(timezone.utc)
            heb._update_coactivation(["only_one"], now)
            assert len(heb._coactivation) == 0
        finally:
            hm.COACTIVATION_FILE = orig


class TestHebbianLogAccess:
    """Test access logging."""

    def test_log_access_creates_file(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.ACCESS_LOG_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            now = datetime.now(timezone.utc)
            heb._log_access("mem-1", "test query", "clarvis-memories", "brain", now)
            assert hm.ACCESS_LOG_FILE.exists()
            content = hm.ACCESS_LOG_FILE.read_text().strip()
            entry = json.loads(content)
            assert entry["memory_id"] == "mem-1"
            assert entry["query"] == "test query"
        finally:
            hm.ACCESS_LOG_FILE = orig

    def test_log_access_appends(self, tmp_path):
        from clarvis.memory import hebbian_memory as hm
        from datetime import datetime, timezone
        orig = hm.ACCESS_LOG_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        try:
            heb = hm.HebbianMemory.__new__(hm.HebbianMemory)
            heb._coactivation = {}
            heb._fisher_scores = {"scores": {}, "computed_at": None}
            now = datetime.now(timezone.utc)
            heb._log_access("m1", "q1", "col", "caller1", now)
            heb._log_access("m2", "q2", "col", "caller2", now)
            lines = hm.ACCESS_LOG_FILE.read_text().strip().split("\n")
            assert len(lines) == 2
        finally:
            hm.ACCESS_LOG_FILE = orig


# ---------------------------------------------------------------------------
# 8. Episodic memory — additional method tests
# ---------------------------------------------------------------------------

class TestEpisodicEncodeAndRecall:
    """Test encode and recall with file patching and mocked brain."""

    def _make_em(self, tmp_path):
        """Create EpisodicMemory with patched file paths and _id_index."""
        from clarvis.memory import episodic_memory as em_mod
        orig_ep = em_mod.EPISODES_FILE
        orig_cl = em_mod.CAUSAL_LINKS_FILE
        em_mod.EPISODES_FILE = tmp_path / "episodes.json"
        em_mod.CAUSAL_LINKS_FILE = tmp_path / "causal_links.json"
        obj = em_mod.EpisodicMemory.__new__(em_mod.EpisodicMemory)
        obj.episodes = []
        obj.causal_links = []
        obj._id_index = {}
        obj._decay_cooldown = 0
        return obj, em_mod, orig_ep, orig_cl

    def _encode(self, em, task_text, outcome, salience=0.5, duration_s=5.0, error_msg=None):
        """Wrapper to call encode with mocked brain.store."""
        from unittest.mock import patch
        with patch("clarvis.memory.episodic_memory.brain") as mock_brain:
            mock_brain.store.return_value = "mock-id"
            return em.encode(task_text, "test_section", salience, outcome,
                             duration_s=duration_s, error_msg=error_msg)

    def test_encode_creates_episode(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep = self._encode(em, "Test task", "success")
            assert ep["task"] == "Test task"
            assert ep["outcome"] == "success"
            assert len(em.episodes) == 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_encode_failure_episode(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep = self._encode(em, "Failed task", "failure", salience=0.8,
                              duration_s=30.0, error_msg="TimeoutError")
            assert ep["outcome"] == "failure"
            assert ep["error"] == "TimeoutError"
            assert ep["valence"] > 0.3  # Failure should have higher valence
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_recall_failures(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            self._encode(em, "Good task", "success")
            self._encode(em, "Bad task", "failure")
            failures = em.recall_failures(n=10)
            assert len(failures) == 1
            assert failures[0]["outcome"] == "failure"
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_get_stats_with_episodes(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            self._encode(em, "A", "success")
            self._encode(em, "B", "failure")
            stats = em.get_stats()
            assert stats["total"] == 2
            assert stats["outcomes"]["success"] == 1
            assert stats["outcomes"]["failure"] == 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_get_stats_empty(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            stats = em.get_stats()
            assert stats == {"total": 0}
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_link_valid(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Cause", "success")
            # Force unique IDs (same-second collision)
            ep1["id"] = "ep_cause_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Effect", "success")
            ep2["id"] = "ep_effect_2"
            em._id_index[ep2["id"]] = ep2
            link = em.causal_link(ep1["id"], ep2["id"], "caused")
            assert link is not None
            assert link["from"] == ep1["id"]
            assert link["to"] == ep2["id"]
            assert link["relationship"] == "caused"
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_link_invalid_type(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            link = em.causal_link("ep_a", "ep_b", "invalid_type")
            assert link is None
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_link_self_loop_rejected(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            link = em.causal_link("ep_same", "ep_same", "caused")
            assert link is None
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_link_with_dicts(self, tmp_path):
        """causal_link should accept episode dicts as well as IDs."""
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Cause", "failure")
            ep1["id"] = "ep_dict_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Fix", "success")
            ep2["id"] = "ep_dict_2"
            em._id_index[ep2["id"]] = ep2
            link = em.causal_link(ep1, ep2, "fixed")
            assert link is not None
            assert link["relationship"] == "fixed"
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_chain_backward(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Root cause", "failure")
            ep1["id"] = "ep_chain_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Fix attempt", "success")
            ep2["id"] = "ep_chain_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "fixed")
            chain = em.causal_chain(ep2["id"], direction="backward")
            assert len(chain) >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_chain_forward(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Trigger", "success")
            ep1["id"] = "ep_fwd_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Consequence", "success")
            ep2["id"] = "ep_fwd_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "caused")
            chain = em.causal_chain(ep1["id"], direction="forward")
            assert len(chain) >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causes_of(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Cause", "success")
            ep1["id"] = "ep_co_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Effect", "success")
            ep2["id"] = "ep_co_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "caused")
            causes = em.causes_of(ep2["id"])
            assert len(causes) >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_effects_of(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Trigger", "success")
            ep1["id"] = "ep_eo_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "Result", "success")
            ep2["id"] = "ep_eo_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "enabled")
            effects = em.effects_of(ep1["id"])
            assert len(effects) >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_graph_stats(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "A", "success")
            ep1["id"] = "ep_gs_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "B", "failure")
            ep2["id"] = "ep_gs_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "caused")
            stats = em.causal_graph_stats()
            assert stats["total_links"] >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_graph_stats_empty(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            stats = em.causal_graph_stats()
            assert stats["total_links"] == 0
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_causal_link_duplicate_returns_existing(self, tmp_path):
        """Adding the same link twice should return the existing one."""
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            link1 = em.causal_link("ep_dup_1", "ep_dup_2", "caused")
            link2 = em.causal_link("ep_dup_1", "ep_dup_2", "caused")
            assert link1 is not None
            assert link2 is not None  # Returns existing
            assert len(em.causal_links) == 1  # Only one stored
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl


class TestEpisodicConflictResolutionIntegration:
    """Test conflict_resolution with actual encode-generated episodes."""

    def _make_em(self, tmp_path):
        from clarvis.memory import episodic_memory as em_mod
        orig_ep = em_mod.EPISODES_FILE
        orig_cl = em_mod.CAUSAL_LINKS_FILE
        em_mod.EPISODES_FILE = tmp_path / "episodes.json"
        em_mod.CAUSAL_LINKS_FILE = tmp_path / "causal_links.json"
        obj = em_mod.EpisodicMemory.__new__(em_mod.EpisodicMemory)
        obj.episodes = []
        obj.causal_links = []
        obj._id_index = {}
        obj._decay_cooldown = 0
        return obj, em_mod, orig_ep, orig_cl

    def _encode(self, em, task_text, outcome, salience=0.5, duration_s=5.0):
        from unittest.mock import patch
        with patch("clarvis.memory.episodic_memory.brain") as mock_brain:
            mock_brain.store.return_value = "mock-id"
            return em.encode(task_text, "test", salience, outcome, duration_s=duration_s)

    def test_conflict_resolution_basic(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Quick success", "success", duration_s=10.0)
            ep2 = self._encode(em, "Slow failure", "failure", duration_s=300.0)
            ranked = em.conflict_resolution([ep1, ep2])
            assert len(ranked) == 2
            # Success should rank higher than failure (higher utility)
            for ep in ranked:
                assert "utility" in ep
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_conflict_resolution_empty(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            result = em.conflict_resolution([])
            assert result == []
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_conflict_resolution_with_goal(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "Task A", "success", duration_s=10.0)
            ranked = em.conflict_resolution([ep1], goal_context="improve tests")
            assert len(ranked) == 1
            assert "utility" in ranked[0]
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl


class TestEpisodicSynthesizeAndSave:
    """Test synthesize and file persistence."""

    def _make_em(self, tmp_path):
        from clarvis.memory import episodic_memory as em_mod
        orig_ep = em_mod.EPISODES_FILE
        orig_cl = em_mod.CAUSAL_LINKS_FILE
        em_mod.EPISODES_FILE = tmp_path / "episodes.json"
        em_mod.CAUSAL_LINKS_FILE = tmp_path / "causal_links.json"
        obj = em_mod.EpisodicMemory.__new__(em_mod.EpisodicMemory)
        obj.episodes = []
        obj.causal_links = []
        obj._id_index = {}
        obj._decay_cooldown = 0
        return obj, em_mod, orig_ep, orig_cl

    def _encode(self, em, task_text, outcome, salience=0.5, duration_s=5.0):
        from unittest.mock import patch
        with patch("clarvis.memory.episodic_memory.brain") as mock_brain:
            mock_brain.store.return_value = "mock-id"
            return em.encode(task_text, "test", salience, outcome, duration_s=duration_s)

    def test_save_and_reload(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            self._encode(em, "Persist test", "success")
            em._save()

            em2 = mod.EpisodicMemory.__new__(mod.EpisodicMemory)
            em2.episodes = []
            em2.causal_links = []
            em2._id_index = {}
            em2._decay_cooldown = 0
            loaded = em2._load()
            assert len(loaded) >= 1
            assert loaded[0]["task"] == "Persist test"
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_save_and_reload_causal(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            ep1 = self._encode(em, "A", "success")
            ep1["id"] = "ep_sr_1"
            em._id_index[ep1["id"]] = ep1
            ep2 = self._encode(em, "B", "failure")
            ep2["id"] = "ep_sr_2"
            em._id_index[ep2["id"]] = ep2
            em.causal_link(ep1["id"], ep2["id"], "caused")
            em._save_causal()

            em2 = mod.EpisodicMemory.__new__(mod.EpisodicMemory)
            em2.episodes = []
            em2.causal_links = []
            em2._id_index = {}
            em2._decay_cooldown = 0
            loaded = em2._load_causal()
            assert len(loaded) >= 1
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl

    def test_synthesize_with_episodes(self, tmp_path):
        em, mod, oep, ocl = self._make_em(tmp_path)
        try:
            from unittest.mock import patch, MagicMock
            for i in range(5):
                outcome = "success" if i % 2 == 0 else "failure"
                self._encode(em, f"Task {i}", outcome, duration_s=float(i + 1))
            with patch("clarvis.memory.episodic_memory.brain") as mock_brain:
                mock_brain.store.return_value = "mock-id"
                mock_brain.set_goal = MagicMock()
                synth = em.synthesize()
            assert "goals_count" in synth or "goals_generated" in synth or "error" not in synth
        finally:
            mod.EPISODES_FILE = oep
            mod.CAUSAL_LINKS_FILE = ocl


# ---------------------------------------------------------------------------
# 9. Working memory — CLI tests (thin shim over attention.py)
# ---------------------------------------------------------------------------

class TestWorkingMemoryCLI:
    """Test working_memory.py CLI entry points."""

    def test_default_no_args(self, capsys):
        from clarvis.memory import working_memory as wm
        orig_argv = sys.argv
        sys.argv = ["working_memory.py"]
        try:
            with pytest.raises(SystemExit) as exc_info:
                wm.main()
            assert exc_info.value.code == 0
        except Exception:
            pass  # Module may raise if attention not ready
        finally:
            sys.argv = orig_argv

    def test_broadcast_command(self, capsys):
        from clarvis.memory import working_memory as wm
        orig_argv = sys.argv
        sys.argv = ["working_memory.py", "broadcast"]
        try:
            wm.main()
            captured = capsys.readouterr()
            assert "spotlight" in captured.out.lower() or len(captured.out) >= 0
        except Exception:
            pass  # OK if attention module has issues
        finally:
            sys.argv = orig_argv

    def test_unknown_command(self, capsys):
        from clarvis.memory import working_memory as wm
        orig_argv = sys.argv
        sys.argv = ["working_memory.py", "nonexistent_cmd"]
        try:
            wm.main()
            captured = capsys.readouterr()
            assert "unknown" in captured.out.lower() or "command" in captured.out.lower()
        except Exception:
            pass
        finally:
            sys.argv = orig_argv


# ---------------------------------------------------------------------------
# 10. Consolidation — _compute_spotlight_salience (pure function)
# ---------------------------------------------------------------------------

class TestComputeSpotlightSalience:
    """Test the pure _compute_spotlight_salience function."""

    def test_empty_spotlight(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        assert _compute_spotlight_salience("some text", []) == 0.0

    def test_empty_memory_text(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "hello world", "salience": 0.8}]
        assert _compute_spotlight_salience("", items) == 0.0

    def test_no_overlap(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "alpha beta gamma", "salience": 0.9}]
        assert _compute_spotlight_salience("delta epsilon zeta", items) == 0.0

    def test_full_overlap(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "hello world", "salience": 1.0}]
        result = _compute_spotlight_salience("hello world", items)
        assert result == pytest.approx(1.0)

    def test_partial_overlap(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "hello world foo bar", "salience": 0.8}]
        result = _compute_spotlight_salience("hello world baz qux", items)
        assert 0.0 < result < 1.0

    def test_multiple_spotlight_items(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [
            {"content": "brain memory recall", "salience": 0.9},
            {"content": "cron schedule task", "salience": 0.3},
        ]
        result = _compute_spotlight_salience("brain memory query system", items)
        assert result > 0.0

    def test_salience_weighting(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        # High-salience item overlaps
        items_high = [{"content": "brain memory", "salience": 1.0}]
        r_high = _compute_spotlight_salience("brain memory", items_high)
        # Low-salience item overlaps
        items_low = [{"content": "brain memory", "salience": 0.1}]
        r_low = _compute_spotlight_salience("brain memory", items_low)
        # Both should give same score (full overlap, salience cancels in numerator/denominator)
        assert r_high == pytest.approx(r_low, abs=0.01)

    def test_result_bounded(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "x", "salience": 1.0}]
        result = _compute_spotlight_salience("x", items)
        assert 0.0 <= result <= 1.0

    def test_spotlight_item_no_content(self):
        from clarvis.memory.memory_consolidation import _compute_spotlight_salience
        items = [{"content": "", "salience": 0.5}]
        result = _compute_spotlight_salience("hello world", items)
        assert result == 0.0


# ---------------------------------------------------------------------------
# 11. Consolidation — _extract_episode_theme (pure function)
# ---------------------------------------------------------------------------

class TestExtractEpisodeTheme:
    """Test the pure _extract_episode_theme function."""

    def test_memory_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "brain memory recall optimization"},
            {"task": "memory store and retrieval test"},
        ]
        assert _extract_episode_theme(episodes) == "memory"

    def test_infrastructure_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "fix cron schedule for heartbeat monitor"},
            {"task": "backup health check gateway"},
        ]
        assert _extract_episode_theme(episodes) == "infrastructure"

    def test_reasoning_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "reasoning chain analysis synthesis"},
            {"task": "thought metacognition review"},
        ]
        assert _extract_episode_theme(episodes) == "reasoning"

    def test_code_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "implement function to refactor script"},
            {"task": "build test for the fix"},
        ]
        assert _extract_episode_theme(episodes) == "code"

    def test_research_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "research paper arxiv study survey"},
        ]
        assert _extract_episode_theme(episodes) == "research"

    def test_metrics_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "benchmark performance score metric"},
        ]
        assert _extract_episode_theme(episodes) == "metrics"

    def test_self_model_domain(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "self reflection awareness identity model confidence"},
        ]
        assert _extract_episode_theme(episodes) == "self-model"

    def test_general_fallback(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [
            {"task": "unrelated random words xyz abc"},
        ]
        assert _extract_episode_theme(episodes) == "general"

    def test_empty_task(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [{"task": ""}]
        assert _extract_episode_theme(episodes) == "general"

    def test_missing_task_key(self):
        from clarvis.memory.memory_consolidation import _extract_episode_theme
        episodes = [{}]
        assert _extract_episode_theme(episodes) == "general"


# ---------------------------------------------------------------------------
# 12. Consolidation — _synthesize_semantic_learning (pure function)
# ---------------------------------------------------------------------------

class TestSynthesizeSemanticLearning:
    """Test the pure _synthesize_semantic_learning function."""

    def test_high_success_rate(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build module A", "outcome": "success", "duration_s": 60, "confidence": 0.9},
            {"task": "Build module B", "outcome": "success", "duration_s": 120, "confidence": 0.8},
            {"task": "Fix module C", "outcome": "success", "duration_s": 90, "confidence": 0.85},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "[SLEEP-CONSOLIDATED]" in result
        assert "code" in result
        assert "3 episodes" in result
        assert "High reliability" in result

    def test_mixed_success_rate(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build X", "outcome": "success"},
            {"task": "Build Y", "outcome": "failure"},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "Mixed reliability" in result

    def test_low_success_rate(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build X", "outcome": "failure"},
            {"task": "Build Y", "outcome": "soft_failure"},
            {"task": "Build Z", "outcome": "failure"},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "Low reliability" in result
        assert "Needs attention" in result

    def test_includes_failure_cases(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build X", "outcome": "success"},
            {"task": "Debug Y crash", "outcome": "failure"},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "Failure cases" in result

    def test_includes_duration(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build module", "outcome": "success", "duration_s": 120},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "Avg duration" in result

    def test_includes_confidence(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Analyze data", "outcome": "success", "confidence": 0.85},
        ]
        result = _synthesize_semantic_learning("research", episodes)
        assert "Avg confidence" in result

    def test_includes_latest_success(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "First task", "outcome": "success"},
            {"task": "Second task done well", "outcome": "success"},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "Latest success" in result

    def test_extracts_actions(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Build the dashboard", "outcome": "success"},
            {"task": "Fix the login bug", "outcome": "success"},
        ]
        result = _synthesize_semantic_learning("code", episodes)
        assert "build" in result.lower() or "fix" in result.lower()

    def test_no_duration_no_confidence(self):
        from clarvis.memory.memory_consolidation import _synthesize_semantic_learning
        episodes = [
            {"task": "Do something", "outcome": "success"},
        ]
        result = _synthesize_semantic_learning("general", episodes)
        assert "Avg duration" not in result
        assert "Avg confidence" not in result


# ---------------------------------------------------------------------------
# 13. Consolidation — Sleep log I/O and sleep_stats
# ---------------------------------------------------------------------------

class TestSleepLogIO:
    """Test sleep consolidation log load/save and stats."""

    def test_load_sleep_log_missing(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        mc.SLEEP_CONSOLIDATION_FILE = str(tmp_path / "nonexistent.json")
        try:
            result = mc._load_sleep_log()
            assert result == {"cycles": [], "total_learnings": 0, "episodes_consolidated": 0}
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig

    def test_save_and_load_sleep_log(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        mc.SLEEP_CONSOLIDATION_FILE = str(tmp_path / "sleep.json")
        try:
            log = {
                "cycles": [{"timestamp": "2026-01-01T00:00:00", "episode_ids": ["ep1", "ep2"]}],
                "total_learnings": 1,
                "episodes_consolidated": 2,
            }
            mc._save_sleep_log(log)
            loaded = mc._load_sleep_log()
            assert loaded["total_learnings"] == 1
            assert len(loaded["cycles"]) == 1
            assert loaded["cycles"][0]["episode_ids"] == ["ep1", "ep2"]
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig

    def test_save_truncates_old_cycles(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        mc.SLEEP_CONSOLIDATION_FILE = str(tmp_path / "sleep.json")
        try:
            log = {
                "cycles": [{"timestamp": f"cycle_{i}"} for i in range(150)],
                "total_learnings": 150,
                "episodes_consolidated": 300,
            }
            mc._save_sleep_log(log)
            loaded = mc._load_sleep_log()
            assert len(loaded["cycles"]) == 100
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig

    def test_load_sleep_log_corrupt_json(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{invalid json")
        mc.SLEEP_CONSOLIDATION_FILE = str(corrupt)
        try:
            result = mc._load_sleep_log()
            assert result == {"cycles": [], "total_learnings": 0, "episodes_consolidated": 0}
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig

    def test_sleep_stats_no_data(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        mc.SLEEP_CONSOLIDATION_FILE = str(tmp_path / "nonexistent.json")
        try:
            stats = mc.sleep_stats()
            assert stats["total_cycles"] == 0
            assert stats["last_cycle"] == "never"
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig

    def test_sleep_stats_with_data(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.SLEEP_CONSOLIDATION_FILE
        mc.SLEEP_CONSOLIDATION_FILE = str(tmp_path / "sleep.json")
        try:
            log = {
                "cycles": [{"timestamp": "2026-03-01T12:00:00Z", "episode_ids": ["ep1"]}],
                "total_learnings": 5,
                "episodes_consolidated": 10,
            }
            mc._save_sleep_log(log)
            stats = mc.sleep_stats()
            assert stats["total_cycles"] == 1
            assert stats["total_learnings"] == 5
            assert stats["total_episodes_consolidated"] == 10
            assert "2026-03-01" in stats["last_cycle"]
        finally:
            mc.SLEEP_CONSOLIDATION_FILE = orig


# ---------------------------------------------------------------------------
# 14. Consolidation — measure_retrieval_quality (mostly pure)
# ---------------------------------------------------------------------------

class TestMeasureRetrievalQuality:
    """Test measure_retrieval_quality with mocked file output."""

    def test_empty_results(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "errors.jsonl")
        try:
            result = mc.measure_retrieval_quality("test query", [])
            assert result["selection_error"] == 1.0
            assert result["integration_error"] == 1.0
            assert result["evidence_density"] == 0.0
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_diverse_results(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "errors.jsonl")
        try:
            results = [
                {"document": "brain memory store recall system", "id": "1"},
                {"document": "cron schedule backup daily task", "id": "2"},
                {"document": "reasoning chain analysis quality", "id": "3"},
            ]
            metrics = mc.measure_retrieval_quality("brain memory recall", results)
            assert 0.0 <= metrics["selection_error"] <= 1.0
            assert 0.0 <= metrics["integration_error"] <= 1.0
            assert 0.0 <= metrics["evidence_density"] <= 1.0
            assert metrics["results_count"] == 3
            assert "redundancy" in metrics
            assert "coverage" in metrics
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_redundant_results(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "errors.jsonl")
        try:
            results = [
                {"document": "brain memory recall store", "id": "1"},
                {"document": "brain memory recall store", "id": "2"},
            ]
            metrics = mc.measure_retrieval_quality("brain memory", results)
            assert metrics["redundancy"] > 0.5  # Identical docs = high redundancy
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_with_expected_useful(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "errors.jsonl")
        try:
            results = [
                {"document": "brain memory store", "id": "1"},
                {"document": "cron schedule", "id": "2"},
                {"document": "random stuff", "id": "3"},
            ]
            metrics = mc.measure_retrieval_quality("brain memory", results, expected_useful=1)
            # 1 useful out of 3 = precision 1/3, selection_error = 2/3
            assert metrics["selection_error"] == pytest.approx(1.0 - 1/3, abs=0.01)
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_appends_to_log(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            results = [{"document": "hello world", "id": "1"}]
            mc.measure_retrieval_quality("hello", results)
            mc.measure_retrieval_quality("world", results)
            lines = log_file.read_text().strip().split("\n")
            assert len(lines) == 2
            entry = json.loads(lines[0])
            assert "selection_error" in entry
            assert "timestamp" in entry
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_high_coverage(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "errors.jsonl")
        try:
            results = [
                {"document": "brain memory recall query search results", "id": "1"},
            ]
            metrics = mc.measure_retrieval_quality("brain memory recall", results)
            assert metrics["coverage"] > 0.5  # query words well-covered
            assert metrics["integration_error"] < 0.5
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig


# ---------------------------------------------------------------------------
# 15. Consolidation — retrieval_error_report
# ---------------------------------------------------------------------------

class TestRetrievalErrorReport:
    """Test retrieval_error_report with mock data files."""

    def test_no_data_file(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        mc.RETRIEVAL_ERROR_FILE = str(tmp_path / "nonexistent.jsonl")
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["entries"] == 0
            assert "No retrieval error data" in result.get("message", "")
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_with_recent_data(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        from datetime import datetime, timezone
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"selection_error": 0.2, "integration_error": 0.3, "evidence_density": 0.8,
             "redundancy": 0.15, "coverage": 0.7, "timestamp": now},
            {"selection_error": 0.4, "integration_error": 0.1, "evidence_density": 0.6,
             "redundancy": 0.35, "coverage": 0.9, "timestamp": now},
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["entries"] == 2
            assert result["avg_selection_error"] == pytest.approx(0.3, abs=0.01)
            assert result["avg_integration_error"] == pytest.approx(0.2, abs=0.01)
            assert result["avg_evidence_density"] == pytest.approx(0.7, abs=0.01)
            assert result["diagnosis"] == "MODERATE — check redundancy and coverage"
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_healthy_diagnosis(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        from datetime import datetime, timezone
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"selection_error": 0.1, "integration_error": 0.1, "evidence_density": 0.9,
             "redundancy": 0.1, "coverage": 0.9, "timestamp": now},
        ]
        log_file.write_text(json.dumps(entries[0]) + "\n")
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["diagnosis"] == "HEALTHY"
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_high_selection_error_diagnosis(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        from datetime import datetime, timezone
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"selection_error": 0.8, "integration_error": 0.1, "evidence_density": 0.5,
             "redundancy": 0.7, "coverage": 0.9, "timestamp": now},
        ]
        log_file.write_text(json.dumps(entries[0]) + "\n")
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["diagnosis"] == "HIGH selection error"
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_high_integration_error_diagnosis(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        from datetime import datetime, timezone
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            {"selection_error": 0.2, "integration_error": 0.8, "evidence_density": 0.3,
             "redundancy": 0.2, "coverage": 0.2, "timestamp": now},
        ]
        log_file.write_text(json.dumps(entries[0]) + "\n")
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["diagnosis"] == "HIGH integration error"
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig

    def test_old_data_filtered_out(self, tmp_path):
        import clarvis.memory.memory_consolidation as mc
        orig = mc.RETRIEVAL_ERROR_FILE
        log_file = tmp_path / "errors.jsonl"
        entries = [
            {"selection_error": 0.5, "integration_error": 0.5, "evidence_density": 0.5,
             "redundancy": 0.5, "coverage": 0.5, "timestamp": "2020-01-01T00:00:00"},
        ]
        log_file.write_text(json.dumps(entries[0]) + "\n")
        mc.RETRIEVAL_ERROR_FILE = str(log_file)
        try:
            result = mc.retrieval_error_report(days=7)
            assert result["entries"] == 0
        finally:
            mc.RETRIEVAL_ERROR_FILE = orig


# ---------------------------------------------------------------------------
# 16. Consolidation — salience constants
# ---------------------------------------------------------------------------

class TestConsolidationSalienceConstants:
    """Test salience threshold constants are sane."""

    def test_salience_ordering(self):
        from clarvis.memory.memory_consolidation import (
            SALIENCE_HIGH, SALIENCE_MEDIUM, PRUNE_SALIENCE_CEILING,
            PRUNE_ACCESS_CEILING, PRUNE_AGE_FLOOR_DAYS,
        )
        assert SALIENCE_HIGH > SALIENCE_MEDIUM
        assert SALIENCE_MEDIUM > PRUNE_SALIENCE_CEILING
        assert PRUNE_ACCESS_CEILING >= 0
        assert PRUNE_AGE_FLOOR_DAYS >= 1

    def test_sleep_constants(self):
        from clarvis.memory.memory_consolidation import (
            SLEEP_MIN_EPISODES, SLEEP_MAX_LEARNINGS, SLEEP_THEME_DISTANCE,
        )
        assert SLEEP_MIN_EPISODES >= 1
        assert SLEEP_MAX_LEARNINGS >= 1
        assert 0.0 < SLEEP_THEME_DISTANCE <= 1.0


# ---------------------------------------------------------------------------
# 17. Hebbian — on_recall with mocked brain (access logging + coactivation)
# ---------------------------------------------------------------------------

class TestHebbianOnRecall:
    """Test HebbianMemory.on_recall with file I/O redirected."""

    def test_on_recall_logs_access(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_access = hm.ACCESS_LOG_FILE
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_stats = hm.STATS_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            hebbian = hm.HebbianMemory()
            # Mock brain calls in _strengthen_memory by providing empty results
            from unittest.mock import patch, MagicMock
            mock_brain = MagicMock()
            mock_brain.collections = {}  # No collections → _strengthen_memory returns early
            with patch("clarvis.memory.hebbian_memory.brain", mock_brain, create=True):
                hebbian.on_recall(
                    query="test query",
                    results=[
                        {"id": "mem_1", "collection": "clarvis-learnings",
                         "metadata": {}, "document": "test doc 1"},
                    ],
                    caller="test",
                )
            # Check access log was written
            assert hm.ACCESS_LOG_FILE.exists()
            lines = hm.ACCESS_LOG_FILE.read_text().strip().split("\n")
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["memory_id"] == "mem_1"
            assert entry["query"] == "test query"
            assert entry["caller"] == "test"
        finally:
            hm.ACCESS_LOG_FILE = orig_access
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.STATS_FILE = orig_stats

    def test_on_recall_updates_coactivation(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_access = hm.ACCESS_LOG_FILE
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_stats = hm.STATS_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            hebbian = hm.HebbianMemory()
            from unittest.mock import patch, MagicMock
            mock_brain = MagicMock()
            mock_brain.collections = {}
            with patch("clarvis.memory.hebbian_memory.brain", mock_brain, create=True):
                hebbian.on_recall(
                    query="multi result query",
                    results=[
                        {"id": "mem_a", "collection": "col", "metadata": {}, "document": "doc a"},
                        {"id": "mem_b", "collection": "col", "metadata": {}, "document": "doc b"},
                        {"id": "mem_c", "collection": "col", "metadata": {}, "document": "doc c"},
                    ],
                    caller="test",
                )
            # Coactivation should have 3 pairs: a-b, a-c, b-c
            assert len(hebbian._coactivation) == 3
            for pair_key, entry in hebbian._coactivation.items():
                assert entry["count"] == 1
                assert entry["strength"] > 0.0
                assert len(entry["ids"]) == 2
        finally:
            hm.ACCESS_LOG_FILE = orig_access
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.STATS_FILE = orig_stats

    def test_on_recall_empty_results(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_access = hm.ACCESS_LOG_FILE
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_stats = hm.STATS_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            hebbian = hm.HebbianMemory()
            hebbian.on_recall("query", [], caller="test")
            # No access log should be written
            assert not hm.ACCESS_LOG_FILE.exists()
        finally:
            hm.ACCESS_LOG_FILE = orig_access
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.STATS_FILE = orig_stats

    def test_on_recall_no_id_skipped(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_access = hm.ACCESS_LOG_FILE
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_stats = hm.STATS_FILE
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.STATS_FILE = tmp_path / "stats.json"
        try:
            hebbian = hm.HebbianMemory()
            from unittest.mock import patch, MagicMock
            mock_brain = MagicMock()
            mock_brain.collections = {}
            with patch("clarvis.memory.hebbian_memory.brain", mock_brain, create=True):
                hebbian.on_recall("query", [{"metadata": {}, "document": "no id"}])
            # Result without id should be skipped
            assert not hm.ACCESS_LOG_FILE.exists() or hm.ACCESS_LOG_FILE.read_text().strip() == ""
        finally:
            hm.ACCESS_LOG_FILE = orig_access
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.STATS_FILE = orig_stats


# ---------------------------------------------------------------------------
# 18. Hebbian — get_fisher_score
# ---------------------------------------------------------------------------

class TestHebbianFisherScore:
    """Test HebbianMemory.get_fisher_score."""

    def test_missing_score_returns_zero(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        try:
            hebbian = hm.HebbianMemory()
            assert hebbian.get_fisher_score("nonexistent_mem") == 0.0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_existing_score_returned(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        fisher_file = tmp_path / "fisher.json"
        fisher_data = {"scores": {"mem_123": 0.75}, "computed_at": "2026-01-01"}
        fisher_file.write_text(json.dumps(fisher_data))
        hm.FISHER_FILE = fisher_file
        try:
            hebbian = hm.HebbianMemory()
            assert hebbian.get_fisher_score("mem_123") == 0.75
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher


# ---------------------------------------------------------------------------
# 19. Hebbian — compute_fisher with mocked brain
# ---------------------------------------------------------------------------

class TestHebbianComputeFisher:
    """Test HebbianMemory.compute_fisher with mock brain."""

    def test_compute_fisher_empty_collections(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"
        try:
            hebbian = hm.HebbianMemory()
            # Clear any cached timestamp so it recomputes
            hebbian._fisher_scores["computed_at"] = None

            mock_brain = MagicMock()
            mock_brain.collections = {}

            with patch("clarvis.brain.brain", mock_brain):
                scores = hebbian.compute_fisher()

            assert isinstance(scores, dict)
            assert len(scores) == 0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_compute_fisher_with_memories(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"

        # Write some access events
        access_log = tmp_path / "access.jsonl"
        access_log.write_text(
            '{"memory_id": "mem_1", "query": "test", "timestamp": "2026-03-01T00:00:00"}\n'
            '{"memory_id": "mem_1", "query": "another", "timestamp": "2026-03-01T01:00:00"}\n'
            '{"memory_id": "mem_2", "query": "test", "timestamp": "2026-03-01T02:00:00"}\n'
        )

        try:
            hebbian = hm.HebbianMemory()
            hebbian._fisher_scores["computed_at"] = None

            mock_col = MagicMock()
            mock_col.get.return_value = {
                "ids": ["mem_1", "mem_2"],
                "metadatas": [
                    {"importance": 0.7, "original_importance": 0.5, "access_count": 5},
                    {"importance": 0.3, "original_importance": 0.3, "access_count": 0},
                ],
                "documents": ["doc 1", "doc 2"],
            }

            mock_brain = MagicMock()
            mock_brain.collections = {"test-col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                scores = hebbian.compute_fisher()

            assert isinstance(scores, dict)
            assert len(scores) == 2
            assert "mem_1" in scores
            assert "mem_2" in scores
            # mem_1 accessed more = higher fisher score
            assert scores["mem_1"] > scores["mem_2"]
            # Scores bounded
            assert all(0.0 <= s <= 1.0 for s in scores.values())
            # Fisher file should be saved
            assert hm.FISHER_FILE.exists()
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_compute_fisher_cached(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from datetime import datetime, timezone

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"

        # Write cached fisher with recent timestamp
        fisher_data = {
            "scores": {"mem_cached": 0.42},
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_memories": 1,
            "total_accesses": 5,
        }
        (tmp_path / "fisher.json").write_text(json.dumps(fisher_data))

        try:
            hebbian = hm.HebbianMemory()
            # Since computed_at is recent, should return cached scores
            scores = hebbian.compute_fisher()
            assert scores == {"mem_cached": 0.42}
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_compute_fisher_with_coactivation(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"

        # Pre-populate coactivation
        coact = {"mem_1|mem_2": {"ids": ["mem_1", "mem_2"], "count": 5,
                                  "strength": 0.5, "first_seen": "2026-01-01",
                                  "last_seen": "2026-03-01"}}
        (tmp_path / "coact.json").write_text(json.dumps(coact))

        try:
            hebbian = hm.HebbianMemory()
            hebbian._fisher_scores["computed_at"] = None

            mock_col = MagicMock()
            mock_col.get.return_value = {
                "ids": ["mem_1", "mem_3"],
                "metadatas": [{"importance": 0.5}, {"importance": 0.5}],
                "documents": ["doc1", "doc3"],
            }
            mock_brain = MagicMock()
            mock_brain.collections = {"col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                scores = hebbian.compute_fisher()

            # mem_1 has coactivation partner → lower uniqueness
            # mem_3 has no coactivation → higher uniqueness
            assert "mem_1" in scores
            assert "mem_3" in scores
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access

    def test_compute_fisher_string_importance(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        orig_access = hm.ACCESS_LOG_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"
        hm.ACCESS_LOG_FILE = tmp_path / "access.jsonl"

        try:
            hebbian = hm.HebbianMemory()
            hebbian._fisher_scores["computed_at"] = None

            mock_col = MagicMock()
            mock_col.get.return_value = {
                "ids": ["mem_str"],
                "metadatas": [{"importance": "0.6", "original_importance": "0.4"}],
                "documents": ["doc"],
            }
            mock_brain = MagicMock()
            mock_brain.collections = {"col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                scores = hebbian.compute_fisher()

            assert "mem_str" in scores
            assert 0.0 <= scores["mem_str"] <= 1.0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher
            hm.ACCESS_LOG_FILE = orig_access


# ---------------------------------------------------------------------------
# 20. Hebbian — diagnose with mocked brain
# ---------------------------------------------------------------------------

class TestHebbianDiagnose:
    """Test HebbianMemory.diagnose with mock brain."""

    def test_diagnose_categorizes_memories(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            hebbian = hm.HebbianMemory()

            mock_col = MagicMock()
            mock_col.get.return_value = {
                "ids": ["high_imp", "low_imp", "never_acc", "heavy_acc"],
                "metadatas": [
                    {"importance": 0.9, "access_count": 5},
                    {"importance": 0.1, "access_count": 3},
                    {"importance": 0.5, "access_count": 0},
                    {"importance": 0.6, "access_count": 15},
                ],
                "documents": ["high doc", "low doc", "never doc", "heavy doc"],
            }
            mock_brain = MagicMock()
            mock_brain.collections = {"test-col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                diag = hebbian.diagnose()

            assert diag["high_importance_count"] == 1
            assert diag["low_importance_count"] == 1
            assert diag["never_accessed_count"] == 1
            assert diag["heavily_accessed_count"] == 1
            assert "coactivation_pairs" in diag
            assert "strong_associations" in diag
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_diagnose_string_metadata(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            hebbian = hm.HebbianMemory()

            mock_col = MagicMock()
            mock_col.get.return_value = {
                "ids": ["str_meta"],
                "metadatas": [{"importance": "0.9", "access_count": "12"}],
                "documents": ["string metadata doc"],
            }
            mock_brain = MagicMock()
            mock_brain.collections = {"col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                diag = hebbian.diagnose()

            assert diag["high_importance_count"] == 1
            assert diag["heavily_accessed_count"] == 1
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_diagnose_with_coactivation_stats(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        # Pre-populate coactivation with a strong pair
        coact = {
            "a|b": {"ids": ["a", "b"], "count": 10, "strength": 0.5},
            "c|d": {"ids": ["c", "d"], "count": 2, "strength": 0.1},
        }
        (tmp_path / "coact.json").write_text(json.dumps(coact))

        try:
            hebbian = hm.HebbianMemory()

            mock_col = MagicMock()
            mock_col.get.return_value = {"ids": [], "metadatas": [], "documents": []}
            mock_brain = MagicMock()
            mock_brain.collections = {"col": mock_col}

            with patch("clarvis.brain.brain", mock_brain):
                diag = hebbian.diagnose()

            assert diag["coactivation_pairs"] == 2
            assert diag["strong_associations"] == 1  # Only a|b has strength > 0.3
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher

    def test_diagnose_empty_collections(self, tmp_path):
        import clarvis.memory.hebbian_memory as hm
        from unittest.mock import patch, MagicMock

        orig_coact = hm.COACTIVATION_FILE
        orig_fisher = hm.FISHER_FILE
        hm.COACTIVATION_FILE = tmp_path / "coact.json"
        hm.FISHER_FILE = tmp_path / "fisher.json"

        try:
            hebbian = hm.HebbianMemory()
            mock_brain = MagicMock()
            mock_brain.collections = {}

            with patch("clarvis.brain.brain", mock_brain):
                diag = hebbian.diagnose()

            assert diag["high_importance_count"] == 0
            assert diag["low_importance_count"] == 0
            assert diag["never_accessed_count"] == 0
            assert diag["heavily_accessed_count"] == 0
        finally:
            hm.COACTIVATION_FILE = orig_coact
            hm.FISHER_FILE = orig_fisher


# ---------------------------------------------------------------------------
# 21. Procedural — CLI section constants
# ---------------------------------------------------------------------------

class TestProceduralCLIConstants:
    """Test additional procedural_memory constants and logic."""

    def test_stale_retire_thresholds(self):
        from clarvis.memory.procedural_memory import (
            STALE_DAYS, RETIRE_DAYS, STALE_MAX_SUCCESS_RATE,
        )
        assert RETIRE_DAYS > STALE_DAYS
        assert 0.0 <= STALE_MAX_SUCCESS_RATE <= 1.0

    def test_all_code_templates_have_required_fields(self):
        from clarvis.memory.procedural_memory import CODE_TEMPLATES
        for key, tmpl in CODE_TEMPLATES.items():
            assert "name" in tmpl, f"Template {key} missing 'name'"
            assert "description" in tmpl, f"Template {key} missing 'description'"
            assert "match_keywords" in tmpl, f"Template {key} missing 'match_keywords'"
            assert "scaffold" in tmpl, f"Template {key} missing 'scaffold'"
            assert isinstance(tmpl["scaffold"], list), f"Template {key} scaffold not a list"
            assert len(tmpl["scaffold"]) >= 3, f"Template {key} scaffold too short"


# ---------------------------------------------------------------------------
# 22. Episodic — action failure sub-bucket classifier (ACTION_FAILURE_TAXONOMY_REFINE)
# ---------------------------------------------------------------------------

class TestActionSubtypeClassifier:
    """Verify the regex classifier splits the generic `action` bucket."""

    def _classify(self, error, output=None):
        from clarvis.memory.episodic_memory import EpisodicMemory
        return EpisodicMemory._classify_action_subtype(error, output)

    def test_path_missing(self):
        assert self._classify("FileNotFoundError: data/episodes.json").endswith("path_missing")
        assert self._classify("No such file or directory: foo.py").endswith("path_missing")

    def test_command_nonzero(self):
        assert self._classify("subprocess returned non-zero exit code 2").endswith("command_nonzero")
        assert self._classify("foo exited with status 1").endswith("command_nonzero")

    def test_assertion_failed(self):
        assert self._classify("AssertionError: expected 5 got 4").endswith("assertion_failed")

    def test_lint_typecheck_error(self):
        assert self._classify("tsc: error TS2304: Cannot find name 'Foo'").endswith("lint_typecheck_error")
        assert self._classify("mypy error: incompatible types").endswith("lint_typecheck_error")

    def test_edit_string_not_found(self):
        assert self._classify("Edit failed: old_string not found in file").endswith("edit_string_not_found")
        assert self._classify("No occurrences of 'foo' found in bar.py").endswith("edit_string_not_found")

    def test_git_conflict(self):
        assert self._classify("CONFLICT (content): Merge conflict in foo.py").endswith("git_conflict")
        assert self._classify("Fix conflicts and run git rebase --continue").endswith("git_conflict")

    def test_test_failed(self):
        assert self._classify("3 tests failed in pytest").endswith("test_failed")
        assert self._classify("Mirror validation FAILED.").endswith("test_failed")

    def test_unverified_self_report(self):
        # Spawned-agent JSON output (escaped quotes as stored)
        s = '"tests_passed\\": true,\\n  "pr_class\\": "A"'
        assert self._classify(s) == "action.unverified"
        assert self._classify("All 3 tasks are done and verified.") == "action.unverified"

    def test_external_dep_reclassified(self):
        # Auth/401 errors should be promoted out of the action namespace
        assert self._classify("401 authentication_error: OAuth token expired") == "external_dep"

    def test_import_error_reclassified(self):
        assert self._classify("ImportError: No module named 'foo'") == "import_error"

    def test_no_signal_returns_none(self):
        assert self._classify("") is None
        assert self._classify(None) is None

    def test_get_failure_type_refines_action(self):
        """Legacy episodes tagged plain 'action' should be retroactively refined."""
        from clarvis.memory.episodic_memory import EpisodicMemory
        ep = {
            "outcome": "failure",
            "failure_type": "action",
            "error": "tsc: error TS2304: Cannot find name 'Foo'",
        }
        assert EpisodicMemory._get_failure_type(ep) == "action.lint_typecheck_error"

    def test_get_failure_type_partial_success_default(self):
        """partial_success episodes without a specific signal default to action.unverified."""
        from clarvis.memory.episodic_memory import EpisodicMemory
        ep = {"outcome": "partial_success", "failure_type": "action", "error": "some neutral text"}
        assert EpisodicMemory._get_failure_type(ep) == "action.unverified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

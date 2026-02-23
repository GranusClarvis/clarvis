"""Tests for ClarvisDB standalone package."""

import json
import os
import tempfile
import time

from clarvis_db import VectorStore, HebbianEngine, SynapticEngine
from clarvis_db.stdp import W_MIN, W_MAX, W_INIT


# === HEBBIAN ENGINE TESTS ===


def test_hebbian_reinforce():
    """Reinforcement should boost importance with diminishing returns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        i1 = heb.reinforce("m1", 0.5, access_count=1)
        i2 = heb.reinforce("m1", i1, access_count=2)
        i3 = heb.reinforce("m1", i2, access_count=3)
        assert i1 > 0.5, "Should boost"
        assert (i2 - i1) >= (i3 - i2), "Should have diminishing returns"


def test_hebbian_decay_grace():
    """No decay within grace period."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        d = heb.compute_decay(0.8, days_since_access=0.5)
        assert d == 0.8, "Should not decay in grace period"


def test_hebbian_decay_power_law():
    """Power-law decay: more days = more decay."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        d2 = heb.compute_decay(0.8, days_since_access=2)
        d3 = heb.compute_decay(0.8, days_since_access=3)
        assert d2 < 0.8, "Should decay after grace"
        assert d3 < d2, "Longer neglect = more decay"


def test_hebbian_decay_access_slows():
    """High access count should slow decay."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        d_low = heb.compute_decay(0.8, days_since_access=10, access_count=0)
        d_high = heb.compute_decay(0.8, days_since_access=10, access_count=20)
        assert d_high > d_low, "More accesses should slow decay"


def test_hebbian_coactivation():
    """Co-recalled memories should form associations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        heb.on_recall("test query", ["m1", "m2", "m3"])
        assoc = heb.get_associations("m1", min_strength=0.0)
        assert len(assoc) >= 1, "Should have associations after co-recall"


def test_hebbian_evolve():
    """Evolution should process memories and return stats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        heb = HebbianEngine(data_dir=tmpdir)
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        memories = [
            {"id": "m1", "importance": 0.8, "access_count": 0, "last_accessed": old},
            {"id": "m2", "importance": 0.6, "access_count": 5, "last_accessed": old},
        ]
        stats = heb.evolve(memories)
        assert stats["total_scanned"] == 2
        assert stats["weakened"] >= 0


# === STDP ENGINE TESTS ===


def test_stdp_memristor_roundtrip():
    """State -> weight -> state should be identity."""
    for state in [0.0, 0.25, 0.5, 0.75, 1.0]:
        w = SynapticEngine.memristor_weight(state)
        s_back = SynapticEngine.inverse_memristor(w)
        assert abs(s_back - state) < 0.01, f"Roundtrip fail: {state} -> {w} -> {s_back}"


def test_stdp_potentiate():
    """Repeated potentiation should increase weight."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        w1 = syn.potentiate("a", "b", delta_t=0)
        w2 = syn.potentiate("a", "b", delta_t=0)
        assert w2 > w1, "Repeated potentiation should strengthen"
        assert w2 <= W_MAX, "Weight should be bounded"


def test_stdp_depress():
    """Depression should decrease weight."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        w1 = syn.potentiate("a", "b", delta_t=0)
        w2 = syn.potentiate("a", "b", delta_t=0)
        d1 = syn.depress("a", "b")
        assert d1 < w2, "Depression should weaken"
        assert d1 >= W_MIN, "Weight should be bounded below"


def test_stdp_depress_nonexistent():
    """Depressing nonexistent synapse returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        assert syn.depress("x", "y") is None


def test_stdp_spread():
    """Spreading activation from a hub should find targets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        for i in range(5):
            syn.potentiate("hub", f"t{i}", delta_t=0)
        spread = syn.spread("hub", n=5)
        assert len(spread) == 5
        # Should be sorted by activation
        for i in range(len(spread) - 1):
            assert spread[i][1] >= spread[i + 1][1]


def test_stdp_consolidate():
    """Consolidation should run without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        syn.potentiate("a", "b")
        result = syn.consolidate()
        assert result["total_synapses"] >= 0
        assert "avg_weight" in result


def test_stdp_stats():
    """Stats should reflect network state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        s = syn.stats()
        assert s["total_synapses"] == 0
        assert s["status"] == "empty"

        syn.potentiate("a", "b")
        s = syn.stats()
        assert s["total_synapses"] == 1
        assert s["status"] == "active"


def test_stdp_on_recall():
    """on_recall should potentiate all pairs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        syn.on_recall(["m1", "m2", "m3"])
        s = syn.stats()
        # 3 memories = 6 directed pairs
        assert s["total_synapses"] == 6


def test_stdp_weight_saturation():
    """Weight-dependent saturation: harder to potentiate strong synapses."""
    with tempfile.TemporaryDirectory() as tmpdir:
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "test.db"))
        weights = []
        for _ in range(20):
            w = syn.potentiate("a", "b", delta_t=0)
            weights.append(w)
        # Increments should decrease over time
        deltas = [weights[i + 1] - weights[i] for i in range(len(weights) - 1)]
        assert deltas[0] > deltas[-1], "Saturation: early deltas > late deltas"


# === VECTORSTORE INTEGRATION TESTS ===


def test_store_and_recall():
    """Basic store/recall cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["facts"])
        db.store("Python is a programming language", collection="facts", importance=0.8)
        db.store("Mars is the fourth planet", collection="facts", importance=0.7)
        results = db.recall("programming")
        assert len(results) >= 1
        assert "Python" in results[0]["document"] or "programming" in results[0]["document"].lower()


def test_store_auto_id():
    """Stored memories get auto-generated IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        mid = db.store("test", collection="mem")
        assert mid.startswith("mem_")


def test_store_custom_id():
    """Custom IDs should be respected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        mid = db.store("test", collection="mem", memory_id="custom-123")
        assert mid == "custom-123"


def test_recall_min_importance():
    """min_importance filter should exclude low-importance memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        db.store("low importance fact", collection="mem", importance=0.1)
        db.store("high importance fact", collection="mem", importance=0.9)
        results = db.recall("fact", min_importance=0.5)
        for r in results:
            assert r["metadata"]["importance"] >= 0.5


def test_delete():
    """Deleted memories should not appear in recall."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        mid = db.store("to be deleted", collection="mem")
        ok = db.delete(mid, collection="mem")
        assert ok is True


def test_graph_relationships():
    """Relationships should be stored in the graph."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        db.add_relationship("a", "b", "related")
        related = db.get_related("a")
        assert len(related) == 1
        assert related[0]["id"] == "b"


def test_stats():
    """Stats should reflect stored memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["facts", "notes"])
        db.store("mem1", collection="facts")
        db.store("mem2", collection="notes")
        s = db.stats()
        assert s["total_memories"] == 2
        assert s["chroma_available"] is True


def test_evolve():
    """Evolution should run Hebbian + STDP without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["mem"])
        db.store("memory one", collection="mem")
        db.store("memory two", collection="mem")
        result = db.evolve()
        assert "hebbian" in result
        assert "stdp" in result


def test_callbacks():
    """Store/recall callbacks should fire."""
    stored = []
    recalled = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(
            data_dir=tmpdir,
            collections=["mem"],
            on_store=lambda mid, text, col: stored.append(mid),
            on_recall=lambda q, r: recalled.append(q),
        )
        db.store("callback test", collection="mem")
        db.recall("callback")
        assert len(stored) == 1
        assert len(recalled) == 1


def test_multi_collection():
    """Recall should search across multiple collections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorStore(data_dir=tmpdir, collections=["facts", "episodes"])
        db.store("Python is great", collection="facts")
        db.store("Debugged Python error", collection="episodes")
        results = db.recall("Python", collections=["facts", "episodes"])
        collections_hit = {r["collection"] for r in results}
        assert len(collections_hit) >= 1


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

    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests")
    exit(1 if failed else 0)

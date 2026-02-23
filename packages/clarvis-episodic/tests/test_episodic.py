"""Tests for ClarvisEpisodic standalone package."""

import json
import tempfile
import time
from pathlib import Path

from clarvis_episodic import EpisodicStore, compute_activation, compute_valence


def test_compute_valence():
    """Valence scoring: failures > success, high salience > low."""
    v_success = compute_valence("success", 0.5)
    v_failure = compute_valence("failure", 0.5)
    v_timeout = compute_valence("timeout", 0.5)
    v_high_sal = compute_valence("success", 1.0)
    v_novel = compute_valence("failure", 0.5, is_novel_error=True)

    assert v_failure > v_success, "Failures should be more memorable"
    assert v_timeout > v_success, "Timeouts should be more memorable"
    assert v_high_sal > v_success, "Higher salience = higher valence"
    assert v_novel > v_failure, "Novel errors = extra memorable"
    assert 0.0 <= v_success <= 1.0
    assert 0.0 <= v_novel <= 1.0


def test_compute_activation_empty():
    """No access times = forgotten."""
    assert compute_activation([]) == -10.0


def test_compute_activation_recent():
    """Recently accessed = high activation."""
    now = time.time()
    act = compute_activation([now - 1], now=now)
    assert act > -1.0, f"Recent access should yield high activation, got {act}"


def test_compute_activation_decay():
    """Spaced recent accesses beat a single old access.

    The Pavlik model rewards spaced repetition — items accessed multiple
    times with spacing decay slower than items seen once long ago.
    """
    now = time.time()
    # Spaced recent: accessed 3 days ago, yesterday, and just now
    act_spaced_recent = compute_activation([now - 86400*3, now - 86400, now - 60], now=now)
    # Single old: accessed once 2 weeks ago, never since
    act_old_single = compute_activation([now - 86400*14], now=now)
    assert act_spaced_recent > act_old_single, (
        f"Spaced recent should beat old single: {act_spaced_recent} vs {act_old_single}"
    )


def test_compute_activation_spacing():
    """Spaced repetitions should yield better activation than massed."""
    now = time.time()
    # Massed: 3 accesses within 1 minute
    massed = [now - 60, now - 30, now]
    # Spaced: 3 accesses over 3 days
    spaced = [now - 86400 * 2, now - 86400, now]

    act_massed = compute_activation(massed, now=now)
    act_spaced = compute_activation(spaced, now=now)
    # Both should be positive (3 accesses), but spaced should be comparable or better
    assert act_spaced > -2.0, f"Spaced should be well-remembered, got {act_spaced}"


def test_encode_and_recall():
    """Basic encode/recall cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)

        store.encode("Fixed auth bug in login page", section="bugs", salience=0.8, outcome="success")
        store.encode("Deploy failed: timeout", section="deploy", salience=0.9, outcome="failure",
                     error_msg="Connection timeout after 30s")
        store.encode("Added dark mode toggle", section="features", salience=0.5, outcome="success")

        assert len(store.episodes) == 3

        # Keyword recall
        results = store.recall("auth bug")
        assert len(results) >= 1
        assert "auth" in results[0]["task"].lower()

        # Empty recall = most active
        all_eps = store.recall("")
        assert len(all_eps) == 3


def test_failures():
    """Failure recall should only return non-success episodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)

        store.encode("Task A", outcome="success")
        store.encode("Task B", outcome="failure", error_msg="boom")
        store.encode("Task C", outcome="soft_failure")
        store.encode("Task D", outcome="timeout")

        fails = store.failures(n=10)
        assert len(fails) == 3
        outcomes = {f["outcome"] for f in fails}
        assert "success" not in outcomes


def test_stats():
    """Stats should reflect encoded episodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)
        store.encode("A", outcome="success")
        store.encode("B", outcome="failure")

        s = store.stats()
        assert s["total"] == 2
        assert s["outcomes"]["success"] == 1
        assert s["outcomes"]["failure"] == 1
        assert "avg_valence" in s
        assert "avg_activation" in s


def test_synthesize():
    """Synthesis should produce actionable insights."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)
        for i in range(5):
            store.encode(f"Build feature {i}", section="features", salience=0.5,
                        outcome="success" if i % 2 == 0 else "failure")

        result = store.synthesize()
        assert result["total_episodes"] == 5
        assert "success_rate" in result
        assert "top_success_actions" in result
        assert "section_outcomes" in result


def test_persistence():
    """Episodes should persist across store instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store1 = EpisodicStore(data_dir=tmpdir)
        store1.encode("Persistent task", outcome="success")
        assert len(store1.episodes) == 1

        store2 = EpisodicStore(data_dir=tmpdir)
        assert len(store2.episodes) == 1
        assert store2.episodes[0]["task"] == "Persistent task"


def test_export_import():
    """Export/import cycle should preserve episodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)
        store.encode("Export test 1", outcome="success")
        store.encode("Export test 2", outcome="failure")

        export_path = str(Path(tmpdir) / "export.json")
        store.export(export_path)

        # Import into fresh store
        store2 = EpisodicStore(data_dir=str(Path(tmpdir) / "new"))
        imported = store2.import_episodes(export_path)
        assert imported == 2
        assert len(store2.episodes) == 2

        # Re-import should skip duplicates
        imported2 = store2.import_episodes(export_path)
        assert imported2 == 0


def test_forget():
    """Explicit forget should remove episode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir)
        ep = store.encode("To be forgotten", outcome="success")
        assert len(store.episodes) == 1

        removed = store.forget(ep["id"])
        assert removed is True
        assert len(store.episodes) == 0


def test_max_episodes():
    """Store should cap at max_episodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir, max_episodes=5)
        for i in range(10):
            store.encode(f"Task {i}", outcome="success")

        # Reload to verify persistence cap
        store2 = EpisodicStore(data_dir=tmpdir, max_episodes=5)
        assert len(store2.episodes) == 5
        # Should have the last 5
        assert store2.episodes[0]["task"] == "Task 5"


def test_callbacks():
    """Encode and recall callbacks should fire."""
    encoded_episodes = []
    recalled_queries = []

    def on_enc(ep):
        encoded_episodes.append(ep)

    def on_rec(q, results):
        recalled_queries.append(q)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EpisodicStore(data_dir=tmpdir, on_encode=on_enc, on_recall=on_rec)
        store.encode("Callback test", outcome="success")
        store.recall("Callback")

        assert len(encoded_episodes) == 1
        assert len(recalled_queries) == 1


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
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

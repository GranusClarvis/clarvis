"""Tests for brain failure counters (BRAIN_OBSERVABILITY_COUNTERS)."""

import pytest


@pytest.fixture(scope="module")
def brain():
    """Get a brain instance for testing."""
    try:
        from clarvis.brain import brain as b
        return b
    except Exception:
        pytest.skip("Brain not available")


def test_failure_counters_present_in_stats(brain):
    """stats() must include failure_counters with >= 3 keys."""
    s = brain.stats()
    assert "failure_counters" in s
    fc = s["failure_counters"]
    assert isinstance(fc, dict)
    assert len(fc) >= 3


def test_failure_counter_keys(brain):
    """Verify expected counter names exist."""
    fc = brain.stats()["failure_counters"]
    expected = {"dedup_failures", "store_link_failures", "temporal_fallbacks",
                "search_query_failures", "expansion_failures", "hook_timeouts"}
    assert expected.issubset(set(fc.keys()))


def test_dedup_failure_counter_increments(brain):
    """Injecting a broken collection should increment dedup_failures."""
    before = brain._failure_counters["dedup_failures"]
    # Inject a broken collection temporarily to trigger dedup failure
    real_col = brain.collections.get("clarvis-memories")
    if real_col is None:
        pytest.skip("clarvis-memories collection not available")

    class BrokenQuery:
        """Proxy that raises on query() to simulate dedup failure."""
        def __getattr__(self, name):
            if name == "query":
                def _raise(*a, **kw):
                    raise RuntimeError("injected failure")
                return _raise
            return getattr(real_col, name)

    brain.collections["clarvis-memories"] = BrokenQuery()
    try:
        # _find_near_duplicate should catch the error and increment counter
        result = brain._find_near_duplicate("test probe text", "clarvis-memories")
        assert result is None  # should return None on failure
    finally:
        brain.collections["clarvis-memories"] = real_col

    after = brain._failure_counters["dedup_failures"]
    assert after > before, f"dedup_failures should have incremented: {before} -> {after}"


def test_hook_timeout_drain():
    """_drain_hook_timeouts returns accumulated count and resets."""
    from clarvis.brain.search import _hook_timeout_count, _drain_hook_timeouts
    _hook_timeout_count[0] = 5
    assert _drain_hook_timeouts() == 5
    assert _hook_timeout_count[0] == 0


def test_counters_are_all_integers(brain):
    """All counter values should be non-negative integers."""
    fc = brain.stats()["failure_counters"]
    for key, val in fc.items():
        assert isinstance(val, int), f"{key} should be int, got {type(val)}"
        assert val >= 0, f"{key} should be non-negative, got {val}"

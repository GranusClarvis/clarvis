"""
Tests for clarvis.heartbeat.hooks — lifecycle hook registry.

Verifies:
  1. Hooks execute in priority order (lower priority number = earlier)
  2. Phase isolation (preflight hooks don't run during postflight and vice versa)
  3. Fault tolerance (one hook failure doesn't block subsequent hooks)
  4. Duplicate name replacement
  5. The 3 migrated subsystems register in correct order
  6. Context is passed through to each hook
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.heartbeat.hooks import HookRegistry, HookPhase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reg():
    """Fresh registry for each test."""
    return HookRegistry()


# ---------------------------------------------------------------------------
# 1. Priority ordering
# ---------------------------------------------------------------------------

class TestPriorityOrder:
    def test_hooks_run_in_priority_order(self, reg):
        """Lower priority number executes first."""
        execution_order = []

        reg.register(HookPhase.POSTFLIGHT, "third", lambda ctx: execution_order.append("third"), priority=90)
        reg.register(HookPhase.POSTFLIGHT, "first", lambda ctx: execution_order.append("first"), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "second", lambda ctx: execution_order.append("second"), priority=50)

        reg.run(HookPhase.POSTFLIGHT, {})
        assert execution_order == ["first", "second", "third"]

    def test_hooks_for_returns_priority_sorted(self, reg):
        """hooks_for() returns (name, priority) tuples sorted by priority."""
        reg.register(HookPhase.POSTFLIGHT, "z_late", lambda ctx: None, priority=99)
        reg.register(HookPhase.POSTFLIGHT, "a_early", lambda ctx: None, priority=1)
        reg.register(HookPhase.POSTFLIGHT, "m_mid", lambda ctx: None, priority=50)

        order = reg.hooks_for(HookPhase.POSTFLIGHT)
        assert order == [("a_early", 1), ("m_mid", 50), ("z_late", 99)]

    def test_hook_names_returns_ordered_names(self, reg):
        """hook_names() is a convenience returning just names in order."""
        reg.register(HookPhase.POSTFLIGHT, "beta", lambda ctx: None, priority=20)
        reg.register(HookPhase.POSTFLIGHT, "alpha", lambda ctx: None, priority=10)

        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["alpha", "beta"]

    def test_same_priority_sorts_alphabetically(self, reg):
        """Hooks with equal priority sort by name (stable, deterministic)."""
        reg.register(HookPhase.POSTFLIGHT, "zebra", lambda ctx: None, priority=50)
        reg.register(HookPhase.POSTFLIGHT, "apple", lambda ctx: None, priority=50)

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["apple", "zebra"]

    def test_many_hooks_maintain_order(self, reg):
        """Stress test: 20 hooks maintain strict priority order."""
        execution_order = []
        for i in range(20):
            p = 20 - i  # register in reverse priority order
            name = f"hook_{p:02d}"
            reg.register(HookPhase.POSTFLIGHT, name,
                         lambda ctx, n=name: execution_order.append(n), priority=p)

        reg.run(HookPhase.POSTFLIGHT, {})
        expected = [f"hook_{i:02d}" for i in range(1, 21)]
        assert execution_order == expected


# ---------------------------------------------------------------------------
# 2. Phase isolation
# ---------------------------------------------------------------------------

class TestPhaseIsolation:
    def test_preflight_hooks_dont_run_on_postflight(self, reg):
        """Preflight hooks are not triggered by postflight run."""
        pre_ran = []
        post_ran = []

        reg.register(HookPhase.PREFLIGHT, "pre_hook", lambda ctx: pre_ran.append(1), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post_hook", lambda ctx: post_ran.append(1), priority=10)

        reg.run(HookPhase.POSTFLIGHT, {})

        assert pre_ran == []
        assert post_ran == [1]

    def test_postflight_hooks_dont_run_on_preflight(self, reg):
        """Postflight hooks are not triggered by preflight run."""
        pre_ran = []
        post_ran = []

        reg.register(HookPhase.PREFLIGHT, "pre_hook", lambda ctx: pre_ran.append(1), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post_hook", lambda ctx: post_ran.append(1), priority=10)

        reg.run(HookPhase.PREFLIGHT, {})

        assert pre_ran == [1]
        assert post_ran == []

    def test_hooks_for_only_returns_matching_phase(self, reg):
        reg.register(HookPhase.PREFLIGHT, "pre1", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post1", lambda ctx: None, priority=10)

        assert reg.hook_names(HookPhase.PREFLIGHT) == ["pre1"]
        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["post1"]


# ---------------------------------------------------------------------------
# 3. Fault tolerance
# ---------------------------------------------------------------------------

class TestFaultTolerance:
    def test_failing_hook_doesnt_block_others(self, reg):
        """A hook that raises an exception should not prevent subsequent hooks from running."""
        execution_order = []

        reg.register(HookPhase.POSTFLIGHT, "good_before",
                     lambda ctx: execution_order.append("good_before"), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "bad",
                     lambda ctx: 1/0, priority=20)  # ZeroDivisionError
        reg.register(HookPhase.POSTFLIGHT, "good_after",
                     lambda ctx: execution_order.append("good_after"), priority=30)

        results = reg.run(HookPhase.POSTFLIGHT, {})

        # Both good hooks ran
        assert execution_order == ["good_before", "good_after"]

        # Bad hook has error in results
        assert "error" in results["bad"]
        assert "division by zero" in results["bad"]["error"]

        # Good hooks have results
        assert "result" in results["good_before"]
        assert "result" in results["good_after"]

    def test_all_hooks_get_timing(self, reg):
        """Even failed hooks report elapsed time."""
        reg.register(HookPhase.POSTFLIGHT, "ok", lambda ctx: "fine", priority=10)
        reg.register(HookPhase.POSTFLIGHT, "fail", lambda ctx: [][0], priority=20)

        results = reg.run(HookPhase.POSTFLIGHT, {})

        assert "elapsed_s" in results["ok"]
        assert "elapsed_s" in results["fail"]
        assert results["ok"]["elapsed_s"] >= 0
        assert results["fail"]["elapsed_s"] >= 0

    def test_run_returns_results_dict(self, reg):
        """run() returns hook name → result mapping."""
        reg.register(HookPhase.POSTFLIGHT, "adder",
                     lambda ctx: ctx.get("x", 0) + 1, priority=10)

        results = reg.run(HookPhase.POSTFLIGHT, {"x": 41})
        assert results["adder"]["result"] == 42


# ---------------------------------------------------------------------------
# 4. Duplicate name replacement
# ---------------------------------------------------------------------------

class TestDuplicateNames:
    def test_re_registration_replaces_hook(self, reg):
        """Registering the same name twice replaces the first hook."""
        reg.register(HookPhase.POSTFLIGHT, "my_hook", lambda ctx: "v1", priority=10)
        reg.register(HookPhase.POSTFLIGHT, "my_hook", lambda ctx: "v2", priority=10)

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names.count("my_hook") == 1

        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["my_hook"]["result"] == "v2"

    def test_re_registration_can_change_priority(self, reg):
        """Re-registering with a different priority moves the hook."""
        reg.register(HookPhase.POSTFLIGHT, "mover", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "anchor", lambda ctx: None, priority=50)
        reg.register(HookPhase.POSTFLIGHT, "mover", lambda ctx: None, priority=90)

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["anchor", "mover"]  # mover now after anchor


# ---------------------------------------------------------------------------
# 5. Migrated subsystems register in correct order
# ---------------------------------------------------------------------------

class TestMigratedSubsystemOrder:
    def test_procedural_before_consolidation_before_metrics(self):
        """The 3 migrated subsystems must run in this order:
           procedural (30-39) → consolidation (50-59) → metrics (60-69)"""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase
        from clarvis.heartbeat.adapters import register_all

        reg = HookRegistry()
        # Monkey-patch the global registry temporarily
        import clarvis.heartbeat.adapters as adapters_mod
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_all()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)

        # Verify all 6 hooks are registered
        assert "procedural_record" in names
        assert "procedural_injection_track" in names
        assert "periodic_synthesis" in names
        assert "perf_benchmark" in names
        assert "latency_budget" in names
        assert "structural_health" in names

        # Verify ordering: procedural < consolidation < metrics
        idx_proc = names.index("procedural_record")
        idx_inject = names.index("procedural_injection_track")
        idx_synth = names.index("periodic_synthesis")
        idx_perf = names.index("perf_benchmark")
        idx_lat = names.index("latency_budget")
        idx_struct = names.index("structural_health")

        # Procedural hooks come first
        assert idx_proc < idx_synth, "procedural_record must run before periodic_synthesis"
        assert idx_inject < idx_synth, "procedural_injection_track must run before periodic_synthesis"

        # Consolidation before metrics
        assert idx_synth < idx_perf, "periodic_synthesis must run before perf_benchmark"
        assert idx_synth < idx_lat, "periodic_synthesis must run before latency_budget"
        assert idx_synth < idx_struct, "periodic_synthesis must run before structural_health"

        # Within metrics, order is: perf < latency < structural
        assert idx_perf < idx_lat, "perf_benchmark must run before latency_budget"
        assert idx_lat < idx_struct, "latency_budget must run before structural_health"

    def test_priority_bands_are_correct(self):
        """Verify actual priority numbers fall in documented bands."""
        from clarvis.heartbeat.hooks import HookRegistry, HookPhase
        from clarvis.heartbeat.adapters import register_all
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_all()
        finally:
            adapters_mod.registry = original

        hooks = reg.hooks_for(HookPhase.POSTFLIGHT)
        priorities = {name: priority for name, priority in hooks}

        # Procedural: 30-39
        assert 30 <= priorities["procedural_record"] <= 39
        assert 30 <= priorities["procedural_injection_track"] <= 39

        # Consolidation: 50-59
        assert 50 <= priorities["periodic_synthesis"] <= 59

        # Metrics: 60-69
        assert 60 <= priorities["perf_benchmark"] <= 69
        assert 60 <= priorities["latency_budget"] <= 69
        assert 60 <= priorities["structural_health"] <= 69


# ---------------------------------------------------------------------------
# 6. Context passthrough
# ---------------------------------------------------------------------------

class TestContextPassthrough:
    def test_context_dict_passed_to_each_hook(self, reg):
        """Each hook receives the same context dict."""
        received = []

        def capture_ctx(ctx):
            received.append(ctx.get("task"))
            return ctx.get("task")

        reg.register(HookPhase.POSTFLIGHT, "h1", capture_ctx, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "h2", capture_ctx, priority=20)

        reg.run(HookPhase.POSTFLIGHT, {"task": "test-task"})

        assert received == ["test-task", "test-task"]

    def test_empty_context(self, reg):
        """Hooks handle empty context gracefully."""
        reg.register(HookPhase.POSTFLIGHT, "safe",
                     lambda ctx: ctx.get("missing", "default"), priority=10)

        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["safe"]["result"] == "default"


# ---------------------------------------------------------------------------
# 7. clear() and unregister()
# ---------------------------------------------------------------------------

class TestManagement:
    def test_clear_all(self, reg):
        reg.register(HookPhase.PREFLIGHT, "pre", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post", lambda ctx: None, priority=10)

        reg.clear()

        assert reg.hook_names(HookPhase.PREFLIGHT) == []
        assert reg.hook_names(HookPhase.POSTFLIGHT) == []

    def test_clear_single_phase(self, reg):
        reg.register(HookPhase.PREFLIGHT, "pre", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post", lambda ctx: None, priority=10)

        reg.clear(HookPhase.PREFLIGHT)

        assert reg.hook_names(HookPhase.PREFLIGHT) == []
        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["post"]

    def test_unregister(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "a", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "b", lambda ctx: None, priority=20)

        reg.unregister(HookPhase.POSTFLIGHT, "a")

        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["b"]

    def test_unregister_nonexistent_is_safe(self, reg):
        """Unregistering a name that doesn't exist should not raise."""
        reg.unregister(HookPhase.POSTFLIGHT, "ghost")  # no error

    def test_invalid_phase_raises(self, reg):
        with pytest.raises(ValueError, match="Unknown phase"):
            reg.register("invalid_phase", "hook", lambda ctx: None)

    def test_repr(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "a", lambda ctx: None, priority=10)
        r = repr(reg)
        assert "HookRegistry" in r
        assert "'postflight': 1" in r

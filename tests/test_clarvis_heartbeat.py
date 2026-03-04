"""Tests for clarvis.heartbeat — hooks and adapters.

HookRegistry is tested in depth (pure Python, no DB).
Adapters are tested for registration correctness.
"""

import os
import sys
import time

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
# 1. HookPhase constants
# ---------------------------------------------------------------------------

class TestHookPhase:
    def test_preflight_constant(self):
        assert HookPhase.PREFLIGHT == "preflight"

    def test_postflight_constant(self):
        assert HookPhase.POSTFLIGHT == "postflight"

    def test_all_contains_both(self):
        assert HookPhase.PREFLIGHT in HookPhase.ALL
        assert HookPhase.POSTFLIGHT in HookPhase.ALL
        assert len(HookPhase.ALL) == 2


# ---------------------------------------------------------------------------
# 2. HookRegistry — register, run, hooks_for
# ---------------------------------------------------------------------------

class TestRegistryBasics:
    def test_empty_registry(self, reg):
        assert reg.hook_names(HookPhase.PREFLIGHT) == []
        assert reg.hook_names(HookPhase.POSTFLIGHT) == []

    def test_register_single_hook(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "test_hook", lambda ctx: "ok", priority=50)
        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["test_hook"]

    def test_run_returns_result(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "adder", lambda ctx: ctx.get("x", 0) + 1, priority=10)
        results = reg.run(HookPhase.POSTFLIGHT, {"x": 41})
        assert results["adder"]["result"] == 42
        assert "elapsed_s" in results["adder"]

    def test_run_empty_phase(self, reg):
        results = reg.run(HookPhase.PREFLIGHT, {})
        assert results == {}

    def test_hooks_for_returns_tuples(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "h1", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "h2", lambda ctx: None, priority=20)
        tuples = reg.hooks_for(HookPhase.POSTFLIGHT)
        assert tuples == [("h1", 10), ("h2", 20)]


class TestRegistryPriority:
    def test_lower_priority_runs_first(self, reg):
        order = []
        reg.register(HookPhase.POSTFLIGHT, "last", lambda ctx: order.append("last"), priority=90)
        reg.register(HookPhase.POSTFLIGHT, "first", lambda ctx: order.append("first"), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "mid", lambda ctx: order.append("mid"), priority=50)

        reg.run(HookPhase.POSTFLIGHT, {})
        assert order == ["first", "mid", "last"]

    def test_same_priority_alphabetical(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "zebra", lambda ctx: None, priority=50)
        reg.register(HookPhase.POSTFLIGHT, "alpha", lambda ctx: None, priority=50)
        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["alpha", "zebra"]


class TestRegistryFaultTolerance:
    def test_exception_does_not_block(self, reg):
        order = []
        reg.register(HookPhase.POSTFLIGHT, "good1", lambda ctx: order.append("g1"), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "bad", lambda ctx: 1/0, priority=20)
        reg.register(HookPhase.POSTFLIGHT, "good2", lambda ctx: order.append("g2"), priority=30)

        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert order == ["g1", "g2"]
        assert "error" in results["bad"]

    def test_timing_reported_for_failures(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "fail", lambda ctx: [][0], priority=10)
        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["fail"]["elapsed_s"] >= 0


class TestRegistryPhaseIsolation:
    def test_preflight_isolated_from_postflight(self, reg):
        pre = []
        post = []
        reg.register(HookPhase.PREFLIGHT, "pre", lambda ctx: pre.append(1), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post", lambda ctx: post.append(1), priority=10)

        reg.run(HookPhase.POSTFLIGHT, {})
        assert pre == []
        assert post == [1]

    def test_postflight_isolated_from_preflight(self, reg):
        pre = []
        post = []
        reg.register(HookPhase.PREFLIGHT, "pre", lambda ctx: pre.append(1), priority=10)
        reg.register(HookPhase.POSTFLIGHT, "post", lambda ctx: post.append(1), priority=10)

        reg.run(HookPhase.PREFLIGHT, {})
        assert pre == [1]
        assert post == []


class TestRegistryManagement:
    def test_clear_all(self, reg):
        reg.register(HookPhase.PREFLIGHT, "a", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "b", lambda ctx: None, priority=10)
        reg.clear()
        assert reg.hook_names(HookPhase.PREFLIGHT) == []
        assert reg.hook_names(HookPhase.POSTFLIGHT) == []

    def test_clear_single_phase(self, reg):
        reg.register(HookPhase.PREFLIGHT, "a", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "b", lambda ctx: None, priority=10)
        reg.clear(HookPhase.PREFLIGHT)
        assert reg.hook_names(HookPhase.PREFLIGHT) == []
        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["b"]

    def test_unregister(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "a", lambda ctx: None, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "b", lambda ctx: None, priority=20)
        reg.unregister(HookPhase.POSTFLIGHT, "a")
        assert reg.hook_names(HookPhase.POSTFLIGHT) == ["b"]

    def test_unregister_nonexistent_safe(self, reg):
        reg.unregister(HookPhase.POSTFLIGHT, "ghost")  # no error

    def test_duplicate_replaces(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "hook", lambda ctx: "v1", priority=10)
        reg.register(HookPhase.POSTFLIGHT, "hook", lambda ctx: "v2", priority=10)
        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names.count("hook") == 1
        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["hook"]["result"] == "v2"

    def test_invalid_phase_raises(self, reg):
        with pytest.raises(ValueError, match="Unknown phase"):
            reg.register("bogus", "hook", lambda ctx: None)

    def test_repr(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "a", lambda ctx: None, priority=10)
        r = repr(reg)
        assert "HookRegistry" in r


class TestRegistryContext:
    def test_context_passed_to_hooks(self, reg):
        received = []
        reg.register(HookPhase.POSTFLIGHT, "cap",
                     lambda ctx: received.append(ctx.get("key")), priority=10)
        reg.run(HookPhase.POSTFLIGHT, {"key": "value"})
        assert received == ["value"]

    def test_empty_context(self, reg):
        reg.register(HookPhase.POSTFLIGHT, "safe",
                     lambda ctx: ctx.get("missing", "default"), priority=10)
        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["safe"]["result"] == "default"


# ---------------------------------------------------------------------------
# 3. Adapters — registration correctness
# ---------------------------------------------------------------------------

class TestAdaptersRegistration:
    def test_register_all_adds_expected_hooks(self):
        from clarvis.heartbeat.adapters import register_all
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_all()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert "procedural_record" in names
        assert "procedural_injection_track" in names
        assert "periodic_synthesis" in names
        assert "perf_benchmark" in names
        assert "latency_budget" in names
        assert "structural_health" in names
        assert "meta_learning" in names
        assert len(names) == 7

    def test_register_procedural_only(self):
        from clarvis.heartbeat.adapters import register_procedural
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_procedural()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert "procedural_record" in names
        assert "procedural_injection_track" in names
        assert len(names) == 2

    def test_register_consolidation_only(self):
        from clarvis.heartbeat.adapters import register_consolidation
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_consolidation()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["periodic_synthesis"]

    def test_register_metrics_only(self):
        from clarvis.heartbeat.adapters import register_metrics
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_metrics()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert "perf_benchmark" in names
        assert "latency_budget" in names
        assert "structural_health" in names

    def test_priority_bands(self):
        """Verify hooks are registered in correct priority bands."""
        from clarvis.heartbeat.adapters import register_all
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_all()
        finally:
            adapters_mod.registry = original

        priorities = {n: p for n, p in reg.hooks_for(HookPhase.POSTFLIGHT)}

        # Procedural: 30-39
        assert 30 <= priorities["procedural_record"] <= 39
        assert 30 <= priorities["procedural_injection_track"] <= 39

        # Consolidation: 50-59
        assert 50 <= priorities["periodic_synthesis"] <= 59

        # Metrics: 60-69
        assert 60 <= priorities["perf_benchmark"] <= 69
        assert 60 <= priorities["latency_budget"] <= 69
        assert 60 <= priorities["structural_health"] <= 69

    def test_execution_order(self):
        """Procedural → consolidation → metrics ordering."""
        from clarvis.heartbeat.adapters import register_all
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_all()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        idx_proc = names.index("procedural_record")
        idx_synth = names.index("periodic_synthesis")
        idx_perf = names.index("perf_benchmark")

        assert idx_proc < idx_synth < idx_perf


# ---------------------------------------------------------------------------
# 4. Adapter hook functions — unit test with mock context
# ---------------------------------------------------------------------------

class TestAdapterHookFunctions:
    def test_procedural_record_skip_on_failure_no_proc_id(self):
        """Without proc_id and non-zero exit code, should skip."""
        from clarvis.heartbeat.adapters import _procedural_record
        result = _procedural_record({"exit_code": 1, "task": "test"})
        assert result["action"] == "skip"

    def test_procedural_record_records_failure(self):
        """With proc_id and non-zero exit code, should record failure."""
        try:
            from clarvis.heartbeat.adapters import _procedural_record
            result = _procedural_record({
                "exit_code": 1,
                "procedure_id": "proc_test_xyz",
                "task": "test task",
            })
            assert result["action"] == "record_failure"
            assert result["proc_id"] == "proc_test_xyz"
        except ImportError:
            pytest.skip("procedural_memory not importable")

    def test_procedural_injection_track_skip(self):
        """Without procedure_injected, should skip."""
        from clarvis.heartbeat.adapters import _procedural_injection_track
        result = _procedural_injection_track({})
        assert result["action"] == "skip"

    def test_procedural_injection_track_records(self, tmp_path):
        """With procedure_injected, should log to file."""
        from clarvis.heartbeat import adapters as adp
        orig_scripts = adp._SCRIPTS_DIR
        adp._SCRIPTS_DIR = str(tmp_path)
        try:
            result = adp._procedural_injection_track({
                "procedure_injected": True,
                "task": "test task",
                "procedure_id": "proc_test",
                "procedures_for_injection": ["proc_test"],
                "task_status": "success",
                "exit_code": 0,
                "task_duration": 10,
            })
            assert result["action"] == "tracked"
        finally:
            adp._SCRIPTS_DIR = orig_scripts

    def test_procedural_record_success_with_proc_id(self):
        """With proc_id and exit_code=0, should record success."""
        try:
            from clarvis.heartbeat.adapters import _procedural_record
            result = _procedural_record({
                "exit_code": 0,
                "procedure_id": "proc_test_success",
                "task": "test task",
                "output_text": "",
            })
            assert result["action"] == "record_success"
            assert result["proc_id"] == "proc_test_success"
        except ImportError:
            pytest.skip("procedural_memory not importable")

    def test_procedural_record_no_proc_id_success(self):
        """With exit_code=0 but no proc_id, should try learning."""
        try:
            from clarvis.heartbeat.adapters import _procedural_record
            result = _procedural_record({
                "exit_code": 0,
                "task": "some task",
                "output_text": "Did step 1. Did step 2. Done.",
            })
            assert result["action"] in ("learned", "no_steps", "extract_steps_unavailable")
        except ImportError:
            pytest.skip("procedural_memory not importable")


# ---------------------------------------------------------------------------
# 5. Advanced registry scenarios
# ---------------------------------------------------------------------------

class TestRegistryAdvanced:
    def test_multiple_hooks_same_phase(self, reg):
        """Multiple hooks in the same phase all run."""
        results_list = []
        for i in range(5):
            reg.register(HookPhase.POSTFLIGHT, f"hook_{i}",
                         lambda ctx, idx=i: results_list.append(idx),
                         priority=10 + i)
        reg.run(HookPhase.POSTFLIGHT, {})
        assert results_list == [0, 1, 2, 3, 4]

    def test_hook_returns_none(self, reg):
        """Hook returning None should be recorded."""
        reg.register(HookPhase.POSTFLIGHT, "none_hook",
                     lambda ctx: None, priority=10)
        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["none_hook"]["result"] is None

    def test_hook_modifies_context(self, reg):
        """Hooks can modify the context dict (shared state)."""
        def modifier(ctx):
            ctx["modified"] = True
            return "modified"

        def reader(ctx):
            return ctx.get("modified", False)

        reg.register(HookPhase.POSTFLIGHT, "modifier", modifier, priority=10)
        reg.register(HookPhase.POSTFLIGHT, "reader", reader, priority=20)
        ctx = {}
        results = reg.run(HookPhase.POSTFLIGHT, ctx)
        assert results["reader"]["result"] is True

    def test_hook_timing_accuracy(self, reg):
        """Hook timing should be reasonably accurate."""
        import time as _time
        def slow_hook(ctx):
            _time.sleep(0.05)
            return "done"

        reg.register(HookPhase.POSTFLIGHT, "slow", slow_hook, priority=10)
        results = reg.run(HookPhase.POSTFLIGHT, {})
        assert results["slow"]["elapsed_s"] >= 0.04

    def test_re_register_updates_priority(self, reg):
        """Re-registering with new priority should update sort order."""
        reg.register(HookPhase.POSTFLIGHT, "hook", lambda ctx: "v1", priority=90)
        reg.register(HookPhase.POSTFLIGHT, "other", lambda ctx: "v2", priority=50)
        # Re-register 'hook' with lower priority
        reg.register(HookPhase.POSTFLIGHT, "hook", lambda ctx: "v3", priority=10)
        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names[0] == "hook"  # Now first due to priority 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

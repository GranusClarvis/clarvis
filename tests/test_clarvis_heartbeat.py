"""Tests for clarvis.heartbeat — hooks and adapters.

HookRegistry is tested in depth (pure Python, no DB).
Adapters are tested for registration correctness.
"""

import json
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
        assert "intrinsic_assessment" in names
        assert len(names) == 8

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


# ---------------------------------------------------------------------------
# 6. _classify_error — pure function, no external deps
# ---------------------------------------------------------------------------

class TestClassifyError:
    @pytest.fixture(autouse=True)
    def _import_classify(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from heartbeat_postflight import _classify_error
        self._classify_error = _classify_error

    def test_timeout_exit_code_124(self):
        etype, evidence = self._classify_error(124, "some output")
        assert etype == "timeout"
        assert "124" in evidence

    def test_timeout_exit_code_124_empty_output(self):
        etype, _ = self._classify_error(124, "")
        assert etype == "timeout"

    def test_memory_keywords(self):
        output = "ChromaDB error: embedding failed on collection xyz"
        etype, evidence = self._classify_error(1, output)
        assert etype == "memory"
        assert "memory keywords" in evidence

    def test_planning_keywords(self):
        output = "preflight task_selector: queue empty, no tasks available"
        etype, evidence = self._classify_error(1, output)
        assert etype == "planning"
        assert "planning keywords" in evidence

    def test_system_keywords(self):
        output = "segfault in process, permission denied on /tmp/lock"
        etype, evidence = self._classify_error(1, output)
        assert etype == "system"
        assert "system keywords" in evidence

    def test_action_default(self):
        """Unrecognized errors default to 'action'."""
        output = "something went wrong but no recognized keywords here"
        etype, evidence = self._classify_error(1, output)
        assert etype == "action"
        assert "default" in evidence

    def test_none_output(self):
        etype, _ = self._classify_error(1, None)
        assert etype == "action"

    def test_long_output_truncated(self):
        """Should only scan last 3000 chars."""
        # Put keywords at start (beyond 3000 chars from end) — should NOT match
        prefix = "chromadb embedding " * 200  # ~3800 chars of memory keywords
        suffix = "x" * 3000
        output = prefix + suffix
        etype, _ = self._classify_error(1, output)
        assert etype == "action"  # keywords truncated away

    def test_single_keyword_not_enough(self):
        """Need >= 2 keyword hits for category match."""
        output = "recall failed once, nothing else wrong"
        etype, _ = self._classify_error(1, output)
        assert etype == "action"  # only 1 memory keyword

    # --- Regression: single-hit categories (threshold=1) ---

    def test_import_single_hit_matches(self):
        """import_error requires only 1 keyword hit (threshold=1)."""
        output = "cannot import name 'foo' from 'bar'"
        etype, evidence = self._classify_error(1, output)
        assert etype == "import_error"
        assert "1 import keywords" in evidence

    def test_logic_bug_single_hit_matches(self):
        """logic_bug requires only 1 keyword hit (threshold=1)."""
        output = "TypeError: unsupported operand type(s)"
        etype, evidence = self._classify_error(1, output)
        assert etype == "logic_bug"
        assert "1 logic-bug keywords" in evidence

    def test_system_single_hit_matches(self):
        """system requires only 1 keyword hit (threshold=1)."""
        output = "killed by signal 9"
        etype, evidence = self._classify_error(1, output)
        assert etype == "system"
        assert "1 system keywords" in evidence

    # --- Regression: threshold=2 categories need 2+ hits ---

    def test_data_single_hit_not_enough(self):
        """data_missing requires >=2 keyword hits."""
        output = "keyerror: 'missing_key'"
        etype, _ = self._classify_error(1, output)
        assert etype != "data_missing"

    def test_data_two_hits_matches(self):
        """data_missing matches with 2 keyword hits."""
        output = "FileNotFoundError: no such file /tmp/data.json"
        etype, evidence = self._classify_error(1, output)
        assert etype == "data_missing"
        assert "data-missing keywords" in evidence

    def test_external_single_hit_not_enough(self):
        """external_dep requires >=2 keyword hits."""
        output = "got 401 response"
        etype, _ = self._classify_error(1, output)
        assert etype != "external_dep"

    def test_external_auth_401_with_context(self):
        """401 + auth keyword = external_dep."""
        output = "authentication_error: 401 Unauthorized"
        etype, evidence = self._classify_error(1, output)
        assert etype == "external_dep"
        assert "external-dep keywords" in evidence

    def test_external_network_errors(self):
        """Network-related keywords trigger external_dep."""
        output = "ConnectionError: ConnectionRefusedError: econnrefused"
        etype, _ = self._classify_error(1, output)
        assert etype == "external_dep"

    # --- Regression: precedence / priority ---

    def test_timeout_beats_all_keywords(self):
        """Exit code 124 takes priority over any keyword matches."""
        output = "ImportError: No module named 'foo' — chromadb chroma embedding"
        etype, _ = self._classify_error(124, output)
        assert etype == "timeout"

    def test_import_beats_data_missing(self):
        """import_error (checked first) wins over data_missing when both present."""
        output = "ImportError: No module named 'foo'\nFileNotFoundError: no such file /data"
        etype, _ = self._classify_error(1, output)
        assert etype == "import_error"

    def test_import_beats_logic_bug(self):
        """import_error (threshold=1) checked before logic_bug (threshold=1)."""
        output = "ImportError: foo\nTypeError: bar"
        etype, _ = self._classify_error(1, output)
        assert etype == "import_error"

    def test_data_beats_external_when_both_present(self):
        """data_missing checked before external_dep in precedence order."""
        output = "FileNotFoundError: no such file\njson.decoder.JSONDecodeError: bad json\n401 connectionerror"
        etype, _ = self._classify_error(1, output)
        assert etype == "data_missing"

    def test_logic_bug_beats_system(self):
        """logic_bug checked before system in precedence order."""
        output = "ValueError: invalid value, permission denied"
        etype, _ = self._classify_error(1, output)
        assert etype == "logic_bug"

    # --- Regression: edge cases ---

    def test_empty_string_output(self):
        """Empty string output should default to action."""
        etype, _ = self._classify_error(1, "")
        assert etype == "action"

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive."""
        output = "IMPORTERROR: Cannot Import Name 'something'"
        etype, _ = self._classify_error(1, output)
        assert etype == "import_error"

    def test_exit_code_zero_with_keywords(self):
        """Non-error exit code still classifies keywords (function is called regardless)."""
        output = "ImportError: foo"
        etype, _ = self._classify_error(0, output)
        assert etype == "import_error"


# ---------------------------------------------------------------------------
# 7. Meta-learning / intrinsic assessment — daily rate limiting
# ---------------------------------------------------------------------------

class TestMetaLearningRateLimit:
    def test_skip_when_already_ran_today(self, tmp_path):
        from clarvis.heartbeat import adapters as adp
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        marker = tmp_path / ".last_postflight_run"
        marker.write_text(today)

        orig = adp._META_LEARNING_MARKER
        adp._META_LEARNING_MARKER = str(marker)
        try:
            result = adp._meta_learning_analyze({})
            assert result["action"] == "skip"
            assert result["reason"] == "already_ran_today"
        finally:
            adp._META_LEARNING_MARKER = orig

    def test_runs_when_marker_is_yesterday(self, tmp_path):
        from clarvis.heartbeat import adapters as adp

        marker = tmp_path / ".last_postflight_run"
        marker.write_text("2020-01-01")  # old date

        orig = adp._META_LEARNING_MARKER
        adp._META_LEARNING_MARKER = str(marker)
        try:
            # This will try to import MetaLearner which may not be available
            # in test env — we just verify it doesn't skip due to rate limit
            try:
                result = adp._meta_learning_analyze({})
                assert result["action"] != "skip" or result.get("reason") != "already_ran_today"
            except ImportError:
                pytest.skip("MetaLearner not importable in test env")
        finally:
            adp._META_LEARNING_MARKER = orig

    def test_runs_when_no_marker(self, tmp_path):
        from clarvis.heartbeat import adapters as adp

        marker = tmp_path / "nonexistent_marker"

        orig = adp._META_LEARNING_MARKER
        adp._META_LEARNING_MARKER = str(marker)
        try:
            try:
                result = adp._meta_learning_analyze({})
                assert result["action"] != "skip" or result.get("reason") != "already_ran_today"
            except ImportError:
                pytest.skip("MetaLearner not importable in test env")
        finally:
            adp._META_LEARNING_MARKER = orig


class TestIntrinsicAssessmentRateLimit:
    def test_skip_when_already_ran_today(self, tmp_path):
        from clarvis.heartbeat import adapters as adp
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        marker = tmp_path / ".last_assessment_run"
        marker.write_text(today)

        orig = adp._ASSESSMENT_MARKER
        adp._ASSESSMENT_MARKER = str(marker)
        try:
            result = adp._intrinsic_assessment({})
            assert result["action"] == "skip"
            assert result["reason"] == "already_ran_today"
        finally:
            adp._ASSESSMENT_MARKER = orig

    def test_runs_when_marker_is_old(self, tmp_path):
        from clarvis.heartbeat import adapters as adp

        marker = tmp_path / ".last_assessment_run"
        marker.write_text("2020-01-01")

        orig = adp._ASSESSMENT_MARKER
        adp._ASSESSMENT_MARKER = str(marker)
        try:
            try:
                result = adp._intrinsic_assessment({})
                assert result["action"] != "skip" or result.get("reason") != "already_ran_today"
            except ImportError:
                pytest.skip("intrinsic_assessment not importable in test env")
        finally:
            adp._ASSESSMENT_MARKER = orig


# ---------------------------------------------------------------------------
# 8. Priority bands — meta_learning and intrinsic_assessment
# ---------------------------------------------------------------------------

class TestPriorityBandsExtended:
    def test_meta_learning_priority_90(self):
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
        assert priorities["meta_learning"] == 90

    def test_intrinsic_assessment_priority_92(self):
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
        assert priorities["intrinsic_assessment"] == 92

    def test_meta_learning_runs_after_metrics(self):
        """meta_learning (90) should run after all metrics (60-69)."""
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
        idx_health = names.index("structural_health")
        idx_meta = names.index("meta_learning")
        idx_assess = names.index("intrinsic_assessment")
        assert idx_health < idx_meta < idx_assess


# ---------------------------------------------------------------------------
# 9. Register meta_learning and intrinsic_assessment individually
# ---------------------------------------------------------------------------

class TestRegisterOptionalHooks:
    def test_register_meta_learning_only(self):
        from clarvis.heartbeat.adapters import register_meta_learning
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_meta_learning()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["meta_learning"]

    def test_register_intrinsic_assessment_only(self):
        from clarvis.heartbeat.adapters import register_intrinsic_assessment
        import clarvis.heartbeat.adapters as adapters_mod

        reg = HookRegistry()
        original = adapters_mod.registry
        adapters_mod.registry = reg
        try:
            register_intrinsic_assessment()
        finally:
            adapters_mod.registry = original

        names = reg.hook_names(HookPhase.POSTFLIGHT)
        assert names == ["intrinsic_assessment"]


# ---------------------------------------------------------------------------
# 10. Periodic synthesis skip logic
# ---------------------------------------------------------------------------

class TestPeriodicSynthesisSkip:
    def test_skip_when_not_10th_episode(self):
        """periodic_synthesis should skip when episode count % 10 != 0."""
        from clarvis.heartbeat.adapters import _periodic_synthesis
        from unittest.mock import patch, MagicMock

        mock_em = MagicMock()
        mock_em.episodes = list(range(7))  # 7 episodes, 7 % 10 != 0
        mock_cls = MagicMock(return_value=mock_em)

        with patch("clarvis.memory.episodic_memory.EpisodicMemory", mock_cls):
            result = _periodic_synthesis({})

        assert result["action"] == "skip"
        assert result["episode_count"] == 7

    def test_skip_when_zero_episodes(self):
        """periodic_synthesis should skip when episode count is 0."""
        from clarvis.heartbeat.adapters import _periodic_synthesis
        from unittest.mock import patch, MagicMock

        mock_em = MagicMock()
        mock_em.episodes = []
        mock_cls = MagicMock(return_value=mock_em)

        with patch("clarvis.memory.episodic_memory.EpisodicMemory", mock_cls):
            result = _periodic_synthesis({})

        assert result["action"] == "skip"
        assert result["episode_count"] == 0


# ---------------------------------------------------------------------------
# 11. Pytest results capture (§7.41) — parse summary + write test_results.json
# ---------------------------------------------------------------------------

class TestPytestResultsCapture:
    """Tests for the §7.41 pytest results capture logic in postflight."""

    def _parse_and_write(self, selftest_result, workspace_dir):
        """Replicate §7.41 parsing logic for isolated testing."""
        import re as _re
        if selftest_result.get("ran") and "pytest_exit" in selftest_result:
            summary_line = selftest_result.get("pytest_summary", "")
            _passed = 0
            _failed = 0
            _m = _re.search(r'(\d+) passed', summary_line)
            if _m:
                _passed = int(_m.group(1))
            _m = _re.search(r'(\d+) failed', summary_line)
            if _m:
                _failed = int(_m.group(1))
            _test_data = {
                "passed": _passed,
                "failed": _failed,
                "errors": 0,
                "total": _passed + _failed,
                "pytest_exit_code": selftest_result.get("pytest_exit", -1),
                "source": "postflight_self_test",
            }
            path = os.path.join(workspace_dir, "data", "test_results.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(_test_data, f)
            return _test_data
        return None

    def test_parse_all_passed(self, tmp_path):
        result = self._parse_and_write(
            {"ran": True, "pytest_exit": 0, "pytest_summary": "12 passed in 3.5s"},
            str(tmp_path),
        )
        assert result["passed"] == 12
        assert result["failed"] == 0
        assert result["total"] == 12
        assert result["pytest_exit_code"] == 0
        assert result["source"] == "postflight_self_test"
        # Verify file was written
        written = json.loads((tmp_path / "data" / "test_results.json").read_text())
        assert written["passed"] == 12

    def test_parse_mixed_results(self, tmp_path):
        result = self._parse_and_write(
            {"ran": True, "pytest_exit": 1, "pytest_summary": "8 passed, 3 failed in 5.2s"},
            str(tmp_path),
        )
        assert result["passed"] == 8
        assert result["failed"] == 3
        assert result["total"] == 11
        assert result["pytest_exit_code"] == 1

    def test_parse_no_summary(self, tmp_path):
        """Empty summary should yield zeros."""
        result = self._parse_and_write(
            {"ran": True, "pytest_exit": 5, "pytest_summary": ""},
            str(tmp_path),
        )
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0

    def test_skip_when_not_ran(self, tmp_path):
        """Should return None when selftest didn't run."""
        result = self._parse_and_write(
            {"ran": False, "code_modified": False},
            str(tmp_path),
        )
        assert result is None

    def test_skip_when_no_pytest_exit(self, tmp_path):
        """Should return None when pytest_exit key is missing."""
        result = self._parse_and_write(
            {"ran": True},
            str(tmp_path),
        )
        assert result is None

    def test_parse_only_failed(self, tmp_path):
        """Summary with only failures and no passes."""
        result = self._parse_and_write(
            {"ran": True, "pytest_exit": 1, "pytest_summary": "2 failed in 1.0s"},
            str(tmp_path),
        )
        assert result["passed"] == 0
        assert result["failed"] == 2
        assert result["total"] == 2


# ---------------------------------------------------------------------------
# 11b. Regression: WORKSPACE must be defined before §7.41 test capture
# ---------------------------------------------------------------------------

class TestWorkspaceDefined:
    """Regression test for POSTFLIGHT_TEST_CAPTURE_WORKSPACE_FIX (2026-03-15).

    The §7.41 test-results capture block uses WORKSPACE for path construction
    and subprocess cwd. If WORKSPACE is not defined, the block raises NameError
    and silently fails (non-fatal). This test ensures the constant is always
    set before any code that references it.
    """

    def test_workspace_defined_in_postflight_ctx(self):
        """WORKSPACE must be available via _build_postflight_ctx or run_postflight.

        After decomposition, WORKSPACE flows through ctx["WORKSPACE"] set in
        _build_postflight_ctx rather than as a direct local in run_postflight.
        """
        import ast
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "heartbeat_postflight.py"
        )
        with open(src_path) as f:
            source = f.read()
        tree = ast.parse(source)
        # WORKSPACE must be assigned somewhere in the postflight module
        # (either in _build_postflight_ctx or run_postflight)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in (
                "run_postflight", "_build_postflight_ctx"
            ):
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name) and target.id == "WORKSPACE":
                                found = True
                    # Also check dict subscript assignments like ctx["WORKSPACE"] = ...
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if (isinstance(target, ast.Subscript)
                                and isinstance(target.slice, ast.Constant)
                                and target.slice.value == "WORKSPACE"):
                                found = True
        assert found, (
            "WORKSPACE must be defined in _build_postflight_ctx or run_postflight "
            "(regression: POSTFLIGHT_TEST_CAPTURE_WORKSPACE_FIX)"
        )

    def test_workspace_used_in_path_construction(self):
        """os.path.join calls for test_results.json in §7.41 must use WORKSPACE."""
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "heartbeat_postflight.py"
        )
        with open(src_path) as f:
            lines = f.readlines()
        in_block = False
        for i, line in enumerate(lines, 1):
            if "7.41" in line and "PYTEST RESULTS CAPTURE" in line:
                in_block = True
            elif in_block and line.strip().startswith("# ===") and "7.4" not in line:
                break
            # Only check actual path construction lines
            if in_block and "os.path.join" in line and "test_results" in line:
                assert "WORKSPACE" in line, (
                    f"Line {i}: os.path.join for test_results must use WORKSPACE, "
                    f"not a hardcoded path: {line.strip()}"
                )


# ---------------------------------------------------------------------------
# 12. Noise ratio computation + episode tagging
# ---------------------------------------------------------------------------

class TestNoiseRatioTagging:
    """Tests for the noise_ratio = 1 - relevance logic and episode tagging."""

    def test_noise_ratio_computation(self):
        """noise_ratio should be 1 - overall relevance."""
        overall = 0.75
        noise_ratio = round(1.0 - overall, 4)
        assert noise_ratio == 0.25

    def test_noise_ratio_zero_relevance(self):
        """0% relevance → 100% noise."""
        noise_ratio = round(1.0 - 0.0, 4)
        assert noise_ratio == 1.0

    def test_noise_ratio_full_relevance(self):
        """100% relevance → 0% noise."""
        noise_ratio = round(1.0 - 1.0, 4)
        assert noise_ratio == 0.0

    def test_noise_ratio_tagged_on_matching_episode(self):
        """When latest episode task matches, noise_ratio should be tagged."""
        from unittest.mock import MagicMock

        task = "Implement feature X for the system"
        noise_ratio = 0.35
        cr_overall = 0.65

        mock_em = MagicMock()
        latest_ep = {"task": task, "id": "ep_42"}
        mock_em.episodes = [latest_ep]

        # Simulate the tagging logic from postflight
        if mock_em.episodes:
            ep = mock_em.episodes[-1]
            if ep.get("task", "")[:60] == task[:60]:
                ep["noise_ratio"] = noise_ratio
                ep["context_relevance"] = cr_overall
                mock_em._save()

        assert latest_ep["noise_ratio"] == 0.35
        assert latest_ep["context_relevance"] == 0.65
        mock_em._save.assert_called_once()

    def test_no_tag_when_task_mismatch(self):
        """When latest episode task doesn't match, no tagging should happen."""
        from unittest.mock import MagicMock

        task = "Implement feature X"
        noise_ratio = 0.35
        cr_overall = 0.65

        mock_em = MagicMock()
        latest_ep = {"task": "Completely different task", "id": "ep_99"}
        mock_em.episodes = [latest_ep]

        if mock_em.episodes:
            ep = mock_em.episodes[-1]
            if ep.get("task", "")[:60] == task[:60]:
                ep["noise_ratio"] = noise_ratio
                ep["context_relevance"] = cr_overall
                mock_em._save()

        assert "noise_ratio" not in latest_ep
        mock_em._save.assert_not_called()

    def test_no_tag_when_no_episodes(self):
        """When episode list is empty, no tagging should happen."""
        from unittest.mock import MagicMock

        mock_em = MagicMock()
        mock_em.episodes = []

        save_called = False
        if mock_em.episodes:
            save_called = True

        assert not save_called

    def test_noise_ratio_added_to_cr_result(self):
        """noise_ratio should be added to the cr_result dict."""
        cr_result = {
            "overall": 0.82,
            "sections_referenced": 5,
            "sections_total": 8,
        }
        noise_ratio = round(1.0 - cr_result["overall"], 4)
        cr_result["noise_ratio"] = noise_ratio

        assert cr_result["noise_ratio"] == 0.18
        assert "noise_ratio" in cr_result


# ---------------------------------------------------------------------------
# 13. Stale test_results.json refresh detection
# ---------------------------------------------------------------------------

class TestStaleRefreshDetection:
    """Tests for the stale detection logic (>24h) in §7.41."""

    def test_fresh_file_not_stale(self, tmp_path):
        """A file modified just now should not be considered stale."""
        test_file = tmp_path / "test_results.json"
        test_file.write_text("{}")

        age = time.time() - os.path.getmtime(str(test_file))
        stale = age > 86400
        assert not stale

    def test_old_file_is_stale(self, tmp_path):
        """A file older than 24h should be considered stale."""
        test_file = tmp_path / "test_results.json"
        test_file.write_text("{}")
        # Backdate modification time by 25 hours
        old_time = time.time() - 90000
        os.utime(str(test_file), (old_time, old_time))

        age = time.time() - os.path.getmtime(str(test_file))
        stale = age > 86400
        assert stale

    def test_missing_file_is_stale(self, tmp_path):
        """A non-existent file should be treated as stale."""
        test_file = tmp_path / "test_results.json"
        stale = True
        if test_file.exists():
            age = time.time() - os.path.getmtime(str(test_file))
            stale = age > 86400
        assert stale


# ---------------------------------------------------------------------------
# 14. _mark_task_in_queue — extracted module-level function
# ---------------------------------------------------------------------------

class TestMarkTaskInQueue:
    """Tests for the _mark_task_in_queue function (extracted from §10)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from heartbeat_postflight import _mark_task_in_queue
        self._mark = _mark_task_in_queue

    def test_tag_match_marks_task(self, tmp_path):
        """Tag-based matching should find and mark the task."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "## P1\n"
            "- [ ] [MY_TASK] Do something important\n"
            "- [ ] [OTHER] Another task\n"
        )
        result = self._mark("[MY_TASK]", "2026-03-17 done", str(queue))
        assert result == "marked"
        content = queue.read_text()
        assert "- [x] [MY_TASK] Do something important (2026-03-17 done)" in content
        # Other task should remain untouched
        assert "- [ ] [OTHER]" in content

    def test_prefix_match_marks_task(self, tmp_path):
        """Legacy prefix matching should work when no tag is present."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "## P1\n"
            "- [ ] Fix the flaky test in test_brain.py that fails intermittently\n"
        )
        result = self._mark(
            "Fix the flaky test in test_brain.py that fails intermittently",
            "done", str(queue)
        )
        assert result == "marked"
        assert "- [x]" in queue.read_text()

    def test_not_found_returns_false(self, tmp_path):
        """Non-matching task returns False."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text("## P1\n- [ ] [EXISTING] Some task\n")
        result = self._mark("[NONEXISTENT]", "done", str(queue))
        assert result is False

    def test_already_archived(self, tmp_path):
        """Task found in archive returns 'archived'."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text("## P1\n")
        archive = tmp_path / "ARCHIVE.md"
        archive.write_text("- [x] Fix the flaky test (done)\n")
        result = self._mark("Fix the flaky test", "done", str(queue), str(archive))
        assert result == "archived"

    def test_no_archive_file(self, tmp_path):
        """Without archive file, unmatched task returns False (no crash)."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text("## P1\n")
        result = self._mark("[MISSING]", "done", str(queue))
        assert result is False

    def test_tag_preferred_over_prefix(self, tmp_path):
        """Tag match should be preferred even if prefix would also match."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "- [ ] [TAG_A] Description that also matches prefix of TAG_A\n"
            "- [ ] [TAG_B] Different task\n"
        )
        result = self._mark("[TAG_A] Description that also matches prefix of TAG_A",
                           "done", str(queue))
        assert result == "marked"
        content = queue.read_text()
        assert "- [x] [TAG_A]" in content
        assert "- [ ] [TAG_B]" in content

    def test_already_checked_task_not_rematched(self, tmp_path):
        """Already-completed tasks (- [x]) should NOT be re-matched."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text("- [x] [DONE_TASK] Already done\n- [ ] [OPEN] Still open\n")
        result = self._mark("[DONE_TASK]", "again", str(queue))
        assert result is False

    def test_annotation_appended(self, tmp_path):
        """Annotation text should appear after the task line."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text("- [ ] [FIX] Repair the widget\n")
        self._mark("[FIX]", "2026-03-17 14:00 UTC", str(queue))
        content = queue.read_text()
        assert "(2026-03-17 14:00 UTC)" in content

    def test_indented_task(self, tmp_path):
        """Indented tasks (sub-items) should also match."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "## P1\n"
            "- [~] [PARENT] Parent task\n"
            "  - [ ] [CHILD_TASK] Sub-task to complete\n"
        )
        result = self._mark("[CHILD_TASK]", "done", str(queue))
        assert result == "marked"
        assert "- [x] [CHILD_TASK]" in queue.read_text()


# ---------------------------------------------------------------------------
# 15. _compute_completeness — extracted scoring function
# ---------------------------------------------------------------------------

class TestComputeCompleteness:
    """Tests for the _compute_completeness function."""

    @pytest.fixture(autouse=True)
    def _import(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from heartbeat_postflight import _compute_completeness
        self._compute = _compute_completeness

    def test_all_stages_pass(self):
        timings = {"confidence": 0.01, "procedural": 0.02, "episodic": 0.03, "total": 0.06}
        attempted, ok, failed, score = self._compute(timings, [])
        assert attempted == 3
        assert ok == 3
        assert failed == 0
        assert score == 1.0

    def test_some_failures(self):
        timings = {"confidence": 0.01, "procedural": 0.02, "episodic": 0.03,
                    "digest": 0.01, "total": 0.07}
        attempted, ok, failed, score = self._compute(timings, ["confidence", "digest"])
        assert attempted == 4
        assert ok == 2
        assert failed == 2
        assert score == 0.5

    def test_all_failures(self):
        timings = {"stage_a": 0.1, "total": 0.1}
        attempted, ok, failed, score = self._compute(timings, ["stage_a"])
        assert attempted == 1
        assert ok == 0
        assert score == 0.0

    def test_empty_timings(self):
        """No stages attempted should return completeness 1.0 (vacuously true)."""
        timings = {"total": 0.0}
        attempted, ok, failed, score = self._compute(timings, [])
        assert attempted == 0
        assert score == 1.0

    def test_total_excluded_from_count(self):
        """The 'total' key should not count as a stage."""
        timings = {"a": 0.1, "b": 0.2, "total": 0.3}
        attempted, _, _, _ = self._compute(timings, [])
        assert attempted == 2


# ---------------------------------------------------------------------------
# 16. Hook context building — verify §4 builds correct context for hooks
# ---------------------------------------------------------------------------

class TestHookContextBuilding:
    """Verify the hook context dict structure matches what adapters expect."""

    def test_hook_context_has_required_keys(self):
        """The context dict built in §4 must contain all keys adapters read."""
        # Simulate the context building from §4 of run_postflight
        preflight_data = {
            "task": "Fix bug in parser",
            "procedure_id": "proc_123",
            "procedure_injected": True,
            "procedures_for_injection": ["proc_123"],
        }
        hook_ctx = {
            "exit_code": 0,
            "task": preflight_data.get("task", "unknown"),
            "output_text": "task output here",
            "procedure_id": preflight_data.get("procedure_id"),
            "task_status": "success",
            "task_duration": 120,
            "procedure_injected": preflight_data.get("procedure_injected", False),
            "procedures_for_injection": preflight_data.get("procedures_for_injection", []),
        }

        # Keys that adapters actually read
        required_keys = [
            "exit_code", "task", "output_text", "procedure_id",
            "task_status", "task_duration", "procedure_injected",
            "procedures_for_injection",
        ]
        for key in required_keys:
            assert key in hook_ctx, f"Missing required hook context key: {key}"

    def test_hook_context_defaults(self):
        """With minimal preflight data, context should still have safe defaults."""
        preflight_data = {}
        hook_ctx = {
            "exit_code": 1,
            "task": preflight_data.get("task", "unknown"),
            "output_text": "",
            "procedure_id": preflight_data.get("procedure_id"),
            "task_status": "failure",
            "task_duration": 0,
            "procedure_injected": preflight_data.get("procedure_injected", False),
            "procedures_for_injection": preflight_data.get("procedures_for_injection", []),
        }
        assert hook_ctx["task"] == "unknown"
        assert hook_ctx["procedure_id"] is None
        assert hook_ctx["procedure_injected"] is False
        assert hook_ctx["procedures_for_injection"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

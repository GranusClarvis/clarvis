"""Unit tests for clarvis/audit/{trace.py, toggles.py}.

Task: [SPINE_AUDIT_MODULE_TEST_HARNESS]
Covers:
  1. Trace lifecycle: start_trace → update_trace → finalize_trace → load_trace
  2. Toggle registry: load_toggles, is_enabled, is_shadow, DEFAULT_TOGGLES seeding
  3. Fail-open behaviour when data/audit/ is read-only
  4. Exercises all __init__.py exports to reduce dead_exports count
"""

import json
import os
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_audit_dirs(tmp_path, monkeypatch):
    """Redirect both trace root and toggle path to tmp so tests never touch real data."""
    import clarvis.audit.trace as _trace
    import clarvis.audit.toggles as _toggles

    traces_root = tmp_path / "traces"
    traces_root.mkdir()
    toggles_path = tmp_path / "feature_toggles.json"

    monkeypatch.setattr(_trace, "TRACES_ROOT", traces_root)
    monkeypatch.setattr(_toggles, "TOGGLES_PATH", toggles_path)

    # Clear ambient trace state
    monkeypatch.delenv("CLARVIS_AUDIT_TRACE_ID", raising=False)
    _trace._active.trace_id = None

    yield {"traces_root": traces_root, "toggles_path": toggles_path}


@pytest.fixture
def dirs(_isolate_audit_dirs):
    return _isolate_audit_dirs


# ---------------------------------------------------------------------------
# Import-level exercise: touch every __init__.py export
# ---------------------------------------------------------------------------

def test_all_exports_importable():
    """Exercise every symbol exported by clarvis.audit.__init__."""
    from clarvis.audit import (
        AuditTrace,
        new_trace_id,
        start_trace,
        update_trace,
        finalize_trace,
        load_trace,
        current_trace_id,
        set_current_trace_id,
        trace_path_for,
        load_toggles,
        is_enabled,
        is_shadow,
        toggle_snapshot,
        DEFAULT_TOGGLES,
    )
    # Verify they are callable / dict as expected
    assert callable(new_trace_id)
    assert callable(start_trace)
    assert callable(update_trace)
    assert callable(finalize_trace)
    assert callable(load_trace)
    assert callable(current_trace_id)
    assert callable(set_current_trace_id)
    assert callable(trace_path_for)
    assert callable(load_toggles)
    assert callable(is_enabled)
    assert callable(is_shadow)
    assert callable(toggle_snapshot)
    assert isinstance(DEFAULT_TOGGLES, dict)
    assert len(DEFAULT_TOGGLES) >= 20  # 23 at time of writing


# ===========================================================================
# 1. Trace lifecycle
# ===========================================================================

class TestNewTraceId:
    def test_format(self):
        from clarvis.audit.trace import new_trace_id
        tid = new_trace_id()
        # Format: YYYYMMDDTHHMMSSZ-<6hex> = 16 + 1 + 6 = 23 chars
        assert len(tid) == 23
        assert "T" in tid
        assert "Z-" in tid

    def test_deterministic_with_fixed_time(self):
        from clarvis.audit.trace import new_trace_id
        dt = datetime(2026, 4, 18, 12, 30, 45, tzinfo=timezone.utc)
        tid = new_trace_id(now=dt)
        assert tid.startswith("20260418T123045Z-")
        assert len(tid.split("-")[-1]) == 6  # 6 hex chars


class TestTracePath:
    def test_date_partition(self, dirs):
        from clarvis.audit.trace import trace_path_for
        tid = "20260418T120000Z-abc123"
        p = trace_path_for(tid)
        assert "2026-04-18" in str(p)
        assert p.name == f"{tid}.json"

    def test_custom_root(self, dirs, tmp_path):
        from clarvis.audit.trace import trace_path_for
        custom = tmp_path / "custom"
        tid = "20260418T120000Z-abc123"
        p = trace_path_for(tid, root=custom)
        assert str(p).startswith(str(custom))

    def test_malformed_id_fallback(self, dirs):
        from clarvis.audit.trace import trace_path_for
        p = trace_path_for("bad")
        # Should use today's date as fallback, not crash
        assert p.name == "bad.json"


class TestAuditTraceDataclass:
    def test_to_dict_round_trip(self):
        from clarvis.audit.trace import AuditTrace
        tr = AuditTrace(
            audit_trace_id="test-id",
            created_at="2026-04-18T00:00:00Z",
            source="manual",
        )
        d = tr.to_dict()
        assert d["audit_trace_id"] == "test-id"
        assert d["source"] == "manual"
        assert d["schema_version"] == 1
        assert isinstance(d["preflight"], dict)
        assert isinstance(d["execution"], dict)


class TestStartTrace:
    def test_creates_file_and_returns_id(self, dirs):
        from clarvis.audit.trace import start_trace, load_trace
        tid = start_trace(source="test")
        assert tid is not None
        data = load_trace(tid)
        assert data is not None
        assert data["source"] == "test"
        assert data["schema_version"] == 1

    def test_custom_trace_id(self, dirs):
        from clarvis.audit.trace import start_trace, load_trace
        tid = start_trace(source="manual", trace_id="20260418T000000Z-custom")
        assert tid == "20260418T000000Z-custom"
        assert load_trace(tid) is not None

    def test_sets_ambient_by_default(self, dirs):
        from clarvis.audit.trace import start_trace, current_trace_id
        tid = start_trace(source="test")
        assert current_trace_id() == tid

    def test_no_ambient_when_disabled(self, dirs):
        from clarvis.audit.trace import start_trace, current_trace_id, set_current_trace_id
        set_current_trace_id(None)
        start_trace(source="test", set_ambient=False)
        assert current_trace_id() is None

    def test_with_task_and_cron_origin(self, dirs):
        from clarvis.audit.trace import start_trace, load_trace
        tid = start_trace(
            source="heartbeat",
            task={"name": "TEST_TASK", "priority": "P1"},
            cron_origin="cron_autonomous.sh",
            queue_run_id="run-42",
        )
        data = load_trace(tid)
        assert data["task"]["name"] == "TEST_TASK"
        assert data["cron_origin"] == "cron_autonomous.sh"
        assert data["queue_run_id"] == "run-42"

    def test_with_feature_toggles(self, dirs):
        from clarvis.audit.trace import start_trace, load_trace
        toggles = {"brain_retrieval": {"enabled": True, "shadow": False}}
        tid = start_trace(source="test", feature_toggles=toggles)
        data = load_trace(tid)
        assert data["feature_toggles"]["brain_retrieval"]["enabled"] is True


class TestUpdateTrace:
    def test_deep_merge(self, dirs):
        from clarvis.audit.trace import start_trace, update_trace, load_trace
        tid = start_trace(source="test", task={"name": "T1", "meta": {"a": 1}})
        ok = update_trace(tid, task={"meta": {"b": 2}}, preflight={"score": 0.9})
        assert ok is True
        data = load_trace(tid)
        # Deep merge: meta should have both a and b
        assert data["task"]["meta"]["a"] == 1
        assert data["task"]["meta"]["b"] == 2
        assert data["preflight"]["score"] == 0.9
        assert "updated_at" in data

    def test_scalar_overwrite(self, dirs):
        from clarvis.audit.trace import start_trace, update_trace, load_trace
        tid = start_trace(source="test")
        update_trace(tid, execution={"duration_s": 10})
        update_trace(tid, execution={"duration_s": 20, "exit_code": 0})
        data = load_trace(tid)
        assert data["execution"]["duration_s"] == 20
        assert data["execution"]["exit_code"] == 0

    def test_returns_false_for_none_id(self, dirs):
        from clarvis.audit.trace import update_trace, set_current_trace_id
        set_current_trace_id(None)
        assert update_trace(None, foo="bar") is False

    def test_returns_false_for_missing_file(self, dirs):
        from clarvis.audit.trace import update_trace
        assert update_trace("nonexistent-trace-id", foo="bar") is False

    def test_uses_ambient_when_id_is_none(self, dirs):
        from clarvis.audit.trace import start_trace, update_trace, load_trace
        tid = start_trace(source="test")  # sets ambient
        ok = update_trace(None, execution={"step": "running"})
        assert ok is True
        data = load_trace(tid)
        assert data["execution"]["step"] == "running"


class TestFinalizeTrace:
    def test_writes_outcome(self, dirs):
        from clarvis.audit.trace import start_trace, finalize_trace, load_trace
        tid = start_trace(source="test")
        ok = finalize_trace(tid, outcome="success", exit_code=0, duration_s=123.456)
        assert ok is True
        data = load_trace(tid)
        assert data["outcome"]["status"] == "success"
        assert data["outcome"]["exit_code"] == 0
        assert data["outcome"]["duration_s"] == 123.456
        assert "finalized_at" in data["outcome"]

    def test_with_outcome_link(self, dirs):
        from clarvis.audit.trace import start_trace, finalize_trace, load_trace
        tid = start_trace(source="test")
        finalize_trace(tid, outcome="success", outcome_link={"episode_id": "ep-1"})
        data = load_trace(tid)
        assert data["outcome_link"]["episode_id"] == "ep-1"

    def test_with_extra_sections(self, dirs):
        from clarvis.audit.trace import start_trace, finalize_trace, load_trace
        tid = start_trace(source="test")
        finalize_trace(tid, outcome="failure", extra={"postflight": {"saved": True}})
        data = load_trace(tid)
        assert data["outcome"]["status"] == "failure"
        assert data["postflight"]["saved"] is True

    def test_returns_false_for_none(self, dirs):
        from clarvis.audit.trace import finalize_trace, set_current_trace_id
        set_current_trace_id(None)
        assert finalize_trace(None, outcome="success") is False

    def test_full_lifecycle(self, dirs):
        """start → update → finalize → load round-trip."""
        from clarvis.audit.trace import start_trace, update_trace, finalize_trace, load_trace
        tid = start_trace(source="heartbeat", task={"name": "LIFECYCLE_TEST"})
        assert tid is not None

        update_trace(tid, preflight={"attention_score": 0.85})
        update_trace(tid, prompt={"token_count": 3400})
        update_trace(tid, execution={"model": "claude-opus-4-6", "duration_s": 120})
        finalize_trace(tid, outcome="success", exit_code=0, duration_s=125.0,
                       outcome_link={"episode_id": "ep-lifecycle"})

        data = load_trace(tid)
        assert data["audit_trace_id"] == tid
        assert data["task"]["name"] == "LIFECYCLE_TEST"
        assert data["preflight"]["attention_score"] == 0.85
        assert data["prompt"]["token_count"] == 3400
        assert data["execution"]["model"] == "claude-opus-4-6"
        assert data["outcome"]["status"] == "success"
        assert data["outcome_link"]["episode_id"] == "ep-lifecycle"


class TestLoadTrace:
    def test_returns_none_for_missing(self, dirs):
        from clarvis.audit.trace import load_trace
        assert load_trace("20260418T000000Z-absent") is None

    def test_returns_none_for_corrupt_json(self, dirs):
        from clarvis.audit.trace import trace_path_for, load_trace
        tid = "20260418T000000Z-bad000"
        p = trace_path_for(tid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("NOT JSON", encoding="utf-8")
        assert load_trace(tid) is None


class TestCurrentTraceId:
    def test_from_env(self, dirs, monkeypatch):
        from clarvis.audit.trace import current_trace_id, _active
        _active.trace_id = None
        monkeypatch.setenv("CLARVIS_AUDIT_TRACE_ID", "env-trace-id")
        assert current_trace_id() == "env-trace-id"

    def test_process_local_takes_precedence(self, dirs, monkeypatch):
        from clarvis.audit.trace import current_trace_id, set_current_trace_id
        monkeypatch.setenv("CLARVIS_AUDIT_TRACE_ID", "env-id")
        set_current_trace_id("local-id")
        assert current_trace_id() == "local-id"

    def test_returns_none_when_unset(self, dirs):
        from clarvis.audit.trace import current_trace_id
        assert current_trace_id() is None

    def test_set_and_clear(self, dirs):
        from clarvis.audit.trace import set_current_trace_id, current_trace_id
        set_current_trace_id("my-trace")
        assert current_trace_id() == "my-trace"
        assert os.environ.get("CLARVIS_AUDIT_TRACE_ID") == "my-trace"
        set_current_trace_id(None)
        assert current_trace_id() is None
        assert os.environ.get("CLARVIS_AUDIT_TRACE_ID") is None


class TestAtomicWrite:
    def test_no_tmp_file_left_behind(self, dirs):
        from clarvis.audit.trace import start_trace
        tid = start_trace(source="test")
        traces_root = dirs["traces_root"]
        # Walk all files — no .tmp should remain
        for f in traces_root.rglob("*"):
            assert not f.name.endswith(".tmp"), f"Leftover tmp file: {f}"


# ===========================================================================
# 2. Toggle registry
# ===========================================================================

class TestLoadToggles:
    def test_seeds_on_first_load(self, dirs):
        from clarvis.audit.toggles import load_toggles, DEFAULT_TOGGLES
        toggles = load_toggles()
        assert len(toggles) == len(DEFAULT_TOGGLES)
        for key in DEFAULT_TOGGLES:
            assert key in toggles
            assert "last_changed" in toggles[key]

    def test_seeds_file_on_disk(self, dirs):
        from clarvis.audit.toggles import load_toggles
        load_toggles()
        path = dirs["toggles_path"]
        assert path.exists()
        raw = json.loads(path.read_text())
        assert "_schema" in raw
        assert "toggles" in raw

    def test_custom_path(self, dirs, tmp_path):
        from clarvis.audit.toggles import load_toggles
        custom = tmp_path / "custom_toggles.json"
        toggles = load_toggles(path=custom)
        assert len(toggles) > 0
        assert custom.exists()

    def test_23_default_features(self):
        from clarvis.audit.toggles import DEFAULT_TOGGLES
        assert len(DEFAULT_TOGGLES) == 23


class TestIsEnabled:
    def test_known_feature_enabled(self, dirs):
        from clarvis.audit.toggles import is_enabled
        assert is_enabled("brain_retrieval") is True

    def test_unknown_feature_defaults_true(self, dirs):
        from clarvis.audit.toggles import is_enabled
        assert is_enabled("nonexistent_feature") is True

    def test_unknown_feature_custom_default(self, dirs):
        from clarvis.audit.toggles import is_enabled
        assert is_enabled("nonexistent_feature", default=False) is False

    def test_disabled_feature(self, dirs):
        from clarvis.audit.toggles import set_toggle, is_enabled
        set_toggle("test_feat", enabled=False)
        assert is_enabled("test_feat") is False


class TestIsShadow:
    def test_default_features_not_shadowed(self, dirs):
        from clarvis.audit.toggles import is_shadow
        assert is_shadow("brain_retrieval") is False

    def test_unknown_feature_defaults_false(self, dirs):
        from clarvis.audit.toggles import is_shadow
        assert is_shadow("nonexistent_feature") is False

    def test_shadow_true_when_enabled(self, dirs):
        from clarvis.audit.toggles import set_toggle, is_shadow
        set_toggle("shadowed_feat", enabled=True, shadow=True)
        assert is_shadow("shadowed_feat") is True

    def test_shadow_false_when_disabled(self, dirs):
        """Shadow is meaningless if feature is disabled — is_shadow returns False."""
        from clarvis.audit.toggles import set_toggle, is_shadow
        set_toggle("off_shadow", enabled=False, shadow=True)
        assert is_shadow("off_shadow") is False


class TestToggleSnapshot:
    def test_returns_copy(self, dirs):
        from clarvis.audit.toggles import toggle_snapshot, load_toggles
        snap = toggle_snapshot()
        toggles = load_toggles()
        # Mutating snapshot should not affect a subsequent load
        snap["brain_retrieval"]["notes"] = "MUTATED"
        fresh = load_toggles()
        assert fresh["brain_retrieval"]["notes"] != "MUTATED"

    def test_all_keys_present(self, dirs):
        from clarvis.audit.toggles import toggle_snapshot, DEFAULT_TOGGLES
        snap = toggle_snapshot()
        for key in DEFAULT_TOGGLES:
            assert key in snap


class TestSetToggle:
    def test_update_existing(self, dirs):
        from clarvis.audit.toggles import load_toggles, set_toggle
        load_toggles()  # seed
        ok = set_toggle("brain_retrieval", shadow=True, notes="testing shadow mode")
        assert ok is True
        refreshed = load_toggles()
        assert refreshed["brain_retrieval"]["shadow"] is True
        assert refreshed["brain_retrieval"]["notes"] == "testing shadow mode"

    def test_create_new_toggle(self, dirs):
        from clarvis.audit.toggles import load_toggles, set_toggle
        load_toggles()  # seed
        set_toggle("brand_new_feature", enabled=True, shadow=False, notes="fresh")
        refreshed = load_toggles()
        assert "brand_new_feature" in refreshed
        assert refreshed["brand_new_feature"]["enabled"] is True


# ===========================================================================
# 3. Fail-open behaviour
# ===========================================================================

class TestFailOpen:
    def test_start_trace_returns_none_on_read_only(self, dirs):
        """start_trace must not raise when data dir is unwritable."""
        from clarvis.audit.trace import start_trace
        traces_root = dirs["traces_root"]
        # Make traces root read-only
        traces_root.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = start_trace(source="test")
            # Fail-open: returns None, does not raise
            assert result is None
        finally:
            traces_root.chmod(stat.S_IRWXU)

    def test_update_trace_returns_false_on_missing_trace(self, dirs):
        from clarvis.audit.trace import update_trace
        assert update_trace("nonexistent", foo="bar") is False

    def test_finalize_trace_returns_false_on_missing(self, dirs):
        from clarvis.audit.trace import finalize_trace
        assert finalize_trace("nonexistent", outcome="success") is False

    def test_load_toggles_returns_defaults_on_corrupt_file(self, dirs):
        """If toggles file is corrupt, load_toggles returns defaults (fail-open)."""
        from clarvis.audit.toggles import load_toggles, DEFAULT_TOGGLES
        path = dirs["toggles_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CORRUPT{{{", encoding="utf-8")
        toggles = load_toggles()
        # Should get defaults, not crash
        assert len(toggles) == len(DEFAULT_TOGGLES)

    def test_is_enabled_survives_corrupt_toggles(self, dirs):
        from clarvis.audit.toggles import is_enabled
        path = dirs["toggles_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("NOT JSON", encoding="utf-8")
        # Fail-open: returns default (True)
        assert is_enabled("brain_retrieval") is True

    def test_is_shadow_survives_corrupt_toggles(self, dirs):
        from clarvis.audit.toggles import is_shadow
        path = dirs["toggles_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("NOT JSON", encoding="utf-8")
        assert is_shadow("brain_retrieval") is False


# ===========================================================================
# 4. Deep-merge unit tests
# ===========================================================================

class TestDeepMerge:
    def test_nested_dicts_merge(self):
        from clarvis.audit.trace import _deep_merge
        base = {"a": {"x": 1, "y": 2}, "b": 10}
        incoming = {"a": {"y": 3, "z": 4}, "c": 20}
        result = _deep_merge(base, incoming)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}, "b": 10, "c": 20}

    def test_list_overwrites(self):
        from clarvis.audit.trace import _deep_merge
        base = {"tags": ["a", "b"]}
        incoming = {"tags": ["c"]}
        result = _deep_merge(base, incoming)
        assert result["tags"] == ["c"]

    def test_scalar_overwrites(self):
        from clarvis.audit.trace import _deep_merge
        base = {"count": 5}
        incoming = {"count": 10}
        assert _deep_merge(base, incoming)["count"] == 10

    def test_empty_incoming(self):
        from clarvis.audit.trace import _deep_merge
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_empty_base(self):
        from clarvis.audit.trace import _deep_merge
        assert _deep_merge({}, {"a": 1}) == {"a": 1}

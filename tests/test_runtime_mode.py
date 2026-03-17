"""Runtime mode control-plane tests."""

import importlib


def _load_mode_module(monkeypatch, tmp_path):
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(tmp_path))
    import clarvis.runtime.mode as mode_module
    return importlib.reload(mode_module)


def test_mode_alias_normalization(monkeypatch, tmp_path):
    mode = _load_mode_module(monkeypatch, tmp_path)
    assert mode.normalize_mode("ge") == "ge"
    assert mode.normalize_mode("maintenance") == "architecture"
    assert mode.normalize_mode("architecture-maintenance") == "architecture"
    assert mode.normalize_mode("user_directed") == "passive"


def test_set_mode_deferred_when_active_tasks(monkeypatch, tmp_path):
    mode = _load_mode_module(monkeypatch, tmp_path)

    result = mode.set_mode("passive", reason="manual pause", defer_if_active=True, active_tasks=2)
    assert result["status"] == "pending"
    assert result["pending_mode"] == "passive"

    state = mode.read_mode_state()
    assert state.mode == "ge"
    assert state.pending_mode == "passive"


def test_apply_pending_mode_when_tasks_clear(monkeypatch, tmp_path):
    mode = _load_mode_module(monkeypatch, tmp_path)
    mode.set_mode("architecture", reason="queue cleanup", defer_if_active=True, active_tasks=1)

    waiting = mode.apply_pending_mode(active_tasks=1)
    assert waiting["status"] == "waiting"
    assert waiting["pending_mode"] == "architecture"

    switched = mode.apply_pending_mode(active_tasks=0)
    assert switched["status"] == "switched"
    assert switched["mode"] == "architecture"

    state = mode.read_mode_state()
    assert state.mode == "architecture"
    assert state.pending_mode is None


def test_task_eligibility_for_modes(monkeypatch, tmp_path):
    mode = _load_mode_module(monkeypatch, tmp_path)

    allow, reason = mode.is_task_allowed_for_mode(
        "[AUTO_SPLIT 2026-03-15] Build new feature for autonomous discovery",
        mode="architecture",
    )
    assert allow is False
    assert "architecture_blocks" in reason

    allow, reason = mode.is_task_allowed_for_mode(
        "[MANUAL 2026-03-15] Build new feature for user project",
        mode="passive",
    )
    assert allow is True
    assert "passive_user_source" in reason

    allow, reason = mode.is_task_allowed_for_mode(
        "[AUTO_SPLIT 2026-03-15] Fix retrieval regression in context assembly",
        mode="architecture",
    )
    assert allow is True
    assert reason == "architecture_improve_existing"

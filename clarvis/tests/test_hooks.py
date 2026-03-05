"""Tests for hook registration and execution."""

import pytest
from clarvis.heartbeat.hooks import HookRegistry, HookPhase


def test_registry_register_and_run():
    """Register hooks, run them, verify results."""
    reg = HookRegistry()

    def hook_a(ctx):
        return ctx.get("x", 0) + 1

    def hook_b(ctx):
        return ctx.get("x", 0) + 2

    reg.register(HookPhase.POSTFLIGHT, "a", hook_a, priority=10)
    reg.register(HookPhase.POSTFLIGHT, "b", hook_b, priority=20)

    results = reg.run(HookPhase.POSTFLIGHT, {"x": 5})
    assert results["a"]["result"] == 6
    assert results["b"]["result"] == 7
    assert results["a"]["elapsed_s"] >= 0
    assert results["b"]["elapsed_s"] >= 0


def test_registry_priority_order():
    """Hooks execute in priority order (lower first)."""
    reg = HookRegistry()
    order = []

    def make_hook(name):
        def hook(ctx):
            order.append(name)
        return hook

    reg.register(HookPhase.POSTFLIGHT, "high", make_hook("high"), priority=90)
    reg.register(HookPhase.POSTFLIGHT, "low", make_hook("low"), priority=10)
    reg.register(HookPhase.POSTFLIGHT, "mid", make_hook("mid"), priority=50)

    reg.run(HookPhase.POSTFLIGHT, {})
    assert order == ["low", "mid", "high"]


def test_registry_error_isolation():
    """A failing hook doesn't block subsequent hooks."""
    reg = HookRegistry()

    def failing_hook(ctx):
        raise ValueError("intentional failure")

    def ok_hook(ctx):
        return "ok"

    reg.register(HookPhase.POSTFLIGHT, "fail", failing_hook, priority=10)
    reg.register(HookPhase.POSTFLIGHT, "ok", ok_hook, priority=20)

    results = reg.run(HookPhase.POSTFLIGHT, {})
    assert "error" in results["fail"]
    assert "intentional failure" in results["fail"]["error"]
    assert results["ok"]["result"] == "ok"


def test_registry_duplicate_replacement():
    """Re-registering same name replaces the hook."""
    reg = HookRegistry()

    reg.register(HookPhase.PREFLIGHT, "test", lambda ctx: "v1", priority=10)
    reg.register(HookPhase.PREFLIGHT, "test", lambda ctx: "v2", priority=10)

    names = reg.hook_names(HookPhase.PREFLIGHT)
    assert names.count("test") == 1

    results = reg.run(HookPhase.PREFLIGHT, {})
    assert results["test"]["result"] == "v2"


def test_registry_clear():
    """Clear removes all hooks."""
    reg = HookRegistry()
    reg.register(HookPhase.POSTFLIGHT, "a", lambda ctx: None, priority=10)
    reg.register(HookPhase.PREFLIGHT, "b", lambda ctx: None, priority=10)

    reg.clear(HookPhase.POSTFLIGHT)
    assert len(reg.hooks_for(HookPhase.POSTFLIGHT)) == 0
    assert len(reg.hooks_for(HookPhase.PREFLIGHT)) == 1

    reg.clear()
    assert len(reg.hooks_for(HookPhase.PREFLIGHT)) == 0


def test_registry_invalid_phase():
    """Registering to an invalid phase raises ValueError."""
    reg = HookRegistry()
    with pytest.raises(ValueError, match="Unknown phase"):
        reg.register("invalid_phase", "test", lambda ctx: None)


def test_brain_hook_registration_structure(tmp_brain):
    """Verify hook registration lists exist and are wirable."""
    assert isinstance(tmp_brain._recall_scorers, list)
    assert isinstance(tmp_brain._recall_boosters, list)
    assert isinstance(tmp_brain._recall_observers, list)
    assert isinstance(tmp_brain._optimize_hooks, list)

    # Verify registration methods work
    dummy = lambda results: None
    tmp_brain.register_recall_scorer(dummy)
    tmp_brain.register_recall_booster(dummy)
    tmp_brain.register_recall_observer(dummy)
    tmp_brain.register_optimize_hook(dummy)

    assert len(tmp_brain._recall_scorers) == 1
    assert len(tmp_brain._recall_boosters) == 1
    assert len(tmp_brain._recall_observers) == 1
    assert len(tmp_brain._optimize_hooks) == 1


def test_brain_hook_idempotent(tmp_brain):
    """register_default_hooks is idempotent (uses _hooks_registered flag)."""
    from clarvis.brain.hooks import register_default_hooks

    result1 = register_default_hooks(tmp_brain)
    result2 = register_default_hooks(tmp_brain)

    assert result2 == {"status": "already_registered"}
    assert tmp_brain._hooks_registered is True

"""Host adapter tests (OpenClaw-only)."""

from clarvis.adapters import get_adapter
import clarvis.adapters.openclaw as openclaw_mod
import pytest


def test_adapter_factory_openclaw():
    assert get_adapter("openclaw").host == "openclaw"


def test_adapter_factory_unknown_raises():
    with pytest.raises(ValueError, match="Unknown host adapter"):
        get_adapter("nosuchhost_zzz")


def test_openclaw_adapter_delegates(monkeypatch):
    monkeypatch.setattr("clarvis.brain.remember", lambda text, importance=0.8, category="clarvis-memories": "mid-1")
    monkeypatch.setattr("clarvis.brain.search", lambda query, n=5, collections=None: [{"document": "ok"}])
    monkeypatch.setattr("clarvis.context.assembly.generate_tiered_brief", lambda current_task, tier="standard": "brief")

    adapter = openclaw_mod.OpenClawAdapter()
    assert adapter.store_memory("hello").data["memory_id"] == "mid-1"
    assert adapter.search_memory("query").data["results"][0]["document"] == "ok"
    assert adapter.build_context("task").data["brief"] == "brief"

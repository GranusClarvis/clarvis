"""Host compatibility contract checks (OpenClaw-only)."""

from clarvis.compat import CONTRACTS


def test_contract_matrix_has_openclaw():
    hosts = {c.host for c in CONTRACTS}
    assert "openclaw" in hosts


def test_contract_matrix_no_dead_hosts():
    hosts = {c.host for c in CONTRACTS}
    assert "hermes" not in hosts
    assert "nanoclaw" not in hosts


def test_openclaw_contract_has_required_ops():
    oc = [c for c in CONTRACTS if c.host == "openclaw"][0]
    assert "remember" in oc.required_brain_ops
    assert "search" in oc.required_brain_ops
    assert "store_memory" in oc.required_adapter_methods
    assert "search_memory" in oc.required_adapter_methods
    assert "build_context" in oc.required_adapter_methods

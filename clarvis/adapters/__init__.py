"""Host adapters for Clarvis memory/context portability (OpenClaw, Hermes)."""

from __future__ import annotations

from clarvis.adapters.base import AdapterResult, HostAdapter


def get_adapter(host: str, **kwargs) -> HostAdapter:
    host_key = (host or "").strip().lower()
    if host_key == "openclaw":
        from clarvis.adapters.openclaw import OpenClawAdapter
        return OpenClawAdapter()
    if host_key == "hermes":
        from clarvis.adapters.hermes import HermesAdapter
        return HermesAdapter()
    raise ValueError(f"Unknown host adapter: {host}. Available: openclaw, hermes")


__all__ = [
    "AdapterResult",
    "HostAdapter",
    "get_adapter",
]

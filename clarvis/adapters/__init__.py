"""Host adapters (OpenClaw-only for now; others added when real consumers exist)."""

from __future__ import annotations

from clarvis.adapters.base import AdapterResult, HostAdapter


def get_adapter(host: str, **kwargs) -> HostAdapter:
    host_key = (host or "").strip().lower()
    if host_key == "openclaw":
        from clarvis.adapters.openclaw import OpenClawAdapter
        return OpenClawAdapter()
    raise ValueError(f"Unknown host adapter: {host}. Available: openclaw")


__all__ = [
    "AdapterResult",
    "HostAdapter",
    "get_adapter",
]

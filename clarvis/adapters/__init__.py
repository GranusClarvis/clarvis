"""Host adapters (OpenClaw-only for now; others added when real consumers exist)."""

from __future__ import annotations

from clarvis.adapters.base import AdapterResult, HostAdapter
from clarvis.adapters.openclaw import OpenClawAdapter


def get_adapter(host: str, **kwargs) -> HostAdapter:
    host_key = (host or "").strip().lower()
    if host_key == "openclaw":
        return OpenClawAdapter()
    raise ValueError(f"Unknown host adapter: {host}. Available: openclaw")


__all__ = [
    "AdapterResult",
    "HostAdapter",
    "OpenClawAdapter",
    "get_adapter",
]

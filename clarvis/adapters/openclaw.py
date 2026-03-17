"""OpenClaw host adapter reference implementation."""

from __future__ import annotations

from clarvis.adapters.base import AdapterResult, HostAdapter

try:  # Prefer extracted bridge packages when available.
    from clarvis_db import remember, search
except ImportError:  # pragma: no cover - exercised in environments without bridge installs.
    from clarvis.brain import remember, search

try:  # Prefer extracted bridge packages when available.
    from clarvis_p import generate_tiered_brief
except ImportError:  # pragma: no cover - exercised in environments without bridge installs.
    from clarvis.context.assembly import generate_tiered_brief


class OpenClawAdapter(HostAdapter):
    host = "openclaw"

    def store_memory(self, text: str, *, importance: float = 0.8, category: str = "clarvis-memories") -> AdapterResult:
        memory_id = remember(text, importance=importance, category=category)
        return AdapterResult(host=self.host, ok=True, data={"memory_id": memory_id})

    def search_memory(
        self,
        query: str,
        *,
        n: int = 5,
        collections: list[str] | None = None,
    ) -> AdapterResult:
        results = search(query, n=n, collections=collections)
        return AdapterResult(host=self.host, ok=True, data={"results": results})

    def build_context(self, task: str, *, tier: str = "standard") -> AdapterResult:
        brief = generate_tiered_brief(current_task=task, tier=tier)
        return AdapterResult(host=self.host, ok=True, data={"brief": brief, "tier": tier})

"""Hermes host adapter for Clarvis memory/context portability.

Hermes (NousResearch/hermes-agent) stores data in ~/.hermes/.
This adapter bridges Clarvis brain operations so they work identically
whether running on OpenClaw or Hermes.

Integration path:
  1. pip install -e . (Clarvis) inside Hermes venv
  2. export CLARVIS_WORKSPACE=/path/to/clarvis/workspace
  3. Clarvis brain/CLI/queue work via spine imports
  4. Hermes config.yaml controls model routing (not openclaw.json)
  5. Use `hermes` CLI (not `hermes-agent`) for chat — respects config.yaml

Known limitations:
  - hermes-agent entry point ignores CLI flags (upstream bug)
  - No Telegram/Discord gateway — Hermes is CLI/programmatic only
  - OpenClaw skills don't port to Hermes Skills Hub format
  - Cron autonomy requires manual migration from system crontab to hermes cron
"""

from __future__ import annotations

import os
from pathlib import Path

from clarvis.adapters.base import AdapterResult, HostAdapter


def detect_hermes() -> bool:
    """Return True if hermes-agent is importable or hermes CLI is available."""
    try:
        import hermes_agent  # noqa: F401
        return True
    except ImportError:
        pass
    # Check for hermes CLI on PATH
    import shutil
    return shutil.which("hermes") is not None


def hermes_config_dir() -> Path:
    """Return the Hermes config directory (~/.hermes/)."""
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


class HermesAdapter(HostAdapter):
    """Adapter for running Clarvis on NousResearch/hermes-agent.

    Brain operations delegate to clarvis.brain (same as OpenClaw adapter)
    since the brain is workspace-local and harness-independent.

    Hermes-specific behavior:
      - Config lives in ~/.hermes/config.yaml (not openclaw.json)
      - Sessions in ~/.hermes/sessions/ (SQLite, not OpenClaw format)
      - Model routing via Hermes provider config, not OpenRouter gateway
    """

    host = "hermes"

    def __init__(self) -> None:
        self._config_dir = hermes_config_dir()

    def store_memory(
        self,
        text: str,
        *,
        importance: float = 0.8,
        category: str = "clarvis-memories",
    ) -> AdapterResult:
        from clarvis.brain import remember
        memory_id = remember(text, importance=importance, category=category)
        return AdapterResult(host=self.host, ok=True, data={"memory_id": memory_id})

    def search_memory(
        self,
        query: str,
        *,
        n: int = 5,
        collections: list[str] | None = None,
    ) -> AdapterResult:
        from clarvis.brain import search
        results = search(query, n=n, collections=collections)
        return AdapterResult(host=self.host, ok=True, data={"results": results})

    def build_context(self, task: str, *, tier: str = "standard") -> AdapterResult:
        from clarvis.context.assembly import generate_tiered_brief
        brief = generate_tiered_brief(current_task=task, tier=tier)
        return AdapterResult(host=self.host, ok=True, data={"brief": brief, "tier": tier})

    def hermes_available(self) -> AdapterResult:
        """Check if Hermes is installed and minimally functional."""
        available = detect_hermes()
        config_exists = (self._config_dir / "config.yaml").exists()
        return AdapterResult(
            host=self.host,
            ok=available,
            data={
                "hermes_importable": available,
                "config_dir": str(self._config_dir),
                "config_exists": config_exists,
            },
            message="Hermes available" if available else "Hermes not found",
        )

"""Feature toggle registry — Phase 0 substrate.

Backs ``data/audit/feature_toggles.json``. Every auditable feature has an entry:

    {"name": "brain_retrieval",
     "enabled": true,
     "shadow": false,
     "notes": "...",
     "owner": "clarvis.brain",
     "last_changed": "2026-04-16T...Z"}

- ``enabled=true,  shadow=false``  → feature runs and its output is used.
- ``enabled=true,  shadow=true``   → feature runs but output is excluded from prompts
                                      (data still logged so comparison is possible).
- ``enabled=false, shadow=*``      → feature is off entirely.

Use ``is_enabled(name)`` and ``is_shadow(name)`` at call sites. Both return safe
defaults (True / False respectively) if the registry is missing — we fail-open
so absent instrumentation does not disable production features.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_WS = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TOGGLES_PATH = _WS / "data" / "audit" / "feature_toggles.json"

# Canonical registry keys recognised by the auditor.
# When adding a feature, append to this list AND to the seed in the JSON file.
DEFAULT_TOGGLES: Dict[str, Dict[str, Any]] = {
    "brain_retrieval": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.brain",
        "notes": "Vector recall from 10 collections. Core to prompt assembly.",
    },
    "wiki_retrieval": {
        "enabled": True, "shadow": True,
        "owner": "clarvis.wiki",
        "notes": "Wired into assembly.py in shadow mode (2026-04-19). Phase 5 REVISE requires shadow data before re-ruling.",
    },
    "conceptual_framework_injection": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition",
        "notes": "Keyword→framework lookups feeding the prompt builder.",
    },
    "somatic_markers": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.somatic_markers",
        "notes": "Damasio-inspired valence gating; Phase 9 candidate.",
    },
    "cognitive_workspace": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.memory.cognitive_workspace",
        "notes": "Baddeley-style active buffer. Reuse-rate KPI live.",
    },
    "phi_guided_task_selection": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.metrics.phi",
        "notes": "Task-selector Phi weighting. Subtle-feature guarded.",
    },
    "dream_engine_outputs": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.dream_engine",
        "notes": "Counterfactual dream surfacing in context.",
    },
    "episodic_memory_injection": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.memory.episodic_memory",
        "notes": "Episode recall surfaced into the context brief.",
    },
    "hebbian_boost": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.memory.hebbian_memory",
        "notes": "Recency/co-activation boost on retrieval ranks.",
    },
    "graph_bridges": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.brain.graph",
        "notes": "Cross-collection graph edges at retrieval time.",
    },
    "attention_scheduler": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.attention",
        "notes": "GWT codelet competition for task selection.",
    },
    "metacognition_check": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.metacognition",
        "notes": "Per-step quality/coherence guards.",
    },
    "workspace_broadcast": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.workspace_broadcast",
        "notes": "GWT-style state broadcast across modules.",
    },
    "thought_protocol": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition",
        "notes": "Structured pre-action reasoning traces.",
    },
    "theory_of_mind": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.theory_of_mind",
        "notes": "Operator modelling. Phase 9 candidate.",
    },
    "world_models": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.world_models",
        "notes": "Predictive models of environment state.",
    },
    "analogy_engine": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.analogy_engine",
        "notes": "Analogy lookup during reasoning.",
    },
    "self_model": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.metrics.self_model",
        "notes": "Self-capability tracking; operator-signoff required.",
    },
    "temporal_self": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.temporal_self",
        "notes": "Across-time self-model continuity.",
    },
    "intrinsic_assessment": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.metrics.phi",
        "notes": "Self-judged reasoning quality for Phi input.",
    },
    "absolute_zero_selfplay": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.cognition.absolute_zero",
        "notes": "AZR self-play. Phase 9 candidate.",
    },
    "context_compression": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.context.compressor",
        "notes": "Brief compression pipeline.",
    },
    "dycp_prune": {
        "enabled": True, "shadow": False,
        "owner": "clarvis.context.assembly",
        "notes": "DyCP context pruning.",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_if_missing(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = {
        "_schema": 1,
        "_notes": "See clarvis/audit/toggles.py DEFAULT_TOGGLES for canonical keys.",
        "_updated": _now_iso(),
        "toggles": {
            k: {**v, "last_changed": _now_iso()}
            for k, v in DEFAULT_TOGGLES.items()
        },
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2)
    os.replace(tmp, path)


def load_toggles(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the toggle registry, auto-seeding if absent. Returns the ``toggles`` submap."""
    path = path or TOGGLES_PATH
    try:
        _seed_if_missing(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return dict(raw.get("toggles") or {})
    except Exception:
        # Last resort — synthesize from defaults, all enabled.
        return {
            k: {**v, "last_changed": _now_iso()}
            for k, v in DEFAULT_TOGGLES.items()
        }


def is_enabled(name: str, default: bool = True) -> bool:
    """True if toggle allows the feature to run at all."""
    entry = load_toggles().get(name)
    if entry is None:
        return default
    return bool(entry.get("enabled", default))


def is_shadow(name: str, default: bool = False) -> bool:
    """True when the feature should run but its output must be excluded from the prompt."""
    entry = load_toggles().get(name)
    if entry is None:
        return default
    return bool(entry.get("enabled", True)) and bool(entry.get("shadow", default))


def toggle_snapshot() -> Dict[str, Dict[str, Any]]:
    """Return a deep-copied snapshot for embedding in traces."""
    return {k: dict(v) for k, v in load_toggles().items()}


def set_toggle(name: str, enabled: Optional[bool] = None, shadow: Optional[bool] = None,
               notes: Optional[str] = None) -> bool:
    """Update a single toggle. Creates the entry if missing. Returns True on success."""
    try:
        path = TOGGLES_PATH
        _seed_if_missing(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        toggles = raw.setdefault("toggles", {})
        entry = toggles.setdefault(name, {
            "enabled": True, "shadow": False, "owner": "", "notes": "",
        })
        if enabled is not None:
            entry["enabled"] = bool(enabled)
        if shadow is not None:
            entry["shadow"] = bool(shadow)
        if notes is not None:
            entry["notes"] = notes
        entry["last_changed"] = _now_iso()
        raw["_updated"] = _now_iso()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        return False

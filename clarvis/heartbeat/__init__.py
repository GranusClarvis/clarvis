"""Clarvis heartbeat — lifecycle hooks, pipeline orchestration, brain bridge."""
from .hooks import registry, HookRegistry, HookPhase  # noqa: F401
from .gate import check_gate, run_gate, load_state, save_state  # noqa: F401
from .runner import run_gate_check  # noqa: F401
from .brain_bridge import (  # noqa: F401
    brain_preflight_context,
    brain_record_outcome,
    brain_update_context,
)

# health is intentionally NOT imported here — it's invoked via `python3 -m
# clarvis.heartbeat.health`, and eager package-level import causes a runpy
# RuntimeWarning ("found in sys.modules after import of package…").
# Import directly: `from clarvis.heartbeat.health import analyze`.

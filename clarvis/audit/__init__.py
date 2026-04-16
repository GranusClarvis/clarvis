"""clarvis.audit — Phase 0 measurement substrate.

Exports:
  - start_trace / update_trace / finalize_trace: per-spawn trace lifecycle
  - current_trace_id: ambient trace id (via env var or active handle)
  - load_toggles / is_enabled / is_shadow: feature-toggle registry

See: docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md (Phase 0).
"""

from clarvis.audit.trace import (
    AuditTrace,
    new_trace_id,
    start_trace,
    update_trace,
    finalize_trace,
    load_trace,
    current_trace_id,
    set_current_trace_id,
    trace_path_for,
)
from clarvis.audit.toggles import (
    load_toggles,
    is_enabled,
    is_shadow,
    toggle_snapshot,
    DEFAULT_TOGGLES,
)

__all__ = [
    "AuditTrace",
    "new_trace_id",
    "start_trace",
    "update_trace",
    "finalize_trace",
    "load_trace",
    "current_trace_id",
    "set_current_trace_id",
    "trace_path_for",
    "load_toggles",
    "is_enabled",
    "is_shadow",
    "toggle_snapshot",
    "DEFAULT_TOGGLES",
]

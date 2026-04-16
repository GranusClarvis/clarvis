"""Audit trace writer — per-spawn structured records linking preflight→exec→postflight→outcome.

Design (Phase 0, CLARVIS_DEEP_AUDIT_PLAN_2026-04-16):
- One JSON file per trace at ``data/audit/traces/<YYYY-MM-DD>/<audit_trace_id>.json``.
- ID format: ``YYYYMMDDTHHMMSSZ-<6hex>`` — UTC-sortable, globally unique.
- Writes are best-effort (fail-open): instrumentation must never crash the caller.
- ``start_trace`` records the environment, ``update_trace`` deep-merges section(s),
  ``finalize_trace`` writes terminal state + outcome link.
- ``current_trace_id()`` resolves from, in order: process-local handle, env var
  ``CLARVIS_AUDIT_TRACE_ID``, or None.

Retention target: ≥ 45 days (enforced by an external sweeper, not this module).
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_WS = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRACES_ROOT = _WS / "data" / "audit" / "traces"

_TRACE_ENV = "CLARVIS_AUDIT_TRACE_ID"

# Process-local active trace id (for Python-level propagation within one process).
_active = threading.local()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_trace_id(now: Optional[datetime] = None) -> str:
    """Generate a new audit_trace_id. Format: YYYYMMDDTHHMMSSZ-<6hex>."""
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def trace_path_for(trace_id: str, root: Optional[Path] = None) -> Path:
    """Resolve the canonical file path for a trace id.

    Uses the date prefix embedded in the id for partitioning.
    """
    root = root or TRACES_ROOT
    # Date component is chars 0-7 (YYYYMMDD) → YYYY-MM-DD partition.
    try:
        y, m, d = trace_id[0:4], trace_id[4:6], trace_id[6:8]
        date_dir = f"{y}-{m}-{d}"
    except Exception:
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return root / date_dir / f"{trace_id}.json"


@dataclass
class AuditTrace:
    """In-memory shape of a trace file. Keys match the on-disk JSON."""
    audit_trace_id: str
    created_at: str
    source: str  # "heartbeat" | "spawn_claude" | "cron_autonomous" | "manual" | ...
    cron_origin: str = ""  # originating cron/shell script name if known
    task: Dict[str, Any] = field(default_factory=dict)
    queue_run_id: str = ""
    preflight: Dict[str, Any] = field(default_factory=dict)
    prompt: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    postflight: Dict[str, Any] = field(default_factory=dict)
    feature_toggles: Dict[str, Any] = field(default_factory=dict)
    toggles_shadowed: list = field(default_factory=list)
    outcome: Dict[str, Any] = field(default_factory=dict)
    outcome_link: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False, default=str)
    os.replace(tmp, path)


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow-per-key, deep-per-dict merge. Lists/scalars overwrite."""
    out = dict(base)
    for k, v in incoming.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def current_trace_id() -> Optional[str]:
    """Return the active audit_trace_id from process-local state or env."""
    tid = getattr(_active, "trace_id", None)
    if tid:
        return tid
    env = os.environ.get(_TRACE_ENV, "").strip()
    return env or None


def set_current_trace_id(trace_id: Optional[str]) -> None:
    """Install an ambient trace id for this process (and its env var)."""
    if trace_id:
        _active.trace_id = trace_id
        os.environ[_TRACE_ENV] = trace_id
    else:
        _active.trace_id = None
        os.environ.pop(_TRACE_ENV, None)


def start_trace(
    source: str,
    task: Optional[Dict[str, Any]] = None,
    cron_origin: str = "",
    queue_run_id: str = "",
    trace_id: Optional[str] = None,
    set_ambient: bool = True,
    feature_toggles: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Open a new trace file and return the trace id.

    Fail-open: on any error, returns None without raising.
    """
    try:
        tid = trace_id or new_trace_id()
        tr = AuditTrace(
            audit_trace_id=tid,
            created_at=_utcnow_iso(),
            source=source,
            cron_origin=cron_origin,
            task=task or {},
            queue_run_id=queue_run_id,
            feature_toggles=feature_toggles or {},
        )
        path = trace_path_for(tid)
        _atomic_write(path, tr.to_dict())
        if set_ambient:
            set_current_trace_id(tid)
        return tid
    except Exception:
        return None


def load_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    """Load a trace from disk. Returns None if missing / unreadable."""
    try:
        path = trace_path_for(trace_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def update_trace(trace_id: Optional[str], **sections: Any) -> bool:
    """Merge ``sections`` into the trace file. Returns True on success.

    Sections are top-level keys (preflight, prompt, execution, postflight,
    outcome_link, feature_toggles, toggles_shadowed, task, etc.). Dict values
    are deep-merged; lists/scalars overwrite.

    Silent fail-open when trace_id is None or file is missing.
    """
    if not trace_id:
        trace_id = current_trace_id()
    if not trace_id:
        return False
    try:
        path = trace_path_for(trace_id)
        if not path.exists():
            return False
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        merged = _deep_merge(payload, sections)
        # Always refresh an updated_at marker at the top level.
        merged["updated_at"] = _utcnow_iso()
        _atomic_write(path, merged)
        return True
    except Exception:
        return False


def finalize_trace(
    trace_id: Optional[str],
    outcome: str,
    exit_code: Optional[int] = None,
    duration_s: Optional[float] = None,
    outcome_link: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """Write the terminal outcome to the trace.

    ``outcome`` is a short string: success | failure | timeout | deferred | skipped.
    """
    if not trace_id:
        trace_id = current_trace_id()
    if not trace_id:
        return False
    sections: Dict[str, Any] = {
        "outcome": {
            "status": outcome,
            "finalized_at": _utcnow_iso(),
        },
    }
    if exit_code is not None:
        sections["outcome"]["exit_code"] = exit_code
    if duration_s is not None:
        sections["outcome"]["duration_s"] = round(float(duration_s), 3)
    if outcome_link:
        sections["outcome_link"] = outcome_link
    if extra:
        sections.update(extra)
    return update_trace(trace_id, **sections)

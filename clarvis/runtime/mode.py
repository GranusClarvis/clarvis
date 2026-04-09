"""Clarvis runtime mode control-plane.

Modes:
  - ge            : Glorious Evolution (full autonomy)
  - architecture  : Architecture / Maintenance (improve existing over new)
  - passive       : User-directed only (no autonomous queue fill/research)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = Path(WORKSPACE) / "data"
MODE_FILE = DATA_DIR / "runtime_mode.json"
MODE_HISTORY_FILE = DATA_DIR / "runtime_mode_history.jsonl"
QUEUE_FILE = Path(WORKSPACE) / "memory" / "evolution" / "QUEUE.md"

VALID_MODES = {"ge", "architecture", "passive"}
MODE_ALIASES = {
    "ge": "ge",
    "glorious_evolution": "ge",
    "glorious-evolution": "ge",
    "evolution": "ge",
    "autonomous": "ge",
    "architecture": "architecture",
    "maintenance": "architecture",
    "architecture_maintenance": "architecture",
    "architecture-maintenance": "architecture",
    "maint": "architecture",
    "passive": "passive",
    "user_directed": "passive",
    "user-directed": "passive",
    "user": "passive",
}

USER_SOURCES = {"MANUAL", "USER", "CLI", "TELEGRAM", "DISCORD", "CHAT", "HUMAN", "PROMPT"}
IMPROVE_EXISTING_KEYWORDS = {
    "fix", "repair", "stabilize", "validate", "benchmark", "refactor", "simplify",
    "cleanup", "optimize", "migrate", "test", "soak", "decompose", "wire", "audit",
    "hardening", "hygiene", "regression", "quality", "reliability",
}
NEW_FEATURE_KEYWORDS = {
    "new feature", "add new", "build new", "introduce", "prototype", "greenfield",
}


@dataclass
class ModeState:
    mode: str = "ge"
    previous_mode: str | None = None
    switched_at: str | None = None
    reason: str = ""
    pending_mode: str | None = None
    pending_reason: str = ""
    pending_since: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_mode(value: str | None) -> str:
    if not value:
        return "ge"
    key = str(value).strip().lower().replace(" ", "_")
    mode = MODE_ALIASES.get(key)
    if not mode:
        raise ValueError(f"Unknown mode '{value}'. Valid modes: ge, architecture, passive")
    return mode


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _append_history(entry: dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(MODE_HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_mode_state() -> ModeState:
    if not MODE_FILE.exists():
        return ModeState()
    try:
        with open(MODE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ModeState()

    mode = data.get("mode", "ge")
    try:
        mode = normalize_mode(mode)
    except ValueError:
        mode = "ge"
    return ModeState(
        mode=mode,
        previous_mode=data.get("previous_mode"),
        switched_at=data.get("switched_at"),
        reason=data.get("reason", ""),
        pending_mode=data.get("pending_mode"),
        pending_reason=data.get("pending_reason", ""),
        pending_since=data.get("pending_since"),
    )


def write_mode_state(state: ModeState) -> None:
    _ensure_data_dir()
    tmp = MODE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(asdict(state), f, indent=2)
    os.replace(tmp, MODE_FILE)


def count_active_tasks(queue_file: Path | None = None) -> int:
    qf = queue_file or QUEUE_FILE
    if not qf.exists():
        return 0
    try:
        content = qf.read_text()
    except OSError:
        return 0
    return len(re.findall(r"^- \[~\]", content, flags=re.MULTILINE))


def infer_task_source(task_text: str) -> str:
    """Infer source tag from queue task text.

    Expected pattern from queue writer:
      [SOURCE YYYY-MM-DD] task text
    """
    m = re.match(r"^\[([A-Z_]+)\s+\d{4}-\d{2}-\d{2}\]\s+", task_text.strip())
    if not m:
        return "UNKNOWN"
    return m.group(1).upper()


def _is_user_directed_source(source: str) -> bool:
    return source.upper() in USER_SOURCES


def _is_improve_existing_task(task_text: str) -> bool:
    lower = task_text.lower()
    if any(k in lower for k in NEW_FEATURE_KEYWORDS):
        return False
    return any(k in lower for k in IMPROVE_EXISTING_KEYWORDS)


def is_task_allowed_for_mode(task_text: str, mode: str | None = None) -> tuple[bool, str]:
    current = normalize_mode(mode or get_mode())
    source = infer_task_source(task_text)

    if current == "ge":
        return True, "ge_allows_all"

    if current == "passive":
        if _is_user_directed_source(source):
            return True, f"passive_user_source:{source}"
        return False, f"passive_blocks_autonomous_source:{source}"

    # architecture / maintenance
    if _is_user_directed_source(source):
        return True, f"architecture_user_source:{source}"
    if _is_improve_existing_task(task_text):
        return True, "architecture_improve_existing"
    return False, f"architecture_blocks_non_improvement_source:{source}"


def mode_policies(mode: str | None = None) -> dict[str, Any]:
    current = normalize_mode(mode or get_mode())
    # Research bursts also gated by durable research config
    research_allowed = current == "ge"
    if research_allowed:
        try:
            from clarvis.research_config import is_enabled
            research_allowed = is_enabled("research_auto_fill")
        except ImportError:
            pass
    return {
        "mode": current,
        "allow_autonomous_execution": current in {"ge", "architecture"},
        "allow_autonomous_queue_generation": current == "ge",
        "allow_research_bursts": research_allowed,
        "allow_self_surgery": current == "ge",
        "allow_user_assigned_execution": True,
        "enforce_improve_existing": current == "architecture",
        "allow_new_feature_work": current == "ge",
    }


def get_mode() -> str:
    return read_mode_state().mode


def set_mode(
    mode: str,
    reason: str = "",
    defer_if_active: bool = True,
    active_tasks: int | None = None,
    queue_file: Path | None = None,
) -> dict[str, Any]:
    target = normalize_mode(mode)
    state = read_mode_state()
    now = _utc_now()

    if active_tasks is None:
        active_tasks = count_active_tasks(queue_file)

    # If we have active tasks and defer is enabled, stage a pending switch.
    if defer_if_active and active_tasks > 0:
        state.pending_mode = target
        state.pending_reason = reason or f"scheduled with {active_tasks} active task(s)"
        state.pending_since = now
        write_mode_state(state)
        _append_history({
            "ts": now,
            "event": "mode_pending",
            "mode": state.mode,
            "pending_mode": target,
            "active_tasks": active_tasks,
            "reason": state.pending_reason,
        })
        return {
            "status": "pending",
            "mode": state.mode,
            "pending_mode": target,
            "active_tasks": active_tasks,
        }

    previous = state.mode
    state.previous_mode = previous
    state.mode = target
    state.switched_at = now
    state.reason = reason or ""
    state.pending_mode = None
    state.pending_reason = ""
    state.pending_since = None
    write_mode_state(state)
    _append_history({
        "ts": now,
        "event": "mode_switched",
        "previous_mode": previous,
        "mode": target,
        "active_tasks": active_tasks,
        "reason": state.reason,
    })
    return {
        "status": "switched",
        "previous_mode": previous,
        "mode": target,
        "active_tasks": active_tasks,
    }


def apply_pending_mode(
    active_tasks: int | None = None,
    queue_file: Path | None = None,
) -> dict[str, Any]:
    state = read_mode_state()
    if not state.pending_mode:
        return {"status": "none", "mode": state.mode}

    if active_tasks is None:
        active_tasks = count_active_tasks(queue_file)
    if active_tasks > 0:
        return {
            "status": "waiting",
            "mode": state.mode,
            "pending_mode": state.pending_mode,
            "active_tasks": active_tasks,
        }

    return set_mode(
        state.pending_mode,
        reason=state.pending_reason or "applied pending mode",
        defer_if_active=False,
        active_tasks=0,
        queue_file=queue_file,
    )


def read_mode_history(limit: int = 50) -> list[dict[str, Any]]:
    if not MODE_HISTORY_FILE.exists():
        return []
    try:
        lines = MODE_HISTORY_FILE.read_text().strip().splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for ln in lines[-limit:]:
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return events


def should_allow_auto_task_injection(task_text: str, source: str) -> tuple[bool, str]:
    """Gate queue auto-injection by current mode."""
    current = get_mode()
    source_u = (source or "unknown").upper()
    if current == "ge":
        return True, "ge_allows_auto_injection"
    if current == "passive":
        if _is_user_directed_source(source_u):
            return True, "passive_user_source"
        return False, "passive_blocks_auto_injection"
    # architecture
    if _is_user_directed_source(source_u):
        return True, "architecture_user_source"
    if _is_improve_existing_task(task_text):
        return True, "architecture_improve_existing"
    return False, "architecture_blocks_non_improvement_injection"

#!/usr/bin/env python3
"""Dashboard Event Publisher — append-only JSONL event log for the visual ops dashboard.

Provides emit_event() for Python callers and a CLI for bash callers (cron scripts).

Event types:
  task_started    — cron job or agent task begins
  task_completed  — cron job or agent task finishes
  agent_spawned   — project agent spawned a Claude session
  pr_created      — PR opened by an agent
  ci_started      — CI polling began
  ci_completed    — CI checks resolved (pass/fail/timeout)
  trust_changed   — agent trust score adjusted
  self_heal       — cron doctor or watchdog self-healed an issue
  health_check    — periodic health check result
  error           — unrecoverable error logged

Usage (Python):
    from dashboard_events import emit_event
    emit_event("task_started", task_id="morning_001", task_name="Morning planning",
               section="cron", executor="claude-opus")

Usage (CLI — for bash cron scripts):
    python3 dashboard_events.py emit task_started --task-id morning_001 \\
        --task-name "Morning planning" --section cron --executor claude-opus
    python3 dashboard_events.py tail [N]          # last N events (default 20)
    python3 dashboard_events.py stats              # event counts by type
"""

import fcntl
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

DASHBOARD_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/dashboard"
EVENTS_FILE = DASHBOARD_DIR / "events.jsonl"
MAX_EVENTS = 5000  # auto-trim when exceeded

# Valid event types
EVENT_TYPES = {
    "task_started",
    "task_completed",
    "agent_spawned",
    "pr_created",
    "ci_started",
    "ci_completed",
    "trust_changed",
    "self_heal",
    "health_check",
    "error",
}


def infer_owner(kwargs: dict) -> tuple[str, str]:
    """Infer owner_type and owner_name from event kwargs.

    Returns (owner_type, owner_name) based on available fields:
      - agent present      → ("subagent", agent_name)
      - section=cron_*     → ("cron", section_name)
      - section=project_*  → ("subagent", section_name)
      - executor present   → ("system", executor)
      - fallback           → ("system", "clarvis")
    """
    # Explicit override takes precedence
    if "owner_type" in kwargs and "owner_name" in kwargs:
        return kwargs["owner_type"], kwargs["owner_name"]

    agent = kwargs.get("agent")
    section = kwargs.get("section", "")
    executor = kwargs.get("executor", "")

    if agent:
        return "subagent", agent
    if section.startswith("cron_"):
        return "cron", section
    if section.startswith("project_"):
        return "subagent", section.replace("project_", "")
    if executor:
        return "system", executor
    return "system", "clarvis"


def emit_event(event_type: str, **kwargs) -> dict:
    """Append a structured event to the dashboard event log.

    Args:
        event_type: One of EVENT_TYPES
        **kwargs: Event-specific fields (task_id, agent, status, etc.)
            owner_type/owner_name are auto-inferred if not provided.

    Returns:
        The event dict that was written.
    """
    if event_type not in EVENT_TYPES:
        # Warn but don't crash — extensibility
        pass

    # Auto-infer owner fields if not explicitly set
    owner_type, owner_name = infer_owner(kwargs)

    event = {
        "type": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        "owner_type": owner_type,
        "owner_name": owner_name,
        **kwargs,
    }

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        line = json.dumps(event, default=str) + "\n"
        with open(EVENTS_FILE, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(line)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Never crash the caller
        pass

    # Auto-trim if too large (async-safe: read, truncate, rewrite)
    _maybe_trim()

    return event


def _maybe_trim():
    """Trim events file if it exceeds MAX_EVENTS lines."""
    try:
        if not EVENTS_FILE.exists():
            return
        size = EVENTS_FILE.stat().st_size
        # Only check if file is > ~500KB (rough heuristic for >5000 events)
        if size < 500_000:
            return
        lines = EVENTS_FILE.read_text().splitlines()
        if len(lines) > MAX_EVENTS:
            # Keep the last MAX_EVENTS * 0.8 events
            keep = int(MAX_EVENTS * 0.8)
            EVENTS_FILE.write_text("\n".join(lines[-keep:]) + "\n")
    except OSError:
        pass


def read_events(n: int = 20) -> list[dict]:
    """Read the last N events from the log."""
    if not EVENTS_FILE.exists():
        return []
    try:
        lines = EVENTS_FILE.read_text().strip().splitlines()
        events = []
        for line in lines[-n:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
    except OSError:
        return []


def event_stats() -> dict:
    """Count events by type."""
    if not EVENTS_FILE.exists():
        return {}
    counts = {}
    try:
        for line in EVENTS_FILE.read_text().strip().splitlines():
            try:
                ev = json.loads(line)
                t = ev.get("type", "unknown")
                counts[t] = counts.get(t, 0) + 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return counts


# ── CLI ──────────────────────────────────────────────────────────────────

def _cli_emit(args):
    """CLI: emit an event."""
    if len(args) < 1:
        print("Usage: dashboard_events.py emit <type> [--key value ...]", file=sys.stderr)
        sys.exit(1)

    event_type = args[0]
    kwargs = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:].replace("-", "_")
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                kwargs[key] = args[i + 1]
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            i += 1

    event = emit_event(event_type, **kwargs)
    print(json.dumps(event, indent=2))


def _cli_tail(args):
    """CLI: show last N events."""
    n = int(args[0]) if args else 20
    events = read_events(n)
    for ev in events:
        ts = ev.get("ts", "")[:19]
        etype = ev.get("type", "?")
        # Build a concise one-liner
        details = []
        for k in ("task_name", "agent", "status", "task_id", "section"):
            if k in ev:
                details.append(f"{k}={ev[k]}")
        detail_str = " ".join(details)
        print(f"{ts}  {etype:<18s}  {detail_str}")


def _cli_stats(args):
    """CLI: show event counts."""
    stats = event_stats()
    if not stats:
        print("No events recorded yet.")
        return
    total = sum(stats.values())
    for etype, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {etype:<20s}  {count:>5d}")
    print(f"  {'TOTAL':<20s}  {total:>5d}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dashboard_events.py [emit|tail|stats] ...", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "emit":
        _cli_emit(rest)
    elif cmd == "tail":
        _cli_tail(rest)
    elif cmd == "stats":
        _cli_stats(rest)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)

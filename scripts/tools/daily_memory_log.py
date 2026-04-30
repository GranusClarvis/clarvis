#!/usr/bin/env python3
"""
daily_memory_log.py — Generate daily memory log from cron digest + logs.

Creates memory/YYYY-MM-DD.md so that heartbeat_gate, clarvis_reflection,
and temporal_self can read today's activity. This replaces the M2.5 session
that previously wrote this file but stopped reliably producing it.

Usage:
    python3 daily_memory_log.py           # Generate/update today's log
    python3 daily_memory_log.py 2026-03-05  # Generate for specific date
"""

import os
import re
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
MEMORY_DIR = WORKSPACE / "memory"
DIGEST_FILE = MEMORY_DIR / "cron" / "digest.md"
DIGEST_STATE = WORKSPACE / "data" / "digest_state.json"
ALERTS_LOG = WORKSPACE / "monitoring" / "alerts.log"
AUDIT_STATE = WORKSPACE / "data" / "daily_log_audit_state.json"


def _read_digest(target_date: str) -> str:
    """Read today's digest if it matches target_date."""
    if not DIGEST_FILE.exists():
        return ""

    content = DIGEST_FILE.read_text(errors="replace")

    # Verify digest is for target date
    if target_date not in content.split("\n")[0] if content else "":
        return ""

    return content


def _tail_log(logpath: Path, n: int = 30) -> list[str]:
    """Return last n lines from a log file."""
    if not logpath.exists():
        return []
    try:
        lines = logpath.read_text(errors="replace").strip().splitlines()
        return lines[-n:]
    except OSError:
        return []


def _extract_key_events(log_lines: list[str], target_date: str) -> list[str]:
    """Extract key events from log lines for target date."""
    events = []
    for line in log_lines:
        if target_date not in line:
            continue
        # Skip noisy lines
        if any(skip in line.lower() for skip in ["debug", "trace", "===", "---"]):
            continue
        # Keep important lines
        if any(keep in line.lower() for keep in [
            "complete", "success", "fail", "error", "warn",
            "started", "result:", "phi=", "committed", "promoted",
            "brain", "task:", "priority", "assessment"
        ]):
            # Clean timestamp prefix
            cleaned = re.sub(r'^\[[\d\-T:]+\]\s*', '', line).strip()
            if cleaned and len(cleaned) > 10:
                events.append(cleaned)
    return events[:20]  # cap


def _get_brain_stats() -> str:
    """Quick brain stats (no-fail)."""
    try:
        from clarvis.brain import brain
        stats = brain.stats()
        total = stats.get("total_memories", "?")
        return f"{total} memories"
    except Exception:
        return "unavailable"


def _get_phi() -> str:
    """Read latest phi from history (no computation)."""
    phi_hist = WORKSPACE / "data" / "phi_history.json"
    try:
        data = json.loads(phi_hist.read_text())
        if data:
            latest = data[-1] if isinstance(data, list) else data
            return str(latest.get("phi", latest.get("composite", "?")))
    except Exception:
        pass
    return "?"


def _daily_log_present(date_str: str) -> bool:
    """Return True if a daily log exists for date_str (either .md or .md.gz)."""
    return (MEMORY_DIR / f"{date_str}.md").exists() or (MEMORY_DIR / f"{date_str}.md.gz").exists()


def _write_stub(date_str: str, marker: str | None = None) -> Path:
    """Write a minimal daily log stub for date_str.

    If `marker` is provided it is appended as a flagged note (used by the
    coverage audit to mark backfilled stubs).
    """
    out_path = MEMORY_DIR / f"{date_str}.md"
    phi = _get_phi()
    body = (
        f"# {date_str} — Clarvis Daily Log\n\n"
        f"**Brain**: pending | **Phi**: {phi}\n\n"
        f"_No digest entries recorded for this date._\n"
    )
    if marker:
        body += f"\n> ⚠️ {marker}\n"
    out_path.write_text(body)
    return out_path


def _append_alert(message: str) -> None:
    """Append a single line to monitoring/alerts.log (no-fail)."""
    try:
        ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with ALERTS_LOG.open("a") as fh:
            fh.write(f"[{ts}] {message}\n")
    except OSError:
        pass


def _load_audit_state() -> dict:
    try:
        return json.loads(AUDIT_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_audit_state(state: dict) -> None:
    try:
        AUDIT_STATE.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_STATE.write_text(json.dumps(state, indent=2, sort_keys=True))
    except OSError:
        pass


def audit_coverage(lookback_days: int = 7, backfill: bool = True) -> dict:
    """Scan recent UTC days for missing daily logs.

    For each closed day in the lookback window (i.e., excluding today UTC):
      - If neither `memory/<date>.md` nor `memory/<date>.md.gz` exists, this
        is a coverage gap. If `backfill` is True, write a stub flagging the
        gap so future trend review still lands somewhere.
      - On the *first* time a gap is observed for a given date (tracked via
        `data/daily_log_audit_state.json`), append an alert to
        `monitoring/alerts.log` so silent disappearance becomes detectable.

    Returns a dict: {"missing": [...], "backfilled": [...], "checked": N}.
    """
    today = datetime.now(timezone.utc).date()
    state = _load_audit_state()
    seen = set(state.get("alerted", []))

    missing: list[str] = []
    backfilled: list[str] = []
    checked = 0
    # Iterate closed days only: yesterday back through lookback
    for delta in range(1, lookback_days + 1):
        day = today - timedelta(days=delta)
        date_str = day.strftime("%Y-%m-%d")
        checked += 1
        if _daily_log_present(date_str):
            continue
        missing.append(date_str)
        if date_str not in seen:
            _append_alert(
                f"[ALERT] Daily log missing for closed UTC day {date_str} "
                f"(memory/{date_str}.md{{,.gz}} not found)"
            )
            seen.add(date_str)
        if backfill:
            _write_stub(
                date_str,
                marker=(
                    f"Coverage gap: no daily log was written on {date_str}. "
                    f"This stub was created by the coverage guard "
                    f"(daily_memory_log.py audit) so trend review remains intact."
                ),
            )
            backfilled.append(date_str)

    # Drop alerted entries that fall outside the audit window so the state
    # file stays bounded — a date that aged out of the window is no longer
    # something we'll re-check, and we don't want infinite growth.
    cutoff = today - timedelta(days=lookback_days)
    pruned = []
    for d in seen:
        try:
            if datetime.strptime(d, "%Y-%m-%d").date() >= cutoff:
                pruned.append(d)
        except ValueError:
            continue
    state["alerted"] = sorted(pruned)
    state["last_audit_utc"] = datetime.now(timezone.utc).isoformat()
    _save_audit_state(state)

    return {"missing": missing, "backfilled": backfilled, "checked": checked}


def ensure_daily_log(target_date: str | None = None, audit_lookback: int = 7) -> str:
    """Create a minimal daily log stub if the file doesn't exist yet.

    This is a fast, no-fail path — no brain/ChromaDB imports, no log parsing.
    Designed to be called from health_monitor.sh (every 15 min) so consumers
    never encounter a missing file.

    Also runs `audit_coverage` for the trailing window to catch any closed UTC
    day that silently shipped without a daily log.

    Returns the path to the file (existing or newly created).
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    out_path = MEMORY_DIR / f"{target_date}.md"

    if not out_path.exists():
        _write_stub(target_date)

    if audit_lookback > 0:
        try:
            audit_coverage(lookback_days=audit_lookback, backfill=True)
        except Exception:
            pass

    return str(out_path)


def generate_daily_log(target_date: str | None = None) -> str:
    """Generate daily memory log for the given date.

    Returns the path to the generated file.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    out_path = MEMORY_DIR / f"{target_date}.md"

    # Read digest
    digest_content = _read_digest(target_date)

    # Extract sections from digest
    sections = []
    if digest_content:
        # Parse digest sections (### emoji Source — HH:MM UTC)
        parts = re.split(r'(?=^### )', digest_content, flags=re.MULTILINE)
        for part in parts[1:]:  # skip header
            part = part.strip().rstrip("-").strip()
            if part:
                sections.append(part)

    # Collect key events from logs
    log_names = ["autonomous", "evolution", "evening", "reflection", "morning"]
    log_events = {}
    for name in log_names:
        logpath = MEMORY_DIR / "cron" / f"{name}.log"
        events = _extract_key_events(_tail_log(logpath, 80), target_date)
        if events:
            log_events[name] = events

    # Brain stats and phi
    brain_stats = _get_brain_stats()
    phi = _get_phi()

    # Build the daily log
    lines = [
        f"# {target_date} — Clarvis Daily Log\n",
    ]

    # Summary line
    lines.append(f"**Brain**: {brain_stats} | **Phi**: {phi}\n")

    # Digest sections (primary content)
    if sections:
        for section in sections:
            lines.append(section)
            lines.append("")
    else:
        lines.append("_No digest entries recorded for this date._\n")

    # Supplementary log events (only those not already in digest)
    extra_events = []
    for source, events in log_events.items():
        for ev in events:
            # Skip if already covered in digest sections
            if not any(ev[:30] in s for s in sections):
                extra_events.append(f"- **{source}**: {ev}")

    if extra_events:
        lines.append("## Log Highlights\n")
        for ev in extra_events[:15]:
            lines.append(ev)
        lines.append("")

    content = "\n".join(lines)

    # Write (create or update)
    out_path.write_text(content)
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ensure":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        path = ensure_daily_log(target)
        print(f"Daily log ensured: {path}")
    elif len(sys.argv) > 1 and sys.argv[1] == "audit":
        try:
            lookback = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        except ValueError:
            lookback = 7
        result = audit_coverage(lookback_days=lookback, backfill=True)
        print(json.dumps(result, indent=2))
        sys.exit(0 if not result["missing"] else 1)
    else:
        target = sys.argv[1] if len(sys.argv) > 1 else None
        path = generate_daily_log(target)
        print(f"Daily log written: {path}")

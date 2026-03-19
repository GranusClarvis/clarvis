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
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
MEMORY_DIR = WORKSPACE / "memory"
DIGEST_FILE = MEMORY_DIR / "cron" / "digest.md"
DIGEST_STATE = WORKSPACE / "data" / "digest_state.json"


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
        sys.path.insert(0, str(WORKSPACE / "scripts"))
        from brain import brain
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


def ensure_daily_log(target_date: str | None = None) -> str:
    """Create a minimal daily log stub if the file doesn't exist yet.

    This is a fast, no-fail path — no brain/ChromaDB imports, no log parsing.
    Designed to be called from health_monitor.sh (every 15 min) so consumers
    never encounter a missing file.

    Returns the path to the file (existing or newly created).
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    out_path = MEMORY_DIR / f"{target_date}.md"

    if out_path.exists():
        return str(out_path)

    # Create minimal stub — generate_daily_log() will enrich it later
    phi = _get_phi()
    content = (
        f"# {target_date} — Clarvis Daily Log\n\n"
        f"**Brain**: pending | **Phi**: {phi}\n\n"
        f"_No digest entries recorded for this date._\n"
    )
    out_path.write_text(content)
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
    else:
        target = sys.argv[1] if len(sys.argv) > 1 else None
        path = generate_daily_log(target)
        print(f"Daily log written: {path}")

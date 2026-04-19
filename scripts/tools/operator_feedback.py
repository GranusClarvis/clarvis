#!/usr/bin/env python3
"""
operator_feedback.py — Operator-in-the-loop feedback for audit EVS signal

Collects two kinds of feedback:
  1. Digest-level: 👍/👎 on a whole morning/evening report
  2. Per-trace: /rate <trace_id> <1-5> for individual audit traces

Persists to data/audit/operator_flags.jsonl with schema:
  {timestamp, audit_trace_id|null, digest_id|null, flag: "up"|"down"|int, note|null}

This data feeds the EVS 0.10 "operator-flagged help" weight defined in
docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md §Execution Value Score.

Usage:
    python3 operator_feedback.py digest-flag <digest_id> up|down [note]
    python3 operator_feedback.py trace-rate <trace_id> <1-5> [note]
    python3 operator_feedback.py stats
    python3 operator_feedback.py recent [N]
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
)
FLAGS_FILE = os.path.join(WORKSPACE, "data", "audit", "operator_flags.jsonl")
TRACES_DIR = os.path.join(WORKSPACE, "data", "audit", "traces")


def _ensure_dir():
    os.makedirs(os.path.dirname(FLAGS_FILE), exist_ok=True)


def _read_flags():
    """Read all flags from JSONL."""
    flags = []
    if not os.path.exists(FLAGS_FILE):
        return flags
    with open(FLAGS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    flags.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return flags


def _append_flag(entry):
    """Append a flag entry."""
    _ensure_dir()
    with open(FLAGS_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _validate_trace_id(trace_id):
    """Check if a trace_id corresponds to a real trace file."""
    # trace_id format: 20260419T010003Z-bcb2c4 → date part is 20260419
    if len(trace_id) < 15:
        return False
    date_part = trace_id[:8]
    try:
        date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    except (IndexError, ValueError):
        return False
    trace_path = os.path.join(TRACES_DIR, date_str, f"{trace_id}.json")
    return os.path.exists(trace_path)


def cmd_digest_flag(args):
    """Flag a digest: digest-flag <digest_id> up|down [note]"""
    if len(args) < 2:
        print("Usage: digest-flag <digest_id> up|down [note]")
        return 1

    digest_id = args[0]
    flag = args[1].lower()
    if flag not in ("up", "down"):
        print(f"Invalid flag '{flag}'. Must be 'up' or 'down'.")
        return 1

    note = " ".join(args[2:]).strip("\"'") if len(args) > 2 else None

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audit_trace_id": None,
        "digest_id": digest_id,
        "flag": flag,
        "note": note,
    }
    _append_flag(entry)
    emoji = "👍" if flag == "up" else "👎"
    print(f"{emoji} Digest [{digest_id}] flagged as {flag.upper()}")
    return 0


def cmd_trace_rate(args):
    """Rate a trace: trace-rate <trace_id> <1-5> [note]"""
    if len(args) < 2:
        print("Usage: trace-rate <trace_id> <1-5> [note]")
        return 1

    trace_id = args[0]
    try:
        score = int(args[1])
    except ValueError:
        print(f"Score must be an integer 1-5, got '{args[1]}'")
        return 1

    if score < 1 or score > 5:
        print(f"Score must be 1-5, got {score}")
        return 1

    note = " ".join(args[2:]).strip("\"'") if len(args) > 2 else None

    # Cross-reference: check if trace exists
    trace_exists = _validate_trace_id(trace_id)
    if not trace_exists:
        print(f"Warning: trace '{trace_id}' not found in traces dir (recording anyway)")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audit_trace_id": trace_id,
        "digest_id": None,
        "flag": score,
        "note": note,
    }
    _append_flag(entry)
    stars = "★" * score + "☆" * (5 - score)
    xref = " (cross-referenced)" if trace_exists else ""
    print(f"Rated trace [{trace_id}] {stars} ({score}/5){xref}")
    return 0


def cmd_stats(args):
    """Show feedback statistics."""
    flags = _read_flags()
    if not flags:
        print("No feedback recorded yet.")
        return 0

    digest_flags = [f for f in flags if f.get("digest_id")]
    trace_flags = [f for f in flags if f.get("audit_trace_id")]

    # Digest stats
    ups = sum(1 for f in digest_flags if f["flag"] == "up")
    downs = sum(1 for f in digest_flags if f["flag"] == "down")
    print(f"Digest feedback: {len(digest_flags)} total ({ups} 👍, {downs} 👎)")

    # Trace stats
    if trace_flags:
        scores = [f["flag"] for f in trace_flags if isinstance(f["flag"], int)]
        if scores:
            avg = sum(scores) / len(scores)
            print(f"Trace ratings: {len(trace_flags)} total (avg {avg:.1f}/5)")

    # Cross-referenced count
    xref = sum(1 for f in trace_flags if _validate_trace_id(f.get("audit_trace_id", "")))
    if xref:
        print(f"Cross-referenced with live traces: {xref}")

    # 7-day window
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [f for f in flags if f.get("timestamp", "") >= week_ago.isoformat()]
    print(f"Last 7 days: {len(recent)} flags")

    return 0


def cmd_recent(args):
    """Show recent flags."""
    n = int(args[0]) if args else 10
    flags = _read_flags()
    if not flags:
        print("No feedback recorded yet.")
        return 0

    for entry in flags[-n:]:
        ts = entry.get("timestamp", "?")[:16]
        flag = entry.get("flag", "?")
        did = entry.get("digest_id")
        tid = entry.get("audit_trace_id")
        note = entry.get("note", "")

        if did:
            target = f"digest:{did}"
            flag_str = "👍" if flag == "up" else "👎"
        elif tid:
            target = f"trace:{tid[:20]}"
            flag_str = f"{'★' * flag}{'☆' * (5 - flag)}" if isinstance(flag, int) else str(flag)
        else:
            target = "?"
            flag_str = str(flag)

        note_str = f" — {note}" if note else ""
        print(f"  {ts} {target} {flag_str}{note_str}")
    return 0


def get_recent_trace_ids(days=1, max_items=3):
    """Get recent trace IDs for embedding in reports."""
    trace_ids = []
    now = datetime.now(timezone.utc)
    for days_ago in range(days):
        date_str = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        day_dir = os.path.join(TRACES_DIR, date_str)
        if not os.path.isdir(day_dir):
            continue
        try:
            for fname in sorted(os.listdir(day_dir), reverse=True):
                if fname.endswith(".json"):
                    trace_id = fname[:-5]  # strip .json
                    trace_ids.append(trace_id)
                    if len(trace_ids) >= max_items:
                        return trace_ids
        except OSError:
            continue
    return trace_ids


def get_feedback_prompt(digest_id, trace_ids=None):
    """Return a feedback prompt block for embedding in Telegram digest reports.

    Args:
        digest_id: Identifier for this digest (e.g. "morning-2026-04-19")
        trace_ids: Optional list of recent trace IDs to show

    Returns:
        String block ready to append to a report, or empty string if nothing to show.
    """
    lines = []
    lines.append("💬 FEEDBACK")
    lines.append("-" * 20)
    lines.append(f"  👍 /digest_flag {digest_id} up")
    lines.append(f"  👎 /digest_flag {digest_id} down")

    if trace_ids:
        lines.append("")
        lines.append("  Rate recent traces (1-5):")
        for tid in trace_ids[:3]:
            lines.append(f"  /trace_rate {tid} <1-5>")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1

    cmd = sys.argv[1].lower().replace("-", "_")
    args = sys.argv[2:]

    commands = {
        "digest_flag": cmd_digest_flag,
        "trace_rate": cmd_trace_rate,
        "stats": cmd_stats,
        "recent": cmd_recent,
    }

    if cmd in commands:
        return commands[cmd](args)
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(c.replace('_', '-') for c in commands)}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

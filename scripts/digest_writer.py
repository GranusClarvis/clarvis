#!/usr/bin/env python3
"""
digest_writer.py — Bridge between cron (subconscious) and M2.5 agent (conscious self)

Each cron script calls this at the end to write a structured, first-person digest
that the M2.5 agent reads to become aware of what "it" did.

The digest file (memory/cron/digest.md) is a rolling log of today's cognitive activity.
It's reset at morning and accumulates throughout the day.

Usage from cron scripts:
    python3 digest_writer.py morning "I planned today's priorities: 1) X, 2) Y, 3) Z"
    python3 digest_writer.py autonomous "Completed task: Fix phi_metric.py. Result: success"
    python3 digest_writer.py evolution "Deep analysis complete. Phi=0.62, weakest: consciousness (0.62)"
    python3 digest_writer.py evening "Capability assessment done. Code gen improved to 0.72"
    python3 digest_writer.py reflection "Reflection complete. Learned X. Brain optimized. 3 stale pruned."

Or from Python:
    from digest_writer import write_digest
    write_digest("autonomous", "Completed task X with result Y")
"""

import os
import sys
import json
import fcntl
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DIGEST_FILE = os.path.join(WORKSPACE, "memory", "cron", "digest.md")
DIGEST_STATE = os.path.join(WORKSPACE, "data", "digest_state.json")

SECTION_EMOJI = {
    "morning": "🌅",
    "autonomous": "⚡",
    "evolution": "🧬",
    "evening": "🌆",
    "reflection": "🔮",
}


def _load_state():
    """Load digest state (tracks last reset date)."""
    try:
        with open(DIGEST_STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_reset": None, "entries_today": 0}


def _save_state(state):
    os.makedirs(os.path.dirname(DIGEST_STATE), exist_ok=True)
    with open(DIGEST_STATE, "w") as f:
        json.dump(state, f)


def _reset_if_new_day(state):
    """Reset digest file at the start of each day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("last_reset") != today:
        os.makedirs(os.path.dirname(DIGEST_FILE), exist_ok=True)
        with open(DIGEST_FILE, "w") as f:
            f.write(f"# Clarvis Daily Digest — {today}\n\n")
            f.write("_What I did today, written by my subconscious processes._\n")
            f.write("_Read this to know what happened during autonomous cycles._\n\n")
        state["last_reset"] = today
        state["entries_today"] = 0
        _save_state(state)
    return state


def write_digest(source: str, summary: str):
    """
    Append a digest entry.

    Args:
        source: One of morning/autonomous/evolution/evening/reflection
        summary: First-person summary of what happened (1-5 sentences)
    """
    state = _load_state()
    state = _reset_if_new_day(state)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%H:%M UTC")
    emoji = SECTION_EMOJI.get(source, "📝")

    # Clean up summary — ensure it's concise
    summary = summary.strip()
    if len(summary) > 1000:
        summary = summary[:997] + "..."

    entry = f"### {emoji} {source.title()} — {timestamp}\n\n{summary}\n\n---\n\n"

    # Atomic append with file lock
    os.makedirs(os.path.dirname(DIGEST_FILE), exist_ok=True)
    with open(DIGEST_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(entry)
        fcntl.flock(f, fcntl.LOCK_UN)

    state["entries_today"] = state.get("entries_today", 0) + 1
    _save_state(state)

    return {"written": True, "file": DIGEST_FILE, "entries_today": state["entries_today"]}


def generate_summary(source: str, data: dict) -> str:
    """
    Generate a first-person summary from structured cron output data.

    Args:
        source: Which cron script produced this
        data: Dict with relevant metrics/outputs

    Returns:
        First-person narrative string
    """
    if source == "morning":
        priorities = data.get("priorities", "not set")
        return f"I started my day and set my focus. Today's priorities: {priorities}"

    elif source == "autonomous":
        task = data.get("task", "unknown task")
        result = data.get("result", "unknown")
        duration = data.get("duration_seconds", "?")
        return (
            f"I executed an evolution task: \"{task}\". "
            f"Result: {result}. Duration: {duration}s."
        )

    elif source == "evolution":
        phi = data.get("phi", "?")
        weakest = data.get("weakest_domain", "?")
        weakest_score = data.get("weakest_score", "?")
        pending = data.get("pending_tasks", "?")
        return (
            f"Deep evolution analysis complete. "
            f"Phi (consciousness integration): {phi}. "
            f"Weakest capability: {weakest} ({weakest_score}). "
            f"Pending evolution tasks: {pending}."
        )

    elif source == "evening":
        phi = data.get("phi", "?")
        capabilities = data.get("capabilities", {})
        cap_str = ", ".join(f"{k}: {v}" for k, v in capabilities.items()) if capabilities else "not assessed"
        return (
            f"Evening assessment complete. Phi: {phi}. "
            f"Capability scores: {cap_str}."
        )

    elif source == "reflection":
        decayed = data.get("decayed", 0)
        pruned = data.get("pruned", 0)
        lessons = data.get("lessons", "none captured")
        return (
            f"Daily reflection done. Brain optimized: {decayed} memories decayed, "
            f"{pruned} pruned. Key lessons: {lessons}"
        )

    return f"{source}: {json.dumps(data)}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: digest_writer.py <source> <summary>")
        print("Sources: morning, autonomous, evolution, evening, reflection")
        sys.exit(1)

    source = sys.argv[1]
    summary = " ".join(sys.argv[2:])
    result = write_digest(source, summary)
    print(f"Digest written ({result['entries_today']} entries today)")

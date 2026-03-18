#!/usr/bin/env python3
"""
Public Feed Generator — sanitized status data safe for website consumption.

Reads internal metrics, goals, trajectory, and digest data. Strips secrets,
personal identity, internal paths, and operator-specific details. Outputs a
single JSON file suitable for serving on a public website.

Usage:
    python3 scripts/public_feed.py                # Write to data/public_feed.json
    python3 scripts/public_feed.py --stdout        # Print to stdout
    python3 scripts/public_feed.py --pretty        # Pretty-print to stdout

Output: data/public_feed.json (safe for public hosting)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
)
DATA_DIR = os.path.join(WORKSPACE, "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "public_feed.json")

# ── Sanitization ──────────────────────────────────────────

# Patterns to strip from any string value
_SANITIZE_PATTERNS = [
    (re.compile(r"/home/agent/\.openclaw/workspace/?"), ""),
    (re.compile(r"/home/agent/[^\s\"']+"), "<redacted-path>"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<redacted-ip>"),
    (re.compile(r"\b(sk-or-v1-[a-zA-Z0-9]+)\b"), "<redacted-key>"),
    (re.compile(r"\b\d{7,12}\b"), "<redacted-id>"),  # Telegram chat IDs etc.
    (re.compile(r"@\w+Bot\b"), "<redacted-bot>"),
    (re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "<redacted-email>"),
    # Operator identity
    (re.compile(r"\bPatrick\b", re.IGNORECASE), "<operator>"),
    (re.compile(r"\bInverse\b", re.IGNORECASE), "<operator>"),
    (re.compile(r"\bInverseAltruism\b", re.IGNORECASE), "<operator>"),
]


def sanitize_string(s):
    """Remove secrets, paths, and personal data from a string."""
    if not isinstance(s, str):
        return s
    for pattern, replacement in _SANITIZE_PATTERNS:
        s = pattern.sub(replacement, s)
    return s


def sanitize_value(v):
    """Recursively sanitize any JSON-serializable value."""
    if isinstance(v, str):
        return sanitize_string(v)
    if isinstance(v, dict):
        return {sanitize_string(k): sanitize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [sanitize_value(item) for item in v]
    return v


# ── Data Loaders ──────────────────────────────────────────

def _load_json(path, default=None):
    """Load JSON file, return default on any error."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _load_jsonl_tail(path, n=20):
    """Load last n lines of a JSONL file."""
    try:
        with open(path) as f:
            lines = f.readlines()
        entries = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries
    except Exception:
        return []


def load_performance():
    """Load latest performance metrics (safe subset)."""
    data = _load_json(os.path.join(DATA_DIR, "performance_metrics.json"))
    if not data:
        return None
    metrics = data.get("metrics", {})
    return {
        "timestamp": data.get("timestamp"),
        "pi": metrics.get("phi"),  # Performance Index
        "brain_query_avg_ms": metrics.get("brain_query_avg_ms"),
        "retrieval_hit_rate": metrics.get("retrieval_hit_rate"),
        "episode_success_rate": metrics.get("episode_success_rate"),
        "context_relevance": metrics.get("context_relevance"),
        "brain_total_memories": metrics.get("brain_total_memories"),
        "code_quality_score": metrics.get("code_quality_score"),
        "task_quality_score": metrics.get("task_quality_score"),
    }


def load_goals():
    """Load active goals (names and progress only — no subtask internals)."""
    data = _load_json(os.path.join(DATA_DIR, "goals_snapshot.json"))
    if not data:
        return None
    goals = []
    for g in data.get("active_goals", []):
        goals.append({
            "name": sanitize_string(g.get("name", "")),
            "progress": g.get("progress", 0),
        })
    # Sort by progress descending, take top 15
    goals.sort(key=lambda x: x["progress"], reverse=True)
    return {
        "generated": data.get("generated"),
        "goals": goals[:15],
    }


def load_trajectory():
    """Load recent trajectory events (sanitized)."""
    events = _load_jsonl_tail(
        os.path.join(DATA_DIR, "trajectory_eval", "history.jsonl"), n=20
    )
    if not events:
        return None
    sanitized = []
    for ev in events:
        sanitized.append({
            "timestamp": ev.get("timestamp"),
            "outcome": ev.get("outcome"),
            "score": ev.get("score"),
            "task_type": sanitize_string(ev.get("task_type", "")),
            "duration_s": ev.get("duration_s"),
        })
    return sanitized


def load_performance_history():
    """Load recent PI history for trend display."""
    entries = _load_jsonl_tail(
        os.path.join(DATA_DIR, "performance_history.jsonl"), n=30
    )
    if not entries:
        return None
    return [
        {
            "timestamp": e.get("timestamp"),
            "pi": e.get("pi") or e.get("summary", {}).get("pi"),
        }
        for e in entries
        if e.get("timestamp")
    ]


def load_queue_summary():
    """Load queue task counts (no task content — just counts per priority)."""
    queue_path = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE.md")
    try:
        with open(queue_path) as f:
            content = f.read()
    except Exception:
        return None

    # Count open and done tasks
    open_tasks = len(re.findall(r"^- \[ \]", content, re.MULTILINE))
    done_tasks = len(re.findall(r"^- \[x\]", content, re.MULTILINE))
    in_progress = len(re.findall(r"^- \[~\]", content, re.MULTILINE))

    return {
        "open": open_tasks,
        "done": done_tasks,
        "in_progress": in_progress,
    }


def load_brain_stats():
    """Load brain stats (safe subset — no collection details)."""
    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from brain import brain
        stats = brain.stats()
        return {
            "total_memories": stats.get("total_memories", 0),
            "collections": stats.get("collections", 0),
            "graph_edges": stats.get("graph_edges", 0),
        }
    except Exception:
        return None


# ── Feed Assembly ─────────────────────────────────────────

def generate_feed():
    """Assemble the full public feed."""
    t0 = time.monotonic()

    feed = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "system": "clarvis",
        "version": "1.0",
    }

    # Performance metrics
    perf = load_performance()
    if perf:
        feed["performance"] = perf

    # Goals
    goals = load_goals()
    if goals:
        feed["goals"] = goals

    # Recent trajectory (task outcomes)
    traj = load_trajectory()
    if traj:
        feed["recent_tasks"] = traj

    # PI trend
    pi_history = load_performance_history()
    if pi_history:
        feed["pi_trend"] = pi_history

    # Queue summary
    queue = load_queue_summary()
    if queue:
        feed["queue"] = queue

    # Brain stats
    brain = load_brain_stats()
    if brain:
        feed["brain"] = brain

    feed["generation_ms"] = round((time.monotonic() - t0) * 1000, 1)

    # Final sanitization pass over entire feed
    feed = sanitize_value(feed)

    return feed


# ── CLI ───────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    pretty = "--pretty" in args
    to_stdout = "--stdout" in args or pretty

    feed = generate_feed()

    if to_stdout:
        indent = 2 if pretty else None
        print(json.dumps(feed, indent=indent, default=str))
    else:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(feed, f, indent=2, default=str)
        print(f"Public feed written to {OUTPUT_PATH} "
              f"({os.path.getsize(OUTPUT_PATH)} bytes, {feed['generation_ms']}ms)")


if __name__ == "__main__":
    main()

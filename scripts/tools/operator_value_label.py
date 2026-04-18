#!/usr/bin/env python3
"""
operator_value_label.py — Operator value labeling for task outcomes

Allows the operator to label completed task outcomes as high-value, neutral,
or low-value. Labels are stored in data/audit/operator_value_labels.jsonl
and can be correlated with task-selector decisions for feedback.

Usage (from Telegram via M2.5):
    /rate <task_tag> high [optional note]
    /rate <task_tag> neutral
    /rate <task_tag> low "wasted tokens"

CLI:
    python3 operator_value_label.py rate <task_tag> high|neutral|low [note]
    python3 operator_value_label.py list              # unlabeled recent tasks
    python3 operator_value_label.py stats             # label distribution
    python3 operator_value_label.py history [N]       # last N labels (default 10)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
)
LABELS_FILE = os.path.join(WORKSPACE, "data", "audit", "operator_value_labels.jsonl")
QUEUE_ARCHIVE = os.path.join(WORKSPACE, "memory", "evolution", "QUEUE_ARCHIVE.md")
DIGEST_FILE = os.path.join(WORKSPACE, "memory", "cron", "digest.md")
DIGEST_ARCHIVE_DIR = os.path.join(WORKSPACE, "memory", "cron", "archive")

VALID_LABELS = ("high", "neutral", "low")


def _ensure_dir():
    os.makedirs(os.path.dirname(LABELS_FILE), exist_ok=True)


def _read_labels():
    """Read all existing labels."""
    labels = []
    if not os.path.exists(LABELS_FILE):
        return labels
    with open(LABELS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    labels.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return labels


def _append_label(entry):
    """Append a label entry to the JSONL file."""
    _ensure_dir()
    with open(LABELS_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _find_trace_id_for_task(task_tag):
    """Try to find an audit_trace_id for a task tag from recent traces."""
    traces_dir = os.path.join(WORKSPACE, "data", "audit", "traces")
    if not os.path.isdir(traces_dir):
        return None
    # Check last 3 days of traces
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    for days_ago in range(3):
        date_str = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        day_dir = os.path.join(traces_dir, date_str)
        if not os.path.isdir(day_dir):
            continue
        try:
            for fname in os.listdir(day_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(day_dir, fname)
                try:
                    with open(fpath) as f:
                        trace = json.load(f)
                    task_text = trace.get("task", {}).get("text", "")
                    if task_tag in task_text:
                        return trace.get("audit_trace_id")
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            continue
    return None


def _get_recent_task_tags(days=3):
    """Get task tags from recent digest archives and current digest."""
    tags = []
    seen = set()

    # Current digest
    if os.path.exists(DIGEST_FILE):
        with open(DIGEST_FILE) as f:
            content = f.read()
        for m in re.finditer(r'\[([A-Z][A-Z0-9_]{2,})\]', content):
            tag = m.group(1)
            if tag not in seen:
                seen.add(tag)
                tags.append(tag)

    # Recent archive digests
    if os.path.isdir(DIGEST_ARCHIVE_DIR):
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        for days_ago in range(1, days + 1):
            date_str = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            path = os.path.join(DIGEST_ARCHIVE_DIR, f"digest-{date_str}.md")
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                for m in re.finditer(r'\[([A-Z][A-Z0-9_]{2,})\]', content):
                    tag = m.group(1)
                    if tag not in seen:
                        seen.add(tag)
                        tags.append(tag)

    # Queue archive (completed today)
    if os.path.exists(QUEUE_ARCHIVE):
        with open(QUEUE_ARCHIVE) as f:
            for line in f:
                if re.match(r'\s*- \[x\]', line):
                    m = re.search(r'\[([A-Z][A-Z0-9_]{2,})\]', line)
                    if m:
                        tag = m.group(1)
                        if tag not in seen:
                            seen.add(tag)
                            tags.append(tag)

    return tags


def cmd_rate(args):
    """Rate a task outcome: rate <task_tag> high|neutral|low [note]"""
    if len(args) < 2:
        print("Usage: rate <task_tag> high|neutral|low [note]")
        return 1

    task_tag = args[0].strip("[]").upper()
    label = args[1].lower()

    if label not in VALID_LABELS:
        print(f"Invalid label '{label}'. Must be one of: {', '.join(VALID_LABELS)}")
        return 1

    note = " ".join(args[2:]).strip('"\'') if len(args) > 2 else None

    # Check for duplicate
    existing = _read_labels()
    for entry in existing:
        if entry.get("task_tag") == task_tag:
            print(f"Task [{task_tag}] already labeled as '{entry['label']}'. Updating.")
            break

    # Try to find audit trace
    trace_id = _find_trace_id_for_task(task_tag)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_tag": task_tag,
        "label": label,
        "audit_trace_id": trace_id,
        "note": note,
    }

    _append_label(entry)

    trace_info = f" (trace: {trace_id[:20]}...)" if trace_id else ""
    print(f"Labeled [{task_tag}] as {label.upper()}{trace_info}")
    if note:
        print(f"  Note: {note}")
    return 0


def cmd_list(args):
    """List recent tasks that haven't been labeled yet."""
    days = int(args[0]) if args else 3
    all_tags = _get_recent_task_tags(days=days)
    existing = _read_labels()
    labeled_tags = {e["task_tag"] for e in existing}

    unlabeled = [t for t in all_tags if t not in labeled_tags]

    if not unlabeled:
        print(f"All recent tasks (last {days} days) have been labeled.")
        return 0

    print(f"Unlabeled tasks (last {days} days):")
    for tag in unlabeled[:20]:
        print(f"  [ ] {tag}")
    print(f"\nRate with: /rate <TAG> high|neutral|low [note]")
    return 0


def cmd_stats(args):
    """Show label distribution statistics."""
    labels = _read_labels()
    if not labels:
        print("No labels recorded yet.")
        return 0

    # Deduplicate: keep latest label per task_tag
    by_tag = {}
    for entry in labels:
        by_tag[entry["task_tag"]] = entry

    counts = {"high": 0, "neutral": 0, "low": 0}
    for entry in by_tag.values():
        label = entry.get("label", "neutral")
        if label in counts:
            counts[label] += 1

    total = sum(counts.values())
    print(f"Operator Value Labels ({total} tasks rated):")
    for label in VALID_LABELS:
        count = counts[label]
        pct = (count / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {label:>7}: {count:3d} ({pct:5.1f}%) {bar}")

    # Recent trend (last 7 labels)
    recent = list(by_tag.values())[-7:]
    if recent:
        recent_labels = [e["label"] for e in recent]
        print(f"\n  Recent: {' → '.join(recent_labels)}")

    return 0


def cmd_history(args):
    """Show last N labels."""
    n = int(args[0]) if args else 10
    labels = _read_labels()
    if not labels:
        print("No labels recorded yet.")
        return 0

    for entry in labels[-n:]:
        ts = entry.get("timestamp", "?")[:10]
        tag = entry.get("task_tag", "?")
        label = entry.get("label", "?")
        note = entry.get("note", "")
        note_str = f" — {note}" if note else ""
        print(f"  {ts} [{tag}] {label.upper()}{note_str}")
    return 0


def get_unlabeled_summary(days=1, max_items=5):
    """Return a short summary of unlabeled tasks for embedding in reports.

    Returns a string suitable for appending to Telegram digest reports.
    """
    all_tags = _get_recent_task_tags(days=days)
    existing = _read_labels()
    labeled_tags = {e["task_tag"] for e in existing}
    unlabeled = [t for t in all_tags if t not in labeled_tags]

    if not unlabeled:
        return ""

    items = unlabeled[:max_items]
    lines = ["", "📊 RATE TODAY'S WORK", "-" * 20]
    for tag in items:
        lines.append(f"  /rate {tag} high|neutral|low")
    if len(unlabeled) > max_items:
        lines.append(f"  ...and {len(unlabeled) - max_items} more")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    commands = {
        "rate": cmd_rate,
        "list": cmd_list,
        "stats": cmd_stats,
        "history": cmd_history,
    }

    if cmd in commands:
        return commands[cmd](args)
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands)}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

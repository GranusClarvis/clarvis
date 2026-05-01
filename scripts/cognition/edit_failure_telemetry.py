#!/usr/bin/env python3
"""
Edit-tool Failure Telemetry — capture old_string mismatches.

The Claude Code `Edit` tool emits two canonical errors that show up
frequently but collapse into the catch-all `action` failure bucket:

  - "String to replace not found in file"  (old_string absent)
  - "Found N matches of the string to replace, but replace_all is false"
     (old_string non-unique)

Both indicate prompt-template friction: the agent guessed an old_string
that didn't anchor uniquely in the file, usually because we asked it to
operate on too small a window. This module makes the failure mode
visible by appending a structured row per occurrence to
`data/action_failure_modes.jsonl` and auto-emitting a P2 queue task
when the rolling 7-day count crosses a threshold.

JSONL schema:
  {ts, task_id, marker, file_path_seen}

Usage (programmatic):
    from edit_failure_telemetry import scan_and_log
    scan_and_log(task_text, task_tag, output_text)

CLI:
    python3 edit_failure_telemetry.py scan <output_file> [task_tag]
    python3 edit_failure_telemetry.py stats
    python3 edit_failure_telemetry.py check-threshold
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
))
JSONL_PATH = WORKSPACE / "data" / "action_failure_modes.jsonl"
STATE_PATH = WORKSPACE / "data" / "edit_failure_telemetry_state.json"

# Rolling-window threshold and cooldown for auto-task emission.
ROLLING_WINDOW_DAYS = 7
THRESHOLD_COUNT = 5
COOLDOWN_DAYS = 7
TELEMETRY_TASK_TAG = "EDIT_TOOL_PROMPT_TEMPLATE_RETUNE"

# Canonical Claude Code Edit-tool error markers.
# Each entry: (marker_label, compiled regex). The label is what we record
# in the JSONL so downstream analysis can split sub-modes cleanly.
_MARKERS = [
    (
        "old_string_not_found",
        re.compile(
            r"String to replace not found in file"
            r"|old_string\s+not\s+found"
            r"|<tool_use_error>[^<]*not found",
            re.IGNORECASE,
        ),
    ),
    (
        "old_string_not_unique",
        re.compile(
            r"Found\s+\d+\s+matches?\s+of\s+the\s+string\s+to\s+replace"
            r"|old_string.*not\s+unique"
            r"|matches?\s+but\s+replace_all\s+is\s+false",
            re.IGNORECASE,
        ),
    ),
]

# Heuristic file_path extractor: prefers an explicit "file_path: <path>"
# capture, falls back to the first plausible absolute or relative path
# in a small window around the error marker.
_FILE_PATH_RE = re.compile(
    r"file_path['\"]?\s*[:=]\s*['\"]?([^\s'\"<>]+)"
    r"|(?:in file|in)\s+([\w./\-]+\.[\w]{1,6})",
    re.IGNORECASE,
)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_state():
    if not STATE_PATH.exists():
        return {"last_emit_ts": None}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"last_emit_ts": None}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _extract_file_path(window_text):
    m = _FILE_PATH_RE.search(window_text or "")
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip().strip("'\",")


def _scan_text(output_text):
    """Yield (marker_label, file_path_seen) for each Edit-tool failure
    occurrence in output_text. Each regex match is a separate row, so
    multiple errors in one transcript surface as multiple rows."""
    if not output_text:
        return
    for label, regex in _MARKERS:
        for m in regex.finditer(output_text):
            start = max(0, m.start() - 200)
            end = min(len(output_text), m.end() + 200)
            window = output_text[start:end]
            yield label, _extract_file_path(window)


def append_rows(rows):
    """Append rows to the JSONL telemetry file. rows: list of dicts."""
    if not rows:
        return 0
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSONL_PATH, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    return len(rows)


def _read_rows():
    if not JSONL_PATH.exists():
        return []
    out = []
    with open(JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def rolling_window_count(days=ROLLING_WINDOW_DAYS, marker_prefix="old_string"):
    """Count rows in the trailing `days` window whose marker starts with
    `marker_prefix` (defaults to all old_string-class failures)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    for row in _read_rows():
        ts = row.get("ts", "")
        try:
            row_ts = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if row_ts < cutoff:
            continue
        marker = row.get("marker", "")
        if marker_prefix and not marker.startswith(marker_prefix):
            continue
        n += 1
    return n


def _emit_p2_task(count):
    """Emit a P2 queue task once the threshold trips. Honours a
    7-day cooldown so a sustained burst doesn't re-fire daily."""
    state = _load_state()
    last = state.get("last_emit_ts")
    if last:
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_dt < timedelta(days=COOLDOWN_DAYS):
                return False, "cooldown_active"
        except Exception:
            pass

    task_text = (
        f"**[{TELEMETRY_TASK_TAG}]** Targets weakest metric (Action Accuracy). "
        f"`Edit`-tool old_string failures crossed {count} occurrences in the "
        f"last {ROLLING_WINDOW_DAYS} days (data/action_failure_modes.jsonl). "
        f"Retune prompt templates to prefer larger context windows around the "
        f"`old_string` anchor and prefer `replace_all` when changing repeated "
        f"identifiers. Acceptance: in the next 7 days, rolling count drops "
        f"below {THRESHOLD_COUNT} or no double-fire occurs. (PROJECT:CLARVIS)"
    )

    try:
        from clarvis.queue.writer import add_task
        added = add_task(task_text, priority="P2", source="edit_failure_telemetry")
    except Exception as e:
        return False, f"add_task_failed: {e}"

    if added:
        state["last_emit_ts"] = _now_iso()
        state["last_emit_count"] = count
        _save_state(state)
        return True, "emitted"
    return False, "add_task_returned_false"


def scan_and_log(task_text, task_tag, output_text):
    """Main entry point called from heartbeat_postflight.

    Returns dict: {rows_added, threshold_count, emitted, emit_reason}
    """
    rows = []
    ts = _now_iso()
    task_id = (task_tag or "").strip() or _derive_task_id(task_text)
    for marker, file_path in _scan_text(output_text or ""):
        rows.append({
            "ts": ts,
            "task_id": task_id,
            "marker": marker,
            "file_path_seen": file_path,
        })

    rows_added = append_rows(rows)

    count = rolling_window_count()
    emitted = False
    emit_reason = "below_threshold"
    if count > THRESHOLD_COUNT:
        emitted, emit_reason = _emit_p2_task(count)

    return {
        "rows_added": rows_added,
        "threshold_count": count,
        "emitted": emitted,
        "emit_reason": emit_reason,
    }


def _derive_task_id(task_text):
    if not task_text:
        return ""
    m = re.search(r"\[([A-Z][A-Z0-9_]+)\]", task_text)
    return m.group(1) if m else ""


def stats():
    rows = _read_rows()
    cutoff = datetime.now(timezone.utc) - timedelta(days=ROLLING_WINDOW_DAYS)
    by_marker = {}
    by_task = {}
    recent = 0
    for row in rows:
        m = row.get("marker", "unknown")
        by_marker[m] = by_marker.get(m, 0) + 1
        tid = row.get("task_id", "unknown")
        by_task[tid] = by_task.get(tid, 0) + 1
        try:
            row_ts = datetime.strptime(
                row.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            if row_ts >= cutoff:
                recent += 1
        except Exception:
            pass
    state = _load_state()
    return {
        "total_rows": len(rows),
        "rolling_7d_count": recent,
        "by_marker": by_marker,
        "by_task_top5": dict(sorted(by_task.items(), key=lambda kv: -kv[1])[:5]),
        "threshold": THRESHOLD_COUNT,
        "last_emit_ts": state.get("last_emit_ts"),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "scan":
        if len(sys.argv) < 3:
            print("Usage: edit_failure_telemetry.py scan <output_file> [task_tag]",
                  file=sys.stderr)
            sys.exit(1)
        out_file = sys.argv[2]
        task_tag = sys.argv[3] if len(sys.argv) > 3 else ""
        text = ""
        if out_file == "-":
            text = sys.stdin.read()
        elif os.path.exists(out_file):
            text = open(out_file, encoding="utf-8", errors="replace").read()
        result = scan_and_log("", task_tag, text)
        print(json.dumps(result, indent=2))
    elif cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif cmd == "check-threshold":
        c = rolling_window_count()
        print(json.dumps({"rolling_7d_count": c, "threshold": THRESHOLD_COUNT,
                          "tripped": c > THRESHOLD_COUNT}, indent=2))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)

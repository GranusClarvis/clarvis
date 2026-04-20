#!/usr/bin/env python3
"""Stale-queue audit: flag pending items with no recent activity.

Used by cron_morning.sh to surface stale tasks before priority selection.
Output: one-line-per-finding to stdout (for log capture).
Exit 0 always (informational, never blocks morning planning).
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
sys.path.insert(0, _WS)

from clarvis.queue.engine import parse_queue, _load_sidecar, STUCK_RUNNING_HOURS

STALE_DAYS = {"P0": 3, "P1": 7, "P2": 14}
REPORT_FILE = os.path.join(_WS, "monitoring", "queue_stale_report.log")


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def audit() -> list[dict]:
    now = datetime.now(timezone.utc)
    tasks = parse_queue()
    sidecar = _load_sidecar()
    findings = []

    for t in tasks:
        tag = t["tag"]
        pri = t["priority"]
        state = sidecar.get(tag, {})

        last_ts = _parse_ts(state.get("last_run") or state.get("updated_at") or state.get("created_at"))
        current_state = state.get("state", "pending")

        if current_state == "running":
            if last_ts and (now - last_ts) > timedelta(hours=STUCK_RUNNING_HOURS):
                findings.append({
                    "tag": tag, "priority": pri, "kind": "stuck_running",
                    "age_hours": round((now - last_ts).total_seconds() / 3600, 1),
                })
            continue

        if current_state in ("deferred",):
            findings.append({"tag": tag, "priority": pri, "kind": "deferred",
                             "reason": state.get("failure_reason", "unknown")})
            continue

        if last_ts:
            age_days = (now - last_ts).days
            threshold = STALE_DAYS.get(pri, 14)
            if age_days >= threshold:
                findings.append({
                    "tag": tag, "priority": pri, "kind": "stale",
                    "age_days": age_days, "threshold": threshold,
                })
        else:
            created = _parse_ts(state.get("created_at"))
            if not created:
                findings.append({"tag": tag, "priority": pri, "kind": "no_sidecar"})

    return findings


def main():
    findings = audit()
    lines = []
    for f in findings:
        if f["kind"] == "stale":
            lines.append(f"STALE [{f['priority']}] {f['tag']}: {f['age_days']}d idle (threshold {f['threshold']}d)")
        elif f["kind"] == "stuck_running":
            lines.append(f"STUCK [{f['priority']}] {f['tag']}: running for {f['age_hours']}h")
        elif f["kind"] == "deferred":
            lines.append(f"DEFERRED [{f['priority']}] {f['tag']}: {f['reason']}")
        elif f["kind"] == "no_sidecar":
            lines.append(f"UNTRACKED [{f['priority']}] {f['tag']}: no sidecar entry")

    if lines:
        print(f"Queue audit: {len(findings)} finding(s)")
        for line in lines:
            print(f"  {line}")
    else:
        print("Queue audit: all items healthy")

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(REPORT_FILE, "a") as rf:
        rf.write(f"[{ts}] findings={len(findings)}\n")
        for line in lines:
            rf.write(f"  {line}\n")


if __name__ == "__main__":
    main()

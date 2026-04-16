#!/usr/bin/env python3
"""Phase 0 audit — deterministic replay of a past task's prompt.

Given an ``audit_trace_id`` written by heartbeat_preflight or spawn_claude,
reconstruct the prompt text that was (or would have been) sent to Claude Code.

Primary use:
  - Debug prompt-quality regressions.
  - A/B the current prompt-builder against a historical trace.
  - Feed the exact prior prompt to a utilization scorer (Phase 3).

Usage:
    python3 scripts/audit/replay.py prompt <trace_id>
    python3 scripts/audit/replay.py rebuild <trace_id> [--tier standard]
    python3 scripts/audit/replay.py diff <trace_id>   # historical vs. rebuilt

``prompt`` prints the stored brief verbatim (what was sent at the time).
``rebuild`` runs the current prompt-builder with the stored task text so
a reviewer can compare how today's stack would have answered the same input.
``diff`` combines both and prints a unified diff.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

_WS = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRACES_ROOT = _WS / "data" / "audit" / "traces"


def _find_trace_path(trace_id: str) -> Optional[Path]:
    if not TRACES_ROOT.exists():
        return None
    for date_dir in TRACES_ROOT.iterdir():
        if not date_dir.is_dir():
            continue
        cand = date_dir / f"{trace_id}.json"
        if cand.exists():
            return cand
    return None


def _load(trace_id: str) -> Optional[dict]:
    path = _find_trace_path(trace_id)
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _get_task_text(tr: dict) -> str:
    return (tr.get("task") or {}).get("text") or ""


def _get_historical_prompt(tr: dict) -> str:
    # Preferred: preflight saves the full context_brief under prompt.context_brief.
    p = (tr.get("prompt") or {}).get("context_brief")
    if p:
        return p
    return ""


def cmd_prompt(args) -> int:
    tr = _load(args.trace_id)
    if tr is None:
        print(f"trace not found: {args.trace_id}", file=sys.stderr)
        return 2
    txt = _get_historical_prompt(tr)
    if not txt:
        print("trace has no stored prompt/context_brief; try 'rebuild'", file=sys.stderr)
        return 3
    sys.stdout.write(txt)
    if not txt.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_rebuild(args) -> int:
    tr = _load(args.trace_id)
    if tr is None:
        print(f"trace not found: {args.trace_id}", file=sys.stderr)
        return 2
    task = _get_task_text(tr)
    if not task:
        print("trace has no task text; cannot rebuild", file=sys.stderr)
        return 3
    builder = _WS / "scripts" / "tools" / "prompt_builder.py"
    if not builder.exists():
        print(f"prompt_builder not found at {builder}", file=sys.stderr)
        return 4
    cmd = ["python3", str(builder), "context-brief", "--task", task, "--tier", args.tier]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"rebuild failed: {e}", file=sys.stderr)
        return 5
    sys.stdout.write(res.stdout)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
    return res.returncode


def cmd_diff(args) -> int:
    tr = _load(args.trace_id)
    if tr is None:
        print(f"trace not found: {args.trace_id}", file=sys.stderr)
        return 2
    historical = _get_historical_prompt(tr)
    # Build current
    task = _get_task_text(tr)
    if not task:
        print("trace has no task text; cannot rebuild", file=sys.stderr)
        return 3
    builder = _WS / "scripts" / "tools" / "prompt_builder.py"
    res = subprocess.run(
        ["python3", str(builder), "context-brief", "--task", task, "--tier", args.tier],
        capture_output=True, text=True, timeout=60,
    )
    current = res.stdout
    print(f"# Historical prompt length: {len(historical)} chars")
    print(f"# Rebuilt (current) length: {len(current)} chars")
    diff = difflib.unified_diff(
        historical.splitlines(keepends=True),
        current.splitlines(keepends=True),
        fromfile=f"historical::{args.trace_id}",
        tofile=f"current::{args.trace_id}",
        lineterm="",
    )
    sys.stdout.writelines(diff)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clarvis Phase 0 audit trace replay")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("prompt", help="Print the stored (historical) prompt")
    p1.add_argument("trace_id")
    p1.set_defaults(func=cmd_prompt)

    p2 = sub.add_parser("rebuild", help="Rebuild the prompt via today's builder")
    p2.add_argument("trace_id")
    p2.add_argument("--tier", default="standard")
    p2.set_defaults(func=cmd_rebuild)

    p3 = sub.add_parser("diff", help="Diff historical vs rebuilt")
    p3.add_argument("trace_id")
    p3.add_argument("--tier", default="standard")
    p3.set_defaults(func=cmd_diff)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

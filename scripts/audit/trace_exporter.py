#!/usr/bin/env python3
"""Phase 0 audit trace exporter — list/filter/dump traces from data/audit/traces/.

Usage:
    python3 scripts/audit/trace_exporter.py list [--days N] [--source S] [--status S] [--limit N]
    python3 scripts/audit/trace_exporter.py show <trace_id>
    python3 scripts/audit/trace_exporter.py dump [--days N] [--source S] [--status S] > traces.jsonl
    python3 scripts/audit/trace_exporter.py stats [--days N]
    python3 scripts/audit/trace_exporter.py gate [--days 7]   # pass/fail gate check

The "gate" subcommand evaluates Phase 0 PASS criterion:
  ≥ 95% of real Claude spawns in the window have a complete recoverable trace.

Exit 0 on PASS; non-zero on FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

_WS = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRACES_ROOT = _WS / "data" / "audit" / "traces"
COSTS_PATH = _WS / "data" / "costs.jsonl"


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _iter_trace_files(days: Optional[int] = None) -> Iterator[Path]:
    """Yield trace file paths, optionally limited to the last N days."""
    if not TRACES_ROOT.exists():
        return
    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for date_dir in sorted(TRACES_ROOT.iterdir()):
        if not date_dir.is_dir():
            continue
        if cutoff is not None:
            try:
                dt = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt < cutoff - timedelta(days=1):
                    continue
            except ValueError:
                continue
        for p in sorted(date_dir.glob("*.json")):
            yield p


def _load(path: Path) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _match(tr: dict, source: Optional[str], status: Optional[str]) -> bool:
    if source and tr.get("source") != source:
        return False
    if status:
        out = (tr.get("outcome") or {}).get("status")
        if out != status:
            return False
    return True


def _is_complete(tr: dict) -> bool:
    """A trace is 'complete' when it has a finalized outcome plus the structural
    sections expected for its source.

    heartbeat: preflight + (execution or postflight)
    spawn_claude / cron_autonomous / manual: task text + (execution or postflight)
    """
    outcome = tr.get("outcome") or {}
    if not outcome.get("status"):
        return False
    source = tr.get("source", "")
    has_exec_or_post = bool(tr.get("execution")) or bool(tr.get("postflight"))
    if source == "heartbeat":
        return bool(tr.get("preflight")) and has_exec_or_post
    task = tr.get("task") or {}
    return bool(task.get("text")) and has_exec_or_post


def cmd_list(args) -> int:
    rows = []
    for path in _iter_trace_files(args.days):
        tr = _load(path)
        if not tr or not _match(tr, args.source, args.status):
            continue
        rows.append({
            "trace_id": tr.get("audit_trace_id"),
            "created_at": tr.get("created_at"),
            "source": tr.get("source"),
            "task": ((tr.get("task") or {}).get("text") or "")[:80],
            "outcome": (tr.get("outcome") or {}).get("status", "-"),
            "duration_s": (tr.get("outcome") or {}).get("duration_s", "-"),
            "path": str(path.relative_to(_WS)),
        })
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['created_at']}  {r['source']:<14}  {r['outcome']:<10}  {r['trace_id']}  {r['task']}")
    return 0


def cmd_show(args) -> int:
    path = None
    for p in _iter_trace_files():
        if p.stem == args.trace_id:
            path = p
            break
    if path is None:
        print(f"trace not found: {args.trace_id}", file=sys.stderr)
        return 2
    tr = _load(path)
    if tr is None:
        print(f"unreadable trace: {path}", file=sys.stderr)
        return 2
    print(json.dumps(tr, indent=2))
    return 0


def cmd_dump(args) -> int:
    for path in _iter_trace_files(args.days):
        tr = _load(path)
        if not tr or not _match(tr, args.source, args.status):
            continue
        print(json.dumps(tr))
    return 0


def cmd_stats(args) -> int:
    total = 0
    by_source: dict = {}
    by_outcome: dict = {}
    complete = 0
    for path in _iter_trace_files(args.days):
        tr = _load(path)
        if not tr:
            continue
        total += 1
        src = tr.get("source", "?")
        out = (tr.get("outcome") or {}).get("status", "open")
        by_source[src] = by_source.get(src, 0) + 1
        by_outcome[out] = by_outcome.get(out, 0) + 1
        if _is_complete(tr):
            complete += 1
    payload = {
        "window_days": args.days,
        "traces": total,
        "complete": complete,
        "completeness_ratio": round(complete / total, 4) if total else 0.0,
        "by_source": by_source,
        "by_outcome": by_outcome,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _count_spawns(days: int) -> int:
    """Approximate real Claude spawn count from costs.jsonl."""
    if not COSTS_PATH.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    with open(COSTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = _parse_iso(d.get("timestamp", ""))
            if ts is None or ts < cutoff:
                continue
            if d.get("model", "").startswith("claude"):
                n += 1
    return n


def cmd_gate(args) -> int:
    """Phase 0 PASS gate: ≥ 95% of real Claude spawns have complete, recoverable trace."""
    spawns = _count_spawns(args.days)
    # Count heartbeat + spawn_claude traces as attempted Claude spawns.
    total = 0
    complete = 0
    for path in _iter_trace_files(args.days):
        tr = _load(path)
        if not tr:
            continue
        if tr.get("source") not in ("heartbeat", "spawn_claude", "cron_autonomous"):
            continue
        total += 1
        if _is_complete(tr):
            complete += 1
    traced_ratio = (total / spawns) if spawns else 0.0
    completeness = (complete / total) if total else 0.0
    passed = bool(total >= 1 and completeness >= 0.95)
    verdict = "PASS" if passed else "FAIL"
    payload = {
        "window_days": args.days,
        "real_claude_spawns_via_costs": spawns,
        "audit_traces_claude_scoped": total,
        "complete_traces": complete,
        "traced_ratio_vs_costs": round(traced_ratio, 4),
        "trace_completeness_ratio": round(completeness, 4),
        "gate": verdict,
        "gate_threshold": 0.95,
        "note": "Seven full days of traces required before this gate carries weight.",
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed else 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clarvis Phase 0 audit trace exporter")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List traces, newest first")
    p_list.add_argument("--days", type=int, default=None)
    p_list.add_argument("--source", default=None)
    p_list.add_argument("--status", default=None, help="outcome status filter")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Print a single trace JSON")
    p_show.add_argument("trace_id")
    p_show.set_defaults(func=cmd_show)

    p_dump = sub.add_parser("dump", help="Dump traces as JSONL to stdout")
    p_dump.add_argument("--days", type=int, default=None)
    p_dump.add_argument("--source", default=None)
    p_dump.add_argument("--status", default=None)
    p_dump.set_defaults(func=cmd_dump)

    p_stats = sub.add_parser("stats", help="Summary counts")
    p_stats.add_argument("--days", type=int, default=7)
    p_stats.set_defaults(func=cmd_stats)

    p_gate = sub.add_parser("gate", help="Check Phase 0 PASS/FAIL gate")
    p_gate.add_argument("--days", type=int, default=7)
    p_gate.set_defaults(func=cmd_gate)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

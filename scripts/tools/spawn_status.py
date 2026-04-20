#!/usr/bin/env python3
"""Claude spawn status surface — per-task state tracking.

Usage:
    python3 scripts/tools/spawn_status.py              # summary view
    python3 scripts/tools/spawn_status.py active        # currently running spawn
    python3 scripts/tools/spawn_status.py recent [N]    # last N completed runs
    python3 scripts/tools/spawn_status.py traces [N]    # last N audit traces
    python3 scripts/tools/spawn_status.py stats         # aggregate stats
    python3 scripts/tools/spawn_status.py --json        # JSON output
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE",
                                os.path.expanduser("~/.openclaw/workspace")))
LOCK_FILE = Path("/tmp/clarvis_claude_global.lock")
QUEUE_RUNS = WORKSPACE / "data" / "queue_runs.jsonl"
COSTS_FILE = WORKSPACE / "data" / "costs.jsonl"
TRACES_DIR = WORKSPACE / "data" / "audit" / "traces"


def _get_active_spawn():
    """Check if a Claude spawn is currently running."""
    if not LOCK_FILE.exists():
        return None
    try:
        content = LOCK_FILE.read_text().strip()
        parts = content.split()
        pid = int(parts[0])
        started = parts[1] if len(parts) > 1 else "unknown"
        try:
            os.kill(pid, 0)
            alive = True
        except (ProcessLookupError, PermissionError):
            alive = False
        elapsed = ""
        if started != "unknown":
            try:
                t0 = datetime.fromisoformat(started)
                elapsed = str(timedelta(seconds=int(time.time() - t0.timestamp())))
            except Exception:
                pass
        return {"pid": pid, "started": started, "alive": alive, "elapsed": elapsed}
    except Exception:
        return None


def _load_recent_runs(n=10):
    """Load last N queue run records."""
    if not QUEUE_RUNS.exists():
        return []
    lines = QUEUE_RUNS.read_text().strip().split("\n")
    runs = []
    for line in lines[-n:]:
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def _load_recent_traces(n=5):
    """Load last N audit traces across date directories."""
    if not TRACES_DIR.exists():
        return []
    trace_files = []
    for date_dir in sorted(TRACES_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for f in sorted(date_dir.iterdir(), reverse=True):
            if f.suffix == ".json":
                trace_files.append(f)
                if len(trace_files) >= n:
                    break
        if len(trace_files) >= n:
            break
    traces = []
    for f in trace_files:
        try:
            data = json.loads(f.read_text())
            traces.append({
                "trace_id": data.get("audit_trace_id", f.stem),
                "created_at": data.get("created_at", ""),
                "source": data.get("source", ""),
                "cron_origin": data.get("cron_origin", ""),
                "task": (data.get("task", {}).get("text", ""))[:80],
                "outcome": data.get("outcome", {}).get("status", "unknown")
                           if isinstance(data.get("outcome"), dict) else
                           data.get("outcome", "unknown"),
                "confidence": data.get("preflight", {}).get("confidence_tier", ""),
                "route": data.get("preflight", {}).get("route_executor", ""),
            })
        except Exception:
            continue
    return traces


def _compute_stats():
    """Aggregate stats from queue runs."""
    runs = _load_recent_runs(n=9999)
    if not runs:
        return {"total_runs": 0}
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    recent_24h = []
    recent_7d = []
    for r in runs:
        try:
            t = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
            if t >= day_ago:
                recent_24h.append(r)
            if t >= week_ago:
                recent_7d.append(r)
        except Exception:
            continue

    def _outcome_counts(subset):
        counts = {}
        for r in subset:
            o = r.get("outcome", "unknown")
            counts[o] = counts.get(o, 0) + 1
        return counts

    def _avg_duration(subset):
        durations = [r["duration_s"] for r in subset if r.get("duration_s") is not None]
        return round(sum(durations) / len(durations)) if durations else 0

    return {
        "total_runs": len(runs),
        "last_24h": {
            "count": len(recent_24h),
            "outcomes": _outcome_counts(recent_24h),
            "avg_duration_s": _avg_duration(recent_24h),
        },
        "last_7d": {
            "count": len(recent_7d),
            "outcomes": _outcome_counts(recent_7d),
            "avg_duration_s": _avg_duration(recent_7d),
        },
    }


def _format_active(active):
    if not active:
        return "No Claude spawn currently running."
    status = "RUNNING" if active["alive"] else "STALE LOCK (process dead)"
    return (f"Active spawn: PID {active['pid']}, started {active['started']}, "
            f"elapsed {active['elapsed']}, status: {status}")


def _format_runs(runs):
    if not runs:
        return "No recent runs."
    lines = ["Recent spawns:"]
    for r in reversed(runs):
        tag = r.get("tag", "?")
        outcome = r.get("outcome", "?")
        dur = r.get("duration_s", 0)
        started = r.get("started_at", "?")[:16]
        source = r.get("source", "?")
        marker = "+" if outcome == "success" else "-" if outcome == "failure" else "~"
        lines.append(f"  [{marker}] {started} {tag:30s} {dur:>4d}s {outcome:8s} ({source})")
    return "\n".join(lines)


def _format_traces(traces):
    if not traces:
        return "No audit traces found."
    lines = ["Recent audit traces:"]
    for t in traces:
        lines.append(
            f"  {t['created_at'][:16]} {t['trace_id']:30s} "
            f"{t['route']:8s} {t['confidence']:6s} {t['task'][:50]}")
    return "\n".join(lines)


def _format_stats(stats):
    if stats["total_runs"] == 0:
        return "No run data."
    lines = [f"Total runs: {stats['total_runs']}"]
    for period in ("last_24h", "last_7d"):
        p = stats[period]
        outcomes = ", ".join(f"{k}={v}" for k, v in p["outcomes"].items())
        lines.append(f"  {period}: {p['count']} runs, avg {p['avg_duration_s']}s [{outcomes}]")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    cmd = args[0] if args else "summary"
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10

    if cmd == "active":
        data = _get_active_spawn()
        print(json.dumps(data, default=str) if as_json else _format_active(data))

    elif cmd == "recent":
        runs = _load_recent_runs(n)
        print(json.dumps(runs, default=str) if as_json else _format_runs(runs))

    elif cmd == "traces":
        traces = _load_recent_traces(n)
        print(json.dumps(traces, default=str) if as_json else _format_traces(traces))

    elif cmd == "stats":
        stats = _compute_stats()
        print(json.dumps(stats, default=str) if as_json else _format_stats(stats))

    elif cmd == "summary":
        active = _get_active_spawn()
        runs = _load_recent_runs(5)
        stats = _compute_stats()
        if as_json:
            print(json.dumps({"active": active, "recent": runs, "stats": stats}, default=str))
        else:
            print(_format_active(active))
            print()
            print(_format_runs(runs))
            print()
            print(_format_stats(stats))

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

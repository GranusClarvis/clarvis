#!/usr/bin/env python3
"""Brain hygiene automation — backfill, verify, health snapshot, alert on regressions.

Run weekly (after graph maintenance window) to catch inconsistencies, fix orphan
nodes, take health snapshots, and alert on regressions.

Usage:
    python3 brain_hygiene.py run          # Full hygiene pass
    python3 brain_hygiene.py snapshot     # Health snapshot only
    python3 brain_hygiene.py check        # Check for regressions (no fixes)
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
SNAPSHOT_DIR = WORKSPACE / "data" / "brain_hygiene"
SNAPSHOT_FILE = SNAPSHOT_DIR / "health_history.jsonl"
LATEST_FILE = SNAPSHOT_DIR / "latest_health.json"
ALERT_LOG = WORKSPACE / "monitoring" / "brain_hygiene_alerts.log"

# Regression thresholds
MIN_MEMORIES = 3000          # Alert if total drops below this
MAX_EDGE_DROP_PCT = 5.0      # Alert if edges drop >5% from previous snapshot
MAX_BACKFILL_ORPHANS = 50    # Alert if backfill finds >50 orphans

sys.path.insert(0, str(WORKSPACE / "scripts"))


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] {msg}")


def _alert(msg: str):
    """Write alert to monitoring log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        f.write(f"[{ts}] [BRAIN_HYGIENE] {msg}\n")
    _log(f"ALERT: {msg}")


def get_brain_stats() -> dict:
    """Get current brain stats via spine module."""
    try:
        from clarvis.brain import brain
        stats = brain.stats()
        health = brain.health_check()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_memories": stats.get("total_memories", 0),
            "collections": stats.get("collections", {}),
            "graph_nodes": stats.get("graph_nodes", 0),
            "graph_edges": stats.get("graph_edges", 0),
            "health_status": health.get("status", "unknown"),
        }
    except Exception as e:
        _alert(f"Failed to get brain stats: {e}")
        return {}


def run_backfill() -> int:
    """Run graph node backfill, return orphan count."""
    _log("Running graph backfill...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "brain", "backfill"],
            capture_output=True, text=True, timeout=120,
            cwd=str(WORKSPACE)
        )
        output = result.stdout + result.stderr
        _log(f"Backfill output: {output.strip()[:200]}")
        # Try to parse orphan count from output
        for line in output.split("\n"):
            if "backfill" in line.lower() and any(c.isdigit() for c in line):
                import re
                nums = re.findall(r'\d+', line)
                if nums:
                    return int(nums[0])
        return 0
    except subprocess.TimeoutExpired:
        _alert("Backfill timed out (>120s)")
        return -1
    except Exception as e:
        _alert(f"Backfill failed: {e}")
        return -1


def run_graph_verify() -> bool:
    """Run graph parity verification between JSON and SQLite."""
    _log("Running graph-verify...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "brain", "graph-verify"],
            capture_output=True, text=True, timeout=120,
            cwd=str(WORKSPACE)
        )
        output = (result.stdout + result.stderr).strip()
        _log(f"Graph-verify: {output[:200]}")
        if result.returncode != 0:
            _alert(f"Graph verification FAILED: {output[:200]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        _alert("Graph-verify timed out (>120s)")
        return False
    except Exception as e:
        _alert(f"Graph-verify failed: {e}")
        return False


def run_optimize_full() -> bool:
    """Run full optimization (decay + dedup + noise prune + archive)."""
    _log("Running optimize-full...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "brain", "optimize-full"],
            capture_output=True, text=True, timeout=300,
            cwd=str(WORKSPACE)
        )
        output = (result.stdout + result.stderr).strip()
        _log(f"Optimize-full: {output[:300]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        _alert("Optimize-full timed out (>300s)")
        return False
    except Exception as e:
        _alert(f"Optimize-full failed: {e}")
        return False


def save_snapshot(stats: dict):
    """Save health snapshot to JSONL history and latest file."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_FILE, "a") as f:
        f.write(json.dumps(stats) + "\n")
    with open(LATEST_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    _log(f"Snapshot saved: {stats.get('total_memories', '?')} memories, "
         f"{stats.get('graph_edges', '?')} edges")


def load_previous_snapshot() -> dict | None:
    """Load the previous health snapshot for regression comparison."""
    if not SNAPSHOT_FILE.exists():
        return None
    lines = SNAPSHOT_FILE.read_text().strip().split("\n")
    # Get second-to-last (the one before current run)
    if len(lines) < 2:
        return None
    try:
        return json.loads(lines[-2])
    except (json.JSONDecodeError, IndexError):
        return None


def check_regressions(current: dict, previous: dict | None) -> list[str]:
    """Check for regressions between current and previous snapshot."""
    issues = []

    total = current.get("total_memories", 0)
    if total < MIN_MEMORIES:
        issues.append(f"Memory count {total} below minimum {MIN_MEMORIES}")

    if current.get("health_status") != "healthy":
        issues.append(f"Brain health status: {current.get('health_status')}")

    if previous:
        prev_edges = previous.get("graph_edges", 0)
        curr_edges = current.get("graph_edges", 0)
        if prev_edges > 0:
            drop_pct = (prev_edges - curr_edges) / prev_edges * 100
            if drop_pct > MAX_EDGE_DROP_PCT:
                issues.append(
                    f"Graph edges dropped {drop_pct:.1f}% "
                    f"({prev_edges} → {curr_edges})"
                )

        prev_mem = previous.get("total_memories", 0)
        if prev_mem > 0 and total < prev_mem * 0.95:
            issues.append(
                f"Memory count dropped >5% ({prev_mem} → {total})"
            )

    return issues


def cmd_run():
    """Full hygiene pass: backfill, verify, optimize, snapshot, check."""
    _log("=== Brain hygiene: full pass ===")
    start = time.time()

    # 1. Backfill orphan graph nodes
    orphans = run_backfill()
    if orphans > MAX_BACKFILL_ORPHANS:
        _alert(f"High orphan count: {orphans} (threshold: {MAX_BACKFILL_ORPHANS})")

    # 2. Graph parity verification
    graph_ok = run_graph_verify()

    # 3. Full optimization (dedup + noise + archive)
    opt_ok = run_optimize_full()

    # 4. Snapshot current state
    stats = get_brain_stats()
    if stats:
        stats["hygiene_run"] = {
            "orphans_backfilled": orphans,
            "graph_verified": graph_ok,
            "optimize_ok": opt_ok,
            "duration_s": round(time.time() - start, 1),
        }
        previous = load_previous_snapshot()
        save_snapshot(stats)

        # 5. Check for regressions
        issues = check_regressions(stats, previous)
        if issues:
            for issue in issues:
                _alert(issue)
            _log(f"REGRESSIONS DETECTED: {len(issues)} issue(s)")
        else:
            _log("No regressions detected")

    elapsed = round(time.time() - start, 1)
    _log(f"=== Brain hygiene complete ({elapsed}s) ===")


def cmd_snapshot():
    """Health snapshot only (no fixes)."""
    stats = get_brain_stats()
    if stats:
        save_snapshot(stats)


def cmd_check():
    """Check for regressions without making changes."""
    stats = get_brain_stats()
    if not stats:
        print("ERROR: Could not get brain stats")
        sys.exit(1)

    previous = load_previous_snapshot()
    issues = check_regressions(stats, previous)

    if issues:
        print(f"REGRESSIONS ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print(f"OK: {stats['total_memories']} memories, "
              f"{stats['graph_edges']} edges, status={stats['health_status']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        cmd_run()
    elif cmd == "snapshot":
        cmd_snapshot()
    elif cmd == "check":
        cmd_check()
    else:
        print(__doc__)
        sys.exit(1)

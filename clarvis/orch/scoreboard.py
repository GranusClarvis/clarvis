"""Orchestration Scoreboard — aggregate snapshot of all agent benchmarks.

Canonical spine module (migrated from scripts/orchestration_scoreboard.py).

Called by cron_orchestrator.sh (Stage 4) after all per-agent benchmarks.
Reads each agent's latest benchmark and appends a summary row to
data/orchestrator/scoreboard.jsonl.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE",
                                os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))))
SCRIPTS = WORKSPACE / "scripts"
BENCHMARKS_DIR = WORKSPACE / "data" / "orchestration_benchmarks"
SCOREBOARD_DIR = WORKSPACE / "data" / "orchestrator"
SCOREBOARD_FILE = SCOREBOARD_DIR / "scoreboard.jsonl"


def _list_agent_names() -> list[str]:
    """Get all agent names from project_agent.py or by scanning directories."""
    try:
        # project_agent.py hasn't been migrated to spine yet — import from scripts
        sys.path.insert(0, str(SCRIPTS))
        try:
            from project_agent import cmd_list
            return [a["name"] if isinstance(a, dict) else a for a in cmd_list()]
        finally:
            # Clean up sys.path insertion
            if str(SCRIPTS) in sys.path:
                sys.path.remove(str(SCRIPTS))
    except Exception:
        names = []
        for root in [Path("/opt/clarvis-agents"), Path("~/agents")]:
            if root.exists():
                for d in sorted(root.iterdir()):
                    if (d / "configs" / "agent.json").exists():
                        names.append(d.name)
        return names


def _load_latest(name: str) -> dict | None:
    """Load the latest benchmark for an agent."""
    latest_file = BENCHMARKS_DIR / f"{name}_latest.json"
    if not latest_file.exists():
        return None
    try:
        return json.loads(latest_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _agent_summary(name: str, bench: dict | None) -> dict:
    """Build a scoreboard row for one agent."""
    if bench is None:
        config_file = None
        for root in [Path("/opt/clarvis-agents"), Path("~/agents")]:
            f = root / name / "configs" / "agent.json"
            if f.exists():
                config_file = f
                break

        config = json.loads(config_file.read_text()) if config_file else {}
        return {
            "agent": name,
            "status": config.get("status", "idle"),
            "total_tasks": config.get("total_tasks", 0),
            "total_successes": config.get("total_successes", 0),
            "success_rate": 0.0,
            "total_prs": 0,
            "pr_rate": 0.0,
            "avg_latency_s": 0.0,
            "est_cost_usd": 0.0,
            "composite_score": None,
            "task_summaries": 0,
        }

    pr_data = bench.get("pr_success", {})
    lat_data = bench.get("latency", {})
    cost_data = bench.get("cost", {})

    total = pr_data.get("total_tasks", 0)
    successes = pr_data.get("succeeded", 0)

    return {
        "agent": name,
        "status": "active" if total > 0 else "idle",
        "total_tasks": total,
        "total_successes": successes,
        "success_rate": round(successes / max(total, 1) * 100, 1),
        "total_prs": pr_data.get("prs_created", 0),
        "pr_rate": round(pr_data.get("prs_created", 0) / max(total, 1) * 100, 1),
        "avg_latency_s": lat_data.get("avg_seconds", 0),
        "est_cost_usd": cost_data.get("estimated_cost_usd", 0),
        "composite_score": bench.get("composite_score"),
        "task_summaries": total,
    }


def record() -> list[dict]:
    """Record a scoreboard snapshot for all agents."""
    SCOREBOARD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    names = _list_agent_names()
    rows = []

    for name in names:
        bench = _load_latest(name)
        row = _agent_summary(name, bench)
        row["date"] = ts
        rows.append(row)

    # Append all rows
    with open(SCOREBOARD_FILE, "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"Recorded {len(rows)} agents to {SCOREBOARD_FILE}")
    for row in rows:
        cs = row["composite_score"]
        cs_str = f"{cs:.3f}" if cs is not None else "n/a"
        print(f"  {row['agent']}: composite={cs_str} tasks={row['total_tasks']} prs={row['total_prs']}")

    return rows


def show() -> list[dict]:
    """Show latest scores for all agents."""
    names = _list_agent_names()
    results = []
    for name in names:
        bench = _load_latest(name)
        row = _agent_summary(name, bench)
        results.append(row)

    for row in results:
        cs = row["composite_score"]
        cs_str = f"{cs:.3f}" if cs is not None else "n/a"
        print(f"{row['agent']:20s}  composite={cs_str:>6s}  tasks={row['total_tasks']}  "
              f"success={row['success_rate']:.0f}%  prs={row['total_prs']}")

    return results


def trend(n: int = 10):
    """Show last N scoreboard snapshots."""
    if not SCOREBOARD_FILE.exists():
        print("No scoreboard data yet.")
        return

    lines = SCOREBOARD_FILE.read_text().strip().split("\n")
    recent = lines[-n:] if len(lines) > n else lines

    for line in recent:
        try:
            row = json.loads(line)
            cs = row.get("composite_score")
            cs_str = f"{cs:.3f}" if cs is not None else "n/a"
            date = row.get("date", "?")[:19]
            print(f"  {date}  {row['agent']:20s}  composite={cs_str}  tasks={row.get('total_tasks', 0)}")
        except json.JSONDecodeError:
            continue

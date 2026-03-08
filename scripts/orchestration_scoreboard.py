#!/usr/bin/env python3
"""Orchestration Scoreboard — per-agent metrics dashboard and JSONL log.

Aggregates data from:
  - agents/<name>/configs/agent.json    (task counts, PR counts, status)
  - agents/<name>/memory/summaries/     (per-task outcomes, elapsed times)
  - data/orchestration_benchmarks/      (composite scores, retrieval, latency)

Outputs:
  - data/orchestrator/scoreboard.jsonl  (append-only daily snapshots)
  - CLI summary table

Usage:
    python3 orchestration_scoreboard.py summary          # Pretty table of all agents
    python3 orchestration_scoreboard.py agent <name>     # Detail view for one agent
    python3 orchestration_scoreboard.py record           # Record snapshot to JSONL
    python3 orchestration_scoreboard.py history [days]   # Show JSONL trend
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

AGENTS_DIRS = [
    Path("/opt/clarvis-agents"),
    Path("/home/agent/agents"),
]
WORKSPACE = Path("/home/agent/.openclaw/workspace")
BENCHMARKS_DIR = WORKSPACE / "data" / "orchestration_benchmarks"
SCOREBOARD_DIR = WORKSPACE / "data" / "orchestrator"
SCOREBOARD_JSONL = SCOREBOARD_DIR / "scoreboard.jsonl"
MAX_JSONL_LINES = 1000


def discover_agents():
    """Find all agent directories across known roots."""
    agents = {}
    for root in AGENTS_DIRS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            cfg = d / "configs" / "agent.json"
            if cfg.is_file():
                agents[d.name] = d
    return agents


def load_agent_config(agent_dir):
    """Load agent.json config."""
    cfg_path = agent_dir / "configs" / "agent.json"
    if not cfg_path.is_file():
        return {}
    with open(cfg_path) as f:
        return json.load(f)


def load_summaries(agent_dir):
    """Load all task summaries for an agent."""
    summaries_dir = agent_dir / "memory" / "summaries"
    if not summaries_dir.is_dir():
        return []
    summaries = []
    for f in sorted(summaries_dir.glob("*.json")):
        try:
            with open(f) as fh:
                summaries.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return summaries


def load_benchmark(agent_name):
    """Load latest benchmark for an agent."""
    latest = BENCHMARKS_DIR / f"{agent_name}_latest.json"
    if not latest.is_file():
        return None
    try:
        with open(latest) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def compute_agent_metrics(agent_dir, agent_name):
    """Compute aggregate metrics for one agent."""
    cfg = load_agent_config(agent_dir)
    summaries = load_summaries(agent_dir)
    benchmark = load_benchmark(agent_name)

    total_tasks = cfg.get("total_tasks", 0)
    total_successes = cfg.get("total_successes", 0)
    total_prs = cfg.get("total_pr_count", 0)
    status = cfg.get("status", "unknown")

    # Derive from summaries if config counts are missing
    if total_tasks == 0 and summaries:
        total_tasks = len(summaries)
        total_successes = sum(
            1 for s in summaries
            if s.get("result", {}).get("status") == "success"
        )
        total_prs = sum(
            1 for s in summaries
            if s.get("result", {}).get("pr_url")
        )

    # Success rate
    success_rate = (total_successes / total_tasks * 100) if total_tasks > 0 else 0.0

    # PR rate (% of tasks that produced a PR)
    pr_rate = (total_prs / total_tasks * 100) if total_tasks > 0 else 0.0

    # Latency stats from summaries
    elapsed_times = []
    for s in summaries:
        e = s.get("elapsed") or s.get("result", {}).get("elapsed")
        if e and isinstance(e, (int, float)):
            elapsed_times.append(e)
    avg_latency = sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0.0

    # Composite benchmark score
    composite = None
    if benchmark:
        composite = benchmark.get("composite_score")

    # Cost estimate (rough: $0.10 per 100s of Claude Code at Opus rate)
    est_cost = sum(elapsed_times) * 0.001  # ~$0.001/s rough estimate

    return {
        "agent": agent_name,
        "status": status,
        "total_tasks": total_tasks,
        "total_successes": total_successes,
        "success_rate": round(success_rate, 1),
        "total_prs": total_prs,
        "pr_rate": round(pr_rate, 1),
        "avg_latency_s": round(avg_latency, 1),
        "est_cost_usd": round(est_cost, 2),
        "composite_score": composite,
        "task_summaries": len(summaries),
    }


def format_summary_table(metrics_list):
    """Format metrics as a pretty CLI table."""
    lines = []
    lines.append("")
    lines.append("Orchestration Scoreboard — " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    lines.append("=" * 90)
    header = f"{'Agent':<20} {'Tasks':>5} {'OK':>4} {'Rate':>6} {'PRs':>4} {'PR%':>5} {'Avg(s)':>7} {'Cost':>6} {'Score':>6}"
    lines.append(header)
    lines.append("-" * 90)

    totals = {"tasks": 0, "ok": 0, "prs": 0, "cost": 0.0}
    for m in sorted(metrics_list, key=lambda x: x["total_tasks"], reverse=True):
        composite_str = f"{m['composite_score']:.3f}" if m["composite_score"] is not None else "  —"
        line = (
            f"{m['agent']:<20} "
            f"{m['total_tasks']:>5} "
            f"{m['total_successes']:>4} "
            f"{m['success_rate']:>5.1f}% "
            f"{m['total_prs']:>4} "
            f"{m['pr_rate']:>4.1f}% "
            f"{m['avg_latency_s']:>7.1f} "
            f"${m['est_cost_usd']:>5.2f} "
            f"{composite_str:>6}"
        )
        lines.append(line)
        totals["tasks"] += m["total_tasks"]
        totals["ok"] += m["total_successes"]
        totals["prs"] += m["total_prs"]
        totals["cost"] += m["est_cost_usd"]

    lines.append("-" * 90)
    total_rate = (totals["ok"] / totals["tasks"] * 100) if totals["tasks"] > 0 else 0.0
    total_pr_rate = (totals["prs"] / totals["tasks"] * 100) if totals["tasks"] > 0 else 0.0
    lines.append(
        f"{'TOTAL':<20} "
        f"{totals['tasks']:>5} "
        f"{totals['ok']:>4} "
        f"{total_rate:>5.1f}% "
        f"{totals['prs']:>4} "
        f"{total_pr_rate:>4.1f}% "
        f"{'':>7} "
        f"${totals['cost']:>5.2f} "
        f"{'':>6}"
    )
    lines.append("")
    return "\n".join(lines)


def format_agent_detail(agent_name, agent_dir):
    """Detailed view for a single agent."""
    cfg = load_agent_config(agent_dir)
    summaries = load_summaries(agent_dir)
    benchmark = load_benchmark(agent_name)
    metrics = compute_agent_metrics(agent_dir, agent_name)

    lines = []
    lines.append(f"\n=== Agent: {agent_name} ===")
    lines.append(f"Repo:     {cfg.get('repo_url', '?')}")
    lines.append(f"Branch:   {cfg.get('branch', '?')}")
    lines.append(f"Status:   {cfg.get('status', '?')}")
    lines.append(f"Created:  {cfg.get('created', '?')}")
    lines.append("")
    lines.append(f"Tasks:    {metrics['total_tasks']} ({metrics['total_successes']} OK, {metrics['success_rate']}%)")
    lines.append(f"PRs:      {metrics['total_prs']} ({metrics['pr_rate']}% of tasks)")
    lines.append(f"Avg time: {metrics['avg_latency_s']}s")
    lines.append(f"Est cost: ${metrics['est_cost_usd']:.2f}")

    if benchmark:
        lines.append(f"\nBenchmark (composite): {benchmark.get('composite_score', '?')}")
        dims = benchmark.get("dimensions", {})
        if dims:
            for dim_name, dim_data in dims.items():
                score = dim_data.get("score", dim_data) if isinstance(dim_data, dict) else dim_data
                lines.append(f"  {dim_name}: {score}")

    if summaries:
        lines.append(f"\nTask History ({len(summaries)} tasks):")
        for s in summaries[-10:]:  # last 10
            tid = s.get("task_id", "?")
            status = s.get("result", {}).get("status", "?")
            pr = s.get("result", {}).get("pr_url", "")
            elapsed = s.get("elapsed", 0)
            task_desc = s.get("task", "")[:60]
            pr_tag = f" PR:{pr}" if pr else ""
            lines.append(f"  [{tid}] {status:<7} {elapsed:>6.1f}s{pr_tag} — {task_desc}")

    lines.append("")
    return "\n".join(lines)


def record_snapshot():
    """Record current metrics to JSONL."""
    SCOREBOARD_DIR.mkdir(parents=True, exist_ok=True)
    agents = discover_agents()
    now = datetime.now(timezone.utc).isoformat()

    entries = []
    for name, agent_dir in agents.items():
        metrics = compute_agent_metrics(agent_dir, name)
        metrics["date"] = now
        entries.append(metrics)

    # Append to JSONL
    with open(SCOREBOARD_JSONL, "a") as f:
        for entry in entries:
            f.write(json.dumps(entry, default=str) + "\n")

    # Trim to MAX_JSONL_LINES
    if SCOREBOARD_JSONL.is_file():
        with open(SCOREBOARD_JSONL) as f:
            all_lines = f.readlines()
        if len(all_lines) > MAX_JSONL_LINES:
            with open(SCOREBOARD_JSONL, "w") as f:
                f.writelines(all_lines[-MAX_JSONL_LINES:])

    print(f"Recorded {len(entries)} agent snapshots to {SCOREBOARD_JSONL}")
    return entries


def show_history(days=7):
    """Show scoreboard history from JSONL."""
    if not SCOREBOARD_JSONL.is_file():
        print("No history yet. Run 'record' first.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    with open(SCOREBOARD_JSONL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    if not entries:
        print("No history entries found.")
        return

    # Group by date (day) and agent
    from collections import defaultdict
    by_date = defaultdict(dict)
    for e in entries:
        date_str = e.get("date", "")[:10]
        agent = e.get("agent", "?")
        by_date[date_str][agent] = e

    agents_seen = sorted(set(e.get("agent", "?") for e in entries))

    print(f"\nScoreboard History (last {days} days)")
    print("=" * 70)
    header = f"{'Date':<12}" + "".join(f" {a[:12]:>14}" for a in agents_seen)
    print(header)
    print("-" * 70)

    for date_str in sorted(by_date.keys()):
        row = f"{date_str:<12}"
        for agent in agents_seen:
            if agent in by_date[date_str]:
                e = by_date[date_str][agent]
                tasks = e.get("total_tasks", 0)
                rate = e.get("success_rate", 0)
                row += f" {tasks:>3}t {rate:>5.1f}%   "
            else:
                row += "            — "
        print(row)
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestration_scoreboard.py <summary|agent|record|history>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "summary":
        agents = discover_agents()
        if not agents:
            print("No agents found.")
            sys.exit(1)
        metrics_list = []
        for name, agent_dir in agents.items():
            metrics_list.append(compute_agent_metrics(agent_dir, name))
        print(format_summary_table(metrics_list))

    elif cmd == "agent":
        if len(sys.argv) < 3:
            print("Usage: orchestration_scoreboard.py agent <name>")
            sys.exit(1)
        name = sys.argv[2]
        agents = discover_agents()
        if name not in agents:
            print(f"Agent '{name}' not found. Available: {', '.join(agents.keys())}")
            sys.exit(1)
        print(format_agent_detail(name, agents[name]))

    elif cmd == "record":
        record_snapshot()

    elif cmd == "history":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        show_history(days)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

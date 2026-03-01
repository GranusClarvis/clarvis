#!/usr/bin/env python3
"""Agent Orchestrator — parallel multi-agent execution with self-healing.

Extends agent_lifecycle.py with:
  - Parallel task execution (bounded concurrency pool)
  - Task dependency DAG (run B only after A succeeds)
  - Self-healing: auto-retry failed/timed-out agents with backoff
  - Result aggregation: collect outputs from all agents
  - Agent coordination protocol: shared message bus via filesystem

Usage:
    # Simple parallel execution (max 3 concurrent):
    python3 agent_orchestrator.py run --tasks tasks.json --concurrency 3

    # Single-shot parallel from CLI:
    python3 agent_orchestrator.py parallel "task A" "task B" "task C" --concurrency 2

    # With dependency DAG:
    python3 agent_orchestrator.py dag --dag dag.json

    # Self-healing status:
    python3 agent_orchestrator.py healing-status

    # Message bus:
    python3 agent_orchestrator.py send <agent_id> "message payload"
    python3 agent_orchestrator.py inbox <agent_id>

tasks.json format:
    [
      {"task": "implement feature X", "timeout": 900, "isolated": true},
      {"task": "write tests for Y", "timeout": 600, "isolated": true}
    ]

dag.json format:
    {
      "nodes": {
        "build": {"task": "build the project", "timeout": 600},
        "test":  {"task": "run tests", "timeout": 900, "deps": ["build"]},
        "lint":  {"task": "run linter", "timeout": 300},
        "deploy": {"task": "deploy if all pass", "timeout": 600, "deps": ["test", "lint"]}
      }
    }

Design principles:
  - Built on agent_lifecycle.py (reuses spawn/kill/status/merge)
  - File-based coordination (no external deps like Redis)
  - Bounded concurrency via threading semaphore
  - Self-healing: configurable retries with exponential backoff
  - Message bus: /data/agents/mailbox/<agent_id>.jsonl
"""

import argparse
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from agent_lifecycle import (
    cmd_spawn, cmd_status, cmd_kill, cmd_list,
    AGENTS_DIR, WORKSPACE
)

# === Configuration ===
MAX_CONCURRENCY = 3          # Default parallel agents
MAX_RETRIES = 2              # Auto-retry attempts for failed agents
RETRY_BACKOFF_BASE = 30      # Seconds before first retry
POLL_INTERVAL = 10           # Seconds between status checks
STUCK_THRESHOLD = 2400       # 40 min — consider agent stuck
MAILBOX_DIR = AGENTS_DIR / "mailbox"
ORCHESTRATOR_LOG = WORKSPACE / "memory" / "cron" / "orchestrator.log"
HEALING_STATE = AGENTS_DIR / "healing_state.json"

MAILBOX_DIR.mkdir(parents=True, exist_ok=True)


def _olog(msg: str):
    """Orchestrator-specific logging."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] [orchestrator] {msg}"
    print(line, file=sys.stderr)
    try:
        with open(ORCHESTRATOR_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


# =========================================================================
# 1. PARALLEL EXECUTION POOL
# =========================================================================

def _wait_for_agent(agent_id: str, timeout: int) -> dict:
    """Block until agent finishes or times out. Returns final status."""
    deadline = time.time() + timeout + 60  # extra grace
    while time.time() < deadline:
        info = cmd_status(agent_id)
        status = info.get("status", "unknown")
        if status in ("completed", "failed", "timeout", "killed", "dead"):
            return info
        time.sleep(POLL_INTERVAL)

    # Force kill if still running past deadline
    _olog(f"Agent {agent_id} exceeded deadline, killing")
    cmd_kill(agent_id)
    info = cmd_status(agent_id)
    info["status"] = "timeout"
    return info


def _spawn_and_wait(task_spec: dict, semaphore: threading.Semaphore) -> dict:
    """Spawn an agent (honoring concurrency semaphore) and wait for completion."""
    with semaphore:
        task = task_spec["task"]
        timeout = task_spec.get("timeout", 1200)
        isolated = task_spec.get("isolated", True)
        node_id = task_spec.get("node_id", "")

        _olog(f"Spawning: {task[:80]} (timeout={timeout}, isolated={isolated})")
        info = cmd_spawn(task, timeout=timeout, isolated=isolated)
        agent_id = info["id"]
        _olog(f"Agent {agent_id} running (pid={info['pid']})")

        result = _wait_for_agent(agent_id, timeout)
        result["node_id"] = node_id
        result["original_task"] = task

        status = result.get("status", "unknown")
        _olog(f"Agent {agent_id} finished: {status}")

        return result


def run_parallel(tasks: list[dict], concurrency: int = MAX_CONCURRENCY,
                 retries: int = MAX_RETRIES) -> dict:
    """Run multiple tasks in parallel with bounded concurrency.

    Returns:
        {
            "total": N,
            "succeeded": N,
            "failed": N,
            "results": [{"agent_id": ..., "status": ..., "task": ...}, ...]
        }
    """
    semaphore = threading.Semaphore(concurrency)
    results = []
    failed_for_retry = []

    _olog(f"Parallel run: {len(tasks)} tasks, concurrency={concurrency}")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_spawn_and_wait, spec, semaphore): spec
            for spec in tasks
        }

        for future in as_completed(futures):
            spec = futures[future]
            try:
                result = future.result()
                results.append(result)

                if result.get("status") in ("failed", "timeout"):
                    failed_for_retry.append((spec, result))
            except Exception as e:
                _olog(f"Exception for task {spec['task'][:60]}: {e}")
                results.append({
                    "task": spec["task"],
                    "status": "exception",
                    "error": str(e),
                    "node_id": spec.get("node_id", ""),
                })

    # Self-healing: retry failed tasks
    if retries > 0 and failed_for_retry:
        _olog(f"Self-healing: retrying {len(failed_for_retry)} failed tasks")
        retry_tasks = []
        for spec, result in failed_for_retry:
            retry_spec = dict(spec)
            retry_spec["_retry_attempt"] = spec.get("_retry_attempt", 0) + 1
            retry_spec["_original_agent"] = result.get("id", "")
            retry_tasks.append(retry_spec)

        # Exponential backoff
        attempt = retry_tasks[0].get("_retry_attempt", 1)
        backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
        _olog(f"Backoff: waiting {backoff}s before retry attempt {attempt}")
        time.sleep(backoff)

        retry_result = run_parallel(retry_tasks, concurrency=concurrency,
                                    retries=retries - 1)
        # Replace failed results with retry results
        for rr in retry_result["results"]:
            results.append(rr)

    succeeded = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") in ("failed", "timeout", "exception"))

    summary = {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }

    _olog(f"Parallel run complete: {succeeded}/{len(results)} succeeded")
    _record_healing(summary)
    return summary


# =========================================================================
# 2. TASK DEPENDENCY DAG
# =========================================================================

def run_dag(dag: dict, concurrency: int = MAX_CONCURRENCY,
            retries: int = MAX_RETRIES) -> dict:
    """Execute a task dependency DAG. Nodes with satisfied deps run in parallel.

    dag format:
        {"nodes": {"id": {"task": str, "timeout": int, "deps": [str], "isolated": bool}}}

    Returns results keyed by node_id.
    """
    nodes = dag["nodes"]
    completed_nodes = {}  # node_id -> result
    failed_nodes = {}
    all_node_ids = set(nodes.keys())

    _olog(f"DAG execution: {len(nodes)} nodes, concurrency={concurrency}")

    # Validate DAG (no cycles)
    if _has_cycle(nodes):
        return {"error": "Cycle detected in DAG", "nodes": list(nodes.keys())}

    while True:
        # Find runnable nodes (deps satisfied, not yet run)
        done_ids = set(completed_nodes.keys()) | set(failed_nodes.keys())
        runnable = []

        for nid, spec in nodes.items():
            if nid in done_ids:
                continue
            deps = spec.get("deps", [])
            # All deps must be in completed (not failed)
            if all(d in completed_nodes for d in deps):
                runnable.append(nid)

        if not runnable:
            # Check if we're stuck (remaining nodes have unsatisfied deps)
            remaining = all_node_ids - done_ids
            if remaining:
                _olog(f"DAG stuck: {remaining} blocked by failed deps")
                for nid in remaining:
                    failed_nodes[nid] = {
                        "node_id": nid,
                        "status": "blocked",
                        "blocked_by": [d for d in nodes[nid].get("deps", [])
                                        if d in failed_nodes],
                    }
            break

        # Build task specs for runnable nodes
        task_specs = []
        for nid in runnable:
            spec = dict(nodes[nid])
            spec["node_id"] = nid
            spec.setdefault("isolated", True)
            spec.setdefault("timeout", 1200)
            # Inject dep results into prompt context
            dep_context = _build_dep_context(nid, nodes, completed_nodes)
            if dep_context:
                spec["task"] = spec["task"] + f"\n\n--- Context from upstream tasks ---\n{dep_context}"
            task_specs.append(spec)

        # Run this batch in parallel
        batch_result = run_parallel(task_specs, concurrency=concurrency,
                                    retries=retries)

        for result in batch_result["results"]:
            nid = result.get("node_id", "")
            if result.get("status") == "completed":
                completed_nodes[nid] = result
            else:
                failed_nodes[nid] = result

    summary = {
        "total": len(nodes),
        "succeeded": len(completed_nodes),
        "failed": len(failed_nodes),
        "completed": completed_nodes,
        "failed_nodes": failed_nodes,
    }

    _olog(f"DAG complete: {len(completed_nodes)}/{len(nodes)} succeeded")
    return summary


def _has_cycle(nodes: dict) -> bool:
    """Detect cycles in the DAG using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid):
        color[nid] = GRAY
        for dep in nodes.get(nid, {}).get("deps", []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                return True
            if color[dep] == WHITE and dfs(dep):
                return True
        color[nid] = BLACK
        return False

    return any(color[nid] == WHITE and dfs(nid) for nid in nodes)


def _build_dep_context(node_id: str, nodes: dict, completed: dict) -> str:
    """Build context string from completed dependency results."""
    deps = nodes[node_id].get("deps", [])
    if not deps:
        return ""

    parts = []
    for dep_id in deps:
        result = completed.get(dep_id, {})
        tail = result.get("output_tail", "")[:500]
        status = result.get("status", "unknown")
        parts.append(f"[{dep_id}] status={status}\n{tail}")

    return "\n".join(parts)


# =========================================================================
# 3. SELF-HEALING: STUCK DETECTION & AUTO-RECOVERY
# =========================================================================

def detect_stuck_agents() -> list[dict]:
    """Find agents that appear stuck (running too long with no progress)."""
    agents = cmd_list()
    stuck = []

    for agent in agents:
        if agent.get("status") != "running":
            continue

        spawned = agent.get("spawned_at", "")
        if not spawned:
            continue

        try:
            spawn_time = datetime.fromisoformat(spawned).timestamp()
        except (ValueError, TypeError):
            continue

        age = time.time() - spawn_time
        timeout = agent.get("timeout", 1200)

        # Stuck if running beyond timeout + grace period
        if age > timeout + 120:
            agent["stuck_duration"] = int(age)
            stuck.append(agent)
            _olog(f"STUCK: {agent['id']} running {int(age)}s (timeout={timeout})")

    return stuck


def heal_stuck_agents(stuck: list[dict]) -> list[dict]:
    """Kill stuck agents and optionally retry them."""
    healed = []
    for agent in stuck:
        agent_id = agent["id"]
        _olog(f"HEALING: killing stuck agent {agent_id}")
        cmd_kill(agent_id)

        # Record healing event
        healing_event = {
            "agent_id": agent_id,
            "action": "killed_stuck",
            "stuck_duration": agent.get("stuck_duration", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": agent.get("task", "")[:100],
        }
        healed.append(healing_event)

    return healed


def _record_healing(summary: dict):
    """Persist healing state for monitoring."""
    state = {}
    if HEALING_STATE.exists():
        try:
            state = json.loads(HEALING_STATE.read_text())
        except (json.JSONDecodeError, OSError):
            state = {}

    if "runs" not in state:
        state["runs"] = []

    state["runs"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": summary["total"],
        "succeeded": summary["succeeded"],
        "failed": summary["failed"],
    })

    # Keep last 50 runs
    state["runs"] = state["runs"][-50:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    tmp = HEALING_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(HEALING_STATE)


def healing_status() -> dict:
    """Get self-healing statistics."""
    state = {}
    if HEALING_STATE.exists():
        try:
            state = json.loads(HEALING_STATE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    stuck = detect_stuck_agents()
    runs = state.get("runs", [])

    total_runs = len(runs)
    total_succeeded = sum(r.get("succeeded", 0) for r in runs)
    total_failed = sum(r.get("failed", 0) for r in runs)

    return {
        "currently_stuck": len(stuck),
        "stuck_agents": [a["id"] for a in stuck],
        "total_orchestrator_runs": total_runs,
        "cumulative_succeeded": total_succeeded,
        "cumulative_failed": total_failed,
        "success_rate": f"{total_succeeded / max(total_succeeded + total_failed, 1) * 100:.1f}%",
        "last_run": state.get("last_run", "never"),
    }


# =========================================================================
# 4. AGENT COORDINATION: MESSAGE BUS
# =========================================================================

def send_message(target_agent_id: str, payload: dict,
                 sender: str = "orchestrator") -> bool:
    """Send a message to an agent's mailbox."""
    mailbox = MAILBOX_DIR / f"{target_agent_id}.jsonl"
    message = {
        "from": sender,
        "to": target_agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    try:
        with open(mailbox, "a") as f:
            f.write(json.dumps(message) + "\n")
        return True
    except OSError as e:
        _olog(f"Failed to send to {target_agent_id}: {e}")
        return False


def read_inbox(agent_id: str, clear: bool = False) -> list[dict]:
    """Read messages from an agent's mailbox."""
    mailbox = MAILBOX_DIR / f"{agent_id}.jsonl"
    messages = []

    if mailbox.exists():
        try:
            for line in mailbox.read_text().strip().split("\n"):
                if line.strip():
                    messages.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            pass

    if clear and mailbox.exists():
        mailbox.unlink()

    return messages


def broadcast_message(payload: dict, sender: str = "orchestrator") -> int:
    """Broadcast a message to ALL running agents."""
    agents = cmd_list()
    sent = 0
    for agent in agents:
        if agent.get("status") == "running":
            if send_message(agent["id"], payload, sender=sender):
                sent += 1
    _olog(f"Broadcast to {sent} agents: {json.dumps(payload)[:100]}")
    return sent


# =========================================================================
# 5. SELF-HEALING CI/CD PIPELINE
# =========================================================================

def run_ci_pipeline(pipeline: Optional[list[dict]] = None) -> dict:
    """Run a self-healing CI/CD pipeline (build → test → lint → deploy).

    If any step fails, the pipeline:
      1. Logs the failure
      2. Spawns a fix-agent targeting the specific failure
      3. Retries the failed step

    Default pipeline if none provided:
        build → test, lint (parallel) → integration
    """
    if pipeline is None:
        pipeline = _default_ci_pipeline()

    _olog(f"CI Pipeline: {len(pipeline)} stages")
    results = []

    for i, stage in enumerate(pipeline):
        stage_name = stage.get("name", f"stage_{i}")
        _olog(f"CI Stage [{i+1}/{len(pipeline)}]: {stage_name}")

        tasks = stage.get("tasks", [])
        concurrency = stage.get("concurrency", MAX_CONCURRENCY)

        result = run_parallel(tasks, concurrency=concurrency, retries=1)

        if result["failed"] > 0 and stage.get("self_heal", True):
            # Self-healing: spawn fix agents
            _olog(f"CI Stage {stage_name} had {result['failed']} failures, attempting heal")
            fix_tasks = []
            for r in result["results"]:
                if r.get("status") in ("failed", "timeout"):
                    error_tail = r.get("output_tail", "")[:800]
                    fix_task = {
                        "task": (
                            f"Fix the CI failure in stage '{stage_name}'.\n"
                            f"Original task: {r.get('original_task', r.get('task', ''))}\n"
                            f"Error output:\n{error_tail}\n\n"
                            "Diagnose the root cause and fix it."
                        ),
                        "timeout": stage.get("heal_timeout", 900),
                        "isolated": True,
                    }
                    fix_tasks.append(fix_task)

            if fix_tasks:
                fix_result = run_parallel(fix_tasks, concurrency=1, retries=0)
                result["healing"] = fix_result

                # Retry original failed tasks
                if fix_result["succeeded"] > 0:
                    _olog("Healing succeeded, retrying original tasks")
                    failed_originals = [
                        t for t, r in zip(tasks, result["results"])
                        if r.get("status") in ("failed", "timeout")
                    ]
                    retry_result = run_parallel(failed_originals, concurrency=concurrency,
                                                retries=0)
                    result["retry_after_heal"] = retry_result

        results.append({
            "stage": stage_name,
            "result": result,
        })

        # Stop pipeline on unrecoverable failure (unless stage says continue)
        if result["failed"] > 0 and not stage.get("continue_on_failure", False):
            heal_result = result.get("retry_after_heal", {})
            if not heal_result or heal_result.get("failed", 1) > 0:
                _olog(f"CI Pipeline halted at stage {stage_name}")
                break

    succeeded_stages = sum(
        1 for r in results
        if r["result"]["failed"] == 0
        or (r["result"].get("retry_after_heal", {}).get("failed", 1) == 0)
    )

    return {
        "total_stages": len(pipeline),
        "completed_stages": len(results),
        "succeeded_stages": succeeded_stages,
        "stages": results,
    }


def _default_ci_pipeline() -> list[dict]:
    """Default CI pipeline for Clarvis: brain health → tests → lint."""
    return [
        {
            "name": "health_check",
            "tasks": [{
                "task": "Run brain health check: python3 workspace/scripts/brain.py health. Report any issues.",
                "timeout": 300,
                "isolated": False,
            }],
            "concurrency": 1,
        },
        {
            "name": "tests",
            "tasks": [
                {
                    "task": "Run clarvis-db tests: cd workspace/packages/clarvis-db && python3 -m pytest tests/ -v",
                    "timeout": 600,
                    "isolated": False,
                },
            ],
            "concurrency": 2,
            "self_heal": True,
        },
        {
            "name": "integration",
            "tasks": [{
                "task": (
                    "Integration check: import all key scripts and verify no import errors.\n"
                    "python3 -c \"\nimport sys; sys.path.insert(0, 'workspace/scripts')\n"
                    "from brain import brain\nfrom episodic_memory import EpisodicMemory\n"
                    "from attention import AttentionSystem\nprint('All imports OK')\n\""
                ),
                "timeout": 300,
                "isolated": False,
            }],
            "concurrency": 1,
            "continue_on_failure": True,
        },
    ]


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Agent Orchestrator — parallel, self-healing multi-agent execution")
    sub = parser.add_subparsers(dest="command", required=True)

    # parallel: quick CLI parallel execution
    pp = sub.add_parser("parallel", help="Run tasks in parallel from CLI")
    pp.add_argument("tasks", nargs="+", help="Task descriptions")
    pp.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY)
    pp.add_argument("--timeout", type=int, default=1200)
    pp.add_argument("--retries", type=int, default=MAX_RETRIES)
    pp.add_argument("--isolated", action="store_true", default=True)

    # run: parallel from JSON file
    rf = sub.add_parser("run", help="Run tasks from JSON file")
    rf.add_argument("--tasks", required=True, help="Path to tasks.json")
    rf.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY)
    rf.add_argument("--retries", type=int, default=MAX_RETRIES)

    # dag: dependency graph execution
    dg = sub.add_parser("dag", help="Execute task dependency DAG")
    dg.add_argument("--dag", required=True, help="Path to dag.json")
    dg.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY)

    # ci: self-healing CI pipeline
    ci = sub.add_parser("ci", help="Run self-healing CI pipeline")
    ci.add_argument("--pipeline", help="Path to pipeline.json (optional)")

    # healing-status
    sub.add_parser("healing-status", help="Show self-healing statistics")

    # detect-stuck
    sub.add_parser("detect-stuck", help="Find stuck agents")

    # heal
    sub.add_parser("heal", help="Kill stuck agents")

    # send message
    sm = sub.add_parser("send", help="Send message to agent")
    sm.add_argument("agent_id", help="Target agent ID")
    sm.add_argument("message", help="Message payload (JSON string or plain text)")

    # read inbox
    ib = sub.add_parser("inbox", help="Read agent's inbox")
    ib.add_argument("agent_id", help="Agent ID")
    ib.add_argument("--clear", action="store_true", help="Clear inbox after reading")

    # broadcast
    bc = sub.add_parser("broadcast", help="Broadcast message to all running agents")
    bc.add_argument("message", help="Message payload")

    args = parser.parse_args()

    if args.command == "parallel":
        tasks = [{"task": t, "timeout": args.timeout, "isolated": args.isolated}
                 for t in args.tasks]
        result = run_parallel(tasks, concurrency=args.concurrency, retries=args.retries)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "run":
        with open(args.tasks) as f:
            tasks = json.load(f)
        result = run_parallel(tasks, concurrency=args.concurrency, retries=args.retries)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "dag":
        with open(args.dag) as f:
            dag = json.load(f)
        result = run_dag(dag, concurrency=args.concurrency)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "ci":
        pipeline = None
        if args.pipeline:
            with open(args.pipeline) as f:
                pipeline = json.load(f)
        result = run_ci_pipeline(pipeline)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "healing-status":
        result = healing_status()
        print(json.dumps(result, indent=2))

    elif args.command == "detect-stuck":
        stuck = detect_stuck_agents()
        if stuck:
            for a in stuck:
                print(f"  STUCK: {a['id']} running {a.get('stuck_duration', '?')}s — {a.get('task', '')[:60]}")
        else:
            print("No stuck agents.")

    elif args.command == "heal":
        stuck = detect_stuck_agents()
        if stuck:
            healed = heal_stuck_agents(stuck)
            print(json.dumps(healed, indent=2))
        else:
            print("No stuck agents to heal.")

    elif args.command == "send":
        try:
            payload = json.loads(args.message)
        except json.JSONDecodeError:
            payload = {"text": args.message}
        ok = send_message(args.agent_id, payload)
        print("sent" if ok else "failed")

    elif args.command == "inbox":
        messages = read_inbox(args.agent_id, clear=args.clear)
        if messages:
            for m in messages:
                print(f"  [{m.get('timestamp', '?')}] from={m.get('from', '?')}: {json.dumps(m.get('payload', ''))}")
        else:
            print(f"No messages for {args.agent_id}")

    elif args.command == "broadcast":
        try:
            payload = json.loads(args.message)
        except json.JSONDecodeError:
            payload = {"text": args.message}
        sent = broadcast_message(payload)
        print(f"Broadcast to {sent} agents")


if __name__ == "__main__":
    main()

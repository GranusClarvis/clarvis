#!/usr/bin/env python3
"""Agent Lifecycle Manager — spawn/track/resume/kill/restore Claude Code agents.

Includes git worktree isolation per task so concurrent autonomous tasks
don't stomp on each other's file changes.

Usage:
    python3 agent_lifecycle.py spawn "task description" [--timeout 1200] [--isolated]
    python3 agent_lifecycle.py list
    python3 agent_lifecycle.py status <agent_id>
    python3 agent_lifecycle.py kill <agent_id>
    python3 agent_lifecycle.py restore <agent_id>      # re-spawn a killed/failed agent
    python3 agent_lifecycle.py cleanup                  # remove stale worktrees + dead agents
    python3 agent_lifecycle.py merge <agent_id>         # merge worktree changes back to main

Design:
    - Each agent gets a unique ID (timestamp + short hash)
    - State tracked in /tmp/clarvis_agents.json (volatile) + data/agents/ (durable)
    - Isolated agents run in .claude/worktrees/<id>/ via git worktree
    - Merge back to main via git merge (with conflict detection)
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/agent/.openclaw/workspace")
AGENTS_DIR = WORKSPACE / "data" / "agents"
AGENTS_STATE = AGENTS_DIR / "agents_state.json"
WORKTREE_ROOT = WORKSPACE / ".claude" / "worktrees"
CLAUDE_BIN = "/home/agent/.local/bin/claude"
LOGFILE = WORKSPACE / "memory" / "cron" / "agent_lifecycle.log"

# Ensure dirs exist
AGENTS_DIR.mkdir(parents=True, exist_ok=True)
WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _load_state() -> dict:
    if AGENTS_STATE.exists():
        try:
            return json.loads(AGENTS_STATE.read_text())
        except (json.JSONDecodeError, OSError):
            return {"agents": {}}
    return {"agents": {}}


def _save_state(state: dict):
    tmp = AGENTS_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(AGENTS_STATE)


def _gen_id(task: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%m%d%H%M")
    h = hashlib.sha256(f"{task}{time.time()}".encode()).hexdigest()[:6]
    return f"a{ts}-{h}"


def _create_worktree(agent_id: str) -> str:
    """Create an isolated git worktree. Returns worktree path."""
    wt_path = WORKTREE_ROOT / agent_id
    branch = f"agent/{agent_id}"

    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_path), "HEAD"],
        cwd=str(WORKSPACE),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        _log(f"WARN: worktree creation failed: {result.stderr.strip()}")
        return ""

    _log(f"Created worktree {wt_path} on branch {branch}")
    return str(wt_path)


def _remove_worktree(agent_id: str):
    """Remove a git worktree and its branch."""
    wt_path = WORKTREE_ROOT / agent_id
    branch = f"agent/{agent_id}"

    if wt_path.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt_path)],
            cwd=str(WORKSPACE),
            capture_output=True, text=True
        )
    # Clean up branch
    subprocess.run(
        ["git", "branch", "-D", branch],
        cwd=str(WORKSPACE),
        capture_output=True, text=True
    )


def cmd_spawn(task: str, timeout: int = 1200, isolated: bool = False) -> dict:
    """Spawn a new Claude Code agent. Returns agent info dict."""
    agent_id = _gen_id(task)
    state = _load_state()

    work_dir = str(WORKSPACE)
    worktree_path = ""

    if isolated:
        worktree_path = _create_worktree(agent_id)
        if worktree_path:
            work_dir = worktree_path
        else:
            _log(f"Falling back to non-isolated for {agent_id}")
            isolated = False

    # Build prompt
    prompt = (
        f"You are Clarvis's executive function (Claude Code Opus).\n\n"
        f"TASK: {task}\n\n"
        f"Work in {work_dir} unless the task specifies another directory.\n"
        f"Be thorough. Write code if needed. Test it. Report what you did concisely."
    )

    prompt_file = f"/tmp/claude_agent_{agent_id}.txt"
    output_file = f"/tmp/claude_agent_{agent_id}_out.txt"
    Path(prompt_file).write_text(prompt)

    # Build env: remove nesting guards
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}

    # Spawn as background process
    cmd = [
        "timeout", str(timeout),
        "env", "-u", "CLAUDECODE", "-u", "CLAUDE_CODE_ENTRYPOINT",
        CLAUDE_BIN,
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--model", "claude-opus-4-6"
    ]

    with open(output_file, "w") as out_f:
        proc = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=subprocess.STDOUT,
            cwd=work_dir,
            env=env,
            start_new_session=True  # detach from parent
        )

    agent_info = {
        "id": agent_id,
        "task": task,
        "pid": proc.pid,
        "status": "running",
        "isolated": isolated,
        "worktree": worktree_path,
        "work_dir": work_dir,
        "output_file": output_file,
        "timeout": timeout,
        "spawned_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "exit_code": None,
    }

    state["agents"][agent_id] = agent_info
    _save_state(state)
    _log(f"SPAWN: {agent_id} pid={proc.pid} isolated={isolated} timeout={timeout}s task={task[:80]}")

    return agent_info


def cmd_list() -> list:
    """List all agents with current status."""
    state = _load_state()
    agents = []

    for aid, info in state["agents"].items():
        # Refresh status for running agents
        if info["status"] == "running":
            pid = info.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)  # check if alive
                except OSError:
                    # Process gone — check output for results
                    info["status"] = "completed"
                    info["completed_at"] = datetime.now(timezone.utc).isoformat()
                    # Try to get exit code from output file
                    out_path = info.get("output_file", "")
                    if out_path and os.path.exists(out_path):
                        content = Path(out_path).read_text()[-200:]
                        if "TIMEOUT" in content:
                            info["status"] = "timeout"
                            info["exit_code"] = 124
                        elif "FAILED" in content:
                            info["status"] = "failed"
                        else:
                            info["exit_code"] = 0

        agents.append(info)

    _save_state(state)
    return agents


def cmd_status(agent_id: str) -> dict:
    """Get detailed status of a specific agent."""
    state = _load_state()
    info = state["agents"].get(agent_id)
    if not info:
        return {"error": f"Agent {agent_id} not found"}

    # Refresh status
    if info["status"] == "running":
        pid = info.get("pid")
        if pid:
            try:
                os.kill(pid, 0)
                info["alive"] = True
            except OSError:
                info["alive"] = False
                info["status"] = "completed"
                info["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Attach output tail
    out_path = info.get("output_file", "")
    if out_path and os.path.exists(out_path):
        content = Path(out_path).read_text()
        info["output_tail"] = content[-2000:]
        info["output_bytes"] = len(content)
    else:
        info["output_tail"] = "(no output file)"

    _save_state(state)
    return info


def cmd_kill(agent_id: str) -> dict:
    """Kill a running agent."""
    state = _load_state()
    info = state["agents"].get(agent_id)
    if not info:
        return {"error": f"Agent {agent_id} not found"}

    pid = info.get("pid")
    if pid and info["status"] == "running":
        try:
            # Kill the process group (timeout + claude + children)
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(1)
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
        except OSError as e:
            _log(f"Kill {agent_id} (pid={pid}): {e}")

        info["status"] = "killed"
        info["completed_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)
        _log(f"KILL: {agent_id} pid={pid}")

    return info


def cmd_restore(agent_id: str) -> dict:
    """Re-spawn a killed/failed/timed-out agent with the same task."""
    state = _load_state()
    info = state["agents"].get(agent_id)
    if not info:
        return {"error": f"Agent {agent_id} not found"}

    if info["status"] == "running":
        return {"error": f"Agent {agent_id} is still running"}

    task = info["task"]
    timeout = info.get("timeout", 1200)
    isolated = info.get("isolated", False)

    # Clean up old worktree if isolated
    if info.get("worktree"):
        _remove_worktree(agent_id)

    _log(f"RESTORE: re-spawning {agent_id} task={task[:80]}")
    return cmd_spawn(task, timeout=timeout, isolated=isolated)


def cmd_merge(agent_id: str) -> dict:
    """Merge an isolated agent's worktree changes back to main."""
    state = _load_state()
    info = state["agents"].get(agent_id)
    if not info:
        return {"error": f"Agent {agent_id} not found"}

    if not info.get("isolated") or not info.get("worktree"):
        return {"error": f"Agent {agent_id} is not isolated (no worktree)"}

    if info["status"] == "running":
        return {"error": "Agent is still running. Kill or wait for completion first."}

    branch = f"agent/{agent_id}"

    # Check if there are changes to merge
    diff_result = subprocess.run(
        ["git", "diff", "--stat", f"main...{branch}"],
        cwd=str(WORKSPACE), capture_output=True, text=True
    )

    if not diff_result.stdout.strip():
        _log(f"MERGE: {agent_id} has no changes to merge")
        _remove_worktree(agent_id)
        info["status"] = "merged_empty"
        _save_state(state)
        return {"result": "no changes to merge", "id": agent_id}

    # Attempt merge
    merge_result = subprocess.run(
        ["git", "merge", "--no-ff", "-m",
         f"Merge agent/{agent_id}: {info['task'][:60]}", branch],
        cwd=str(WORKSPACE), capture_output=True, text=True
    )

    if merge_result.returncode != 0:
        # Conflict — abort
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=str(WORKSPACE), capture_output=True, text=True
        )
        _log(f"MERGE CONFLICT: {agent_id} — {merge_result.stderr.strip()}")
        return {
            "result": "merge_conflict",
            "id": agent_id,
            "details": merge_result.stderr.strip(),
            "diff": diff_result.stdout.strip()
        }

    # Success — clean up worktree
    _remove_worktree(agent_id)
    info["status"] = "merged"
    _save_state(state)
    _log(f"MERGE: {agent_id} merged successfully — {diff_result.stdout.strip()[:200]}")

    return {
        "result": "merged",
        "id": agent_id,
        "diff": diff_result.stdout.strip()
    }


def cmd_cleanup() -> dict:
    """Remove stale worktrees and dead agents older than 24h."""
    state = _load_state()
    cleaned = {"worktrees": 0, "agents": 0}
    cutoff = time.time() - 86400  # 24h ago

    for aid in list(state["agents"].keys()):
        info = state["agents"][aid]

        # Skip running agents
        if info["status"] == "running":
            pid = info.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    continue  # still alive
                except OSError:
                    info["status"] = "dead"

        # Check age
        spawned = info.get("spawned_at", "")
        if spawned:
            try:
                spawn_time = datetime.fromisoformat(spawned).timestamp()
                if spawn_time > cutoff:
                    continue  # too recent
            except (ValueError, TypeError):
                pass

        # Clean up worktree
        if info.get("worktree"):
            _remove_worktree(aid)
            cleaned["worktrees"] += 1

        # Clean up output file
        out_path = info.get("output_file", "")
        if out_path and os.path.exists(out_path):
            os.remove(out_path)

        del state["agents"][aid]
        cleaned["agents"] += 1

    # Also prune git worktrees
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(WORKSPACE), capture_output=True, text=True
    )

    _save_state(state)
    _log(f"CLEANUP: removed {cleaned['agents']} agents, {cleaned['worktrees']} worktrees")
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Agent Lifecycle Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("spawn", help="Spawn a new agent")
    sp.add_argument("task", help="Task description")
    sp.add_argument("--timeout", type=int, default=1200)
    sp.add_argument("--isolated", action="store_true",
                    help="Run in git worktree isolation")

    sub.add_parser("list", help="List all agents")

    st = sub.add_parser("status", help="Get agent status")
    st.add_argument("agent_id")

    ki = sub.add_parser("kill", help="Kill a running agent")
    ki.add_argument("agent_id")

    re = sub.add_parser("restore", help="Re-spawn a failed agent")
    re.add_argument("agent_id")

    me = sub.add_parser("merge", help="Merge worktree changes to main")
    me.add_argument("agent_id")

    sub.add_parser("cleanup", help="Remove stale worktrees and dead agents")

    args = parser.parse_args()

    if args.command == "spawn":
        result = cmd_spawn(args.task, timeout=args.timeout, isolated=args.isolated)
        print(json.dumps(result, indent=2))
    elif args.command == "list":
        agents = cmd_list()
        if not agents:
            print("No agents tracked.")
        else:
            for a in agents:
                iso = " [isolated]" if a.get("isolated") else ""
                print(f"  {a['id']}  {a['status']:<10}{iso}  {a['task'][:60]}")
    elif args.command == "status":
        result = cmd_status(args.agent_id)
        print(json.dumps(result, indent=2))
    elif args.command == "kill":
        result = cmd_kill(args.agent_id)
        print(json.dumps(result, indent=2))
    elif args.command == "restore":
        result = cmd_restore(args.agent_id)
        print(json.dumps(result, indent=2))
    elif args.command == "merge":
        result = cmd_merge(args.agent_id)
        print(json.dumps(result, indent=2))
    elif args.command == "cleanup":
        result = cmd_cleanup()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

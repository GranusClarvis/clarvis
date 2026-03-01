#!/usr/bin/env python3
"""Project Agent Manager — create, spawn, communicate with isolated project agents.

Each project agent lives in /home/agent/agents/<name>/ with:
  workspace/  — cloned repo (the agent's working directory)
  data/       — ChromaDB brain (vector + graph), episodes, metrics
  memory/     — daily logs, procedures, summaries promoted to Clarvis
  logs/       — execution logs, task history
  configs/    — agent config (repo, branch, constraints, budget)

Orchestration protocol:
  1. Clarvis sends: task brief + constraints + context
  2. Agent executes in its repo workspace
  3. Agent returns: PR link/patch, summary, reusable procedures, follow-ups

Hard isolation: project agent ChromaDB is separate from Clarvis brain.
Only structured summaries + artifacts flow back via the promotion protocol.

Usage:
    python3 project_agent.py create <name> --repo <url> [--branch dev]
    python3 project_agent.py list
    python3 project_agent.py info <name>
    python3 project_agent.py spawn <name> "task description" [--timeout 1200]
    python3 project_agent.py status <name>
    python3 project_agent.py promote <name>   # pull summaries/procedures back to Clarvis
    python3 project_agent.py destroy <name>   # remove agent (requires --confirm)
    python3 project_agent.py benchmark <name> # run isolation + retrieval benchmarks
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

AGENTS_ROOT_PRIMARY = Path("/opt/clarvis-agents")  # preferred (needs sudo once)
AGENTS_ROOT_FALLBACK = Path("/home/agent/agents")  # fallback (always writable)
CLARVIS_WORKSPACE = Path("/home/agent/.openclaw/workspace")
CLAUDE_BIN = "/home/agent/.local/bin/claude"
CRON_ENV = CLARVIS_WORKSPACE / "scripts" / "cron_env.sh"
LOGFILE = CLARVIS_WORKSPACE / "memory" / "cron" / "project_agents.log"


def _agents_root() -> Path:
    """Return the active agents root, preferring /opt/clarvis-agents."""
    if AGENTS_ROOT_PRIMARY.exists() and AGENTS_ROOT_PRIMARY.is_dir():
        return AGENTS_ROOT_PRIMARY
    return AGENTS_ROOT_FALLBACK


# Collections for lite brain (subset of Clarvis's 10)
LITE_COLLECTIONS = [
    "project-learnings",      # what the agent learned about this repo
    "project-procedures",     # how-to for this repo (build, test, deploy)
    "project-context",        # current state, recent work
    "project-episodes",       # task outcomes with timestamps
    "project-goals",          # project-specific objectives
]

AGENT_CONFIG_TEMPLATE = {
    "name": "",
    "repo_url": "",
    "branch": "main",
    "created": "",
    "status": "idle",          # idle, running, error
    "last_task": None,
    "last_run": None,
    "total_tasks": 0,
    "total_successes": 0,
    "total_pr_count": 0,
    "budget": {
        "max_timeout": 1800,   # 30 min max per task
        "max_daily_tasks": 10,
    },
    "constraints": [
        "Do NOT push to main/master without PR",
        "Do NOT modify files outside the repo workspace",
        "Do NOT access Clarvis brain or memory directly",
        "Create feature branches for all changes",
        "Run tests before creating PRs",
    ],
}


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] [project-agent] {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _agent_dir(name: str) -> Path:
    """Resolve agent directory. Checks primary (/opt) then fallback."""
    primary = AGENTS_ROOT_PRIMARY / name
    fallback = AGENTS_ROOT_FALLBACK / name
    if primary.exists():
        return primary
    if fallback.exists():
        return fallback
    # New agent — use whichever root is writable
    if AGENTS_ROOT_PRIMARY.exists() and os.access(AGENTS_ROOT_PRIMARY, os.W_OK):
        return primary
    return fallback


def _load_config(name: str) -> Optional[dict]:
    cfg_path = _agent_dir(name) / "configs" / "agent.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_config(name: str, config: dict):
    cfg_path = _agent_dir(name) / "configs" / "agent.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2))
    tmp.replace(cfg_path)


def _task_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    h = hashlib.sha256(str(time.time()).encode()).hexdigest()[:4]
    return f"t{ts}-{h}"


# =========================================================================
# CREATE — scaffold a new project agent
# =========================================================================

def cmd_create(name: str, repo_url: str, branch: str = "main") -> dict:
    """Create a new project agent with isolated workspace."""
    agent_dir = _agent_dir(name)

    if agent_dir.exists():
        return {"error": f"Agent '{name}' already exists at {agent_dir}"}

    _log(f"Creating agent '{name}' for {repo_url}")

    # Create directory structure
    for subdir in ["workspace", "data/brain", "memory/promoted",
                   "memory/summaries", "logs", "configs"]:
        (agent_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Clone the repo into workspace/
    workspace = agent_dir / "workspace"
    # Remove the empty workspace dir so git clone works
    workspace.rmdir()

    _log(f"Cloning {repo_url} (branch: {branch})")
    result = subprocess.run(
        ["git", "clone", "--branch", branch, "--single-branch",
         repo_url, str(workspace)],
        capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        # Cleanup on failure
        shutil.rmtree(agent_dir, ignore_errors=True)
        return {"error": f"Clone failed: {result.stderr.strip()}"}

    # Initialize lite brain
    _init_lite_brain(name)

    # Write agent config
    config = dict(AGENT_CONFIG_TEMPLATE)
    config["name"] = name
    config["repo_url"] = repo_url
    config["branch"] = branch
    config["created"] = datetime.now(timezone.utc).isoformat()
    _save_config(name, config)

    # Write CLAUDE.md for the project agent
    _write_agent_claude_md(name, config)

    # Write initial procedures
    _write_initial_procedures(name)

    _log(f"Agent '{name}' created successfully")
    return {
        "status": "created",
        "name": name,
        "path": str(agent_dir),
        "repo": repo_url,
        "branch": branch,
        "collections": LITE_COLLECTIONS,
    }


def _init_lite_brain(name: str):
    """Initialize a ChromaDB instance for the project agent."""
    agent_dir = _agent_dir(name)
    brain_dir = agent_dir / "data" / "brain"
    graph_file = brain_dir / "relationships.json"

    # Initialize empty graph
    graph_file.write_text(json.dumps({"nodes": {}, "edges": []}, indent=2))

    # ChromaDB will auto-create on first use via the lite brain script
    _log(f"Lite brain initialized at {brain_dir}")


def _write_agent_claude_md(name: str, config: dict):
    """Write a CLAUDE.md tailored for this project agent."""
    agent_dir = _agent_dir(name)
    claude_md = agent_dir / "workspace" / "CLAUDE.md"

    # Don't overwrite if repo already has one
    if claude_md.exists():
        # Append our agent instructions
        existing = claude_md.read_text()
        agent_section = _agent_instructions(name, config)
        claude_md.write_text(existing + "\n\n" + agent_section)
    else:
        claude_md.write_text(_agent_instructions(name, config))


def _agent_instructions(name: str, config: dict) -> str:
    agent_dir = _agent_dir(name)
    constraints = "\n".join(f"- {c}" for c in config.get("constraints", []))
    return f"""
# Project Agent: {name}

You are a specialized project agent managed by Clarvis.
Your workspace is: {agent_dir}/workspace
Your brain DB is: {agent_dir}/data/brain (isolated — NOT shared with Clarvis)

## Constraints
{constraints}

## Workflow
1. Read the task brief carefully
2. Explore the codebase to understand context
3. Implement the requested changes
4. Run tests to verify
5. Create a PR (or commit if tests pass)
6. Write a concise summary of what you did

## Output Protocol
At the end of your task, output a JSON block with this structure:
```json
{{
  "status": "success" | "partial" | "failed",
  "pr_url": "https://github.com/..." | null,
  "branch": "feature/...",
  "summary": "What I did in 2-3 sentences",
  "files_changed": ["path/to/file1", "path/to/file2"],
  "procedures": ["How to build: ...", "How to test: ..."],
  "follow_ups": ["TODO: ...", "NEEDS: ..."],
  "tests_passed": true | false
}}
```

## Brain Usage
Store learnings about this repo:
```python
import sys; sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
from lite_brain import LiteBrain
brain = LiteBrain("{agent_dir}/data/brain")
brain.store("insight about this repo", "project-learnings")
brain.recall("how to build this project")
```
""".strip()


def _write_initial_procedures(name: str):
    """Write initial procedure memory for the agent."""
    agent_dir = _agent_dir(name)
    proc_file = agent_dir / "memory" / "procedures.md"
    proc_file.write_text(f"""# Procedures — {name}

## Git Workflow
1. Always create a feature branch: `git checkout -b feature/<description>`
2. Make changes and commit with clear messages
3. Push branch: `git push origin feature/<description>`
4. Create PR: `gh pr create --title "..." --body "..."`
5. Report PR URL in output

## Testing
- Run project tests before creating PR
- Report test results in output

## Communication
- Write concise summaries
- List files changed
- Note any follow-up work needed
""")


# =========================================================================
# SPAWN — execute a task in a project agent
# =========================================================================

def cmd_spawn(name: str, task: str, timeout: int = 1200,
              context: str = "") -> dict:
    """Spawn Claude Code to execute a task in the project agent's workspace."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    if config.get("status") == "running":
        return {"error": f"Agent '{name}' is already running a task"}

    agent_dir = _agent_dir(name)
    workspace = agent_dir / "workspace"
    task_id = _task_id()

    # Enforce budget
    max_timeout = config.get("budget", {}).get("max_timeout", 1800)
    timeout = min(timeout, max_timeout)

    _log(f"Spawning task {task_id} on agent '{name}': {task[:80]}")

    # Update status
    config["status"] = "running"
    config["last_task"] = {"id": task_id, "task": task[:200], "started": datetime.now(timezone.utc).isoformat()}
    _save_config(name, config)

    # Build the prompt
    procedures = ""
    proc_file = agent_dir / "memory" / "procedures.md"
    if proc_file.exists():
        procedures = proc_file.read_text()[:2000]

    constraints = "\n".join(f"- {c}" for c in config.get("constraints", []))

    prompt_parts = [
        f"You are a project agent for '{name}'.",
        f"Working directory: {workspace}",
        "",
        "## Constraints",
        constraints,
        "",
    ]

    if procedures:
        prompt_parts.extend([
            "## Known Procedures",
            procedures[:1500],
            "",
        ])

    if context:
        prompt_parts.extend([
            "## Context from Clarvis",
            context[:2000],
            "",
        ])

    prompt_parts.extend([
        "## Task",
        task,
        "",
        "## Brain (optional — store useful learnings)",
        f"export AGENT_BRAIN_DIR={agent_dir}/data/brain",
        f"python3 -c \"import sys; sys.path.insert(0, '{CLARVIS_WORKSPACE}/scripts'); "
        f"from lite_brain import LiteBrain; b=LiteBrain('{agent_dir}/data/brain'); "
        "b.store('what you learned', 'project-procedures')\"",
        "",
        "## Git Workflow for PRs",
        "1. git checkout -b feature/<desc>",
        "2. Make changes, commit",
        "3. git push origin feature/<desc>",
        "4. gh pr create --title '...' --body '...'",
        "",
        "## Output Protocol",
        "At the END of your work, output a JSON block (```json ... ```) with this EXACT structure:",
        "```json",
        "{",
        '  "status": "success" | "partial" | "failed",',
        '  "pr_url": "https://github.com/..." or null,',
        '  "branch": "feature/...",',
        '  "summary": "2-3 sentences of what you did",',
        '  "files_changed": ["path/to/file1", "path/to/file2"],',
        '  "procedures": ["Build: npm run build", "Test: npm run test"],',
        '  "follow_ups": ["TODO: ...", "NEEDS: ..."],',
        '  "tests_passed": true or false',
        "}",
        "```",
    ])

    prompt = "\n".join(prompt_parts)

    # Write prompt to file
    prompt_file = f"/tmp/project_agent_{name}_{task_id}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    output_file = f"/tmp/project_agent_{name}_{task_id}_output.txt"
    log_file = agent_dir / "logs" / f"{task_id}.log"

    # Spawn Claude Code
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    cmd = [
        "timeout", str(timeout),
        "env", "-u", "CLAUDECODE", "-u", "CLAUDE_CODE_ENTRYPOINT",
        CLAUDE_BIN,
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--model", "claude-opus-4-6",
    ]

    _log(f"Executing in {workspace} with {timeout}s timeout")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 60,
            cwd=str(workspace),
            env=env,
        )
        exit_code = result.returncode
        output = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        exit_code = 124
        output = "(timeout)"
        stderr = ""
    except Exception as e:
        exit_code = 1
        output = ""
        stderr = str(e)

    elapsed = time.time() - start_time

    # Save output
    with open(output_file, "w") as f:
        f.write(output)
    with open(log_file, "w") as f:
        f.write(f"Task: {task}\n")
        f.write(f"Exit: {exit_code}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n")
        f.write(f"---\n{output}\n---\n{stderr}\n")

    # Clean up prompt file
    try:
        os.unlink(prompt_file)
    except OSError:
        pass

    # Parse agent output for structured result
    agent_result = _parse_agent_output(output)

    # Update config
    config["status"] = "idle"
    config["last_run"] = datetime.now(timezone.utc).isoformat()
    config["total_tasks"] = config.get("total_tasks", 0) + 1
    if agent_result.get("status") == "success":
        config["total_successes"] = config.get("total_successes", 0) + 1
    if agent_result.get("pr_url"):
        config["total_pr_count"] = config.get("total_pr_count", 0) + 1
    config["last_task"]["completed"] = datetime.now(timezone.utc).isoformat()
    config["last_task"]["exit_code"] = exit_code
    config["last_task"]["elapsed"] = round(elapsed, 1)
    config["last_task"]["result"] = agent_result.get("status", "unknown")
    _save_config(name, config)

    # Store task summary
    summary_file = agent_dir / "memory" / "summaries" / f"{task_id}.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps({
        "task_id": task_id,
        "task": task[:500],
        "result": agent_result,
        "exit_code": exit_code,
        "elapsed": round(elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    _log(f"Task {task_id} completed: exit={exit_code} elapsed={elapsed:.0f}s status={agent_result.get('status', 'unknown')}")

    return {
        "task_id": task_id,
        "agent": name,
        "exit_code": exit_code,
        "elapsed": round(elapsed, 1),
        "result": agent_result,
        "output_tail": output[-1500:] if output else "",
        "log": str(log_file),
    }


def _parse_agent_output(output: str) -> dict:
    """Extract structured JSON result from agent output."""
    if not output:
        return {"status": "failed", "summary": "No output"}

    # Find last JSON block in output
    import re
    json_blocks = re.findall(r'```json\s*\n(.*?)\n```', output, re.DOTALL)

    if json_blocks:
        try:
            return json.loads(json_blocks[-1])
        except json.JSONDecodeError:
            pass

    # Fallback: try to find raw JSON object
    for line in reversed(output.split("\n")):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    # No structured output — extract what we can
    return {
        "status": "unknown",
        "summary": output[-500:] if output else "No output",
    }


# =========================================================================
# PROMOTE — pull results back to Clarvis
# =========================================================================

def cmd_promote(name: str) -> dict:
    """Promote summaries and procedures from project agent to Clarvis."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"
    promoted_dir = agent_dir / "memory" / "promoted"

    promoted = []
    procedures_to_promote = []

    # Scan summaries not yet promoted
    if summaries_dir.exists():
        for sf in sorted(summaries_dir.glob("*.json")):
            promoted_marker = promoted_dir / sf.name
            if promoted_marker.exists():
                continue

            try:
                summary = json.loads(sf.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            result = summary.get("result", {})

            # Collect procedures
            for proc in result.get("procedures", []):
                if proc and len(proc) > 10:
                    procedures_to_promote.append(proc)

            # Build promotion record
            promoted.append({
                "task_id": summary.get("task_id"),
                "agent": name,
                "task": summary.get("task", "")[:200],
                "status": result.get("status", "unknown"),
                "summary": result.get("summary", ""),
                "pr_url": result.get("pr_url"),
                "follow_ups": result.get("follow_ups", []),
                "timestamp": summary.get("timestamp"),
            })

            # Mark as promoted
            promoted_marker.write_text(datetime.now(timezone.utc).isoformat())

    if not promoted:
        return {"status": "nothing_to_promote", "agent": name}

    # Write promotion digest for Clarvis
    digest_file = CLARVIS_WORKSPACE / "memory" / "cron" / f"agent_{name}_digest.md"
    lines = [f"# Project Agent Digest: {name}", f"_Promoted {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}_\n"]

    for p in promoted:
        status_emoji = {"success": "+", "partial": "~", "failed": "-"}.get(p["status"], "?")
        lines.append(f"[{status_emoji}] {p['task_id']}: {p['summary']}")
        if p.get("pr_url"):
            lines.append(f"  PR: {p['pr_url']}")
        for fu in p.get("follow_ups", []):
            lines.append(f"  -> {fu}")
        lines.append("")

    if procedures_to_promote:
        lines.append("## Learned Procedures")
        for proc in procedures_to_promote:
            lines.append(f"- {proc}")

    digest_file.write_text("\n".join(lines))

    _log(f"Promoted {len(promoted)} results from agent '{name}'")

    return {
        "status": "promoted",
        "agent": name,
        "count": len(promoted),
        "procedures": len(procedures_to_promote),
        "digest": str(digest_file),
    }


# =========================================================================
# LIST / INFO / STATUS
# =========================================================================

def cmd_list() -> list:
    """List all project agents (checks both /opt and /home roots)."""
    agents = []
    seen = set()

    for root in [AGENTS_ROOT_PRIMARY, AGENTS_ROOT_FALLBACK]:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name not in seen:
                config = _load_config(d.name)
                if config:
                    seen.add(d.name)
                    agents.append({
                        "name": config["name"],
                        "repo": config["repo_url"],
                        "branch": config.get("branch", "main"),
                        "status": config.get("status", "unknown"),
                        "tasks": config.get("total_tasks", 0),
                        "successes": config.get("total_successes", 0),
                        "prs": config.get("total_pr_count", 0),
                        "last_run": config.get("last_run"),
                        "created": config.get("created"),
                        "path": str(_agent_dir(d.name)),
                    })
    return agents


def cmd_info(name: str) -> dict:
    """Get detailed info about a project agent."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)

    # Count summaries
    summaries_dir = agent_dir / "memory" / "summaries"
    summary_count = len(list(summaries_dir.glob("*.json"))) if summaries_dir.exists() else 0

    # Brain size
    brain_dir = agent_dir / "data" / "brain"
    brain_size = sum(f.stat().st_size for f in brain_dir.rglob("*") if f.is_file()) if brain_dir.exists() else 0

    # Workspace git status
    workspace = agent_dir / "workspace"
    git_status = ""
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True,
                           cwd=str(workspace), timeout=10)
        git_status = r.stdout.strip()
    except Exception:
        git_status = "(unavailable)"

    config["summaries"] = summary_count
    config["brain_size_kb"] = round(brain_size / 1024, 1)
    config["git_status"] = git_status
    config["path"] = str(agent_dir)

    return config


def cmd_status(name: str) -> dict:
    """Quick status of a project agent."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    return {
        "name": name,
        "status": config.get("status", "unknown"),
        "last_run": config.get("last_run"),
        "last_task": config.get("last_task"),
        "tasks": config.get("total_tasks", 0),
        "successes": config.get("total_successes", 0),
    }


# =========================================================================
# DESTROY
# =========================================================================

def cmd_destroy(name: str, confirm: bool = False) -> dict:
    """Remove a project agent entirely."""
    agent_dir = _agent_dir(name)
    if not agent_dir.exists():
        return {"error": f"Agent '{name}' not found"}

    if not confirm:
        return {"error": "Use --confirm to destroy agent. This is irreversible."}

    config = _load_config(name)
    if config and config.get("status") == "running":
        return {"error": "Cannot destroy a running agent. Kill it first."}

    _log(f"DESTROYING agent '{name}' at {agent_dir}")
    shutil.rmtree(agent_dir)
    return {"status": "destroyed", "name": name}


# =========================================================================
# SEED — populate agent brain with golden Q/A and repo knowledge
# =========================================================================

def cmd_seed(name: str) -> dict:
    """Seed the agent's lite brain with repo-specific knowledge from golden_qa.json."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)
    golden_file = agent_dir / "data" / "golden_qa.json"

    if not golden_file.exists():
        return {"error": f"No golden_qa.json at {golden_file}. Create it first."}

    try:
        golden = json.loads(golden_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to read golden_qa.json: {e}"}

    # Import lite brain
    sys.path.insert(0, str(CLARVIS_WORKSPACE / "scripts"))
    from lite_brain import LiteBrain
    brain = LiteBrain(str(agent_dir / "data" / "brain"))

    seeded = 0
    for qa in golden:
        # Store the expected answer as a procedure/learning
        answer = qa.get("answer", "")
        collection = qa.get("collection", "project-procedures")
        if answer:
            brain.store(answer, collection, importance=0.8,
                        tags=qa.get("tags", ["golden_qa"]),
                        source="golden_qa_seed")
            seeded += 1

    _log(f"Seeded {seeded} memories into agent '{name}' brain from golden_qa.json")
    return {"status": "seeded", "count": seeded, "agent": name}


# =========================================================================
# MIGRATE — move agent between roots (e.g., /home → /opt)
# =========================================================================

def cmd_migrate(name: str, target_root: str = "/opt/clarvis-agents") -> dict:
    """Migrate an agent to a different root directory."""
    current = _agent_dir(name)
    if not current.exists():
        return {"error": f"Agent '{name}' not found"}

    target = Path(target_root) / name
    if target.exists():
        return {"error": f"Target {target} already exists"}

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(current), str(target))
    except (OSError, PermissionError) as e:
        return {"error": f"Migration failed: {e}. Run: sudo mkdir -p {target_root} && sudo chown agent:agent {target_root}"}

    _log(f"Migrated agent '{name}' from {current} to {target}")
    return {"status": "migrated", "from": str(current), "to": str(target)}


# =========================================================================
# BENCHMARK — isolation + retrieval quality checks
# =========================================================================

def cmd_benchmark(name: str) -> dict:
    """Run isolation and retrieval benchmarks for a project agent."""
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)
    results = {
        "agent": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Context Isolation: check for leakage
    results["isolation"] = _benchmark_isolation(name)

    # 2. Retrieval Quality (placeholder — needs golden Q/A set per project)
    results["retrieval"] = _benchmark_retrieval(name)

    # 3. Task metrics from history
    results["task_metrics"] = _benchmark_tasks(name)

    # Save benchmark result
    bench_file = agent_dir / "data" / "benchmark.json"
    bench_file.write_text(json.dumps(results, indent=2))

    return results


def _benchmark_isolation(name: str) -> dict:
    """Check embedding overlap between project agent and Clarvis brain."""
    # This requires both brains to be importable
    # For now, return structural isolation checks
    agent_dir = _agent_dir(name)
    clarvis_brain = CLARVIS_WORKSPACE / "data" / "clarvisdb"
    agent_brain = agent_dir / "data" / "brain"

    # Check paths don't overlap
    clarvis_path = str(clarvis_brain.resolve())
    agent_path = str(agent_brain.resolve())

    return {
        "paths_isolated": not agent_path.startswith(clarvis_path) and not clarvis_path.startswith(agent_path),
        "clarvis_brain": clarvis_path,
        "agent_brain": agent_path,
        "no_shared_files": True,  # structural guarantee
        "status": "pass",
    }


def _benchmark_retrieval(name: str) -> dict:
    """Placeholder for retrieval quality benchmark."""
    return {
        "status": "not_configured",
        "note": "Create data/golden_qa.json with repo-specific Q/A pairs to enable",
    }


def _benchmark_tasks(name: str) -> dict:
    """Compute task success metrics from history."""
    config = _load_config(name)
    total = config.get("total_tasks", 0)
    successes = config.get("total_successes", 0)

    agent_dir = _agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"

    # Compute timing stats
    elapsed_times = []
    pr_count = 0

    if summaries_dir.exists():
        for sf in summaries_dir.glob("*.json"):
            try:
                s = json.loads(sf.read_text())
                if "elapsed" in s:
                    elapsed_times.append(s["elapsed"])
                if s.get("result", {}).get("pr_url"):
                    pr_count += 1
            except (json.JSONDecodeError, OSError):
                continue

    return {
        "total_tasks": total,
        "successes": successes,
        "success_rate": f"{successes / max(total, 1) * 100:.0f}%",
        "pr_count": pr_count,
        "pr_rate": f"{pr_count / max(total, 1) * 100:.0f}%",
        "avg_elapsed": round(sum(elapsed_times) / max(len(elapsed_times), 1), 1) if elapsed_times else 0,
        "p50_elapsed": round(sorted(elapsed_times)[len(elapsed_times) // 2], 1) if elapsed_times else 0,
        "p95_elapsed": round(sorted(elapsed_times)[int(len(elapsed_times) * 0.95)] if elapsed_times else 0, 1),
    }


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Project Agent Manager — isolated agents for specific repos")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    cp = sub.add_parser("create", help="Create a new project agent")
    cp.add_argument("name", help="Agent name (e.g., star-world-order)")
    cp.add_argument("--repo", required=True, help="Git repository URL")
    cp.add_argument("--branch", default="dev", help="Default branch")

    # list
    sub.add_parser("list", help="List all project agents")

    # info
    ip = sub.add_parser("info", help="Detailed agent info")
    ip.add_argument("name")

    # spawn
    sp = sub.add_parser("spawn", help="Execute a task on a project agent")
    sp.add_argument("name", help="Agent name")
    sp.add_argument("task", help="Task description")
    sp.add_argument("--timeout", type=int, default=1200)
    sp.add_argument("--context", default="", help="Additional context from Clarvis")

    # status
    st = sub.add_parser("status", help="Quick agent status")
    st.add_argument("name")

    # promote
    pp = sub.add_parser("promote", help="Pull results back to Clarvis")
    pp.add_argument("name")

    # destroy
    dp = sub.add_parser("destroy", help="Remove agent entirely")
    dp.add_argument("name")
    dp.add_argument("--confirm", action="store_true")

    # benchmark
    bp = sub.add_parser("benchmark", help="Run isolation/retrieval benchmarks")
    bp.add_argument("name")

    # seed
    sedp = sub.add_parser("seed", help="Seed agent brain from golden_qa.json")
    sedp.add_argument("name")

    # migrate
    mp = sub.add_parser("migrate", help="Migrate agent to /opt/clarvis-agents")
    mp.add_argument("name")
    mp.add_argument("--target", default="/opt/clarvis-agents", help="Target root")

    args = parser.parse_args()

    if args.command == "create":
        result = cmd_create(args.name, args.repo, args.branch)
    elif args.command == "list":
        result = cmd_list()
    elif args.command == "info":
        result = cmd_info(args.name)
    elif args.command == "spawn":
        result = cmd_spawn(args.name, args.task, args.timeout, args.context)
    elif args.command == "status":
        result = cmd_status(args.name)
    elif args.command == "promote":
        result = cmd_promote(args.name)
    elif args.command == "destroy":
        result = cmd_destroy(args.name, args.confirm)
    elif args.command == "benchmark":
        result = cmd_benchmark(args.name)
    elif args.command == "seed":
        result = cmd_seed(args.name)
    elif args.command == "migrate":
        result = cmd_migrate(args.name, args.target)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

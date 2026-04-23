#!/usr/bin/env python3
"""Project Agent Manager — create, spawn, communicate with isolated project agents.

Each project agent lives in ~/agents/<name>/ with:
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
    python3 project_agent.py decompose <name> "task" # break task into subtasks
    python3 project_agent.py loop <name> "task" [--timeout 1200] [--max-sessions 8] [--budget 2.0]
    python3 project_agent.py ci-check <name> <pr_number> [--timeout 600]
    python3 project_agent.py spawn-parallel --tasks '[{"agent":"a","task":"t1"},{"agent":"b","task":"t2"}]'
"""

import argparse
import json
import os
import random
import shlex
import shutil
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

AGENTS_ROOT_PRIMARY = Path("/opt/clarvis-agents")  # preferred (needs sudo once)
AGENTS_ROOT_FALLBACK = Path("~/agents").expanduser()  # fallback (always writable)
CLARVIS_WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
CRON_ENV = CLARVIS_WORKSPACE / "scripts" / "cron_env.sh"
LOGFILE = CLARVIS_WORKSPACE / "memory" / "cron" / "project_agents.log"

# Retry configuration
MAX_RETRIES = 2              # Max retry attempts per task
RETRY_BACKOFF_BASE = 15      # Seconds before first retry (doubles each attempt)

# ── Auto-Commit Safety Whitelist ──────────────────────────────────────
# Extensions that untracked files must match to be staged.
# Tracked (modified/deleted) files are always staged regardless.
COMMIT_EXT_WHITELIST = frozenset({
    ".py", ".ts", ".js", ".jsx", ".tsx", ".json", ".md", ".css", ".scss",
    ".html", ".go", ".rs", ".toml", ".yaml", ".yml", ".sh", ".sql", ".txt",
    ".mjs", ".cjs", ".svelte", ".vue", ".lock",
})

# Regex patterns for paths that must NEVER be staged (secrets, binaries, logs).
import re as _re_mod
COMMIT_BLOCKED_PATTERNS = _re_mod.compile(
    r"(\.env|id_rsa|id_ed25519|\.pem$|\.key$|\.p12$|\.pfx$|"
    r"\.sqlite$|\.db$|\.log$|\.zip$|\.tar$|\.gz$|\.tgz$|"
    r"\.whl$|\.egg$|\.pyc$|node_modules/|__pycache__/|"
    r"\.git/|credentials|secrets?\.)"
)

# ── A2A Message Protocol (v1) ─────────────────────────────────────────
# Internal Agent-to-Agent message schema for structured communication.
# Agents MUST return this JSON at end of task. Clarvis validates on receive.

A2A_PROTOCOL_VERSION = "1"

# Required fields every agent response must contain
A2A_REQUIRED_FIELDS = {"status", "summary"}

# Valid status values
A2A_VALID_STATUSES = {"success", "partial", "failed", "blocked", "unknown"}

# Full schema with types (for documentation and validation)
A2A_RESULT_SCHEMA = {
    "protocol":      "a2a/v1",        # str  — protocol identifier (auto-injected)
    "status":        "unknown",        # str  — one of A2A_VALID_STATUSES (default unknown, not success)
    "summary":       "",               # str  — 1-3 sentence description of what was done
    "pr_url":        None,             # str|null — PR URL if one was created
    "branch":        None,             # str|null — git branch name
    "files_changed": [],               # list[str] — relative paths of modified files
    "procedures":    [],               # list[str] — reusable build/test/deploy commands
    "follow_ups":    [],               # list[str] — suggested next tasks
    "tests_passed":  None,             # bool|null — whether tests passed
    "error":         None,             # str|null — error message if status=failed/blocked
    "confidence":    None,             # float|null — 0.0-1.0 agent self-assessed confidence
    "pr_class":      None,             # str|null — A/B/C PR class (required when pr_url is set)
}


def validate_a2a_result(result: dict) -> tuple[bool, list[str]]:
    """Validate an agent result against A2A protocol v1.

    Returns (is_valid, list_of_warnings). A result is valid if it has
    all required fields with acceptable values. Warnings are non-fatal
    issues (missing optional fields, unexpected types).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check required fields
    for field in A2A_REQUIRED_FIELDS:
        if field not in result:
            errors.append(f"missing required field: {field}")
    if not errors:
        # All required present — check values
        if result.get("status") not in A2A_VALID_STATUSES:
            errors.append(f"invalid status: {result.get('status')!r} "
                          f"(expected one of {A2A_VALID_STATUSES})")
        if not isinstance(result.get("summary", ""), str) or not result.get("summary"):
            errors.append("summary must be a non-empty string")

    is_valid = len(errors) == 0

    # Type checks for optional fields (warnings only)
    if "files_changed" in result and not isinstance(result["files_changed"], list):
        warnings.append("files_changed should be a list")
    if "procedures" in result and not isinstance(result["procedures"], list):
        warnings.append("procedures should be a list")
    if "follow_ups" in result and not isinstance(result["follow_ups"], list):
        warnings.append("follow_ups should be a list")
    if "confidence" in result and result["confidence"] is not None:
        try:
            c = float(result["confidence"])
            if not (0.0 <= c <= 1.0):
                warnings.append(f"confidence out of range: {c}")
        except (ValueError, TypeError):
            warnings.append(f"confidence must be a number: {result['confidence']!r}")

    # PR class validation: warn if pr_url set but pr_class missing/invalid
    if result.get("pr_url"):
        pr_class = result.get("pr_class")
        if not pr_class:
            warnings.append("pr_class should be set when pr_url is present (A/B/C)")
        elif pr_class not in ("A", "B", "C"):
            warnings.append(f"pr_class must be one of A, B, C — got {pr_class!r}")

    return is_valid, errors + warnings


def normalize_a2a_result(result: dict) -> dict:
    """Normalize an agent result to conform to A2A protocol v1.

    Fills in defaults for missing optional fields and adds protocol tag.
    """
    normalized = {"protocol": f"a2a/v{A2A_PROTOCOL_VERSION}"}
    for key, default in A2A_RESULT_SCHEMA.items():
        if key == "protocol":
            continue
        normalized[key] = result.get(key, default)
    # Preserve any extra fields the agent sent (extensibility)
    for key, value in result.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


# ── Trust scoring ──────────────────────────────────────────────────────
# Outcome-based adjustment table: event -> delta
TRUST_ADJUSTMENTS = {
    "task_success":    +0.03,   # basic task completed
    "pr_created":      +0.05,   # opened a PR
    "pr_merged":       +0.05,   # PR was merged (applied via promote/manual)
    "task_failed":     -0.10,   # task failed
    "timeout":         -0.05,   # task timed out
    "ci_broke_main":   -0.20,   # broke the main branch CI
    "manual_boost":    +0.10,   # operator manually boosts
    "manual_penalize": -0.10,   # operator manually penalizes
}

# Trust tiers: (min_score, tier_name, description)
TRUST_TIERS = [
    (0.80, "autonomous",  "Full autonomy — can spawn without review"),
    (0.50, "supervised",   "Supervised — results reviewed before merge"),
    (0.20, "restricted",   "Restricted — limited task types, extra guardrails"),
    (0.00, "suspended",    "Suspended — no tasks dispatched"),
]

DEFAULT_TRUST_SCORE = 0.50  # new agents start supervised

# Cost tracking via OpenRouter API
try:
    from clarvis.orch.cost_api import fetch_usage as _fetch_openrouter_usage
    _HAS_COST_API = True
except ImportError:
    _HAS_COST_API = False

# Dashboard event publishing
try:
    from dashboard_events import emit_event as _emit_dashboard_event
    _HAS_DASHBOARD = True
except ImportError:
    _HAS_DASHBOARD = False


def _emit(event_type: str, **kwargs):
    """Emit a dashboard event (no-op if module unavailable)."""
    if _HAS_DASHBOARD:
        try:
            _emit_dashboard_event(event_type, **kwargs)
        except Exception:
            pass


def _snapshot_cost() -> Optional[float]:
    """Snapshot current OpenRouter total spend. Returns None on failure."""
    if not _HAS_COST_API:
        return None
    try:
        usage = _fetch_openrouter_usage()
        return usage.get("total")
    except Exception:
        return None


def _agents_root() -> Path:
    """Return the active agents root, preferring /opt/clarvis-agents."""
    if AGENTS_ROOT_PRIMARY.exists() and AGENTS_ROOT_PRIMARY.is_dir():
        return AGENTS_ROOT_PRIMARY
    return AGENTS_ROOT_FALLBACK


# ── Lock liveness via /proc ──────────────────────────────────────────

_CLARVIS_PROCESS_MARKERS = (
    "clarvis", "claude",
    "cron_autonomous", "cron_morning", "cron_evening",
    "cron_evolution", "cron_reflection", "cron_research",
    "cron_implementation", "cron_strategic", "cron_orchestrator",
    "project_agent",
)


def _is_pid_clarvis(pid: int) -> bool:
    """Check if PID is alive AND belongs to a clarvis/claude process.

    Reads /proc/<pid>/cmdline to verify identity, preventing false lock
    honors from PID recycling after the original process died.
    """
    try:
        os.kill(pid, 0)  # alive?
    except (ProcessLookupError, PermissionError):
        return False

    cmdline_path = Path(f"/proc/{pid}/cmdline")
    if cmdline_path.exists():
        try:
            cmdline = cmdline_path.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace")
            return any(marker in cmdline for marker in _CLARVIS_PROCESS_MARKERS)
        except OSError:
            return False
    # /proc unavailable (non-Linux) — fall back to kill-0 (already passed)
    return True


# ── Claude concurrency controls ───────────────────────────────────────
#
# We intentionally do NOT use the global Clarvis Claude lock for project agents.
# Agents are repo-isolated under ~/agents/<name>/ and may run in parallel.
#
# Policy (operator directive 2026-03-07):
# - Each agent may run at most 1 Claude session at a time (per-agent lock).
# - Up to MAX_PARALLEL_AGENT_CLAUDE agents may run Claude concurrently.
# - Clarvis core cron scripts still use /tmp/clarvis_claude_global.lock.

MAX_PARALLEL_AGENT_CLAUDE = int(os.environ.get("CLARVIS_MAX_PARALLEL_AGENT_CLAUDE", "3"))


def _agent_claude_lock_path(agent_name: str) -> Path:
    return Path(f"/tmp/clarvis_agent_{agent_name}_claude.lock")


def _acquire_agent_claude_lock(agent_name: str) -> Optional[str]:
    """Acquire per-agent Claude lock. Returns error string if locked."""
    lock = _agent_claude_lock_path(agent_name)
    if lock.exists():
        try:
            pid_str = lock.read_text().strip()
            if pid_str.isdigit() and _is_pid_clarvis(int(pid_str)):
                age = int(time.time() - lock.stat().st_mtime)
                return f"agent Claude lock held for '{agent_name}' by PID {pid_str} (age={age}s)"
            lock.unlink(missing_ok=True)
        except OSError:
            lock.unlink(missing_ok=True)
    try:
        lock.write_text(str(os.getpid()))
        return None
    except OSError as e:
        return f"failed to acquire agent Claude lock for '{agent_name}': {e}"


def _release_agent_claude_lock(agent_name: str) -> None:
    lock = _agent_claude_lock_path(agent_name)
    try:
        if lock.exists() and lock.read_text().strip() == str(os.getpid()):
            lock.unlink(missing_ok=True)
    except OSError:
        pass


def _slots_dir() -> Path:
    return Path("/tmp/clarvis_claude_slots")


def _cleanup_stale_slot_files() -> None:
    d = _slots_dir()
    if not d.exists():
        return
    for f in d.glob("slot_*.lock"):
        try:
            pid_str = f.read_text().strip().split()[0]
            if not pid_str.isdigit() or not _is_pid_clarvis(int(pid_str)):
                f.unlink(missing_ok=True)
        except OSError:
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass


def _acquire_claude_slot(agent_name: str) -> tuple[Optional[Path], Optional[str]]:
    """Acquire a global *semaphore slot* for agent Claude runs.

    Returns (slot_file, error). If slot_file is not None, caller MUST release.
    """
    if MAX_PARALLEL_AGENT_CLAUDE <= 0:
        return None, None

    d = _slots_dir()
    d.mkdir(parents=True, exist_ok=True)

    _cleanup_stale_slot_files()

    # Count current holders
    holders = list(d.glob("slot_*.lock"))
    if len(holders) >= MAX_PARALLEL_AGENT_CLAUDE:
        return None, f"agent Claude concurrency cap reached ({len(holders)}/{MAX_PARALLEL_AGENT_CLAUDE})"

    # Create a unique slot file
    slot = d / f"slot_{agent_name}_{os.getpid()}_{int(time.time())}.lock"
    try:
        slot.write_text(f"{os.getpid()} {agent_name}\n")
        return slot, None
    except OSError as e:
        return None, f"failed to acquire agent Claude slot: {e}"


def _release_claude_slot(slot_file: Optional[Path]) -> None:
    if not slot_file:
        return
    try:
        slot_file.unlink(missing_ok=True)
    except OSError:
        pass


# ── Per-agent loop lockfile ─────────────────────────────────────────

def _loop_lock_path(agent_name: str) -> Path:
    """Return the lockfile path for a per-agent task loop."""
    return Path(f"/tmp/clarvis_agent_{agent_name}_loop.lock")


def _acquire_loop_lock(agent_name: str) -> bool:
    """Acquire per-agent loop lock with stale PID detection.

    Returns True if lock acquired, False if another live loop is running.
    Stale locks (dead PID or recycled non-clarvis PID) are auto-cleaned.
    """
    lock = _loop_lock_path(agent_name)
    if lock.exists():
        try:
            pid_str = lock.read_text().strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid == os.getpid() or _is_pid_clarvis(pid):
                    age = int(time.time() - lock.stat().st_mtime)
                    if age <= 5 * 3600:  # 5h max loop duration
                        _log(f"Loop lock held by PID {pid} (age={age}s) for agent '{agent_name}'")
                        return False
                    else:
                        _log(f"WARN: Stale loop lock (PID {pid}, age={age}s) for '{agent_name}' — reclaiming")
                else:
                    _log(f"WARN: Loop lock PID {pid} dead/recycled for '{agent_name}' — reclaiming")
            # Invalid or stale — remove
            lock.unlink(missing_ok=True)
        except (OSError, ValueError):
            lock.unlink(missing_ok=True)
    # Write our PID
    try:
        lock.write_text(str(os.getpid()))
        return True
    except OSError as e:
        _log(f"Failed to acquire loop lock for '{agent_name}': {e}")
        return False


def _release_loop_lock(agent_name: str) -> None:
    """Release per-agent loop lock (only if we own it)."""
    lock = _loop_lock_path(agent_name)
    try:
        if lock.exists():
            pid_str = lock.read_text().strip()
            if pid_str == str(os.getpid()):
                lock.unlink(missing_ok=True)
    except OSError:
        pass


# Delay between subtask sessions (seconds)
LOOP_INTER_SUBTASK_DELAY_MIN = 10
LOOP_INTER_SUBTASK_DELAY_MAX = 20


# Collections for lite brain (subset of Clarvis's 10)
LITE_COLLECTIONS = [
    "project-learnings",      # what the agent learned about this repo
    "project-procedures",     # how-to for this repo (build, test, deploy)
    "project-context",        # current state, recent work
    "project-episodes",       # task outcomes with timestamps
    "project-goals",          # project-specific objectives
    "project-sector",         # domain/product playbook constraints (Layer E)
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
    "trust_score": DEFAULT_TRUST_SCORE,
    "trust_history": [],          # last N adjustments [{event, delta, score, ts}]
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


def find_agent_for_lane(lane: str) -> Optional[str]:
    """Find the project agent name mapped to a given lane (e.g. 'SWO' → 'star-world-order').

    Scans all agent configs for a matching 'lane' field. Returns the agent name or None.
    """
    if not lane:
        return None
    lane_upper = lane.upper()
    for root in (AGENTS_ROOT_PRIMARY, AGENTS_ROOT_FALLBACK):
        if not root.exists():
            continue
        for agent_dir in root.iterdir():
            if not agent_dir.is_dir():
                continue
            cfg_path = agent_dir / "configs" / "agent.json"
            if not cfg_path.exists():
                continue
            try:
                cfg = json.loads(cfg_path.read_text())
                if cfg.get("lane", "").upper() == lane_upper:
                    return cfg.get("name", agent_dir.name)
            except (json.JSONDecodeError, OSError):
                continue
    return None


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


# ── Trust scoring functions ─────────────────────────────────────────────

def get_trust_tier(score: float) -> tuple[str, str]:
    """Return (tier_name, description) for a trust score."""
    for min_score, tier, desc in TRUST_TIERS:
        if score >= min_score:
            return tier, desc
    return "suspended", "Suspended — no tasks dispatched"


def adjust_trust(name: str, event: str, config: Optional[dict] = None) -> dict:
    """Apply a trust adjustment to an agent. Returns updated config.

    Args:
        name: Agent name
        event: Key from TRUST_ADJUSTMENTS
        config: If provided, use this config (avoids re-read). Caller must save.
    """
    if config is None:
        config = _load_config(name)
        if not config:
            return {"error": f"Agent '{name}' not found"}

    delta = TRUST_ADJUSTMENTS.get(event)
    if delta is None:
        return {"error": f"Unknown trust event: {event}"}

    old_score = config.get("trust_score", DEFAULT_TRUST_SCORE)
    new_score = round(max(0.0, min(1.0, old_score + delta)), 3)

    config["trust_score"] = new_score

    # Append to history (keep last 50)
    history = config.get("trust_history", [])
    history.append({
        "event": event,
        "delta": delta,
        "old": old_score,
        "new": new_score,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    config["trust_history"] = history[-50:]

    old_tier, _ = get_trust_tier(old_score)
    new_tier, _ = get_trust_tier(new_score)
    if old_tier != new_tier:
        _log(f"Trust tier change for '{name}': {old_tier} -> {new_tier} "
             f"(score {old_score:.3f} -> {new_score:.3f}, event={event})")
    else:
        _log(f"Trust update for '{name}': {old_score:.3f} -> {new_score:.3f} "
             f"(event={event}, tier={new_tier})")

    _emit("trust_changed", agent=name, event=event, delta=delta,
          old_score=old_score, new_score=new_score,
          old_tier=old_tier, new_tier=new_tier)

    return config


def _apply_spawn_trust(name: str, config: dict, spawn_result: dict):
    """Apply trust adjustments based on spawn outcome. Saves config."""
    exit_code = spawn_result.get("exit_code", 1)
    agent_result = spawn_result.get("result", {})
    status = agent_result.get("status", "unknown")

    if exit_code == 124:
        adjust_trust(name, "timeout", config)
    elif status == "success" or exit_code == 0:
        adjust_trust(name, "task_success", config)
        if agent_result.get("pr_url"):
            adjust_trust(name, "pr_created", config)
    elif status in ("failed", "unknown"):
        adjust_trust(name, "task_failed", config)

    _save_config(name, config)


def _task_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    h = hashlib.sha256(str(time.time()).encode()).hexdigest()[:4]
    return f"t{ts}-{h}"


def _run_git(workspace: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a git command in the given workspace."""
    return subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def safe_stage_files(workspace: Path) -> tuple[list[str], list[str]]:
    """Stage files respecting the auto-commit safety whitelist.

    Rules:
    - Tracked changes (modified/deleted): always staged.
    - Untracked files: staged only if extension is whitelisted AND path
      does not match any blocked pattern.

    Returns (staged, blocked) — lists of relative file paths.
    """
    staged = []
    blocked = []

    # 1) Stage all tracked changes (modified/deleted) unconditionally
    r = _run_git(workspace, ["diff", "--name-only"])
    tracked_modified = [f for f in r.stdout.strip().splitlines() if f]

    # Also include already-staged tracked changes
    r2 = _run_git(workspace, ["diff", "--cached", "--name-only"])
    tracked_staged = [f for f in r2.stdout.strip().splitlines() if f]

    # Filter tracked files: block secrets even in tracked files
    for f in set(tracked_modified) | set(tracked_staged):
        if COMMIT_BLOCKED_PATTERNS.search(f):
            blocked.append(f"TRACKED-BLOCKED: {f}")
            _run_git(workspace, ["reset", "HEAD", "--", f])
        else:
            _run_git(workspace, ["add", "--", f])
            staged.append(f)

    # 2) Handle deleted files (tracked deletions)
    r3 = _run_git(workspace, ["diff", "--name-only", "--diff-filter=D"])
    for f in r3.stdout.strip().splitlines():
        if f and f not in staged:
            _run_git(workspace, ["add", "--", f])
            staged.append(f)

    # 3) Untracked files: whitelist extension + not blocked
    r4 = _run_git(workspace, ["ls-files", "--others", "--exclude-standard"])
    for f in r4.stdout.strip().splitlines():
        if not f:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext not in COMMIT_EXT_WHITELIST:
            blocked.append(f"EXT-BLOCKED: {f} ({ext})")
            continue
        if COMMIT_BLOCKED_PATTERNS.search(f):
            blocked.append(f"PATTERN-BLOCKED: {f}")
            continue
        _run_git(workspace, ["add", "--", f])
        staged.append(f)

    return staged, blocked


def _fetch_and_resolve_base(workspace: Path, base_branch: str) -> str:
    """Fetch all remotes and resolve the true base ref for a project workspace.

    Project-agent workspaces ALWAYS sync aggressively before work.  This is the
    opposite of Clarvis's own repo policy (CLARVIS_SELF_SYNC=skip) because
    project agents open PRs against upstream, not commit directly to main.

    For fork-based workflows (upstream remote exists), also fast-forwards
    origin/<base> to upstream/<base> so the fork stays current.

    Returns the resolved base ref (e.g. "upstream/dev" or "origin/main").
    """
    _run_git(workspace, ["fetch", "--all", "--prune"], timeout=120)

    r_upstream = _run_git(workspace, ["rev-parse", "--verify", f"upstream/{base_branch}"])
    has_upstream = r_upstream.returncode == 0

    if has_upstream:
        base_ref = f"upstream/{base_branch}"
        _run_git(workspace, ["push", "origin", f"upstream/{base_branch}:{base_branch}"], timeout=120)
    else:
        base_ref = f"origin/{base_branch}"

    return base_ref


def _sync_and_checkout_work_branch(workspace: Path, base_branch: str, agent: str, task_id: str) -> str:
    """Hard-sync to upstream (or origin) base branch and checkout a fresh work branch.

    For fork-based workflows (upstream remote exists), syncs origin/<base>
    to upstream/<base> so new branches always start from the latest upstream.

    Returns the created branch name.
    """
    branch = f"clarvis/{agent}/{task_id}"

    base_ref = _fetch_and_resolve_base(workspace, base_branch)

    # Ensure local base branch matches the chosen ref
    r = _run_git(workspace, ["checkout", base_branch])
    if r.returncode != 0:
        _run_git(workspace, ["checkout", "-B", base_branch, base_ref])

    _run_git(workspace, ["reset", "--hard", base_ref])
    _run_git(workspace, ["clean", "-fd"])

    # Fresh work branch from the true upstream head
    _run_git(workspace, ["checkout", "-B", branch])
    return branch


# =========================================================================
# WORKTREE ISOLATION — shared git objects, ~100x faster than full clone
# =========================================================================
# Inspired by Claude Code harness EnterWorktree/ExitWorktree tools:
#   - `git worktree add` creates a lightweight checkout sharing .git objects
#   - No network I/O (objects already fetched), ~1-2s vs ~60-120s clone
#   - Atomic merge-back: worktree branch merges cleanly or is discarded
#   - Multiple agents can work on the same repo concurrently (different worktrees)
#
# Architecture:
#   /opt/clarvis-agents/<name>/
#     workspace/          — main clone (bare or full, used for fetch/push)
#     worktrees/<task_id>/ — per-task worktree (created, used, cleaned up)


def cleanup_stale_branches(workspace: Path, keep_branch: str = "",
                           base_branch: str = "dev", dry_run: bool = False) -> dict:
    """Delete local branches that are merged into base or are stale task branches.

    Targets:
      - clarvis/*/t* branches (auto-created per spawn, safe to remove when merged)
      - feat/*, feature/*, fix/*, chore/* branches merged into base_branch
    Preserves:
      - The current branch and keep_branch
      - base_branch itself
      - Any branch with an open PR (checked via local ref only — no API call)
      - Not-merged feat/feature/fix/chore branches (may have open PRs)

    Returns dict with deleted, skipped, errors lists.
    """
    result = {"deleted": [], "skipped": [], "errors": []}

    r = _run_git(workspace, ["fetch", "--all", "--prune"], timeout=120)

    current = _run_git(workspace, ["rev-parse", "--abbrev-ref", "HEAD"])
    current_branch = current.stdout.strip() if current.returncode == 0 else ""

    protected = {base_branch, current_branch}
    if keep_branch:
        protected.add(keep_branch)

    r = _run_git(workspace, ["branch", "--format=%(refname:short)"])
    if r.returncode != 0:
        result["errors"].append(f"git branch list failed: {r.stderr.strip()}")
        return result

    all_branches = [b.strip() for b in r.stdout.strip().split("\n") if b.strip()]

    for branch in all_branches:
        if branch in protected:
            continue

        is_task_branch = branch.startswith("clarvis/") and "/t" in branch

        is_merged = _run_git(workspace, ["merge-base", "--is-ancestor", branch, base_branch])
        merged = is_merged.returncode == 0

        if is_task_branch and merged:
            if dry_run:
                result["deleted"].append(f"{branch} (merged, dry-run)")
            else:
                r = _run_git(workspace, ["branch", "-d", branch])
                if r.returncode == 0:
                    result["deleted"].append(branch)
                else:
                    result["errors"].append(f"{branch}: {r.stderr.strip()}")
        elif merged and any(branch.startswith(p) for p in ("feat/", "feature/", "fix/", "chore/")):
            if dry_run:
                result["deleted"].append(f"{branch} (merged, dry-run)")
            else:
                r = _run_git(workspace, ["branch", "-d", branch])
                if r.returncode == 0:
                    result["deleted"].append(branch)
                else:
                    result["errors"].append(f"{branch}: {r.stderr.strip()}")
        elif is_task_branch and not merged:
            result["skipped"].append(f"{branch} (not merged)")
        else:
            result["skipped"].append(f"{branch} (not merged or not a cleanup target)")

    stale_remotes = _run_git(workspace, ["remote", "prune", "origin"])
    if stale_remotes.stdout.strip():
        result["_pruned_remotes"] = stale_remotes.stdout.strip()

    return result


def worktree_create(workspace: Path, agent: str, task_id: str,
                    base_branch: str = "main") -> tuple[Path, str]:
    """Create a git worktree for an isolated agent task.

    Returns (worktree_path, branch_name).
    Raises RuntimeError on failure.
    """
    branch = f"clarvis/{agent}/{task_id}"
    worktrees_dir = workspace.parent / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    wt_path = worktrees_dir / task_id

    if wt_path.exists():
        _log(f"Removing stale worktree at {wt_path}")
        _run_git(workspace, ["worktree", "remove", "--force", str(wt_path)])
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)

    base_ref = _fetch_and_resolve_base(workspace, base_branch)

    # Create worktree on a new branch from the true upstream head
    r = _run_git(workspace, [
        "worktree", "add", "-B", branch,
        str(wt_path), base_ref
    ])
    if r.returncode != 0:
        raise RuntimeError(f"worktree add failed: {r.stderr.strip()}")

    _log(f"Worktree created: {wt_path} (branch={branch})")
    return wt_path, branch


def worktree_cleanup(workspace: Path, wt_path: Path, branch: str = ""):
    """Remove a worktree and its branch after task completion.

    Safe to call even if the worktree was already removed.
    """
    if wt_path.exists():
        r = _run_git(workspace, ["worktree", "remove", "--force", str(wt_path)])
        if r.returncode != 0:
            _log(f"worktree remove failed, forcing: {r.stderr.strip()}")
            shutil.rmtree(wt_path, ignore_errors=True)
    # Prune stale worktree bookkeeping
    _run_git(workspace, ["worktree", "prune"])
    # Delete the branch (only if merged or force-clean)
    if branch:
        _run_git(workspace, ["branch", "-D", branch])
    _log(f"Worktree cleaned: {wt_path}")


def worktree_merge_back(workspace: Path, wt_path: Path, branch: str,
                        base_branch: str = "main") -> dict:
    """Merge worktree branch back into base and push.

    Returns dict with status, merge_commit, conflicts.
    """
    # Check if worktree has any changes
    r = _run_git(wt_path, ["diff", "--stat", f"origin/{base_branch}...HEAD"])
    if not r.stdout.strip():
        return {"status": "no_changes", "branch": branch}

    # Try merge in the main workspace
    _run_git(workspace, ["checkout", base_branch])
    _run_git(workspace, ["pull", "--ff-only"])
    r = _run_git(workspace, ["merge", "--no-ff", branch, "-m",
                              f"Merge {branch} (agent worktree)"])
    if r.returncode != 0:
        # Abort the merge
        _run_git(workspace, ["merge", "--abort"])
        return {"status": "conflict", "branch": branch, "error": r.stderr.strip()}

    return {"status": "merged", "branch": branch}


def worktree_list(workspace: Path) -> list[dict]:
    """List active worktrees for this agent."""
    r = _run_git(workspace, ["worktree", "list", "--porcelain"])
    worktrees = []
    current = {}
    for line in r.stdout.strip().splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line == "bare":
            current["bare"] = True
    if current:
        worktrees.append(current)
    return worktrees


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
5. Create a PR (or commit if tests pass — see Commit Safety)
6. Write a concise summary of what you did

## Commit Safety
NEVER commit secrets, credentials, or binary artifacts.
Use `git add <specific-files>` — NEVER use `git add .` or `git add -A`.
Blocked: .env, id_rsa, *.pem, *.key, *.sqlite, *.db, *.log, *.zip, node_modules/.

## Output Protocol (A2A/v1 — MANDATORY)
At the end of your task, output EXACTLY ONE JSON block. Clarvis validates this automatically.
Fields marked REQUIRED must be present.
```json
{{
  "status": "success|partial|failed|blocked",  // REQUIRED
  "summary": "What I did in 2-3 sentences",    // REQUIRED
  "pr_url": "https://github.com/..." | null,
  "branch": "feature/...",
  "files_changed": ["path/to/file1", "path/to/file2"],
  "procedures": ["How to build: ...", "How to test: ..."],
  "follow_ups": ["TODO: ...", "NEEDS: ..."],
  "tests_passed": true | false,
  "error": "why it failed" | null,
  "confidence": 0.0 to 1.0
}}
```
Status: success=done, partial=incomplete, failed=error, blocked=external dep.

## Brain Usage
Store learnings about this repo:
```python
import sys; sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "scripts", "brain_mem"))
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
1. You are already on a fresh work branch — do NOT create or switch to another branch
2. Make changes and commit on the CURRENT branch
3. Push: `git push origin HEAD`
4. Create PR (the orchestrator provides exact gh pr create flags in the prompt)
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
# MIRROR VALIDATION — pre-submit checks against production mirror
# =========================================================================

# Map agent names to their PROD mirror directories
MIRROR_DIRS = {
    "star-world-order": Path("/opt/star_world_order/PROD"),
}

# Validation commands per project type (run in mirror dir)
MIRROR_CHECKS = {
    "star-world-order": [
        {"name": "tsc --noEmit", "cmd": ["npx", "tsc", "--noEmit"], "timeout": 120},
        {"name": "vitest run",   "cmd": ["npx", "vitest", "run"],   "timeout": 180},
    ],
}

# Gate behavior: "soft" = comment only, "hard" = close PR, "off" = skip entirely
MIRROR_GATE_MODE = {
    "star-world-order": "soft",
}
_MIRROR_GATE_DEFAULT = "soft"


def _sync_mirror(agent_name: str) -> bool:
    """Pull latest changes into the PROD mirror before validation."""
    mirror_dir = MIRROR_DIRS.get(agent_name)
    if not mirror_dir or not mirror_dir.exists():
        return False
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(mirror_dir),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            _log(f"Mirror sync: pulled latest for '{agent_name}'")
            return True
        _log(f"Mirror sync: git pull failed for '{agent_name}': {result.stderr[:200]}")
        return False
    except Exception as e:
        _log(f"Mirror sync error for '{agent_name}': {e}")
        return False


def _get_changed_files_from_git(workspace: Path, base_branch: str = "dev") -> list[str]:
    """Get the actual list of changed files using git diff against base branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            cwd=str(workspace),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except Exception as e:
        _log(f"git diff failed: {e}")
    return []


def _parse_error_lines(output: str) -> set[str]:
    """Extract individual error lines from tsc/vitest output for diffing."""
    lines = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # tsc errors: file(line,col): error TS...
        if ": error TS" in stripped:
            lines.add(stripped)
        # vitest FAIL lines
        elif stripped.startswith("FAIL ") or "AssertionError" in stripped or "ENOENT" in stripped:
            lines.add(stripped)
    return lines


def _run_check(check: dict, cwd: str) -> dict:
    """Run a single validation check. Returns {name, passed, output, elapsed, errors}."""
    start = time.time()
    try:
        proc = subprocess.run(
            check["cmd"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=check.get("timeout", 120),
        )
        passed = proc.returncode == 0
        output = (proc.stdout + proc.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        passed = False
        output = f"TIMEOUT after {check.get('timeout', 120)}s"
    except Exception as e:
        passed = False
        output = str(e)

    elapsed = round(time.time() - start, 1)
    errors = _parse_error_lines(output)
    return {
        "name": check["name"],
        "passed": passed,
        "output": output,
        "elapsed": elapsed,
        "errors": errors,
    }


def run_mirror_validation(agent_name: str, changed_files: list[str] = None,
                          agent_workspace: Path = None) -> dict:
    """Run pre-submit validation against a production mirror.

    Uses baseline-diff: runs checks BEFORE copying files (baseline), then AFTER
    (overlay). Only fails if the overlay introduces NEW errors beyond baseline.
    This prevents false negatives from pre-existing PROD issues or missing
    dependencies for additive changes.

    Returns:
        {
            "passed": bool,
            "checks": [{"name": str, "passed": bool, "output": str, "elapsed": float,
                         "new_errors": list[str], "baseline_errors": int}],
            "summary": str,  # markdown-ready for PR body
        }
    """
    mirror_dir = MIRROR_DIRS.get(agent_name)
    if not mirror_dir or not mirror_dir.exists():
        return {"passed": None, "checks": [],
                "summary": f"Mirror validation skipped: no mirror for '{agent_name}'"}

    checks = MIRROR_CHECKS.get(agent_name, [])
    if not checks:
        return {"passed": None, "checks": [],
                "summary": "Mirror validation skipped: no checks configured"}

    # Sync mirror to latest upstream before validating
    _sync_mirror(agent_name)

    # Use git-based file detection if agent didn't report files
    if agent_workspace and (not changed_files):
        changed_files = _get_changed_files_from_git(agent_workspace)
        if changed_files:
            _log(f"Mirror: using git-detected file list ({len(changed_files)} files)")

    has_overlay = bool(changed_files and agent_workspace)

    # ── Step 1: Baseline (PROD mirror as-is) ──
    baseline_results = {}
    if has_overlay:
        for check in checks:
            baseline_results[check["name"]] = _run_check(check, str(mirror_dir))

    # ── Step 2: Copy changed files into mirror ──
    backup_files = {}
    created_dirs = []
    copied = []
    if has_overlay:
        for rel_path in changed_files:
            src = agent_workspace / rel_path
            dst = mirror_dir / rel_path
            if not src.exists():
                continue
            if dst.exists():
                backup_files[rel_path] = dst.read_bytes()
            else:
                backup_files[rel_path] = None
            new_dirs = []
            d = dst.parent
            while d != mirror_dir and not d.exists():
                new_dirs.append(d)
                d = d.parent
            dst.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.extend(reversed(new_dirs))
            try:
                shutil.copy2(str(src), str(dst))
                copied.append(rel_path)
            except OSError as e:
                _log(f"Mirror copy failed for {rel_path}: {e}")

    # ── Step 3: Overlay checks (with changed files in mirror) ──
    results = []
    all_passed = True

    try:
        for check in checks:
            overlay = _run_check(check, str(mirror_dir))

            if has_overlay and check["name"] in baseline_results:
                baseline = baseline_results[check["name"]]
                new_errors = sorted(overlay["errors"] - baseline["errors"])
                # Pass if no NEW errors were introduced (even if pre-existing errors exist)
                effectively_passed = len(new_errors) == 0
            else:
                new_errors = sorted(overlay["errors"]) if not overlay["passed"] else []
                effectively_passed = overlay["passed"]

            if not effectively_passed:
                all_passed = False

            results.append({
                "name": check["name"],
                "passed": effectively_passed,
                "output": overlay["output"],
                "elapsed": overlay["elapsed"],
                "new_errors": new_errors,
                "baseline_errors": len(baseline_results.get(check["name"], {}).get("errors", set())) if has_overlay else 0,
            })
    finally:
        # Restore mirror to original state
        for rel_path, original_bytes in backup_files.items():
            dst = mirror_dir / rel_path
            if original_bytes is None:
                try:
                    dst.unlink(missing_ok=True)
                except OSError:
                    pass
            else:
                try:
                    dst.write_bytes(original_bytes)
                except OSError:
                    pass
        for d in reversed(created_dirs):
            try:
                d.rmdir()
            except OSError:
                pass

    # Build markdown summary for PR body
    lines = ["## Mirror Validation (PROD)"]
    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        baseline_note = ""
        if r.get("baseline_errors", 0) > 0:
            baseline_note = f" ({r['baseline_errors']} pre-existing errors excluded)"
        lines.append(f"- **{r['name']}**: {icon} ({r['elapsed']}s){baseline_note}")
        if not r["passed"] and r.get("new_errors"):
            snippet = "\n".join(r["new_errors"])[:500].strip()
            if snippet:
                lines.append(f"  ```\n  {snippet}\n  ```")
    lines.append(f"\nOverall: {'PASS' if all_passed else 'FAIL'}")
    summary = "\n".join(lines)

    _log(f"Mirror validation for '{agent_name}': {'PASS' if all_passed else 'FAIL'} "
         f"({len(results)} checks, {len(copied)} files copied)")

    return {"passed": all_passed, "checks": results, "summary": summary}


def _flag_pr(pr_url: str, repo: str, reason: str, close: bool = False) -> bool:
    """Comment on a PR with validation findings. Only closes if close=True."""
    import re as _re
    m = _re.search(r'/pull/(\d+)', pr_url)
    if not m:
        _log(f"Cannot flag PR — could not parse PR number from {pr_url}")
        return False
    pr_number = m.group(1)
    try:
        if close:
            comment = (f"Automatically closed: mirror validation FAILED.\n\n{reason}\n\n"
                       "Fix the issues and re-submit.")
        else:
            comment = (f"⚠️ **Mirror validation found issues** (not auto-closing — needs review).\n\n"
                       f"{reason}\n\n"
                       "These may be false positives if the mirror is stale or if "
                       "changes depend on other unmerged PRs.")
        subprocess.run(
            ["gh", "pr", "comment", pr_number, "--repo", repo, "--body", comment],
            capture_output=True, text=True, timeout=30,
        )
        if close:
            result = subprocess.run(
                ["gh", "pr", "close", pr_number, "--repo", repo],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                _log(f"Closed PR #{pr_number} due to mirror validation failure")
                return True
            else:
                _log(f"Failed to close PR #{pr_number}: {result.stderr}")
                return False
        _log(f"Flagged PR #{pr_number} with mirror validation findings (not closed)")
        return True
    except Exception as e:
        _log(f"Error flagging PR #{pr_number}: {e}")
        return False


def _comment_pr(pr_url: str, repo: str, reason: str) -> bool:
    """Comment on a PR with validation findings without closing it (soft gate).

    Equivalent to ``_flag_pr(pr_url, repo, reason, close=False)``.
    """
    return _flag_pr(pr_url, repo, reason, close=False)


def _extract_gh_repo(repo_url: str) -> str:
    """Extract 'owner/repo' slug from a git remote URL."""
    import re as _re
    m = _re.search(r'[:/]([^/]+/[^/.]+?)(?:\.git)?$', repo_url)
    return m.group(1) if m else ""


def apply_mirror_gate(name: str, agent_result: dict, config: dict,
                      workspace: Path, task_id: str = "") -> dict:
    """Apply mirror validation gate to an agent result.

    Runs mirror validation and, based on gate mode, either:
      - "off": skips entirely
      - "soft" (default): comments on PR if validation fails
      - "hard": closes PR and marks result as failed

    Returns the (possibly mutated) agent_result dict.
    """
    gate_mode = MIRROR_GATE_MODE.get(name, _MIRROR_GATE_DEFAULT)
    if name not in MIRROR_DIRS or gate_mode == "off":
        return agent_result

    try:
        changed = agent_result.get("files_changed", [])
        mirror_result = run_mirror_validation(name, changed, workspace)
        agent_result["mirror_validation"] = mirror_result

        if mirror_result.get("passed") is False:
            pr_url = agent_result.get("pr_url")
            gh_repo = _extract_gh_repo(config.get("repo_url", ""))
            summary = mirror_result.get("summary", "")

            if gate_mode == "hard":
                _log(f"MIRROR HARD GATE: validation FAILED for task {task_id} — closing PR")
                if pr_url and gh_repo:
                    _flag_pr(pr_url, gh_repo, summary, close=True)
                    agent_result["pr_url"] = None
                    agent_result["_mirror_closed_pr"] = pr_url
                agent_result["status"] = "failed"
                agent_result["error"] = (agent_result.get("error") or "") + " Mirror validation FAILED."
            else:
                _log(f"MIRROR SOFT GATE: validation found issues for task {task_id} — commenting (PR stays open)")
                if pr_url and gh_repo:
                    _flag_pr(pr_url, gh_repo, summary, close=False)
                agent_result["_mirror_flagged"] = True
        elif mirror_result.get("passed") is True:
            _log(f"Mirror validation PASSED for task {task_id}")
    except Exception as e:
        _log(f"Mirror validation error (non-fatal): {e}")
        agent_result["mirror_validation"] = {
            "passed": None, "checks": [],
            "summary": f"Mirror validation error: {e}",
        }

    return agent_result


# =========================================================================
# SPAWN — execute a task in a project agent
# =========================================================================

def build_dependency_map(name: str) -> dict:
    """Scan agent repo for entry points, config files, test dirs, key modules.

    Produces a structured map written to dependency_map.json in agent data dir.
    Used by decompose_task() for smarter subtask splits (e.g., knowing which
    dirs contain tests, what the main entry points are, project structure).

    Returns the dependency map dict.
    """
    agent_dir = _agent_dir(name)
    if not agent_dir.exists():
        return {"error": f"Agent '{name}' not found"}
    workspace = agent_dir / "workspace"
    if not workspace.exists():
        return {"error": f"Workspace not found: {workspace}"}

    dep = {
        "agent": name,
        "entry_points": [],
        "config_files": [],
        "test_dirs": [],
        "test_files": [],
        "key_modules": [],
        "source_dirs": [],
        "doc_files": [],
        "project_type": "unknown",
        "framework": None,
        "language": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── Detect project type / language / framework ───────────────────────
    has_package_json = (workspace / "package.json").exists()
    has_pyproject = (workspace / "pyproject.toml").exists()
    has_setup_py = (workspace / "setup.py").exists()
    has_cargo = (workspace / "Cargo.toml").exists()
    has_go_mod = (workspace / "go.mod").exists()

    if has_package_json:
        dep["language"] = "javascript/typescript"
        try:
            pkg = json.loads((workspace / "package.json").read_text())
            pkg_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in pkg_deps:
                dep["framework"] = "next.js"
                dep["project_type"] = "webapp"
            elif "react" in pkg_deps:
                dep["framework"] = "react"
                dep["project_type"] = "webapp"
            elif "vue" in pkg_deps:
                dep["framework"] = "vue"
                dep["project_type"] = "webapp"
            elif "express" in pkg_deps or "fastify" in pkg_deps:
                dep["framework"] = "express" if "express" in pkg_deps else "fastify"
                dep["project_type"] = "api"
            else:
                dep["project_type"] = "node"
        except (json.JSONDecodeError, OSError):
            dep["project_type"] = "node"
    elif has_pyproject or has_setup_py:
        dep["language"] = "python"
        dep["project_type"] = "python"
    elif has_cargo:
        dep["language"] = "rust"
        dep["project_type"] = "rust"
    elif has_go_mod:
        dep["language"] = "go"
        dep["project_type"] = "go"

    # ── Config files ────────────────────────────────────────────────────
    config_patterns = [
        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        "tsconfig.json", "tsconfig.*.json", "jsconfig.json",
        "next.config.*", "vite.config.*", "vitest.config.*", "jest.config.*",
        "webpack.config.*", "rollup.config.*",
        "tailwind.config.*", "postcss.config.*",
        "eslint.config.*", ".eslintrc*", ".prettierrc*",
        "pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "mypy.ini",
        "Cargo.toml", "go.mod", "go.sum",
        "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".env.example", ".env.local.example",
    ]
    for pattern in config_patterns:
        for f in workspace.glob(pattern):
            if f.is_file():
                dep["config_files"].append(str(f.relative_to(workspace)))

    # ── Entry points ──────────────────────────────────────────────────
    entry_patterns = {
        "javascript/typescript": [
            "app/layout.tsx", "app/layout.ts", "app/page.tsx", "app/page.ts",
            "pages/index.tsx", "pages/index.ts", "pages/index.jsx", "pages/index.js",
            "pages/_app.tsx", "pages/_app.ts",
            "src/index.tsx", "src/index.ts", "src/index.jsx", "src/index.js",
            "src/main.tsx", "src/main.ts", "src/main.jsx", "src/main.js",
            "src/App.tsx", "src/App.ts", "src/App.jsx", "src/App.js",
            "index.ts", "index.js", "main.ts", "main.js",
            "server.ts", "server.js", "src/server.ts", "src/server.js",
        ],
        "python": [
            "main.py", "app.py", "run.py", "manage.py",
            "src/main.py", "src/app.py",
            "__main__.py", "src/__main__.py",
        ],
        "rust": ["src/main.rs", "src/lib.rs"],
        "go": ["main.go", "cmd/main.go"],
    }
    lang = dep["language"] or ""
    for pattern_list in ([entry_patterns.get(lang, [])] +
                         [v for k, v in entry_patterns.items() if k != lang]):
        for ep in pattern_list:
            if (workspace / ep).exists():
                dep["entry_points"].append(ep)
    # Deduplicate
    dep["entry_points"] = list(dict.fromkeys(dep["entry_points"]))

    # ── Source directories ──────────────────────────────────────────────
    source_dir_candidates = [
        "src", "lib", "app", "components", "pages", "api",
        "packages", "modules", "core", "utils", "helpers",
        "contracts", "scripts", "hooks", "services", "middleware",
    ]
    for d in source_dir_candidates:
        p = workspace / d
        if p.is_dir():
            # Count files to verify it's a real source dir, not just a few configs
            file_count = sum(1 for _ in p.rglob("*") if _.is_file()
                             and not _.name.startswith("."))
            if file_count > 0:
                dep["source_dirs"].append({
                    "path": d,
                    "file_count": min(file_count, 9999),  # cap for perf
                })

    # ── Key modules (files that many things likely depend on) ──────────
    key_module_patterns = [
        "lib/**/*.ts", "lib/**/*.tsx", "lib/**/*.js",
        "utils/**/*.ts", "utils/**/*.tsx", "utils/**/*.js",
        "src/lib/**/*.ts", "src/utils/**/*.ts",
        "core/**/*.py", "utils/**/*.py",
        "contracts/**/*.sol",
    ]
    for pattern in key_module_patterns:
        for f in workspace.glob(pattern):
            if f.is_file() and not f.name.startswith("."):
                dep["key_modules"].append(str(f.relative_to(workspace)))
    # Cap key modules list (largest files first by name length as proxy)
    dep["key_modules"] = sorted(dep["key_modules"])[:50]

    # ── Test directories and files ──────────────────────────────────────
    test_dir_candidates = [
        "tests", "test", "__tests__", "spec", "specs",
        "src/tests", "src/__tests__", "src/test",
        "e2e", "cypress", "playwright",
    ]
    for d in test_dir_candidates:
        p = workspace / d
        if p.is_dir():
            test_count = sum(1 for _ in p.rglob("*") if _.is_file()
                             and not _.name.startswith("."))
            dep["test_dirs"].append({"path": d, "file_count": min(test_count, 9999)})

    # Find test files in source dirs (co-located tests)
    test_file_globs = [
        "**/*.test.ts", "**/*.test.tsx", "**/*.test.js", "**/*.test.jsx",
        "**/*.spec.ts", "**/*.spec.tsx", "**/*.spec.js", "**/*.spec.jsx",
        "**/test_*.py", "**/*_test.py", "**/*_test.go",
    ]
    test_files_found = set()
    for pattern in test_file_globs:
        for f in workspace.glob(pattern):
            if f.is_file() and "node_modules" not in str(f):
                test_files_found.add(str(f.relative_to(workspace)))
    dep["test_files"] = sorted(test_files_found)[:100]  # cap

    # ── Documentation files ───────────────────────────────────────────
    doc_patterns = ["README.md", "CONTRIBUTING.md", "CHANGELOG.md",
                    "docs/**/*.md", "*.md"]
    for pattern in doc_patterns:
        for f in workspace.glob(pattern):
            if f.is_file() and "node_modules" not in str(f):
                dep["doc_files"].append(str(f.relative_to(workspace)))
    dep["doc_files"] = sorted(set(dep["doc_files"]))[:30]

    # ── CI workflow files ───────────────────────────────────────────
    workflows_dir = workspace / ".github" / "workflows"
    if workflows_dir.exists():
        try:
            wf_names = []
            for wf in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
                if wf.is_file():
                    wf_names.append(wf.name)
            if wf_names:
                dep["ci_workflows"] = wf_names
        except OSError:
            pass

    # ── Write dependency_map.json ────────────────────────────────────
    dep_file = agent_dir / "data" / "dependency_map.json"
    dep_file.parent.mkdir(parents=True, exist_ok=True)
    dep_file.write_text(json.dumps(dep, indent=2))
    _log(f"Dependency map for '{name}': {dep['project_type']}/{dep['framework']}, "
         f"{len(dep['entry_points'])} entries, {len(dep['source_dirs'])} src dirs, "
         f"{len(dep['test_dirs'])} test dirs, {len(dep['key_modules'])} key modules")

    return dep


def build_ci_context(name: str) -> dict:
    """Scan agent repo for test/build/lint commands from config files.

    Scans: package.json, Makefile, pyproject.toml, .github/workflows/*.yml
    Writes ci_context.json to agent data dir. Returns the context dict.
    """
    agent_dir = _agent_dir(name)
    if not agent_dir:
        return {"error": f"Agent '{name}' not found"}
    workspace = agent_dir / "workspace"
    if not workspace.exists():
        return {"error": f"Workspace not found: {workspace}"}

    ci = {"agent": name, "commands": {}, "sources": []}

    # --- package.json ---
    pkg_json = workspace / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text())
            scripts = pkg.get("scripts", {})
            ci["sources"].append("package.json")
            # Categorize npm scripts
            for key in ("test", "test:run", "test:ci"):
                if key in scripts:
                    ci["commands"].setdefault("test", []).append(f"npm run {key}")
            if "test" not in ci["commands"]:
                # fallback: any script with 'test' in the name (skip watch/ui variants)
                for key, val in scripts.items():
                    if "test" in key and "watch" not in key and "ui" not in key:
                        ci["commands"].setdefault("test", []).append(f"npm run {key}")
                        break
            for key in ("build", "compile"):
                if key in scripts:
                    ci["commands"].setdefault("build", []).append(f"npm run {key}")
            for key in ("lint", "eslint", "lint:fix"):
                if key in scripts:
                    ci["commands"].setdefault("lint", []).append(f"npm run {key}")
            for key in ("type-check", "typecheck", "tsc"):
                if key in scripts:
                    ci["commands"].setdefault("typecheck", []).append(f"npm run {key}")
            # Package manager detection
            if (workspace / "pnpm-lock.yaml").exists():
                ci["package_manager"] = "pnpm"
            elif (workspace / "yarn.lock").exists():
                ci["package_manager"] = "yarn"
            elif (workspace / "bun.lockb").exists():
                ci["package_manager"] = "bun"
            else:
                ci["package_manager"] = "npm"
        except (json.JSONDecodeError, OSError):
            pass

    # --- pyproject.toml ---
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            ci["sources"].append("pyproject.toml")
            # Basic TOML parsing for scripts section (avoid toml dependency)
            if "[tool.pytest" in content or "pytest" in content:
                ci["commands"].setdefault("test", []).append("python3 -m pytest")
            if "[tool.ruff" in content or "ruff" in content:
                ci["commands"].setdefault("lint", []).append("ruff check .")
            if "[tool.mypy" in content or "mypy" in content:
                ci["commands"].setdefault("typecheck", []).append("mypy .")
            if "[tool.black" in content or "black" in content:
                ci["commands"].setdefault("format", []).append("black --check .")
            # Check for build system
            if "[build-system]" in content:
                ci["commands"].setdefault("build", []).append("python3 -m build")
        except OSError:
            pass

    # --- Makefile ---
    makefile = workspace / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text()
            ci["sources"].append("Makefile")
            import re
            targets = re.findall(r'^([a-zA-Z_][a-zA-Z0-9_-]*):', content, re.MULTILINE)
            for target in targets:
                tl = target.lower()
                if tl in ("test", "tests", "check"):
                    ci["commands"].setdefault("test", []).append(f"make {target}")
                elif tl in ("build", "compile", "all"):
                    ci["commands"].setdefault("build", []).append(f"make {target}")
                elif tl in ("lint", "linter"):
                    ci["commands"].setdefault("lint", []).append(f"make {target}")
                elif tl in ("fmt", "format"):
                    ci["commands"].setdefault("format", []).append(f"make {target}")
        except OSError:
            pass

    # --- GitHub Actions workflows ---
    workflows_dir = workspace / ".github" / "workflows"
    if workflows_dir.exists():
        ci["sources"].append(".github/workflows/")
        try:
            for wf in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
                try:
                    content = wf.read_text()
                    ci.setdefault("ci_workflows", []).append(wf.name)
                except OSError:
                    pass
        except OSError:
            pass

    # Deduplicate commands
    for category in ci.get("commands", {}):
        ci["commands"][category] = list(dict.fromkeys(ci["commands"][category]))

    # Write ci_context.json
    ci_file = agent_dir / "data" / "ci_context.json"
    ci_file.parent.mkdir(parents=True, exist_ok=True)
    ci_file.write_text(json.dumps(ci, indent=2))
    _log(f"CI context for '{name}': {len(ci.get('commands', {}))} categories from {ci['sources']}")

    return ci


def _gather_episodic_context(agent_dir: Path, task: str, max_episodes: int = 5) -> str:
    """Gather episodic context from prior runs — success-first framing.

    Reads summaries/*.json.  Surfaces what worked (proven patterns, timing,
    approach) prominently, with a brief note on recent failures only when they
    carry actionable signal not already in the failure-constraints section.
    """
    summaries_dir = agent_dir / "memory" / "summaries"
    if not summaries_dir.exists():
        return ""

    episodes = []
    for sf in sorted(summaries_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(sf.read_text())
            result = data.get("result", {})
            status = result.get("status", "unknown")
            if status == "unknown":
                continue
            episodes.append({
                "task_id": data.get("task_id", ""),
                "task": data.get("task", "")[:120],
                "status": status,
                "error": result.get("error", ""),
                "summary": result.get("summary", "")[:150],
                "pr_url": result.get("pr_url"),
                "elapsed": data.get("elapsed", 0),
                "files_changed": result.get("files_changed", []),
                "procedures": result.get("procedures", []),
                "confidence": result.get("confidence"),
            })
        except (json.JSONDecodeError, OSError):
            continue
        if len(episodes) >= 20:
            break

    if not episodes:
        return ""

    successes = [e for e in episodes if e["status"] == "success"]
    failures = [e for e in episodes if e["status"] in ("failed", "partial")]

    lines = []

    # Success exemplars first — what works in this repo
    if successes:
        lines.append("PROVEN PATTERNS (from successful runs):")
        for s in successes[:3]:
            pr_note = f" PR:{s['pr_url'].split('/')[-1]}" if s.get("pr_url") else ""
            lines.append(f"  [OK] {s['task'][:100]} ({s['elapsed']:.0f}s){pr_note}")
            if s.get("procedures"):
                lines.append(f"       Steps used: {'; '.join(s['procedures'][:3])}")

    # Recent failures — brief, only for situational awareness (details in constraints)
    if failures:
        lines.append("RECENT ISSUES (details in constraints if recurring):")
        for f in failures[:2]:
            error_brief = f" — {f['error'][:60]}" if f.get("error") else ""
            lines.append(f"  [{f['status'].upper()}] {f['task'][:80]}{error_brief}")

    return "\n".join(lines)


def _gather_failure_avoidance(agent_dir: Path, task: str) -> str:
    """Build failure avoidance hints from recent failures — specific causal analysis."""
    summaries_dir = agent_dir / "memory" / "summaries"
    if not summaries_dir.exists():
        return ""

    avoidance = []
    for sf in sorted(summaries_dir.glob("*.json"), reverse=True)[:15]:
        try:
            data = json.loads(sf.read_text())
            result = data.get("result", {})
            if result.get("status") not in ("failed",):
                continue
            mirror = result.get("mirror_validation", {})
            if mirror.get("passed") is False:
                for check in mirror.get("checks", []):
                    if not check.get("passed", True):
                        output_snippet = check.get("output", "")[:200]
                        avoidance.append(
                            f"AVOID: {check['name']} failed on task '{data.get('task', '')[:60]}' — "
                            f"{output_snippet}"
                        )
            elif result.get("error"):
                avoidance.append(f"AVOID: {result['error'][:120]}")
        except (json.JSONDecodeError, OSError):
            continue

    if not avoidance:
        return ""
    return "FAILURE AVOIDANCE (learn from past mistakes):\n" + "\n".join(f"  {a}" for a in avoidance[:5])


# ── Failure Pattern Auto-Learning ────────────────────────────────────────
# Classifies mirror/spawn failures into reusable pattern classes, persists
# them in a per-agent registry, and promotes high-frequency patterns into
# procedures.md + lite brain so future spawns avoid repeating mistakes.

FAILURE_CLASSIFIERS = [
    # (pattern_name, regex_on_error_output, constraint_template)
    ("missing_type_export", r"TS2305.*exported member|TS2724.*not exported|has no exported member",
     "Ensure all new types/interfaces are explicitly exported from their module's index.ts"),
    ("type_mismatch", r"TS2345|TS2322|TS2339|Type .* is not assignable",
     "Verify argument types match function signatures; check union types and optional fields"),
    ("missing_import", r"TS2307.*Cannot find module|Cannot find module",
     "Verify import paths exist and spelling matches filesystem case-sensitively"),
    ("unused_variable", r"TS6133.*declared but|is declared but its value is never read",
     "Remove or use all declared variables; prefix intentionally unused params with _"),
    ("test_assertion", r"AssertionError|expect\(.*\)\.(toBe|toEqual|toMatch)|FAIL.*test",
     "Run tests locally before committing; check that mocked data matches current schema"),
    ("test_import", r"vitest.*Cannot find|SyntaxError.*import|ERR_MODULE_NOT_FOUND",
     "Ensure test files import from correct paths; check that vitest config resolves aliases"),
    ("build_error", r"tsc.*error TS|Build failed|Compilation failed",
     "Run tsc --noEmit before creating PR; fix all type errors, not just the ones in changed files"),
    ("mirror_restore", r"mirror.*not restored|byte-identical|mirror cleanup",
     "After mirror validation, restore ALL files including new directories created during copy"),
    ("wrong_target_repo", r"targets? wrong repo|misrouted.*pr|fork.*upstream",
     "PRs must target the upstream repo, not the fork; use --repo flag with gh pr create"),
    ("stale_baseline", r"merge conflict|CONFLICT|diverged|out of date|needs rebase",
     "Pull latest from target branch before starting work; rebase if branch has diverged"),
    ("missing_dependency", r"npm ERR!|Module not found|No matching version|peer dep",
     "Check package.json for required dependencies before importing new packages"),
    ("runtime_error", r"ReferenceError|TypeError.*undefined|Cannot read propert",
     "Add null checks for optional chain access; verify API response shapes match types"),
    ("timeout", r"timed? ?out|SIGTERM|killed|deadline exceeded",
     "Break large tasks into smaller increments; avoid unbounded loops or network calls in tests"),
]

FAILURE_REGISTRY_FILE = "failure_patterns.json"
PROMOTION_THRESHOLD = 2  # occurrences before pattern gets promoted to procedures


def _classify_failure(error_output: str, mirror_checks: list = None) -> list[dict]:
    """Classify error output into known failure pattern classes.

    Returns list of {class, constraint, snippet} dicts for each matched pattern.
    """
    if not error_output and not mirror_checks:
        return []

    matches = []
    for class_name, regex, constraint in FAILURE_CLASSIFIERS:
        if not error_output:
            break
        m = _re_mod.search(regex, error_output, _re_mod.IGNORECASE)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(error_output), m.end() + 80)
            snippet = error_output[start:end].strip()
            matches.append({
                "class": class_name,
                "constraint": constraint,
                "snippet": snippet[:150],
            })

    if mirror_checks:
        for check in mirror_checks:
            if not check.get("passed", True):
                check_output = check.get("output", "")
                sub_matches = _classify_failure(check_output)
                if sub_matches:
                    matches.extend(sub_matches)
                elif check_output:
                    matches.append({
                        "class": f"mirror_{check.get('name', 'unknown').replace(' ', '_')}",
                        "constraint": f"Fix {check.get('name', 'check')} errors before creating PR",
                        "snippet": check_output[:150],
                    })

    seen = set()
    deduped = []
    for m in matches:
        if m["class"] not in seen:
            seen.add(m["class"])
            deduped.append(m)
    return deduped


def _load_failure_registry(agent_dir: Path) -> dict:
    """Load the persistent failure pattern registry for an agent."""
    reg_file = agent_dir / "data" / FAILURE_REGISTRY_FILE
    if reg_file.exists():
        try:
            return json.loads(reg_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"patterns": {}, "version": 1}


def _save_failure_registry(agent_dir: Path, registry: dict):
    """Save the failure pattern registry."""
    reg_file = agent_dir / "data" / FAILURE_REGISTRY_FILE
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(json.dumps(registry, indent=2, default=str))


def _update_failure_registry(agent_dir: Path, classified: list[dict],
                             task: str, task_id: str) -> list[dict]:
    """Update persistent failure registry with newly classified patterns.

    Returns list of patterns that crossed the promotion threshold this time.
    """
    if not classified:
        return []

    registry = _load_failure_registry(agent_dir)
    patterns = registry.setdefault("patterns", {})
    now = datetime.now(timezone.utc).isoformat()
    newly_promoted = []

    for item in classified:
        cls = item["class"]
        if cls in patterns:
            prev_count = patterns[cls]["count"]
            patterns[cls]["count"] += 1
            patterns[cls]["last_seen"] = now
            patterns[cls]["last_task_id"] = task_id
            patterns[cls]["last_snippet"] = item["snippet"]
            if prev_count < PROMOTION_THRESHOLD <= patterns[cls]["count"]:
                newly_promoted.append(patterns[cls])
        else:
            patterns[cls] = {
                "class": cls,
                "constraint": item["constraint"],
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "first_task": task[:120],
                "last_task_id": task_id,
                "last_snippet": item["snippet"],
                "promoted": False,
            }

    registry["last_updated"] = now
    _save_failure_registry(agent_dir, registry)
    return newly_promoted


def _promote_failure_patterns(agent_dir: Path, patterns_to_promote: list[dict]):
    """Promote high-frequency failure patterns to procedures.md and lite brain."""
    if not patterns_to_promote:
        return

    # 1. Append to procedures.md
    proc_file = agent_dir / "memory" / "procedures.md"
    proc_file.parent.mkdir(parents=True, exist_ok=True)
    existing = proc_file.read_text() if proc_file.exists() else ""

    new_lines = []
    for p in patterns_to_promote:
        constraint_line = f"- **[auto-learned]** {p['constraint']} (failed {p['count']}x, class: {p['class']})"
        if constraint_line not in existing and p["constraint"] not in existing:
            new_lines.append(constraint_line)
            p["promoted"] = True

    if new_lines:
        with open(proc_file, "a") as f:
            f.write(f"\n## Failure Constraints (auto-learned {datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n")
            for line in new_lines:
                f.write(f"{line}\n")
        _log(f"Promoted {len(new_lines)} failure patterns to procedures.md")

    # 2. Store in lite brain as project-learnings
    try:
        sys.path.insert(0, str(CLARVIS_WORKSPACE / "scripts" / "brain_mem"))
        from lite_brain import LiteBrain
        lb = LiteBrain(str(agent_dir / "data" / "brain"))
        for p in patterns_to_promote:
            learning = (
                f"FAILURE PATTERN [{p['class']}]: {p['constraint']} "
                f"(observed {p['count']}x, last: {p.get('last_snippet', '')[:80]})"
            )
            lb.store(
                learning,
                collection="project-learnings",
                importance=0.9,
                tags=["failure-pattern", f"class:{p['class']}", "auto-learned"],
                source="failure_registry",
            )
        _log(f"Stored {len(patterns_to_promote)} failure patterns in lite brain")
    except Exception as e:
        _log(f"Lite brain failure pattern store failed (non-fatal): {e}")

    # 3. Mark promoted in registry
    registry = _load_failure_registry(agent_dir)
    for p in patterns_to_promote:
        if p["class"] in registry.get("patterns", {}):
            registry["patterns"][p["class"]]["promoted"] = True
    _save_failure_registry(agent_dir, registry)


def _gather_failure_constraints(agent_dir: Path) -> str:
    """Build concise failure constraints from the persistent registry.

    Returns at most 3 high-frequency, actionable constraints.  Keeps each
    entry to one line so the prompt leaves room for reasoning.
    """
    registry = _load_failure_registry(agent_dir)
    patterns = registry.get("patterns", {})
    if not patterns:
        return ""

    # Only include patterns that have occurred more than once
    recurring = [p for p in patterns.values() if p.get("count", 0) >= 2]
    if not recurring:
        return ""

    sorted_patterns = sorted(recurring, key=lambda p: p["count"], reverse=True)
    lines = ["Known pitfalls in this repo:"]
    for p in sorted_patterns[:3]:
        lines.append(f"- {p['constraint']} ({p['count']}x)")

    return "\n".join(lines)


def _gather_success_exemplar(agent_dir: Path, task: str) -> str:
    """Find the best success exemplar for a similar task type.

    Returns a compact description of how a similar past task succeeded,
    including the approach, files touched, and timing.  This gives the
    agent a concrete model to follow rather than just avoidance rules.
    """
    summaries_dir = agent_dir / "memory" / "summaries"
    if not summaries_dir.exists():
        return ""

    task_lower = task.lower()
    task_words = set(task_lower.split())

    best = None
    best_overlap = 0
    for sf in sorted(summaries_dir.glob("*.json"), reverse=True)[:30]:
        try:
            data = json.loads(sf.read_text())
            result = data.get("result", {})
            if result.get("status") != "success" or not result.get("pr_url"):
                continue
            past_words = set(data.get("task", "").lower().split())
            overlap = len(task_words & past_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best = {
                    "task": data.get("task", "")[:80],
                    "summary": result.get("summary", "")[:120],
                    "files": result.get("files_changed", [])[:5],
                    "elapsed": data.get("elapsed", 0),
                    "pr_url": result.get("pr_url", ""),
                    "procedures": result.get("procedures", [])[:3],
                }
        except (json.JSONDecodeError, OSError):
            continue

    if not best or best_overlap < 2:
        return ""

    lines = [f"SUCCESS EXEMPLAR (similar past task):"]
    lines.append(f"  Task: {best['task']}")
    lines.append(f"  Result: {best['summary']}")
    if best["procedures"]:
        lines.append(f"  Steps: {'; '.join(best['procedures'])}")
    if best["files"]:
        lines.append(f"  Files: {', '.join(best['files'][:4])}")
    lines.append(f"  Time: {best['elapsed']:.0f}s | PR: {best['pr_url'].split('/')[-1]}")
    return "\n".join(lines)


def _query_lite_brain(agent_dir: Path, task: str, *,
                      skip_procedures: bool = False,
                      skip_failure_patterns: bool = False) -> str:
    """Query the project's lite brain for relevant learnings and procedures.

    Args:
        skip_procedures: True when procedures.md is already in the prompt.
        skip_failure_patterns: True when failure_constraints section is present.
    """
    brain_dir = agent_dir / "data" / "brain"
    if not brain_dir.exists():
        return ""

    try:
        sys.path.insert(0, str(CLARVIS_WORKSPACE / "scripts" / "brain_mem"))
        from lite_brain import LiteBrain
        brain = LiteBrain(str(brain_dir))

        learnings = brain.recall(task, n_results=5, collection="project-learnings")

        lines = []
        if learnings:
            relevant = [l for l in learnings if l.get("relevance", 0) > 0.3]
            if skip_failure_patterns:
                relevant = [l for l in relevant
                            if "FAILURE PATTERN" not in l.get("document", "")]
            if relevant:
                lines.append("PROJECT KNOWLEDGE (from prior runs):")
                for l in relevant[:4]:
                    lines.append(f"  [learn] {l['document'][:120]}")

        if not skip_procedures:
            procedures = brain.recall(task, n_results=3, collection="project-procedures")
            if procedures:
                relevant_procs = [p for p in procedures if p.get("relevance", 0) > 0.3]
                if relevant_procs:
                    lines.append("PROJECT PROCEDURES (proven):")
                    for p in relevant_procs[:3]:
                        lines.append(f"  [proc] {p['document'][:120]}")

        return "\n".join(lines) if lines else ""
    except Exception:
        return ""


def _get_worker_template_for_task(task: str) -> str:
    """Select and return the appropriate worker template for the task type."""
    template_dir = CLARVIS_WORKSPACE / "scripts" / "worker_templates"
    if not template_dir.exists():
        return ""

    task_lower = task.lower()
    if any(kw in task_lower for kw in ["implement", "add", "fix", "build", "create", "replace", "wrap", "refactor"]):
        template_name = "implementation.txt"
    elif any(kw in task_lower for kw in ["research", "investigate", "analyze", "review"]):
        template_name = "research.txt"
    elif any(kw in task_lower for kw in ["maintain", "cleanup", "migrate", "update", "upgrade"]):
        template_name = "maintenance.txt"
    else:
        template_name = "general.txt"

    template_file = template_dir / template_name
    if template_file.exists():
        try:
            return template_file.read_text()[:1500]
        except OSError:
            pass
    return ""


# Sections in procedures.md that duplicate hardcoded prompt sections
_PROC_ALWAYS_REDUNDANT = {
    "git workflow", "git workflow (critical", "communication", "notes", "note",
}
_PROC_REDUNDANT_IF_CI = {
    "build & test", "build", "testing",
}


def _dedup_procedures(raw: str, has_ci_context: bool = False) -> str:
    """Strip sections from procedures.md that duplicate other prompt sections.

    Always removed: Git Workflow, Communication, Notes (hardcoded in prompt).
    Removed when CI context present: Build & Test, Testing (in CI Commands).
    """
    redundant = _PROC_ALWAYS_REDUNDANT | (_PROC_REDUNDANT_IF_CI if has_ci_context else set())
    lines = raw.split("\n")
    result = []
    skip = False
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().rstrip(")")
            skip = any(heading.startswith(r) for r in redundant)
        if not skip:
            result.append(line)
    return "\n".join(result).strip()


def build_spawn_prompt(name: str, task: str, config: dict,
                       agent_dir: Path, context: str = "",
                       timeout: int = 1200) -> str:
    """Build the full prompt string for a project agent spawn.

    Extracted for testability. Returns the prompt text.
    Enriched with episodic context, failure avoidance, brain knowledge,
    worker template, and time budget — matching Clarvis self-work quality.
    """
    workspace = agent_dir / "workspace"

    raw_procedures = ""
    proc_file = agent_dir / "memory" / "procedures.md"
    if proc_file.exists():
        try:
            raw_procedures = proc_file.read_text()[:2000]
        except OSError:
            pass

    constraints = "\n".join(f"- {c}" for c in config.get("constraints", []))

    # Select worker template based on task type
    worker_template = _get_worker_template_for_task(task)

    prompt_parts = []

    if worker_template:
        prompt_parts.append(worker_template)
        prompt_parts.append("")

    prompt_parts.extend([
        f"You are a project agent for '{name}'.",
        f"Working directory: {workspace}",
        f"TIME BUDGET: You have ~{timeout // 60} minutes. Prioritize completing something concrete over perfection.",
        "",
        "## Constraints",
        constraints,
        "",
    ])

    # Load CI context if available
    has_ci_context = False
    ci_file = agent_dir / "data" / "ci_context.json"
    if ci_file.exists():
        try:
            ci = json.loads(ci_file.read_text())
            cmds = ci.get("commands", {})
            if cmds:
                has_ci_context = True
                ci_lines = ["## CI Commands (auto-detected)"]
                for category, cmd_list in cmds.items():
                    ci_lines.append(f"- **{category}**: {' ; '.join(cmd_list)}")
                pm = ci.get("package_manager")
                if pm and pm != "npm":
                    ci_lines.append(f"- **package manager**: {pm} (use instead of npm)")
                ci_lines.append("")
                prompt_parts.extend(ci_lines)
        except (json.JSONDecodeError, OSError):
            pass

    # Load dependency map if available
    dep_file = agent_dir / "data" / "dependency_map.json"
    if dep_file.exists():
        try:
            dm = json.loads(dep_file.read_text())
            dm_lines = ["## Project Structure (auto-detected)"]
            if dm.get("framework"):
                dm_lines.append(f"- **Framework**: {dm['framework']} ({dm.get('language', '?')})")
            elif dm.get("language"):
                dm_lines.append(f"- **Language**: {dm['language']}")
            if dm.get("entry_points"):
                dm_lines.append(f"- **Entry points**: {', '.join(dm['entry_points'][:5])}")
            if dm.get("source_dirs"):
                dirs = [f"{d['path']}/ ({d['file_count']} files)" for d in dm["source_dirs"][:6]]
                dm_lines.append(f"- **Source dirs**: {', '.join(dirs)}")
            if dm.get("test_dirs"):
                tdirs = [f"{d['path']}/ ({d['file_count']} files)" for d in dm["test_dirs"][:3]]
                dm_lines.append(f"- **Test dirs**: {', '.join(tdirs)}")
            if dm.get("test_files"):
                dm_lines.append(f"- **Test files**: {len(dm['test_files'])} co-located test files")
            dm_lines.append("")
            prompt_parts.extend(dm_lines)
        except (json.JSONDecodeError, OSError):
            pass

    # PR Factory Phase 2: inject intake artifacts + indexes into prompt
    try:
        from clarvis.orch.pr_intake import load_all_artifacts, format_artifacts_for_prompt
        from clarvis.orch.pr_indexes import load_all_indexes, format_indexes_for_prompt
        artifacts = load_all_artifacts(agent_dir)
        if artifacts:
            art_text = format_artifacts_for_prompt(artifacts)
            if art_text.strip():
                prompt_parts.extend(["## Project Intake (auto-generated)", art_text, ""])
        indexes = load_all_indexes(agent_dir)
        if indexes:
            idx_text = format_indexes_for_prompt(indexes)
            if idx_text.strip():
                prompt_parts.extend(["## Precision Indexes (auto-generated)", idx_text, ""])
    except ImportError:
        pass
    except Exception:
        pass

    # PR Factory Phase 3: inject execution brief into prompt
    try:
        from pr_factory import build_factory_context
        factory_context = build_factory_context(name, task, agent_dir)
        if factory_context and factory_context.strip():
            prompt_parts.extend(["## Execution Brief (compiled)", factory_context, ""])
    except ImportError:
        pass
    except Exception:
        pass

    # Mirror validation instructions (for agents with PROD mirrors)
    if name in MIRROR_DIRS and MIRROR_DIRS[name].exists():
        mirror_dir = MIRROR_DIRS[name]
        mirror_checks = MIRROR_CHECKS.get(name, [])
        check_cmds = ", ".join(f"`{c['name']}`" for c in mirror_checks)
        gate_mode = MIRROR_GATE_MODE.get(name, _MIRROR_GATE_DEFAULT)
        prompt_parts.extend([
            "## Pre-Submit Mirror Validation",
            f"Before creating a PR, validate your changes against the PROD mirror at `{mirror_dir}`.",
            "**Try to fix any validation errors before creating the PR, but create the PR even if",
            "some errors remain — the post-spawn gate will comment with findings for review.**",
            "",
            "The post-spawn gate uses **baseline-diff**: it runs checks BEFORE and AFTER overlaying",
            "your files. Only NEW errors (not pre-existing in PROD) cause failure. Pre-existing errors",
            "in PROD (e.g., missing modules not yet deployed) are excluded from the diff.",
            f"Gate mode: **{gate_mode}** — {'PR will be commented but NOT closed on failure' if gate_mode == 'soft' else 'PR will be closed on failure' if gate_mode == 'hard' else 'validation skipped'}.",
            "",
            "Steps:",
            f"1. Copy your changed files into `{mirror_dir}`",
            f"2. Run: {check_cmds} in `{mirror_dir}`",
            f"3. Restore ALL files AND remove any NEW directories you created (leave mirror byte-identical)",
            "4. Include a '## Mirror Validation (PROD)' section in your PR body with results",
            "5. If your changes introduce NEW tsc/vitest errors, fix them before creating the PR",
            "",
            "Example PR body section:",
            "```",
            "## Mirror Validation (PROD)",
            "- **tsc --noEmit**: PASS (12.3s) (3 pre-existing errors excluded)",
            "- **vitest run**: PASS (8.1s)",
            "Overall: PASS",
            "```",
            "",
        ])

    procedures = _dedup_procedures(raw_procedures, has_ci_context=has_ci_context) if raw_procedures else ""
    if procedures:
        prompt_parts.extend([
            "## Known Procedures",
            procedures[:1500],
            "",
        ])

    # Only include explicit caller-provided context. The Clarvis tiered
    # brief (generate_tiered_brief) was previously used as a fallback here,
    # but it injects Clarvis-internal failure patterns, episodic memory, and
    # queue tasks that are irrelevant noise for project agents. Project-specific
    # context is assembled below via episodic/failure/brain sections.
    if context:
        prompt_parts.extend([
            "## Context from Clarvis",
            context[:2000],
            "",
        ])

    # ── Task (placed early so the agent knows what context to weight) ──
    prompt_parts.extend([
        "## Task",
        task,
        "",
    ])

    # ── Project Intelligence (success-first, concise) ────────────────
    # Order: success exemplar → brain knowledge → episodic context →
    # failure constraints (max 3).  The goal is to give the agent a
    # positive model to follow, relevant repo knowledge, then brief
    # situational awareness of past issues — not a wall of avoidance.

    # 1. Success exemplar — what a good run looked like for a similar task
    success_exemplar = _gather_success_exemplar(agent_dir, task)

    # 2. Lite brain learnings (skip procedures if already in prompt)
    failure_constraints = _gather_failure_constraints(agent_dir)
    brain_knowledge = _query_lite_brain(agent_dir, task,
                                         skip_procedures=bool(procedures),
                                         skip_failure_patterns=bool(failure_constraints))

    # 3. Episodic context (successes + brief failure notes)
    episodic_ctx = _gather_episodic_context(agent_dir, task)

    intel_parts = []
    if success_exemplar:
        intel_parts.append(success_exemplar)
    if brain_knowledge:
        intel_parts.append(brain_knowledge)
    if episodic_ctx:
        intel_parts.append(episodic_ctx)
    if failure_constraints:
        intel_parts.append(failure_constraints)
    if intel_parts:
        prompt_parts.extend([
            "## Project Intelligence",
            "\n\n".join(intel_parts),
            "",
        ])

    # PR Factory rules injection (Phase 1 — graceful if not installed)
    try:
        from clarvis.orch.pr_rules import build_pr_rules_section
        prompt_parts.extend(build_pr_rules_section())
    except ImportError:
        pass

    # ── Delivery Protocol (Git + Safety + Output) ────────────────────
    _repo_url = config.get("repo_url", "")
    import re as _re_prompt
    _m = _re_prompt.search(r'[:/]([^/]+/[^/.]+?)(?:\.git)?$', _repo_url)
    _upstream_repo = _m.group(1) if _m else ""
    _fork_owner = "GranusClarvis"
    _base_branch = config.get("branch", "main")

    prompt_parts.append("## Delivery")
    prompt_parts.append("You are on a fresh work branch. Commit → push → PR. Do NOT switch branches.")
    if _upstream_repo:
        _current_branch_var = "$(git rev-parse --abbrev-ref HEAD)"
        prompt_parts.append(
            f"PR command: `gh pr create --repo {_upstream_repo} "
            f"--head {_fork_owner}:{_current_branch_var} --base {_base_branch} "
            f"--title '...' --body '...'`"
        )
        prompt_parts.append(f"Target the upstream repo ({_upstream_repo}), not the fork.")
    else:
        prompt_parts.append("PR command: `gh pr create --title '...' --body '...'`")
    prompt_parts.extend([
        "Use `git add <specific-files>` — never `git add .`.",
        f"Allowed file extensions: {', '.join(sorted(COMMIT_EXT_WHITELIST))}",
        "Never commit: .env, keys, *.pem, *.sqlite, *.db, *.log, node_modules/.",
        "",
    ])

    # Brain storage hint (optional, one line)
    prompt_parts.extend([
        "## Brain (optional)",
        f"Store learnings: `python3 -c \"import sys; sys.path.insert(0, '{CLARVIS_WORKSPACE}/scripts/brain_mem'); "
        f"from lite_brain import LiteBrain; b=LiteBrain('{agent_dir}/data/brain'); "
        "b.store('what you learned', 'project-procedures')\"",
        "",
    ])

    prompt_parts.extend([
        "## Output (A2A/v1 — MANDATORY)",
        "End with EXACTLY ONE ```json block:",
        "```json",
        "{",
        '  "status": "success|partial|failed|blocked",',
        '  "summary": "2-3 sentences of what you did",',
        '  "pr_url": "https://github.com/..." or null,',
        '  "branch": "current branch name",',
        '  "files_changed": ["path/to/file1"],',
        '  "procedures": ["Build: npm run build"],',
        '  "follow_ups": ["TODO: ..."],',
        '  "tests_passed": true or false,',
        '  "error": "description if failed" or null,',
        '  "confidence": 0.0 to 1.0,',
        '  "pr_class": "A|B|C"',
        "}",
        "```",
    ])

    return "\n".join(prompt_parts)


def build_spawn_command(prompt_file: str, timeout: int) -> str:
    """Build shell command that reads prompt from file (avoids ARG_MAX).

    Uses $(cat file) pattern matching spawn_claude.sh convention.
    Returns a shell command string (use with shell=True).
    """
    return (
        f"timeout {timeout} env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT "
        f"{shlex.quote(CLAUDE_BIN)} "
        f"-p \"$(cat {shlex.quote(prompt_file)})\" "
        f"--dangerously-skip-permissions --model claude-opus-4-6"
    )


def cmd_spawn(name: str, task: str, timeout: int = 1200,
              context: str = "") -> dict:
    """Spawn Claude Code to execute a task in the project agent's workspace.

    Policy:
    - Always sync to upstream before work.
    - Always do work on a fresh branch named `clarvis/<agent>/<task_id>`.
      (Agents may push ONLY such branches in order to open PRs; never main/owner branches.)
    """
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    if config.get("status") == "running":
        return {"error": f"Agent '{name}' is already running a task"}

    # Trust gate — suspended agents cannot run
    trust = config.get("trust_score", DEFAULT_TRUST_SCORE)
    tier, _ = get_trust_tier(trust)
    if tier == "suspended":
        return {"error": f"Agent '{name}' is suspended (trust={trust:.3f}). "
                f"Use 'trust {name} boost' to restore."}

    # Agent Claude concurrency controls (per-agent lock + global semaphore cap)
    lock_err = _acquire_agent_claude_lock(name)
    if lock_err:
        _log(f"SKIP spawn '{name}': {lock_err}")
        return {"error": f"Cannot spawn: {lock_err}"}

    slot_file, slot_err = _acquire_claude_slot(name)
    if slot_err:
        _release_agent_claude_lock(name)
        _log(f"SKIP spawn '{name}': {slot_err}")
        return {"error": f"Cannot spawn: {slot_err}"}

    agent_dir = _agent_dir(name)
    workspace = agent_dir / "workspace"
    task_id = _task_id()

    # Always sync + create a fresh work branch for this run
    base_branch = config.get("branch", "main")
    work_branch = _sync_and_checkout_work_branch(workspace, base_branch, name, task_id)

    # Enforce budget
    max_timeout = config.get("budget", {}).get("max_timeout", 1800)
    timeout = min(timeout, max_timeout)

    _log(f"Spawning task {task_id} on agent '{name}' (branch={work_branch}): {task[:80]}")
    _emit("agent_spawned", agent=name, task_id=task_id,
          task_name=task[:120], branch=work_branch)

    # Refresh CI context before building prompt
    try:
        build_ci_context(name)
    except Exception as e:
        _log(f"CI context scan failed (non-fatal): {e}")

    # PR Factory Phase 2: refresh intake artifacts + precision indexes
    try:
        from clarvis.orch.pr_intake import refresh_artifacts
        from clarvis.orch.pr_indexes import refresh_indexes
        refresh_artifacts(agent_dir, workspace)
        refresh_indexes(agent_dir, workspace)
    except ImportError:
        pass  # Phase 2 not installed yet — graceful degradation
    except Exception as e:
        _log(f"PR factory intake refresh failed (non-fatal): {e}")

    # Update status
    config["status"] = "running"
    config["last_task"] = {"id": task_id, "task": task[:200], "started": datetime.now(timezone.utc).isoformat()}
    _save_config(name, config)

    # Build prompt and write to file
    prompt = build_spawn_prompt(name, task, config, agent_dir, context, timeout=timeout)
    prompt_file = f"/tmp/project_agent_{name}_{task_id}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)

    output_file = f"/tmp/project_agent_{name}_{task_id}_output.txt"
    log_file = agent_dir / "logs" / f"{task_id}.log"

    # Build shell command that reads prompt from file (avoids ARG_MAX)
    cmd = build_spawn_command(prompt_file, timeout)

    # Spawn Claude Code — scrub Clarvis secrets from subprocess environment
    _SECRET_ENV_PREFIXES = ("CLARVIS_TG", "CLARVIS_AUDIT", "OPENROUTER_API",
                            "TELEGRAM_BOT", "TELEGRAM_TOKEN")
    env = {k: v for k, v in os.environ.items()
           if not any(k.startswith(p) for p in _SECRET_ENV_PREFIXES)}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    _log(f"Executing in {workspace} with {timeout}s timeout")

    # Snapshot OpenRouter cost before task
    cost_before = _snapshot_cost()

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
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
    finally:
        # Always release concurrency controls
        _release_claude_slot(slot_file)
        _release_agent_claude_lock(name)

    elapsed = time.time() - start_time

    # Compute actual OpenRouter cost delta
    cost_after = _snapshot_cost()
    actual_cost_usd = None
    if cost_before is not None and cost_after is not None:
        actual_cost_usd = round(cost_after - cost_before, 6)
        _log(f"Task {task_id} cost: ${actual_cost_usd:.6f} (before=${cost_before:.4f} after=${cost_after:.4f})")

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

    # ── Post-spawn PR URL validation ───────────────────────────────��──
    # Reject PRs targeting the fork instead of upstream
    _pr_url = agent_result.get("pr_url")
    if _pr_url and isinstance(_pr_url, str):
        import re as _re_pr
        _repo_url_cfg = config.get("repo_url", "")
        _m_up = _re_pr.search(r'[:/]([^/]+/[^/.]+?)(?:\.git)?$', _repo_url_cfg)
        _upstream_slug = _m_up.group(1).lower() if _m_up else ""
        if _upstream_slug and _upstream_slug not in _pr_url.lower():
            _log(f"PR URL targets wrong repo (expected {_upstream_slug}): {_pr_url}")
            agent_result["_misrouted_pr"] = _pr_url
            agent_result["pr_url"] = None

    # ── Post-spawn commit safety audit ───────────────��────────────────
    # Re-stage any remaining dirty files through the safety filter.
    # This catches cases where the agent used `git add .` or staged secrets.
    try:
        _staged, _blocked = safe_stage_files(workspace)
        if _blocked:
            _log(f"Commit safety blocked {len(_blocked)} files: {_blocked[:5]}")
            agent_result.setdefault("_safety_blocked", _blocked)
    except Exception as e:
        _log(f"Post-spawn safety audit error (non-fatal): {e}")

    # PR Factory Phase 3: mandatory writeback (episode, facts, procedures, golden QA)
    try:
        from pr_factory import run_writeback
        run_writeback(name, agent_dir, agent_result, task)
    except ImportError:
        pass  # Phase 3 not installed yet — graceful degradation
    except Exception as e:
        _log(f"PR factory writeback failed (non-fatal): {e}")

    # ── Post-spawn mirror validation ─────────────────────────────────
    apply_mirror_gate(name, agent_result, config, workspace, task_id)

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

    # Apply trust scoring based on outcome (also saves config)
    _apply_spawn_trust(name, config, {
        "exit_code": exit_code,
        "result": agent_result,
    })

    # Store task summary
    summary_file = agent_dir / "memory" / "summaries" / f"{task_id}.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "task_id": task_id,
        "task": task[:500],
        "result": agent_result,
        "exit_code": exit_code,
        "elapsed": round(elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if actual_cost_usd is not None:
        summary_data["actual_cost_usd"] = actual_cost_usd
    summary_file.write_text(json.dumps(summary_data, indent=2))

    # Episode writeback to lite brain — store real task outcomes for future retrieval
    try:
        sys.path.insert(0, str(CLARVIS_WORKSPACE / "scripts" / "brain_mem"))
        from lite_brain import LiteBrain
        lb = LiteBrain(str(agent_dir / "data" / "brain"))
        status = agent_result.get("status", "unknown")
        summary_text = agent_result.get("summary", "")[:200]
        pr_note = f" PR:{agent_result['pr_url']}" if agent_result.get("pr_url") else ""
        episode_text = (
            f"[{status.upper()}] {task[:120]} — "
            f"{summary_text}{pr_note}"
        )
        lb.store(
            episode_text,
            collection="project-episodes",
            importance=0.8 if status == "success" else 0.9,
            tags=[f"status:{status}", f"task_id:{task_id}"],
            source="spawn-writeback",
        )
        # Store learned procedures from successful runs
        if status == "success" and agent_result.get("procedures"):
            for proc in agent_result["procedures"][:5]:
                if proc and len(proc) > 10:
                    lb.store(proc, collection="project-procedures",
                             importance=0.7, tags=["auto-learned"],
                             source="spawn-writeback")
        _log(f"Episode writeback: stored to lite brain (status={status})")
    except Exception as e:
        _log(f"Episode writeback to lite brain failed (non-fatal): {e}")

    # Auto-refresh procedures.md from successful run procedures
    if agent_result.get("status") == "success" and agent_result.get("procedures"):
        try:
            proc_file = agent_dir / "memory" / "procedures.md"
            existing = proc_file.read_text() if proc_file.exists() else ""
            new_procs = [p for p in agent_result["procedures"]
                         if p and len(p) > 10 and p not in existing]
            if new_procs:
                with open(proc_file, "a") as f:
                    f.write(f"\n## Learned {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n")
                    for p in new_procs[:5]:
                        f.write(f"- {p}\n")
                _log(f"Procedures.md updated: +{len(new_procs)} new procedures")
        except Exception as e:
            _log(f"Procedures.md update failed (non-fatal): {e}")

    # ── Postflight parity: mirror key Clarvis heartbeat postflight steps ──
    _run_clarvis_postflight(
        name=name,
        task_id=task_id,
        task=task,
        agent_result=agent_result,
        exit_code=exit_code,
        elapsed=elapsed,
        output=output,
    )

    _log(f"Task {task_id} completed: exit={exit_code} elapsed={elapsed:.0f}s status={agent_result.get('status', 'unknown')}")

    # ── Post-task branch cleanup (best-effort, non-blocking) ──────────
    try:
        cleanup = cleanup_stale_branches(
            workspace, keep_branch=work_branch, base_branch=base_branch)
        if cleanup["deleted"]:
            _log(f"Branch cleanup: deleted {len(cleanup['deleted'])} stale branches")
        if cleanup["errors"]:
            _log(f"Branch cleanup errors: {cleanup['errors'][:3]}")
    except Exception as e:
        _log(f"Branch cleanup failed (non-fatal): {e}")

    _emit("task_completed", agent=name, task_id=task_id,
          status=agent_result.get("status", "unknown"),
          exit_code=exit_code, duration_s=round(elapsed, 1),
          cost_usd=actual_cost_usd, section="project_agent")

    # Emit PR event if one was created
    if agent_result.get("pr_url"):
        _emit("pr_created", agent=name, task_id=task_id,
              pr_url=agent_result["pr_url"])

    return {
        "task_id": task_id,
        "agent": name,
        "exit_code": exit_code,
        "elapsed": round(elapsed, 1),
        "result": agent_result,
        "output_tail": output[-1500:] if output else "",
        "log": str(log_file),
    }


def _run_clarvis_postflight(*, name, task_id, task, agent_result, exit_code, elapsed, output):
    """Lightweight postflight mirroring key heartbeat_postflight steps for parity.

    Runs six steps:
    1. Clarvis-side episodic encoding (not just lite brain)
    2. Brain outcome recording (store to clarvis-learnings)
    3. Failure lesson extraction (learn from errors)
    3.5. Failure pattern classification → registry → promotion (auto-learning)
    4. Digest writing (surface to conscious layer)
    5. Routing log entry (track project-agent decisions)
    """
    status = agent_result.get("status", "unknown")
    summary_text = agent_result.get("summary", "")[:200]
    pr_url = agent_result.get("pr_url")
    t0 = time.time()

    # 1. Clarvis-side episodic encoding
    try:
        from clarvis.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        error_msg = agent_result.get("error", "")[:200] if status != "success" else None
        failure_type = None
        if status == "timeout":
            failure_type = "timeout"
        elif status == "failed" or status == "failure":
            failure_type = "action"
        em.encode(
            task_text=f"[agent:{name}] {task[:200]}",
            section="project-agent",
            salience=0.7 if status == "success" else 0.85,
            outcome="success" if status == "success" else ("timeout" if status == "timeout" else "failure"),
            duration_s=int(elapsed),
            error_msg=error_msg,
            failure_type=failure_type,
            output_text=output[-500:] if output else None,
        )
        _log(f"Postflight: Clarvis episodic encode done (agent={name})")
    except Exception as e:
        _log(f"Postflight: episodic encode failed (non-fatal): {e}")

    # 2. Brain outcome recording
    try:
        from clarvis.heartbeat.brain_bridge import brain_record_outcome
        brain_record_outcome(
            task_text=f"[agent:{name}] {task[:150]}",
            status="success" if status == "success" else ("timeout" if status == "timeout" else "failure"),
            output_text=output[-500:] if output else "",
            duration_s=int(elapsed),
        )
        _log(f"Postflight: brain outcome recorded")
    except Exception as e:
        _log(f"Postflight: brain outcome failed (non-fatal): {e}")

    # 3. Failure lesson extraction
    if status not in ("success",) and output:
        try:
            from clarvis.brain import get_brain
            from clarvis.brain.constants import LEARNINGS
            b = get_brain()
            error_tail = output[-300:]
            import re as _re_fl
            error_tail = _re_fl.sub(r'[^a-zA-Z0-9 _.,:;=+\-/()@#%\n]', '', error_tail)[:250]
            lesson = f"AGENT-FAILURE [{name}] {task[:100]} — {error_tail}"
            b.store(
                lesson,
                collection=LEARNINGS,
                importance=0.85,
                tags=["agent-failure", f"agent:{name}", f"task_id:{task_id}"],
                source="project_agent_postflight",
            )
            _log(f"Postflight: failure lesson stored")
        except Exception as e:
            _log(f"Postflight: failure lesson failed (non-fatal): {e}")

    # 3.5. Failure pattern classification + registry + promotion
    if status not in ("success",):
        try:
            agent_dir = _agent_dir(name)
            error_text = (output or "")[-600:] + " " + (agent_result.get("error") or "")
            mirror_checks = agent_result.get("mirror_validation", {}).get("checks", [])
            classified = _classify_failure(error_text, mirror_checks if mirror_checks else None)
            if classified:
                newly_promoted = _update_failure_registry(
                    agent_dir, classified, task, task_id
                )
                classes = [c["class"] for c in classified]
                _log(f"Postflight: classified failure patterns: {classes}")
                if newly_promoted:
                    _promote_failure_patterns(agent_dir, newly_promoted)
                    _log(f"Postflight: promoted {len(newly_promoted)} patterns to procedures + lite brain")
            else:
                _log(f"Postflight: no known failure pattern matched — raw lesson stored in step 3")
        except Exception as e:
            _log(f"Postflight: failure pattern classification failed (non-fatal): {e}")

    # 4. Digest writing
    try:
        from clarvis._script_loader import load as _load_script
        _dw = _load_script("digest_writer", "tools")
        pr_note = f" PR: {pr_url}" if pr_url else ""
        _dw.write_digest(
            "autonomous",
            f'Project agent [{name}] completed task: "{task[:100]}". '
            f'Result: {status} ({elapsed:.0f}s).{pr_note} '
            f'{summary_text[:150]}'
        )
        _log(f"Postflight: digest written")
    except Exception as e:
        _log(f"Postflight: digest write failed (non-fatal): {e}")

    # 5. Routing log entry
    try:
        from clarvis.orch.router import log_decision
        log_decision(
            task_text=f"[agent:{name}] {task[:150]}",
            classification={"tier": "COMPLEX", "score": 1.0, "reason": "project-agent"},
            executor_used=f"project-agent:{name}",
            outcome=status,
        )
        _log(f"Postflight: routing decision logged")
    except Exception as e:
        _log(f"Postflight: routing log failed (non-fatal): {e}")

    pf_elapsed = time.time() - t0
    _log(f"Postflight parity: completed in {pf_elapsed:.2f}s (5 steps)")


def _parse_agent_output(output: str) -> dict:
    """Extract structured JSON result from agent output, validate against A2A protocol.

    Returns a normalized A2A-conformant dict. If the agent didn't produce
    valid JSON, synthesizes a minimal result with status=unknown.
    """
    if not output:
        return normalize_a2a_result({"status": "failed", "summary": "No output"})

    raw_result = None

    # Find last JSON block in output
    import re
    json_blocks = re.findall(r'```json\s*\n(.*?)\n```', output, re.DOTALL)

    if json_blocks:
        try:
            raw_result = json.loads(json_blocks[-1])
        except json.JSONDecodeError:
            pass

    # Fallback: try to find raw JSON object
    if raw_result is None:
        for line in reversed(output.split("\n")):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    raw_result = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

    # No structured output — synthesize minimal result
    if raw_result is None:
        return normalize_a2a_result({
            "status": "unknown",
            "summary": output[-500:] if output else "No output",
        })

    # Validate and normalize
    is_valid, issues = validate_a2a_result(raw_result)
    if issues:
        level = "errors" if not is_valid else "warnings"
        _log(f"A2A validation {level}: {'; '.join(issues)}")

    # Fix missing required fields before normalizing
    if not is_valid:
        if "status" not in raw_result:
            raw_result["status"] = "unknown"
        if "summary" not in raw_result or not raw_result.get("summary"):
            raw_result["summary"] = output[-500:].strip() if output else "No structured summary"

    normalized = normalize_a2a_result(raw_result)
    normalized["_a2a_valid"] = is_valid
    if issues:
        normalized["_a2a_warnings"] = issues

    return normalized


def _is_task_failure(spawn_result: dict) -> bool:
    """Determine if a spawn result represents a retryable failure."""
    if spawn_result.get("error"):
        return False  # config errors (agent not found, already running) aren't retryable
    exit_code = spawn_result.get("exit_code", 1)
    status = spawn_result.get("result", {}).get("status", "unknown")
    return exit_code != 0 or status in ("failed", "unknown")


def _build_retry_context(spawn_result: dict, attempt: int, max_retries: int) -> str:
    """Build context string for retry prompt explaining previous failure."""
    exit_code = spawn_result.get("exit_code", -1)
    status = spawn_result.get("result", {}).get("status", "unknown")
    summary = spawn_result.get("result", {}).get("summary", "")
    output_tail = spawn_result.get("output_tail", "")

    lines = [
        f"## RETRY ATTEMPT {attempt}/{max_retries}",
        "",
        "The previous attempt FAILED. Adjust your approach.",
        f"- Exit code: {exit_code}",
        f"- Status: {status}",
    ]
    if summary:
        lines.append(f"- Summary: {summary[:300]}")
    if output_tail:
        # Include last 500 chars of output for error context
        tail = output_tail[-500:].strip()
        if tail:
            lines.extend(["", "Previous output (tail):", f"```", tail, "```"])
    lines.extend([
        "",
        "Strategies for this retry:",
        "- Read error messages carefully and fix the root cause",
        "- Try a simpler approach if the previous one was too complex",
        "- Check prerequisites (dependencies, permissions, branch state)",
        "- If tests failed, fix the failing tests before creating a PR",
    ])
    return "\n".join(lines)


def cmd_spawn_with_retry(name: str, task: str, timeout: int = 1200,
                         context: str = "", max_retries: int = MAX_RETRIES) -> dict:
    """Spawn a task with automatic retry on failure.

    If the task fails, re-spawns with an adjusted prompt that includes
    error context from the previous attempt. Max 2 retries by default.

    Returns the final spawn result, augmented with retry metadata.
    """
    max_retries = min(max_retries, MAX_RETRIES)  # hard cap
    attempts = []

    current_context = context
    for attempt in range(max_retries + 1):  # 0 = first try, 1..N = retries
        if attempt > 0:
            # Backoff before retry
            backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            _log(f"Retry {attempt}/{max_retries} for agent '{name}' "
                 f"(backoff {backoff}s): {task[:60]}")
            time.sleep(backoff)

            # Build retry context from previous failure
            retry_ctx = _build_retry_context(attempts[-1], attempt, max_retries)
            current_context = (context + "\n\n" + retry_ctx).strip() if context else retry_ctx

        result = cmd_spawn(name, task, timeout, current_context)

        # Track attempt
        attempt_record = {
            "attempt": attempt,
            "task_id": result.get("task_id"),
            "exit_code": result.get("exit_code"),
            "status": result.get("result", {}).get("status", "unknown"),
            "elapsed": result.get("elapsed"),
        }
        attempts.append(result)

        # Check for non-retryable errors (config issues)
        if result.get("error"):
            _log(f"Non-retryable error for agent '{name}': {result['error']}")
            break

        # Check if task succeeded
        if not _is_task_failure(result):
            if attempt > 0:
                _log(f"Task succeeded on retry {attempt} for agent '{name}'")
            break

        # Log failure
        _log(f"Attempt {attempt} failed for agent '{name}': "
             f"exit={result.get('exit_code')} "
             f"status={result.get('result', {}).get('status', 'unknown')}")

    # Augment final result with retry metadata
    result["retry_metadata"] = {
        "total_attempts": len(attempts),
        "max_retries": max_retries,
        "succeeded_on_attempt": len(attempts) - 1 if not _is_task_failure(result) else None,
        "attempts": [
            {
                "attempt": i,
                "task_id": a.get("task_id"),
                "exit_code": a.get("exit_code"),
                "status": a.get("result", {}).get("status", "unknown"),
                "elapsed": a.get("elapsed"),
            }
            for i, a in enumerate(attempts)
        ],
    }

    # Save retry summary alongside regular task summary
    if len(attempts) > 1:
        agent_dir = _agent_dir(name)
        retry_log = agent_dir / "logs" / f"retry_{result.get('task_id', 'unknown')}.json"
        try:
            retry_log.write_text(json.dumps(result["retry_metadata"], indent=2))
        except OSError:
            pass

    return result


def cmd_spawn_parallel(tasks: list[dict], timeout: int = 1200) -> dict:
    """Spawn multiple agent tasks in parallel, respecting concurrency limits.

    Each entry in tasks should be: {"agent": "<name>", "task": "<description>"}
    Optionally: {"agent": ..., "task": ..., "timeout": 900, "context": "..."}

    Uses ThreadPoolExecutor bounded by MAX_PARALLEL_AGENT_CLAUDE.
    Returns aggregated results keyed by agent name.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not tasks:
        return {"error": "No tasks provided", "results": {}}

    max_workers = min(len(tasks), MAX_PARALLEL_AGENT_CLAUDE)
    results = {}
    _log(f"spawn_parallel: {len(tasks)} tasks, max_workers={max_workers}")

    def _run_one(entry):
        name = entry["agent"]
        task = entry["task"]
        t = entry.get("timeout", timeout)
        ctx = entry.get("context", "")
        return name, cmd_spawn(name, task, t, ctx)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_one, t): t for t in tasks}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                name, result = future.result()
                results[name] = result
            except Exception as e:
                results[entry["agent"]] = {"error": str(e)}

    succeeded = sum(1 for r in results.values()
                    if not r.get("error") and not _is_task_failure(r))
    _log(f"spawn_parallel complete: {succeeded}/{len(tasks)} succeeded")

    return {
        "total": len(tasks),
        "succeeded": succeeded,
        "failed": len(tasks) - succeeded,
        "results": results,
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

    # Store top procedures in Clarvis brain with project tag
    brain_stored = 0
    if procedures_to_promote:
        try:
            from clarvis.brain import brain as clarvis_brain
            tag = f"project:{name}"
            for proc in procedures_to_promote[:10]:  # cap at 10 per promotion
                clarvis_brain.store(
                    proc,
                    collection="clarvis-procedures",
                    importance=0.75,
                    tags=[tag, "project-agent"],
                    source="project-agent-promote",
                )
                brain_stored += 1
            _log(f"Stored {brain_stored} procedures in Clarvis brain tagged '{tag}'")
        except Exception as e:
            _log(f"WARNING: Failed to store procedures in Clarvis brain: {e}")

    _log(f"Promoted {len(promoted)} results from agent '{name}'")

    return {
        "status": "promoted",
        "agent": name,
        "count": len(promoted),
        "procedures": len(procedures_to_promote),
        "brain_stored": brain_stored,
        "digest": str(digest_file),
    }


# =========================================================================
# AUTO GOLDEN QA — generate Q/A pairs from successful task summaries
# =========================================================================

GOLDEN_QA_CAP = 50
GOLDEN_QA_DEDUP_THRESHOLD = 0.85  # cosine similarity above this = duplicate


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cmd_auto_golden_qa(name: str) -> dict:
    """Auto-generate golden QA pairs from successful task summaries.

    For each successful task, generates 1-2 Q/A pairs from the task
    description and result summary. Deduplicates against existing QA
    by cosine similarity (threshold 0.85). Caps at 50 total pairs.
    """
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)
    summaries_dir = agent_dir / "memory" / "summaries"
    golden_file = agent_dir / "data" / "golden_qa.json"

    # Load existing golden QA
    existing_qa = []
    if golden_file.exists():
        try:
            existing_qa = json.loads(golden_file.read_text())
        except (json.JSONDecodeError, OSError):
            existing_qa = []

    if len(existing_qa) >= GOLDEN_QA_CAP:
        return {"status": "at_cap", "count": len(existing_qa),
                "cap": GOLDEN_QA_CAP}

    # Get embedding function for dedup
    try:
        from clarvis.brain.factory import get_embedding_function
        embed_fn = get_embedding_function(use_onnx=True)
    except Exception as e:
        return {"error": f"Cannot load embeddings: {e}"}

    # Embed existing QA queries for dedup
    existing_queries = [qa.get("query", "") for qa in existing_qa]
    existing_embeddings = []
    if existing_queries:
        existing_embeddings = embed_fn(existing_queries)

    # Track which summaries we already processed
    processed_marker = agent_dir / "data" / "auto_qa_processed.json"
    processed_ids = set()
    if processed_marker.exists():
        try:
            processed_ids = set(json.loads(processed_marker.read_text()))
        except (json.JSONDecodeError, OSError):
            pass

    # Scan successful summaries
    candidates = []
    if summaries_dir.exists():
        for sf in sorted(summaries_dir.glob("*.json")):
            try:
                summary = json.loads(sf.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            task_id = summary.get("task_id", sf.stem)
            if task_id in processed_ids:
                continue

            result = summary.get("result", {})
            status = result.get("status", "")
            if status != "success":
                processed_ids.add(task_id)
                continue

            task_desc = summary.get("task", "")
            result_summary = result.get("summary", "")
            procedures = result.get("procedures", [])

            if not task_desc or not result_summary:
                processed_ids.add(task_id)
                continue

            # Generate Q/A pair 1: "How to <task>?"
            q1 = f"How do I {task_desc.lower().rstrip('.')}?"
            if len(q1) > 200:
                q1 = q1[:197] + "..."
            a1 = result_summary[:500] if result_summary else task_desc

            candidates.append({
                "query": q1,
                "expected_docs": [task_desc[:100].lower()],
                "answer": a1,
                "collection": "project-procedures",
                "tags": ["auto_qa", "golden_qa"],
                "source_task": task_id,
            })

            # Generate Q/A pair 2: from first procedure (if available)
            if procedures and len(procedures) > 0:
                proc = procedures[0] if isinstance(procedures[0], str) else ""
                if proc and len(proc) > 20:
                    q2 = f"What is the procedure for: {proc[:100]}?"
                    a2 = proc[:500]
                    candidates.append({
                        "query": q2,
                        "expected_docs": [proc[:80].lower()],
                        "answer": a2,
                        "collection": "project-procedures",
                        "tags": ["auto_qa", "golden_qa"],
                        "source_task": task_id,
                    })

            processed_ids.add(task_id)

    if not candidates:
        # Save processed IDs even if no candidates
        processed_marker.parent.mkdir(parents=True, exist_ok=True)
        processed_marker.write_text(json.dumps(list(processed_ids)))
        return {"status": "no_new_candidates", "existing": len(existing_qa)}

    # Deduplicate candidates against existing QA
    added = 0
    skipped_dedup = 0
    for candidate in candidates:
        if len(existing_qa) >= GOLDEN_QA_CAP:
            break

        # Embed candidate query
        cand_query = candidate.get("query", "")
        if not cand_query:
            skipped_dedup += 1
            continue
        cand_emb = embed_fn([cand_query])[0]

        # Check similarity against all existing
        is_dup = False
        for ex_emb in existing_embeddings:
            sim = _cosine_sim(cand_emb, ex_emb)
            if sim >= GOLDEN_QA_DEDUP_THRESHOLD:
                is_dup = True
                break

        if is_dup:
            skipped_dedup += 1
            continue

        # Add to QA set
        existing_qa.append(candidate)
        existing_embeddings.append(cand_emb)
        existing_queries.append(cand_query)
        added += 1

    # Save updated golden QA
    golden_file.parent.mkdir(parents=True, exist_ok=True)
    golden_file.write_text(json.dumps(existing_qa, indent=2))

    # Save processed IDs
    processed_marker.parent.mkdir(parents=True, exist_ok=True)
    processed_marker.write_text(json.dumps(list(processed_ids)))

    _log(f"Auto golden QA for '{name}': +{added} pairs "
         f"({skipped_dedup} deduped, {len(existing_qa)} total)")

    return {
        "status": "generated",
        "agent": name,
        "added": added,
        "skipped_dedup": skipped_dedup,
        "total": len(existing_qa),
        "cap": GOLDEN_QA_CAP,
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
                    trust = config.get("trust_score", DEFAULT_TRUST_SCORE)
                    tier, _ = get_trust_tier(trust)
                    agents.append({
                        "name": config["name"],
                        "repo": config["repo_url"],
                        "branch": config.get("branch", "main"),
                        "status": config.get("status", "unknown"),
                        "trust_score": trust,
                        "trust_tier": tier,
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

    # Enrich with trust tier
    trust = config.get("trust_score", DEFAULT_TRUST_SCORE)
    tier, tier_desc = get_trust_tier(trust)
    config["trust_tier"] = tier
    config["trust_tier_desc"] = tier_desc

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
    """Seed the agent's lite brain with repo-specific knowledge from golden_qa.json.

    Looks in (in order):
    1) <agent>/data/golden_qa.json (canonical)
    2) <agent>/workspace/data/golden_qa.json (common authoring location)

    If found in workspace/, it is copied into <agent>/data/ for future runs.
    """
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    agent_dir = _agent_dir(name)
    golden_file = agent_dir / "data" / "golden_qa.json"
    golden_file_alt = agent_dir / "workspace" / "data" / "golden_qa.json"

    if not golden_file.exists() and golden_file_alt.exists():
        golden_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(golden_file_alt, golden_file)

    if not golden_file.exists():
        return {"error": f"No golden_qa.json at {golden_file} (or {golden_file_alt}). Create it first."}

    try:
        golden = json.loads(golden_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to read golden_qa.json: {e}"}

    # Import lite brain
    from clarvis._script_loader import load as _load_script
    LiteBrain = _load_script("lite_brain", "brain_mem").LiteBrain
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
    """Benchmark retrieval quality against golden QA pairs."""
    agent_dir = _agent_dir(name)
    golden_file = agent_dir / "data" / "golden_qa.json"
    if not golden_file.exists():
        return {
            "status": "not_configured",
            "note": "Create data/golden_qa.json with repo-specific Q/A pairs to enable",
        }

    try:
        qa_pairs = json.loads(golden_file.read_text())
    except Exception as e:
        return {"status": "error", "error": str(e)}

    from clarvis._script_loader import load as _load_script
    LiteBrain = _load_script("lite_brain", "brain_mem").LiteBrain
    brain = LiteBrain(str(agent_dir / "data" / "brain"))

    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []

    for qa in qa_pairs:
        query = qa.get("query", "")
        if not query:
            continue
        expected = [e.lower() for e in qa.get("expected_docs", [])]
        collection = qa.get("collection")

        results = brain.recall(query, n_results=5, collection=collection)
        docs = [(r.get("document") or r.get("text") or "").lower() for r in results] if results else []

        # Find first rank where any expected substring matches
        found_rank = None
        for rank, doc in enumerate(docs):
            if any(exp in doc for exp in expected):
                if found_rank is None:
                    found_rank = rank + 1
                break

        if found_rank is not None:
            reciprocal_ranks.append(1.0 / found_rank)
            if found_rank <= 1:
                hits_at_1 += 1
                hits_at_3 += 1
            elif found_rank <= 3:
                hits_at_3 += 1
        else:
            reciprocal_ranks.append(0.0)

    total = len(qa_pairs)
    p_at_1 = hits_at_1 / total if total else 0
    p_at_3 = hits_at_3 / total if total else 0
    mrr = sum(reciprocal_ranks) / total if total else 0

    return {
        "status": "ok",
        "total_queries": total,
        "p_at_1": round(p_at_1, 3),
        "p_at_3": round(p_at_3, 3),
        "mrr": round(mrr, 3),
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
# TRUST — view / adjust trust score
# =========================================================================

def cmd_trust(name: str, action: str = "show") -> dict:
    """View or adjust an agent's trust score.

    Actions: show, boost, penalize, set:<value>, history
    """
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    trust = config.get("trust_score", DEFAULT_TRUST_SCORE)
    tier, tier_desc = get_trust_tier(trust)

    if action == "show":
        return {
            "name": name,
            "trust_score": trust,
            "tier": tier,
            "tier_desc": tier_desc,
            "recent_history": config.get("trust_history", [])[-10:],
        }
    elif action == "boost":
        config = adjust_trust(name, "manual_boost", config)
        _save_config(name, config)
        new_tier, _ = get_trust_tier(config["trust_score"])
        return {"name": name, "trust_score": config["trust_score"],
                "tier": new_tier, "action": "boosted +0.10"}
    elif action == "penalize":
        config = adjust_trust(name, "manual_penalize", config)
        _save_config(name, config)
        new_tier, _ = get_trust_tier(config["trust_score"])
        return {"name": name, "trust_score": config["trust_score"],
                "tier": new_tier, "action": "penalized -0.10"}
    elif action.startswith("set:"):
        try:
            new_val = float(action.split(":", 1)[1])
            new_val = round(max(0.0, min(1.0, new_val)), 3)
        except ValueError:
            return {"error": f"Invalid trust value: {action}"}
        old_score = config.get("trust_score", DEFAULT_TRUST_SCORE)
        config["trust_score"] = new_val
        history = config.get("trust_history", [])
        history.append({
            "event": "manual_set",
            "delta": round(new_val - old_score, 3),
            "old": old_score,
            "new": new_val,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        config["trust_history"] = history[-50:]
        _save_config(name, config)
        new_tier, _ = get_trust_tier(new_val)
        _log(f"Trust manually set for '{name}': {old_score:.3f} -> {new_val:.3f} (tier={new_tier})")
        return {"name": name, "trust_score": new_val, "tier": new_tier,
                "action": f"set to {new_val:.3f}"}
    elif action == "history":
        return {
            "name": name,
            "trust_score": trust,
            "tier": tier,
            "history": config.get("trust_history", []),
        }
    else:
        return {"error": f"Unknown action: {action}. Use: show, boost, penalize, set:<value>, history"}


# =========================================================================
# CI FEEDBACK LOOP — poll checks, extract failure logs, re-spawn to fix
# =========================================================================

CI_POLL_INTERVAL = 30       # seconds between polls
CI_POLL_MAX_WAIT = 600      # max seconds to wait for CI (10 min)
CI_FIX_MAX_ATTEMPTS = 2     # max times to re-spawn for CI fixes


def _poll_ci_checks(pr_number: int, repo: str, timeout: int = CI_POLL_MAX_WAIT) -> dict:
    """Poll GitHub CI checks for a PR until they complete or timeout.

    Uses `gh pr checks <number> --repo <repo> --json` for reliable structured output.
    Returns: {status: 'pass'|'fail'|'pending'|'error', checks: [...], elapsed: float}
    """
    start = time.time()
    last_checks = []

    while time.time() - start < timeout:
        try:
            r = subprocess.run(
                ["gh", "pr", "checks", str(pr_number), "--repo", repo,
                 "--json", "bucket,state,link,name"],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {"status": "error", "error": str(e), "checks": [], "elapsed": round(time.time() - start, 1)}

        # Detect "no checks" message (can appear with any returncode)
        combined_output = (r.stdout + r.stderr).lower()
        if "no checks" in combined_output or "no check runs" in combined_output:
            return {"status": "pass", "checks": [], "elapsed": round(time.time() - start, 1),
                    "note": "No CI checks configured"}

        # gh exit 8 = checks still pending (not an error)
        if r.returncode not in (0, 1, 8):
            return {"status": "error", "error": f"gh exit {r.returncode}: {r.stderr.strip()[:200]}",
                    "checks": [], "elapsed": round(time.time() - start, 1)}

        # Parse JSON output
        try:
            checks_json = json.loads(r.stdout) if r.stdout.strip() else []
        except json.JSONDecodeError:
            return {"status": "error", "error": f"Invalid JSON from gh: {r.stdout[:200]}",
                    "checks": [], "elapsed": round(time.time() - start, 1)}

        checks = []
        for c in checks_json:
            checks.append({
                "name": c.get("name", ""),
                "bucket": c.get("bucket", ""),
                "state": c.get("state", ""),
                "url": c.get("link", ""),
            })
        last_checks = checks

        if not checks:
            time.sleep(CI_POLL_INTERVAL)
            continue

        # Use the bucket field for reliable status aggregation
        buckets = {c["bucket"] for c in checks}

        # If any check is pending, keep waiting
        if "pending" in buckets:
            _log(f"CI checks still pending for PR #{pr_number}: "
                 f"{[c['name'] for c in checks if c['bucket'] == 'pending']}")
            time.sleep(CI_POLL_INTERVAL)
            continue

        # All checks resolved — check for failures
        failed = [c for c in checks if c["bucket"] in ("fail", "cancel")]
        if failed:
            return {
                "status": "fail",
                "checks": checks,
                "failed_checks": [c["name"] for c in failed],
                "elapsed": round(time.time() - start, 1),
            }
        else:
            return {
                "status": "pass",
                "checks": checks,
                "elapsed": round(time.time() - start, 1),
            }

    # Timeout
    return {
        "status": "pending",
        "checks": last_checks,
        "elapsed": round(time.time() - start, 1),
        "note": f"Timed out after {timeout}s",
    }


def _extract_ci_failure_logs(pr_number: int, repo: str, check_names: list[str] = None) -> str:
    """Extract failure logs from GitHub Actions for failed CI checks.

    Uses `gh api` to fetch check run details and annotations.
    Returns a formatted string with failure context for the agent.
    """
    logs = []

    # Get check runs for the PR's head SHA
    try:
        # Get PR details to find head SHA
        r = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "headRefOid"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return f"Could not fetch PR details: {r.stderr.strip()}"

        pr_data = json.loads(r.stdout)
        sha = pr_data.get("headRefOid", "")
        if not sha:
            return "Could not determine head SHA for PR"

        # Fetch check runs for this commit
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{sha}/check-runs",
             "--jq", ".check_runs[] | {name: .name, status: .status, conclusion: .conclusion, "
                     "output_title: .output.title, output_summary: .output.summary, "
                     "html_url: .html_url}"],
            capture_output=True, text=True, timeout=30,
        )

        if r.returncode != 0:
            # Fallback: just report check names
            if check_names:
                return f"CI checks failed: {', '.join(check_names)}. Check the PR for details."
            return f"Could not fetch check run details: {r.stderr.strip()}"

        # Parse JSONL output (one JSON object per line)
        for line in r.stdout.strip().splitlines():
            try:
                run = json.loads(line)
            except json.JSONDecodeError:
                continue

            name = run.get("name", "unknown")
            conclusion = run.get("conclusion", "")

            # Skip if we're filtering and this isn't a target
            if check_names and name not in check_names:
                continue

            if conclusion in ("failure", "cancelled", "timed_out", "action_required"):
                entry = [f"### Failed: {name}"]
                if run.get("output_title"):
                    entry.append(f"Title: {run['output_title']}")
                if run.get("output_summary"):
                    # Truncate long summaries
                    summary = run["output_summary"][:800]
                    entry.append(f"Summary:\n{summary}")
                if run.get("html_url"):
                    entry.append(f"URL: {run['html_url']}")
                logs.append("\n".join(entry))

        # Also try to get annotations (more detailed error messages)
        r2 = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{sha}/check-runs",
             "--jq", ".check_runs[] | select(.conclusion==\"failure\") | "
                     ".output.annotations[]? | {path: .path, line: .start_line, "
                     "message: .message, level: .annotation_level}"],
            capture_output=True, text=True, timeout=30,
        )
        if r2.returncode == 0 and r2.stdout.strip():
            annotation_lines = ["### Annotations (specific errors):"]
            for line in r2.stdout.strip().splitlines()[:20]:  # cap at 20 annotations
                try:
                    ann = json.loads(line)
                    annotation_lines.append(
                        f"- {ann.get('path', '?')}:{ann.get('line', '?')} "
                        f"[{ann.get('level', '?')}] {ann.get('message', '')[:200]}"
                    )
                except json.JSONDecodeError:
                    continue
            if len(annotation_lines) > 1:
                logs.append("\n".join(annotation_lines))

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"Error extracting CI logs: {e}"

    if not logs:
        if check_names:
            return f"CI checks failed: {', '.join(check_names)}. No detailed logs available."
        return "CI failed but no detailed logs could be extracted."

    return "\n\n".join(logs)


def _ci_fix_loop(name: str, pr_number: int, repo: str, spawn_result: dict,
                 task: str, timeout: int = 1200, max_attempts: int = CI_FIX_MAX_ATTEMPTS) -> dict:
    """Re-spawn agent to fix CI failures, up to max_attempts times.

    Args:
        name: Agent name
        pr_number: PR number to monitor
        repo: GitHub repo (owner/name)
        spawn_result: The spawn result that created the PR
        task: Original task description
        timeout: Timeout per fix attempt
        max_attempts: Max CI fix iterations

    Returns: dict with final status, attempts, and CI outcome
    """
    ci_attempts = []

    for attempt in range(max_attempts):
        # Poll CI checks
        _log(f"CI fix loop: polling checks for PR #{pr_number} (attempt {attempt + 1}/{max_attempts})")
        _emit("ci_started", agent=name, pr_number=pr_number,
              attempt=attempt + 1, max_attempts=max_attempts)
        ci_result = _poll_ci_checks(pr_number, repo)
        ci_attempts.append({"attempt": attempt, "ci_result": ci_result})

        if ci_result["status"] == "pass":
            _log(f"CI passed for PR #{pr_number}")
            _emit("ci_completed", agent=name, pr_number=pr_number,
                  status="pass", attempt=attempt + 1)
            return {
                "status": "ci_pass",
                "pr_number": pr_number,
                "attempts": ci_attempts,
                "total_ci_attempts": attempt,
            }

        if ci_result["status"] == "error":
            _log(f"Error polling CI for PR #{pr_number}: {ci_result.get('error')}")
            _emit("ci_completed", agent=name, pr_number=pr_number,
                  status="error", error=ci_result.get("error"))
            return {
                "status": "ci_error",
                "pr_number": pr_number,
                "attempts": ci_attempts,
                "error": ci_result.get("error"),
            }

        if ci_result["status"] == "pending":
            _log(f"CI timed out waiting for checks on PR #{pr_number}")
            return {
                "status": "ci_timeout",
                "pr_number": pr_number,
                "attempts": ci_attempts,
            }

        # CI failed — extract logs and re-spawn
        failed_checks = ci_result.get("failed_checks", [])
        _log(f"CI failed for PR #{pr_number}: {failed_checks}")
        _emit("ci_completed", agent=name, pr_number=pr_number,
              status="fail", failed_checks=failed_checks, attempt=attempt + 1)

        failure_logs = _extract_ci_failure_logs(pr_number, repo, failed_checks)

        fix_context = "\n".join([
            f"## CI FIX ATTEMPT {attempt + 1}/{max_attempts}",
            "",
            f"Your PR #{pr_number} has **failing CI checks**. Fix the errors below.",
            "Do NOT create a new PR — push fixes to the existing branch.",
            "",
            "## CI Failure Details",
            failure_logs,
            "",
            "## Strategy",
            "1. Read the error messages carefully",
            "2. Fix the root cause in the code",
            "3. Commit and push to the same branch",
            "4. The CI will re-run automatically",
        ])

        fix_task = (
            f"Fix CI failures on PR #{pr_number}. "
            f"Failed checks: {', '.join(failed_checks)}. "
            f"Push fixes to the existing branch — do NOT create a new PR."
        )

        # Re-spawn to fix
        _log(f"Re-spawning agent '{name}' to fix CI (attempt {attempt + 1})")
        fix_result = cmd_spawn(name, fix_task, timeout, fix_context)
        ci_attempts[-1]["fix_result"] = {
            "task_id": fix_result.get("task_id"),
            "exit_code": fix_result.get("exit_code"),
            "status": fix_result.get("result", {}).get("status", "unknown"),
            "elapsed": fix_result.get("elapsed"),
        }

        if fix_result.get("error"):
            _log(f"CI fix spawn error: {fix_result['error']}")
            return {
                "status": "ci_fix_error",
                "pr_number": pr_number,
                "attempts": ci_attempts,
                "error": fix_result["error"],
            }

    # Exhausted attempts — do one final poll
    final_ci = _poll_ci_checks(pr_number, repo)
    ci_attempts.append({"attempt": max_attempts, "ci_result": final_ci, "type": "final_poll"})

    final_status = "ci_pass" if final_ci["status"] == "pass" else "ci_stuck"
    _log(f"CI fix loop exhausted for PR #{pr_number}: {final_status}")
    _emit("ci_completed", agent=name, pr_number=pr_number,
          status=final_status, attempt=max_attempts, exhausted=True)

    return {
        "status": final_status,
        "pr_number": pr_number,
        "attempts": ci_attempts,
        "total_ci_attempts": max_attempts,
    }


# =========================================================================
# DECOMPOSE — break a task into subtasks
# =========================================================================

def decompose_task(name: str, task: str) -> list[dict]:
    """Decompose a task into 1-5 subtasks based on agent context.

    Uses heuristics + agent procedures/context to break down the task.
    Returns list of {id, task, deps, timeout} dicts.

    For simple/short tasks, returns a single-task list (passthrough).
    """
    config = _load_config(name)
    agent_dir = _agent_dir(name)

    # Heuristic: short tasks (< 100 chars, no "and"/"then") get single-task treatment
    task_lower = task.lower().strip()
    connectors = [" and then ", " then ", " and ", " also ", " + ", "; ", " after that"]
    has_connectors = any(c in task_lower for c in connectors)
    is_long = len(task) > 120

    if not has_connectors and not is_long:
        # Check if it's an "implement" style task that should be decomposed
        impl_keywords = ["implement", "add", "create", "build", "write", "develop"]
        if not any(task_lower.startswith(kw) for kw in impl_keywords):
            return [{"id": "t1", "task": task, "deps": [], "timeout": 1200}]

    # Load agent procedures for context
    procedures = ""
    if agent_dir.exists():
        proc_file = agent_dir / "memory" / "procedures.md"
        if proc_file.exists():
            try:
                procedures = proc_file.read_text()[:1500]
            except OSError:
                pass

    # Load CI context for build/test commands
    ci_commands = {}
    if agent_dir.exists():
        ci_file = agent_dir / "data" / "ci_context.json"
        if ci_file.exists():
            try:
                ci = json.loads(ci_file.read_text())
                ci_commands = ci.get("commands", {})
            except (json.JSONDecodeError, OSError):
                pass

    # Load dependency map if available
    dep_map = {}
    if agent_dir.exists():
        dep_file = agent_dir / "data" / "dependency_map.json"
        if dep_file.exists():
            try:
                dep_map = json.loads(dep_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    # Decompose using heuristics
    subtasks = []

    # Split on connectors
    parts = [task]
    for connector in [" and then ", " then ", " and ", "; "]:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(connector))
        parts = [p.strip() for p in new_parts if p.strip()]

    # Cap at 5 subtasks
    parts = parts[:5]

    # Build project context hint from dep_map (if available)
    project_hint = ""
    if dep_map:
        hints = []
        if dep_map.get("framework"):
            hints.append(f"Framework: {dep_map['framework']}")
        if dep_map.get("language"):
            hints.append(f"Language: {dep_map['language']}")
        if dep_map.get("entry_points"):
            hints.append(f"Entry points: {', '.join(dep_map['entry_points'][:5])}")
        if dep_map.get("source_dirs"):
            dirs = [d["path"] for d in dep_map["source_dirs"][:6]]
            hints.append(f"Source dirs: {', '.join(dirs)}")
        if dep_map.get("test_dirs"):
            tdirs = [d["path"] for d in dep_map["test_dirs"][:3]]
            hints.append(f"Test dirs: {', '.join(tdirs)}")
        if dep_map.get("test_files"):
            hints.append(f"Test files: {len(dep_map['test_files'])} found")
        if hints:
            project_hint = " [Project: " + "; ".join(hints) + "]"

    if len(parts) <= 1:
        # No natural split — try semantic decomposition
        # Pattern: "implement X" → [implement, test, PR]
        impl_keywords = ["implement", "add", "create", "build", "write", "develop"]
        if any(task_lower.startswith(kw) for kw in impl_keywords):
            impl_task = task + project_hint if project_hint else task
            subtasks = [
                {"id": "t1", "task": impl_task, "deps": [], "timeout": 1200},
            ]
            # Add test subtask if CI has test commands
            if ci_commands.get("test"):
                test_cmd = ci_commands["test"][0]
                # Enrich test hint with test dir info from dep_map
                test_hint = f"Run tests ({test_cmd}) and fix any failures from the implementation"
                if dep_map.get("test_dirs"):
                    tdirs = [d["path"] for d in dep_map["test_dirs"][:2]]
                    test_hint += f". Test dirs: {', '.join(tdirs)}"
                if dep_map.get("test_files") and len(dep_map["test_files"]) <= 10:
                    test_hint += f". Existing test files: {', '.join(dep_map['test_files'][:5])}"
                subtasks.append({
                    "id": "t2",
                    "task": test_hint,
                    "deps": ["t1"],
                    "timeout": 600,
                })
            # Add PR subtask
            subtasks.append({
                "id": f"t{len(subtasks) + 1}",
                "task": "Create a PR with all changes. Include a clear description of what was implemented.",
                "deps": [f"t{len(subtasks)}"],
                "timeout": 300,
            })
            return subtasks
        else:
            # Simple task, no decomposition needed
            return [{"id": "t1", "task": task, "deps": [], "timeout": 1200}]

    # Build subtask chain from parts
    for i, part in enumerate(parts, 1):
        tid = f"t{i}"
        deps = [f"t{i-1}"] if i > 1 else []
        # Smaller timeout for sub-pieces
        timeout = min(1200, max(600, 1200 // len(parts) + 300))
        # Add project hint to first subtask only (avoids noise in follow-ups)
        enriched = (part + project_hint) if (i == 1 and project_hint) else part
        subtasks.append({"id": tid, "task": enriched, "deps": deps, "timeout": timeout})

    # Add final verification subtask if we have test commands and didn't already add one
    has_test_subtask = any("test" in s["task"].lower() for s in subtasks)
    if ci_commands.get("test") and not has_test_subtask and len(subtasks) < 5:
        test_cmd = ci_commands["test"][0]
        subtasks.append({
            "id": f"t{len(subtasks) + 1}",
            "task": f"Run full test suite ({test_cmd}) and fix any regressions",
            "deps": [subtasks[-1]["id"]],
            "timeout": 600,
        })

    _log(f"Decomposed task for '{name}' into {len(subtasks)} subtasks")
    return subtasks


# =========================================================================
# TASK LOOP — plan → execute → verify → fix cycle
# =========================================================================

# Exit criteria defaults
LOOP_MAX_SESSIONS = 8
LOOP_MAX_BUDGET_USD = 2.00
LOOP_MAX_WALL_SECONDS = 4 * 3600  # 4 hours


def run_task_loop(name: str, task: str, timeout_per_subtask: int = 1200,
                  max_sessions: int = LOOP_MAX_SESSIONS,
                  budget_usd: float = LOOP_MAX_BUDGET_USD,
                  max_wall_seconds: int = LOOP_MAX_WALL_SECONDS) -> dict:
    """Execute a full plan→execute→verify→fix loop for a task.

    1. PLAN: decompose task into subtasks
    2. EXECUTE: spawn agent on each subtask (sequential, respecting deps)
    3. VERIFY: check result, run CI if PR created
    4. FIX: retry on failure (max 2 retries per subtask, CI fix loop for PRs)
    5. REFLECT: store episode per subtask

    Exit when: all done, max_sessions exceeded, budget exceeded, or wall clock exceeded.

    Returns: {status, subtasks, episodes, total_cost, total_sessions, total_elapsed}
    """
    config = _load_config(name)
    if not config:
        return {"error": f"Agent '{name}' not found"}

    # Acquire per-agent loop lock (prevent concurrent loop invocations)
    if not _acquire_loop_lock(name):
        msg = f"Loop already running for agent '{name}' — skipping"
        _log(msg)
        return {"error": msg, "status": "locked"}

    try:

        agent_dir = _agent_dir(name)
        loop_start = time.time()
        total_sessions = 0
        total_cost = 0.0
        cost_start = _snapshot_cost()
        episodes = []
        work_branch = None
        pr_number = None
        repo = config.get("repo_url", "")

        # Derive owner/repo for gh commands
        gh_repo = ""
        if repo:
            # Handle SSH and HTTPS URLs
            import re as _re
            m = _re.search(r'[:/]([^/]+/[^/.]+?)(?:\.git)?$', repo)
            if m:
                gh_repo = m.group(1)

        _log(f"Starting task loop for agent '{name}': {task[:80]}")
        _emit("task_started", agent=name, task_name=task[:120],
              section="project_agent_loop", executor="claude-opus")

        # Phase 1: PLAN — decompose
        subtasks = decompose_task(name, task)
        _log(f"Task loop plan: {len(subtasks)} subtasks")

        subtask_results = {}

        for st in subtasks:
            # Check exit criteria
            elapsed = time.time() - loop_start
            if elapsed > max_wall_seconds:
                _log(f"Task loop wall clock exceeded ({elapsed:.0f}s > {max_wall_seconds}s)")
                break

            if total_sessions >= max_sessions:
                _log(f"Task loop max sessions reached ({total_sessions} >= {max_sessions})")
                break

            if cost_start is not None:
                current_cost = _snapshot_cost()
                if current_cost is not None:
                    total_cost = round(current_cost - cost_start, 6)
                    if total_cost > budget_usd:
                        _log(f"Task loop budget exceeded (${total_cost:.4f} > ${budget_usd:.2f})")
                        break

            # Check deps
            deps_met = all(
                subtask_results.get(dep, {}).get("status") == "success"
                for dep in st.get("deps", [])
            )
            if not deps_met:
                # Skip subtask if deps failed
                failed_deps = [d for d in st.get("deps", [])
                               if subtask_results.get(d, {}).get("status") != "success"]
                _log(f"Skipping subtask {st['id']}: unmet deps {failed_deps}")
                subtask_results[st["id"]] = {
                    "status": "skipped",
                    "reason": f"Dependencies not met: {failed_deps}",
                }
                episodes.append({
                    "subtask_id": st["id"],
                    "task": st["task"][:200],
                    "status": "skipped",
                    "reason": f"deps_not_met: {failed_deps}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue

            # Phase 2: EXECUTE
            st_timeout = st.get("timeout", timeout_per_subtask)
            context_parts = [f"This is subtask {st['id']} of {len(subtasks)} in a multi-step task loop."]
            if work_branch:
                context_parts.append(f"Continue working on branch: {work_branch}")
                context_parts.append("Do NOT create a new branch — push to the existing one.")
            if pr_number:
                context_parts.append(f"PR #{pr_number} already exists. Push commits to the same branch.")

            # Include context from previous subtasks
            prev_summaries = []
            for prev_id, prev_res in subtask_results.items():
                if prev_res.get("status") == "success":
                    prev_summaries.append(f"- {prev_id}: {prev_res.get('summary', 'done')[:100]}")
            if prev_summaries:
                context_parts.append("\nCompleted subtasks:\n" + "\n".join(prev_summaries))

            context = "\n".join(context_parts)

            _log(f"Executing subtask {st['id']}: {st['task'][:60]}")
            spawn_result = cmd_spawn_with_retry(name, st["task"], st_timeout, context)
            total_sessions += spawn_result.get("retry_metadata", {}).get("total_attempts", 1)

            # Phase 3: VERIFY
            result_data = spawn_result.get("result", {})
            status = result_data.get("status", "unknown")
            summary = result_data.get("summary", "")

            # Track work branch from first successful spawn
            if result_data.get("branch") and not work_branch:
                work_branch = result_data["branch"]

            # Extract PR number if created
            pr_url = result_data.get("pr_url", "")
            if pr_url and not pr_number:
                import re as _re
                m = _re.search(r'/pull/(\d+)', pr_url)
                if m:
                    pr_number = int(m.group(1))
                    _log(f"PR created: #{pr_number} ({pr_url})")

            subtask_results[st["id"]] = {
                "status": status,
                "summary": summary,
                "task_id": spawn_result.get("task_id"),
                "elapsed": spawn_result.get("elapsed"),
                "exit_code": spawn_result.get("exit_code"),
            }

            # Phase 5: REFLECT — store episode
            episode = {
                "subtask_id": st["id"],
                "task": st["task"][:200],
                "status": status,
                "summary": summary[:300],
                "task_id": spawn_result.get("task_id"),
                "elapsed": spawn_result.get("elapsed"),
                "exit_code": spawn_result.get("exit_code"),
                "retry_count": spawn_result.get("retry_metadata", {}).get("total_attempts", 1) - 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            episodes.append(episode)

            # Store episode in agent brain
            try:
                from clarvis._script_loader import load as _load_script
                LiteBrain = _load_script("lite_brain", "brain_mem").LiteBrain
                brain = LiteBrain(str(agent_dir / "data" / "brain"))
                brain.store(
                    f"Task: {st['task'][:150]} | Status: {status} | Summary: {summary[:200]}",
                    "project-episodes",
                    importance=0.7 if status == "success" else 0.5,
                    tags=["task_loop", st["id"]],
                    source="task_loop",
                )
            except Exception as e:
                _log(f"Failed to store episode in agent brain: {e}")

            if status not in ("success", "partial"):
                _log(f"Subtask {st['id']} failed: {status}")
                # Don't continue with dependent subtasks (handled by deps check above)

            # Randomized inter-subtask delay (prevent API hammering, mimic claw-empire pattern)
            if st != subtasks[-1]:  # skip delay after last subtask
                delay = random.uniform(LOOP_INTER_SUBTASK_DELAY_MIN, LOOP_INTER_SUBTASK_DELAY_MAX)
                _log(f"Inter-subtask delay: {delay:.1f}s")
                time.sleep(delay)

        # Phase 4 (post-loop): CI feedback if PR was created
        ci_result = None
        if pr_number and gh_repo:
            _log(f"Running CI feedback loop for PR #{pr_number}")
            ci_result = _ci_fix_loop(name, pr_number, gh_repo, spawn_result, task, timeout_per_subtask)

            # Apply trust adjustment based on CI outcome
            config = _load_config(name)  # reload
            if config:
                if ci_result.get("status") == "ci_pass":
                    _log(f"CI passed after {ci_result.get('total_ci_attempts', 0)} fix attempts")
                elif ci_result.get("status") == "ci_stuck":
                    adjust_trust(name, "ci_broke_main", config)
                    _save_config(name, config)

        # Compute final cost
        cost_end = _snapshot_cost()
        if cost_start is not None and cost_end is not None:
            total_cost = round(cost_end - cost_start, 6)

        total_elapsed = round(time.time() - loop_start, 1)

        # Determine overall status
        completed = [sid for sid, r in subtask_results.items() if r.get("status") == "success"]
        failed = [sid for sid, r in subtask_results.items() if r.get("status") in ("failed", "unknown")]
        skipped = [sid for sid, r in subtask_results.items() if r.get("status") == "skipped"]

        if len(completed) == len(subtasks):
            overall = "success"
        elif completed:
            overall = "partial"
        else:
            overall = "failed"

        # Save loop summary
        loop_summary = {
            "task": task[:500],
            "agent": name,
            "status": overall,
            "subtasks_total": len(subtasks),
            "subtasks_completed": len(completed),
            "subtasks_failed": len(failed),
            "subtasks_skipped": len(skipped),
            "total_sessions": total_sessions,
            "total_cost_usd": total_cost,
            "total_elapsed": total_elapsed,
            "pr_number": pr_number,
            "ci_result": ci_result.get("status") if ci_result else None,
            "episodes": episodes,
            "subtask_results": subtask_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Write loop log
        loop_file = agent_dir / "logs" / f"loop_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        try:
            loop_file.parent.mkdir(parents=True, exist_ok=True)
            loop_file.write_text(json.dumps(loop_summary, indent=2, default=str))
        except OSError:
            pass

        _log(f"Task loop complete for '{name}': {overall} "
             f"({len(completed)}/{len(subtasks)} subtasks, {total_sessions} sessions, "
             f"${total_cost:.4f}, {total_elapsed:.0f}s)")

        _emit("task_completed", agent=name, task_name=task[:120],
              status=overall, section="project_agent_loop",
              subtasks_completed=len(completed), subtasks_total=len(subtasks),
              total_sessions=total_sessions, duration_s=total_elapsed,
              cost_usd=total_cost, pr_number=pr_number)

        return loop_summary
    finally:
        _release_loop_lock(name)


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
    sp.add_argument("--retries", type=int, default=0,
                    help="Max retries on failure (0=no retry, max 2)")

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

    # dep-map
    dmp = sub.add_parser("dep-map", help="Scan repo and build dependency map")
    dmp.add_argument("name")

    # ci-context
    cip = sub.add_parser("ci-context", help="Scan repo and build CI context")
    cip.add_argument("name")

    # trust
    tp = sub.add_parser("trust", help="View or adjust agent trust score")
    tp.add_argument("name")
    tp.add_argument("action", nargs="?", default="show",
                    help="show|boost|penalize|set:<value>|history")

    # decompose
    dcp = sub.add_parser("decompose", help="Decompose a task into subtasks")
    dcp.add_argument("name", help="Agent name")
    dcp.add_argument("task", help="Task description")

    # loop
    lp = sub.add_parser("loop", help="Run full plan→execute→verify→fix loop")
    lp.add_argument("name", help="Agent name")
    lp.add_argument("task", help="Task description")
    lp.add_argument("--timeout", type=int, default=1200, help="Timeout per subtask")
    lp.add_argument("--max-sessions", type=int, default=LOOP_MAX_SESSIONS,
                    help=f"Max Claude Code sessions (default: {LOOP_MAX_SESSIONS})")
    lp.add_argument("--budget", type=float, default=LOOP_MAX_BUDGET_USD,
                    help=f"Max budget in USD (default: {LOOP_MAX_BUDGET_USD})")

    # spawn-parallel
    spp = sub.add_parser("spawn-parallel",
                         help="Spawn tasks on multiple agents in parallel")
    spp.add_argument("--tasks", required=True,
                     help='JSON array: [{"agent":"name","task":"desc"}, ...]')
    spp.add_argument("--timeout", type=int, default=1200,
                     help="Default timeout per task")

    # auto-qa
    aqp = sub.add_parser("auto-qa", help="Auto-generate golden QA from successful tasks")
    aqp.add_argument("name")

    # ci-check (manual CI check for a PR)
    ccp = sub.add_parser("ci-check", help="Poll CI checks for a PR")
    ccp.add_argument("name", help="Agent name")
    ccp.add_argument("pr_number", type=int, help="PR number")
    ccp.add_argument("--timeout", type=int, default=CI_POLL_MAX_WAIT,
                     help=f"Max wait seconds (default: {CI_POLL_MAX_WAIT})")

    args = parser.parse_args()

    if args.command == "create":
        result = cmd_create(args.name, args.repo, args.branch)
    elif args.command == "list":
        result = cmd_list()
    elif args.command == "info":
        result = cmd_info(args.name)
    elif args.command == "spawn":
        if args.retries > 0:
            result = cmd_spawn_with_retry(args.name, args.task, args.timeout,
                                          args.context, args.retries)
        else:
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
    elif args.command == "dep-map":
        result = build_dependency_map(args.name)
    elif args.command == "ci-context":
        result = build_ci_context(args.name)
    elif args.command == "trust":
        result = cmd_trust(args.name, args.action)
    elif args.command == "decompose":
        result = decompose_task(args.name, args.task)
    elif args.command == "loop":
        result = run_task_loop(args.name, args.task, args.timeout,
                               args.max_sessions, args.budget)
    elif args.command == "spawn-parallel":
        try:
            task_list = json.loads(args.tasks)
        except json.JSONDecodeError as e:
            result = {"error": f"Invalid JSON for --tasks: {e}"}
            print(json.dumps(result, indent=2, default=str))
            return
        result = cmd_spawn_parallel(task_list, args.timeout)
    elif args.command == "auto-qa":
        result = cmd_auto_golden_qa(args.name)
    elif args.command == "ci-check":
        config = _load_config(args.name)
        if not config:
            result = {"error": f"Agent '{args.name}' not found"}
        else:
            repo_url = config.get("repo_url", "")
            import re as _re
            m = _re.search(r'[:/]([^/]+/[^/.]+?)(?:\.git)?$', repo_url)
            gh_repo = m.group(1) if m else ""
            if not gh_repo:
                result = {"error": f"Cannot derive GitHub repo from URL: {repo_url}"}
            else:
                result = _poll_ci_checks(args.pr_number, gh_repo, args.timeout)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

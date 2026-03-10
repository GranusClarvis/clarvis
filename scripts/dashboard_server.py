#!/usr/bin/env python3
"""Clarvis Visual Dashboard — SSE event hub + state API.

Starlette app serving:
  GET /                   — static files (PixiJS dashboard)
  GET /state              — full JSON snapshot of system state
  GET /queue-block/{tag}  — full QUEUE.md markdown block for a task tag
  GET /sse                — Server-Sent Events stream (live updates)

Data sources:
  - memory/evolution/QUEUE.md (task queue)
  - memory/cron/digest.md (cron activity)
  - data/dashboard/events.jsonl (dashboard events)
  - /tmp/clarvis_*.lock (active locks)
  - data/orchestration_scoreboard.jsonl (agent scores)
  - gh pr list (GitHub PRs, cached 60s)

Port: 18799 (LAN accessible, read-only, no auth)

Usage:
    python3 dashboard_server.py                  # start server
    python3 dashboard_server.py --port 18791     # custom port
"""

import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

# ── Paths ──────────────────────────────────────────────────────────────

WORKSPACE = Path("/home/agent/.openclaw/workspace")
QUEUE_FILE = WORKSPACE / "memory" / "evolution" / "QUEUE.md"
DIGEST_FILE = WORKSPACE / "memory" / "cron" / "digest.md"
EVENTS_FILE = WORKSPACE / "data" / "dashboard" / "events.jsonl"
SCOREBOARD_FILE = WORKSPACE / "data" / "orchestration_scoreboard.jsonl"
STATIC_DIR = Path(__file__).parent / "dashboard_static"
LOCK_DIR = Path("/tmp")
AGENTS_DIR = Path("/home/agent/agents")

# ── Config ─────────────────────────────────────────────────────────────

MAX_SSE_CONNECTIONS = 5
STATE_POLL_INTERVAL = 5     # seconds between state refreshes
PR_CACHE_TTL = 60           # seconds to cache GH PR list
EVENT_TAIL_COUNT = 30       # recent events to include in state

# ── Shared state ───────────────────────────────────────────────────────

_state = {
    "queue": [],
    "agents": [],
    "locks": [],
    "recent_events": [],
    "prs": [],
    "digest_lines": [],
    "scoreboard": [],
    "updated_at": None,
}
_sse_clients: list[asyncio.Queue] = []
_pr_cache = {"data": [], "ts": 0.0}


# ── Data readers ───────────────────────────────────────────────────────

def parse_queue(path: Path) -> list[dict]:
    """Parse QUEUE.md into structured task items."""
    if not path.exists():
        return []
    try:
        text = path.read_text()
    except OSError:
        return []

    tasks = []
    current_section = ""
    for line in text.splitlines():
        # Track section headers
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        # Match top-level task lines only: - [ ] [TAG] description
        m = re.match(r'^-\s+\[([ x~])\]\s+\[([A-Z0-9_]+)\]\s*(.*)', line)
        if m:
            check, tag, desc = m.groups()
            status = {"x": "done", "~": "in_progress", " ": "pending"}[check]

            # Extract owner from [SOURCE DATE] prefix in description
            owner_type = "manual"
            owner_name = "unknown"
            source_m = re.match(r'^\[([A-Z_]+)\s+\d{4}-\d{2}-\d{2}\]\s*(.*)', desc)
            if source_m:
                source_tag = source_m.group(1).lower()
                desc = source_m.group(2)
                # Map known source tags to owner types
                if source_tag in ("auto_split", "auto_evolve", "goal_tracker",
                                  "self_model", "perf_monitor"):
                    owner_type = "system"
                    owner_name = source_tag
                elif source_tag == "manual":
                    owner_type = "manual"
                    owner_name = "user"
                else:
                    owner_type = "system"
                    owner_name = source_tag

            tasks.append({
                "tag": tag,
                "status": status,
                "description": desc[:120],
                "section": current_section,
                "owner_type": owner_type,
                "owner_name": owner_name,
            })
    return tasks


def extract_queue_block(path: Path, tag: str) -> str | None:
    """Extract the full markdown block for a task identified by [TAG].

    Returns the task line plus all continuation lines (indented text,
    sub-bullets, blank lines) until the next task or section header.
    """
    if not path.exists():
        return None
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None

    # Regex to find a task line with the given tag (possibly indented)
    tag_pattern = re.compile(
        r'^\s*-\s+\[[ x~]\]\s+\[' + re.escape(tag) + r'\]\s'
    )
    # Regex to detect the *next* task line (any tag) or section header
    next_boundary = re.compile(r'^\s*-\s+\[[ x~]\]\s+\[[A-Z0-9_]+\]|^#{1,4}\s')

    start = None
    for i, line in enumerate(lines):
        if tag_pattern.match(line):
            start = i
            break
    if start is None:
        return None

    # Collect lines from start until the next task/header boundary
    block = [lines[start]]
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if next_boundary.match(line):
            break
        block.append(line)

    # Strip trailing blank lines
    while block and not block[-1].strip():
        block.pop()

    return "\n".join(block)


def read_locks() -> list[dict]:
    """Read active clarvis lockfiles from /tmp."""
    locks = []
    try:
        for f in LOCK_DIR.glob("clarvis_*.lock"):
            try:
                pid = f.read_text().strip()
                # Check if process is alive
                alive = os.path.exists(f"/proc/{pid}") if pid.isdigit() else False
                locks.append({
                    "name": f.stem.replace("clarvis_", ""),
                    "pid": pid,
                    "alive": alive,
                    "age_s": int(time.time() - f.stat().st_mtime),
                })
            except OSError:
                continue
    except OSError:
        pass
    return locks


def read_agents() -> list[dict]:
    """Read project agent configs."""
    agents = []
    for agents_root in [Path("/opt/clarvis-agents"), AGENTS_DIR]:
        if not agents_root.exists():
            continue
        try:
            for d in sorted(agents_root.iterdir()):
                cfg = d / "configs" / "agent.json"
                if cfg.exists():
                    try:
                        c = json.loads(cfg.read_text())
                        agents.append({
                            "name": c.get("name", d.name),
                            "status": c.get("status", "unknown"),
                            "trust_score": c.get("trust_score", 0.5),
                            "total_tasks": c.get("total_tasks", 0),
                            "total_successes": c.get("total_successes", 0),
                            "last_run": c.get("last_run"),
                            "last_task": (c.get("last_task") or {}).get("task", "")[:80],
                        })
                    except (json.JSONDecodeError, OSError):
                        continue
        except OSError:
            continue
    return agents


def _normalize_event_owner(ev: dict) -> dict:
    """Ensure every event has owner_type + owner_name (backfill legacy events)."""
    if "owner_type" in ev and "owner_name" in ev:
        return ev
    agent = ev.get("agent", "")
    section = ev.get("section", "")
    executor = ev.get("executor", "")
    if agent:
        ev.setdefault("owner_type", "subagent")
        ev.setdefault("owner_name", agent)
    elif section.startswith("cron_"):
        ev.setdefault("owner_type", "cron")
        ev.setdefault("owner_name", section)
    elif section.startswith("project_"):
        ev.setdefault("owner_type", "subagent")
        ev.setdefault("owner_name", section.replace("project_", ""))
    elif executor:
        ev.setdefault("owner_type", "system")
        ev.setdefault("owner_name", executor)
    else:
        ev.setdefault("owner_type", "system")
        ev.setdefault("owner_name", "clarvis")
    return ev


def read_recent_events(n: int = EVENT_TAIL_COUNT) -> list[dict]:
    """Read last N dashboard events, normalizing owner fields."""
    if not EVENTS_FILE.exists():
        return []
    try:
        lines = EVENTS_FILE.read_text().strip().splitlines()
        events = []
        for line in lines[-n:]:
            try:
                ev = json.loads(line)
                events.append(_normalize_event_owner(ev))
            except json.JSONDecodeError:
                continue
        return events
    except OSError:
        return []


def read_digest(n: int = 15) -> list[str]:
    """Read last N lines from digest."""
    if not DIGEST_FILE.exists():
        return []
    try:
        lines = DIGEST_FILE.read_text().strip().splitlines()
        return lines[-n:]
    except OSError:
        return []


def read_scoreboard(n: int = 20) -> list[dict]:
    """Read last N scoreboard entries."""
    if not SCOREBOARD_FILE.exists():
        return []
    try:
        lines = SCOREBOARD_FILE.read_text().strip().splitlines()
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
    except OSError:
        return []


def fetch_prs() -> list[dict]:
    """Fetch open PRs via gh CLI (cached)."""
    now = time.time()
    if now - _pr_cache["ts"] < PR_CACHE_TTL:
        return _pr_cache["data"]

    try:
        r = subprocess.run(
            ["gh", "pr", "list", "--json",
             "number,title,state,url,headRefName,author,createdAt",
             "--limit", "10"],
            capture_output=True, text=True, timeout=15,
            cwd=str(WORKSPACE),
        )
        if r.returncode == 0:
            prs = json.loads(r.stdout)
            _pr_cache["data"] = prs
            _pr_cache["ts"] = now
            return prs
    except (subprocess.TimeoutExpired, FileNotFoundError,
            json.JSONDecodeError, OSError):
        pass
    return _pr_cache["data"]


# ── State builder ──────────────────────────────────────────────────────

def build_state() -> dict:
    """Build full system state snapshot."""
    return {
        "queue": parse_queue(QUEUE_FILE),
        "agents": read_agents(),
        "locks": read_locks(),
        "recent_events": read_recent_events(),
        "prs": fetch_prs(),
        "digest_lines": read_digest(),
        "scoreboard": read_scoreboard(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── SSE broadcasting ──────────────────────────────────────────────────

async def broadcast(event_type: str, data: dict):
    """Send event to all connected SSE clients."""
    msg = json.dumps({"type": event_type, **data})
    dead = []
    for i, q in enumerate(_sse_clients):
        try:
            q.put_nowait({"event": event_type, "data": msg})
        except asyncio.QueueFull:
            dead.append(i)
    # Remove dead clients (reverse to preserve indices)
    for i in reversed(dead):
        _sse_clients.pop(i)


# ── Background poller ─────────────────────────────────────────────────

_file_mtimes: dict[str, float] = {}


async def state_poller():
    """Poll data sources for changes and broadcast updates."""
    global _state

    while True:
        try:
            new_state = await asyncio.get_event_loop().run_in_executor(
                None, build_state
            )

            # Detect changes and broadcast
            changed = False
            if new_state["queue"] != _state["queue"]:
                await broadcast("queue_update", {"queue": new_state["queue"]})
                changed = True
            if new_state["agents"] != _state["agents"]:
                await broadcast("agent_status", {"agents": new_state["agents"]})
                changed = True
            if new_state["locks"] != _state["locks"]:
                await broadcast("cron_activity", {"locks": new_state["locks"]})
                changed = True
            if len(new_state["recent_events"]) != len(_state["recent_events"]):
                await broadcast("events_update",
                              {"events": new_state["recent_events"][-5:]})
                changed = True
            if new_state["prs"] != _state["prs"]:
                await broadcast("pr_update", {"prs": new_state["prs"]})
                changed = True

            _state = new_state

        except Exception as e:
            print(f"[dashboard] poller error: {e}")

        await asyncio.sleep(STATE_POLL_INTERVAL)


# ── Routes ─────────────────────────────────────────────────────────────

async def state_endpoint(request):
    """GET /state — full state snapshot."""
    state = await asyncio.get_event_loop().run_in_executor(None, build_state)
    return JSONResponse(
        state,
        headers={"Cache-Control": "no-cache"},
    )


async def sse_endpoint(request):
    """GET /sse — Server-Sent Events stream."""
    if len(_sse_clients) >= MAX_SSE_CONNECTIONS:
        return JSONResponse(
            {"error": "Too many connections"},
            status_code=429,
        )

    queue: asyncio.Queue = asyncio.Queue(maxsize=60)
    _sse_clients.append(queue)

    # Send initial full state
    state = await asyncio.get_event_loop().run_in_executor(None, build_state)
    await queue.put({
        "event": "state",
        "data": json.dumps(state),
    })

    async def event_generator() -> AsyncGenerator:
        try:
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _sse_clients:
                _sse_clients.remove(queue)

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache"},
    )


async def queue_block_endpoint(request):
    """GET /queue-block/{tag} — full QUEUE.md block for a task tag."""
    tag = request.path_params.get("tag", "").upper()
    if not tag or not re.match(r'^[A-Z0-9_]+$', tag):
        return JSONResponse({"error": "Invalid tag"}, status_code=400)

    block = await asyncio.get_event_loop().run_in_executor(
        None, extract_queue_block, QUEUE_FILE, tag
    )
    if block is None:
        return JSONResponse({"error": f"Tag [{tag}] not found"}, status_code=404)

    return JSONResponse({"tag": tag, "block": block})


async def health_endpoint(request):
    """GET /health — simple health check."""
    return JSONResponse({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})


# ── App ────────────────────────────────────────────────────────────────

async def on_startup():
    """Start background poller."""
    asyncio.create_task(state_poller())


routes = [
    Route("/state", state_endpoint),
    Route("/queue-block/{tag}", queue_block_endpoint),
    Route("/sse", sse_endpoint),
    Route("/health", health_endpoint),
    Mount("/", app=StaticFiles(directory=str(STATIC_DIR), html=True)),
]

app = Starlette(routes=routes, on_startup=[on_startup])


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Clarvis Visual Dashboard")
    parser.add_argument("--port", type=int, default=18799)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    print(f"[dashboard] Starting on {args.host}:{args.port}")
    print(f"[dashboard] Static dir: {STATIC_DIR}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

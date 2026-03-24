#!/usr/bin/env python3
"""Clarvis website v0 — minimal Starlette server.

Serves static HTML pages and /api/public/status with live data
from CLR benchmark, Performance Index, and evolution queue.

Usage:
    python3 website/server.py [--port 18801] [--host 0.0.0.0]
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
import uvicorn

STATIC_DIR = Path(__file__).parent / "static"
WORKSPACE = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE / "data"
MEMORY_DIR = WORKSPACE / "memory"

CLR_FILE = DATA_DIR / "clr_benchmark.json"
PI_FILE = DATA_DIR / "performance_metrics.json"
QUEUE_FILE = MEMORY_DIR / "evolution" / "QUEUE.md"
QUEUE_ARCHIVE = MEMORY_DIR / "evolution" / "QUEUE_ARCHIVE.md"

# Page route mapping
PAGE_FILES = {
    "/": "index.html",
    "/architecture": "architecture.html",
    "/repos": "repos.html",
    "/benchmarks": "benchmarks.html",
    "/roadmap": "roadmap.html",
}


def _read_json(path: Path) -> dict | None:
    """Read a JSON file, return None on any error."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _parse_queue_counts(path: Path) -> dict:
    """Parse QUEUE.md to count pending/in-progress/done tasks."""
    pending = in_progress = done = 0
    try:
        text = path.read_text()
    except OSError:
        return {"pending": 0, "in_progress": 0, "done": 0}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            pending += 1
        elif stripped.startswith("- [~]"):
            in_progress += 1
        elif stripped.startswith("- [x]"):
            done += 1
    return {"pending": pending, "in_progress": in_progress, "done": done}


def _recent_completions(queue_path: Path, archive_path: Path, limit: int = 5) -> list:
    """Extract recent [x] completions from queue and archive."""
    completions = []
    tag_re = re.compile(r"\[x\]\s*\[([A-Z0-9_]+)\]")
    for path in [queue_path, archive_path]:
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            m = tag_re.search(line.strip())
            if m:
                completions.append({"tag": m.group(1), "status": "success"})
    return completions[:limit]


def _build_clr_payload(data: dict) -> dict:
    """Extract public-safe CLR fields."""
    return {
        "clr": data.get("clr"),
        "baseline_clr": data.get("baseline_clr"),
        "value_add": data.get("value_add"),
        "gate_pass": data.get("gate", {}).get("pass"),
        "dimensions": {
            k: v.get("score")
            for k, v in data.get("dimensions", {}).items()
        },
        "timestamp": data.get("timestamp"),
    }


def _build_pi_payload(data: dict) -> dict:
    """Extract public-safe PI fields."""
    summary = data.get("summary", {})
    return {
        "pi": data.get("pi", {}).get("pi") or summary.get("pi"),
        "dimensions": summary.get("total_scored", 0),
        "timestamp": data.get("timestamp"),
    }


async def page_handler(request):
    """Serve an HTML page from static/."""
    path = request.url.path.rstrip("/") or "/"
    filename = PAGE_FILES.get(path)
    if not filename:
        return HTMLResponse("<h1>404</h1>", status_code=404)
    filepath = STATIC_DIR / filename
    if not filepath.exists():
        return HTMLResponse("<h1>404</h1>", status_code=404)
    return HTMLResponse(filepath.read_text())


async def api_public_status(request):
    """Public status endpoint serving live CLR, PI, and queue data."""
    clr_raw = _read_json(CLR_FILE)
    pi_raw = _read_json(PI_FILE)
    queue = _parse_queue_counts(QUEUE_FILE)
    completions = _recent_completions(QUEUE_FILE, QUEUE_ARCHIVE)

    return JSONResponse({
        "mode": {"mode": "ge", "pending_mode": None},
        "queue": queue,
        "benchmarks": {
            "clr": _build_clr_payload(clr_raw) if clr_raw else None,
            "pi": _build_pi_payload(pi_raw) if pi_raw else None,
        },
        "recent_completions": completions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def generate_static_status() -> dict:
    """Build the status payload and return it (also writes to static/status.json)."""
    clr_raw = _read_json(CLR_FILE)
    pi_raw = _read_json(PI_FILE)
    queue = _parse_queue_counts(QUEUE_FILE)
    completions = _recent_completions(QUEUE_FILE, QUEUE_ARCHIVE)

    payload = {
        "mode": {"mode": "ge", "pending_mode": None},
        "queue": queue,
        "benchmarks": {
            "clr": _build_clr_payload(clr_raw) if clr_raw else None,
            "pi": _build_pi_payload(pi_raw) if pi_raw else None,
        },
        "recent_completions": completions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    out = STATIC_DIR / "status.json"
    out.write_text(json.dumps(payload, indent=2))
    return payload


routes = [
    Route("/", page_handler),
    Route("/architecture", page_handler),
    Route("/repos", page_handler),
    Route("/benchmarks", page_handler),
    Route("/roadmap", page_handler),
    Route("/api/public/status", api_public_status),
    Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clarvis website v0 server")
    parser.add_argument("--port", type=int, default=18801)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--generate-status", action="store_true",
                        help="Generate static/status.json and exit (for cron)")
    args = parser.parse_args()
    if args.generate_status:
        payload = generate_static_status()
        print(f"Wrote {STATIC_DIR / 'status.json'} ({len(payload['recent_completions'])} completions)")
    else:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")

#!/usr/bin/env python3
"""Clarvis website v0 — minimal Starlette server.

Serves static HTML pages and will proxy /api/public/status
once D2 endpoint is implemented.

Usage:
    python3 website/server.py [--port 18800] [--host 0.0.0.0]
"""

import argparse
import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
import uvicorn

STATIC_DIR = Path(__file__).parent / "static"

# Page route mapping
PAGE_FILES = {
    "/": "index.html",
    "/architecture": "architecture.html",
    "/repos": "repos.html",
    "/benchmarks": "benchmarks.html",
    "/roadmap": "roadmap.html",
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
    """Placeholder for /api/public/status — returns stub until D2 is built."""
    # TODO(D2): Replace with real data from dashboard/brain
    return JSONResponse({
        "mode": {"mode": "ge", "pending_mode": None, "updated_at": None},
        "queue": {"pending": 0, "in_progress": 0, "done": 0},
        "benchmarks": {
            "clr": None,
            "pi": None,
        },
        "recent_completions": [],
        "updated_at": None,
        "_note": "Stub response. Real data available after D2_PUBLIC_STATUS_ENDPOINT."
    })


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
    parser.add_argument("--port", type=int, default=18800)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

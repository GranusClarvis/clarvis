#!/usr/bin/env python3
"""Playwright smoke test: append a synthetic event to events.jsonl and verify
the dashboard UI updates live via SSE (status-bar #last-event changes).

Runs headless Chromium — no display required.  Designed for local + CI use.

Usage:
    python3 -m pytest scripts/tests/test_dashboard_live.py -v
"""

import json
import shutil
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import uvicorn

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        _browser = p.chromium.launch(headless=True)
        _browser.close()
    _PW_OK = True
except Exception:
    _PW_OK = False

pytestmark = pytest.mark.skipif(not _PW_OK, reason="Playwright browser unavailable")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Detect system Chromium (snap or apt) — Playwright's bundled Chromium
# may lack shared libs (libatk) on minimal installs.
_CHROMIUM_PATH = shutil.which("chromium-browser") or shutil.which("chromium")


# ── helpers ───────────────────────────────────────────────────────────────

def _free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _launch_browser(pw):
    """Launch headless Chromium, preferring system binary if available."""
    kwargs = {"headless": True}
    if _CHROMIUM_PATH:
        kwargs["executable_path"] = _CHROMIUM_PATH
    return pw.chromium.launch(**kwargs)


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def dashboard(tmp_path, monkeypatch):
    """Start a dashboard server on a random port with isolated data paths.

    Yields (base_url, events_file) so the test can append events and browse.
    """
    import dashboard_server as ds

    # Isolated data files
    events_file = tmp_path / "events.jsonl"
    events_file.touch()
    queue_file = tmp_path / "QUEUE.md"
    queue_file.write_text("## Test\n- [ ] [SMOKE] placeholder task\n")
    digest_file = tmp_path / "digest.md"
    digest_file.write_text("test digest line\n")
    scoreboard_file = tmp_path / "scoreboard.jsonl"
    scoreboard_file.touch()

    # Patch module-level paths
    monkeypatch.setattr(ds, "EVENTS_FILE", events_file)
    monkeypatch.setattr(ds, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(ds, "DIGEST_FILE", digest_file)
    monkeypatch.setattr(ds, "SCOREBOARD_FILE", scoreboard_file)
    monkeypatch.setattr(ds, "LOCK_DIR", tmp_path)
    monkeypatch.setattr(ds, "AGENTS_DIR", tmp_path / "agents")
    # Speed up polling for the test
    monkeypatch.setattr(ds, "STATE_POLL_INTERVAL", 1)

    # Reset shared state so previous test state doesn't leak
    ds._state = {
        "queue": [], "agents": [], "locks": [], "recent_events": [],
        "prs": [], "digest_lines": [], "scoreboard": [], "updated_at": None,
    }
    ds._sse_clients.clear()
    ds._file_mtimes.clear()
    ds._pr_cache.update({"data": [], "ts": 0.0})

    # Stub out GH PR fetch (no network in tests)
    monkeypatch.setattr(ds, "fetch_prs", lambda: [])

    port = _free_port()
    config = uvicorn.Config(
        ds.app, host="127.0.0.1", port=port, log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is accepting connections
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        pytest.fail("Dashboard server failed to start")

    yield f"http://127.0.0.1:{port}", events_file

    server.should_exit = True
    thread.join(timeout=5)


# ── test ──────────────────────────────────────────────────────────────────

def test_sse_live_update(dashboard):
    """Append a synthetic event and verify the status bar reflects it."""
    from playwright.sync_api import sync_playwright

    base_url, events_file = dashboard

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded")

        # Wait for SSE connection — status-bar shows "LIVE"
        page.wait_for_function(
            'document.getElementById("conn-label").textContent === "LIVE"',
            timeout=10_000,
        )

        # Record initial last-event text
        initial_text = page.text_content("#last-event")

        # Append a synthetic event
        event = {
            "type": "task_completed",
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": "smoke-test",
            "task_name": "Playwright smoke",
            "status": "success",
        }
        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        # Wait for the status bar to update (poll interval is 1s in test)
        page.wait_for_function(
            f'''() => {{
                const el = document.getElementById("last-event");
                return el && el.textContent !== "{initial_text}"
                       && el.textContent.includes("task_completed");
            }}''',
            timeout=15_000,
        )

        final_text = page.text_content("#last-event")
        assert "task_completed" in final_text

        # Screenshot for visual verification (saved next to events_file in tmp_path)
        page.screenshot(path=str(events_file.parent / "dashboard_live.png"))

        browser.close()


def test_sse_connection_indicator(dashboard):
    """Verify the SSE connection dot turns green on connect."""
    from playwright.sync_api import sync_playwright

    base_url, _ = dashboard

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded")

        page.wait_for_function(
            'document.getElementById("conn-dot").classList.contains("dot-green")',
            timeout=10_000,
        )
        label = page.text_content("#conn-label")
        assert label == "LIVE"

        browser.close()


def test_queue_reflected_in_status_bar(dashboard):
    """Verify the placeholder queue task shows up in the status bar."""
    from playwright.sync_api import sync_playwright

    base_url, _ = dashboard

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded")

        # Wait for state to load
        page.wait_for_function(
            'document.getElementById("pending-count").textContent.includes("pending")',
            timeout=10_000,
        )
        text = page.text_content("#pending-count")
        assert "1 pending" in text

        browser.close()

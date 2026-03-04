#!/usr/bin/env python3
"""ClarvisBrowser — Unified high-performance browser automation for Clarvis agents.

Combines two engines:
  1. Agent-Browser (Vercel) — Snapshot/refs system, 93% fewer tokens, Rust CLI speed
  2. Playwright CDP (existing BrowserAgent) — Session persistence, file uploads, JS eval

The module auto-selects the best engine per operation. Agent-Browser handles
navigation, clicking, form filling, and snapshots. Playwright handles session
persistence, file uploads, dynamic file choosers, and raw JS evaluation.

Usage (as library):
    from clarvis_browser import ClarvisBrowser
    async with ClarvisBrowser() as cb:
        await cb.goto("https://example.com")
        snap = await cb.snapshot()          # Get page elements with refs
        await cb.click("@e2")              # Click by ref (fast, token-efficient)
        await cb.fill("@e3", "hello")      # Fill input by ref
        text = await cb.get_text("@e1")    # Extract text by ref
        await cb.screenshot("/tmp/s.png")  # Screenshot with optional annotations
        md = await cb.markdown()            # Clean markdown extraction
        await cb.wait_for_text("Welcome")  # Wait for text appearance

Usage (CLI):
    python3 clarvis_browser.py goto https://example.com
    python3 clarvis_browser.py snapshot [-i] [--json]
    python3 clarvis_browser.py click @e2
    python3 clarvis_browser.py fill @e3 "user@example.com"
    python3 clarvis_browser.py text @e1
    python3 clarvis_browser.py screenshot [url] [path] [--annotate]
    python3 clarvis_browser.py markdown [url]
    python3 clarvis_browser.py search "query"
    python3 clarvis_browser.py wait-text "Welcome" [timeout_ms]
    python3 clarvis_browser.py upload /path/to/file [selector]
    python3 clarvis_browser.py agent "Find the latest Python release"
    python3 clarvis_browser.py status
    python3 clarvis_browser.py tabs
    python3 clarvis_browser.py tab-new [url]
    python3 clarvis_browser.py find role button "Submit"
    python3 clarvis_browser.py eval "document.title"
    python3 clarvis_browser.py save-session [path]
    python3 clarvis_browser.py session-info [path]

Flags:
    --persist       Auto-save session on exit
    --session PATH  Use specific session file
    --headed        Use headed mode (visible browser)
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CDP_PORT = int(os.environ.get("CLARVIS_CDP_PORT", "18800"))
AGENT_BROWSER_BIN = os.environ.get(
    "AGENT_BROWSER_BIN",
    shutil.which("agent-browser") or "/home/agent/.npm-global/bin/agent-browser"
)
SCREENSHOT_DIR = Path("/tmp/clarvis-screenshots")
SESSION_DIR = Path("/home/agent/.openclaw/workspace/data/browser_sessions")
DEFAULT_SESSION_FILE = SESSION_DIR / "default_session.json"

# Agent LLM config for browser-use agent mode
AGENT_MODEL = os.environ.get("CLARVIS_AGENT_MODEL", "google/gemini-2.5-flash")
AUTH_JSON = Path("/home/agent/.openclaw/agents/main/agent/auth.json")

# Timeouts
DEFAULT_TIMEOUT_MS = 25000
NAVIGATION_TIMEOUT_MS = 30000


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class BrowseResult:
    """Result from a browser operation."""
    url: str = ""
    title: str = ""
    text: str = ""
    snapshot: str = ""
    refs: dict = field(default_factory=dict)
    screenshot_path: Optional[str] = None
    links: list = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: float = 0
    engine: str = ""  # "agent-browser" or "playwright"

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        d = {
            "url": self.url,
            "title": self.title,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "engine": self.engine,
        }
        if self.text:
            d["text"] = self.text[:2000]
        if self.snapshot:
            d["snapshot"] = self.snapshot[:3000]
        if self.refs:
            d["refs_count"] = len(self.refs)
        if self.screenshot_path:
            d["screenshot_path"] = self.screenshot_path
        if self.links:
            d["links_count"] = len(self.links)
        return d


# ---------------------------------------------------------------------------
# Agent-Browser CLI wrapper (fast, token-efficient)
# ---------------------------------------------------------------------------
class _AgentBrowserCLI:
    """Thin wrapper around the agent-browser Rust CLI."""

    def __init__(self, cdp_port: int = CDP_PORT, session: Optional[str] = None):
        self.cdp_port = cdp_port
        self.session = session
        self._available = None

    def available(self) -> bool:
        """Check if agent-browser CLI is installed and reachable."""
        if self._available is not None:
            return self._available
        try:
            r = subprocess.run(
                [AGENT_BROWSER_BIN, "--version"],
                capture_output=True, text=True, timeout=5
            )
            self._available = r.returncode == 0
        except Exception:
            self._available = False
        return self._available

    def _base_args(self) -> list:
        args = [AGENT_BROWSER_BIN, "--cdp", str(self.cdp_port)]
        if self.session:
            args.extend(["--session", self.session])
        return args

    def run(self, *cmd_args, timeout: int = 30, json_output: bool = False) -> dict:
        """Run an agent-browser command synchronously. Returns parsed result."""
        args = self._base_args()
        if json_output:
            args.append("--json")
        args.extend(str(a) for a in cmd_args)

        t0 = time.monotonic()
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout
            )
            elapsed = (time.monotonic() - t0) * 1000
            output = r.stdout.strip()
            stderr = r.stderr.strip()

            if json_output and output:
                try:
                    parsed = json.loads(output)
                    parsed["_elapsed_ms"] = elapsed
                    return parsed
                except json.JSONDecodeError:
                    pass

            return {
                "success": r.returncode == 0,
                "data": output,
                "error": stderr if r.returncode != 0 else None,
                "_elapsed_ms": elapsed,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "_elapsed_ms": (time.monotonic() - t0) * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "_elapsed_ms": (time.monotonic() - t0) * 1000,
            }

    async def arun(self, *cmd_args, timeout: int = 30,
                   json_output: bool = False) -> dict:
        """Run an agent-browser command asynchronously."""
        args = self._base_args()
        if json_output:
            args.append("--json")
        args.extend(str(a) for a in cmd_args)

        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            elapsed = (time.monotonic() - t0) * 1000
            output = stdout.decode().strip()
            err_text = stderr.decode().strip()

            if json_output and output:
                try:
                    parsed = json.loads(output)
                    parsed["_elapsed_ms"] = elapsed
                    return parsed
                except json.JSONDecodeError:
                    pass

            return {
                "success": proc.returncode == 0,
                "data": output,
                "error": err_text if proc.returncode != 0 else None,
                "_elapsed_ms": elapsed,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "_elapsed_ms": (time.monotonic() - t0) * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "_elapsed_ms": (time.monotonic() - t0) * 1000,
            }


# ---------------------------------------------------------------------------
# ClarvisBrowser — unified interface
# ---------------------------------------------------------------------------
class ClarvisBrowser:
    """Unified browser automation combining Agent-Browser + Playwright.

    Agent-Browser is used for:
      - Navigation (open), snapshot/refs, click, fill, type, get text/html
      - Screenshot (with --annotate support)
      - find (semantic element finding), wait, tabs
      - All ref-based operations (@e1, @e2, etc.)

    Playwright (via BrowserAgent) is used as fallback and for:
      - Session persistence (cookies + localStorage + sessionStorage)
      - File uploads (static and dynamic file chooser)
      - Raw JavaScript evaluation
      - LLM-driven agent mode (browser-use)
      - Markdown extraction (JS-based DOM walker)
      - Web search with result parsing
    """

    def __init__(self, cdp_port: int = CDP_PORT,
                 session_file: Optional[str] = None,
                 persist_session: bool = False):
        self.cdp_port = cdp_port
        self.persist_session = persist_session
        # Always resolve session file — load existing sessions even without persist
        if session_file:
            self.session_file = Path(session_file)
        else:
            self.session_file = DEFAULT_SESSION_FILE
        self._ab = _AgentBrowserCLI(cdp_port=cdp_port)
        self._pw_agent = None  # Lazy-loaded BrowserAgent
        self._last_snapshot = None
        self._last_refs = {}
        self._session_loaded = False

    async def __aenter__(self):
        await self._load_session_cookies()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        """Clean up resources. Save session if persist_session is enabled."""
        if self.persist_session:
            try:
                await self.save_session()
            except Exception as e:
                logger.warning("Failed to auto-save session on close: %s", e)
        if self._pw_agent:
            # Disable BrowserAgent's own auto-save since we already saved
            self._pw_agent.persist_session = False
            await self._pw_agent.stop()
            self._pw_agent = None

    async def _load_session_cookies(self):
        """Load saved session cookies into the browser via agent-browser CLI.

        This ensures both Agent-Browser and Playwright see the same cookies,
        since they share the same underlying Chromium browser via CDP.
        Critical for maintaining login state across engines.
        """
        if self._session_loaded:
            return
        if not self.session_file or not self.session_file.exists():
            self._session_loaded = True
            return

        try:
            with open(self.session_file) as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("Invalid session file %s: %s", self.session_file, e)
            self._session_loaded = True
            return

        cookies = state.get("cookies", [])
        if not cookies:
            self._session_loaded = True
            return

        # Inject cookies via agent-browser CLI (works for both engines)
        if self.has_agent_browser:
            loaded = 0
            failed = 0
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                domain = cookie.get("domain", "")
                if not name or not domain:
                    continue

                args = ["cookies", "set", name, value]

                # agent-browser requires EITHER --url OR --domain, not both.
                # Use --domain + --path for domain cookies (dot-prefixed),
                # use --url for exact-domain cookies.
                path = cookie.get("path", "/")
                if domain.startswith("."):
                    args.extend(["--domain", domain])
                    args.extend(["--path", path or "/"])
                else:
                    scheme = "https" if cookie.get("secure", False) else "http"
                    args.extend(["--url", f"{scheme}://{domain}{path}"])

                if cookie.get("httpOnly", False):
                    args.append("--httpOnly")
                if cookie.get("secure", False):
                    args.append("--secure")
                if cookie.get("sameSite"):
                    args.extend(["--sameSite", cookie["sameSite"]])
                if cookie.get("expires", -1) > 0:
                    args.extend(["--expires", str(int(cookie["expires"]))])

                r = await self._ab.arun(*args, timeout=5)
                if r.get("success", False) or r.get("error") is None:
                    loaded += 1
                else:
                    failed += 1
                    logger.debug("Cookie %s@%s failed: %s", name, domain,
                                 r.get("error", "unknown"))

            logger.info("Session loaded: %d/%d cookies injected via agent-browser (%d failed)",
                        loaded, loaded + failed, failed)
        else:
            # No agent-browser — fall back to loading via Playwright
            logger.info("No agent-browser; loading session via Playwright fallback")
            await self._get_playwright()  # This triggers BrowserAgent._load_session()

        self._session_loaded = True

    async def _get_playwright(self):
        """Lazy-load the Playwright-based BrowserAgent."""
        if self._pw_agent is None:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from browser_agent import BrowserAgent
            self._pw_agent = BrowserAgent(
                cdp_url=f"http://127.0.0.1:{self.cdp_port}",
                session_file=str(self.session_file) if self.session_file else None,
                persist_session=self.persist_session,
            )
            await self._pw_agent.start()
        return self._pw_agent

    @property
    def has_agent_browser(self) -> bool:
        """Whether agent-browser CLI is available."""
        return self._ab.available()

    # -- Navigation -----------------------------------------------------------

    async def goto(self, url: str, wait_until: str = "domcontentloaded",
                   timeout_ms: int = NAVIGATION_TIMEOUT_MS) -> BrowseResult:
        """Navigate to a URL. Uses agent-browser if available, else Playwright."""
        t0 = time.monotonic()
        if self.has_agent_browser:
            timeout_s = max(5, timeout_ms // 1000)
            r = await self._ab.arun("open", url, timeout=timeout_s)
            elapsed = (time.monotonic() - t0) * 1000
            if r.get("success", False) or r.get("data"):
                # Get title from output (format: "✓ Title\n  url")
                data = r.get("data", "")
                title = ""
                for line in data.split("\n"):
                    line = line.strip()
                    # Strip ANSI codes for parsing
                    clean = _strip_ansi(line)
                    if clean.startswith("✓ "):
                        title = clean[2:].strip()
                    elif clean and not title:
                        title = clean
                return BrowseResult(
                    url=url, title=title, elapsed_ms=elapsed,
                    engine="agent-browser"
                )
            else:
                return BrowseResult(
                    url=url, error=r.get("error", "Navigation failed"),
                    elapsed_ms=elapsed, engine="agent-browser"
                )

        # Fallback: Playwright
        pw = await self._get_playwright()
        result = await pw.navigate(url, wait_until=wait_until,
                                   timeout_ms=timeout_ms)
        result_br = BrowseResult(
            url=result.url, title=result.title, error=result.error,
            elapsed_ms=result.elapsed_ms, engine="playwright"
        )
        return result_br

    async def open(self, url: str, **kwargs) -> BrowseResult:
        """Alias for goto()."""
        return await self.goto(url, **kwargs)

    async def navigate(self, url: str, **kwargs) -> BrowseResult:
        """Alias for goto() — backward compatible with BrowserAgent API."""
        return await self.goto(url, **kwargs)

    # -- Snapshot & Refs (Agent-Browser exclusive) ----------------------------

    async def snapshot(self, interactive_only: bool = True,
                       compact: bool = False,
                       scope: Optional[str] = None,
                       depth: Optional[int] = None) -> BrowseResult:
        """Get accessibility snapshot with element refs.

        This is the core token-efficient operation. Returns a structured
        snapshot where each interactive element has a ref like @e1, @e2.

        Args:
            interactive_only: Only show interactive elements (buttons, inputs, links).
            compact: Remove empty structural elements.
            scope: CSS selector to scope the snapshot to.
            depth: Max depth of the accessibility tree.
        """
        t0 = time.monotonic()
        if not self.has_agent_browser:
            return BrowseResult(
                error="agent-browser not available for snapshot",
                elapsed_ms=0, engine="none"
            )

        args = ["snapshot"]
        if interactive_only:
            args.append("-i")
        if compact:
            args.append("-c")
        if scope:
            args.extend(["-s", scope])
        if depth is not None:
            args.extend(["-d", str(depth)])

        # Get JSON for structured data
        r = await self._ab.arun(*args, json_output=True)
        elapsed = (time.monotonic() - t0) * 1000

        if r.get("success", False):
            data = r.get("data", {})
            snap_text = data.get("snapshot", r.get("data", ""))
            refs = data.get("refs", {})
            self._last_snapshot = snap_text
            self._last_refs = refs
            return BrowseResult(
                url=data.get("origin", ""),
                snapshot=snap_text if isinstance(snap_text, str) else str(snap_text),
                refs=refs,
                elapsed_ms=elapsed,
                engine="agent-browser",
            )

        # Fallback: try non-JSON
        r2 = await self._ab.arun(*args, json_output=False)
        snap_text = r2.get("data", "")
        return BrowseResult(
            snapshot=snap_text, elapsed_ms=elapsed,
            error=r2.get("error"), engine="agent-browser"
        )

    # -- Click ----------------------------------------------------------------

    async def click(self, selector: str, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        """Click an element. Supports @refs, CSS selectors, text= selectors.

        Examples:
            await cb.click("@e2")              # By ref (preferred)
            await cb.click("text=Sign in")     # By text
            await cb.click("#submit-btn")      # By CSS
        """
        if self.has_agent_browser:
            r = await self._ab.arun("click", selector,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", r.get("data", "").strip()):
                return
            # If ref not found, fall through to playwright
            if not selector.startswith("@"):
                raise RuntimeError(r.get("error", "Click failed"))

        # Fallback for CSS/text selectors
        pw = await self._get_playwright()
        if selector.startswith("text="):
            await pw.click_by_text(selector[5:], timeout_ms=timeout_ms)
        else:
            await pw.click(selector, timeout_ms=timeout_ms)

    async def click_text(self, text: str, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        """Click the first element with the given visible text."""
        if self.has_agent_browser:
            r = await self._ab.arun("find", "text", text, "click",
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.click_by_text(text, timeout_ms=timeout_ms)

    async def click_role(self, role: str, name: str,
                         timeout_ms: int = DEFAULT_TIMEOUT_MS):
        """Click element by ARIA role and name. E.g., click_role("button", "Submit")."""
        if self.has_agent_browser:
            r = await self._ab.arun("find", "role", role, "click",
                                    "--name", name,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.click_by_role(role, name, timeout_ms=timeout_ms)

    # -- Fill & Type ----------------------------------------------------------

    async def fill(self, selector: str, text: str,
                   timeout_ms: int = DEFAULT_TIMEOUT_MS):
        """Fill a form field (clears first). Supports @refs and CSS selectors."""
        if self.has_agent_browser:
            r = await self._ab.arun("fill", selector, text,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", r.get("data", "").strip()):
                return
            if not selector.startswith("@"):
                raise RuntimeError(r.get("error", "Fill failed"))
        pw = await self._get_playwright()
        await pw.fill(selector, text, timeout_ms=timeout_ms)

    async def type_text(self, selector: str, text: str):
        """Type text without clearing (appends). Supports @refs and CSS."""
        if self.has_agent_browser:
            r = await self._ab.arun("type", selector, text)
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.type_text(selector, text)

    async def press_key(self, key: str):
        """Press a keyboard key (Enter, Tab, Escape, etc.)."""
        if self.has_agent_browser:
            r = await self._ab.arun("press", key)
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.press_key(key)

    # -- Get / Extract --------------------------------------------------------

    async def get_text(self, selector: str = "") -> str:
        """Get text content of an element or the whole page.

        Args:
            selector: @ref, CSS selector, or empty for full page text.
        """
        if self.has_agent_browser and selector:
            r = await self._ab.arun("get", "text", selector)
            if r.get("success", False):
                return r.get("data", "")
        pw = await self._get_playwright()
        if selector and not selector.startswith("@"):
            return await pw.extract_text(selector)
        return await pw.extract_text("body")

    async def get_html(self, selector: str = "html") -> str:
        """Get innerHTML of an element."""
        if self.has_agent_browser and selector:
            r = await self._ab.arun("get", "html", selector)
            if r.get("success", False):
                return r.get("data", "")
        pw = await self._get_playwright()
        return await pw.extract_html(selector)

    async def get_url(self) -> str:
        """Get the current page URL."""
        if self.has_agent_browser:
            r = await self._ab.arun("get", "url")
            if r.get("success", False):
                return r.get("data", "")
        pw = await self._get_playwright()
        info = await pw.get_page_info()
        return info.get("url", "")

    async def get_title(self) -> str:
        """Get the current page title."""
        if self.has_agent_browser:
            r = await self._ab.arun("get", "title")
            if r.get("success", False):
                return r.get("data", "")
        pw = await self._get_playwright()
        info = await pw.get_page_info()
        return info.get("title", "")

    async def extract_links(self) -> list:
        """Extract all links from the current page."""
        pw = await self._get_playwright()
        return await pw.extract_links()

    # -- Screenshot -----------------------------------------------------------

    async def screenshot(self, path: Optional[str] = None,
                         full_page: bool = False,
                         annotate: bool = False) -> str:
        """Take a screenshot. Supports annotation (numbered element labels).

        Args:
            path: Output file path. Auto-generated if None.
            full_page: Capture full scrollable page.
            annotate: Overlay numbered labels on interactive elements.
        """
        if path is None:
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            path = str(SCREENSHOT_DIR / f"shot_{int(time.time())}.png")

        if self.has_agent_browser:
            args = ["screenshot"]
            if full_page:
                args.append("--full")
            if annotate:
                args.append("--annotate")
            args.append(path)
            r = await self._ab.arun(*args)
            if r.get("success", False):
                return path

        pw = await self._get_playwright()
        return await pw.screenshot(path=path, full_page=full_page)

    # -- Markdown extraction --------------------------------------------------

    async def markdown(self, url: Optional[str] = None) -> str:
        """Extract page content as clean markdown."""
        if url:
            await self.goto(url)
        pw = await self._get_playwright()
        return await pw.extract_markdown()

    # -- Wait -----------------------------------------------------------------

    async def wait_for_text(self, text: str,
                            timeout_ms: int = 10000) -> bool:
        """Wait for text to appear on the page."""
        if self.has_agent_browser:
            r = await self._ab.arun("wait", "--text", text,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", False):
                return True
        pw = await self._get_playwright()
        return await pw.wait_for_text(text, timeout_ms=timeout_ms)

    async def wait_for(self, selector: str, timeout_ms: int = 10000):
        """Wait for an element to be visible."""
        if self.has_agent_browser:
            r = await self._ab.arun("wait", selector,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.wait_for(selector, timeout_ms=timeout_ms)

    async def wait_ms(self, ms: int):
        """Wait a fixed number of milliseconds."""
        await asyncio.sleep(ms / 1000)

    # -- Modals & Popups ------------------------------------------------------

    async def handle_modal(self, timeout_ms: int = 2000) -> bool:
        """Auto-dismiss modals, popups, cookie banners, dialogs."""
        pw = await self._get_playwright()
        return await pw.handle_modal(timeout_ms=timeout_ms)

    # -- File Upload ----------------------------------------------------------

    async def upload_file(self, filepath: str,
                          selector: Optional[str] = None,
                          timeout_ms: int = 10000):
        """Upload a file to a file input."""
        if self.has_agent_browser and selector:
            r = await self._ab.arun("upload", selector, filepath,
                                    timeout=max(5, timeout_ms // 1000))
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.upload_file(filepath, selector=selector, timeout_ms=timeout_ms)

    async def upload_file_on_click(self, click_selector: str, filepath: str,
                                   timeout_ms: int = 10000):
        """Upload a file by clicking a trigger element (handles dynamic file choosers)."""
        pw = await self._get_playwright()
        await pw.upload_file_on_click(click_selector, filepath, timeout_ms=timeout_ms)

    # -- JavaScript evaluation ------------------------------------------------

    async def evaluate(self, js: str):
        """Run arbitrary JavaScript on the page."""
        if self.has_agent_browser:
            r = await self._ab.arun("eval", js)
            if r.get("success", False):
                data = r.get("data", "")
                try:
                    return json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    return data
        pw = await self._get_playwright()
        return await pw.evaluate(js)

    # -- Navigation history ---------------------------------------------------

    async def go_back(self):
        """Go back in browser history."""
        if self.has_agent_browser:
            r = await self._ab.arun("back")
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.go_back()

    async def go_forward(self):
        """Go forward in browser history."""
        if self.has_agent_browser:
            r = await self._ab.arun("forward")
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.go_forward()

    # -- Tabs -----------------------------------------------------------------

    async def tabs(self) -> str:
        """List open tabs."""
        if self.has_agent_browser:
            r = await self._ab.arun("tab")
            return r.get("data", "")
        return "(tabs not supported without agent-browser)"

    async def tab_new(self, url: Optional[str] = None) -> str:
        """Open a new tab."""
        if self.has_agent_browser:
            args = ["tab", "new"]
            if url:
                args.append(url)
            r = await self._ab.arun(*args)
            return r.get("data", "")
        return "(tab management not supported without agent-browser)"

    async def tab_switch(self, n: int):
        """Switch to tab number n."""
        if self.has_agent_browser:
            await self._ab.arun("tab", str(n))

    async def tab_close(self, n: Optional[int] = None):
        """Close a tab."""
        if self.has_agent_browser:
            args = ["tab", "close"]
            if n is not None:
                args.append(str(n))
            await self._ab.arun(*args)

    # -- Semantic find --------------------------------------------------------

    async def find_and_click(self, by: str, value: str, **kwargs) -> bool:
        """Find an element semantically and click it.

        Args:
            by: "role", "label", "text", "first"
            value: The role name, label text, etc.
            kwargs: Additional args like name= for role.
        """
        if self.has_agent_browser:
            args = ["find", by, value, "click"]
            name = kwargs.get("name")
            if name:
                args.extend(["--name", name])
            r = await self._ab.arun(*args)
            return r.get("success", False)
        return False

    async def find_and_fill(self, by: str, value: str,
                            text: str, **kwargs) -> bool:
        """Find an element semantically and fill it."""
        if self.has_agent_browser:
            args = ["find", by, value, "fill", text]
            r = await self._ab.arun(*args)
            return r.get("success", False)
        return False

    # -- Scroll ---------------------------------------------------------------

    async def scroll(self, direction: str = "down", amount: int = 500,
                     selector: Optional[str] = None):
        """Scroll the page or a specific element.

        Args:
            direction: "up" or "down"
            amount: Pixels to scroll
            selector: Optional element to scroll within
        """
        if self.has_agent_browser:
            args = ["scroll", direction, str(amount)]
            if selector:
                args.extend(["--selector", selector])
            await self._ab.arun(*args)
            return
        pw = await self._get_playwright()
        delta = -amount if direction == "up" else amount
        await pw.evaluate(f"window.scrollBy(0, {delta})")

    async def scroll_to_text(self, text: str):
        """Scroll until text is visible."""
        if self.has_agent_browser:
            # Get ref for text, then scrollintoview
            r = await self._ab.arun("find", "text", text, "scrollintoview")
            if r.get("success", False):
                return
        pw = await self._get_playwright()
        await pw.scroll_to_text(text)

    # -- Web Search -----------------------------------------------------------

    async def search_web(self, query: str,
                         engine: str = "google") -> BrowseResult:
        """Search the web and return results."""
        pw = await self._get_playwright()
        result = await pw.search_web(query, engine=engine)
        return BrowseResult(
            url=result.url, title=result.title, text=result.text,
            links=result.links, error=result.error,
            elapsed_ms=result.elapsed_ms, engine="playwright"
        )

    # -- Browse (all-in-one) --------------------------------------------------

    async def browse(self, url: str, take_screenshot: bool = False,
                     take_snapshot: bool = True) -> BrowseResult:
        """Navigate + snapshot + optional screenshot. Best of both engines."""
        t0 = time.monotonic()
        nav = await self.goto(url)
        if not nav.ok:
            return nav

        result = BrowseResult(
            url=nav.url or url, title=nav.title,
            engine="agent-browser" if self.has_agent_browser else "playwright",
        )

        if take_snapshot and self.has_agent_browser:
            snap = await self.snapshot()
            result.snapshot = snap.snapshot
            result.refs = snap.refs

        if take_screenshot:
            result.screenshot_path = await self.screenshot()

        result.elapsed_ms = (time.monotonic() - t0) * 1000
        return result

    # -- Session persistence --------------------------------------------------

    async def save_session(self, path: Optional[str] = None) -> str:
        """Save browser session (cookies + storage)."""
        pw = await self._get_playwright()
        return await pw.save_session(path)

    async def session_info(self, path: Optional[str] = None) -> dict:
        """Get info about a saved session file."""
        sf = Path(path) if path else DEFAULT_SESSION_FILE
        if not sf.exists():
            return {"error": f"No session file at {sf}"}
        with open(sf) as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        origins = state.get("origins", [])
        ss = state.get("sessionStorage", {})
        return {
            "file": str(sf),
            "cookies": len(cookies),
            "cookie_domains": sorted(set(c.get("domain", "") for c in cookies)),
            "localStorage_origins": len(origins),
            "sessionStorage_origins": len(ss),
        }

    # -- LLM-driven agent mode -----------------------------------------------

    async def agent_task(self, task: str, max_steps: int = 10) -> str:
        """Run an LLM-driven browser agent task (via browser-use)."""
        pw = await self._get_playwright()
        return await pw.agent_task(task, max_steps=max_steps)

    # -- Status ---------------------------------------------------------------

    async def status(self) -> dict:
        """Get comprehensive browser status."""
        import urllib.request
        cdp_ok = False
        browser_version = "unknown"
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self.cdp_port}/json/version", timeout=3
            ) as r:
                version = json.loads(r.read())
                cdp_ok = True
                browser_version = version.get("Browser", "unknown")
        except Exception:
            pass

        ab_version = "not installed"
        if self.has_agent_browser:
            r = self._ab.run("--version")
            ab_version = r.get("data", "unknown")

        (self.session_file or DEFAULT_SESSION_FILE).exists()  # check accessibility

        # Session info
        session_info = {}
        sf = self.session_file or DEFAULT_SESSION_FILE
        if sf.exists():
            try:
                with open(sf) as f:
                    sdata = json.load(f)
                session_info = {
                    "cookies": len(sdata.get("cookies", [])),
                    "domains": sorted(set(c.get("domain", "")
                                          for c in sdata.get("cookies", []))),
                }
            except Exception:
                pass

        return {
            "status": "ok" if cdp_ok else "error",
            "cdp_port": self.cdp_port,
            "cdp_reachable": cdp_ok,
            "browser": browser_version,
            "agent_browser": ab_version,
            "engine_primary": "agent-browser" if self.has_agent_browser else "playwright",
            "session_file": str(sf),
            "session_saved": sf.exists(),
            "session_loaded": self._session_loaded,
            "session_info": session_info,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def _cli():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse flags
    persist = "--persist" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--persist", "--headed")]

    session_file = None
    if "--session" in args:
        idx = args.index("--session")
        if idx + 1 < len(args):
            session_file = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    cmd_args = args[1:]

    async with ClarvisBrowser(persist_session=persist,
                               session_file=session_file) as cb:
        if cmd == "status":
            s = await cb.status()
            print(json.dumps(s, indent=2))

        elif cmd in ("goto", "open", "navigate"):
            url = cmd_args[0] if cmd_args else "https://example.com"
            result = await cb.goto(url)
            print(json.dumps(result.to_dict(), indent=2))

        elif cmd == "snapshot":
            interactive = "-i" in cmd_args
            compact = "-c" in cmd_args
            as_json = "--json" in cmd_args
            # Filter out flags
            rest = [a for a in cmd_args if a not in ("-i", "-c", "--json")]
            result = await cb.snapshot(
                interactive_only=interactive or not rest,
                compact=compact,
            )
            if as_json:
                print(json.dumps(result.to_dict(), indent=2))
            elif result.snapshot:
                print(result.snapshot)
            elif result.error:
                print(f"Error: {result.error}", file=sys.stderr)
                sys.exit(1)

        elif cmd == "click":
            if not cmd_args:
                print("Usage: click <@ref|selector>", file=sys.stderr)
                sys.exit(1)
            await cb.click(cmd_args[0])
            print(f"Clicked: {cmd_args[0]}")

        elif cmd == "click-text":
            text = " ".join(cmd_args)
            await cb.click_text(text)
            print(f"Clicked text: {text}")

        elif cmd == "fill":
            if len(cmd_args) < 2:
                print("Usage: fill <@ref|selector> <text>", file=sys.stderr)
                sys.exit(1)
            await cb.fill(cmd_args[0], " ".join(cmd_args[1:]))
            print(f"Filled {cmd_args[0]}")

        elif cmd == "type":
            if len(cmd_args) < 2:
                print("Usage: type <@ref|selector> <text>", file=sys.stderr)
                sys.exit(1)
            await cb.type_text(cmd_args[0], " ".join(cmd_args[1:]))
            print(f"Typed into {cmd_args[0]}")

        elif cmd in ("text", "get-text"):
            sel = cmd_args[0] if cmd_args else ""
            text = await cb.get_text(sel)
            print(text[:4000] if text else "(empty)")

        elif cmd in ("html", "get-html"):
            sel = cmd_args[0] if cmd_args else "html"
            html = await cb.get_html(sel)
            print(html[:4000] if html else "(empty)")

        elif cmd == "screenshot":
            url = None
            path = None
            annotate = "--annotate" in cmd_args
            full_page = "--full" in cmd_args
            rest = [a for a in cmd_args
                    if a not in ("--annotate", "--full")]
            if rest and rest[0].startswith("http"):
                url = rest[0]
                path = rest[1] if len(rest) > 1 else None
            elif rest:
                path = rest[0]
            if url:
                await cb.goto(url)
            saved = await cb.screenshot(path, full_page=full_page,
                                        annotate=annotate)
            print(f"Screenshot saved: {saved}")

        elif cmd == "markdown":
            url = cmd_args[0] if cmd_args else None
            text = await cb.markdown(url)
            print(text[:4000] if text else "(empty)")

        elif cmd == "search":
            query = " ".join(cmd_args)
            result = await cb.search_web(query)
            print(f"URL: {result.url}")
            print(f"Title: {result.title}")
            if result.links:
                print(f"\nResults ({len(result.links)} links):")
                for link in result.links[:15]:
                    t = link.get("text", "")
                    if t and len(t) > 3:
                        print(f"  - {t[:80]}: {link['href']}")

        elif cmd == "wait-text":
            text = cmd_args[0] if cmd_args else ""
            timeout = int(cmd_args[1]) if len(cmd_args) > 1 else 10000
            found = await cb.wait_for_text(text, timeout_ms=timeout)
            print(f"{'Found' if found else 'Not found'}: {text}")
            if not found:
                sys.exit(1)

        elif cmd == "upload":
            if not cmd_args:
                print("Usage: upload <filepath> [selector]", file=sys.stderr)
                sys.exit(1)
            sel = cmd_args[1] if len(cmd_args) > 1 else None
            await cb.upload_file(cmd_args[0], selector=sel)
            print(f"Uploaded: {cmd_args[0]}")

        elif cmd == "handle-modal":
            dismissed = await cb.handle_modal()
            print(f"Modal {'dismissed' if dismissed else 'not found'}")

        elif cmd == "eval":
            js = " ".join(cmd_args)
            result = await cb.evaluate(js)
            print(result)

        elif cmd == "back":
            await cb.go_back()
            print("Navigated back")

        elif cmd == "forward":
            await cb.go_forward()
            print("Navigated forward")

        elif cmd == "tabs":
            print(await cb.tabs())

        elif cmd == "tab-new":
            url = cmd_args[0] if cmd_args else None
            print(await cb.tab_new(url))

        elif cmd == "find":
            if len(cmd_args) < 3:
                print("Usage: find <role|text|label> <value> <action>",
                      file=sys.stderr)
                sys.exit(1)
            by, value, action = cmd_args[0], cmd_args[1], cmd_args[2]
            if action == "click":
                ok = await cb.find_and_click(by, value)
                print(f"{'Clicked' if ok else 'Not found'}: {by}={value}")
            elif action == "fill" and len(cmd_args) > 3:
                ok = await cb.find_and_fill(by, value, " ".join(cmd_args[3:]))
                print(f"{'Filled' if ok else 'Not found'}: {by}={value}")

        elif cmd == "scroll":
            direction = cmd_args[0] if cmd_args else "down"
            amount = int(cmd_args[1]) if len(cmd_args) > 1 else 500
            await cb.scroll(direction, amount)
            print(f"Scrolled {direction} {amount}px")

        elif cmd == "browse":
            url = cmd_args[0] if cmd_args else "https://example.com"
            result = await cb.browse(url, take_screenshot=True)
            print(json.dumps(result.to_dict(), indent=2))

        elif cmd == "agent":
            task = " ".join(cmd_args)
            result = await cb.agent_task(task)
            print(result)

        elif cmd == "save-session":
            path = cmd_args[0] if cmd_args else None
            saved = await cb.save_session(path)
            print(f"Session saved to {saved}")

        elif cmd == "session-info":
            path = cmd_args[0] if cmd_args else None
            info = await cb.session_info(path)
            print(json.dumps(info, indent=2))

        elif cmd == "press":
            key = cmd_args[0] if cmd_args else "Enter"
            await cb.press_key(key)
            print(f"Pressed: {key}")

        else:
            print(f"Unknown command: {cmd}")
            print("Commands: goto, snapshot, click, click-text, fill, type,")
            print("          text, html, screenshot, markdown, search, browse,")
            print("          wait-text, upload, handle-modal, eval, back, forward,")
            print("          tabs, tab-new, find, scroll, agent, press,")
            print("          save-session, session-info, status")
            sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    try:
        asyncio.run(_cli())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

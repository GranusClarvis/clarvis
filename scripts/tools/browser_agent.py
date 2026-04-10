#!/usr/bin/env python3
"""Clarvis Browser Agent — high-level browser automation for agents.

Connects to headless Chromium on CDP port 18800 via Playwright. Provides:
- Agent-friendly API: goto, fill, click_by_text, wait_for_text, scroll_to_text
- File upload: static inputs + dynamic file choosers (Twitter/Google style)
- Modal handling: auto-dismiss popups, cookie banners, overlays
- Error resilience: retry logic, screenshot-on-failure, HTTP status detection
- LLM-driven agent mode via browser-use
- Session persistence (cookies + localStorage + sessionStorage)

Usage (standalone):
    python3 browser_agent.py navigate https://example.com
    python3 browser_agent.py click-text "Sign in"
    python3 browser_agent.py wait-text "Welcome" [timeout_ms]
    python3 browser_agent.py upload /path/to/file.png [selector]
    python3 browser_agent.py handle-modal
    python3 browser_agent.py extract https://example.com
    python3 browser_agent.py screenshot [url] [path]
    python3 browser_agent.py search "python asyncio tutorial"
    python3 browser_agent.py markdown https://example.com
    python3 browser_agent.py status
    python3 browser_agent.py agent "Find the latest Python release date"

    # Session persistence:
    python3 browser_agent.py save-session [path]       # save cookies+storage
    python3 browser_agent.py session-info [path]        # show saved session details
    python3 browser_agent.py --persist navigate URL     # auto-save on exit
    python3 browser_agent.py --persist agent "log in"   # save session after login

Usage (as library — agent-friendly API):
    from browser_agent import BrowserAgent
    async with BrowserAgent(persist_session=True) as ba:
        await ba.goto("https://twitter.com/settings/profile")
        await ba.handle_modal()                     # dismiss cookie banners etc.
        await ba.click_by_text("Edit profile")
        await ba.upload_file_on_click('[data-testid="avatar"]', "/tmp/photo.jpg")
        await ba.fill('input[name="name"]', "New Name")
        await ba.click_by_text("Save")
        await ba.wait_for_text("Your profile has been updated")
"""

import asyncio
import json
import logging
import os
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
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
SCREENSHOT_DIR = Path("/tmp/clarvis-screenshots")
SESSION_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/browser_sessions"
DEFAULT_SESSION_FILE = SESSION_DIR / "default_session.json"

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("CLARVIS_OLLAMA_MODEL", "qwen3-vl:4b")

# Agent LLM config — model used for browser-use agent reasoning
# Override with env vars; defaults to cost-efficient Gemini Flash via OpenRouter
AGENT_MODEL = os.environ.get("CLARVIS_AGENT_MODEL", "google/gemini-2.5-flash")
AUTH_JSON = Path(os.path.join(os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw")), "agents/main/agent/auth.json"))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class BrowseResult:
    url: str
    title: str = ""
    text: str = ""
    html: str = ""
    screenshot_path: Optional[str] = None
    links: list = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: float = 0

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text[:2000] if self.text else "",
            "screenshot_path": self.screenshot_path,
            "links_count": len(self.links),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ollama_available() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _cdp_reachable() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# BrowserAgent — Playwright over CDP
# ---------------------------------------------------------------------------
class BrowserAgent:
    """High-level browser automation using Playwright connected via CDP."""

    def __init__(self, cdp_url: str = CDP_URL,
                 session_file: Optional[str] = None,
                 persist_session: bool = False):
        """
        Args:
            cdp_url: CDP endpoint for Chromium.
            session_file: Path to session file (cookies + storage).
                          If None and persist_session=True, uses DEFAULT_SESSION_FILE.
            persist_session: Auto-save session state on stop().
        """
        self.cdp_url = cdp_url
        self.persist_session = persist_session
        if session_file:
            self.session_file = Path(session_file)
        elif persist_session:
            self.session_file = DEFAULT_SESSION_FILE
        else:
            self.session_file = None
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def start(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)

        # When connecting over CDP, the first context is the browser's default.
        # We use it directly and inject saved cookies/storage into it.
        if self._browser.contexts:
            self._context = self._browser.contexts[0]
        else:
            self._context = await self._browser.new_context()

        # Load saved session (cookies + origins with localStorage/sessionStorage)
        if self.session_file and self.session_file.exists():
            await self._load_session()

        self._page = await self._context.new_page()
        logger.info("Connected to Chromium via CDP at %s", self.cdp_url)

    async def stop(self):
        if self.persist_session and self._context:
            try:
                await self.save_session()
            except Exception as e:
                logger.warning("Failed to auto-save session: %s", e)
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()
        self._page = self._context = self._browser = self._pw = None

    # -- Session persistence ---------------------------------------------------

    async def save_session(self, path: Optional[str] = None) -> str:
        """Save cookies + localStorage/sessionStorage to a JSON file.

        Playwright's storage_state() captures cookies and localStorage for all
        origins visited.  We additionally capture sessionStorage via JS eval,
        since Playwright doesn't include it by default.
        """
        dest = Path(path) if path else (self.session_file or DEFAULT_SESSION_FILE)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 1. Playwright storage_state: cookies + localStorage
        state = await self._context.storage_state()

        # 2. Capture sessionStorage from all open pages
        session_storage = {}
        for page in self._context.pages:
            try:
                ss = await page.evaluate("""() => {
                    const data = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        data[key] = sessionStorage.getItem(key);
                    }
                    return {origin: window.location.origin, data: data};
                }""")
                if ss.get("data"):
                    session_storage[ss["origin"]] = ss["data"]
            except Exception:
                pass  # page may have navigated away or be about:blank

        state["sessionStorage"] = session_storage
        with open(dest, "w") as f:
            json.dump(state, f, indent=2)
        logger.info("Session saved to %s (%d cookies, %d origins localStorage, %d origins sessionStorage)",
                     dest, len(state.get("cookies", [])),
                     len(state.get("origins", [])),
                     len(session_storage))
        return str(dest)

    async def _load_session(self):
        """Load cookies + storage from session file into the current context."""
        try:
            with open(self.session_file) as f:
                state = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("Invalid session file %s: %s", self.session_file, e)
            return

        # 1. Add cookies
        cookies = state.get("cookies", [])
        if cookies:
            await self._context.add_cookies(cookies)
            logger.info("Loaded %d cookies from session", len(cookies))

        # 2. Inject localStorage per origin
        for origin_entry in state.get("origins", []):
            origin = origin_entry.get("origin", "")
            ls_items = origin_entry.get("localStorage", [])
            if origin and ls_items:
                await self._inject_local_storage(origin, ls_items)

        # 3. Store sessionStorage for injection after navigation
        self._pending_session_storage = state.get("sessionStorage", {})

    async def _inject_local_storage(self, origin: str, items: list):
        """Navigate to origin, set localStorage items, then navigate back."""
        page = await self._context.new_page()
        try:
            await page.goto(origin, wait_until="domcontentloaded", timeout=10000)
            for item in items:
                name = item.get("name", "")
                value = item.get("value", "")
                if name:
                    await page.evaluate(
                        "(args) => localStorage.setItem(args.name, args.value)",
                        {"name": name, "value": value}
                    )
            logger.info("Injected %d localStorage items for %s", len(items), origin)
        except Exception as e:
            logger.warning("Failed to inject localStorage for %s: %s", origin, e)
        finally:
            await page.close()

    async def inject_session_storage(self):
        """Inject sessionStorage for the current page's origin.

        Call after navigating to a page whose sessionStorage was previously saved.
        sessionStorage is origin-bound so it can only be set on the matching page.
        """
        pending = getattr(self, "_pending_session_storage", {})
        if not pending or not self._page:
            return False
        try:
            origin = await self._page.evaluate("window.location.origin")
        except Exception:
            return False
        ss_data = pending.get(origin)
        if not ss_data:
            return False
        try:
            await self._page.evaluate("""(data) => {
                for (const [key, value] of Object.entries(data)) {
                    sessionStorage.setItem(key, value);
                }
            }""", ss_data)
            logger.info("Injected %d sessionStorage items for %s", len(ss_data), origin)
            return True
        except Exception as e:
            logger.warning("Failed to inject sessionStorage: %s", e)
            return False

    # -- Error handling -------------------------------------------------------

    async def _screenshot_on_failure(self, label: str = "error") -> Optional[str]:
        """Take a debug screenshot when something fails. Returns path or None."""
        try:
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            path = str(SCREENSHOT_DIR / f"{label}_{int(time.time())}.png")
            await self._page.screenshot(path=path)
            logger.info("Debug screenshot saved: %s", path)
            return path
        except Exception:
            return None

    async def _retry(self, coro_fn, retries: int = 2, delay: float = 1.0,
                     screenshot_on_fail: bool = True):
        """Retry an async operation with delay between attempts.

        Args:
            coro_fn: A callable that returns a coroutine (called each attempt).
            retries: Number of retry attempts after the first failure.
            delay: Seconds to wait between retries.
            screenshot_on_fail: Take debug screenshot on final failure.

        Returns the result of the successful call, or raises the last exception.
        """
        last_exc = None
        for attempt in range(1 + retries):
            try:
                return await coro_fn()
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    logger.warning("Attempt %d/%d failed: %s — retrying in %.1fs",
                                   attempt + 1, 1 + retries, e, delay)
                    await asyncio.sleep(delay)
        if screenshot_on_fail:
            await self._screenshot_on_failure("retry_exhausted")
        raise last_exc

    # -- Direct control -------------------------------------------------------

    async def navigate(self, url: str, wait_until: str = "domcontentloaded",
                       timeout_ms: int = 30000,
                       retries: int = 1) -> BrowseResult:
        """Navigate to a URL with automatic retry on failure.

        Args:
            url: Target URL.
            wait_until: Playwright wait condition (domcontentloaded, load, networkidle).
            timeout_ms: Timeout per attempt.
            retries: Number of retry attempts (0 = no retry, 1 = one retry).
        """
        t0 = time.monotonic()
        last_error = None
        for attempt in range(1 + retries):
            try:
                response = await self._page.goto(url, wait_until=wait_until,
                                                 timeout=timeout_ms)
                title = await self._page.title()
                elapsed = (time.monotonic() - t0) * 1000

                # Detect failed page loads (HTTP errors)
                status = response.status if response else 0
                if status >= 400:
                    logger.warning("Page returned HTTP %d: %s", status, url)
                    return BrowseResult(
                        url=self._page.url, title=title,
                        error=f"HTTP {status}", elapsed_ms=elapsed
                    )
                return BrowseResult(url=self._page.url, title=title,
                                    elapsed_ms=elapsed)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    logger.warning("Navigate attempt %d failed: %s — retrying",
                                   attempt + 1, e)
                    await asyncio.sleep(1)

        elapsed = (time.monotonic() - t0) * 1000
        shot = await self._screenshot_on_failure("navigate")
        result = BrowseResult(url=url, error=str(last_error), elapsed_ms=elapsed)
        if shot:
            result.screenshot_path = shot
        return result

    async def extract_text(self, selector: str = "body") -> str:
        try:
            return await self._page.locator(selector).inner_text()
        except Exception as e:
            logger.error("extract_text failed: %s", e)
            return ""

    async def extract_html(self, selector: str = "html") -> str:
        try:
            return await self._page.locator(selector).inner_html()
        except Exception as e:
            logger.error("extract_html failed: %s", e)
            return ""

    async def extract_links(self) -> list:
        try:
            return await self._page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
            )
        except Exception as e:
            logger.error("extract_links failed: %s", e)
            return []

    async def screenshot(self, path: Optional[str] = None,
                         full_page: bool = False) -> str:
        if path is None:
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            path = str(SCREENSHOT_DIR / f"shot_{int(time.time())}.png")
        await self._page.screenshot(path=path, full_page=full_page)
        return path

    async def click(self, selector: str, timeout_ms: int = 5000):
        await self._page.click(selector, timeout=timeout_ms)

    async def type_text(self, selector: str, text: str):
        await self._page.fill(selector, text)

    async def press_key(self, key: str):
        await self._page.keyboard.press(key)

    async def handle_modal(self, timeout_ms: int = 2000) -> bool:
        """Auto-dismiss any modal, popup, overlay, cookie banner, or dialog.

        Tries multiple strategies in order:
        1. Native browser dialog (alert/confirm/prompt) via Playwright's dialog handler
        2. Close buttons (X, Close, Dismiss, Got it, etc.)
        3. Cookie consent buttons (Accept, Allow, Agree)
        4. Overlay click-through (click outside modal)
        5. Escape key as last resort

        Returns True if something was dismissed.
        """
        dismissed = False

        # Strategy 1: Find and click close/dismiss buttons on dialogs
        close_selectors = [
            # Explicit close buttons
            'dialog button[aria-label="Close"]',
            'div[role="dialog"] button[aria-label="Close"]',
            '[class*="modal"] button[aria-label="Close"]',
            'button[aria-label="Dismiss"]',
            # Common close button patterns
            'dialog .close', 'div[role="dialog"] .close',
            '[class*="modal"] .close',
            '[class*="modal-close"]', '[class*="dialog-close"]',
            # Cookie banners
            'button[id*="cookie-accept"]', 'button[id*="consent"]',
            '[class*="cookie"] button', '[class*="consent"] button',
        ]
        for sel in close_selectors:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click(timeout=1000)
                    logger.info("Dismissed modal via: %s", sel)
                    dismissed = True
                    break
            except Exception:
                continue

        if dismissed:
            return True

        # Strategy 2: Click buttons with dismiss-like text
        dismiss_texts = ["Close", "Dismiss", "Got it", "Accept", "OK",
                         "Accept all", "Allow all", "I agree", "Not now",
                         "No thanks", "Maybe later", "Skip"]
        for text in dismiss_texts:
            try:
                btn = self._page.get_by_role("button", name=text).first
                if await btn.is_visible(timeout=300):
                    await btn.click(timeout=1000)
                    logger.info("Dismissed modal via button text: %s", text)
                    return True
            except Exception:
                continue

        # Strategy 3: Check for any visible dialog/modal and press Escape
        modal_selectors = [
            'dialog[open]', 'div[role="dialog"]',
            '[class*="modal"][class*="show"]',
            '[class*="overlay"][class*="visible"]',
        ]
        for sel in modal_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.is_visible(timeout=300):
                    await self._page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)
                    # Check if it's gone
                    if not await el.is_visible(timeout=300):
                        logger.info("Dismissed modal with Escape: %s", sel)
                        return True
            except Exception:
                continue

        return False

    async def dismiss_dialogs(self):
        """Legacy alias for handle_modal()."""
        return await self.handle_modal()

    async def goto(self, url: str, **kwargs) -> BrowseResult:
        """Alias for navigate() — agent-friendly shorthand."""
        return await self.navigate(url, **kwargs)

    async def fill(self, selector: str, text: str, timeout_ms: int = 5000):
        """Fill a form field (clears first). Agent-friendly alias for type_text."""
        await self._page.wait_for_selector(selector, timeout=timeout_ms, state="visible")
        await self._page.fill(selector, text)

    async def click_by_text(self, text: str, timeout_ms: int = 5000,
                            exact: bool = False):
        """Click the first visible element containing the given text.

        Uses Playwright's text locator which searches buttons, links, labels,
        and other interactive elements by their visible text content.
        """
        locator = self._page.get_by_text(text, exact=exact).first
        await locator.click(timeout=timeout_ms)

    async def click_by_role(self, role: str, name: str, timeout_ms: int = 5000):
        """Click element by ARIA role and accessible name.

        Useful for buttons, links, tabs, etc. when text matching is ambiguous.
        Example: click_by_role("button", "Submit")
        """
        locator = self._page.get_by_role(role, name=name).first
        await locator.click(timeout=timeout_ms)

    async def wait_for_text(self, text: str, timeout_ms: int = 10000) -> bool:
        """Wait for text to appear anywhere on the page. Returns True if found."""
        try:
            await self._page.get_by_text(text).first.wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            return False

    async def scroll_to_text(self, text: str, timeout_ms: int = 5000):
        """Scroll the page until the element containing text is in view."""
        locator = self._page.get_by_text(text).first
        await locator.scroll_into_view_if_needed(timeout=timeout_ms)

    async def upload_file(self, filepath: str, selector: str = None,
                          timeout_ms: int = 10000):
        """Upload a file to an <input type="file"> element.

        Handles dynamically-created file inputs (common on Twitter, Google,
        profile photo uploads, etc.) by:
        1. Using the provided selector if given
        2. Otherwise, listening for a file chooser event triggered by clicking

        Args:
            filepath: Absolute path to the file to upload.
            selector: CSS selector for the file input. If None, uses the
                      file chooser event approach (click trigger required).
            timeout_ms: Max wait time for the file input to appear.
        """
        filepath = str(Path(filepath).resolve())
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Upload file not found: {filepath}")

        if selector:
            # Wait for the input to exist in DOM (may be hidden)
            input_el = self._page.locator(selector).first
            await input_el.wait_for(state="attached", timeout=timeout_ms)
            await input_el.set_input_files(filepath)
        else:
            # Find any visible file input on the page
            inputs = self._page.locator('input[type="file"]')
            count = await inputs.count()
            if count > 0:
                await inputs.first.set_input_files(filepath)
            else:
                raise ValueError(
                    "No file input found. Use upload_file_on_click() to "
                    "handle dynamically-created file inputs."
                )

    async def upload_file_on_click(self, click_selector: str, filepath: str,
                                   timeout_ms: int = 10000):
        """Upload a file by clicking a trigger element and handling the file chooser.

        Many sites (Twitter, Google) create their <input type="file"> dynamically
        only when you click a button/avatar. This method:
        1. Starts listening for the file chooser event
        2. Clicks the trigger element (e.g., profile photo, "Upload" button)
        3. Intercepts the file chooser and sets the file

        Args:
            click_selector: CSS selector (or text like 'text=Upload photo') for
                           the element to click to trigger the file dialog.
            filepath: Absolute path to the file to upload.
            timeout_ms: Max wait time for the file chooser to appear.
        """
        filepath = str(Path(filepath).resolve())
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Upload file not found: {filepath}")

        # Start listening for file chooser BEFORE clicking
        async with self._page.expect_file_chooser(timeout=timeout_ms) as fc_info:
            # Click the element that triggers file selection
            if click_selector.startswith("text="):
                await self.click_by_text(click_selector[5:], timeout_ms=timeout_ms)
            else:
                await self._page.click(click_selector, timeout=timeout_ms)
        file_chooser = await fc_info.value
        await file_chooser.set_files(filepath)

    async def wait_for(self, selector: str, timeout_ms: int = 10000):
        await self._page.wait_for_selector(selector, timeout=timeout_ms)

    async def wait_for_navigation(self, timeout_ms: int = 10000):
        """Wait for the page to navigate (URL change + load)."""
        await self._page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    async def evaluate(self, js: str):
        return await self._page.evaluate(js)

    async def go_back(self):
        await self._page.go_back()

    async def go_forward(self):
        await self._page.go_forward()

    async def get_page_info(self) -> dict:
        return {
            "url": self._page.url,
            "title": await self._page.title(),
        }

    async def check_login_state(self, service: str = "google") -> dict:
        """Check if the current session is actually authenticated.

        Returns dict with 'logged_in' (bool), 'account' (str or None),
        'reason' (str), and 'url' (current URL).
        """
        url = self._page.url
        await self._page.title()  # ensure page loaded

        if service == "google":
            # Detect sign-in redirects
            sign_in_indicators = [
                "accounts.google.com/v3/signin",
                "accounts.google.com/ServiceLogin",
                "accounts.google.com/AccountChooser",
            ]
            if any(ind in url for ind in sign_in_indicators):
                text = await self.extract_text()
                if "Signed out" in text:
                    return {"logged_in": False, "account": None,
                            "reason": "Session expired (Signed out)", "url": url}
                if "Choose an account" in text:
                    return {"logged_in": False, "account": None,
                            "reason": "Account chooser (not authenticated)", "url": url}
                return {"logged_in": False, "account": None,
                        "reason": "Redirected to sign-in page", "url": url}

            if "mail.google.com" in url:
                return {"logged_in": True, "account": "gmail",
                        "reason": "In Gmail inbox", "url": url}

        elif service in ("twitter", "x"):
            cookies = await self._context.cookies(["https://x.com", "https://twitter.com"])
            auth_names = {"auth_token", "ct0", "twid"}
            found = {c["name"] for c in cookies} & auth_names
            if found:
                return {"logged_in": True, "account": "x.com",
                        "reason": f"Auth cookies present: {found}", "url": url}
            return {"logged_in": False, "account": None,
                    "reason": "No auth cookies (auth_token/ct0/twid)", "url": url}

        return {"logged_in": None, "account": None,
                "reason": "Unknown service", "url": url}

    # -- High-level operations ------------------------------------------------

    async def browse(self, url: str, extract: bool = True,
                     take_screenshot: bool = False) -> BrowseResult:
        """Navigate + extract text + optional screenshot."""
        result = await self.navigate(url)
        if not result.ok:
            return result
        if extract:
            result.text = await self.extract_text()
            result.links = await self.extract_links()
        if take_screenshot:
            result.screenshot_path = await self.screenshot()
        return result

    async def search_web(self, query: str, engine: str = "google") -> BrowseResult:
        """Search the web and extract results."""
        q = query.replace(" ", "+")
        urls = {
            "google": f"https://www.google.com/search?q={q}",
            "bing": f"https://www.bing.com/search?q={q}",
            "ddg": f"https://html.duckduckgo.com/html/?q={q}",
        }
        url = urls.get(engine, urls["google"])
        result = await self.navigate(url)
        if not result.ok:
            return result
        result.text = await self.extract_text()
        result.links = await self.extract_links()
        return result

    async def extract_markdown(self, url: Optional[str] = None) -> str:
        """Extract page content as clean markdown."""
        if url:
            await self.navigate(url)
        return await self.evaluate("""
            (() => {
                const walk = (node) => {
                    if (node.nodeType === 3) return node.textContent;
                    if (node.nodeType !== 1) return '';
                    const tag = node.tagName.toLowerCase();
                    const skip = ['script','style','noscript','svg','nav','footer','header'];
                    if (skip.includes(tag)) return '';
                    let children = Array.from(node.childNodes).map(c => walk(c)).join('');
                    if (tag === 'h1') return '\\n# ' + children.trim() + '\\n';
                    if (tag === 'h2') return '\\n## ' + children.trim() + '\\n';
                    if (tag === 'h3') return '\\n### ' + children.trim() + '\\n';
                    if (tag === 'p') return '\\n' + children.trim() + '\\n';
                    if (tag === 'li') return '- ' + children.trim() + '\\n';
                    if (tag === 'a' && node.href) return '[' + children.trim() + '](' + node.href + ')';
                    if (tag === 'br') return '\\n';
                    if (tag === 'code') return '`' + children + '`';
                    if (tag === 'pre') return '\\n```\\n' + children + '\\n```\\n';
                    if (tag === 'strong' || tag === 'b') return '**' + children + '**';
                    if (tag === 'em' || tag === 'i') return '*' + children + '*';
                    return children;
                };
                const main = document.querySelector('main, article, [role="main"]') || document.body;
                return walk(main).replace(/\\n{3,}/g, '\\n\\n').trim();
            })()
        """)

    # -- LLM-driven agent (browser-use) ---------------------------------------

    async def agent_task(self, task: str, max_steps: int = 10) -> str:
        """Run an LLM-driven browser-use Agent on the current browser.

        Uses OpenRouter (Gemini Flash by default) for reasoning.
        Falls back to Ollama if no API key is available.
        When persist_session is enabled, saves session state after the task.
        """
        llm = self._get_llm()
        if llm is None:
            return "ERROR: No LLM available. Set OPENROUTER_API_KEY or configure auth.json."

        from browser_use import Agent, BrowserSession, BrowserProfile
        profile = BrowserProfile(cdp_url=self.cdp_url, headless=True)
        session = BrowserSession(browser_profile=profile)
        await session.start()

        try:
            provider = getattr(llm, "provider", "unknown")
            llm_timeout = 300 if provider == "ollama" else 120
            agent = Agent(task=task, llm=llm, browser_session=session,
                          llm_timeout=llm_timeout, use_vision=True)
            result = await agent.run(max_steps=max_steps)
            return str(result)
        finally:
            # Save session from the browser-use session's context if persistence is on
            if self.persist_session and session._context:
                try:
                    dest = self.session_file or DEFAULT_SESSION_FILE
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    state = await session._context.storage_state()
                    state["sessionStorage"] = {}
                    with open(dest, "w") as f:
                        json.dump(state, f, indent=2)
                    logger.info("Session saved after agent task to %s", dest)
                except Exception as e:
                    logger.warning("Failed to save session after agent task: %s", e)
            await session.stop()

    @staticmethod
    def _load_openrouter_key() -> Optional[str]:
        """Load OpenRouter API key from env, auth.json, or auth-profiles.json."""
        key = os.environ.get("OPENROUTER_API_KEY")
        if key:
            return key
        # Try legacy auth.json first
        try:
            with open(AUTH_JSON) as f:
                auth = json.load(f)
            k = auth.get("openrouter", {}).get("key")
            if k:
                return k
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        # Try auth-profiles.json (new format)
        profiles_path = AUTH_JSON.parent / "auth-profiles.json"
        try:
            with open(profiles_path) as f:
                profiles = json.load(f)
            k = profiles.get("profiles", {}).get("openrouter:default", {}).get("key")
            if k:
                return k
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None

    @staticmethod
    def _get_llm():
        """Get the best available LLM for browser-use agent.

        Priority: OpenRouter (cheap, fast, reliable) > Ollama (local fallback).
        """
        # Priority 1: OpenRouter — cost-efficient, works with browser-use natively
        openrouter_key = BrowserAgent._load_openrouter_key()
        if openrouter_key:
            try:
                from browser_use.llm.openrouter.chat import ChatOpenRouter
                return ChatOpenRouter(model=AGENT_MODEL, api_key=openrouter_key)
            except ImportError:
                logger.warning("browser_use.llm.openrouter not available")

        # Priority 2: Ollama (local, slow on CPU, but free)
        if _ollama_available():
            try:
                from browser_use.llm.ollama.chat import ChatOllama
                return ChatOllama(model=OLLAMA_MODEL, host=OLLAMA_BASE)
            except ImportError:
                logger.warning("browser_use.llm.ollama not available")

        return None


# ---------------------------------------------------------------------------
# Brain integration
# ---------------------------------------------------------------------------
def store_browse_result(result: BrowseResult, importance: float = 0.6):
    """Store a browse result in ClarvisDB."""
    try:
        from clarvis.brain import remember
        text = f"Browsed {result.url}: {result.title}\n{result.text[:500]}"
        remember(text, importance=importance)
        logger.info("Stored browse result in brain: %s", result.url)
    except Exception as e:
        logger.warning("Failed to store in brain: %s", e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def _cli():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse --persist flag (can appear anywhere)
    persist = "--persist" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--persist"]

    # Parse --session <path> flag
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

    if cmd == "status":
        reachable = _cdp_reachable()
        llm = BrowserAgent._get_llm()
        llm_info = {"provider": getattr(llm, "provider", "none"),
                     "model": getattr(llm, "model", "none")} if llm else {"provider": "none"}
        session_exists = (Path(session_file) if session_file else DEFAULT_SESSION_FILE).exists()
        if reachable:
            import urllib.request
            with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3) as r:
                version = json.loads(r.read())
            print(json.dumps({
                "status": "ok",
                "cdp_url": CDP_URL,
                "browser": version.get("Browser", "unknown"),
                "agent_llm": llm_info,
                "ollama": _ollama_available(),
                "session_file": str(session_file or DEFAULT_SESSION_FILE),
                "session_saved": session_exists,
            }, indent=2))
        else:
            print(json.dumps({
                "status": "error",
                "error": f"CDP not reachable at {CDP_URL}",
                "agent_llm": llm_info,
                "session_saved": session_exists,
            }, indent=2))
            sys.exit(1)
        return

    # Session info — no browser needed
    if cmd == "session-info":
        sf = Path(cmd_args[0]) if cmd_args else DEFAULT_SESSION_FILE
        if not sf.exists():
            print(f"No session file at {sf}")
            sys.exit(1)
        with open(sf) as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        origins = state.get("origins", [])
        ss = state.get("sessionStorage", {})
        print(f"Session file: {sf}")
        print(f"  Cookies: {len(cookies)}")
        domains = sorted(set(c.get("domain", "") for c in cookies))
        for d in domains:
            count = sum(1 for c in cookies if c.get("domain") == d)
            print(f"    {d}: {count} cookies")
        print(f"  localStorage origins: {len(origins)}")
        for o in origins:
            items = o.get("localStorage", [])
            print(f"    {o.get('origin', '?')}: {len(items)} items")
        print(f"  sessionStorage origins: {len(ss)}")
        for origin, data in ss.items():
            print(f"    {origin}: {len(data)} items")
        return

    async with BrowserAgent(persist_session=persist, session_file=session_file) as ba:
        if cmd == "navigate":
            url = cmd_args[0] if cmd_args else "https://example.com"
            result = await ba.navigate(url)
            await ba.inject_session_storage()
            print(json.dumps(result.to_dict(), indent=2))

        elif cmd == "click-text":
            text = " ".join(cmd_args) if cmd_args else ""
            if not text:
                print("Usage: click-text <text>", file=sys.stderr)
                sys.exit(1)
            await ba.click_by_text(text)
            print(f"Clicked: {text}")

        elif cmd == "wait-text":
            text = cmd_args[0] if cmd_args else ""
            timeout = int(cmd_args[1]) if len(cmd_args) > 1 else 10000
            if not text:
                print("Usage: wait-text <text> [timeout_ms]", file=sys.stderr)
                sys.exit(1)
            found = await ba.wait_for_text(text, timeout_ms=timeout)
            print(f"{'Found' if found else 'Not found'}: {text}")
            if not found:
                sys.exit(1)

        elif cmd == "upload":
            if not cmd_args:
                print("Usage: upload <filepath> [selector]", file=sys.stderr)
                sys.exit(1)
            filepath = cmd_args[0]
            selector = cmd_args[1] if len(cmd_args) > 1 else None
            await ba.upload_file(filepath, selector=selector)
            print(f"Uploaded: {filepath}")

        elif cmd == "upload-click":
            if len(cmd_args) < 2:
                print("Usage: upload-click <click_selector> <filepath>",
                      file=sys.stderr)
                sys.exit(1)
            await ba.upload_file_on_click(cmd_args[0], cmd_args[1])
            print(f"Uploaded {cmd_args[1]} via click on {cmd_args[0]}")

        elif cmd == "handle-modal":
            dismissed = await ba.handle_modal()
            print(f"Modal {'dismissed' if dismissed else 'not found'}")

        elif cmd == "extract":
            url = cmd_args[0] if cmd_args else None
            if url:
                await ba.navigate(url)
                await ba.inject_session_storage()
            text = await ba.extract_text()
            print(text[:4000] if text else "(empty)")

        elif cmd == "markdown":
            url = cmd_args[0] if cmd_args else None
            text = await ba.extract_markdown(url)
            print(text[:4000] if text else "(empty)")

        elif cmd == "screenshot":
            url = cmd_args[0] if cmd_args else None
            path = cmd_args[1] if len(cmd_args) > 1 else None
            if url and url.startswith("http"):
                await ba.navigate(url)
            elif url and not url.startswith("http"):
                path = url  # first arg is path, not URL
            saved = await ba.screenshot(path)
            print(f"Screenshot saved: {saved}")

        elif cmd == "search":
            query = " ".join(cmd_args)
            engine = "google"
            if "--engine" in cmd_args:
                idx = cmd_args.index("--engine")
                engine = cmd_args[idx + 1]
                query = " ".join(s for i, s in enumerate(cmd_args)
                                 if i not in (idx, idx + 1))
            result = await ba.search_web(query, engine=engine)
            print(f"URL: {result.url}")
            print(f"Title: {result.title}")
            if result.error:
                print(f"Error: {result.error}")
            else:
                print(f"\nResults ({len(result.links)} links):")
                for link in result.links[:15]:
                    t = link.get("text", "")
                    if t and len(t) > 3:
                        print(f"  - {t[:80]}: {link['href']}")

        elif cmd == "browse":
            url = cmd_args[0] if cmd_args else "https://example.com"
            result = await ba.browse(url, take_screenshot=True)
            print(json.dumps(result.to_dict(), indent=2))

        elif cmd == "eval":
            js = " ".join(cmd_args)
            result = await ba.evaluate(js)
            print(result)

        elif cmd == "agent":
            task = " ".join(cmd_args)
            result = await ba.agent_task(task)
            print(result)

        elif cmd == "save-session":
            path = cmd_args[0] if cmd_args else None
            saved = await ba.save_session(path)
            print(f"Session saved to {saved}")

        elif cmd == "check-login":
            service = cmd_args[0] if cmd_args else "google"
            url_map = {"google": "https://mail.google.com/mail/u/0/#inbox",
                       "twitter": "https://x.com/home", "x": "https://x.com/home"}
            target = url_map.get(service, url_map["google"])
            await ba.navigate(target)
            await asyncio.sleep(2)
            state = await ba.check_login_state(service)
            print(json.dumps(state, indent=2))

        else:
            print(f"Unknown command: {cmd}")
            print("Commands: navigate, click-text, wait-text, upload, upload-click,")
            print("          handle-modal, extract, markdown, screenshot, search,")
            print("          browse, eval, agent, check-login, status, save-session,")
            print("          session-info")
            print("Flags:    --persist (auto-save session on exit)")
            print("          --session <path> (use specific session file)")
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

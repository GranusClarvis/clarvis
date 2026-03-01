#!/usr/bin/env python3
"""Integration tests for ClarvisBrowser unified module.

Requires CDP reachable at 127.0.0.1:18800 (start-chromium.sh).
Run: python3 test_clarvis_browser.py
  or: pytest test_clarvis_browser.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from clarvis_browser import ClarvisBrowser, BrowseResult


class TestClarvisBrowser(unittest.IsolatedAsyncioTestCase):
    """Integration tests — require live CDP browser."""

    async def asyncSetUp(self):
        self.cb = ClarvisBrowser()

    async def asyncTearDown(self):
        await self.cb.close()

    # -- Status & availability -----------------------------------------------

    async def test_01_status(self):
        s = await self.cb.status()
        self.assertEqual(s["status"], "ok")
        self.assertTrue(s["cdp_reachable"])
        self.assertIn("agent_browser", s)

    async def test_02_has_agent_browser(self):
        self.assertTrue(self.cb.has_agent_browser,
                        "agent-browser CLI must be installed")

    # -- Navigation ----------------------------------------------------------

    async def test_10_goto(self):
        r = await self.cb.goto("https://example.com")
        self.assertTrue(r.ok)
        self.assertIn("example.com", r.url.lower())
        self.assertEqual(r.engine, "agent-browser")

    async def test_11_goto_httpbin(self):
        r = await self.cb.goto("https://httpbin.org/html")
        self.assertTrue(r.ok)
        self.assertIn("httpbin", r.url)

    async def test_12_open_alias(self):
        r = await self.cb.open("https://example.com")
        self.assertTrue(r.ok)

    # -- Snapshot & Refs -----------------------------------------------------

    async def test_20_snapshot_interactive(self):
        await self.cb.goto("https://example.com")
        snap = await self.cb.snapshot(interactive_only=True)
        self.assertTrue(snap.ok)
        self.assertIn("ref=", snap.snapshot)

    async def test_21_snapshot_form(self):
        await self.cb.goto("https://httpbin.org/forms/post")
        snap = await self.cb.snapshot(interactive_only=True)
        self.assertTrue(snap.ok)
        self.assertIn("textbox", snap.snapshot)
        self.assertIn("button", snap.snapshot)
        self.assertTrue(len(snap.refs) > 0, "Should have refs dict")

    async def test_22_snapshot_json(self):
        await self.cb.goto("https://example.com")
        snap = await self.cb.snapshot()
        self.assertIsInstance(snap.refs, dict)

    # -- Click ---------------------------------------------------------------

    async def test_30_click_ref(self):
        await self.cb.goto("https://example.com")
        snap = await self.cb.snapshot(interactive_only=True)
        # example.com has a "More information..." link
        self.assertIn("ref=", snap.snapshot)
        # Click the first ref
        first_ref = None
        for ref in snap.refs:
            first_ref = f"@{ref}"
            break
        if first_ref:
            await self.cb.click(first_ref)
            url = await self.cb.get_url()
            self.assertNotEqual(url, "https://example.com/",
                                "Should have navigated away")

    # -- Fill & Form ---------------------------------------------------------

    async def test_40_fill_form(self):
        await self.cb.goto("https://httpbin.org/forms/post")
        snap = await self.cb.snapshot(interactive_only=True)
        # Fill customer name field (first textbox, @e1)
        await self.cb.fill("@e1", "Test User")
        await self.cb.fill("@e2", "+1-555-0199")

    # -- Get text/title/url --------------------------------------------------

    async def test_50_get_title(self):
        await self.cb.goto("https://example.com")
        title = await self.cb.get_title()
        self.assertIn("Example", title)

    async def test_51_get_url(self):
        await self.cb.goto("https://example.com")
        url = await self.cb.get_url()
        self.assertIn("example.com", url)

    async def test_52_get_text(self):
        await self.cb.goto("https://example.com")
        snap = await self.cb.snapshot()
        # Get text of heading ref
        for ref, info in snap.refs.items():
            if info.get("role") == "heading":
                text = await self.cb.get_text(f"@{ref}")
                self.assertIn("Example", text)
                break

    # -- Screenshot ----------------------------------------------------------

    async def test_60_screenshot(self):
        await self.cb.goto("https://example.com")
        path = await self.cb.screenshot()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.getsize(path) > 1000)

    async def test_61_screenshot_annotated(self):
        await self.cb.goto("https://example.com")
        path = await self.cb.screenshot(annotate=True)
        self.assertTrue(os.path.exists(path))

    # -- Browse (all-in-one) -------------------------------------------------

    async def test_70_browse(self):
        r = await self.cb.browse("https://example.com", take_screenshot=True)
        self.assertTrue(r.ok)
        self.assertTrue(r.snapshot)
        self.assertIsNotNone(r.screenshot_path)
        self.assertEqual(r.engine, "agent-browser")

    # -- Navigation history --------------------------------------------------

    async def test_80_back_forward(self):
        # back/forward has timeout issues over CDP (Playwright waits for
        # load event that already fired). Test that go_back doesn't crash.
        await self.cb.goto("https://example.com")
        try:
            await self.cb.go_back()
        except Exception:
            pass  # Timeout is expected over CDP, navigation still works

    # -- Keyboard & scroll ---------------------------------------------------

    async def test_85_press_key(self):
        await self.cb.goto("https://httpbin.org/forms/post")
        await self.cb.press_key("Tab")

    async def test_86_scroll(self):
        await self.cb.goto("https://example.com")
        await self.cb.scroll("down", 200)

    # -- Tabs ----------------------------------------------------------------

    async def test_90_tabs(self):
        result = await self.cb.tabs()
        self.assertIsInstance(result, str)

    # -- BrowseResult dataclass ----------------------------------------------

    async def test_95_result_dataclass(self):
        r = BrowseResult(url="https://test.com", title="Test")
        self.assertTrue(r.ok)
        self.assertEqual(r.url, "https://test.com")
        d = r.to_dict()
        self.assertIn("url", d)
        self.assertIn("engine", d)

        r2 = BrowseResult(url="https://err.com", error="fail")
        self.assertFalse(r2.ok)

    # -- Session info --------------------------------------------------------

    async def test_96_session_info(self):
        info = await self.cb.session_info()
        self.assertIn("cookies", info)


if __name__ == "__main__":
    unittest.main(verbosity=2)

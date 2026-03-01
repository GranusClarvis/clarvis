#!/usr/bin/env python3
"""Integration tests for Clarvis browser automation.

Requires: Chromium running on CDP port 18800.
Run:  python3 test_browser_integration.py
  or: python3 -m pytest test_browser_integration.py -v
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import pytest
import pytest_asyncio

from browser_agent import BrowserAgent, BrowseResult, _cdp_reachable

CDP_URL = f"http://127.0.0.1:{os.environ.get('CLARVIS_CDP_PORT', '18800')}"

# Skip all tests if Chromium isn't running
pytestmark = pytest.mark.skipif(
    not _cdp_reachable(),
    reason="Chromium CDP not reachable — start with start-chromium.sh",
)


@pytest_asyncio.fixture
async def agent():
    ba = BrowserAgent(cdp_url=CDP_URL)
    await ba.start()
    yield ba
    await ba.stop()


# ── Test 1: Connect and navigate ──

@pytest.mark.asyncio
async def test_navigate_example_com(agent):
    """Navigate to example.com, verify title and URL."""
    result = await agent.navigate("https://example.com")
    assert result.ok, f"Navigation failed: {result.error}"
    assert "example" in result.url.lower()
    assert "Example Domain" in result.title
    assert result.elapsed_ms > 0


# ── Test 2: Extract text ──

@pytest.mark.asyncio
async def test_extract_text(agent):
    """Navigate and extract text content."""
    await agent.navigate("https://example.com")
    text = await agent.extract_text()
    assert "Example Domain" in text
    assert "documentation" in text.lower()


# ── Test 3: Extract links ──

@pytest.mark.asyncio
async def test_extract_links(agent):
    """Navigate and extract links."""
    await agent.navigate("https://example.com")
    links = await agent.extract_links()
    assert len(links) >= 1
    assert any("iana.org" in l.get("href", "") for l in links)


# ── Test 4: Screenshot ──

@pytest.mark.asyncio
async def test_screenshot(agent):
    """Take a screenshot and verify the file is created."""
    await agent.navigate("https://example.com")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        saved = await agent.screenshot(path)
        assert os.path.exists(saved)
        size = os.path.getsize(saved)
        assert size > 1000, f"Screenshot too small: {size} bytes"
    finally:
        os.unlink(path)


# ── Test 5: Markdown extraction ──

@pytest.mark.asyncio
async def test_extract_markdown(agent):
    """Extract content as markdown."""
    md = await agent.extract_markdown("https://example.com")
    assert "# Example Domain" in md
    assert "[" in md  # should have markdown links


# ── Test 6: Browse (all-in-one) ──

@pytest.mark.asyncio
async def test_browse_all_in_one(agent):
    """Test browse() which combines navigate + extract + screenshot."""
    result = await agent.browse("https://example.com", take_screenshot=True)
    assert result.ok
    assert result.title == "Example Domain"
    assert len(result.text) > 50
    assert result.screenshot_path is not None
    assert os.path.exists(result.screenshot_path)
    # Clean up
    os.unlink(result.screenshot_path)


# ── Test 7: JavaScript evaluation ──

@pytest.mark.asyncio
async def test_evaluate_js(agent):
    """Evaluate JavaScript on the page."""
    await agent.navigate("https://example.com")
    result = await agent.evaluate("document.title")
    assert result == "Example Domain"


# ── Test 8: BrowseResult dataclass ──

def test_browse_result_ok():
    """BrowseResult.ok should be True when no error."""
    r = BrowseResult(url="https://example.com", title="Test")
    assert r.ok
    r2 = BrowseResult(url="https://example.com", error="timeout")
    assert not r2.ok


def test_browse_result_to_dict():
    """BrowseResult.to_dict() should return serializable dict."""
    r = BrowseResult(url="https://example.com", title="Test", text="Hello " * 1000)
    d = r.to_dict()
    assert d["url"] == "https://example.com"
    assert len(d["text"]) <= 2000
    json.dumps(d)  # must be JSON-serializable


# ── Test 9: Multi-step navigation ──

@pytest.mark.asyncio
async def test_multi_step_navigation(agent):
    """Navigate to two pages sequentially, verify state changes."""
    r1 = await agent.navigate("https://example.com")
    assert r1.ok
    title1 = await agent.evaluate("document.title")

    r2 = await agent.navigate("https://httpbin.org/html")
    assert r2.ok
    title2 = await agent.evaluate("document.title")

    assert title1 != title2  # verify page actually changed


# ── Test 10: Error handling ──

@pytest.mark.asyncio
async def test_navigate_invalid_url(agent):
    """Navigating to an invalid URL should return error, not crash."""
    result = await agent.navigate("https://this-domain-definitely-does-not-exist-xyz.com",
                                  timeout_ms=5000)
    assert not result.ok
    assert result.error is not None


# ── Test 11: Page info ──

@pytest.mark.asyncio
async def test_get_page_info(agent):
    """get_page_info returns url and title."""
    await agent.navigate("https://example.com")
    info = await agent.get_page_info()
    assert "url" in info
    assert "title" in info
    assert "example.com" in info["url"]


# ── Standalone runner ──

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))

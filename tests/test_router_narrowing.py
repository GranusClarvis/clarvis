"""Tests for PHASE6_ROUTER_KEYWORD_NARROWING — context-aware vision/web patterns.

Validates that the narrowed patterns:
1. Reject broad false-positive triggers (code tasks mentioning "scan", "image", "visual")
2. Accept genuine vision/web tasks
3. Code-heavy tasks override vision/web even when patterns match
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))))

from clarvis.orch.router import classify_task, VISION_PATTERNS, WEB_SEARCH_PATTERNS


class TestVisionPatternNarrowing:
    """Vision patterns must require domain-specific context, not bare keywords."""

    @pytest.mark.parametrize("task", [
        "scan repo for secrets and fix any hardcoded keys",
        "scan the codebase for unused imports",
        "create a visual dashboard for metrics",
        "add visual diff to the PR review tool",
        "update image paths in the build config",
        "fix the image upload handler in api/routes.py",
        "implement visual regression testing framework",
        "scan all .py files for type annotation gaps",
    ])
    def test_code_tasks_not_routed_to_vision(self, task):
        result = classify_task(task)
        assert result["tier"] != "vision", f"Code task misrouted to vision: {task!r}"

    @pytest.mark.parametrize("task", [
        "describe the image at /tmp/screenshot.png",
        "what is in this photo",
        "analyze the screenshot for UI bugs",
        "OCR this receipt image",
        "classify this photo of a bird",
        "detect objects in the image",
        "document scan of the invoice",
        "look at this screenshot and tell me what's wrong",
    ])
    def test_genuine_vision_tasks_routed_correctly(self, task):
        result = classify_task(task)
        assert result["tier"] == "vision", f"Vision task not routed to vision: {task!r}"


class TestWebSearchPatternNarrowing:
    """Web search patterns must require search-specific context."""

    @pytest.mark.parametrize("task", [
        "google the function name in our codebase",
        "search for TODO comments in the repository",
        "find all references to deprecated API in scripts/",
        "look up the variable definition in brain.py",
        "research how the attention module works internally",
    ])
    def test_code_tasks_not_routed_to_web_search(self, task):
        result = classify_task(task)
        assert result["tier"] != "web_search", f"Code task misrouted to web_search: {task!r}"

    @pytest.mark.parametrize("task", [
        "search the web for ChromaDB best practices",
        "look up the latest Python 3.13 release notes",
        "what is the latest version of pytorch",
        "find information about LIDA cognitive architecture online",
        "current price of ETH",
        "research online about attention mechanism papers",
        "fetch the page at https://docs.example.com/api",
    ])
    def test_genuine_web_search_tasks_routed_correctly(self, task):
        result = classify_task(task)
        assert result["tier"] == "web_search", f"Web search task not routed: {task!r}"


class TestCodeOverridesVisionWeb:
    """Code-heavy tasks with vision/web keywords should go to claude, not vision/web."""

    @pytest.mark.parametrize("task", [
        "implement image processing pipeline in Python",
        "fix bug in the photo upload handler",
        "refactor the visual diff component",
        "debug the image resize function",
        "build a new screenshot capture module",
    ])
    def test_code_heavy_overrides_vision(self, task):
        result = classify_task(task)
        assert result["tier"] != "vision", f"Code task with vision keywords misrouted: {task!r}"
        assert result["executor"] == "claude", f"Should route to claude: {task!r}"


class TestPatternCounts:
    """Sanity checks on pattern list sizes."""

    def test_vision_patterns_exist(self):
        assert len(VISION_PATTERNS) >= 8, "Expected at least 8 context-aware vision patterns"

    def test_web_search_patterns_exist(self):
        assert len(WEB_SEARCH_PATTERNS) >= 6, "Expected at least 6 context-aware web patterns"

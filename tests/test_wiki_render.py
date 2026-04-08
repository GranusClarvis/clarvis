#!/usr/bin/env python3
"""Tests for wiki_render.py and wiki_lint.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from wiki_render import (
    RENDERERS,
    _slugify,
    _short_hash,
    _extract_claims,
    render_markdown,
    render_memo,
    render_plan,
    render_slides,
    render_and_save,
)
from wiki_lint import (
    scan_pages,
    run_lint,
    lint_summary,
    generate_health_report,
    check_orphans,
    check_broken_links,
    check_oversized,
    check_underspecified,
    LintIssue,
)


# ============================================================
# wiki_render tests
# ============================================================

def test_slugify():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("What is IIT?") == "what-is-iit"
    assert len(_slugify("a" * 100)) <= 60


def test_short_hash():
    h = _short_hash("test")
    assert len(h) == 6
    assert h == _short_hash("test")  # deterministic


def test_renderers_registered():
    assert "markdown" in RENDERERS
    assert "memo" in RENDERERS
    assert "plan" in RENDERERS
    assert "slides" in RENDERERS


def test_render_markdown_empty_context():
    ctx = {"question": "test?", "wiki_pages": [], "raw_sources": [], "keywords": ["test"]}
    result = render_markdown("test?", ctx)
    assert "# test?" in result
    assert "No relevant wiki pages" in result


def test_render_memo_empty_context():
    ctx = {"question": "A vs B", "wiki_pages": [], "raw_sources": [], "keywords": ["test"]}
    result = render_memo("A vs B", ctx)
    assert "Comparison Memo" in result
    assert "Comparison Matrix" in result


def test_render_plan_empty_context():
    ctx = {"question": "Build X", "wiki_pages": [], "raw_sources": [], "keywords": ["build"]}
    result = render_plan("Build X", ctx)
    assert "Implementation Plan" in result
    assert "Phase 1" in result
    assert "Phase 2" in result


def test_render_slides_empty_context():
    ctx = {"question": "Overview", "wiki_pages": [], "raw_sources": [], "keywords": ["overview"]}
    result = render_slides("Overview", ctx)
    assert "marp: true" in result
    assert "# Overview" in result


def test_render_markdown_with_pages():
    ctx = {
        "question": "What is X?",
        "wiki_pages": [{
            "title": "Page A",
            "slug": "page-a",
            "section": "concepts",
            "score": 5.0,
            "content": "---\ntitle: Page A\n---\n# Page A\n\nSome text.\n\n## Key Claims\n\n- Claim one [Source: test]\n- Claim two\n",
        }],
        "raw_sources": [],
        "keywords": ["what"],
    }
    result = render_markdown("What is X?", ctx)
    assert "Key Findings" in result
    assert "Claim one" in result
    assert "Page A" in result


def test_render_and_save_dry_run():
    result = render_and_save("markdown", "test question dry", dry_run=True)
    assert "error" not in result
    assert "preview" in result
    assert result["format"] == "markdown"


def test_render_and_save_unknown_format():
    result = render_and_save("nonexistent", "test")
    assert "error" in result


def test_extract_claims_empty():
    assert _extract_claims([]) == []


def test_extract_claims_with_content():
    pages = [{
        "title": "Test",
        "slug": "test",
        "section": "concepts",
        "content": "## Key Claims\n\n- Claim A [Source: x]\n- _Pending_\n- Claim B\n\n## Next",
    }]
    claims = _extract_claims(pages)
    assert len(claims) == 2
    assert claims[0]["text"].startswith("Claim A")


# ============================================================
# wiki_lint tests
# ============================================================

def test_lint_issue_str():
    i = LintIssue("orphan_page", "warning", "concepts/test.md", "No inbound links")
    s = str(i)
    assert "orphan_page" in s
    assert "warning" not in s  # Uses icon ~
    assert "~" in s


def test_lint_issue_to_dict():
    i = LintIssue("broken_link", "error", "x.md", "broken")
    d = i.to_dict()
    assert d["check"] == "broken_link"
    assert d["severity"] == "error"


def test_scan_pages():
    pages = scan_pages()
    assert isinstance(pages, dict)
    # Should have at least the pages we know exist
    assert len(pages) >= 1


def test_run_lint():
    issues = run_lint()
    assert isinstance(issues, list)
    for i in issues:
        assert isinstance(i, LintIssue)


def test_run_lint_single_check():
    issues = run_lint(["orphans"])
    for i in issues:
        assert i.check == "orphan_page"


def test_lint_summary():
    issues = [
        LintIssue("a", "error", "x", "m"),
        LintIssue("b", "warning", "y", "n"),
        LintIssue("b", "warning", "z", "o"),
    ]
    s = lint_summary(issues)
    assert s["total"] == 3
    assert s["by_severity"]["error"] == 1
    assert s["by_severity"]["warning"] == 2
    assert s["by_check"]["b"] == 2


def test_generate_health_report():
    report = generate_health_report([])
    assert "Wiki Health Report" in report
    assert "HEALTHY" in report
    assert "Size" in report
    assert "Ingest Velocity" in report


def test_check_oversized():
    pages = {"test.md": {"body_len": 10000, "body": "x" * 10000, "slug": "test", "title": "Test", "fm": {}}}
    issues = check_oversized(pages)
    assert len(issues) == 1
    assert issues[0].check == "oversized_page"


def test_check_underspecified():
    pages = {"test.md": {"body_len": 50, "body": "x" * 50, "slug": "test", "title": "Test", "fm": {}}}
    issues = check_underspecified(pages)
    assert len(issues) == 1
    assert issues[0].check == "underspecified"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

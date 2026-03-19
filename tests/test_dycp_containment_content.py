"""Tests for _dycp_task_containment_fast content-aware containment.

Validates that the containment check considers cached section *content*
tokens, not just the section name — fixing the bug where sections with
relevant content but non-matching names were wrongly suppressed.
"""

import pytest
from clarvis.context.assembly import (
    _dycp_task_containment_fast,
    _section_content_cache,
    should_suppress_section,
    DYCP_DEFAULT_SUPPRESS,
    DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE,
)
import clarvis.context.assembly as assembly


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset the content cache before and after each test."""
    old = assembly._section_content_cache.copy()
    assembly._section_content_cache.clear()
    yield
    assembly._section_content_cache.clear()
    assembly._section_content_cache.update(old)


# ---------------------------------------------------------------------------
# §1  Name-only matching (backward compat — empty cache)
# ---------------------------------------------------------------------------

def test_name_match_without_cache():
    """Section name tokens still match task text when cache is empty."""
    score = _dycp_task_containment_fast("working_memory", "optimize working memory buffer")
    assert score > 0.0, "Name tokens 'working'+'memory' should overlap with task"


def test_no_match_without_cache():
    """Non-matching name returns 0 when cache is empty."""
    score = _dycp_task_containment_fast("gwt_broadcast", "fix memory retrieval speed")
    assert score == 0.0, "No name overlap and no cache → should be 0"


# ---------------------------------------------------------------------------
# §2  Content-aware matching (with cache)
# ---------------------------------------------------------------------------

def test_content_cache_enables_match():
    """Section with non-matching name but relevant cached content scores > 0."""
    # gwt_broadcast name doesn't match "memory retrieval" task,
    # but its content does (e.g., it broadcasts about memory tasks)
    assembly._section_content_cache["gwt_broadcast"] = {
        "memory", "retrieval", "episodic", "brain", "recall"
    }
    score = _dycp_task_containment_fast(
        "gwt_broadcast", "fix memory retrieval speed"
    )
    assert score > 0.0, (
        "Cached content tokens 'memory'+'retrieval' should match task"
    )


def test_content_score_is_fraction_of_cached_tokens():
    """Content score = overlap / len(content_tokens)."""
    assembly._section_content_cache["attention"] = {
        "memory", "brain", "salience", "focus", "task"
    }
    # Task has "memory" and "brain" → 2/5 = 0.4
    score = _dycp_task_containment_fast(
        "attention", "improve memory brain search"
    )
    assert abs(score - 0.4) < 0.01, f"Expected ~0.4, got {score}"


def test_max_of_name_and_content():
    """Returns max(name_score, content_score) — either signal suffices."""
    # "working_memory" name matches "working memory" task → name_score=1.0
    # Also set cache with unrelated tokens → content_score low
    assembly._section_content_cache["working_memory"] = {
        "unrelated", "tokens", "here"
    }
    score = _dycp_task_containment_fast(
        "working_memory", "optimize working memory buffer"
    )
    assert score >= 0.9, "Name match should dominate when content doesn't match"


def test_content_overrides_name_miss():
    """Content match rescues a section whose name doesn't match the task."""
    assembly._section_content_cache["introspection"] = {
        "context", "relevance", "pruning", "assembly", "brief"
    }
    score = _dycp_task_containment_fast(
        "introspection", "fix context relevance in assembly"
    )
    # name "introspection" has 0 overlap, but content has context+relevance+assembly = 3/5
    assert score >= 0.5, f"Content tokens should rescue: got {score}"


# ---------------------------------------------------------------------------
# §3  Integration: should_suppress_section respects content cache
# ---------------------------------------------------------------------------

def test_suppress_overridden_by_content_cache():
    """A default-suppressed section is NOT suppressed when cached content matches."""
    # Pick a section that's in DYCP_DEFAULT_SUPPRESS
    section = "gwt_broadcast"
    assert section in DYCP_DEFAULT_SUPPRESS

    # Without cache: should be suppressed (name doesn't match)
    assert should_suppress_section(section, "fix memory retrieval") is True

    # With cache containing relevant content: should NOT be suppressed
    assembly._section_content_cache[section] = {
        "memory", "retrieval", "episodic", "brain", "recall"
    }
    # Content score = 2/5 = 0.4 > DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE (0.10)
    assert should_suppress_section(section, "fix memory retrieval") is False


def test_suppress_still_works_with_irrelevant_cache():
    """A soft-suppressed section with irrelevant cached content is still suppressed."""
    section = "world_model"
    assert section in DYCP_DEFAULT_SUPPRESS

    assembly._section_content_cache[section] = {
        "exploration", "strategy", "weights", "gradient", "learning"
    }
    # Task is about "database migration" — no overlap with cache
    assert should_suppress_section(section, "run database migration") is True


def test_hard_suppress_ignores_content_cache():
    """Hard-suppressed section stays suppressed even with relevant cached content."""
    from clarvis.context.assembly import HARD_SUPPRESS
    section = "meta_gradient"
    assert section in HARD_SUPPRESS

    assembly._section_content_cache[section] = {
        "meta", "gradient", "exploration", "reward", "learning"
    }
    # Even with matching content, hard-suppressed sections stay suppressed
    assert should_suppress_section(section, "fix meta gradient exploration") is True


# ---------------------------------------------------------------------------
# §4  Edge cases
# ---------------------------------------------------------------------------

def test_empty_task_text():
    score = _dycp_task_containment_fast("working_memory", "")
    assert score == 0.0


def test_empty_section_name():
    score = _dycp_task_containment_fast("", "some task text here")
    assert score == 0.0


def test_short_task_words_filtered():
    """Words shorter than 3 chars are filtered out by the regex."""
    score = _dycp_task_containment_fast("gwt_broadcast", "a b c")
    assert score == 0.0

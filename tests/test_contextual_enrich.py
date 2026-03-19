"""Tests for contextual_enrich() — chunk-level metadata synthesis for pilot collections."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clarvis"))

from clarvis.brain.search import contextual_enrich, _CONTEXTUAL_PILOT_COLLECTIONS


def _make_result(collection, document, metadata=None):
    return {
        "collection": collection,
        "document": document,
        "metadata": metadata or {},
        "id": "test-id",
        "distance": 0.5,
    }


def test_pilot_collection_gets_prefix():
    """Results from pilot collections should get _contextual_document with prefix."""
    r = _make_result("clarvis-learnings", "Brain query speed averages 7.5s", {
        "source": "performance_benchmark",
        "created_at": "2026-03-15T10:00:00Z",
        "tags": ["perf", "brain"],
    })
    enriched = contextual_enrich([r])
    doc = enriched[0]["_contextual_document"]
    # Should contain collection description
    assert "Insight/lesson learned" in doc
    # Should contain source
    assert "src=performance_benchmark" in doc
    # Should contain date
    assert "2026-03-15" in doc
    # Should contain tags
    assert "perf" in doc
    # Original document preserved
    assert enriched[0]["document"] == "Brain query speed averages 7.5s"
    # Enriched document contains original text
    assert "Brain query speed averages 7.5s" in doc


def test_context_collection_gets_prefix():
    """clarvis-context should also get enrichment."""
    r = _make_result("clarvis-context", "Working on heartbeat pipeline", {
        "created_at": "2026-03-19T08:00:00Z",
    })
    enriched = contextual_enrich([r])
    doc = enriched[0]["_contextual_document"]
    assert "Current working context" in doc
    assert "2026-03-19" in doc
    assert "Working on heartbeat pipeline" in doc


def test_non_pilot_collection_passthrough():
    """Non-pilot collections should get _contextual_document = document (passthrough)."""
    r = _make_result("clarvis-episodes", "Episode: completed task X")
    enriched = contextual_enrich([r])
    assert enriched[0]["_contextual_document"] == "Episode: completed task X"


def test_mixed_collections():
    """Mix of pilot and non-pilot results should be handled correctly."""
    results = [
        _make_result("clarvis-learnings", "Learning A", {"source": "test"}),
        _make_result("clarvis-episodes", "Episode B"),
        _make_result("clarvis-context", "Context C", {"tags": "active"}),
        _make_result("clarvis-memories", "Memory D"),
    ]
    enriched = contextual_enrich(results)
    assert len(enriched) == 4
    # Pilot collections get prefix
    assert enriched[0]["_contextual_document"] != enriched[0]["document"]
    assert enriched[2]["_contextual_document"] != enriched[2]["document"]
    # Non-pilot are passthrough
    assert enriched[1]["_contextual_document"] == "Episode B"
    assert enriched[3]["_contextual_document"] == "Memory D"


def test_empty_metadata():
    """Pilot collection with no metadata should still get collection description."""
    r = _make_result("clarvis-learnings", "Some insight")
    enriched = contextual_enrich([r])
    doc = enriched[0]["_contextual_document"]
    assert doc.startswith("(Insight/lesson learned)")
    assert "Some insight" in doc


def test_tags_list_handling():
    """Tags as list should be joined."""
    r = _make_result("clarvis-learnings", "Test", {"tags": ["a", "b", "c", "d", "e"]})
    enriched = contextual_enrich([r])
    doc = enriched[0]["_contextual_document"]
    # Only first 3 tags
    assert "[a,b,c]" in doc


def test_empty_results():
    """Empty results list should return empty list."""
    assert contextual_enrich([]) == []


def test_pilot_collections_are_correct():
    """Verify pilot collections match the expected set."""
    assert "clarvis-learnings" in _CONTEXTUAL_PILOT_COLLECTIONS
    assert "clarvis-context" in _CONTEXTUAL_PILOT_COLLECTIONS
    assert len(_CONTEXTUAL_PILOT_COLLECTIONS) == 2


if __name__ == "__main__":
    test_pilot_collection_gets_prefix()
    test_context_collection_gets_prefix()
    test_non_pilot_collection_passthrough()
    test_mixed_collections()
    test_empty_metadata()
    test_tags_list_handling()
    test_empty_results()
    test_pilot_collections_are_correct()
    print("All contextual_enrich tests passed!")

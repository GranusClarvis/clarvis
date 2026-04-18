"""Tests for clarvis.metrics.memory_audit — run_full_audit, classify_source, audit_memory_ratios.

Unit tests that mock the brain to avoid dependency on live ChromaDB.
"""

import pytest
from unittest.mock import patch, MagicMock

from clarvis.metrics.memory_audit import (
    classify_source,
    audit_memory_ratios,
    audit_archived_vs_active,
    run_full_audit,
    format_audit,
    record_audit,
    SYNTHETIC_SOURCES,
    CANONICAL_SOURCES,
)


class TestClassifySource:
    """classify_source is pure logic — no mocking needed."""

    def test_synthetic_sources(self):
        for src in ("conversation_learner", "semantic_bridge_builder", "dream_engine"):
            assert classify_source(src) == "synthetic", f"{src} should be synthetic"

    def test_canonical_sources(self):
        for src in ("conversation", "manual", "user", "research"):
            assert classify_source(src) == "canonical", f"{src} should be canonical"

    def test_unknown_source(self):
        assert classify_source("totally_new_source") == "unknown"

    def test_none_source(self):
        assert classify_source(None) == "unknown"

    def test_heuristic_bridge(self):
        assert classify_source("custom_bridge_maker") == "synthetic"

    def test_case_insensitive(self):
        assert classify_source("CONVERSATION") == "canonical"
        assert classify_source("Dream_Engine") == "synthetic"


def _make_mock_brain(collections_data):
    """Build a mock brain with the given per-collection metadata."""
    brain = MagicMock()
    cols = {}
    for name, metas in collections_data.items():
        col = MagicMock()
        col.count.return_value = len(metas)
        col.get.return_value = {
            "metadatas": metas,
            "documents": [f"doc_{i}" for i in range(len(metas))],
        }
        cols[name] = col
    brain.collections = cols
    return brain


class TestAuditMemoryRatios:
    """Test audit_memory_ratios with a mocked brain."""

    def test_basic_ratio_computation(self):
        fake = _make_mock_brain({
            "clarvis-identity": [
                {"source": "manual", "importance": 0.9},
                {"source": "manual", "importance": 0.8},
                {"source": "semantic_bridge_builder", "importance": 0.3},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = audit_memory_ratios()

        assert "collections" in result
        assert "clarvis-identity" in result["collections"]
        col = result["collections"]["clarvis-identity"]
        assert col["canonical"] == 2
        assert col["synthetic"] == 1
        assert col["total"] == 3
        # 1/3 ≈ 0.333 — over 0.30 threshold
        assert col["over_threshold"] is True

    def test_empty_collection(self):
        fake = _make_mock_brain({"clarvis-goals": []})
        with patch("clarvis.brain.brain", fake):
            result = audit_memory_ratios()
        col = result["collections"]["clarvis-goals"]
        assert col["total"] == 0
        assert col["synthetic_ratio"] == 0.0
        assert col["over_threshold"] is False

    def test_alerts_generated(self):
        # All synthetic → over threshold
        fake = _make_mock_brain({
            "clarvis-identity": [
                {"source": "dream_engine", "importance": 0.2},
                {"source": "semantic_bridge_builder", "importance": 0.1},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = audit_memory_ratios()
        assert len(result["alerts"]) >= 1
        assert "clarvis-identity" in result["alerts"][0]


class TestAuditArchivedVsActive:

    def test_low_importance_synthetic_detected(self):
        fake = _make_mock_brain({
            "clarvis-memories": [
                {"source": "dream_engine", "importance": 0.1},
                {"source": "manual", "importance": 0.9},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = audit_archived_vs_active()
        assert result["quality_signals"]["low_importance_synthetic_count"] >= 1

    def test_healthy_collection(self):
        fake = _make_mock_brain({
            "clarvis-goals": [
                {"source": "manual", "importance": 0.8},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = audit_archived_vs_active()
        assert result["quality_signals"]["recommendation"] == "HEALTHY"


class TestRunFullAudit:

    def test_combined_structure(self):
        fake = _make_mock_brain({
            "clarvis-memories": [
                {"source": "manual", "importance": 0.7},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = run_full_audit()

        assert "timestamp" in result
        assert "ratios" in result
        assert "archive_vs_active" in result
        assert "overall_health" in result

    def test_health_healthy(self):
        fake = _make_mock_brain({
            "clarvis-memories": [
                {"source": "manual", "importance": 0.7},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = run_full_audit()
        assert result["overall_health"] == "HEALTHY"

    def test_health_alert_on_over_threshold(self):
        # All synthetic in identity → alert
        fake = _make_mock_brain({
            "clarvis-identity": [
                {"source": "dream_engine", "importance": 0.5},
                {"source": "crosslink", "importance": 0.5},
            ],
        })
        with patch("clarvis.brain.brain", fake):
            result = run_full_audit()
        assert result["overall_health"] == "ALERT"


class TestFormatAudit:

    def test_format_produces_string(self):
        result = {
            "timestamp": "2026-04-18T00:00:00Z",
            "overall_health": "HEALTHY",
            "ratios": {
                "totals": {"total": 10, "canonical": 7, "synthetic": 2, "unknown": 1, "synthetic_ratio": 0.2},
                "collections": {},
                "alerts": [],
            },
            "archive_vs_active": {
                "quality_signals": {"low_importance_synthetic_count": 0, "recommendation": "HEALTHY"},
                "low_importance_synthetic": [],
            },
        }
        output = format_audit(result)
        assert "Memory Audit Report" in output
        assert "HEALTHY" in output

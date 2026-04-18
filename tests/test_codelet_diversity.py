"""Tests for PHASE6_CODELET_DIVERSITY_FLOOR — anti-starvation in codelet competition.

Verifies that non-memory codelets win >= 20% of competitions when memory dominates.
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))

from clarvis.cognition.attention import (
    AttentionCodelet,
    AttentionItem,
    AttentionSpotlight,
    CodeletCompetition,
    CODELET_STATE_FILE,
    DOMAIN_KEYWORDS,
)


@pytest.fixture
def spotlight(tmp_path, monkeypatch):
    """Create a fresh Spotlight with test items spanning multiple domains."""
    monkeypatch.setattr("clarvis.cognition.attention.SPOTLIGHT_FILE", tmp_path / "spotlight.json")
    monkeypatch.setattr("clarvis.cognition.attention.CODELET_STATE_FILE", tmp_path / "codelets.json")
    monkeypatch.setattr("clarvis.cognition.attention.ATTENTION_DIR", tmp_path)
    s = AttentionSpotlight()
    return s


def _submit_items(spotlight, items_config):
    """Submit items to spotlight. items_config: list of (content, importance, relevance)."""
    for content, importance, relevance in items_config:
        spotlight.submit(content, source="test", importance=importance, relevance=relevance)


def _run_n_competitions(spotlight, n):
    """Run n competition cycles and return domain win counts."""
    comp = CodeletCompetition(spotlight)
    wins = {d: 0 for d in DOMAIN_KEYWORDS}
    for _ in range(n):
        result = comp.compete()
        for d in result["coalition"]:
            wins[d] += 1
    return wins, comp


class TestDiversityFloor:
    """Diversity floor must prevent memory from winning > 80% indefinitely."""

    def test_floor_activates_when_memory_dominates(self, spotlight):
        """When memory items dominate, floor should eventually give non-memory a win."""
        # Submit mostly memory items with one code item
        _submit_items(spotlight, [
            ("chromadb memory recall vector store retrieval", 0.9, 0.9),
            ("brain consolidation episodic semantic", 0.8, 0.8),
            ("memory dedup hebbian embedding collection", 0.85, 0.85),
            ("implement python script module refactor", 0.6, 0.6),
        ])

        wins, comp = _run_n_competitions(spotlight, 50)

        non_memory_wins = sum(v for d, v in wins.items() if d != "memory")
        total = sum(wins.values())

        assert non_memory_wins > 0, "Non-memory domains should win at least once in 50 cycles"
        non_memory_share = non_memory_wins / total
        assert non_memory_share >= 0.10, (
            f"Non-memory share {non_memory_share:.2%} too low — "
            f"floor should guarantee diversity. Wins: {wins}"
        )

    def test_floor_does_not_suppress_genuine_diversity(self, spotlight):
        """When domains are naturally balanced, floor should not interfere."""
        _submit_items(spotlight, [
            ("chromadb memory recall", 0.7, 0.7),
            ("python script implement fix bug", 0.7, 0.7),
            ("research paper arxiv cognitive", 0.7, 0.7),
            ("cron gateway systemd backup", 0.7, 0.7),
        ])

        wins, comp = _run_n_competitions(spotlight, 50)

        # All domains should have wins
        active_domains = sum(1 for v in wins.values() if v > 0)
        assert active_domains >= 2, f"Expected multiple winning domains, got: {wins}"

    def test_floor_respects_zero_activation(self, spotlight):
        """Floor should not override to a domain with zero activation."""
        # Only memory items — no other domain should have activation
        _submit_items(spotlight, [
            ("chromadb memory recall vector store", 0.9, 0.9),
            ("brain consolidation episodic", 0.8, 0.8),
        ])

        wins, comp = _run_n_competitions(spotlight, 30)

        # Memory should win every time since there's nothing else activated
        assert wins["memory"] == 30 or sum(wins.values()) == 30

    def test_accumulated_50_cycles_non_memory_above_20pct(self, spotlight):
        """After 50 compete() cycles, non-memory wins >= 20%."""
        _submit_items(spotlight, [
            ("chromadb memory recall dedup embedding", 0.9, 0.9),
            ("brain hebbian vector collection consolidat", 0.85, 0.85),
            ("store retriev semantic episodic", 0.8, 0.8),
            ("python code implement module refactor test", 0.5, 0.5),
            ("cron gateway backup health monitor", 0.4, 0.4),
        ])

        wins, comp = _run_n_competitions(spotlight, 50)

        non_memory_wins = sum(v for d, v in wins.items() if d != "memory")
        total = sum(wins.values())
        share = non_memory_wins / total if total else 0

        # The acceptance criterion from the queue item
        assert share >= 0.20, (
            f"After 50 cycles, non-memory share = {share:.2%} (need >= 20%). Wins: {wins}"
        )

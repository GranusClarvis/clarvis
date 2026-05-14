"""Tests for scripts/seed/seed_preferences_canonical.py — idempotent canonical preferences seed.

Cases:
  (a) clean-state run inserts 4-6 docs
  (b) re-run inserts 0 docs (idempotent)
  (c) every seeded doc carries metadata.source == SEED_SOURCE
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

# Ensure scripts/ is importable for the seed module path
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from clarvis.brain import PREFERENCES  # noqa: E402


@pytest.fixture
def seed_module(monkeypatch, tmp_brain):
    """Load the seed module with get_brain + remember patched to use tmp_brain."""
    # Patch BEFORE importing so module-level `from clarvis.brain import ...`
    # resolves correctly (it's already imported as names; we patch the
    # module-level symbols after import).
    seed_mod = importlib.import_module("scripts.seed.seed_preferences_canonical")
    importlib.reload(seed_mod)

    def fake_get_brain():
        return tmp_brain

    def fake_remember(text, importance=0.9, category=None):
        # Minimal stand-in for clarvis.brain.remember(); seed module now uses
        # brain.store() directly with explicit ids, so this is only kept to
        # satisfy the live import reference in the seed module.
        return tmp_brain.store(
            text, collection=category or PREFERENCES, importance=importance,
            source="manual",
        )

    monkeypatch.setattr(seed_mod, "get_brain", fake_get_brain)
    monkeypatch.setattr(seed_mod, "remember", fake_remember)
    return seed_mod


def test_clean_state_inserts_four_to_six(seed_module, tmp_brain):
    """Case (a): on an empty preferences collection, seed inserts 4-6 docs."""
    result = seed_module.seed(dry_run=False)
    assert result["inserted"] >= 4, f"expected >=4 inserts, got {result['inserted']}"
    assert result["inserted"] <= 6, f"expected <=6 inserts, got {result['inserted']}"
    assert result["skipped"] == 0
    assert len(result["inserted_ids"]) == result["inserted"]

    # Confirm they really landed in PREFERENCES
    col = tmp_brain.collections[PREFERENCES]
    all_items = col.get()
    assert len(all_items["ids"]) == result["inserted"]


def test_rerun_inserts_zero(seed_module, tmp_brain):
    """Case (b): re-running after a successful seed inserts zero duplicates."""
    first = seed_module.seed(dry_run=False)
    assert first["inserted"] >= 4

    second = seed_module.seed(dry_run=False)
    assert second["inserted"] == 0, (
        f"idempotency broken: re-run inserted {second['inserted']} docs"
    )
    assert second["skipped"] >= 4
    assert second["reason"] == "already_seeded"

    # Collection size unchanged after re-run
    col = tmp_brain.collections[PREFERENCES]
    assert len(col.get()["ids"]) == first["inserted"]


def test_metadata_source_present_on_every_doc(seed_module, tmp_brain):
    """Case (c): every seeded doc has metadata.source == SEED_SOURCE."""
    result = seed_module.seed(dry_run=False)
    assert result["inserted"] >= 4

    col = tmp_brain.collections[PREFERENCES]
    items = col.get()
    metas = items.get("metadatas") or []

    assert len(metas) == result["inserted"], "metadata count mismatch"
    for i, meta in enumerate(metas):
        assert meta is not None, f"doc {i} has no metadata"
        assert meta.get("source") == seed_module.SEED_SOURCE, (
            f"doc {i}: metadata.source={meta.get('source')!r} "
            f"expected {seed_module.SEED_SOURCE!r}"
        )
        # Topic should also be present (per task spec)
        assert meta.get("topic"), f"doc {i} missing metadata.topic"
        # Importance per task spec
        assert meta.get("importance") == 0.85, (
            f"doc {i} importance={meta.get('importance')} expected 0.85"
        )

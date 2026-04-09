"""Tests for sidecar pruning (Phase 3.5 — bound sidecar growth)."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest


@pytest.fixture
def sidecar_file(tmp_path):
    """Create a temp sidecar file with aged entries."""
    sf = str(tmp_path / "queue_state.json")
    now = datetime.now(timezone.utc)
    data = {
        "OLD_REMOVED": {
            "state": "removed",
            "updated_at": (now - timedelta(days=45)).isoformat(),
        },
        "RECENT_REMOVED": {
            "state": "removed",
            "updated_at": (now - timedelta(days=5)).isoformat(),
        },
        "OLD_SUCCEEDED": {
            "state": "succeeded",
            "updated_at": (now - timedelta(days=100)).isoformat(),
        },
        "RECENT_SUCCEEDED": {
            "state": "succeeded",
            "updated_at": (now - timedelta(days=30)).isoformat(),
        },
        "PENDING_TASK": {
            "state": "pending",
            "updated_at": (now - timedelta(days=200)).isoformat(),
        },
        "RUNNING_TASK": {
            "state": "running",
            "updated_at": (now - timedelta(days=200)).isoformat(),
        },
    }
    with open(sf, "w") as f:
        json.dump(data, f)
    return sf


def test_prune_removes_old_entries(sidecar_file):
    """Old 'removed' (>30d) and 'succeeded' (>90d) entries are pruned."""
    with patch("clarvis.queue.engine.SIDECAR_FILE", sidecar_file):
        from clarvis.queue.writer import prune_sidecar
        result = prune_sidecar(removed_days=30, succeeded_days=90)

    assert result["removed"] == 1  # OLD_REMOVED
    assert result["succeeded"] == 1  # OLD_SUCCEEDED
    assert result["total_before"] == 6
    assert result["total_after"] == 4

    with open(sidecar_file) as f:
        remaining = json.load(f)
    assert "OLD_REMOVED" not in remaining
    assert "OLD_SUCCEEDED" not in remaining
    assert "RECENT_REMOVED" in remaining
    assert "RECENT_SUCCEEDED" in remaining
    assert "PENDING_TASK" in remaining
    assert "RUNNING_TASK" in remaining


def test_prune_preserves_pending_and_running(sidecar_file):
    """Pending and running entries are never pruned regardless of age."""
    with patch("clarvis.queue.engine.SIDECAR_FILE", sidecar_file):
        from clarvis.queue.writer import prune_sidecar
        result = prune_sidecar(removed_days=0, succeeded_days=0)

    with open(sidecar_file) as f:
        remaining = json.load(f)
    assert "PENDING_TASK" in remaining
    assert "RUNNING_TASK" in remaining


def test_prune_noop_when_nothing_old(sidecar_file):
    """No pruning when all entries are within retention windows."""
    with patch("clarvis.queue.engine.SIDECAR_FILE", sidecar_file):
        from clarvis.queue.writer import prune_sidecar
        result = prune_sidecar(removed_days=999, succeeded_days=999)

    assert result["removed"] == 0
    assert result["succeeded"] == 0
    assert result["total_before"] == result["total_after"]

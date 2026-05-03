"""Tests for clarvis.orch.task_selector — project lane boost behavior.

Covers `[TASK_SELECTOR_MULTI_LANE_BOOST]`: the boost helper must read both
`CLARVIS_PROJECT_LANE` (legacy single lane) and `CLARVIS_ACTIVE_PROJECT_LANES`
(comma-separated multi-lane) at call-time, and apply the boost at most once.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.orch.task_selector import (
    PROJECT_LANE_BOOST,
    _project_lane_boost,
    _active_project_lanes,
)


@pytest.fixture(autouse=True)
def _clean_lane_env(monkeypatch):
    """Ensure each test starts with no lane env vars set."""
    monkeypatch.delenv("CLARVIS_PROJECT_LANE", raising=False)
    monkeypatch.delenv("CLARVIS_ACTIVE_PROJECT_LANES", raising=False)
    yield


def test_no_lane_env_returns_zero():
    assert _project_lane_boost("[SWO_V2_POLISH] some task") == 0.0
    assert _project_lane_boost("any text", "### Subsection") == 0.0


def test_multi_lane_boost(monkeypatch):
    """Acceptance test for [TASK_SELECTOR_MULTI_LANE_BOOST].

    (a) CLARVIS_PROJECT_LANE=SWO only — only SWO tasks boosted.
    (b) CLARVIS_ACTIVE_PROJECT_LANES=SWO,BUNNYBAGZ only — both boosted.
    (c) Both env vars set — both boosted, no double-counting.
    """
    swo_task = "[SWO_V2_POLISH] tighten Star-World-Order grid (PROJECT:SWO)"
    bb_task = "[BB_MOBILE_THUMB_ZONE_AUDIT] verify thumb zone (PROJECT:BUNNYBAGZ)"
    other_task = "[CLARVIS_BRAIN_OPTIMIZE] tune retrieval"

    # (a) Single-lane legacy env: only SWO matches.
    monkeypatch.setenv("CLARVIS_PROJECT_LANE", "SWO")
    monkeypatch.delenv("CLARVIS_ACTIVE_PROJECT_LANES", raising=False)
    assert _project_lane_boost(swo_task) == PROJECT_LANE_BOOST
    assert _project_lane_boost(bb_task) == 0.0
    assert _project_lane_boost(other_task) == 0.0

    # (b) Multi-lane env only: both lanes match.
    monkeypatch.delenv("CLARVIS_PROJECT_LANE", raising=False)
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "SWO,BUNNYBAGZ")
    assert _project_lane_boost(swo_task) == PROJECT_LANE_BOOST
    assert _project_lane_boost(bb_task) == PROJECT_LANE_BOOST
    assert _project_lane_boost(other_task) == 0.0

    # (c) Both env vars: still boosted exactly once (no double-counting).
    monkeypatch.setenv("CLARVIS_PROJECT_LANE", "SWO")
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "SWO,BUNNYBAGZ")
    assert _project_lane_boost(swo_task) == PROJECT_LANE_BOOST
    assert _project_lane_boost(bb_task) == PROJECT_LANE_BOOST
    assert _project_lane_boost(other_task) == 0.0


def test_active_lanes_dedup_and_uppercase(monkeypatch):
    """Lanes from both env vars merge with dedup and upper-case normalization."""
    monkeypatch.setenv("CLARVIS_PROJECT_LANE", "swo")
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "SWO, bunnybagz ,SWO_V2")
    lanes = _active_project_lanes()
    assert lanes == ["SWO", "BUNNYBAGZ", "SWO_V2"]


def test_lane_match_against_subsection(monkeypatch):
    """Subsection text is also scanned (e.g. '### [SWO]')."""
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "SWO")
    assert _project_lane_boost("plain task text", "### [SWO] sprint") == PROJECT_LANE_BOOST


def test_env_read_at_call_time(monkeypatch):
    """Env changes after import must take effect — no stale module-level cache."""
    # First call: nothing set.
    assert _project_lane_boost("(PROJECT:SWO) task") == 0.0
    # Now set lanes mid-run; the next call must pick them up.
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "SWO")
    assert _project_lane_boost("(PROJECT:SWO) task") == PROJECT_LANE_BOOST


def test_boost_value_unchanged():
    """Boost magnitude stays at 0.3 regardless of how many lanes match."""
    assert PROJECT_LANE_BOOST == 0.3

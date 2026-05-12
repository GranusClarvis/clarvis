"""Unit tests for `scripts/maint/esr_backfill_falsely_downgraded.py`.

Acceptance from `[ESR_BACKFILL_FALSELY_DOWNGRADED]`:
  - The predicate the backfill uses matches the 56 falsely-downgraded IDs
    enumerated by the 2026-05-12 triage report.
  - The predicate rejects the 11 `correctly-downgraded` IDs from the same
    report (we must not accidentally flip those — they're real deferrals).

Both assertions exercise the live triage classifier (the same one the audit
script uses) against the live episode records, since that is the defense-in-
depth predicate the backfill script uses before flipping anything.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
TRIAGE_JSON = WORKSPACE / "data" / "audit" / "esr_unverified_triage_2026-05-12.json"
EPISODES_JSON = WORKSPACE / "data" / "episodes.json"
BACKFILL_SCRIPT = WORKSPACE / "scripts" / "maint" / "esr_backfill_falsely_downgraded.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def backfill():
    return _load_module("esr_backfill_falsely_downgraded", BACKFILL_SCRIPT)


@pytest.fixture(scope="module")
def classify(backfill):
    return backfill._load_classify()


@pytest.fixture(scope="module")
def triage():
    return json.loads(TRIAGE_JSON.read_text())


@pytest.fixture(scope="module")
def episodes():
    return {ep["id"]: ep for ep in json.loads(EPISODES_JSON.read_text())}


def _ids_for_bucket(triage, bucket: str) -> list[str]:
    return [c["id"] for c in triage["classifications"] if c["bucket"] == bucket]


def test_triage_report_present_and_well_formed(triage):
    """Sanity: the 2026-05-12 triage exists with the expected bucket counts."""
    counts = triage["bucket_counts"]
    assert counts["falsely-downgraded"] == 56
    assert counts["correctly-downgraded"] == 11
    assert counts["infra-failure"] == 1


def test_predicate_matches_56_falsely_downgraded_ids(classify, triage, episodes):
    """Live classifier must return `falsely-downgraded` for all 56 triage IDs.

    This is the predicate the backfill uses to decide what to flip. If it
    matches fewer than 56, the backfill under-delivers the +0.112 ESR lift.
    If it matches the wrong IDs, the backfill mutates the wrong episodes.
    """
    triage_ids = _ids_for_bucket(triage, "falsely-downgraded")
    assert len(triage_ids) == 56

    matched: list[str] = []
    mismatched: list[tuple[str, str]] = []

    for ep_id in triage_ids:
        ep = episodes.get(ep_id)
        assert ep is not None, f"Missing episode in episodes.json: {ep_id}"
        bucket, _reason = classify(ep)
        if bucket == "falsely-downgraded":
            matched.append(ep_id)
        else:
            mismatched.append((ep_id, bucket))

    assert mismatched == [], (
        f"{len(mismatched)} triage IDs no longer classify as `falsely-downgraded`: "
        f"{mismatched[:5]}"
    )
    assert len(matched) == 56


def test_predicate_rejects_11_correctly_downgraded_ids(classify, triage, episodes):
    """The 11 `correctly-downgraded` IDs MUST NOT match the flip predicate.

    These are episodes where the agent itself flagged the work as not-yet-
    landed (follow-up, operator-blocked, UNVERIFIED). Flipping them to
    success would silently hide real deferrals from the ESR signal.
    """
    triage_ids = _ids_for_bucket(triage, "correctly-downgraded")
    assert len(triage_ids) == 11

    leaked: list[tuple[str, str]] = []
    for ep_id in triage_ids:
        ep = episodes.get(ep_id)
        assert ep is not None, f"Missing episode in episodes.json: {ep_id}"
        bucket, _reason = classify(ep)
        if bucket == "falsely-downgraded":
            leaked.append((ep_id, bucket))

    assert leaked == [], (
        f"{len(leaked)} correctly-downgraded IDs would be wrongly flipped: {leaked}"
    )


def test_is_falsely_downgraded_helper_returns_bool(backfill, classify, episodes, triage):
    """The `is_falsely_downgraded()` helper exposes a clean boolean predicate."""
    falsely_id = _ids_for_bucket(triage, "falsely-downgraded")[0]
    correct_id = _ids_for_bucket(triage, "correctly-downgraded")[0]

    matches_falsely, _ = backfill.is_falsely_downgraded(episodes[falsely_id], classify)
    matches_correct, _ = backfill.is_falsely_downgraded(episodes[correct_id], classify)

    assert matches_falsely is True
    assert matches_correct is False

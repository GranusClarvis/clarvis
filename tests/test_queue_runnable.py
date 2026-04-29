"""Tests for clarvis.queue.runnable — eligible/blocked breakdown.

Covers the lever the evening review and watchdog need:
given QUEUE.md says N pending, what does the engine actually consider runnable
and which filter is dropping each blocked task?
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.queue.engine import QueueEngine
from clarvis.queue.runnable import (
    runnable_view,
    format_view,
    digest_summary,
    _classify,
)


SAMPLE_QUEUE = """\
# Evolution Queue

## P0 — Current Sprint

- [ ] [URGENT_FIX] Fix critical bug in brain.py
- [ ] [DEPLOY_PREP] Prepare deployment checklist

## P1 — This Week

- [ ] [ENGINE_V2] Implement queue engine v2
- [ ] [SWO_V2_POLISH] [SWO_V2] polish work for Star-World-Order
- [x] [DONE_TASK] Already completed

## P2 — When Idle

- [ ] [CLEANUP] Clean up old logs
"""


@pytest.fixture
def tmp_engine(tmp_path):
    queue_file = str(tmp_path / "QUEUE.md")
    sidecar_file = str(tmp_path / "queue_state.json")
    runs_file = str(tmp_path / "queue_runs.jsonl")
    with open(queue_file, "w") as f:
        f.write(SAMPLE_QUEUE)
    return QueueEngine(
        queue_file=queue_file,
        sidecar_file=sidecar_file,
        runs_file=runs_file,
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def test_pending_with_no_skip_until_is_eligible():
    now = time.time()
    task = {"state": "pending", "skip_until": 0, "attempts": 0, "priority": "P1"}
    assert _classify(task, now) == "eligible"


def test_pending_in_backoff_window_is_blocked():
    now = time.time()
    task = {"state": "pending", "skip_until": now + 600, "attempts": 0, "priority": "P1"}
    assert _classify(task, now) == "backoff"


def test_failed_under_retry_cap_is_eligible():
    now = time.time()
    task = {"state": "failed", "skip_until": 0, "attempts": 1, "priority": "P0"}
    assert _classify(task, now) == "eligible"


def test_failed_at_or_above_retry_cap_classifies_max_retries():
    now = time.time()
    # P1 cap is 2
    task = {"state": "failed", "skip_until": 0, "attempts": 2, "priority": "P1"}
    assert _classify(task, now) == "max_retries"


def test_running_classifies_in_progress():
    assert _classify({"state": "running", "priority": "P1"}, time.time()) == "in_progress"


def test_succeeded_state_classifies_succeeded():
    assert _classify({"state": "succeeded", "priority": "P1"}, time.time()) == "succeeded"


def test_deferred_state_classifies_deferred():
    assert _classify({"state": "deferred", "priority": "P1"}, time.time()) == "deferred"


# ---------------------------------------------------------------------------
# runnable_view end-to-end
# ---------------------------------------------------------------------------

def test_clean_queue_all_eligible(tmp_engine):
    view = runnable_view(engine=tmp_engine)
    assert view.in_queue_total == 5
    assert view.eligible_count == 5
    assert view.blocked_count == 0
    assert view.severity == "ok"
    # P0/P1/P2 mix represented
    assert view.counts_by_priority.get("P0") == 2
    assert view.counts_by_priority.get("P1") == 2
    assert view.counts_by_priority.get("P2") == 1


def test_top_eligible_sorted_by_score(tmp_engine):
    view = runnable_view(engine=tmp_engine, top_n=3)
    scores = [t["score"] for t in view.eligible_top]
    assert len(scores) == 3
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    # P0 tasks should outrank P2 in our sample (higher priority weight)
    assert view.eligible_top[0]["priority"] in ("P0", "P1")


def test_in_progress_counted_as_blocked(tmp_engine):
    tmp_engine.reconcile()
    tmp_engine.mark_running("URGENT_FIX")
    view = runnable_view(engine=tmp_engine)
    assert view.counts_by_reason.get("in_progress", 0) == 1
    assert view.eligible_count == 4
    assert view.blocked_count == 1


def test_succeeded_but_unchecked_counts_as_blocked(tmp_engine):
    """If sidecar says succeeded but checkbox stays [ ], runnable_view should
    surface this — it indicates archive_completed/QUEUE drift."""
    tmp_engine.reconcile()
    sidecar = tmp_engine._load()
    sidecar["URGENT_FIX"]["state"] = "succeeded"
    sidecar["DEPLOY_PREP"]["state"] = "succeeded"
    sidecar["ENGINE_V2"]["state"] = "succeeded"
    tmp_engine._save(sidecar)
    view = runnable_view(engine=tmp_engine)
    assert view.counts_by_reason.get("succeeded", 0) == 3
    assert any("checkbox still" in f for f in view.findings)
    assert view.severity in ("warn", "critical")


def test_all_blocked_is_critical(tmp_engine):
    """The exact failure mode that bit us: queue full but engine returns 0
    eligible. runnable_view must mark this critical."""
    tmp_engine.reconcile()
    sidecar = tmp_engine._load()
    for tag in list(sidecar.keys()):
        sidecar[tag]["state"] = "deferred"
    tmp_engine._save(sidecar)
    view = runnable_view(engine=tmp_engine)
    assert view.eligible_count == 0
    assert view.in_queue_total > 0
    assert view.severity == "critical"
    assert any("nothing eligible" in f for f in view.findings)


def test_backoff_window_blocks_pending(tmp_engine):
    tmp_engine.reconcile()
    sidecar = tmp_engine._load()
    sidecar["CLEANUP"]["skip_until"] = time.time() + 7200
    tmp_engine._save(sidecar)
    view = runnable_view(engine=tmp_engine)
    assert view.counts_by_reason.get("backoff", 0) == 1
    samples = view.blocked_samples.get("backoff", [])
    assert any(s["tag"] == "CLEANUP" for s in samples)


def test_project_lane_zero_eligible_warns(tmp_engine, monkeypatch):
    """Project lane set + project tasks all blocked → warn finding so the
    operator/auditor sees the lane is starving."""
    monkeypatch.setenv("CLARVIS_PROJECT_LANE", "SWO_V2")
    # Defer the only project task in our fixture
    tmp_engine.reconcile()
    sidecar = tmp_engine._load()
    sidecar["SWO_V2_POLISH"]["state"] = "deferred"
    tmp_engine._save(sidecar)

    view = runnable_view(engine=tmp_engine)
    assert view.project_lane == "SWO_V2"
    assert view.project_in_queue == 1
    assert view.project_eligible == 0
    assert any("project lane" in f.lower() for f in view.findings)
    assert view.severity in ("warn", "critical")


def test_digest_summary_includes_severity_and_counts(tmp_engine):
    view = runnable_view(engine=tmp_engine)
    s = digest_summary(view)
    assert "queue runnable" in s
    assert f"{view.eligible_count}/{view.in_queue_total}" in s
    assert "[" + view.severity + "]" in s


def test_format_view_text_renders_findings(tmp_engine):
    tmp_engine.reconcile()
    sidecar = tmp_engine._load()
    for tag in list(sidecar.keys()):
        sidecar[tag]["state"] = "deferred"
    tmp_engine._save(sidecar)
    view = runnable_view(engine=tmp_engine)
    text = format_view(view)
    assert "Severity: CRITICAL" in text
    assert "## Findings" in text
    assert "## Block reasons" in text


def test_runnable_view_dict_is_json_safe(tmp_engine):
    view = runnable_view(engine=tmp_engine)
    payload = json.dumps(view.to_dict(), default=str)
    decoded = json.loads(payload)
    assert decoded["in_queue_total"] == view.in_queue_total
    assert decoded["eligible_count"] == view.eligible_count

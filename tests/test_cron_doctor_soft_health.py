"""Regression tests for cron_doctor.check_chromadb_health() soft-vs-hard semantics.

Context: when the brain initializes successfully but health_check reports
non-fatal issues (e.g. graph orphan edges), cron doctor must:
  - return success=True (no hard failure → no paging, no retry-budget burn)
  - mark recoverable_soft_issue=True
  - surface the issue to the evolution queue so hygiene jobs pick it up

Hard init failures (RuntimeError from get_brain) must still:
  - return success=False
  - increment the daily retry budget
"""

import importlib.util
import os
from unittest.mock import MagicMock, patch

import pytest

WORKSPACE = os.environ.get(
    "CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
)
DOCTOR_PATH = os.path.join(WORKSPACE, "scripts", "cron", "cron_doctor.py")


@pytest.fixture(scope="module")
def cd():
    """Import cron_doctor.py as a module without polluting sys.path."""
    if not os.path.exists(DOCTOR_PATH):
        pytest.skip(f"cron_doctor.py not found at {DOCTOR_PATH}")
    spec = importlib.util.spec_from_file_location("cron_doctor", DOCTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_brain(status, issues=None):
    b = MagicMock()
    payload = {"status": status, "total_memories": 1234}
    if issues:
        payload["issues"] = issues
    b.health_check.return_value = payload
    return b


def test_healthy_brain_reports_healthy_and_success(cd):
    with patch("clarvis.brain.get_brain", return_value=_mk_brain("healthy")):
        r = cd.check_chromadb_health()
    assert r["healthy"] is True
    assert r["recoverable_soft_issue"] is False
    assert r["success"] is True


def test_soft_issue_does_not_escalate_as_hard_failure(cd):
    issues = ["graph has 42 orphan edges (run backfill)"]
    with patch("clarvis.brain.get_brain", return_value=_mk_brain("unhealthy", issues)), \
         patch.object(cd, "_add_evolution_task") as aet:
        r = cd.check_chromadb_health()
    assert r["healthy"] is False
    assert r["recoverable_soft_issue"] is True
    # Critical: success=True so cron doctor doesn't page or burn retry budget.
    assert r["success"] is True
    assert "issues" in r and r["issues"] == issues
    # Soft issues must be surfaced to the queue so hygiene/backfill jobs run.
    assert aet.called, "soft issues must be routed to evolution queue"
    queued_text = aet.call_args[0][0]
    assert "orphan" in queued_text.lower()


def test_hard_init_failure_returns_failure(cd):
    with patch("clarvis.brain.get_brain", side_effect=RuntimeError("init busted")), \
         patch.object(cd, "_add_evolution_task"), \
         patch("subprocess.run") as sr:
        sr.return_value = MagicMock(returncode=1, stdout="", stderr="nope")
        r = cd.check_chromadb_health()
    assert r["healthy"] is False
    assert r["recoverable_soft_issue"] is False
    assert r["success"] is False
    assert "init_error" in r


def test_recover_does_not_burn_retry_budget_for_soft_issues(cd):
    """Soft issues must not consume the daily MAX_RETRIES_PER_DAY=2 budget."""
    issues = ["graph has 1 orphan edges (run backfill)"]
    state = {"date": "2026-04-25", "retries": {}, "recoveries": []}
    with patch("clarvis.brain.get_brain", return_value=_mk_brain("unhealthy", issues)), \
         patch.object(cd, "_add_evolution_task"), \
         patch.object(cd, "_load_state", return_value=state), \
         patch.object(cd, "_save_state"), \
         patch.object(cd, "diagnose", return_value=[]):
        cd.recover(dry_run=False)
    assert state["retries"].get("chromadb", 0) == 0


def test_recover_burns_retry_budget_for_hard_failure(cd):
    state = {"date": "2026-04-25", "retries": {}, "recoveries": []}
    with patch("clarvis.brain.get_brain", side_effect=RuntimeError("init busted")), \
         patch.object(cd, "_load_state", return_value=state), \
         patch.object(cd, "_save_state"), \
         patch.object(cd, "diagnose", return_value=[]), \
         patch.object(cd, "_add_evolution_task"), \
         patch("subprocess.run") as sr:
        sr.return_value = MagicMock(returncode=1, stdout="", stderr="")
        cd.recover(dry_run=False)
    assert state["retries"].get("chromadb", 0) == 1

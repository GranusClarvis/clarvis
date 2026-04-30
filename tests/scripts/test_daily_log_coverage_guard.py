"""Tests for the daily-log coverage guard.

Verifies `daily_memory_log.ensure_daily_log` and `audit_coverage` correctly:
  1. Create a stub for today when missing.
  2. Detect closed UTC days that have no .md *or* .md.gz file.
  3. Backfill stubs for missing closed days and emit an alert.
  4. Stay idempotent — re-running does not produce duplicate alerts.
  5. Treat .md.gz as "present" so compressed days are not falsely flagged.
"""
import gzip
import importlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def fresh_ws(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="dlg_test_")
    ws = Path(tmp)
    (ws / "memory").mkdir()
    (ws / "monitoring").mkdir()
    (ws / "data").mkdir()
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(ws))

    repo = Path(os.environ.get("CLARVIS_WORKSPACE_REPO", os.path.expanduser("~/.openclaw/workspace")))
    sys.path.insert(0, str(repo / "scripts" / "tools"))
    import daily_memory_log
    importlib.reload(daily_memory_log)
    yield ws, daily_memory_log
    shutil.rmtree(tmp)


def _utc(delta_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=delta_days)).strftime("%Y-%m-%d")


def test_ensure_creates_today_stub(fresh_ws):
    ws, mod = fresh_ws
    today = _utc(0)
    mod.ensure_daily_log(audit_lookback=0)
    assert (ws / "memory" / f"{today}.md").exists()


def test_audit_backfills_missing_closed_day(fresh_ws):
    ws, mod = fresh_ws
    yesterday = _utc(1)
    result = mod.audit_coverage(lookback_days=2, backfill=True)
    assert yesterday in result["missing"]
    assert yesterday in result["backfilled"]
    assert (ws / "memory" / f"{yesterday}.md").exists()


def test_audit_treats_gz_as_present(fresh_ws):
    ws, mod = fresh_ws
    target = _utc(2)
    (ws / "memory" / f"{target}.md.gz").write_bytes(gzip.compress(b"old day"))
    result = mod.audit_coverage(lookback_days=3, backfill=True)
    assert target not in result["missing"]
    assert not (ws / "memory" / f"{target}.md").exists()


def test_audit_writes_alert_on_first_observation(fresh_ws):
    ws, mod = fresh_ws
    yesterday = _utc(1)
    mod.audit_coverage(lookback_days=2, backfill=False)
    alerts = (ws / "monitoring" / "alerts.log").read_text()
    assert yesterday in alerts
    assert "Daily log missing" in alerts


def test_audit_is_idempotent(fresh_ws):
    ws, mod = fresh_ws
    mod.audit_coverage(lookback_days=2, backfill=False)
    size1 = (ws / "monitoring" / "alerts.log").stat().st_size
    mod.audit_coverage(lookback_days=2, backfill=False)
    size2 = (ws / "monitoring" / "alerts.log").stat().st_size
    assert size1 == size2


def test_audit_state_pruned_outside_window(fresh_ws):
    ws, mod = fresh_ws
    state_path = ws / "data" / "daily_log_audit_state.json"
    state_path.write_text(json.dumps({"alerted": ["2025-01-01"], "last_audit_utc": ""}))
    mod.audit_coverage(lookback_days=3, backfill=True)
    state = json.loads(state_path.read_text())
    assert "2025-01-01" not in state["alerted"]


def test_today_not_flagged_missing(fresh_ws):
    ws, mod = fresh_ws
    # Today must never be reported missing by audit_coverage (the day is open).
    result = mod.audit_coverage(lookback_days=7, backfill=False)
    assert _utc(0) not in result["missing"]

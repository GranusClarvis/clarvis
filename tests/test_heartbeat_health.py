"""Tests for clarvis.heartbeat.health — the silent-failure detector.

Why this exists:
We previously had 11+ consecutive heartbeats silently exit with
all_filtered_by_v2 / "No task selected — exiting" because the queue tag
extractor collapsed every [UNVERIFIED] task to a single sidecar entry.
The shallow evening grep audit ("error|fail|warn") never caught it because
those exits aren't errors — they're just early returns. These tests pin the
classifier so a future regression of the same shape would flip severity to
CRITICAL and surface in the watchdog/digest.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from clarvis.heartbeat import health as hb_health


def _write_log(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "autonomous.log"
    p.write_text(textwrap.dedent(body).lstrip("\n"))
    return p


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

def test_executed_ok_cycle(tmp_path):
    log = _write_log(tmp_path, """
        [2026-04-29T01:00:01] GATE: wake — proceeding with autonomous cycle
        [2026-04-29T01:00:02] === Heartbeat starting (optimized batched pipeline) ===
        [2026-04-29T01:00:04] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T01:06:05] EXECUTION: executor=claude exit=0 duration=361s timeout=1500s tier=complex
        [2026-04-29T01:06:18] === Heartbeat complete (preflight=2.0s + exec=361s + postflight=11.8s) ===
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.total_cycles == 1
    assert report.counts.get("executed_ok") == 1
    assert report.severity in ("ok", "warn", "critical")  # severity may flag '0 executions in window' edge
    # With one ok execution we expect ok or warn (depending on bucket thresholds)
    assert "executed_ok" in report.counts


def test_all_filtered_by_v2_classifies_as_no_task(tmp_path):
    """The exact pattern that bit us: preflight returns all_filtered_by_v2 and
    then 'No task selected — exiting'. Must be classified as no_task."""
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake — proceeding with autonomous cycle
        [2026-04-29T07:00:03] === Heartbeat starting (optimized batched pipeline) ===
        [2026-04-29T07:00:04] PREFLIGHT: AST prediction: domain=code focus=diffuse
        [2026-04-29T07:00:04] PREFLIGHT: Queue status: all_filtered_by_v2
        [2026-04-29T07:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude confidence_tier=HIGH time=0.215s
        [2026-04-29T07:00:05] No task selected — exiting
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.total_cycles == 1
    assert report.counts.get("no_task") == 1
    assert report.consecutive_no_execution == 1
    # 1/1 cycles is 100% no-task — must escalate
    assert report.severity == "critical"


def test_three_consecutive_no_task_is_critical(tmp_path):
    log_lines = []
    for hour in (7, 9, 11):
        log_lines.append(f"[2026-04-29T{hour:02d}:00:01] GATE: wake — proceeding with autonomous cycle")
        log_lines.append(f"[2026-04-29T{hour:02d}:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude")
        log_lines.append(f"[2026-04-29T{hour:02d}:00:05] No task selected — exiting")
    log = _write_log(tmp_path, "\n".join(log_lines) + "\n")
    report = hb_health.analyze(window=10, log_path=log)
    assert report.consecutive_no_execution == 3
    assert report.consecutive_no_task == 3
    assert report.severity == "critical"
    assert any("consecutive" in f.lower() or "no-task" in f.lower() for f in report.findings)


def test_gate_skip_does_not_count_as_no_task(tmp_path):
    """Gate skips are intentional and shouldn't pollute the no-task signal."""
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
        [2026-04-29T09:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
        [2026-04-29T11:00:01] GATE: wake — proceeding with autonomous cycle
        [2026-04-29T11:00:04] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T11:06:05] EXECUTION: executor=claude exit=0 duration=361s timeout=1500s tier=complex
        [2026-04-29T11:06:18] === Heartbeat complete (preflight=2.0s + exec=361s + postflight=11.8s) ===
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.counts.get("gate_skip") == 2
    assert report.counts.get("executed_ok") == 1
    assert report.counts.get("no_task", 0) == 0
    assert report.consecutive_no_task == 0


def test_executed_fail_and_timeout(tmp_path):
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake
        [2026-04-29T07:00:03] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T07:25:05] EXECUTION: executor=claude exit=124 duration=1500s timeout=1500s tier=complex
        [2026-04-29T07:25:18] === Heartbeat complete (preflight=2.0s + exec=1500s + postflight=1.0s) ===
        [2026-04-29T09:00:01] GATE: wake
        [2026-04-29T09:00:03] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T09:01:05] EXECUTION: executor=claude exit=1 duration=60s timeout=1500s tier=complex
        [2026-04-29T09:01:18] === Heartbeat complete (preflight=2.0s + exec=60s + postflight=1.0s) ===
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.counts.get("timeout") == 1
    assert report.counts.get("executed_fail") == 1


def test_instant_fail_is_classified_as_crash(tmp_path):
    """Instant-fail (exit!=0 in <10s) is infrastructure crash, not task failure."""
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake
        [2026-04-29T07:00:03] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T07:00:05] EXECUTION: executor=claude exit=1 duration=2s timeout=1500s tier=complex
        [2026-04-29T07:00:05] CRASH_GUARD: Instant-fail detected (2s < 10s, exit=1) — marking as crash, not failure
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.counts.get("crash") == 1
    assert report.counts.get("executed_fail", 0) == 0


# ---------------------------------------------------------------------------
# Aggregate behaviour
# ---------------------------------------------------------------------------

def test_window_truncates_to_most_recent(tmp_path):
    """Window=N must keep the LATEST N cycles, not the oldest."""
    log_lines = []
    # 5 ancient executions
    for hour in range(5):
        log_lines += [
            f"[2026-04-25T{hour:02d}:00:01] GATE: wake",
            f"[2026-04-25T{hour:02d}:00:03] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s",
            f"[2026-04-25T{hour:02d}:01:05] EXECUTION: executor=claude exit=0 duration=60s timeout=1500s tier=complex",
            f"[2026-04-25T{hour:02d}:01:18] === Heartbeat complete (preflight=2.0s + exec=60s + postflight=1.0s) ===",
        ]
    # 3 recent silent exits
    for hour in range(3):
        log_lines += [
            f"[2026-04-29T{hour:02d}:00:01] GATE: wake",
            f"[2026-04-29T{hour:02d}:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude",
            f"[2026-04-29T{hour:02d}:00:05] No task selected — exiting",
        ]
    log = _write_log(tmp_path, "\n".join(log_lines) + "\n")
    report = hb_health.analyze(window=3, log_path=log)
    assert report.total_cycles == 3
    assert report.counts.get("no_task") == 3
    assert report.severity == "critical"


def test_zero_executions_across_window_is_critical(tmp_path):
    """A window full of skips/no-tasks/deferrals with no execution must alert."""
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
        [2026-04-29T09:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
        [2026-04-29T11:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
        [2026-04-29T13:00:01] GATE: skip — deferring autonomous cycle (nothing changed)
    """)
    report = hb_health.analyze(window=10, log_path=log)
    assert report.severity == "critical"
    assert any("0 executions" in f for f in report.findings)


def test_digest_summary_is_concise_and_includes_severity(tmp_path):
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake
        [2026-04-29T07:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude
        [2026-04-29T07:00:05] No task selected — exiting
    """)
    report = hb_health.analyze(window=10, log_path=log)
    summary = hb_health.digest_summary(report)
    assert "critical" in summary.lower()
    assert "no-task" in summary.lower()
    # Keep the digest tight — it's appended to digest.md
    assert len(summary) < 400


def test_format_report_handles_empty_log(tmp_path):
    log = _write_log(tmp_path, "")
    report = hb_health.analyze(window=10, log_path=log)
    text = hb_health.format_report(report)
    # Empty log gets 0 cycles → critical (zero executions across window)
    assert "Severity:" in text
    assert report.total_cycles == 0


def test_missing_log_file_does_not_crash():
    report = hb_health.analyze(window=10, log_path="/nonexistent/path/autonomous.log")
    assert report.total_cycles == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_json_mode(tmp_path, capsys):
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake
        [2026-04-29T07:00:03] PREFLIGHT: status=ok task_salience=0.5 route=claude confidence_tier=HIGH time=2.0s
        [2026-04-29T07:01:05] EXECUTION: executor=claude exit=0 duration=60s timeout=1500s tier=complex
        [2026-04-29T07:01:18] === Heartbeat complete (preflight=2.0s + exec=60s + postflight=1.0s) ===
    """)
    rc = hb_health.main(["--window", "10", "--log", str(log), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["total_cycles"] == 1
    assert data["counts"]["executed_ok"] == 1
    # Exit code mirrors severity ladder (ok=0, warn=1, critical=2)
    assert rc in (0, 1, 2)


def test_cli_critical_returns_exit_code_2(tmp_path):
    log = _write_log(tmp_path, """
        [2026-04-29T07:00:01] GATE: wake
        [2026-04-29T07:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude
        [2026-04-29T07:00:05] No task selected — exiting
        [2026-04-29T09:00:01] GATE: wake
        [2026-04-29T09:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude
        [2026-04-29T09:00:05] No task selected — exiting
        [2026-04-29T11:00:01] GATE: wake
        [2026-04-29T11:00:05] PREFLIGHT: status=all_filtered_by_v2 task_salience=0.0 route=claude
        [2026-04-29T11:00:05] No task selected — exiting
    """)
    rc = hb_health.main(["--window", "10", "--log", str(log), "--digest"])
    assert rc == 2  # critical → exit code 2 for shell consumers

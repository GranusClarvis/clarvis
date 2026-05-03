"""Tests for clarvis.agents.spawn_ledger and the deferred-spawn flow.

Covers the failure modes that bit us on 2026-05-03:
  - `clarvis queue add` silently exiting 0 when the task was rejected.
  - Deferred spawns having no durable persistence (truncation + no respawn).
  - spawn_claude.sh accepting non-numeric TIMEOUT (arg-swap incident).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from clarvis.agents import spawn_ledger as L


@pytest.fixture
def isolated_ledger(tmp_path, monkeypatch):
    """Point the ledger at a temp directory so we don't pollute production."""
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path / "deferred_spawns")
    monkeypatch.setattr(L, "LEDGER_LOG", tmp_path / "respawn_deferred.log")
    L.LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    return L.LEDGER_DIR


def test_record_deferred_preserves_full_task(isolated_ledger):
    """Ledger must preserve the full operator task — no 120-char truncation."""
    long_task = "Investigate " + ("X" * 800) + " thoroughly."
    path = L.record_deferred(long_task, timeout=1800, isolated=True, retry_max=2)
    assert path is not None
    data = json.loads(path.read_text())
    assert data["task"] == long_task
    assert data["timeout"] == 1800
    assert data["isolated"] is True
    assert data["retry_max"] == 2


def test_list_pending_excludes_processing_dead_expired(isolated_ledger):
    L.record_deferred("Task one", timeout=600)
    L.record_deferred("Task two", timeout=600)
    # Drop a stray .processing file — must be ignored
    (isolated_ledger / "fake.processing-1234").write_text("{}")
    (isolated_ledger / "fake.dead").write_text("{}")
    (isolated_ledger / "fake.expired").write_text("{}")
    pending = L.list_pending()
    assert len(pending) == 2
    tasks = sorted(e.task for e in pending)
    assert tasks == ["Task one", "Task two"]


def test_claim_is_atomic(isolated_ledger):
    L.record_deferred("only-task", timeout=600)
    [entry] = L.list_pending()
    first = L.claim(entry, claimer_pid=11111)
    assert first is not None
    # Second claimer must not get the same entry
    second = L.claim(entry, claimer_pid=22222)
    assert second is None


def test_release_success_consumes_entry(isolated_ledger):
    L.record_deferred("consume-me", timeout=600)
    [entry] = L.list_pending()
    claimed = L.claim(entry, claimer_pid=999)
    L.release(claimed, entry, success=True)
    assert L.list_pending() == []
    assert not claimed.exists()


def test_release_failure_bumps_attempts(isolated_ledger):
    L.record_deferred("retry-me", timeout=600)
    [entry] = L.list_pending()
    claimed = L.claim(entry, claimer_pid=1)
    L.release(claimed, entry, success=False)
    pending = L.list_pending()
    assert len(pending) == 1
    assert pending[0].attempts == 1
    assert pending[0].last_attempt_at is not None


def test_release_failure_at_cap_creates_dead_file(isolated_ledger):
    """After MAX_ATTEMPTS, the entry moves to a `.dead` file for operator review."""
    L.record_deferred("doomed", timeout=600)
    [entry] = L.list_pending()
    entry.attempts = L.MAX_ATTEMPTS - 1
    claimed = L.claim(entry, claimer_pid=2)
    L.release(claimed, entry, success=False)
    assert L.list_pending() == []
    dead = list(isolated_ledger.glob("*.dead"))
    assert len(dead) == 1


def test_reap_expired_drops_old_entries(isolated_ledger, monkeypatch):
    L.record_deferred("ancient", timeout=600)
    [entry] = L.list_pending()
    # Rewrite deferred_at to an obviously old timestamp.
    entry.deferred_at = "2020-01-01T00:00:00Z"
    entry.write()
    dropped = L.reap_expired()
    assert len(dropped) == 1
    assert L.list_pending() == []
    expired = list(isolated_ledger.glob("*.expired"))
    assert len(expired) == 1


def test_iter_to_respawn_skips_max_attempts(isolated_ledger):
    L.record_deferred("eligible", timeout=600)
    L.record_deferred("at-cap", timeout=600)
    for entry in L.list_pending():
        if entry.task == "at-cap":
            entry.attempts = L.MAX_ATTEMPTS
            entry.write()
    eligible = list(L.iter_to_respawn())
    assert len(eligible) == 1
    assert eligible[0].task == "eligible"


# ---------------------------------------------------------------------------
# `clarvis queue add` exit code — root cause #1 of the 2026-05-03 incident.
# ---------------------------------------------------------------------------


def test_queue_add_cli_exits_2_on_duplicate(tmp_path):
    """The CLI must exit non-zero when add_task() returns False.

    The previous behavior was exit 0 with a "Not added" stdout line. This let
    spawn_claude.sh's `if python3 -m clarvis queue add` always think the task
    landed, masking silent loss of deferred entries.

    Triggers rejection via word-overlap dedup against an identical preexisting
    task — works regardless of date/cap state, so the test is hermetic.
    """
    workspace = tmp_path / "ws"
    queue_dir = workspace / "memory" / "evolution"
    queue_dir.mkdir(parents=True)
    queue_file = queue_dir / "QUEUE.md"
    duplicate_text = "Investigate the deferred queue ledger persistence bug fix carefully"
    queue_file.write_text(f"## P0\n\n- [ ] {duplicate_text}\n")
    env = os.environ.copy()
    env["CLARVIS_WORKSPACE"] = str(workspace)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    # Adding the same text again must trip the dedup path → exit 2.
    result = subprocess.run(
        ["python3", "-m", "clarvis", "queue", "add", duplicate_text, "--source", "manual"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2, (
        f"expected exit 2, got {result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Not added" in result.stdout


def test_queue_add_cli_exits_0_on_success(tmp_path):
    workspace = tmp_path / "ws"
    queue_dir = workspace / "memory" / "evolution"
    queue_dir.mkdir(parents=True)
    queue_file = queue_dir / "QUEUE.md"
    queue_file.write_text("## P0\n\n")
    env = os.environ.copy()
    env["CLARVIS_WORKSPACE"] = str(workspace)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    result = subprocess.run(
        ["python3", "-m", "clarvis", "queue", "add",
         "[TEST_GOOD_TASK_TAG] genuinely new task with a tag",
         "--source", "manual"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Added to" in result.stdout


# ---------------------------------------------------------------------------
# spawn_claude.sh argument validation — root cause #4 of the incident.
# ---------------------------------------------------------------------------


SPAWN_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "agents" / "spawn_claude.sh"
)


def _run_spawn(*args, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    # Defang Telegram delivery so the script can't try to wake the bot.
    env["CLARVIS_TG_BOT_TOKEN"] = ""
    env["CLARVIS_TG_CHAT_ID"] = ""
    return subprocess.run(
        [str(SPAWN_SCRIPT), *args],
        env=env, capture_output=True, text=True, timeout=30,
    )


def test_spawn_claude_rejects_empty_task():
    r = _run_spawn("")
    assert r.returncode == 2
    assert "Usage:" in r.stderr or "Usage:" in r.stdout


def test_spawn_claude_rejects_task_starting_with_dash():
    """Catches the failure mode where the operator typed `--retry=3 "real task"`
    and the args got mis-aligned."""
    r = _run_spawn("--retry=3", "would-be-task")
    assert r.returncode == 64
    assert "USAGE_ERROR" in r.stderr or "USAGE_ERROR" in r.stdout


def test_spawn_claude_rejects_non_numeric_timeout():
    """Reproduces the 13:44 incident: TIMEOUT got the prompt text. Previously
    `timeout` accepted the bogus arg only after the worker was detached and
    crashed; now we reject up front with exit 64."""
    r = _run_spawn("legitimate task", "Overhaul Claude spawning...")
    assert r.returncode == 64
    assert "USAGE_ERROR" in r.stderr or "USAGE_ERROR" in r.stdout
    assert "timeout must be" in r.stderr or "timeout must be" in r.stdout


def test_spawn_claude_rejects_too_low_timeout():
    r = _run_spawn("legitimate task", "30")
    assert r.returncode == 64
    assert "too low" in r.stderr or "too low" in r.stdout

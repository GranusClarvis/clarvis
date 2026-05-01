"""Regression tests for the [UNVERIFIED] archive guard.

Covers the prevention mechanism added 2026-05-01 after the BunnyBagz
Phase-1 false-DONE incident (see
`memory/evolution/bunnybagz_realignment_2026-05-01.md`):

  1. In default `log` mode, every `[UNVERIFIED]` archive event is appended
     to `monitoring/queue_unverified_archive.log` so the audit trail
     exists even when the guard is permissive.
  2. In `block` mode (env `CLARVIS_QUEUE_UNVERIFIED_GUARD=block`),
     `[UNVERIFIED]` items without a sidecar verification record at
     `data/audit/queue_verifications/<tag>.json` are NOT archived — they
     stay in QUEUE.md as `[x]` so an operator review can resolve them.
  3. In `block` mode, `[UNVERIFIED]` items WITH a verification record
     archive normally (the gate is honoured).
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clarvis.queue import writer as queue_writer


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    ws = tmp_path
    (ws / "memory" / "evolution").mkdir(parents=True)
    (ws / "data").mkdir(parents=True)
    (ws / "monitoring").mkdir(parents=True)

    queue_file = str(ws / "memory" / "evolution" / "QUEUE.md")
    monkeypatch.setattr(queue_writer, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(
        queue_writer, "STATE_FILE", str(ws / "data" / "queue_writer_state.json")
    )

    return {
        "queue_file": queue_file,
        "archive_file": str(ws / "memory" / "evolution" / "QUEUE_ARCHIVE.md"),
        "verification_dir": str(ws / "data" / "audit" / "queue_verifications"),
        "audit_log": str(ws / "monitoring" / "queue_unverified_archive.log"),
    }


def _seed_queue(path, body):
    with open(path, "w") as f:
        f.write(body)


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


def test_log_mode_archives_unverified_and_writes_audit_entry(tmp_workspace, monkeypatch):
    """Default mode is permissive — items archive but the audit log records it."""
    monkeypatch.delenv("CLARVIS_QUEUE_UNVERIFIED_GUARD", raising=False)
    _seed_queue(
        tmp_workspace["queue_file"],
        "# Evolution Queue\n\n"
        "## P1\n\n"
        "- [x] [UNVERIFIED] **[BB_FAKE_TOKENS]** Claimed token install — done.\n"
        "- [x] **[REAL_DONE_ITEM]** Truly done item (no UNVERIFIED tag).\n",
    )

    archived = queue_writer.archive_completed()
    assert archived == 2, "Both items should archive in default log mode"

    queue_after = _read(tmp_workspace["queue_file"])
    assert "[BB_FAKE_TOKENS]" not in queue_after, "UNVERIFIED still in queue under log mode"
    assert "[REAL_DONE_ITEM]" not in queue_after

    archive_after = _read(tmp_workspace["archive_file"])
    assert "[BB_FAKE_TOKENS]" in archive_after
    assert "[REAL_DONE_ITEM]" in archive_after

    # Audit-log entry exists and is a valid JSONL line.
    log_after = _read(tmp_workspace["audit_log"])
    assert "BB_FAKE_TOKENS" in log_after
    assert "archived" in log_after
    # REAL_DONE_ITEM should NOT log because it has no [UNVERIFIED] marker.
    assert "REAL_DONE_ITEM" not in log_after
    for line in [l for l in log_after.splitlines() if l.strip()]:
        rec = json.loads(line)
        assert rec["guard_mode"] == "log"
        assert rec["action"] == "archived"


def test_block_mode_holds_unverified_without_verification_record(tmp_workspace, monkeypatch):
    """In block mode, UNVERIFIED items stay in QUEUE.md as [x] when no record exists."""
    monkeypatch.setenv("CLARVIS_QUEUE_UNVERIFIED_GUARD", "block")
    _seed_queue(
        tmp_workspace["queue_file"],
        "# Evolution Queue\n\n"
        "## P1\n\n"
        "- [x] [UNVERIFIED] **[BB_FAKE_TOKENS]** Claimed token install — done.\n"
        "- [x] **[VERIFIED_REAL]** Item without UNVERIFIED tag, archives normally.\n",
    )

    archived = queue_writer.archive_completed()
    assert archived == 1, "Only the verified item should archive"

    queue_after = _read(tmp_workspace["queue_file"])
    assert "[BB_FAKE_TOKENS]" in queue_after, "UNVERIFIED item must stay in queue"
    assert "[VERIFIED_REAL]" not in queue_after, "Verified item must archive"

    archive_after = _read(tmp_workspace["archive_file"])
    assert "[BB_FAKE_TOKENS]" not in archive_after
    assert "[VERIFIED_REAL]" in archive_after

    log_after = _read(tmp_workspace["audit_log"])
    held_records = [
        json.loads(l) for l in log_after.splitlines() if l.strip()
    ]
    assert any(
        r.get("tag") == "BB_FAKE_TOKENS" and r.get("action") == "held"
        for r in held_records
    )


def test_block_mode_archives_unverified_with_verification_record(tmp_workspace, monkeypatch):
    """In block mode, an UNVERIFIED item WITH a sidecar verification record
    archives normally."""
    monkeypatch.setenv("CLARVIS_QUEUE_UNVERIFIED_GUARD", "block")

    # Create the verification record at the expected path.
    os.makedirs(tmp_workspace["verification_dir"], exist_ok=True)
    rec_path = os.path.join(tmp_workspace["verification_dir"], "BB_FAKE_TOKENS.json")
    with open(rec_path, "w") as f:
        json.dump(
            {"tag": "BB_FAKE_TOKENS", "verified_at": "2026-05-01T10:00:00Z",
             "evidence": ["theme-tokens.test.ts pass"]},
            f,
        )

    _seed_queue(
        tmp_workspace["queue_file"],
        "# Evolution Queue\n\n"
        "## P1\n\n"
        "- [x] [UNVERIFIED] **[BB_FAKE_TOKENS]** With verification record.\n",
    )

    archived = queue_writer.archive_completed()
    assert archived == 1

    queue_after = _read(tmp_workspace["queue_file"])
    assert "[BB_FAKE_TOKENS]" not in queue_after

    archive_after = _read(tmp_workspace["archive_file"])
    assert "[BB_FAKE_TOKENS]" in archive_after


def test_log_mode_does_not_log_for_non_unverified_items(tmp_workspace, monkeypatch):
    monkeypatch.delenv("CLARVIS_QUEUE_UNVERIFIED_GUARD", raising=False)
    _seed_queue(
        tmp_workspace["queue_file"],
        "# Evolution Queue\n\n## P1\n\n"
        "- [x] **[CLEAN_TASK]** No UNVERIFIED marker, archives silently.\n",
    )

    queue_writer.archive_completed()

    log_after = _read(tmp_workspace["audit_log"])
    # File may not even exist if no UNVERIFIED items were processed.
    assert "CLEAN_TASK" not in log_after

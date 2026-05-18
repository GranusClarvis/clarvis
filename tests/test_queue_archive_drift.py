"""Regression tests for QUEUE.md / sidecar drift repair.

Covers [QUEUE_ARCHIVE_DRIFT_REPAIR] (2026-04-30) — original cause — and the
canonical-fix follow-up (2026-05-18, SWO_CASINO_HILO_UI / TESTNET_OPEN_ACCESS
drift):

  - QUEUE.md `[ ]` is the human-authoritative "open" signal.
  - When sidecar says succeeded for a tag that appears as `[ ]` in QUEUE.md,
    the previous self-heal flipped `[ ]` → `[x]` based on the sidecar. That
    silently erased operator re-opens (the SWO Casino drift case).
  - The new semantics: archive_completed() calls reconcile() first, which
    resurrects sidecar entries (succeeded|removed → pending) for any tag that
    appears as `[ ]` in QUEUE.md. The `[ ]` line stays open; the sidecar
    follows.

Also covers the root-cause fix in engine._mark_checkbox: it must flip ALL
matching unchecked occurrences (not just the first), so duplicate task lines
sharing a tag (e.g., spawned by auto_split) all transition together.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sys as _sys
from clarvis.queue.engine import QueueEngine
from clarvis.queue import writer as queue_writer

# `clarvis.queue.engine` resolves to the QueueEngine *instance* exported by the
# package __init__, not the module — fetch the actual module from sys.modules.
_engine_mod = _sys.modules["clarvis.queue.engine"]


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """Set up an isolated workspace with QUEUE.md, sidecar, archive."""
    ws = tmp_path
    (ws / "memory" / "evolution").mkdir(parents=True)
    (ws / "data").mkdir(parents=True)

    queue_file = str(ws / "memory" / "evolution" / "QUEUE.md")
    archive_file = str(ws / "memory" / "evolution" / "QUEUE_ARCHIVE.md")
    sidecar_file = str(ws / "data" / "queue_state.json")

    # Re-point module-level paths in writer + engine to the temp workspace
    monkeypatch.setattr(queue_writer, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(queue_writer, "STATE_FILE", str(ws / "data" / "queue_writer_state.json"))

    monkeypatch.setattr(_engine_mod, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(_engine_mod, "SIDECAR_FILE", sidecar_file)
    monkeypatch.setattr(_engine_mod, "RUNS_FILE", str(ws / "data" / "queue_runs.jsonl"))

    return {
        "queue_file": queue_file,
        "archive_file": archive_file,
        "sidecar_file": sidecar_file,
    }


def _seed_queue(path, body):
    with open(path, "w") as f:
        f.write(body)


def _seed_sidecar(path, entries):
    with open(path, "w") as f:
        json.dump(entries, f)


def test_archive_resurrects_sidecar_when_queue_md_has_open_box(tmp_workspace):
    """SWO Casino drift regression (2026-05-18).

    When sidecar says succeeded but QUEUE.md still has the row as `[ ]`, the
    operator is signalling "re-open this task". archive_completed() must NOT
    silently flip the box to `[x]` (the prior bug). Instead, it triggers
    reconcile(), which resurrects the sidecar entry to pending.
    """
    queue_body = (
        "# Evolution Queue\n\n"
        "## P0 — Current Sprint\n\n"
        "- [ ] [REOPENED_TASK] Should stay open (added: 2026-05-18, source: test)\n"
        "- [ ] [STILL_RUNNING] Pending task that must remain (added: 2026-05-18, source: test)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "REOPENED_TASK": {
            "state": "succeeded",
            "attempts": 1,
            "updated_at": "2026-04-30T06:08:46Z",
            "priority": "P0",
            "failure_reason": None,
            "skip_until": 0,
        },
        "STILL_RUNNING": {
            "state": "pending",
            "attempts": 0,
            "updated_at": "2026-04-30T06:08:46Z",
            "priority": "P0",
            "failure_reason": None,
            "skip_until": 0,
        },
    })

    archived = queue_writer.archive_completed()
    assert archived == 0, "No [x] entries exist — nothing to archive"

    queue_after = open(tmp_workspace["queue_file"]).read()
    # Re-opened row stays open in QUEUE.md
    assert "- [ ] [REOPENED_TASK]" in queue_after
    assert "- [ ] [STILL_RUNNING]" in queue_after
    # No archive file written (or empty)
    if os.path.exists(tmp_workspace["archive_file"]):
        archive_after = open(tmp_workspace["archive_file"]).read()
        assert "[REOPENED_TASK]" not in archive_after

    # Sidecar got resurrected to pending by the reconcile() call inside
    # archive_completed
    sidecar_after = json.load(open(tmp_workspace["sidecar_file"]))
    assert sidecar_after["REOPENED_TASK"]["state"] == "pending"
    assert sidecar_after["REOPENED_TASK"]["attempts"] == 0
    assert sidecar_after["STILL_RUNNING"]["state"] == "pending"


def test_archive_resurrects_indented_subtask_drift(tmp_workspace):
    """Indented (sub-)task lines are also subject to the resurrection rule."""
    queue_body = (
        "## P0\n\n"
        "- [ ] [PARENT] Parent task (added: 2026-05-18, source: test)\n"
        "  - [ ] [SUB_TASK] Sub-item (added: 2026-05-18, source: auto_split)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "SUB_TASK": {"state": "succeeded", "attempts": 1,
                     "updated_at": "2026-04-30T06:08:46Z", "priority": "P0",
                     "failure_reason": None, "skip_until": 0},
        "PARENT": {"state": "pending", "attempts": 0,
                   "updated_at": "2026-04-30T06:08:46Z", "priority": "P0",
                   "failure_reason": None, "skip_until": 0},
    })

    archived = queue_writer.archive_completed()
    assert archived == 0  # nothing to archive, only resurrection happens

    queue_after = open(tmp_workspace["queue_file"]).read()
    assert "[SUB_TASK]" in queue_after
    assert "- [ ] [PARENT]" in queue_after

    sidecar_after = json.load(open(tmp_workspace["sidecar_file"]))
    assert sidecar_after["SUB_TASK"]["state"] == "pending"
    assert sidecar_after["PARENT"]["state"] == "pending"


def test_archive_resurrects_when_one_of_many_duplicates_reopens(tmp_workspace):
    """If duplicate `[ ]` rows share a tag and the sidecar says succeeded,
    the rule is the same: resurrect to pending. (In practice, engine
    `_mark_checkbox` now flips ALL duplicates together — see
    test_engine_mark_succeeded_flips_all_duplicates — so this drift only
    arises from manual edits or external writers.)"""
    queue_body = (
        "## P0\n\n"
        "- [ ] [DUPE] First occurrence (added: 2026-05-18, source: auto_split)\n"
        "- [ ] [OTHER] Pending other (added: 2026-05-18, source: test)\n"
        "- [ ] [DUPE] Second occurrence (added: 2026-05-18, source: auto_split)\n"
        "- [ ] [DUPE] Third occurrence (added: 2026-05-18, source: auto_split)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "DUPE": {"state": "succeeded", "attempts": 1,
                 "updated_at": "2026-04-30T06:08:46Z", "priority": "P0",
                 "failure_reason": None, "skip_until": 0},
        "OTHER": {"state": "pending", "attempts": 0,
                  "updated_at": "2026-04-30T06:08:46Z", "priority": "P0",
                  "failure_reason": None, "skip_until": 0},
    })

    archived = queue_writer.archive_completed()
    assert archived == 0

    queue_after = open(tmp_workspace["queue_file"]).read()
    assert queue_after.count("- [ ] [DUPE]") == 3
    assert "- [ ] [OTHER]" in queue_after

    sidecar_after = json.load(open(tmp_workspace["sidecar_file"]))
    assert sidecar_after["DUPE"]["state"] == "pending"
    assert sidecar_after["DUPE"]["attempts"] == 0


def test_engine_mark_succeeded_flips_all_duplicates(tmp_workspace):
    """Root-cause fix: engine._mark_checkbox flips every matching [ ] line,
    not just the first — so subsequent archive_completed() can sweep them."""
    queue_body = (
        "## P0\n\n"
        "- [ ] [DUP_TAG] Line one (added: 2026-04-30, source: auto_split)\n"
        "- [ ] [DUP_TAG] Line two (added: 2026-04-30, source: auto_split)\n"
        "  - [ ] [DUP_TAG] Indented line three (added: 2026-04-30, source: auto_split)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)

    eng = QueueEngine(
        queue_file=tmp_workspace["queue_file"],
        sidecar_file=tmp_workspace["sidecar_file"],
        runs_file=str(tmp_workspace["sidecar_file"]) + ".runs",
    )
    eng.reconcile()
    eng.mark_running("DUP_TAG")
    assert eng.mark_succeeded("DUP_TAG", "done")

    queue_after = open(tmp_workspace["queue_file"]).read()
    # All three [ ] [DUP_TAG] became [x] [DUP_TAG] — including the indented one
    assert "- [ ] [DUP_TAG]" not in queue_after
    assert queue_after.count("[x] [DUP_TAG]") == 3


def test_archive_no_op_when_no_drift_and_no_completed(tmp_workspace):
    """Healthy state: no [x] in QUEUE.md and no succeeded sidecar entries
    → archive_completed returns 0 and leaves the file unchanged."""
    queue_body = (
        "## P0\n\n"
        "- [ ] [PENDING] Just pending (added: 2026-04-30, source: test)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "PENDING": {"state": "pending", "updated_at": "2026-04-30T06:08:46Z", "priority": "P0"},
    })

    before = open(tmp_workspace["queue_file"]).read()
    archived = queue_writer.archive_completed()
    after = open(tmp_workspace["queue_file"]).read()

    assert archived == 0
    assert before == after


# ---------------------------------------------------------------------------
# _sync_sidecar_add resurrection tests (write-side canonical fix)
# ---------------------------------------------------------------------------

def test_sync_sidecar_add_inserts_new_tag(tmp_workspace):
    """Baseline: adding a brand-new tag creates a pending sidecar entry."""
    _seed_sidecar(tmp_workspace["sidecar_file"], {})
    queue_writer._sync_sidecar_add(
        [("BRAND_NEW_TAG", "P1")], source="test_source",
    )
    sidecar = json.load(open(tmp_workspace["sidecar_file"]))
    assert sidecar["BRAND_NEW_TAG"]["state"] == "pending"
    assert sidecar["BRAND_NEW_TAG"]["priority"] == "P1"
    assert sidecar["BRAND_NEW_TAG"]["source"] == "test_source"


def test_sync_sidecar_add_resurrects_removed_entry(tmp_workspace):
    """SWO Sanctuary drift regression (2026-05-18): when add_task() re-adds
    a tag whose sidecar entry is `removed`, the entry must be resurrected to
    `pending` immediately — not on the next heartbeat reconcile. Otherwise
    the sidecar stays stuck in `removed` until reconcile runs, and any
    runnable_view / stats inspection in between shows the wrong state.
    """
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "REOPENED": {
            "state": "removed",
            "attempts": 3,
            "failure_reason": "previously gave up",
            "skip_until": 1234567890,
            "updated_at": "2026-05-01T00:00:00Z",
            "priority": "P2",
            "source": "old_source",
        },
    })
    queue_writer._sync_sidecar_add(
        [("REOPENED", "P0")], source="manual_reopen",
    )
    sidecar = json.load(open(tmp_workspace["sidecar_file"]))
    entry = sidecar["REOPENED"]
    assert entry["state"] == "pending"
    assert entry["attempts"] == 0
    assert entry["failure_reason"] is None
    assert entry["skip_until"] == 0
    assert entry["priority"] == "P0"  # priority updated to new section


def test_sync_sidecar_add_resurrects_succeeded_entry(tmp_workspace):
    """Same resurrection rule applies to `succeeded` entries: re-adding a tag
    to QUEUE.md as `[ ]` means the operator wants it run again."""
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "REPEAT_ME": {
            "state": "succeeded",
            "attempts": 1,
            "failure_reason": None,
            "skip_until": 0,
            "updated_at": "2026-05-01T00:00:00Z",
            "priority": "P1",
        },
    })
    queue_writer._sync_sidecar_add([("REPEAT_ME", "P1")], source="rerun")
    sidecar = json.load(open(tmp_workspace["sidecar_file"]))
    entry = sidecar["REPEAT_ME"]
    assert entry["state"] == "pending"
    assert entry["attempts"] == 0


def test_sync_sidecar_add_leaves_active_entries_untouched(tmp_workspace):
    """A `pending`/`running`/`failed`/`deferred` entry is mid-lifecycle —
    _sync_sidecar_add must not clobber it. Priority gets a refresh if it
    moved sections, but state/attempts/failure_reason are preserved."""
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "ACTIVE": {
            "state": "failed",
            "attempts": 2,
            "failure_reason": "still trying",
            "skip_until": 1234567890,
            "updated_at": "2026-05-01T00:00:00Z",
            "priority": "P1",
        },
        "RUNNING": {
            "state": "running",
            "attempts": 1,
            "failure_reason": None,
            "skip_until": 0,
            "updated_at": "2026-05-01T00:00:00Z",
            "priority": "P0",
        },
    })
    queue_writer._sync_sidecar_add(
        [("ACTIVE", "P0"), ("RUNNING", "P0")], source="rerun",
    )
    sidecar = json.load(open(tmp_workspace["sidecar_file"]))
    # Failed entry kept its state + attempts; only priority refreshed.
    assert sidecar["ACTIVE"]["state"] == "failed"
    assert sidecar["ACTIVE"]["attempts"] == 2
    assert sidecar["ACTIVE"]["failure_reason"] == "still trying"
    assert sidecar["ACTIVE"]["priority"] == "P0"
    # Running entry similarly untouched (still running).
    assert sidecar["RUNNING"]["state"] == "running"

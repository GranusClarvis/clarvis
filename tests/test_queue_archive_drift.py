"""Regression tests for QUEUE.md / sidecar drift repair.

Covers [QUEUE_ARCHIVE_DRIFT_REPAIR] (2026-04-30):
  - sidecar shows tag as 'succeeded' but the task line in QUEUE.md is still [ ]
  - this happens when engine._mark_checkbox flipped count=1 of duplicate lines,
    or when a sidecar update happened without touching QUEUE.md at all
  - archive_completed() must self-heal these by flipping [ ] -> [x] using the
    sidecar as the source of truth, then archiving

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


def test_archive_completed_heals_succeeded_unchecked_drift(tmp_workspace):
    """Sidecar says succeeded, QUEUE.md still has [ ] — archive_completed
    must flip the checkbox and archive the entry."""
    queue_body = (
        "# Evolution Queue\n\n"
        "## P0 — Current Sprint\n\n"
        "- [ ] [STUCK_TASK] Should have flipped (added: 2026-04-30, source: test)\n"
        "- [ ] [STILL_RUNNING] Pending task that must remain (added: 2026-04-30, source: test)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "STUCK_TASK": {
            "state": "succeeded",
            "attempts": 1,
            "updated_at": "2026-04-30T06:08:46Z",
            "priority": "P0",
        },
        "STILL_RUNNING": {
            "state": "pending",
            "attempts": 0,
            "updated_at": "2026-04-30T06:08:46Z",
            "priority": "P0",
        },
    })

    archived = queue_writer.archive_completed()
    assert archived == 1, "Expected the drifted task to be archived"

    queue_after = open(tmp_workspace["queue_file"]).read()
    archive_after = open(tmp_workspace["archive_file"]).read()

    # Stuck task was flipped + moved to archive (no longer in QUEUE.md)
    assert "[STUCK_TASK]" not in queue_after
    assert "[STUCK_TASK]" in archive_after
    assert "drift-recovered" in archive_after  # provenance left in archive

    # Pending task untouched
    assert "- [ ] [STILL_RUNNING]" in queue_after


def test_archive_heals_indented_subtask_drift(tmp_workspace):
    """Indented (sub-)task lines must also be flipped + archived."""
    queue_body = (
        "## P0\n\n"
        "- [ ] [PARENT] Parent task (added: 2026-04-30, source: test)\n"
        "  - [ ] [SUB_TASK] Sub-item (added: 2026-04-30, source: auto_split)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "SUB_TASK": {"state": "succeeded", "updated_at": "2026-04-30T06:08:46Z", "priority": "P0"},
        "PARENT": {"state": "pending", "updated_at": "2026-04-30T06:08:46Z", "priority": "P0"},
    })

    archived = queue_writer.archive_completed()
    assert archived == 1

    queue_after = open(tmp_workspace["queue_file"]).read()
    archive_after = open(tmp_workspace["archive_file"]).read()

    assert "[SUB_TASK]" not in queue_after
    assert "[SUB_TASK]" in archive_after
    assert "[PARENT]" in queue_after  # parent untouched


def test_archive_heals_duplicate_lines_sharing_tag(tmp_workspace):
    """Multiple [ ] lines sharing one tag (auto_split duplicates) all flip
    and archive together once the sidecar marks the tag succeeded."""
    queue_body = (
        "## P0\n\n"
        "- [ ] [DUPE] First occurrence (added: 2026-04-30, source: auto_split)\n"
        "- [ ] [OTHER] Pending other (added: 2026-04-30, source: test)\n"
        "- [ ] [DUPE] Second occurrence (added: 2026-04-30, source: auto_split)\n"
        "- [ ] [DUPE] Third occurrence (added: 2026-04-30, source: auto_split)\n"
    )
    _seed_queue(tmp_workspace["queue_file"], queue_body)
    _seed_sidecar(tmp_workspace["sidecar_file"], {
        "DUPE": {"state": "succeeded", "updated_at": "2026-04-30T06:08:46Z", "priority": "P0"},
        "OTHER": {"state": "pending", "updated_at": "2026-04-30T06:08:46Z", "priority": "P0"},
    })

    archived = queue_writer.archive_completed()
    assert archived == 3, "All three duplicate DUPE lines should archive"

    queue_after = open(tmp_workspace["queue_file"]).read()
    archive_after = open(tmp_workspace["archive_file"]).read()

    assert "[DUPE]" not in queue_after, "All DUPE lines must be archived"
    assert archive_after.count("[DUPE]") == 3
    assert "- [ ] [OTHER]" in queue_after


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

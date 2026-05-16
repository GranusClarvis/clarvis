"""Tests for `scripts/cron/queue_swo_sync.py`.

Four acceptance cases per the [CLARVIS_PROC_QUEUE_SWO_SYNC] contract:

  1. tracker has new P0 not in queue -> row appended
  2. tracker has tag now DONE      -> queue row archived (flipped to [x])
  3. tracker row already in queue  -> no-op
  4. --dry-run                     -> no writes
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def sync_mod():
    here = Path(__file__).resolve()
    script_path = here.parent.parent / "scripts" / "cron" / "queue_swo_sync.py"
    spec = importlib.util.spec_from_file_location("queue_swo_sync", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["queue_swo_sync"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_tracker(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def _write_queue(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def files(tmp_path: Path):
    tracker = tmp_path / "SWO_TRACKER.md"
    queue = tmp_path / "QUEUE.md"
    return tracker, queue


# --------------------------------------------------------------------------- #
# Case 1: tracker has new P0 not in queue -> row appended                      #
# --------------------------------------------------------------------------- #
def test_new_p0_tracker_row_is_appended_to_queue(sync_mod, files):
    tracker, queue = files
    _write_tracker(tracker, (
        "## V2 — De-Slop Priority Queue\n\n"
        "| # | Task | Acceptance | Lane | Priority |\n"
        "|---|------|------------|------|----------|\n"
        "| 2 | `[SWO_V2_PLAYER_SPRITE_ALIASING]` | Fix aliasing. | V2 | P0 |\n"
    ))
    _write_queue(queue, (
        "# Evolution Queue — Clarvis\n\n"
        "### Star Sanctuary — Companion-First Core Loop\n\n"
        "#### V2 — De-Slop Polish (Track B)\n\n"
        "- [ ] [UNVERIFIED] **[SWO_V2_ROOM_PALETTE_STANDARDIZE]** placeholder\n"
    ))

    rc = sync_mod.main([
        "--tracker", str(tracker), "--queue", str(queue),
    ])
    assert rc == 0

    body = queue.read_text(encoding="utf-8")
    assert "[SWO_V2_PLAYER_SPRITE_ALIASING]" in body
    # Two rows now exist in QUEUE.md task lines.
    open_tags = sync_mod.queue_task_tags(body)
    assert "SWO_V2_PLAYER_SPRITE_ALIASING" in open_tags
    assert "SWO_V2_ROOM_PALETTE_STANDARDIZE" in open_tags


# --------------------------------------------------------------------------- #
# Case 2: tracker has tag now DONE -> queue row archived                       #
# --------------------------------------------------------------------------- #
def test_done_tracker_row_archives_queue_row(sync_mod, files, monkeypatch):
    tracker, queue = files
    _write_tracker(tracker, (
        "## V2 — De-Slop Priority Queue\n\n"
        "| # | Task | Acceptance | Lane | Priority | Status |\n"
        "|---|------|------------|------|----------|--------|\n"
        "| 1 | `[SWO_V2_DESLOP_SHADER]` | Shader. | V2 | P0 | ✅ DONE |\n"
    ))
    _write_queue(queue, (
        "# Evolution Queue\n\n"
        "#### V2 — De-Slop Polish\n\n"
        "- [ ] [UNVERIFIED] **[SWO_V2_DESLOP_SHADER]** Shader. (PROJECT:SWO)\n"
    ))

    # Stub out the writer side-effect so the test does not depend on the
    # production sidecar/archive files.
    archive_calls = {"n": 0}

    def _fake_archive():
        archive_calls["n"] += 1
        return 1

    fake_mod = type(sys)("clarvis.queue.writer")
    fake_mod.archive_completed = _fake_archive
    monkeypatch.setitem(sys.modules, "clarvis.queue.writer", fake_mod)

    rc = sync_mod.main([
        "--tracker", str(tracker), "--queue", str(queue),
    ])
    assert rc == 0
    assert archive_calls["n"] == 1

    body = queue.read_text(encoding="utf-8")
    # The row is flipped to [x] in QUEUE.md before archive_completed runs.
    assert "- [x]" in body
    assert "[SWO_V2_DESLOP_SHADER]" in body
    # No new open row was added.
    assert body.count("- [ ] [UNVERIFIED] **[SWO_V2_DESLOP_SHADER]**") == 0


# --------------------------------------------------------------------------- #
# Case 3: tracker row already in queue -> no-op                                #
# --------------------------------------------------------------------------- #
def test_existing_tracker_row_in_queue_is_noop(sync_mod, files):
    tracker, queue = files
    _write_tracker(tracker, (
        "## V2 — De-Slop Priority Queue\n\n"
        "| # | Task | Lane | Priority |\n"
        "|---|------|------|----------|\n"
        "| 4 | `[SWO_V2_ROOM_PALETTE_STANDARDIZE]` | V2 | P1 |\n"
    ))
    original = (
        "# Evolution Queue\n\n"
        "#### V2 — De-Slop Polish\n\n"
        "- [ ] [UNVERIFIED] **[SWO_V2_ROOM_PALETTE_STANDARDIZE]** Standardize palette.\n"
    )
    _write_queue(queue, original)

    rc = sync_mod.main([
        "--tracker", str(tracker), "--queue", str(queue),
    ])
    assert rc == 0
    # QUEUE.md was not modified.
    assert queue.read_text(encoding="utf-8") == original


# --------------------------------------------------------------------------- #
# Case 4: --dry-run -> no writes                                               #
# --------------------------------------------------------------------------- #
def test_dry_run_writes_nothing(sync_mod, files, capsys):
    tracker, queue = files
    _write_tracker(tracker, (
        "## V2 — De-Slop Priority Queue\n\n"
        "| # | Task | Lane | Priority |\n"
        "|---|------|------|----------|\n"
        "| 3 | `[SWO_V2_NPC_DISPLAY_SIZE]` | V2 | P0 |\n"
    ))
    original = (
        "# Evolution Queue\n\n"
        "#### V2 — De-Slop Polish\n\n"
        "- [ ] [UNVERIFIED] **[SWO_V2_ROOM_PALETTE_STANDARDIZE]** placeholder\n"
    )
    _write_queue(queue, original)

    rc = sync_mod.main([
        "--dry-run", "--tracker", str(tracker), "--queue", str(queue),
    ])
    assert rc == 0

    # QUEUE.md unchanged on disk.
    assert queue.read_text(encoding="utf-8") == original

    # But the dry-run diff is printed.
    out = capsys.readouterr().out
    assert "[SWO_V2_NPC_DISPLAY_SIZE]" in out
    assert "forward: 1 tracker rows missing" in out


# --------------------------------------------------------------------------- #
# Compile guard                                                                #
# --------------------------------------------------------------------------- #
def test_script_passes_py_compile():
    import py_compile
    here = Path(__file__).resolve()
    target = here.parent.parent / "scripts" / "cron" / "queue_swo_sync.py"
    py_compile.compile(str(target), doraise=True)

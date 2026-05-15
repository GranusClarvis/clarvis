"""Tests for `scripts/hooks/pre_commit_queue_artifact_check.py`.

Four fixture-backed acceptance cases per the [CLARVIS_PROC_QUEUE_ARTIFACT_HOOK]
contract:

  1. newly-checked row with missing path -> reject
  2. newly-checked row with present path -> accept
  3. PROJECT-tagged row matching an active lane with missing path -> accept
  4. row unchanged in diff (same `[x] [UNVERIFIED]` text in both HEAD and
     staged) -> ignored

A fifth `py_compile` test guards acceptance (a).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def hook():
    here = Path(__file__).resolve()
    scripts_dir = here.parent.parent / "scripts"
    hooks_dir = scripts_dir / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    return importlib.import_module("pre_commit_queue_artifact_check")


@pytest.fixture
def workspace(tmp_path):
    """A throwaway 'repo root' with a scripts/ tree we can populate per test."""
    (tmp_path / "scripts" / "hooks").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def _write_queue(path: Path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_newly_checked_row_with_missing_path_is_rejected(hook, workspace, tmp_path):
    head = tmp_path / "QUEUE.head.md"
    staged = tmp_path / "QUEUE.staged.md"
    _write_queue(
        head,
        [
            "## P0 — Current Sprint",
            "- [ ] **[CLARVIS_TEST_MISSING]** Build the thing. (PROJECT:CLARVIS)",
        ],
    )
    _write_queue(
        staged,
        [
            "## P0 — Current Sprint",
            "- [x] [UNVERIFIED] **[CLARVIS_TEST_MISSING]** Shipped at `scripts/never_existed.py` with tests in `tests/never_existed.py`. (PROJECT:CLARVIS)",
        ],
    )
    rc = hook.main(
        [
            "--path",
            str(staged),
            "--head",
            str(head),
            "--workspace",
            str(workspace),
        ]
    )
    assert rc == 1


def test_newly_checked_row_with_present_path_is_accepted(hook, workspace, tmp_path):
    # Provide the artifact on disk under the workspace.
    artifact_dir = workspace / "scripts" / "infra"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "shipped_thing.py"
    artifact.write_text("# shipped\n", encoding="utf-8")

    head = tmp_path / "QUEUE.head.md"
    staged = tmp_path / "QUEUE.staged.md"
    _write_queue(
        head,
        [
            "## P0 — Current Sprint",
            "- [ ] **[CLARVIS_TEST_PRESENT]** Ship it. (PROJECT:CLARVIS)",
        ],
    )
    _write_queue(
        staged,
        [
            "## P0 — Current Sprint",
            "- [x] [UNVERIFIED] **[CLARVIS_TEST_PRESENT]** Shipped at `scripts/infra/shipped_thing.py`. (PROJECT:CLARVIS)",
        ],
    )
    rc = hook.main(
        [
            "--path",
            str(staged),
            "--head",
            str(head),
            "--workspace",
            str(workspace),
        ]
    )
    assert rc == 0


def test_project_tagged_missing_path_is_bypassed_via_active_lanes(
    hook, workspace, tmp_path, monkeypatch
):
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "PROJECT:SWO PROJECT:BUNNYBAGZ")

    head = tmp_path / "QUEUE.head.md"
    staged = tmp_path / "QUEUE.staged.md"
    _write_queue(
        head,
        [
            "## P1 — This Week",
            "- [ ] **[SWO_V2_COMPANION_PIP]** Polish companion. (PROJECT:SWO)",
        ],
    )
    _write_queue(
        staged,
        [
            "## P1 — This Week",
            "- [x] [UNVERIFIED] **[SWO_V2_COMPANION_PIP]** Polish landed at `scripts/never_existed.py` and `docs/never_existed.md`. (PROJECT:SWO)",
        ],
    )
    rc = hook.main(
        [
            "--path",
            str(staged),
            "--head",
            str(head),
            "--workspace",
            str(workspace),
        ]
    )
    assert rc == 0, "PROJECT:SWO row should bypass the artifact check"


def test_unchanged_row_is_ignored(hook, workspace, tmp_path):
    """A row that was already `[x] [UNVERIFIED]` in HEAD must not trigger
    the check, even if its referenced artifact is missing — the failure
    belonged to the original commit, not this one."""
    same_row = (
        "- [x] [UNVERIFIED] **[CLARVIS_TEST_UNCHANGED]** Old shipment "
        "at `scripts/long_gone.py`. (PROJECT:CLARVIS)"
    )
    head = tmp_path / "QUEUE.head.md"
    staged = tmp_path / "QUEUE.staged.md"
    _write_queue(head, ["## P0 — Current Sprint", same_row])
    _write_queue(
        staged,
        [
            "## P0 — Current Sprint",
            same_row,
            "",  # whitespace-only addition so the diff is nonempty.
        ],
    )
    rc = hook.main(
        [
            "--path",
            str(staged),
            "--head",
            str(head),
            "--workspace",
            str(workspace),
        ]
    )
    assert rc == 0


def test_script_compiles():
    """Acceptance (a): hook file passes `python3 -m py_compile`."""
    here = Path(__file__).resolve()
    script = (
        here.parent.parent
        / "scripts"
        / "hooks"
        / "pre_commit_queue_artifact_check.py"
    )
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

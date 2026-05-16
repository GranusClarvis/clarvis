"""Tests for `scripts/agents/spawn_postflight_verify.py`.

Coverage:
  1. No-concrete-path closure -> emits a NO_CONCRETE_ARTIFACT_PATH hold and
     annotates the row.
  2. Present-path closure -> no holds, no annotation.
  3. Active-lane bypass exempts both missing-path and no-path rows.
  4. py_compile guard on the script.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_postflight():
    here = Path(__file__).resolve()
    script = (
        here.parent.parent / "scripts" / "agents" / "spawn_postflight_verify.py"
    )
    spec = importlib.util.spec_from_file_location("spawn_postflight_verify", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def postflight():
    return _load_postflight()


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "memory" / "evolution").mkdir(parents=True)
    (tmp_path / "monitoring").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    return tmp_path


def _write(path: Path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_holds(holds_log: Path):
    if not holds_log.exists():
        return []
    return [json.loads(l) for l in holds_log.read_text().splitlines() if l.strip()]


def test_no_concrete_path_closure_emits_hold(postflight, workspace):
    queue = workspace / "memory" / "evolution" / "QUEUE.md"
    holds_log = workspace / "monitoring" / "spawn_artifact_holds.log"
    pre_lines = [
        "## P0 — Current Sprint",
        "- [ ] **[CLARVIS_T_PROSE]** Look into the thing. (PROJECT:CLARVIS)",
    ]
    _write(queue, pre_lines)
    # Flip to UNVERIFIED prose-only closure.
    post_lines = [
        "## P0 — Current Sprint",
        "- [x] [UNVERIFIED] **[CLARVIS_T_PROSE]** Looked, no action needed. (PROJECT:CLARVIS)",
    ]
    _write(queue, post_lines)

    rc, holds = postflight.verify(
        pre_lines=pre_lines,
        workspace=workspace,
        queue_path=queue,
        holds_log_path=holds_log,
        session_id="sess-test-1",
    )
    assert rc == 1
    assert len(holds) == 1
    assert holds[0]["reason"] == "NO_CONCRETE_ARTIFACT_PATH"
    assert holds[0]["missing_path"] is None
    assert holds[0]["tag"] == "CLARVIS_T_PROSE"

    persisted = _read_holds(holds_log)
    assert len(persisted) == 1
    assert persisted[0]["reason"] == "NO_CONCRETE_ARTIFACT_PATH"

    annotated = queue.read_text()
    assert "SPAWN_POSTFLIGHT_HELD: NO_CONCRETE_ARTIFACT_PATH" in annotated
    assert "add a real file path" in annotated


def test_present_path_closure_emits_no_hold(postflight, workspace):
    queue = workspace / "memory" / "evolution" / "QUEUE.md"
    holds_log = workspace / "monitoring" / "spawn_artifact_holds.log"
    # Provide the artifact.
    (workspace / "scripts" / "infra").mkdir(parents=True)
    (workspace / "scripts" / "infra" / "shipped.py").write_text("# ok\n")

    pre_lines = [
        "## P0 — Current Sprint",
        "- [ ] **[CLARVIS_T_PRESENT]** Ship it. (PROJECT:CLARVIS)",
    ]
    _write(queue, pre_lines)
    post_lines = [
        "## P0 — Current Sprint",
        "- [x] [UNVERIFIED] **[CLARVIS_T_PRESENT]** Shipped at `scripts/infra/shipped.py`. (PROJECT:CLARVIS)",
    ]
    _write(queue, post_lines)

    rc, holds = postflight.verify(
        pre_lines=pre_lines,
        workspace=workspace,
        queue_path=queue,
        holds_log_path=holds_log,
        session_id="sess-test-2",
    )
    assert rc == 0
    assert holds == []
    assert not holds_log.exists()


def test_active_lane_bypasses_both_failure_modes(
    postflight, workspace, monkeypatch
):
    """An active project lane exempts the row regardless of which failure
    mode it would otherwise trigger."""
    monkeypatch.setenv("CLARVIS_ACTIVE_PROJECT_LANES", "PROJECT:SWO")
    queue = workspace / "memory" / "evolution" / "QUEUE.md"
    holds_log = workspace / "monitoring" / "spawn_artifact_holds.log"
    pre_lines = [
        "## P1 — This Week",
        "- [ ] **[SWO_PROSE]** Polish vibes. (PROJECT:SWO)",
        "- [ ] **[SWO_MISSING]** Land a thing. (PROJECT:SWO)",
    ]
    _write(queue, pre_lines)
    post_lines = [
        "## P1 — This Week",
        "- [x] [UNVERIFIED] **[SWO_PROSE]** Done, looks good. (PROJECT:SWO)",
        "- [x] [UNVERIFIED] **[SWO_MISSING]** Landed at `scripts/never_existed.py`. (PROJECT:SWO)",
    ]
    _write(queue, post_lines)

    rc, holds = postflight.verify(
        pre_lines=pre_lines,
        workspace=workspace,
        queue_path=queue,
        holds_log_path=holds_log,
        session_id="sess-test-3",
    )
    assert rc == 0
    assert holds == []
    assert not holds_log.exists()


def test_script_compiles():
    here = Path(__file__).resolve()
    script = (
        here.parent.parent / "scripts" / "agents" / "spawn_postflight_verify.py"
    )
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

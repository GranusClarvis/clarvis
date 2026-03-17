"""Queue writer mode-gating tests."""

import importlib
import sys
from pathlib import Path


def _prepare_queue_file(path: Path):
    path.write_text(
        "\n".join(
            [
                "# Evolution Queue",
                "",
                "## P0",
                "",
                "## P1",
                "",
                "## P2",
                "",
            ]
        )
    )


def _load_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("CLARVIS_WORKSPACE", str(tmp_path))
    import clarvis.runtime.mode as mode_module
    mode_module = importlib.reload(mode_module)

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import queue_writer as queue_writer_module
    queue_writer_module = importlib.reload(queue_writer_module)

    queue_writer_module.QUEUE_FILE = str(tmp_path / "memory" / "evolution" / "QUEUE.md")
    queue_writer_module.STATE_FILE = str(tmp_path / "data" / "queue_writer_state.json")
    return mode_module, queue_writer_module


def test_passive_mode_blocks_autonomous_injection(monkeypatch, tmp_path):
    queue_path = tmp_path / "memory" / "evolution" / "QUEUE.md"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_queue_file(queue_path)

    mode, q = _load_modules(monkeypatch, tmp_path)
    mode.set_mode("passive", defer_if_active=False, active_tasks=0)

    added = q.add_tasks(
        ["[AUTO_SPLIT 2026-03-15] Improve retrieval graph heuristics"],
        priority="P1",
        source="auto_split",
    )
    assert added == []

    # User-directed/manual source should be allowed in passive mode.
    added_manual = q.add_tasks(
        ["[MANUAL 2026-03-15] User task: update architecture notes"],
        priority="P1",
        source="manual",
    )
    assert len(added_manual) == 1


def test_architecture_mode_allows_improvements_but_blocks_new_features(monkeypatch, tmp_path):
    queue_path = tmp_path / "memory" / "evolution" / "QUEUE.md"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_queue_file(queue_path)

    mode, q = _load_modules(monkeypatch, tmp_path)
    mode.set_mode("architecture", defer_if_active=False, active_tasks=0)

    blocked = q.add_tasks(
        ["[AUTO_SPLIT 2026-03-15] Build new feature for autonomous ideation"],
        priority="P1",
        source="auto_split",
    )
    assert blocked == []

    allowed = q.add_tasks(
        ["[AUTO_SPLIT 2026-03-15] Fix retrieval regressions and benchmark precision"],
        priority="P1",
        source="auto_split",
    )
    assert len(allowed) == 1

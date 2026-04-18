"""Tests for queue_writer provenance suffix format (Phase 13)."""

import os
import re
import tempfile

import pytest


@pytest.fixture
def queue_env(tmp_path, monkeypatch):
    """Set up isolated queue_writer environment."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evo_dir = workspace / "memory" / "evolution"
    evo_dir.mkdir(parents=True)
    data_dir = workspace / "data"
    data_dir.mkdir(parents=True)

    # Create minimal QUEUE.md
    queue_file = evo_dir / "QUEUE.md"
    queue_file.write_text(
        "# Evolution Queue\n\n## P0 — Current Sprint\n\n## P1 — This Week\n\n## P2 — When Idle\n"
    )

    monkeypatch.setenv("CLARVIS_WORKSPACE", str(workspace))

    import importlib
    import clarvis.queue.writer as qw
    qw._WS = str(workspace)
    qw.QUEUE_FILE = str(queue_file)
    qw.STATE_FILE = str(data_dir / "queue_writer_state.json")

    return qw, str(queue_file)


def test_add_task_has_provenance_suffix(queue_env):
    """Auto-generated tasks should have (added: DATE, source: SOURCE) suffix."""
    qw, queue_file = queue_env
    added = qw.add_tasks(
        ["**[TEST_PROV_ITEM]** Test provenance formatting is correct"],
        priority="P1",
        source="manual",
    )
    assert len(added) == 1

    with open(queue_file) as f:
        content = f.read()

    # Check suffix format
    prov_re = re.compile(r'\(added: \d{4}-\d{2}-\d{2}, source: manual\)')
    assert prov_re.search(content), f"Provenance suffix not found in:\n{content}"

    # Ensure no legacy prefix format
    prefix_re = re.compile(r'\[MANUAL \d{4}-\d{2}-\d{2}\]')
    assert not prefix_re.search(content), f"Legacy prefix format found in:\n{content}"


def test_provenance_dedup_on_readd(queue_env):
    """Re-adding a task with existing provenance should not double-suffix."""
    qw, queue_file = queue_env

    task = "**[TEST_DEDUP_PROV]** Unique dedup test task ABC789 (added: 2026-01-01, source: old)"
    added = qw.add_tasks([task], priority="P1", source="manual")
    assert len(added) == 1

    with open(queue_file) as f:
        content = f.read()

    # Should have exactly one provenance suffix (the new one), not the old one
    matches = re.findall(r'\(added: \d{4}-\d{2}-\d{2}, source: [^)]+\)', content)
    task_line = [l for l in content.split('\n') if 'TEST_DEDUP_PROV' in l][0]
    prov_count = len(re.findall(r'\(added:', task_line))
    assert prov_count == 1, f"Expected 1 provenance suffix, got {prov_count} in: {task_line}"


def test_legacy_prefix_stripped(queue_env):
    """Tasks with legacy [SOURCE DATE] prefix should have it stripped."""
    qw, queue_file = queue_env

    task = "[EVOLUTION 2026-04-01] **[TEST_LEGACY_STRIP]** Some legacy formatted task XYZ"
    added = qw.add_tasks([task], priority="P1", source="manual")
    assert len(added) == 1

    with open(queue_file) as f:
        content = f.read()

    # Legacy prefix should be gone
    assert "[EVOLUTION 2026-04-01]" not in content
    # New provenance suffix should exist
    assert "(added:" in content
    assert "source: manual)" in content

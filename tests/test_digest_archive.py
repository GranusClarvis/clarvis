"""Tests for digest_writer archive and provenance features."""

import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def digest_env(tmp_path, monkeypatch):
    """Set up isolated digest_writer environment."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "memory" / "cron").mkdir(parents=True)
    (workspace / "data").mkdir(parents=True)

    monkeypatch.setenv("CLARVIS_WORKSPACE", str(workspace))

    # Load module by file path (no __init__.py in scripts/)
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "digest_writer",
        os.path.join(os.path.dirname(__file__), "..", "scripts", "tools", "digest_writer.py"),
    )
    dw = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(dw)
    dw.WORKSPACE = str(workspace)
    dw.DIGEST_FILE = os.path.join(str(workspace), "memory", "cron", "digest.md")
    dw.DIGEST_STATE = os.path.join(str(workspace), "data", "digest_state.json")
    dw.DIGEST_ARCHIVE_DIR = os.path.join(str(workspace), "memory", "cron", "archive")

    return dw, workspace


def test_archive_creates_file(digest_env):
    """Archive should create dated file in archive dir."""
    dw, workspace = digest_env

    # Write a digest with enough content to archive
    digest_path = dw.DIGEST_FILE
    with open(digest_path, "w") as f:
        f.write("# Clarvis Daily Digest — 2026-04-17\n\n")
        f.write("Some content here that is long enough to pass the 100-byte threshold.\n")
        f.write("More content to ensure we meet the minimum size requirement.\n")

    dw._archive_digest("2026-04-17")

    archive_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2026-04-17.md")
    assert os.path.exists(archive_path)
    with open(archive_path) as f:
        content = f.read()
    assert "2026-04-17" in content


def test_archive_skips_small_files(digest_env):
    """Archive should not create file for tiny digests (header only)."""
    dw, workspace = digest_env

    digest_path = dw.DIGEST_FILE
    with open(digest_path, "w") as f:
        f.write("# Header\n")  # < 100 bytes

    dw._archive_digest("2026-04-17")
    archive_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2026-04-17.md")
    assert not os.path.exists(archive_path)


def test_archive_no_duplicate(digest_env):
    """Archive should not overwrite existing archive file."""
    dw, workspace = digest_env

    digest_path = dw.DIGEST_FILE
    with open(digest_path, "w") as f:
        f.write("# Clarvis Daily Digest — 2026-04-17\n\nOriginal content that is long enough.\n" * 3)

    dw._archive_digest("2026-04-17")

    # Modify digest and try again
    with open(digest_path, "w") as f:
        f.write("# Modified content\n\nThis should NOT overwrite the archive if it exists.\n" * 3)

    dw._archive_digest("2026-04-17")

    archive_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2026-04-17.md")
    with open(archive_path) as f:
        content = f.read()
    assert "Original content" in content


def test_archive_prunes_old_files(digest_env):
    """Archive should remove files older than retention period."""
    dw, workspace = digest_env
    dw.DIGEST_ARCHIVE_RETAIN_DAYS = 5  # short for testing

    os.makedirs(dw.DIGEST_ARCHIVE_DIR, exist_ok=True)

    # Create an old archive file
    old_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2020-01-01.md")
    with open(old_path, "w") as f:
        f.write("old data\n")

    # Create a recent archive file
    recent_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2026-04-17.md")
    with open(recent_path, "w") as f:
        f.write("recent data\n")

    # Trigger pruning via archive
    digest_path = dw.DIGEST_FILE
    with open(digest_path, "w") as f:
        f.write("# Digest\n\nContent long enough to pass threshold for archiving.\n" * 3)

    dw._archive_digest("2026-04-18")

    assert not os.path.exists(old_path), "Old archive should be pruned"
    assert os.path.exists(recent_path), "Recent archive should be kept"


def test_reset_triggers_archive(digest_env):
    """_reset_if_new_day should archive before resetting."""
    dw, workspace = digest_env

    # Write substantial content
    with open(dw.DIGEST_FILE, "w") as f:
        f.write("# Clarvis Daily Digest — 2026-04-17\n\nSubstantial content for archive test.\n" * 3)

    # Set state to yesterday
    state = {"last_reset": "2026-04-17", "entries_today": 3}
    dw._save_state(state)

    # Trigger reset (simulating new day)
    from unittest.mock import patch
    from datetime import datetime, timezone
    fake_now = datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc)
    with patch.object(dw, "datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        state = dw._reset_if_new_day(state)

    archive_path = os.path.join(dw.DIGEST_ARCHIVE_DIR, "digest-2026-04-17.md")
    assert os.path.exists(archive_path), "Archive should be created on day reset"


def test_section_emoji_has_research_and_sprint(digest_env):
    """SECTION_EMOJI should include research and sprint sources."""
    dw, _ = digest_env
    assert "research" in dw.SECTION_EMOJI
    assert "sprint" in dw.SECTION_EMOJI


def test_write_digest_with_new_sources(digest_env):
    """write_digest should accept research and sprint sources."""
    dw, workspace = digest_env

    # Initialize state
    state = {"last_reset": None, "entries_today": 0}
    dw._save_state(state)

    result = dw.write_digest("research", "Research session completed: topic X")
    assert result["written"]

    with open(dw.DIGEST_FILE) as f:
        content = f.read()
    assert "Research" in content

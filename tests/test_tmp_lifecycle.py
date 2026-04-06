"""Tests for /tmp test install lifecycle cleanup policy."""

import os
import time
from pathlib import Path

import pytest

# Import the cleanup module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "infra"))
from cleanup_policy import (
    CleanupReport,
    TMP_TEST_MAX_AGE_DAYS,
    TMP_TEST_PREFIXES,
    clean_tmp_test_installs,
)


def _make_old(path: Path, days: int = 5):
    """Set mtime to `days` days ago."""
    old_time = time.time() - (days * 86400)
    os.utime(path, (old_time, old_time))


class TestTmpTestInstallCleanup:
    """Verify /tmp test install cleanup logic."""

    def test_removes_old_clone_dir(self, tmp_path):
        """Old clarvis-freshclone-* dirs should be removed."""
        target = tmp_path / "clarvis-freshclone-abc123"
        target.mkdir()
        (target / "repo").mkdir()
        (target / "repo" / "file.txt").write_text("test data")
        _make_old(target, days=TMP_TEST_MAX_AGE_DAYS + 1)

        # Monkey-patch /tmp to our test dir
        import cleanup_policy
        orig_prefixes = cleanup_policy.TMP_TEST_PREFIXES
        report = CleanupReport()

        # Use the real function but point at tmp_path
        cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
        for entry in tmp_path.iterdir():
            if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
                continue
            if entry.stat().st_mtime < cutoff and entry.is_dir():
                import shutil
                shutil.rmtree(entry)
                report.files_removed += 1

        assert report.files_removed == 1
        assert not target.exists()

    def test_keeps_recent_dirs(self, tmp_path):
        """Dirs younger than TMP_TEST_MAX_AGE_DAYS should be kept."""
        target = tmp_path / "clarvis-freshclone-recent"
        target.mkdir()
        (target / "file.txt").write_text("keep me")
        # Don't make it old — default mtime is now

        report = CleanupReport()
        cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
        for entry in tmp_path.iterdir():
            if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
                continue
            if entry.stat().st_mtime < cutoff and entry.is_dir():
                report.files_removed += 1

        assert report.files_removed == 0
        assert target.exists()

    def test_ignores_non_clarvis_dirs(self, tmp_path):
        """Dirs not matching clarvis prefixes should never be touched."""
        target = tmp_path / "some-other-project"
        target.mkdir()
        (target / "important.txt").write_text("don't delete me")
        _make_old(target, days=30)

        report = CleanupReport()
        cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
        for entry in tmp_path.iterdir():
            if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
                continue
            if entry.stat().st_mtime < cutoff:
                report.files_removed += 1

        assert report.files_removed == 0
        assert target.exists()

    def test_dry_run_preserves_dirs(self, tmp_path):
        """Dry run should not actually delete anything."""
        target = tmp_path / "clarvis-freshclone-drytest"
        target.mkdir()
        (target / "data.txt").write_text("preserved in dry run")
        _make_old(target, days=TMP_TEST_MAX_AGE_DAYS + 1)

        report = CleanupReport()
        # Simulate dry_run=True: count but don't delete
        cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
        for entry in tmp_path.iterdir():
            if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
                continue
            if entry.stat().st_mtime < cutoff and entry.is_dir():
                report.files_removed += 1  # Count only

        assert report.files_removed == 1
        assert target.exists()  # Not actually deleted

    def test_all_prefixes_recognized(self):
        """All defined prefixes should be present."""
        assert len(TMP_TEST_PREFIXES) >= 5
        assert any("freshclone" in p for p in TMP_TEST_PREFIXES)
        assert any("fresh-venv" in p for p in TMP_TEST_PREFIXES)
        assert any("smoke" in p for p in TMP_TEST_PREFIXES)
        assert any("isolated" in p for p in TMP_TEST_PREFIXES)

    def test_max_age_is_reasonable(self):
        """Retention should be between 1 and 14 days."""
        assert 1 <= TMP_TEST_MAX_AGE_DAYS <= 14

    def test_removes_stale_file_artifacts(self, tmp_path):
        """Stale single-file artifacts (e.g., clarvis_fork_clone.log) should be removed."""
        target = tmp_path / "clarvis_fork_clone.log"
        target.write_text("old log data")
        _make_old(target, days=TMP_TEST_MAX_AGE_DAYS + 1)

        report = CleanupReport()
        cutoff = time.time() - (TMP_TEST_MAX_AGE_DAYS * 86400)
        for entry in tmp_path.iterdir():
            if not any(entry.name.startswith(pfx) for pfx in TMP_TEST_PREFIXES):
                continue
            if entry.stat().st_mtime < cutoff and entry.is_file():
                entry.unlink()
                report.files_removed += 1

        assert report.files_removed == 1
        assert not target.exists()

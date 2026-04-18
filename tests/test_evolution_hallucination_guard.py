"""Tests for evolution_hallucination_guard.py"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'evolution'))

from evolution_hallucination_guard import extract_paths, validate_paths, run


class TestExtractPaths:
    def test_script_paths(self):
        text = "Fix `scripts/tools/digest_writer.py` to handle edge cases"
        paths = extract_paths(text)
        assert "scripts/tools/digest_writer.py" in paths

    def test_clarvis_paths(self):
        text = "Update clarvis/brain/store.py with new logic"
        paths = extract_paths(text)
        assert "clarvis/brain/store.py" in paths

    def test_data_paths(self):
        text = "Check data/audit/traces/latest.json for staleness"
        paths = extract_paths(text)
        assert "data/audit/traces/latest.json" in paths

    def test_no_paths(self):
        text = "Improve the overall test coverage significantly"
        paths = extract_paths(text)
        assert paths == []

    def test_multiple_paths(self):
        text = "Wire scripts/foo.py to read from data/bar.json"
        paths = extract_paths(text)
        assert len(paths) == 2

    def test_absolute_path(self):
        text = "Check /home/agent/.openclaw/workspace/scripts/foo.py"
        paths = extract_paths(text)
        assert any("/home/agent" in p for p in paths)

    def test_trailing_punctuation_stripped(self):
        text = "Fix scripts/tools/digest_writer.py."
        paths = extract_paths(text)
        assert "scripts/tools/digest_writer.py" in paths


class TestValidatePaths:
    def test_existing_path(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "foo.py").write_text("x")
        results = validate_paths(["scripts/foo.py"], str(tmp_path))
        assert results[0]["exists"] is True

    def test_missing_path(self, tmp_path):
        results = validate_paths(["scripts/nonexistent.py"], str(tmp_path))
        assert results[0]["exists"] is False


class TestRun:
    def test_clean_queue(self, tmp_path):
        """Queue with valid paths produces no flags."""
        # Create the referenced file
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "real.py").write_text("x")

        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[TASK1]** Fix `scripts/real.py` to handle edge cases\n"
            "- [x] **[DONE]** Already completed\n"
        )
        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 0
        assert len(result["hallucinated"]) == 0

    def test_hallucinated_path_flagged(self, tmp_path):
        """Queue items referencing nonexistent files get [UNVERIFIED] tag."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[BAD]** Fix `scripts/nonexistent_file.py` completely\n"
        )
        # Create monitoring dir for log
        (tmp_path / "monitoring").mkdir(exist_ok=True)

        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 1
        assert len(result["hallucinated"]) == 1
        assert "scripts/nonexistent_file.py" in result["hallucinated"][0]["bad_paths"]

        # Verify the file was updated with [UNVERIFIED]
        content = queue.read_text()
        assert "[UNVERIFIED]" in content

    def test_already_flagged_skipped(self, tmp_path):
        """Items already tagged [UNVERIFIED] are not re-checked."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] [UNVERIFIED] **[BAD]** Fix `scripts/ghost.py` completely\n"
        )
        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 0

    def test_no_path_items_pass(self, tmp_path):
        """Items with no file references are not flagged."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[TASK]** Improve overall test coverage\n"
        )
        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 0
        assert result["paths_checked"] == 0

    def test_creation_context_skipped(self, tmp_path):
        """Tasks that say 'Create scripts/foo.py' are not flagged (file doesn't exist yet by design)."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[TASK]** Create `scripts/infra/restore_drill.sh` that restores the latest backup\n"
        )
        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 0

    def test_stale_path_context_skipped(self, tmp_path):
        """Tasks citing stale paths as the problem are not flagged."""
        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[FIX]** Fix stale script paths (`scripts/old.py`) in config\n"
        )
        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 0

    def test_mixed_good_and_bad(self, tmp_path):
        """Only items with bad paths are flagged; good ones left alone."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "real.py").write_text("x")

        queue = tmp_path / "QUEUE.md"
        queue.write_text(
            "# Queue\n\n"
            "- [ ] **[GOOD]** Fix `scripts/real.py` edge case\n"
            "- [ ] **[BAD]** Rewrite `scripts/fake_module.py` entirely\n"
        )
        (tmp_path / "monitoring").mkdir(exist_ok=True)

        result = run(queue_file=str(queue), workspace=str(tmp_path))
        assert result["flagged"] == 1
        content = queue.read_text()
        assert "[UNVERIFIED]" in content
        # Good item should NOT be flagged
        assert "- [ ] **[GOOD]**" in content

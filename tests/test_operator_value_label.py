#!/usr/bin/env python3
"""Tests for operator_value_label.py"""

import json
import os
import sys
import tempfile

import pytest

# Add scripts/tools to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "tools"))
import operator_value_label as ovl


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with expected directory structure."""
    audit_dir = tmp_path / "data" / "audit"
    audit_dir.mkdir(parents=True)
    digest_dir = tmp_path / "memory" / "cron"
    digest_dir.mkdir(parents=True)
    archive_dir = digest_dir / "archive"
    archive_dir.mkdir()
    queue_dir = tmp_path / "memory" / "evolution"
    queue_dir.mkdir(parents=True)

    # Write a sample digest
    digest = (
        "# Clarvis Daily Digest — 2026-04-18\n\n"
        "### ⚡ Autonomous — 01:06 UTC\n\n"
        'I executed evolution task: "[PHI_CROSS_LINK] cross-link". Result: success\n\n---\n\n'
        "### ⚡ Autonomous — 07:00 UTC\n\n"
        'I executed evolution task: "[SWO_SECURITY_AUDIT] audit". Result: success\n\n---\n\n'
        "### 🔬 Research — 10:00 UTC\n\n"
        'Researched: [RESEARCH_TRANSFORMERS] attention mechanisms. Result: success\n\n---\n\n'
    )
    (digest_dir / "digest.md").write_text(digest)

    # Write a sample queue archive
    archive = (
        "# Queue Archive\n"
        "- [x] [PHI_CROSS_LINK] cross-link (2026-04-18)\n"
        "- [x] [OLD_TASK] old (2026-04-10)\n"
    )
    (queue_dir / "QUEUE_ARCHIVE.md").write_text(archive)

    # Patch module paths
    ovl.LABELS_FILE = str(audit_dir / "operator_value_labels.jsonl")
    ovl.DIGEST_FILE = str(digest_dir / "digest.md")
    ovl.DIGEST_ARCHIVE_DIR = str(archive_dir)
    ovl.QUEUE_ARCHIVE = str(queue_dir / "QUEUE_ARCHIVE.md")
    ovl.WORKSPACE = str(tmp_path)

    yield tmp_path

    # Restore defaults (not critical since each test gets fresh fixture)


class TestRate:
    def test_rate_high(self, tmp_workspace, capsys):
        result = ovl.cmd_rate(["PHI_CROSS_LINK", "high"])
        assert result == 0
        out = capsys.readouterr().out
        assert "HIGH" in out
        assert "PHI_CROSS_LINK" in out

        # Verify JSONL written
        labels = ovl._read_labels()
        assert len(labels) == 1
        assert labels[0]["task_tag"] == "PHI_CROSS_LINK"
        assert labels[0]["label"] == "high"
        assert labels[0]["audit_trace_id"] is None
        assert labels[0]["note"] is None

    def test_rate_with_note(self, tmp_workspace, capsys):
        result = ovl.cmd_rate(["SWO_SECURITY_AUDIT", "low", "wasted", "tokens"])
        assert result == 0
        labels = ovl._read_labels()
        assert labels[0]["note"] == "wasted tokens"
        assert labels[0]["label"] == "low"

    def test_rate_invalid_label(self, tmp_workspace, capsys):
        result = ovl.cmd_rate(["SOME_TASK", "excellent"])
        assert result == 1
        out = capsys.readouterr().out
        assert "Invalid label" in out

    def test_rate_missing_args(self, tmp_workspace, capsys):
        result = ovl.cmd_rate(["SOME_TASK"])
        assert result == 1

    def test_rate_duplicate_appends(self, tmp_workspace, capsys):
        ovl.cmd_rate(["TASK_A", "high"])
        ovl.cmd_rate(["TASK_A", "low", "changed my mind"])
        labels = ovl._read_labels()
        assert len(labels) == 2  # both entries kept (latest wins in stats)


class TestList:
    def test_list_shows_unlabeled(self, tmp_workspace, capsys):
        result = ovl.cmd_list([])
        assert result == 0
        out = capsys.readouterr().out
        assert "PHI_CROSS_LINK" in out
        assert "SWO_SECURITY_AUDIT" in out

    def test_list_excludes_labeled(self, tmp_workspace, capsys):
        ovl.cmd_rate(["PHI_CROSS_LINK", "high"])
        capsys.readouterr()  # clear
        result = ovl.cmd_list([])
        out = capsys.readouterr().out
        assert "PHI_CROSS_LINK" not in out
        assert "SWO_SECURITY_AUDIT" in out


class TestStats:
    def test_stats_empty(self, tmp_workspace, capsys):
        result = ovl.cmd_stats([])
        assert result == 0
        assert "No labels" in capsys.readouterr().out

    def test_stats_with_data(self, tmp_workspace, capsys):
        ovl.cmd_rate(["TASK_A", "high"])
        ovl.cmd_rate(["TASK_B", "neutral"])
        ovl.cmd_rate(["TASK_C", "low"])
        capsys.readouterr()  # clear
        result = ovl.cmd_stats([])
        assert result == 0
        out = capsys.readouterr().out
        assert "3 tasks rated" in out
        assert "high" in out
        assert "neutral" in out
        assert "low" in out


class TestHistory:
    def test_history(self, tmp_workspace, capsys):
        ovl.cmd_rate(["T1", "high"])
        ovl.cmd_rate(["T2", "low", "bad"])
        capsys.readouterr()
        result = ovl.cmd_history([])
        assert result == 0
        out = capsys.readouterr().out
        assert "T1" in out
        assert "T2" in out
        assert "bad" in out


class TestUnlabeledSummary:
    def test_summary_returns_rating_block(self, tmp_workspace):
        result = ovl.get_unlabeled_summary(days=1, max_items=5)
        assert "RATE TODAY'S WORK" in result
        assert "/rate" in result

    def test_summary_empty_when_all_labeled(self, tmp_workspace):
        # Label all tasks from digest
        for tag in ovl._get_recent_task_tags(days=1):
            ovl.cmd_rate([tag, "neutral"])
        result = ovl.get_unlabeled_summary(days=1, max_items=5)
        assert result == ""

"""Regression test: research_to_queue disposition log deduplication.

Verifies that repeated scan/inject runs do NOT inflate the disposition log
with duplicate records for the same (paper_file, proposal, disposition).
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import _paths  # noqa: F401,E402
from research_to_queue import _dedup_key, _load_existing_keys, _log_dispositions


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    """Provide a temporary disposition log path."""
    log_path = str(tmp_path / "research_dispositions.jsonl")
    monkeypatch.setattr("research_to_queue.DISPOSITION_LOG", log_path)
    return log_path


def _make_entry(paper_file="paper_a.md", proposal="Implement X in brain.py", disposition="code_change"):
    return {
        "timestamp": "2026-03-16T00:00:00+00:00",
        "paper": "Paper A",
        "paper_file": paper_file,
        "proposal": proposal,
        "disposition": disposition,
        "reason": "test",
        "score": 0.5,
    }


class TestDedupKey:
    def test_same_inputs_same_key(self):
        e1 = _make_entry()
        e2 = _make_entry()
        assert _dedup_key(e1) == _dedup_key(e2)

    def test_whitespace_normalized(self):
        e1 = _make_entry(proposal="Implement   X  in   brain.py")
        e2 = _make_entry(proposal="Implement X in brain.py")
        assert _dedup_key(e1) == _dedup_key(e2)

    def test_case_normalized(self):
        e1 = _make_entry(proposal="Implement X in Brain.py")
        e2 = _make_entry(proposal="implement x in brain.py")
        assert _dedup_key(e1) == _dedup_key(e2)

    def test_different_paper_different_key(self):
        e1 = _make_entry(paper_file="paper_a.md")
        e2 = _make_entry(paper_file="paper_b.md")
        assert _dedup_key(e1) != _dedup_key(e2)

    def test_different_disposition_different_key(self):
        e1 = _make_entry(disposition="code_change")
        e2 = _make_entry(disposition="discard")
        assert _dedup_key(e1) != _dedup_key(e2)


class TestLogDispositionsDedup:
    def test_first_write_creates_all(self, tmp_log):
        entries = [_make_entry(paper_file=f"paper_{i}.md") for i in range(5)]
        count = _log_dispositions(entries)
        assert count == 5
        with open(tmp_log) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 5

    def test_second_identical_write_adds_nothing(self, tmp_log):
        entries = [_make_entry(paper_file=f"paper_{i}.md") for i in range(5)]
        _log_dispositions(entries)
        count = _log_dispositions(entries)
        assert count == 0
        with open(tmp_log) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 5

    def test_mixed_new_and_existing(self, tmp_log):
        first_batch = [_make_entry(paper_file=f"paper_{i}.md") for i in range(3)]
        _log_dispositions(first_batch)

        second_batch = [
            _make_entry(paper_file="paper_0.md"),  # dup
            _make_entry(paper_file="paper_3.md"),  # new
            _make_entry(paper_file="paper_1.md"),  # dup
        ]
        count = _log_dispositions(second_batch)
        assert count == 1
        with open(tmp_log) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 4

    def test_dedup_key_stored_in_record(self, tmp_log):
        entries = [_make_entry()]
        _log_dispositions(entries)
        with open(tmp_log) as f:
            rec = json.loads(f.readline())
        assert "dedup_key" in rec
        assert rec["dedup_key"] == _dedup_key(entries[0])

    def test_legacy_records_without_key_still_deduped(self, tmp_log):
        """Records written before the fix (no dedup_key field) are still matched."""
        legacy = _make_entry()
        # Write a legacy record (no dedup_key)
        with open(tmp_log, "w") as f:
            f.write(json.dumps(legacy, default=str) + "\n")

        # Now try to log the same entry via the new function
        count = _log_dispositions([_make_entry()])
        assert count == 0
        with open(tmp_log) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 1

    def test_empty_log_file(self, tmp_log):
        """Handles missing log file gracefully."""
        count = _log_dispositions([_make_entry()])
        assert count == 1

    def test_repeated_scan_simulation(self, tmp_log):
        """Simulate 5 monthly scans of the same papers — log should not grow."""
        papers = [_make_entry(paper_file=f"p{i}.md", proposal=f"Do thing {i}") for i in range(10)]
        _log_dispositions(papers)
        for _ in range(4):
            count = _log_dispositions(papers)
            assert count == 0

        with open(tmp_log) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 10  # exactly 10, not 50

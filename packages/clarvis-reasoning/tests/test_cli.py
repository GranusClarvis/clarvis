"""Tests for clarvis_reasoning CLI (__main__.py)."""

import sys

import pytest

from clarvis_reasoning.__main__ import main


class TestCLI:
    def test_no_args_exits(self):
        sys.argv = ["clarvis-reasoning"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_check_clean(self, capsys):
        sys.argv = ["clarvis-reasoning", "check",
                     "The database needs an index on the email column for faster lookups."]
        main()
        out = capsys.readouterr().out
        assert "No quality issues" in out

    def test_check_with_confidence(self, capsys):
        sys.argv = ["clarvis-reasoning", "check", "Short", "0.95"]
        main()
        out = capsys.readouterr().out
        assert "flags" in out.lower() or "issues" in out.lower() or "No quality" in out

    def test_check_missing_args(self):
        sys.argv = ["clarvis-reasoning", "check"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_coherence(self, capsys):
        sys.argv = ["clarvis-reasoning", "coherence",
                     "First thought about databases",
                     "Second thought about indexing"]
        main()
        out = capsys.readouterr().out
        assert "Coherence" in out

    def test_coherence_missing_args(self):
        sys.argv = ["clarvis-reasoning", "coherence", "only-one"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_demo(self, capsys):
        sys.argv = ["clarvis-reasoning", "demo"]
        main()
        out = capsys.readouterr().out
        assert "Demo" in out

    def test_unknown_command(self):
        sys.argv = ["clarvis-reasoning", "foobar"]
        with pytest.raises(SystemExit, match="1"):
            main()

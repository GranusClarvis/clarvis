"""Tests for clarvis_cost CLI (__main__.py)."""

import json
import os
import sys
import tempfile

import pytest

from clarvis_cost.__main__ import main


@pytest.fixture
def tmp_log(tmp_path):
    return str(tmp_path / "costs.jsonl")


class TestCLI:
    def test_no_args_exits(self):
        sys.argv = ["clarvis-cost"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_estimate(self, capsys):
        sys.argv = ["clarvis-cost", "estimate", "claude-opus-4-6", "1000", "500"]
        main()
        out = capsys.readouterr().out
        assert out.startswith("$")

    def test_tokens(self, capsys):
        sys.argv = ["clarvis-cost", "tokens", "Hello", "world"]
        main()
        out = capsys.readouterr().out
        assert "tokens" in out

    def test_log(self, capsys, tmp_log):
        sys.argv = ["clarvis-cost", "log", "test-model", "100", "50", "cli", tmp_log]
        main()
        out = capsys.readouterr().out
        assert "Logged" in out
        assert os.path.exists(tmp_log)

    def test_rollup(self, capsys, tmp_log):
        sys.argv = ["clarvis-cost", "rollup", "all", tmp_log]
        main()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "total_cost" in data

    def test_budget(self, capsys, tmp_log):
        sys.argv = ["clarvis-cost", "budget", "5.0", tmp_log]
        main()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "alert" in data

    def test_pricing_all(self, capsys):
        sys.argv = ["clarvis-cost", "pricing"]
        main()
        out = capsys.readouterr().out
        assert "claude" in out.lower()

    def test_pricing_specific(self, capsys):
        sys.argv = ["clarvis-cost", "pricing", "claude-opus-4-6"]
        main()
        out = capsys.readouterr().out
        assert "claude-opus-4-6" in out

    def test_pricing_unknown(self, capsys):
        sys.argv = ["clarvis-cost", "pricing", "nonexistent-model"]
        main()
        out = capsys.readouterr().out
        assert "Unknown" in out

    def test_demo(self, capsys):
        sys.argv = ["clarvis-cost", "demo"]
        main()
        out = capsys.readouterr().out
        assert "Demo" in out

    def test_unknown_command(self):
        sys.argv = ["clarvis-cost", "foobar"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_estimate_missing_args(self):
        sys.argv = ["clarvis-cost", "estimate", "model"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_budget_missing_args(self):
        sys.argv = ["clarvis-cost", "budget"]
        with pytest.raises(SystemExit, match="1"):
            main()

    def test_log_missing_args(self):
        sys.argv = ["clarvis-cost", "log", "model"]
        with pytest.raises(SystemExit, match="1"):
            main()

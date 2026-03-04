"""Tests for the unified clarvis CLI.

Uses typer.testing.CliRunner to exercise --help and at least one
real invocation per subcommand group (brain, bench, heartbeat, queue).
"""

import json
import re

import pytest
from typer.testing import CliRunner

from clarvis.cli import app, _register_subcommands

# Register subcommands once for the test session
_register_subcommands()

runner = CliRunner()


# ── --help smoke tests ────────────────────────────────────────────────

class TestHelp:
    """Every subcommand group must render --help cleanly."""

    def test_root_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "brain" in result.output
        assert "bench" in result.output
        assert "heartbeat" in result.output
        assert "queue" in result.output

    def test_brain_help(self):
        result = runner.invoke(app, ["brain", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output
        assert "stats" in result.output

    def test_bench_help(self):
        result = runner.invoke(app, ["bench", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "pi" in result.output

    def test_heartbeat_help(self):
        result = runner.invoke(app, ["heartbeat", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "gate" in result.output

    def test_queue_help(self):
        result = runner.invoke(app, ["queue", "--help"])
        assert result.exit_code == 0
        assert "next" in result.output
        assert "status" in result.output


# ── Real invocations ──────────────────────────────────────────────────

class TestBrainInvocation:
    """At least one real brain command must work."""

    def test_brain_stats(self):
        result = runner.invoke(app, ["brain", "stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_memories" in data
        assert "collections" in data
        assert isinstance(data["total_memories"], int)
        assert data["total_memories"] > 0


class TestBenchInvocation:
    """At least one real bench command must work."""

    def test_bench_pi(self):
        result = runner.invoke(app, ["bench", "pi"])
        assert result.exit_code == 0
        assert "PI:" in result.output


class TestHeartbeatInvocation:
    """At least one real heartbeat command must work."""

    def test_heartbeat_gate(self):
        result = runner.invoke(app, ["heartbeat", "gate"])
        # Gate may return 0 (WAKE) or 1 (SKIP) — both are valid
        assert result.exit_code in (0, 1)
        # First line of output should be valid JSON with a decision key
        first_line = result.output.strip().splitlines()[0]
        data = json.loads(first_line)
        assert "decision" in data


class TestQueueInvocation:
    """At least one real queue command must work."""

    def test_queue_status(self):
        result = runner.invoke(app, ["queue", "status"])
        assert result.exit_code == 0
        assert "pending" in result.output

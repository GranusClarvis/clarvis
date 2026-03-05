"""CLI smoke tests — verify Typer app structure without running against live brain."""

import pytest


def test_cli_app_importable():
    """Root CLI app imports without error."""
    from clarvis.cli import app
    assert app is not None
    assert app.info.name == "clarvis"


def test_cli_subcommands_registered():
    """All expected subcommands register cleanly."""
    from clarvis.cli import app, _register_subcommands
    _register_subcommands()

    # Typer stores sub-apps in registered_groups
    group_names = [g.typer_instance.info.name or g.name for g in app.registered_groups]
    expected = {"brain", "bench", "cron", "heartbeat", "queue"}
    assert expected.issubset(set(group_names)), (
        f"Missing subcommands: {expected - set(group_names)}"
    )


def test_cli_brain_subcommand_importable():
    """Brain CLI module imports cleanly."""
    from clarvis.cli_brain import app as brain_app
    assert brain_app is not None


def test_cli_bench_subcommand_importable():
    """Bench CLI module imports cleanly."""
    from clarvis.cli_bench import app as bench_app
    assert bench_app is not None


def test_cli_queue_subcommand_importable():
    """Queue CLI module imports cleanly."""
    from clarvis.cli_queue import app as queue_app
    assert queue_app is not None

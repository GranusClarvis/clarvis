"""clarvis maintenance — Periodic hygiene and lifecycle commands.

Canonical CLI entrypoints for scripts that were previously invoked
directly from crontab as ``python3 scripts/X.py``.
"""

import os
import sys
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")


def _ensure_scripts_path():
    """Add scripts/ to sys.path so legacy imports resolve."""
    scripts = os.path.join(WORKSPACE, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


# --- brain-hygiene -----------------------------------------------------------

@app.command("brain-hygiene")
def brain_hygiene(
    mode: str = typer.Argument("run", help="run | snapshot | check"),
):
    """Weekly brain hygiene — backfill, verify, optimize, snapshot.

    Replaces: python3 scripts/brain_hygiene.py <mode>
    """
    _ensure_scripts_path()
    import brain_hygiene as bh

    if mode == "run":
        bh.cmd_run()
    elif mode == "snapshot":
        bh.cmd_snapshot()
    elif mode == "check":
        bh.cmd_check()
    else:
        typer.echo(f"Unknown mode: {mode}. Use run | snapshot | check.")
        raise typer.Exit(1)


# --- goal-hygiene -------------------------------------------------------------

@app.command("goal-hygiene")
def goal_hygiene(
    mode: str = typer.Argument("clean", help="audit | deprecate | archive | clean | stats | dry-run"),
):
    """Weekly goal hygiene — audit, deprecate stale, archive completed.

    Replaces: python3 scripts/goal_hygiene.py <mode>
    """
    _ensure_scripts_path()
    import goal_hygiene as gh

    dispatch = {
        "audit": gh.audit_goals,
        "deprecate": gh.deprecate_goals,
        "archive": gh.archive_goals,
        "clean": gh.clean,
        "stats": gh.show_stats,
    }
    if mode == "dry-run":
        print("=== Dry Run: Deprecation ===")
        gh.deprecate_goals(dry_run=True)
        print("\n=== Dry Run: Archival ===")
        gh.archive_goals(dry_run=True)
    elif mode in dispatch:
        dispatch[mode]()
    else:
        typer.echo(f"Unknown mode: {mode}. Use audit | deprecate | archive | clean | stats | dry-run.")
        raise typer.Exit(1)


# --- data-lifecycle -----------------------------------------------------------

@app.command("data-lifecycle")
def data_lifecycle(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without making changes"),
    verbose: bool = typer.Option(False, "--verbose", help="Show skipped files"),
):
    """Data lifecycle — archive chains, rotate sessions, clean old archives.

    Replaces: python3 scripts/data_lifecycle.py [--dry-run] [--verbose]
    """
    _ensure_scripts_path()
    # Inject args before importing (data_lifecycle uses argparse in main())
    orig_argv = sys.argv[:]
    sys.argv = ["data_lifecycle"]
    if dry_run:
        sys.argv.append("--dry-run")
    if verbose:
        sys.argv.append("--verbose")
    try:
        import data_lifecycle as dl
        dl.main()
    finally:
        sys.argv = orig_argv


# --- graph-compaction ---------------------------------------------------------

@app.command("graph-compaction")
def graph_compaction(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
):
    """Graph compaction — orphan removal, dedup, edge injection.

    Replaces: python3 scripts/graph_compaction.py [--dry-run]
    """
    _ensure_scripts_path()
    import graph_compaction as gc

    if dry_run:
        print("=== DRY RUN (no changes) ===\n")
    gc.run_compaction(dry_run=dry_run)

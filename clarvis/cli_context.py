"""Clarvis context CLI — garbage collection, compression, brief generation."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def gc(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without doing it."),
):
    """Archive old completed tasks and rotate logs."""
    import json
    import sys
    import os
    sys.path.insert(0, os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "scripts"))
    from context_compressor import gc as run_gc

    result = run_gc(dry_run=dry_run)
    typer.echo(json.dumps(result, indent=2))

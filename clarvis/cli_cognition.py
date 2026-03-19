"""Clarvis cognition CLI — context relevance refresh and diagnostics."""

import typer

app = typer.Typer(no_args_is_help=True)
cr_app = typer.Typer(no_args_is_help=True, help="Context relevance tools.")
app.add_typer(cr_app, name="context-relevance")


@cr_app.command()
def refresh(
    days: int = typer.Option(14, help="Lookback window in days."),
    recency_boost: int = typer.Option(5, help="Recency boost window (episodes)."),
    min_episodes: int = typer.Option(10, help="Minimum episodes required."),
):
    """Refresh section importance weights from recent episode data."""
    import json
    from clarvis.cognition.context_relevance import refresh_weights

    result = refresh_weights(days=days, recency_boost=recency_boost,
                             min_episodes=min_episodes)
    typer.echo(json.dumps(result, indent=2))
    if result.get("status") == "ok":
        raise typer.Exit(0)
    else:
        raise typer.Exit(1)


@cr_app.command()
def aggregate(
    days: int = typer.Option(7, help="Lookback window in days."),
):
    """Aggregate context relevance scores from recent episodes."""
    import json
    from clarvis.cognition.context_relevance import aggregate_relevance

    result = aggregate_relevance(days=days)
    typer.echo(json.dumps(result, indent=2))


@cr_app.command()
def show():
    """Show current section importance weights."""
    import json
    from clarvis.cognition.context_relevance import _SECTION_IMPORTANCE, WEIGHTS_FILE
    import os

    source = "disk" if os.path.exists(WEIGHTS_FILE) else "hardcoded"
    typer.echo(f"Source: {source}")
    if os.path.exists(WEIGHTS_FILE):
        typer.echo(f"File: {WEIGHTS_FILE}")
    for name, weight in sorted(_SECTION_IMPORTANCE.items(), key=lambda x: -x[1]):
        typer.echo(f"  {name:25s} {weight:.4f}")

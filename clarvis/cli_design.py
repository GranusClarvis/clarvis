"""CLI subcommand: clarvis design — Claude Design bridge operations."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def pack(
    project: str = typer.Option(..., "--project", "-p", help="Project profile name"),
    task: str = typer.Option(..., "--task", "-t", help="Design task description"),
):
    """Generate a handoff pack for a Claude Design session."""
    from clarvis.context.design_bridge import generate_pack
    print(generate_pack(project, task))


@app.command()
def decide(
    task: str = typer.Option(..., "--task", "-t", help="Task description to classify"),
):
    """Recommend: Claude Design, code-first, or pixel-art tool."""
    from clarvis.context.design_bridge import decide as _decide
    result = _decide(task)
    print(f"Recommendation: {result['recommendation']}")
    print(f"Reason: {result['reason']}")
    print(f"Scores: design={result['scores']['design']}, code={result['scores']['code']}, pixel_art={result['scores']['pixel_art']}")


@app.command()
def ingest(
    export: str = typer.Option(..., "--export", "-e", help="Path to Design export file"),
    project: str = typer.Option(..., "--project", "-p", help="Project profile name"),
):
    """Process a Claude Design export into implementation specs."""
    import json
    from clarvis.context.design_bridge import ingest_export
    result = ingest_export(export, project)
    print(json.dumps(result, indent=2))


@app.command()
def projects():
    """List available project design profiles."""
    from clarvis.context.design_bridge import get_profile, list_projects
    for p in list_projects():
        profile = get_profile(p)
        print(f"  {p:12s} — {profile.get('name', '?')} ({profile.get('stack', 'unknown')[:50]})")


@app.command()
def profile(
    project: str = typer.Option(..., "--project", "-p", help="Project profile name"),
):
    """Show full design profile for a project."""
    import json
    from clarvis.context.design_bridge import get_profile
    p = get_profile(project)
    if p:
        print(json.dumps(p, indent=2))
    else:
        print(f"No profile for '{project}'")
        raise typer.Exit(1)

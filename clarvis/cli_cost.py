"""clarvis cost — cost tracking and budget monitoring.

Delegates to scripts/cost_tracker.py and scripts/budget_alert.py.
"""

import json
import sys

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = "/home/agent/.openclaw/workspace"


def _get_tracker():
    """Lazy-import CostTracker."""
    import os
    sys.path.insert(0, f"{WORKSPACE}/packages/clarvis-cost")
    from clarvis_cost.core import CostTracker
    cost_log = os.path.join(WORKSPACE, "data", "costs.jsonl")
    return CostTracker(cost_log)


@app.command()
def daily():
    """Today's cost report from local log."""
    tracker = _get_tracker()
    rollup = tracker.rollup("day")
    typer.echo(f"=== Daily Cost Report ===")
    typer.echo(f"Total: ${rollup['total_cost']:.4f}")
    typer.echo(f"Calls: {rollup['call_count']}")
    typer.echo(f"Tokens: {rollup['total_input_tokens']:,} in / {rollup['total_output_tokens']:,} out")
    if rollup["by_model"]:
        typer.echo("\nBy model:")
        for m, d in sorted(rollup["by_model"].items(), key=lambda x: -x[1]["cost"]):
            typer.echo(f"  {m}: ${d['cost']:.4f} ({d['count']} calls)")
    if rollup["by_source"]:
        typer.echo("\nBy source:")
        for s, d in sorted(rollup["by_source"].items(), key=lambda x: -x[1]["cost"]):
            typer.echo(f"  {s}: ${d['cost']:.4f} ({d['count']} calls)")


@app.command()
def weekly():
    """This week's cost report from local log."""
    tracker = _get_tracker()
    rollup = tracker.rollup("week")
    typer.echo(f"=== Weekly Cost Report ===")
    typer.echo(f"Total: ${rollup['total_cost']:.4f}")
    typer.echo(f"Calls: {rollup['call_count']}")
    typer.echo(f"Tokens: {rollup['total_input_tokens']:,} in / {rollup['total_output_tokens']:,} out")
    if rollup["by_model"]:
        typer.echo("\nBy model:")
        for m, d in sorted(rollup["by_model"].items(), key=lambda x: -x[1]["cost"]):
            typer.echo(f"  {m}: ${d['cost']:.4f} ({d['count']} calls)")


@app.command()
def budget(
    limit: float = typer.Argument(5.0, help="Daily budget limit in USD"),
):
    """Check today's spend against daily budget."""
    tracker = _get_tracker()
    b = tracker.budget_check(daily_budget=limit)
    typer.echo(f"Today: ${b['today_cost']:.4f} / ${b['daily_budget']:.2f}")
    typer.echo(f"Used: {b['pct_used']:.1f}%")
    typer.echo(f"Remaining: ${b['remaining']:.4f}")
    typer.echo(f"Status: {b['alert'].upper()}")


@app.command()
def realtime():
    """Real costs from OpenRouter API."""
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    from cost_api import fetch_usage, format_usage
    usage = fetch_usage()
    typer.echo(format_usage(usage))


@app.command()
def summary():
    """One-line cost summary for digest integration."""
    tracker = _get_tracker()
    b = tracker.budget_check(daily_budget=5.0)
    rollup = tracker.rollup("day")
    models = ", ".join(f"{m}:{d['count']}" for m, d in rollup.get("by_model", {}).items())
    typer.echo(
        f"Cost today: ${b['today_cost']:.4f}/{b['daily_budget']:.2f} "
        f"({b['pct_used']:.0f}% used, {rollup['call_count']} calls) [{models}]"
    )


@app.command()
def trend(days: int = typer.Argument(7, help="Number of days to show")):
    """Daily cost trend over N days."""
    tracker = _get_tracker()
    t = tracker.daily_trend(days)
    typer.echo(f"=== {days}-Day Cost Trend ===")
    for day in t:
        bar = "#" * min(int(day["cost"] * 20), 40)
        typer.echo(f"  {day['date']}: ${day['cost']:.4f}  {day['calls']}calls  {bar}")

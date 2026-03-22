"""clarvis mode — runtime mode control-plane CLI."""

import json

import typer

from clarvis.runtime.mode import (
    ModeState,
    apply_pending_mode,
    count_active_tasks,
    mode_policies,
    normalize_mode,
    read_mode_history,
    read_mode_state,
    set_mode,
    VALID_MODES,
)

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def _validate_mode(mode: str) -> str:
    """Normalize and validate a mode string, exiting with a clear error if invalid."""
    try:
        return normalize_mode(mode)
    except ValueError:
        valid = ", ".join(sorted(VALID_MODES))
        typer.echo(f"Error: unknown mode '{mode}'. Valid modes: {valid}", err=True)
        raise typer.Exit(1)


def _state_payload(state: ModeState) -> dict:
    return {
        "mode": state.mode,
        "previous_mode": state.previous_mode,
        "switched_at": state.switched_at,
        "reason": state.reason,
        "pending_mode": state.pending_mode,
        "pending_reason": state.pending_reason,
        "pending_since": state.pending_since,
        "active_tasks": count_active_tasks(),
    }


@app.command()
def show(json_output: bool = typer.Option(False, "--json", help="Print JSON output.")):
    """Show current runtime mode and pending switch state."""
    state = read_mode_state()
    payload = _state_payload(state)
    payload["policies"] = mode_policies(state.mode)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"Mode: {payload['mode']}")
    if payload["pending_mode"]:
        typer.echo(
            f"Pending: {payload['pending_mode']} "
            f"(reason: {payload['pending_reason'] or 'none'})"
        )
    typer.echo(f"Active tasks: {payload['active_tasks']}")
    typer.echo(f"Switched at: {payload['switched_at'] or 'n/a'}")
    if payload["reason"]:
        typer.echo(f"Reason: {payload['reason']}")


@app.command("set")
def set_mode_cmd(
    mode: str = typer.Argument(..., help="Target mode: ge | architecture | passive"),
    reason: str = typer.Option("", "--reason", "-r", help="Why this mode is being set."),
    immediate: bool = typer.Option(
        False,
        "--immediate",
        help="Switch immediately even if there are active tasks (default: defer).",
    ),
):
    """Set runtime mode (deferred if active tasks exist by default)."""
    _validate_mode(mode)
    result = set_mode(mode, reason=reason, defer_if_active=not immediate)
    typer.echo(json.dumps(result, indent=2))


@app.command("apply-pending")
def apply_pending():
    """Apply pending mode switch when no active tasks remain."""
    result = apply_pending_mode()
    typer.echo(json.dumps(result, indent=2))


@app.command()
def explain(mode: str = typer.Argument(..., help="Mode to explain: ge | architecture | passive")):
    """Explain mode policy behavior."""
    _validate_mode(mode)
    policies = mode_policies(mode)
    typer.echo(json.dumps(policies, indent=2))


@app.command()
def history(limit: int = typer.Option(20, "--limit", "-n", min=1, max=200)):
    """Show recent mode switch history."""
    events = read_mode_history(limit=limit)
    if not events:
        typer.echo("No mode history yet.")
        raise typer.Exit(0)
    typer.echo(json.dumps(events, indent=2))

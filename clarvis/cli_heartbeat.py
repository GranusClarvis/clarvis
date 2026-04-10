"""clarvis heartbeat — heartbeat pipeline operations.

The heartbeat pipeline is:
  1. heartbeat gate — zero-LLM pre-check
  2. heartbeat preflight — attention scoring, task selection, context
  3. Claude Code executes selected task
  4. heartbeat postflight — episode encoding, confidence, brain storage

Subcommands:
  gate       — run gate only (exit 0=WAKE, 1=SKIP)
  preflight  — run preflight only, print JSON
  postflight — record outcome from exit-code + output-file + preflight-file
  run        — gate + preflight together (diagnostic)
"""

import json
import os
import sys
from pathlib import Path

import typer

from clarvis._script_loader import load as _load_script

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))


@app.command()
def run(dry_run: bool = typer.Option(False, "--dry-run", help="Run gate + preflight without spawning Claude Code.")):
    """Run heartbeat gate check, then preflight task selection.

    Without --dry-run: prints the selected task and context (does NOT spawn Claude Code —
    that requires the full cron_autonomous.sh pipeline with locks and timeouts).

    With --dry-run: same but explicitly labeled as dry run.
    """
    # Step 1: Gate (use spine module)
    print("=== Heartbeat Gate ===")
    try:
        from clarvis.heartbeat.gate import run_gate
        decision, output = run_gate()
        print(f"Decision: {decision.upper()}")
        if decision == "skip":
            print(f"Reason: {output.get('reason', 'unknown')}")
            return
    except Exception as e:
        print(f"Gate error (proceeding anyway): {e}")

    # Step 2: Preflight (loaded via importlib from scripts/pipeline/)
    print("\n=== Heartbeat Preflight ===")
    try:
        heartbeat_preflight = _load_script("heartbeat_preflight", "pipeline")
        preflight_result = heartbeat_preflight.run_preflight()
        task = preflight_result.get("selected_task", "No task selected")
        print(f"Selected task: {task}")
        if "context" in preflight_result:
            ctx = preflight_result["context"]
            if isinstance(ctx, str):
                print(f"Context length: {len(ctx)} chars")
            elif isinstance(ctx, dict):
                print(f"Context keys: {list(ctx.keys())}")
    except Exception as e:
        print(f"Preflight error: {e}")

    if dry_run:
        print("\n[dry-run] Would spawn Claude Code here. Exiting.")
    else:
        print("\n[info] To execute the full heartbeat with Claude Code spawning,")
        print("       use: scripts/cron_autonomous.sh")


@app.command()
def gate():
    """Run only the heartbeat gate (zero-LLM pre-check)."""
    try:
        from clarvis.heartbeat.gate import run_gate
        decision, output = run_gate()
        print(json.dumps(output, default=str))
        if decision == "skip":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        print(f"Gate error: {e}")
        raise typer.Exit(1)


@app.command()
def preflight(
    dry_run: bool = typer.Option(False, "--dry-run", help="Label output as dry run."),
    output_file: str = typer.Option(None, "--output", "-o", help="Write JSON result to file instead of stdout."),
):
    """Run preflight only (attention scoring, task selection, context).

    Prints the full preflight result as JSON. Useful for diagnostics and
    for piping into postflight after manual execution.
    """
    try:
        heartbeat_preflight = _load_script("heartbeat_preflight", "pipeline")
        result = heartbeat_preflight.run_preflight(dry_run=dry_run)
        json_out = json.dumps(result, indent=2, default=str)
        if output_file:
            Path(output_file).write_text(json_out)
            print(f"Preflight result written to {output_file}")
        else:
            print(json_out)
    except Exception as e:
        print(f"Preflight error: {e}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def postflight(
    exit_code: int = typer.Argument(..., help="Exit code from the executor (0=success, 124=timeout)."),
    output_file: str = typer.Argument(..., help="Path to the task output file."),
    preflight_file: str = typer.Argument(..., help="Path to the preflight JSON file (from `heartbeat preflight -o`)."),
    duration: int = typer.Option(0, "--duration", "-d", help="Task duration in seconds."),
):
    """Run postflight only (episode encoding, confidence, brain storage).

    Accepts the executor exit code, output file, and preflight JSON file.
    Typically used after manual task execution:

        clarvis heartbeat preflight -o /tmp/pf.json
        # ... execute task, producing /tmp/output.txt ...
        clarvis heartbeat postflight 0 /tmp/output.txt /tmp/pf.json
    """
    # Load preflight data
    pf_path = Path(preflight_file)
    if not pf_path.exists():
        print(f"Preflight file not found: {preflight_file}", file=sys.stderr)
        raise typer.Exit(1)
    try:
        preflight_data = json.loads(pf_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to read preflight file: {e}", file=sys.stderr)
        raise typer.Exit(1)

    out_path = Path(output_file)
    if not out_path.exists():
        print(f"Output file not found: {output_file}", file=sys.stderr)
        raise typer.Exit(1)

    try:
        heartbeat_postflight = _load_script("heartbeat_postflight", "pipeline")
        heartbeat_postflight.run_postflight(
            exit_code=exit_code,
            output_file=output_file,
            preflight_data=preflight_data,
            task_duration=duration,
        )
        print(f"Postflight complete (exit_code={exit_code}, duration={duration}s)")
    except Exception as e:
        print(f"Postflight error: {e}", file=sys.stderr)
        raise typer.Exit(1)

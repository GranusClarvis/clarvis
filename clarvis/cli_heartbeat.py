"""clarvis heartbeat — heartbeat pipeline operations.

The heartbeat pipeline is:
  1. heartbeat gate — zero-LLM pre-check
  2. heartbeat preflight — attention scoring, task selection, context
  3. Claude Code executes selected task
  4. heartbeat postflight — episode encoding, confidence, brain storage

This CLI wraps the gate + preflight for diagnostics.
Full heartbeat execution still happens via cron_autonomous.sh (spawns Claude Code).
"""

import json
import sys

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = "/home/agent/.openclaw/workspace"


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

    # Step 2: Preflight (still uses scripts/ — heavy cognitive imports)
    print("\n=== Heartbeat Preflight ===")
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    try:
        import heartbeat_preflight
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
    except ImportError:
        # Fallback to scripts/ if spine not available
        sys.path.insert(0, f"{WORKSPACE}/scripts")
        import heartbeat_gate
        result = heartbeat_gate.run_gate()
        print(json.dumps(result, default=str))
    except typer.Exit:
        raise
    except Exception as e:
        print(f"Gate error: {e}")
        raise typer.Exit(1)

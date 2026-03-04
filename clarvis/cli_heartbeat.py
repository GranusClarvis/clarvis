"""clarvis heartbeat — heartbeat pipeline operations.

The heartbeat pipeline is:
  1. heartbeat_gate.py — zero-LLM pre-check
  2. heartbeat_preflight.py — attention scoring, task selection, context
  3. Claude Code executes selected task
  4. heartbeat_postflight.py — episode encoding, confidence, brain storage

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
    sys.path.insert(0, f"{WORKSPACE}/scripts")

    # Step 1: Gate
    print("=== Heartbeat Gate ===")
    try:
        import heartbeat_gate
        gate_result = heartbeat_gate.run_gate()
        decision = gate_result.get("decision", "UNKNOWN")
        print(f"Decision: {decision}")
        if decision == "SKIP":
            print(f"Reason: {gate_result.get('reason', 'unknown')}")
            return
    except Exception as e:
        print(f"Gate error (proceeding anyway): {e}")

    # Step 2: Preflight
    print("\n=== Heartbeat Preflight ===")
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
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    try:
        import heartbeat_gate
        result = heartbeat_gate.run_gate()
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"Gate error: {e}")
        raise typer.Exit(1)

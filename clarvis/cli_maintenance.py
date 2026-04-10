"""clarvis maintenance — Periodic hygiene and lifecycle commands.

Canonical CLI entrypoints for scripts that were previously invoked
directly from crontab as ``python3 scripts/X.py``.
"""

import os
import sys
from typing import Optional

import typer

from clarvis._script_loader import load as _load_script

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))


# --- brain-hygiene -----------------------------------------------------------

@app.command("brain-hygiene")
def brain_hygiene(
    mode: str = typer.Argument("run", help="run | snapshot | check"),
):
    """Weekly brain hygiene — backfill, verify, optimize, snapshot.

    Replaces: python3 scripts/brain_hygiene.py <mode>
    """
    bh = _load_script("brain_hygiene", "brain_mem")

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
    gh = _load_script("goal_hygiene", "hooks")

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
    # Inject args before loading (data_lifecycle uses argparse in main())
    orig_argv = sys.argv[:]
    sys.argv = ["data_lifecycle"]
    if dry_run:
        sys.argv.append("--dry-run")
    if verbose:
        sys.argv.append("--verbose")
    try:
        dl = _load_script("data_lifecycle", "infra")
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
    gc = _load_script("graph_compaction", "brain_mem")

    if dry_run:
        print("=== DRY RUN (no changes) ===\n")
    gc.run_compaction(dry_run=dry_run)


# --- dream -------------------------------------------------------------------

@app.command("dream")
def dream_cmd(
    mode: str = typer.Argument("sleep", help="dream | rethink | sleep | stats | insights"),
    n: int = typer.Argument(10, help="Number of episodes (for dream/rethink/sleep)"),
):
    """Counterfactual dreaming engine — mental simulation of alternative outcomes.

    Replaces: python3 scripts/dream_engine.py <mode> [n]
    """
    import json as _json
    de = _load_script("dream_engine", "cognition")

    if mode == "dream":
        result = de.dream(n)
        print(_json.dumps(result, indent=2))
    elif mode == "rethink":
        result = de.rethink_memory(n)
        print(_json.dumps(result, indent=2))
    elif mode == "sleep":
        print("=== SLEEP CYCLE: Phase 1 — Counterfactual Dreaming ===")
        dream_result = de.dream(n)
        print("\n=== SLEEP CYCLE: Phase 2 — Rethink Memory ===")
        rethink_result = de.rethink_memory(n * 2)
        print("\n=== SLEEP CYCLE COMPLETE ===")
        print(f"  Dreams: {dream_result.get('insights_generated', 0)} insights")
        print(f"  Rethink: {rethink_result.get('learnings', 0)} learned patterns")
    elif mode == "stats":
        stats = de.get_stats()
        print(_json.dumps(stats, indent=2))
    elif mode == "insights":
        insights = de.list_insights()
        if not insights:
            print("No dream insights found yet.")
        else:
            for ins in insights:
                print(f"  [{ins['created']}] (imp={ins['importance']:.2f}) {ins['text']}")
    else:
        typer.echo(f"Unknown mode: {mode}. Use dream | rethink | sleep | stats | insights.")
        raise typer.Exit(1)


# --- status-json --------------------------------------------------------------

@app.command("status-json")
def status_json():
    """Generate public status.json snapshot for dashboards.

    Replaces: python3 scripts/generate_status_json.py
    """
    gs = _load_script("generate_status_json", "infra")

    gs.main()


# --- brief-benchmark ----------------------------------------------------------

@app.command("brief-benchmark")
def brief_benchmark(
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without updating report files"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Brief quality benchmark — measures context brief quality.

    Replaces: python3 scripts/brief_benchmark.py [--dry-run] [--json]
    """
    import json as _json
    bb = _load_script("brief_benchmark", "metrics")

    result = bb.run_benchmark(dry_run=dry_run)

    if json_output:
        print(_json.dumps(result, indent=2))
    else:
        if "error" in result:
            typer.echo(f"ERROR: {result['error']}")
            raise typer.Exit(1)

        print(f"Brief Benchmark: {result['tasks_scored']}/{result['tasks_total']} tasks scored")
        print(f"  Overall:  {result['mean_overall']:.3f}")
        print(f"  Tokens:   {result['mean_token_coverage']:.3f}")
        print(f"  Sections: {result['mean_section_coverage']:.3f}")
        print(f"  Jaccard:  {result['mean_jaccard']:.3f}")
        print(f"  ROUGE-L:  {result['mean_rouge_l']:.3f}")
        print(f"  By category: {result['by_category']}")
        print(f"  By tier:     {result['by_tier']}")
        print(f"  Avg brief:   {result['avg_brief_bytes']} bytes")

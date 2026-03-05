"""clarvis bench — performance benchmarks.

Delegates to scripts/performance_benchmark.py for actual measurement.
"""

import json
import sys

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = "/home/agent/.openclaw/workspace"


def _get_benchmark():
    """Lazy-import performance_benchmark module."""
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    import performance_benchmark
    return performance_benchmark


def _get_retrieval_benchmark():
    """Lazy-import retrieval_benchmark module."""
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    import retrieval_benchmark
    return retrieval_benchmark


@app.command()
def run():
    """Full benchmark — all 8 dimensions, record to history."""
    pb = _get_benchmark()
    report = pb.record()
    pb.print_report(report)
    print(f"\nRecorded to {pb.METRICS_FILE}")
    print(f"Appended to {pb.HISTORY_FILE}")
    alerts = report.get("_alerts", [])
    if alerts:
        print(f"Self-optimization: {len(alerts)} alert(s), "
              f"{report.get('_optimization_tasks_pushed', 0)} task(s) pushed")


@app.command()
def quick():
    """Quick benchmark — subset of dimensions, JSON output."""
    pb = _get_benchmark()
    report = pb.run_quick_benchmark()
    print(json.dumps(report, indent=2))


@app.command()
def pi(fresh: bool = typer.Option(False, "--fresh", help="Recompute PI (slow)")):
    """Print Performance Index score (reads cached value by default)."""
    import os
    pb = _get_benchmark()

    if not fresh and os.path.exists(pb.METRICS_FILE):
        try:
            with open(pb.METRICS_FILE) as f:
                stored = json.load(f)
            pi_data = stored.get("pi", {})
            pi_val = pi_data.get("pi", 0)
            interp = pi_data.get("interpretation", "")
            ts = stored.get("timestamp", "?")[:19]
            print(f"PI: {pi_val:.4f} — {interp}")
            print(f"  Last recorded: {ts}")
            return
        except Exception:
            pass

    # Fallback: quick benchmark
    report = pb.run_quick_benchmark()
    pi_data = report.get("pi_estimate", {})
    pi_val = pi_data.get("pi", 0) if isinstance(pi_data, dict) else 0
    interp = pi_data.get("interpretation", "") if isinstance(pi_data, dict) else ""
    print(f"PI: {pi_val:.4f} — {interp} (estimate from quick benchmark)")


@app.command(name="golden-qa")
def golden_qa(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-query results")):
    """Run golden QA retrieval benchmark (P@1, P@3, MRR)."""
    rb = _get_retrieval_benchmark()
    report = rb.run_benchmark(use_smart=True, k=3)
    rb.print_report(report)
    rb.save_report(report)
    print(f"\n  Results saved to {rb.LATEST_FILE}")


@app.command(name="golden-qa-trend")
def golden_qa_trend(days: int = typer.Argument(30, help="Number of days to show")):
    """Show golden QA retrieval benchmark trend."""
    rb = _get_retrieval_benchmark()
    rb.show_trend(days)

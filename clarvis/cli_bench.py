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
def pi():
    """Print Performance Index score only."""
    pb = _get_benchmark()
    report = pb.run_quick_benchmark()
    score = report.get("pi", report.get("performance_index", "N/A"))
    print(f"PI: {score}")

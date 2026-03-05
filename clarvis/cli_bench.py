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


@app.command()
def record():
    """Full benchmark — run all 8 dimensions and record to history."""
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
def trend(days: int = typer.Argument(30, help="Number of days to show")):
    """Show performance trend over N days."""
    pb = _get_benchmark()
    trend_data = pb.show_trend(days)
    pb.print_trend(trend_data)


@app.command()
def check():
    """Full benchmark with exit code 1 if any metric below target."""
    pb = _get_benchmark()
    report = pb.run_full_benchmark()
    pb.print_report(report)
    fails = report["summary"]["fail"]
    if fails:
        print(f"\n{fails} metric(s) below target.")
        raise typer.Exit(1)
    else:
        print("\nAll metrics within targets.")


@app.command()
def heartbeat():
    """Quick heartbeat check — JSON output, designed for <3s."""
    pb = _get_benchmark()
    result = pb.run_heartbeat_check()
    print(json.dumps(result))


@app.command()
def weakest():
    """Show the metric with worst margin-to-target ratio."""
    import os
    pb = _get_benchmark()
    if not os.path.exists(pb.METRICS_FILE):
        print("unknown")
        raise typer.Exit(1)
    with open(pb.METRICS_FILE) as f:
        stored = json.load(f)
    metrics = stored.get("metrics", {})
    worst_name, worst_margin = None, float("inf")
    for key, meta in pb.TARGETS.items():
        target = meta.get("target")
        if target is None or meta.get("direction") == "monitor":
            continue
        val = metrics.get(key)
        if val is None:
            continue
        if meta["direction"] == "higher":
            margin = (val - target) / max(target, 0.001)
        else:
            margin = (target - val) / max(target, 0.001)
        if margin < worst_margin:
            worst_margin = margin
            worst_name = key
    if worst_name:
        meta = pb.TARGETS[worst_name]
        val = metrics[worst_name]
        print(f"{meta['label']}={val:.3f} (target: {meta['target']})")
    else:
        print("unknown")


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

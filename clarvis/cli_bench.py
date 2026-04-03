"""clarvis bench — performance benchmarks.

Delegates to scripts/performance_benchmark.py for actual measurement.
"""

import json
import os
import sys

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")


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


@app.command(name="brief")
def brief(
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without updating report files"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Brief quality benchmark — measures context brief quality.

    Replaces: python3 scripts/brief_benchmark.py [--dry-run] [--json]
    """
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    import brief_benchmark as bb

    result = bb.run_benchmark(dry_run=dry_run)

    if json_output:
        print(json.dumps(result, indent=2))
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


@app.command(name="golden-qa")
def golden_qa(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-query results")):
    """Run golden QA retrieval benchmark (P@1, P@3, MRR)."""
    rb = _get_retrieval_benchmark()
    report = rb.run_benchmark(use_smart=True, k=3)
    rb.print_report(report)
    rb.save_report(report)
    print(f"\n  Results saved to {rb.LATEST_FILE}")


@app.command(name="golden-qa-oracle")
def golden_qa_oracle():
    """Run oracle comparison: normal vs gold-evidence retrieval.

    Isolates retrieval failures from reasoning/evidence-quality failures.
    Oracle mode injects gold evidence directly, bypassing actual retrieval.
    """
    rb = _get_retrieval_benchmark()
    comparison = rb.run_oracle_comparison(use_smart=True, k=3)

    normal = comparison["normal"]
    oracle = comparison["oracle"]
    gap = comparison["gap"]

    print("=== Oracle Retrieval Comparison ===\n")
    print(f"  {'Metric':<20} {'Normal':>8} {'Oracle':>8} {'Gap':>8}")
    print(f"  {'─' * 48}")
    print(f"  {'P@3':<20} {normal['avg_precision_at_k']:>8.3f} {oracle['avg_precision_at_k']:>8.3f} {gap['precision_at_k_gap']:>+8.3f}")
    print(f"  {'P@1':<20} {normal['avg_precision_at_1']:>8.3f} {oracle['avg_precision_at_1']:>8.3f} {gap['precision_at_1_gap']:>+8.3f}")
    print(f"  {'Recall':<20} {normal['avg_recall']:>8.3f} {oracle['avg_recall']:>8.3f} {gap['recall_gap']:>+8.3f}")
    print(f"  {'MRR':<20} {normal['mrr']:>8.3f} {oracle['mrr']:>8.3f} {gap['mrr_gap']:>+8.3f}")

    cat_gap = comparison.get("category_gap", {})
    if cat_gap:
        print(f"\n  Category gaps (recall / MRR):")
        for cat, g in sorted(cat_gap.items()):
            print(f"    {cat:<20} {g['recall_gap']:>+.3f} / {g['mrr_gap']:>+.3f}")

    rf = comparison["retrieval_failures"]
    sf = comparison["shared_failures"]
    print(f"\n  Diagnosis: {comparison['diagnosis']}")
    if rf:
        print(f"  Pure retrieval failures: {', '.join(rf)}")
    if sf:
        print(f"  Evidence-quality failures: {', '.join(sf)}")


@app.command(name="trajectory-check")
def trajectory_check(
    hours: int = typer.Option(24, "--hours", "-H", help="Hours of history to evaluate"),
):
    """Run trajectory evaluation gate on recent episodes."""
    from clarvis.metrics.trajectory import (
        format_trajectory_summary,
        load_trajectory_events,
        summarize_trajectory,
    )
    events = load_trajectory_events(hours=hours)
    summary = summarize_trajectory(events)
    print(format_trajectory_summary(summary, hours=hours))
    if not summary.get("gate", {}).get("pass"):
        raise typer.Exit(1)


@app.command(name="trajectory-summary")
def trajectory_summary(
    hours: int = typer.Option(24, "--hours", "-H", help="Hours of history"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON output"),
):
    """Show trajectory evaluation summary."""
    from clarvis.metrics.trajectory import (
        format_trajectory_summary,
        load_trajectory_events,
        summarize_trajectory,
    )
    events = load_trajectory_events(hours=hours)
    summary = summarize_trajectory(events)
    if json_output:
        print(json.dumps(summary, indent=2))
    else:
        print(format_trajectory_summary(summary, hours=hours))


@app.command(name="retrieval-report")
def retrieval_report(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),
):
    """Show retrieval quality report — hit rate, dead recall, diagnosis."""
    sys.path.insert(0, f"{WORKSPACE}/scripts")
    import retrieval_quality
    report = retrieval_quality.tracker.report()
    if as_json:
        print(json.dumps(report, indent=2, default=str))
        return
    if report.get("status") == "no_data":
        print(f"No recent retrieval events (have {report.get('total_events', 0)} total).")
        return
    print("=== Retrieval Quality Report ===\n")
    hit_rate = report.get("hit_rate")
    avg_dist = report.get("avg_distance_overall")
    print(f"  Period:          {report.get('period_days', 7)} days")
    print(f"  Total events:    {report.get('total_events', 0)}")
    print(f"  Empty recalls:   {report.get('empty_recalls', 0)}")
    print(f"  Dead recall:     {report.get('dead_recall_rate', 0):.1%}")
    print(f"  Hit rate:        {f'{hit_rate:.1%}' if hit_rate is not None else 'N/A (no rated events)'}")
    print(f"  Avg distance:    {f'{avg_dist:.4f}' if avg_dist is not None else 'N/A'}")
    print(f"  Diagnosis:       {report.get('diagnosis', 'unknown')}")
    rec = report.get("recommendation")
    if rec:
        print(f"  Recommendation:  {rec}")
    callers = report.get("by_caller", {})
    if callers:
        print(f"\n  By caller:")
        for caller, stats in sorted(callers.items()):
            hr = stats.get("hit_rate")
            hr_str = f"{hr:.1%}" if hr is not None else "N/A"
            print(f"    {caller:<30} {stats.get('total_recalls', 0):>4} recalls  hit_rate={hr_str}")
    # Feedback stats
    try:
        from clarvis.brain.retrieval_feedback import get_feedback
        fb = get_feedback()
        fb_stats = fb.stats()
        print(f"\n  Feedback loop:")
        print(f"    Verdict counts: {fb_stats.get('verdict_counts', {})}")
        avg_r = fb_stats.get("avg_reward", 0)
        print(f"    Avg reward:     {avg_r:.3f}" if avg_r else "    Avg reward:     N/A")
        suggestions = fb_stats.get("suggestions", [])
        if suggestions:
            print(f"    Suggestions:    {len(suggestions)}")
            for s in suggestions[:3]:
                print(f"      - {s}")
    except Exception:
        pass


@app.command(name="golden-qa-trend")
def golden_qa_trend(days: int = typer.Argument(30, help="Number of days to show")):
    """Show golden QA retrieval benchmark trend."""
    rb = _get_retrieval_benchmark()
    rb.show_trend(days)


@app.command(name="membench")
def membench(
    quadrant: str = typer.Option(None, "--quadrant", "-q",
                                 help="Specific quadrant to evaluate"),
    oracle: bool = typer.Option(False, "--oracle",
                                help="Use gold evidence (bypass retrieval)"),
    save: bool = typer.Option(True, "--save/--no-save",
                              help="Save results to data/benchmarks/"),
):
    """Run MemBench four-quadrant memory evaluation.

    Quadrants: participation-factual, participation-reflective,
    observation-factual, observation-reflective.
    """
    from clarvis.metrics.membench import run_membench, save_report, format_report
    report = run_membench(quadrant=quadrant, oracle=oracle)
    print(format_report(report))
    if save:
        save_report(report)
        from clarvis.metrics.membench import MEMBENCH_FILE
        print(f"  Results saved to {MEMBENCH_FILE}")


@app.command(name="longmemeval")
def longmemeval(
    ability: str = typer.Option(None, "--ability", "-a",
                                help="Specific ability: IE, MR, KU, TR, ABS"),
    oracle: bool = typer.Option(False, "--oracle",
                                help="Use gold evidence (bypass retrieval)"),
    k: int = typer.Option(5, "--k", help="Number of retrieval results"),
    save: bool = typer.Option(True, "--save/--no-save",
                              help="Save results to data/benchmarks/"),
):
    """Run LongMemEval five-ability memory evaluation.

    Abilities: IE (Information Extraction), MR (Multi-Session Reasoning),
    KU (Knowledge Update), TR (Temporal Reasoning), ABS (Abstention).
    """
    from clarvis.metrics.longmemeval import run_longmemeval, save_report, format_report
    report = run_longmemeval(ability=ability, k=k, oracle=oracle)
    print(format_report(report))
    if save:
        save_report(report)
        from clarvis.metrics.longmemeval import LONGMEMEVAL_FILE
        print(f"  Results saved to {LONGMEMEVAL_FILE}")


@app.command(name="longmemeval-oracle")
def longmemeval_oracle(
    ability: str = typer.Option(None, "--ability", "-a",
                                help="Specific ability: IE, MR, KU, TR, ABS"),
    k: int = typer.Option(5, "--k", help="Number of retrieval results"),
):
    """Run LongMemEval oracle comparison: normal vs gold-evidence retrieval.

    Isolates retrieval failures from reasoning failures per ability.
    """
    from clarvis.metrics.longmemeval import run_oracle_comparison, format_oracle_comparison
    comparison = run_oracle_comparison(ability=ability, k=k)
    print(format_oracle_comparison(comparison))

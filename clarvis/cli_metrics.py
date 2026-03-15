"""Clarvis CLI — metrics subcommand."""

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.command("self-model")
def self_model_cmd():
    """Run 7-domain self-model capability assessment."""
    from clarvis.metrics.self_model import SelfModel

    sm = SelfModel()
    scores = sm.get_capabilities()
    print("=== Self-Model — 7 Domain Capability Scores ===")
    for domain, score in scores.items():
        print(f"  {domain}: {score:.2f}")
    avg = sum(scores.values()) / len(scores) if scores else 0
    print(f"\n  Average: {avg:.2f}")


@app.command("phi")
def phi_cmd():
    """Compute Phi (IIT) integrated information metric."""
    from clarvis.metrics.phi import compute_phi

    result = compute_phi()
    print(f"Phi: {result}")


@app.command("pi")
def pi_cmd():
    """Compute Performance Index (PI)."""
    from clarvis.metrics.benchmark import compute_pi

    result = compute_pi()
    print(f"PI: {result}")


@app.command("clr")
def clr_cmd(
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip slow assessments"),
    record: bool = typer.Option(False, "--record", "-r", help="Record result to history"),
):
    """Compute CLR (Clarvis Rating) — composite agent intelligence score."""
    from clarvis.metrics.clr import compute_clr, record_clr, format_clr

    result = compute_clr(quick=quick)
    print(format_clr(result))
    if record:
        record_clr(result)
        print(f"\nRecorded to history.")


@app.command("clr-trend")
def clr_trend_cmd(days: int = typer.Argument(14, help="Number of days to show")):
    """Show CLR trend over recent days."""
    from clarvis.metrics.clr import get_clr_trend

    entries = get_clr_trend(days=days)
    if not entries:
        print(f"No CLR history found. Run 'python3 -m clarvis metrics clr --record' first.")
        return

    print(f"=== CLR Trend — Last {days} Days ===")
    for entry in entries:
        ts = entry["timestamp"][:10]
        clr = entry["clr"]
        va = entry["value_add"]
        bar = "#" * int(clr * 40)
        print(f"  {ts}  CLR={clr:.3f}  +{va:.3f}  |{bar}")

    clr_values = [e["clr"] for e in entries]
    print(f"\n  Min: {min(clr_values):.3f}  Max: {max(clr_values):.3f}  Avg: {sum(clr_values)/len(clr_values):.3f}")
    if len(clr_values) >= 2:
        delta = clr_values[-1] - clr_values[0]
        direction = "improving" if delta > 0.01 else "declining" if delta < -0.01 else "stable"
        print(f"  Trend: {direction} ({'+' if delta >= 0 else ''}{delta:.3f})")


@app.command("memory-audit")
def memory_audit_cmd(
    record: bool = typer.Option(False, "--record", "-r", help="Record result to history"),
):
    """Audit memory quality: canonical vs synthetic ratios, archived vs active."""
    from clarvis.metrics.memory_audit import run_full_audit, record_audit, format_audit

    result = run_full_audit()
    print(format_audit(result))
    if record:
        record_audit(result)
        print(f"\nRecorded to history.")

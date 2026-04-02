"""Clarvis unified CLI — root app and subcommand registration.

Usage:
    python3 -m clarvis --help
    python3 -m clarvis brain health
    python3 -m clarvis bench run
    python3 -m clarvis heartbeat run
    python3 -m clarvis queue next
"""

import typer

app = typer.Typer(
    name="clarvis",
    help="Clarvis — dual-layer cognitive agent CLI.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _register_subcommands():
    """Lazy-register sub-apps to keep top-level import fast."""
    from clarvis.cli_brain import app as brain_app
    from clarvis.cli_bench import app as bench_app
    from clarvis.cli_cognition import app as cognition_app
    from clarvis.cli_cost import app as cost_app
    from clarvis.cli_cron import app as cron_app
    from clarvis.cli_demo import app as demo_app
    from clarvis.cli_heartbeat import app as heartbeat_app
    from clarvis.cli_mode import app as mode_app
    from clarvis.cli_queue import app as queue_app
    from clarvis.cli_metrics import app as metrics_app

    app.add_typer(brain_app, name="brain", help="ClarvisDB brain operations.")
    app.add_typer(bench_app, name="bench", help="Performance benchmarks.")
    app.add_typer(cognition_app, name="cognition", help="Cognition: context relevance, weights.")
    app.add_typer(cost_app, name="cost", help="Cost tracking and budget monitoring.")
    app.add_typer(cron_app, name="cron", help="Cron job inspection and execution.")
    app.add_typer(demo_app, name="demo", help="Self-contained demo (no data needed).")
    app.add_typer(heartbeat_app, name="heartbeat", help="Heartbeat pipeline.")
    app.add_typer(metrics_app, name="metrics", help="Metrics: self-model, phi, PI.")
    app.add_typer(mode_app, name="mode", help="Runtime mode control-plane.")
    app.add_typer(queue_app, name="queue", help="Evolution queue management.")


def main():
    _register_subcommands()
    app()

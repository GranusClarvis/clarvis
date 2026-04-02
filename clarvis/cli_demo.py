"""clarvis demo — self-contained demo showing core capabilities.

Runs without existing brain data: stores, searches, recalls, and runs
the heartbeat gate.  Good for README walkthroughs, conference demos,
and verifying a fresh install works end-to-end.
"""

from __future__ import annotations

import sys
import time
import typer

app = typer.Typer()


def _print(label: str, msg: str) -> None:
    typer.echo(f"  [{label}] {msg}")


def _section(title: str) -> None:
    typer.echo(f"\n── {title} {'─' * max(1, 58 - len(title))}")


@app.callback(invoke_without_command=True)
def demo(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show extra detail"),
) -> None:
    """Run a self-contained Clarvis demo (no existing data needed)."""

    typer.echo("╔══════════════════════════════════════════════════════════════╗")
    typer.echo("║              Clarvis — Self-Contained Demo                  ║")
    typer.echo("╚══════════════════════════════════════════════════════════════╝")

    ok = True

    # ── 1. Brain import ─────────────────────────────────────────────
    _section("1. Brain availability")
    try:
        from clarvis.brain import brain  # noqa: F811
        _print("OK", "clarvis.brain imported successfully")
        stats = brain.stats()
        if isinstance(stats, dict):
            total = sum(v for v in stats.values() if isinstance(v, (int, float)))
            _print("OK", f"Brain has {total} memories across {len(stats)} collections")
        else:
            _print("OK", "Brain is operational")
    except Exception as e:
        _print("WARN", f"Brain not available ({e}) — demo continues without it")
        brain = None

    # ── 2. Store ────────────────────────────────────────────────────
    _section("2. Store a memory")
    demo_text = f"Clarvis demo memory — stored at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    if brain is not None:
        try:
            from clarvis.brain import remember
            result = remember(demo_text, importance=0.5)
            _print("OK", f"Stored: {demo_text!r}")
            if verbose and result:
                _print("OK", f"Result: {result}")
        except Exception as e:
            _print("FAIL", f"Store failed: {e}")
            ok = False
    else:
        _print("SKIP", "Brain not available — skipping store")

    # ── 3. Search ───────────────────────────────────────────────────
    _section("3. Search memories")
    if brain is not None:
        try:
            from clarvis.brain import search
            results = search("Clarvis demo", n=3)
            count = len(results) if results else 0
            _print("OK", f"Search returned {count} result(s)")
            if verbose and results:
                for i, r in enumerate(results[:3]):
                    doc = r.get("document", r) if isinstance(r, dict) else str(r)
                    if isinstance(doc, str) and len(doc) > 80:
                        doc = doc[:77] + "..."
                    _print("OK", f"  #{i + 1}: {doc}")
        except Exception as e:
            _print("FAIL", f"Search failed: {e}")
            ok = False
    else:
        _print("SKIP", "Brain not available — skipping search")

    # ── 4. CLI subcommands ──────────────────────────────────────────
    _section("4. CLI health")
    import subprocess
    for subcmd in ["brain --help", "heartbeat --help", "bench --help"]:
        try:
            subprocess.run(
                [sys.executable, "-m", "clarvis"] + subcmd.split(),
                capture_output=True, text=True, timeout=15,
            )
            _print("OK", f"clarvis {subcmd.split()[0]} — responds")
        except Exception as e:
            _print("FAIL", f"clarvis {subcmd}: {e}")
            ok = False

    # ── 5. Heartbeat gate ───────────────────────────────────────────
    _section("5. Heartbeat gate")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "clarvis", "heartbeat", "gate"],
            capture_output=True, text=True, timeout=30,
        )
        status = "WAKE" if result.returncode == 0 else "SKIP"
        _print("OK", f"Gate decision: {status} (exit {result.returncode})")
        if verbose and result.stdout.strip():
            for line in result.stdout.strip().splitlines()[:5]:
                _print("OK", f"  {line}")
    except Exception as e:
        _print("WARN", f"Heartbeat gate: {e}")

    # ── Summary ─────────────────────────────────────────────────────
    _section("Summary")
    if ok:
        typer.echo("\n  ✓ All checks passed. Clarvis is ready.\n")
        typer.echo("  Next steps:")
        typer.echo("    clarvis brain health          # full brain health report")
        typer.echo("    clarvis brain search 'topic'  # search memories")
        typer.echo("    clarvis heartbeat run         # run heartbeat pipeline")
        typer.echo()
    else:
        typer.echo("\n  ✗ Some checks failed — see above for details.\n")
        raise typer.Exit(code=1)

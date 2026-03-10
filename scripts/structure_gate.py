#!/usr/bin/env python3
"""
Structural Gate Suite — regression barrier for Clarvis spine migration.

Runs a sequence of fast, zero-LLM structural checks:
  1. compileall — every .py in clarvis/ and scripts/ compiles
  2. import-health — circular imports, depth, side effects (relaxed thresholds)
  3. spine smoke — core clarvis.* modules import cleanly
  4. CLI smoke — Typer CLI app + subcommands register
  5. pytest gate — targeted fast test groups (preflight, hooks, retrieval_eval)

Exit 0 = all gates pass. Exit 1 = at least one gate failed.

Usage:
    python3 scripts/structure_gate.py           # full suite
    python3 scripts/structure_gate.py --quick   # compileall + spine smoke only (~2s)
    python3 scripts/structure_gate.py --json    # machine-readable JSON output
"""

import json
import os
import subprocess
import sys
import time

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(WORKSPACE, "scripts")
CLARVIS_DIR = os.path.join(WORKSPACE, "clarvis")

# Spine modules that must import cleanly (no ChromaDB/ONNX init at import time)
SPINE_MODULES = [
    "clarvis",
    "clarvis.brain",
    "clarvis.cognition.confidence",
    "clarvis.heartbeat",
    "clarvis.metrics",
    "clarvis.metrics.phi",
    "clarvis.metrics.benchmark",
    "clarvis.metrics.self_model",
    "clarvis.context",
    "clarvis.memory",
    "clarvis.learning",
]

# CLI modules
CLI_MODULES = [
    "clarvis.cli",
    "clarvis.cli_brain",
    "clarvis.cli_bench",
    "clarvis.cli_queue",
    "clarvis.cli_heartbeat",
]


def _run(cmd, timeout=60):
    """Run a subprocess, return (success, output, elapsed)."""
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=WORKSPACE
        )
        elapsed = time.monotonic() - t0
        output = (r.stdout + r.stderr).strip()
        return r.returncode == 0, output, elapsed
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s", time.monotonic() - t0
    except Exception as e:
        return False, str(e), time.monotonic() - t0


def gate_compileall():
    """Gate 1: compileall — all .py files must compile."""
    results = {}
    for label, directory in [("clarvis/", CLARVIS_DIR), ("scripts/", SCRIPTS_DIR)]:
        ok, output, elapsed = _run(
            [sys.executable, "-m", "compileall", "-q", "-l", directory]
        )
        results[label] = {"passed": ok, "elapsed": round(elapsed, 2)}
        if not ok:
            results[label]["errors"] = output[:500]
    passed = all(r["passed"] for r in results.values())
    return {"gate": "compileall", "passed": passed, "details": results}


def gate_import_health():
    """Gate 2: import_health.py — structural health (relaxed thresholds)."""
    ok, output, elapsed = _run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "import_health.py"), "--quick"]
    )
    return {
        "gate": "import_health",
        "passed": ok,
        "elapsed": round(elapsed, 2),
        "output": output[:400] if not ok else "",
    }


def gate_spine_smoke():
    """Gate 3: Core clarvis.* spine modules import without error."""
    failures = []
    for mod in SPINE_MODULES:
        try:
            __import__(mod)
        except Exception as e:
            failures.append(f"{mod}: {e}")
    return {
        "gate": "spine_smoke",
        "passed": len(failures) == 0,
        "modules_checked": len(SPINE_MODULES),
        "failures": failures,
    }


def gate_cli_smoke():
    """Gate 4: CLI app + subcommands register cleanly."""
    failures = []
    for mod in CLI_MODULES:
        try:
            __import__(mod)
        except Exception as e:
            failures.append(f"{mod}: {e}")

    # Verify subcommand registration
    try:
        from clarvis.cli import app, _register_subcommands
        _register_subcommands()
        group_names = {
            g.typer_instance.info.name or g.name for g in app.registered_groups
        }
        expected = {"brain", "bench", "heartbeat", "queue"}
        missing = expected - group_names
        if missing:
            failures.append(f"missing CLI subcommands: {missing}")
    except Exception as e:
        failures.append(f"CLI registration: {e}")

    return {
        "gate": "cli_smoke",
        "passed": len(failures) == 0,
        "modules_checked": len(CLI_MODULES),
        "failures": failures,
    }


def gate_pytest(groups=None):
    """Gate 5: Run targeted pytest groups (fast tests only)."""
    if groups is None:
        groups = [
            "scripts/tests/test_preflight_defer.py",
            "clarvis/tests/test_cli_smoke.py",
            "clarvis/tests/test_hooks.py",
            "clarvis/tests/test_retrieval_eval.py",
        ]
    # Filter to only existing files
    existing = [g for g in groups if os.path.exists(os.path.join(WORKSPACE, g))]
    if not existing:
        return {"gate": "pytest", "passed": True, "details": "no test files found"}

    ok, output, elapsed = _run(
        [sys.executable, "-m", "pytest", "-x", "--tb=short", "-q"] + existing,
        timeout=120,
    )
    # Extract summary line
    lines = output.strip().split("\n")
    summary = lines[-1] if lines else ""
    return {
        "gate": "pytest",
        "passed": ok,
        "elapsed": round(elapsed, 2),
        "summary": summary,
        "output": output[-500:] if not ok else "",
    }


def run_suite(quick=False):
    """Run the full structural gate suite."""
    t0 = time.monotonic()
    results = []

    # Always run these fast gates
    results.append(gate_compileall())
    results.append(gate_spine_smoke())

    if not quick:
        results.append(gate_import_health())
        results.append(gate_cli_smoke())
        results.append(gate_pytest())

    total_elapsed = round(time.monotonic() - t0, 2)
    all_passed = all(r["passed"] for r in results)

    return {
        "passed": all_passed,
        "gates_run": len(results),
        "gates_passed": sum(1 for r in results if r["passed"]),
        "elapsed": total_elapsed,
        "results": results,
    }


def main():
    quick = "--quick" in sys.argv
    json_output = "--json" in sys.argv

    suite = run_suite(quick=quick)

    if json_output:
        print(json.dumps(suite, indent=2))
    else:
        mode = "QUICK" if quick else "FULL"
        print(f"=== Structural Gate Suite ({mode}) ===\n")
        for r in suite["results"]:
            status = "PASS" if r["passed"] else "FAIL"
            elapsed = r.get("elapsed", "")
            elapsed_str = f" ({elapsed}s)" if elapsed else ""
            print(f"  [{status}] {r['gate']}{elapsed_str}")
            if not r["passed"]:
                # Print failure details
                if r.get("failures"):
                    for f in r["failures"][:5]:
                        print(f"         {f}")
                if r.get("output"):
                    for line in r["output"].split("\n")[:5]:
                        print(f"         {line}")
                if r.get("errors"):
                    print(f"         {r['errors'][:200]}")
                if r.get("summary"):
                    print(f"         {r['summary']}")

        print(f"\n  {suite['gates_passed']}/{suite['gates_run']} gates passed "
              f"in {suite['elapsed']}s")

        if not suite["passed"]:
            print("\n  GATE SUITE FAILED — fix failures before proceeding.")

    sys.exit(0 if suite["passed"] else 1)


if __name__ == "__main__":
    main()

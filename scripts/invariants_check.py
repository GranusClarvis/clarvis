#!/usr/bin/env python3
"""Ouroboros invariants runner — drift detection for Clarvis migrations.

Runs a battery of checks and outputs a single JSONL record to
data/invariants_runs.jsonl with pass/fail + per-check timings.

Checks:
  1. pytest — fast subset (clarvis/tests/ + packages/clarvis-db/tests/)
  2. golden-qa — brain recall benchmark (if golden_qa.json exists)
  3. graph-verify — parity check (only when CLARVIS_GRAPH_BACKEND=sqlite)
  4. brain-health — basic store/recall health check
  5. hook-count — verify expected hook registrations load

Usage:
    python3 scripts/invariants_check.py              # Run all checks, append JSONL
    python3 scripts/invariants_check.py --json        # Print result as JSON (no file write)
    python3 scripts/invariants_check.py --check NAME  # Run single check (pytest|golden-qa|graph-verify|brain-health|hook-count)

Exit codes:
    0 — all checks PASS
    1 — one or more checks FAIL
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
INVARIANTS_LOG = os.path.join(WORKSPACE, "data", "invariants_runs.jsonl")

# Minimum expected hook registrations (from clarvis/brain/hooks.py _HOOK_DEFS)
MIN_HOOK_COUNT = 5


def _run_cmd(cmd: list[str], timeout: int = 120, cwd: str | None = None) -> tuple[int, str]:
    """Run a command and return (exit_code, combined output)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or WORKSPACE,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    except Exception as exc:
        return 1, f"ERROR: {exc}"


def check_pytest() -> dict:
    """Run pytest on fast test subset."""
    t0 = time.time()

    test_dirs = [
        os.path.join(WORKSPACE, "clarvis", "tests"),
        os.path.join(WORKSPACE, "packages", "clarvis-db", "tests"),
    ]
    existing = [d for d in test_dirs if os.path.isdir(d)]
    if not existing:
        return {
            "name": "pytest", "passed": False,
            "elapsed_s": round(time.time() - t0, 3),
            "detail": "no test directories found",
        }

    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--tb=short"] + existing
    code, output = _run_cmd(cmd, timeout=180)

    # Extract summary line (e.g. "26 passed in 4.12s")
    summary = ""
    for line in output.splitlines()[-5:]:
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
            break

    return {
        "name": "pytest",
        "passed": code == 0,
        "elapsed_s": round(time.time() - t0, 3),
        "exit_code": code,
        "summary": summary or output[-200:] if output else "(no output)",
    }


def check_golden_qa() -> dict:
    """Run brain recall benchmark on golden_qa.json if it exists."""
    t0 = time.time()

    # Main golden_qa.json for Clarvis brain
    golden_path = os.path.join(WORKSPACE, "data", "golden_qa.json")
    if not os.path.exists(golden_path):
        return {
            "name": "golden-qa",
            "passed": True,  # skip gracefully — no golden QA defined
            "elapsed_s": round(time.time() - t0, 3),
            "detail": "skipped (no golden_qa.json)",
        }

    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from brain import get_brain
        brain = get_brain()

        with open(golden_path) as f:
            qa_items = json.load(f)

        hits = 0
        total = len(qa_items)
        for item in qa_items:
            query = item.get("query", "")
            expected = item.get("answer", "")
            results = brain.recall(query, n=3)
            # Check if expected answer appears in top-3 results
            for r in results:
                doc = r.get("document", r.get("text", ""))
                if expected.lower() in doc.lower():
                    hits += 1
                    break

        precision = hits / total if total > 0 else 0.0
        return {
            "name": "golden-qa",
            "passed": precision >= 0.5,  # at least 50% P@3
            "elapsed_s": round(time.time() - t0, 3),
            "precision_at_3": round(precision, 3),
            "hits": hits,
            "total": total,
        }
    except Exception as exc:
        return {
            "name": "golden-qa",
            "passed": False,
            "elapsed_s": round(time.time() - t0, 3),
            "error": str(exc),
        }


def check_graph_verify() -> dict:
    """Run graph-verify parity check (only if CLARVIS_GRAPH_BACKEND=sqlite)."""
    t0 = time.time()

    backend = os.environ.get("CLARVIS_GRAPH_BACKEND", "json")
    if backend != "sqlite":
        return {
            "name": "graph-verify",
            "passed": True,  # skip when not on SQLite
            "elapsed_s": round(time.time() - t0, 3),
            "detail": f"skipped (backend={backend})",
        }

    cmd = [sys.executable, "-m", "clarvis", "brain", "graph-verify", "--sample-n", "200"]
    code, output = _run_cmd(cmd, timeout=120)

    # Check for "parity_ok" in output
    parity_ok = "parity_ok" in output and '"parity_ok": true' in output.lower()
    # Also accept exit code 0 as pass
    passed = code == 0

    return {
        "name": "graph-verify",
        "passed": passed,
        "elapsed_s": round(time.time() - t0, 3),
        "exit_code": code,
        "detail": output[-300:] if output else "(no output)",
    }


def check_brain_health() -> dict:
    """Run basic brain health check (store + recall roundtrip)."""
    t0 = time.time()

    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from brain import get_brain
        brain = get_brain()
        health = brain.health_check()

        passed = health.get("status") == "healthy"
        return {
            "name": "brain-health",
            "passed": passed,
            "elapsed_s": round(time.time() - t0, 3),
            "status": health.get("status", "unknown"),
            "collections": health.get("collections", 0),
        }
    except Exception as exc:
        return {
            "name": "brain-health",
            "passed": False,
            "elapsed_s": round(time.time() - t0, 3),
            "error": str(exc),
        }


def check_hook_count() -> dict:
    """Verify brain hook registrations reach minimum expected count."""
    t0 = time.time()

    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from brain import get_brain
        brain = get_brain()

        # Count registered hooks
        scorers = len(getattr(brain, '_recall_scorers', []))
        boosters = len(getattr(brain, '_recall_boosters', []))
        observers = len(getattr(brain, '_recall_observers', []))
        optimize = len(getattr(brain, '_optimize_hooks', []))
        total = scorers + boosters + observers + optimize

        passed = total >= MIN_HOOK_COUNT
        return {
            "name": "hook-count",
            "passed": passed,
            "elapsed_s": round(time.time() - t0, 3),
            "total": total,
            "breakdown": {
                "scorers": scorers,
                "boosters": boosters,
                "observers": observers,
                "optimize": optimize,
            },
            "minimum": MIN_HOOK_COUNT,
        }
    except Exception as exc:
        return {
            "name": "hook-count",
            "passed": False,
            "elapsed_s": round(time.time() - t0, 3),
            "error": str(exc),
        }


ALL_CHECKS = {
    "pytest": check_pytest,
    "golden-qa": check_golden_qa,
    "graph-verify": check_graph_verify,
    "brain-health": check_brain_health,
    "hook-count": check_hook_count,
}


def run_invariants(checks: list[str] | None = None) -> dict:
    """Run all (or selected) invariant checks.

    Returns:
        dict with overall pass/fail, individual check results, and timings.
    """
    t0 = time.time()
    check_names = checks or list(ALL_CHECKS.keys())
    results = []

    for name in check_names:
        fn = ALL_CHECKS.get(name)
        if fn is None:
            results.append({
                "name": name, "passed": False,
                "elapsed_s": 0, "error": f"unknown check: {name}",
            })
            continue
        result = fn()
        results.append(result)
        symbol = "PASS" if result["passed"] else "FAIL"
        print(f"  [{symbol}] {result['name']} ({result['elapsed_s']:.1f}s)")

    all_passed = all(r["passed"] for r in results)
    total_elapsed = round(time.time() - t0, 3)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "passed": all_passed,
        "elapsed_s": total_elapsed,
        "checks": results,
        "backend": os.environ.get("CLARVIS_GRAPH_BACKEND", "json"),
    }
    return record


def append_jsonl(record: dict, path: str = INVARIANTS_LOG) -> None:
    """Append a record to the JSONL log."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Ouroboros invariants runner")
    parser.add_argument("--json", action="store_true",
                        help="Print result as JSON to stdout (no file write)")
    parser.add_argument("--check", metavar="NAME",
                        help="Run single check: " + "|".join(ALL_CHECKS.keys()))
    args = parser.parse_args()

    checks = [args.check] if args.check else None

    print("=== Invariants Check ===")
    record = run_invariants(checks)

    status = "PASS" if record["passed"] else "FAIL"
    print(f"\nOverall: {status} ({record['elapsed_s']:.1f}s)")

    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        append_jsonl(record)
        print(f"Logged to: {INVARIANTS_LOG}")

    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

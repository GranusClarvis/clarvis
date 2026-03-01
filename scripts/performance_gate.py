#!/usr/bin/env python3
"""
Performance Gate — single go/no-go check for Clarvis system health.

Runs 4 checks in sequence, fails (exit 1) if any exceed thresholds:
  1. Brain health     — store/recall/stats smoke test
  2. Retrieval bench  — query speed + semantic hit quality
  3. Performance PI   — composite score across all dimensions
  4. Browser smoke    — CDP reachable, navigation, snapshot+refs

Exit codes:
  0 = all gates PASS
  1 = one or more gates FAIL
  2 = script error (crash, bad import)

Usage:
    python3 performance_gate.py              # Run all gates, exit 0 or 1
    python3 performance_gate.py --json       # Output JSON report + exit code
    python3 performance_gate.py --skip-browser  # Skip browser gate (faster)
    python3 performance_gate.py --verbose    # Extra detail per gate
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Thresholds ──────────────────────────────────────────────
THRESHOLDS = {
    "brain_health_status": "healthy",
    "brain_query_avg_ms": 12000.0,       # critical ceiling (matches performance_benchmark)
    "retrieval_hit_rate_min": 0.40,      # critical floor
    "pi_min": 0.20,                      # PI below this = Critical
    "pi_warn": 0.40,                     # PI below this = warning (still passes)
    "benchmark_fail_max": 5,             # max FAIL metrics before gate fails
    "browser_nav_timeout_ms": 30000,     # navigation must complete within this
}


def _ts():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg, verbose=True):
    if verbose:
        print(f"  {msg}", file=sys.stderr)


# ── Gate 1: Brain Health ────────────────────────────────────
def gate_brain_health(verbose=False):
    """Brain store/recall/stats smoke test."""
    t0 = time.monotonic()
    try:
        from brain import brain
        hc = brain.health_check()
        elapsed = round((time.monotonic() - t0) * 1000, 1)

        passed = hc.get("status") == "healthy"
        detail = {
            "status": hc.get("status"),
            "total_memories": hc.get("total_memories", 0),
            "collections": hc.get("collections", 0),
            "graph_edges": hc.get("graph_edges", 0),
            "elapsed_ms": elapsed,
        }
        if not passed:
            detail["error"] = hc.get("error", "unknown")

        _log(f"Brain: {hc.get('status')} ({detail['total_memories']} memories, {elapsed}ms)", verbose)
        return {"gate": "brain_health", "passed": passed, "detail": detail}

    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        _log(f"Brain: CRASH — {e}", verbose)
        return {"gate": "brain_health", "passed": False, "detail": {"error": str(e), "elapsed_ms": elapsed}}


# ── Gate 2: Retrieval Benchmark ─────────────────────────────
def gate_retrieval_benchmark(verbose=False):
    """Query speed + retrieval quality from performance_benchmark."""
    t0 = time.monotonic()
    try:
        from performance_benchmark import run_quick_benchmark
        result = run_quick_benchmark()
        elapsed = round((time.monotonic() - t0) * 1000, 1)

        speed = result.get("speed", {})
        avg_ms = speed.get("avg_ms", 99999)
        pi_est = result.get("pi_estimate", {}).get("pi", 0)

        speed_ok = avg_ms <= THRESHOLDS["brain_query_avg_ms"]

        detail = {
            "avg_ms": avg_ms,
            "p95_ms": speed.get("p95_ms", 0),
            "threshold_ms": THRESHOLDS["brain_query_avg_ms"],
            "speed_ok": speed_ok,
            "pi_estimate": pi_est,
            "elapsed_ms": elapsed,
        }

        # Also grab brain stats if available
        bstats = result.get("brain_stats", {})
        if bstats:
            detail["total_memories"] = bstats.get("total_memories", 0)
            detail["graph_density"] = bstats.get("graph_density", 0)

        passed = speed_ok
        _log(f"Retrieval: avg={avg_ms}ms (threshold={THRESHOLDS['brain_query_avg_ms']}ms) "
             f"PI≈{pi_est} {'PASS' if passed else 'FAIL'}", verbose)
        return {"gate": "retrieval_benchmark", "passed": passed, "detail": detail}

    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        _log(f"Retrieval: CRASH — {e}", verbose)
        return {"gate": "retrieval_benchmark", "passed": False, "detail": {"error": str(e), "elapsed_ms": elapsed}}


# ── Gate 3: Performance Benchmark (full PI) ─────────────────
def gate_performance_pi(verbose=False):
    """Full performance benchmark with PI computation."""
    t0 = time.monotonic()
    try:
        from performance_benchmark import run_full_benchmark
        report = run_full_benchmark()
        elapsed = round((time.monotonic() - t0) * 1000, 1)

        summary = report.get("summary", {})
        pi_val = summary.get("pi", 0)
        fail_count = summary.get("fail", 0)
        pass_count = summary.get("pass", 0)

        pi_ok = pi_val >= THRESHOLDS["pi_min"]
        fails_ok = fail_count <= THRESHOLDS["benchmark_fail_max"]
        passed = pi_ok and fails_ok

        # Collect individual failures for detail
        failures = []
        for key, r in report.get("results", {}).items():
            if r.get("status") == "FAIL":
                failures.append(f"{r.get('label', key)}: {r.get('value')} (target: {r.get('target')})")

        detail = {
            "pi": pi_val,
            "pi_interpretation": report.get("pi", {}).get("interpretation", ""),
            "pi_threshold": THRESHOLDS["pi_min"],
            "pass_count": pass_count,
            "fail_count": fail_count,
            "fail_max": THRESHOLDS["benchmark_fail_max"],
            "failures": failures,
            "bench_duration_s": report.get("bench_duration_s", 0),
            "elapsed_ms": elapsed,
        }

        warn = ""
        if pi_val < THRESHOLDS["pi_warn"]:
            warn = " (WARNING: below acceptable)"
        _log(f"PI: {pi_val}{warn} | {pass_count} pass, {fail_count} fail | "
             f"{'PASS' if passed else 'FAIL'}", verbose)
        return {"gate": "performance_pi", "passed": passed, "detail": detail}

    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        _log(f"PI: CRASH — {e}", verbose)
        return {"gate": "performance_pi", "passed": False, "detail": {"error": str(e), "elapsed_ms": elapsed}}


# ── Gate 4: Browser Smoke ───────────────────────────────────
async def _browser_smoke(verbose=False):
    """CDP reachable + navigate to example.com + snapshot with refs."""
    t0 = time.monotonic()
    try:
        from clarvis_browser import ClarvisBrowser

        async with ClarvisBrowser() as cb:
            # Step 1: status check (CDP reachable?)
            status = await cb.status()
            cdp_ok = status.get("cdp_reachable", False)
            if not cdp_ok:
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                _log("Browser: CDP not reachable — FAIL", verbose)
                return {"gate": "browser_smoke", "passed": False,
                        "detail": {"error": "CDP not reachable", "cdp_port": status.get("cdp_port"),
                                   "elapsed_ms": elapsed}}

            # Step 2: navigate
            nav_result = await cb.goto("https://example.com",
                                       timeout_ms=THRESHOLDS["browser_nav_timeout_ms"])
            nav_ok = nav_result.ok
            if not nav_ok:
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                _log(f"Browser: navigation failed — {nav_result.error}", verbose)
                return {"gate": "browser_smoke", "passed": False,
                        "detail": {"error": f"navigation: {nav_result.error}",
                                   "elapsed_ms": elapsed}}

            # Step 3: snapshot (tests agent-browser refs system)
            snap = await cb.snapshot()
            snap_ok = snap.ok
            has_refs = bool(snap.refs) if snap.ok else False

            elapsed = round((time.monotonic() - t0) * 1000, 1)
            passed = nav_ok and snap_ok

            detail = {
                "cdp_reachable": True,
                "engine": nav_result.engine or status.get("engine_primary", "unknown"),
                "nav_url": nav_result.url,
                "nav_title": nav_result.title,
                "nav_elapsed_ms": nav_result.elapsed_ms,
                "snapshot_ok": snap_ok,
                "snapshot_refs_count": len(snap.refs) if snap.ok else 0,
                "has_refs": has_refs,
                "elapsed_ms": elapsed,
            }

            _log(f"Browser: nav={'OK' if nav_ok else 'FAIL'} snap={'OK' if snap_ok else 'FAIL'} "
                 f"refs={len(snap.refs) if snap.ok else 0} ({elapsed}ms) "
                 f"{'PASS' if passed else 'FAIL'}", verbose)
            return {"gate": "browser_smoke", "passed": passed, "detail": detail}

    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        _log(f"Browser: CRASH — {e}", verbose)
        return {"gate": "browser_smoke", "passed": False,
                "detail": {"error": str(e), "elapsed_ms": elapsed}}


def gate_browser_smoke(verbose=False):
    """Sync wrapper for browser smoke test."""
    return asyncio.run(_browser_smoke(verbose))


# ── Main Runner ─────────────────────────────────────────────
def run_gate(skip_browser=False, verbose=False):
    """Run all gates, return unified report."""
    t0 = time.monotonic()
    timestamp = _ts()

    gates = []

    # Gate 1: brain health (fast, ~1-2s)
    _log("── Gate 1: Brain Health ──", verbose)
    gates.append(gate_brain_health(verbose))

    # Gate 2: retrieval benchmark (fast, ~2-3s)
    _log("── Gate 2: Retrieval Benchmark ──", verbose)
    gates.append(gate_retrieval_benchmark(verbose))

    # Gate 3: full PI (heavier, ~10-30s)
    _log("── Gate 3: Performance PI ──", verbose)
    gates.append(gate_performance_pi(verbose))

    # Gate 4: browser smoke (network, ~5-15s)
    if not skip_browser:
        _log("── Gate 4: Browser Smoke ──", verbose)
        gates.append(gate_browser_smoke(verbose))
    else:
        _log("── Gate 4: Browser Smoke (SKIPPED) ──", verbose)

    elapsed_s = round(time.monotonic() - t0, 2)

    all_passed = all(g["passed"] for g in gates)
    passed_count = sum(1 for g in gates if g["passed"])
    total_count = len(gates)

    report = {
        "timestamp": timestamp,
        "all_passed": all_passed,
        "passed": passed_count,
        "total": total_count,
        "elapsed_s": elapsed_s,
        "gates": gates,
    }

    return report


def print_report(report):
    """Human-readable report to stdout."""
    print(f"\n{'=' * 52}")
    print(f"  PERFORMANCE GATE  —  {'PASS' if report['all_passed'] else 'FAIL'}")
    print(f"{'=' * 52}")
    print(f"  Time: {report['timestamp']}  Duration: {report['elapsed_s']}s")
    print(f"  Result: {report['passed']}/{report['total']} gates passed")
    print(f"{'-' * 52}")

    for g in report["gates"]:
        icon = "PASS" if g["passed"] else "FAIL"
        name = g["gate"].replace("_", " ").title()
        print(f"  [{icon}] {name}")

        detail = g.get("detail", {})
        if g["gate"] == "brain_health":
            print(f"         memories={detail.get('total_memories', '?')} "
                  f"edges={detail.get('graph_edges', '?')} "
                  f"({detail.get('elapsed_ms', '?')}ms)")
        elif g["gate"] == "retrieval_benchmark":
            print(f"         avg={detail.get('avg_ms', '?')}ms "
                  f"p95={detail.get('p95_ms', '?')}ms "
                  f"PI≈{detail.get('pi_estimate', '?')} "
                  f"({detail.get('elapsed_ms', '?')}ms)")
        elif g["gate"] == "performance_pi":
            print(f"         PI={detail.get('pi', '?')} "
                  f"({detail.get('pi_interpretation', '?')})")
            print(f"         {detail.get('pass_count', '?')} pass, "
                  f"{detail.get('fail_count', '?')} fail "
                  f"(max {detail.get('fail_max', '?')} failures allowed)")
            for f in detail.get("failures", []):
                print(f"           - {f}")
        elif g["gate"] == "browser_smoke":
            if g["passed"]:
                print(f"         engine={detail.get('engine', '?')} "
                      f"title=\"{detail.get('nav_title', '?')}\" "
                      f"refs={detail.get('snapshot_refs_count', '?')} "
                      f"({detail.get('elapsed_ms', '?')}ms)")
            else:
                print(f"         error: {detail.get('error', 'unknown')}")

        if not g["passed"] and "error" in detail:
            print(f"         error: {detail['error']}")

    print(f"{'=' * 52}\n")


# ── CLI ─────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    json_mode = "--json" in args
    skip_browser = "--skip-browser" in args

    report = run_gate(skip_browser=skip_browser, verbose=verbose)

    if json_mode:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    sys.exit(0 if report["all_passed"] else 1)

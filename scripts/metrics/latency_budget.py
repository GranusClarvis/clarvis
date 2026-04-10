#!/usr/bin/env python3
"""
Latency budget tracker for Clarvis operations.

Measures actual p50/p95 latencies for brain and browser operations,
compares against budgets in data/perf_budget.json, records daily trend
to data/latency_trend.jsonl.

CLI:
  python3 latency_budget.py              # Full benchmark (brain + browser)
  python3 latency_budget.py brain        # Brain operations only (~15s)
  python3 latency_budget.py quick        # 3-query quick check (<5s)
  python3 latency_budget.py trend [days] # Show trend analysis
  python3 latency_budget.py status       # Load latest trend entry, no measurement
"""

import json
import statistics
import sys
import os
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
BUDGET_FILE = WORKSPACE / "data" / "perf_budget.json"
TREND_FILE = WORKSPACE / "data" / "latency_trend.jsonl"


# ---------------------------------------------------------------------------
# Budget loading
# ---------------------------------------------------------------------------

def load_budgets() -> dict:
    with open(BUDGET_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------

def _time_call(fn, *args, **kwargs):
    """Time a single call. Returns (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    return result, elapsed


def _percentile(values: list, pct: int) -> float:
    """Calculate percentile from sorted list."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_v):
        return sorted_v[-1]
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


BRAIN_QUERIES = [
    "What are my current goals?",
    "How does the heartbeat work?",
    "What happened in the last evolution cycle?",
    "Browser automation capabilities",
    "Memory consolidation procedures",
    "What is my performance index?",
    "Research topics recently explored",
    "Infrastructure and system health",
]


def measure_brain_recall(n_queries: int = 8) -> dict:
    """Measure brain.recall() latencies."""
    from clarvis.brain import brain

    queries = BRAIN_QUERIES[:n_queries]
    latencies = []

    # Warmup (not counted)
    _ = brain.recall("warmup", n=1)

    for q in queries:
        _, ms = _time_call(brain.recall, q, n=3)
        latencies.append(round(ms, 2))

    return {
        "operation": "brain.recall",
        "samples": len(latencies),
        "latencies_ms": latencies,
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "avg_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


def measure_smart_recall(n_queries: int = 5) -> dict:
    """Measure smart_recall() latencies."""
    try:
        from retrieval_experiment import smart_recall
    except ImportError:
        return {"operation": "brain.smart_recall", "error": "retrieval_experiment not importable", "samples": 0}

    queries = BRAIN_QUERIES[:n_queries]
    latencies = []

    for q in queries:
        _, ms = _time_call(smart_recall, q, n=3)
        latencies.append(round(ms, 2))

    return {
        "operation": "brain.smart_recall",
        "samples": len(latencies),
        "latencies_ms": latencies,
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "avg_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


def measure_brain_remember() -> dict:
    """Measure brain.remember() latency (write path)."""
    from clarvis.brain import remember

    latencies = []
    test_texts = [
        "Latency budget test entry — safe to ignore",
        "Performance measurement calibration datum",
        "Temporal benchmark sample for write-path timing",
    ]
    for txt in test_texts:
        _, ms = _time_call(remember, txt, importance=0.1)
        latencies.append(round(ms, 2))

    return {
        "operation": "brain.remember",
        "samples": len(latencies),
        "latencies_ms": latencies,
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "avg_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


def measure_browser(actions: list = None) -> list:
    """Measure ClarvisBrowser action latencies. Returns list of result dicts."""
    import asyncio

    results = []

    async def _run():
        try:
            from clarvis_browser import ClarvisBrowser
        except ImportError:
            results.append({"operation": "browser.*", "error": "clarvis_browser not importable", "samples": 0})
            return

        try:
            async with ClarvisBrowser() as cb:
                # goto
                _, ms = _time_call(asyncio.get_event_loop().run_until_complete, cb.goto("https://example.com"))
                # Can't nest run_until_complete; use direct await instead
                pass
        except Exception:
            pass

    # Use a simpler approach — just test if browser is available
    async def _measure():
        try:
            from clarvis_browser import ClarvisBrowser
        except ImportError:
            results.append({"operation": "browser.*", "error": "clarvis_browser not importable", "samples": 0})
            return

        try:
            cb = ClarvisBrowser()
            await cb.__aenter__()

            # goto
            t0 = time.perf_counter()
            await cb.goto("https://example.com")
            goto_ms = round((time.perf_counter() - t0) * 1000, 2)

            # snapshot
            t0 = time.perf_counter()
            await cb.snapshot()
            snap_ms = round((time.perf_counter() - t0) * 1000, 2)

            # click (safe target — a link on example.com)
            t0 = time.perf_counter()
            try:
                await cb.click("a", timeout_ms=5000)
                click_ms = round((time.perf_counter() - t0) * 1000, 2)
            except Exception:
                click_ms = round((time.perf_counter() - t0) * 1000, 2)

            await cb.__aexit__(None, None, None)

            results.append({"operation": "browser.goto", "samples": 1, "latencies_ms": [goto_ms],
                            "p50_ms": goto_ms, "p95_ms": goto_ms, "avg_ms": goto_ms, "min_ms": goto_ms, "max_ms": goto_ms})
            results.append({"operation": "browser.snapshot", "samples": 1, "latencies_ms": [snap_ms],
                            "p50_ms": snap_ms, "p95_ms": snap_ms, "avg_ms": snap_ms, "min_ms": snap_ms, "max_ms": snap_ms})
            results.append({"operation": "browser.click", "samples": 1, "latencies_ms": [click_ms],
                            "p50_ms": click_ms, "p95_ms": click_ms, "avg_ms": click_ms, "min_ms": click_ms, "max_ms": click_ms})

        except Exception as e:
            results.append({"operation": "browser.*", "error": str(e), "samples": 0})

    try:
        asyncio.run(_measure())
    except Exception as e:
        results.append({"operation": "browser.*", "error": str(e), "samples": 0})

    return results


# ---------------------------------------------------------------------------
# Budget comparison
# ---------------------------------------------------------------------------

def compare_to_budget(measurement: dict, budgets: dict) -> dict:
    """Compare a measurement dict against budget thresholds."""
    op_name = measurement["operation"]
    # Map to budget key
    budget_key = op_name.replace("brain.", "brain.").replace("browser.", "browser.")
    budget = budgets.get("operations", {}).get(budget_key)

    if not budget or measurement.get("error") or measurement.get("samples", 0) == 0:
        return {
            "operation": op_name,
            "status": "skip",
            "reason": measurement.get("error", "no budget defined or no samples"),
        }

    p50_ok = measurement["p50_ms"] <= budget["p50_ms"]
    p95_ok = measurement["p95_ms"] <= budget["p95_ms"]
    critical = measurement["p95_ms"] > budget.get("critical_ms", float("inf"))

    if critical:
        status = "CRITICAL"
    elif p50_ok and p95_ok:
        status = "PASS"
    elif p50_ok:
        status = "WARN_P95"
    else:
        status = "FAIL"

    return {
        "operation": op_name,
        "status": status,
        "measured_p50_ms": measurement["p50_ms"],
        "measured_p95_ms": measurement["p95_ms"],
        "budget_p50_ms": budget["p50_ms"],
        "budget_p95_ms": budget["p95_ms"],
        "critical_ms": budget.get("critical_ms"),
        "p50_headroom_pct": round((1 - measurement["p50_ms"] / budget["p50_ms"]) * 100, 1) if budget["p50_ms"] else 0,
        "p95_headroom_pct": round((1 - measurement["p95_ms"] / budget["p95_ms"]) * 100, 1) if budget["p95_ms"] else 0,
    }


# ---------------------------------------------------------------------------
# Trend recording
# ---------------------------------------------------------------------------

def record_trend(measurements: list, comparisons: list):
    """Append a trend entry to latency_trend.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "measurements": {m["operation"]: {
            "p50_ms": m.get("p50_ms"),
            "p95_ms": m.get("p95_ms"),
            "avg_ms": m.get("avg_ms"),
            "samples": m.get("samples", 0),
        } for m in measurements if m.get("samples", 0) > 0},
        "budget_status": {c["operation"]: c["status"] for c in comparisons if c.get("status") != "skip"},
        "summary": {
            "total": sum(1 for c in comparisons if c.get("status") != "skip"),
            "pass": sum(1 for c in comparisons if c.get("status") == "PASS"),
            "warn": sum(1 for c in comparisons if c.get("status", "").startswith("WARN")),
            "fail": sum(1 for c in comparisons if c.get("status") == "FAIL"),
            "critical": sum(1 for c in comparisons if c.get("status") == "CRITICAL"),
        },
    }

    # Append
    TREND_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TREND_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Prune to max entries
    budgets = load_budgets()
    max_entries = budgets.get("max_trend_entries", 500)
    try:
        lines = TREND_FILE.read_text().strip().split("\n")
        if len(lines) > max_entries:
            TREND_FILE.write_text("\n".join(lines[-max_entries:]) + "\n")
    except Exception:
        pass

    return entry


def show_trend(days: int = 7):
    """Show trend analysis from latency_trend.jsonl."""
    if not TREND_FILE.exists():
        print("No trend data yet. Run a benchmark first.")
        return

    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    for line in TREND_FILE.read_text().strip().split("\n"):
        if not line.strip():
            continue
        e = json.loads(line)
        ts = datetime.fromisoformat(e["timestamp"])
        if ts >= cutoff:
            entries.append(e)

    if not entries:
        print(f"No trend data in the last {days} days.")
        return

    print(f"\n=== Latency Trend ({days}d, {len(entries)} samples) ===\n")

    # Aggregate per operation
    ops = {}
    for e in entries:
        for op, m in e.get("measurements", {}).items():
            if op not in ops:
                ops[op] = {"p50s": [], "p95s": [], "avgs": []}
            if m.get("p50_ms") is not None:
                ops[op]["p50s"].append(m["p50_ms"])
            if m.get("p95_ms") is not None:
                ops[op]["p95s"].append(m["p95_ms"])
            if m.get("avg_ms") is not None:
                ops[op]["avgs"].append(m["avg_ms"])

    budgets = load_budgets()
    for op, data in sorted(ops.items()):
        budget = budgets.get("operations", {}).get(op, {})
        print(f"  {op}:")
        if data["p50s"]:
            p50_mean = statistics.mean(data["p50s"])
            p50_budget = budget.get("p50_ms", "?")
            print(f"    p50: {p50_mean:.0f}ms avg (budget: {p50_budget}ms)  range: {min(data['p50s']):.0f}-{max(data['p50s']):.0f}ms")
        if data["p95s"]:
            p95_mean = statistics.mean(data["p95s"])
            p95_budget = budget.get("p95_ms", "?")
            print(f"    p95: {p95_mean:.0f}ms avg (budget: {p95_budget}ms)  range: {min(data['p95s']):.0f}-{max(data['p95s']):.0f}ms")
        print()

    # Status summary
    statuses = {"PASS": 0, "WARN_P95": 0, "FAIL": 0, "CRITICAL": 0}
    for e in entries:
        for _, s in e.get("budget_status", {}).items():
            statuses[s] = statuses.get(s, 0) + 1
    total = sum(statuses.values())
    if total:
        pass_rate = statuses["PASS"] / total * 100
        print(f"  Budget compliance: {pass_rate:.0f}% PASS ({statuses['PASS']}/{total})")
        if statuses["CRITICAL"]:
            print(f"  ⚠ {statuses['CRITICAL']} CRITICAL breaches")
    print()


def show_status():
    """Show latest trend entry without measuring."""
    if not TREND_FILE.exists():
        print("No trend data yet. Run a benchmark first.")
        return

    lines = TREND_FILE.read_text().strip().split("\n")
    latest = json.loads(lines[-1])
    ts = latest["timestamp"][:19]
    print(f"\n=== Latest Latency Budget Status ({ts}) ===\n")

    budgets = load_budgets()
    for op, m in sorted(latest.get("measurements", {}).items()):
        budget = budgets.get("operations", {}).get(op, {})
        status = latest.get("budget_status", {}).get(op, "?")
        tag = {"PASS": "OK", "WARN_P95": "WARN", "FAIL": "FAIL", "CRITICAL": "CRIT"}.get(status, status)
        print(f"  [{tag:4s}] {op}: p50={m['p50_ms']:.0f}ms (budget {budget.get('p50_ms','?')}ms) "
              f"p95={m['p95_ms']:.0f}ms (budget {budget.get('p95_ms','?')}ms)")

    s = latest.get("summary", {})
    print(f"\n  Total: {s.get('pass',0)} pass, {s.get('warn',0)} warn, {s.get('fail',0)} fail, {s.get('critical',0)} critical\n")


# ---------------------------------------------------------------------------
# Quick check (for heartbeat integration)
# ---------------------------------------------------------------------------

def quick_check() -> dict:
    """3-query brain check, returns dict suitable for heartbeat postflight."""
    from clarvis.brain import brain

    # Warmup
    _ = brain.recall("warmup", n=1)

    latencies = []
    for q in BRAIN_QUERIES[:3]:
        _, ms = _time_call(brain.recall, q, n=3)
        latencies.append(round(ms, 2))

    budgets = load_budgets()
    budget = budgets["operations"]["brain.recall"]

    p50 = round(_percentile(latencies, 50), 2)
    p95 = round(max(latencies), 2)  # With 3 samples, max ≈ p95

    return {
        "type": "latency_quick",
        "operation": "brain.recall",
        "samples": 3,
        "p50_ms": p50,
        "p95_ms": p95,
        "budget_p50_ms": budget["p50_ms"],
        "budget_p95_ms": budget["p95_ms"],
        "p50_ok": p50 <= budget["p50_ms"],
        "p95_ok": p95 <= budget["p95_ms"],
        "critical": p95 > budget["critical_ms"],
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_full(include_browser: bool = True):
    """Run full benchmark, compare, record trend, print results."""
    budgets = load_budgets()
    measurements = []
    comparisons = []

    print("\n=== Latency Budget Benchmark ===\n")

    # Brain recall
    print("  Measuring brain.recall() ...", end="", flush=True)
    m = measure_brain_recall()
    measurements.append(m)
    c = compare_to_budget(m, budgets)
    comparisons.append(c)
    print(f" p50={m['p50_ms']:.0f}ms p95={m['p95_ms']:.0f}ms [{c['status']}]")

    # Smart recall
    print("  Measuring smart_recall() ...", end="", flush=True)
    m = measure_smart_recall()
    measurements.append(m)
    c = compare_to_budget(m, budgets)
    comparisons.append(c)
    if m.get("error"):
        print(f" {m['error']}")
    else:
        print(f" p50={m['p50_ms']:.0f}ms p95={m['p95_ms']:.0f}ms [{c['status']}]")

    # Brain remember
    print("  Measuring brain.remember() ...", end="", flush=True)
    m = measure_brain_remember()
    measurements.append(m)
    c = compare_to_budget(m, budgets)
    comparisons.append(c)
    print(f" p50={m['p50_ms']:.0f}ms p95={m['p95_ms']:.0f}ms [{c['status']}]")

    # Browser (optional)
    if include_browser:
        print("  Measuring browser actions ...", end="", flush=True)
        browser_results = measure_browser()
        for m in browser_results:
            measurements.append(m)
            c = compare_to_budget(m, budgets)
            comparisons.append(c)
            if m.get("error"):
                print(f"\n    {m['operation']}: {m['error']}")
            else:
                print(f"\n    {m['operation']}: p50={m['p50_ms']:.0f}ms [{c['status']}]", end="")
        print()

    # Record trend
    entry = record_trend(measurements, comparisons)
    s = entry["summary"]
    print(f"\n  Recorded: {s['pass']} pass, {s['warn']} warn, {s['fail']} fail, {s['critical']} critical")
    print(f"  Trend file: {TREND_FILE}\n")

    # Detailed report
    print("  Budget Comparison:")
    for c in comparisons:
        if c.get("status") == "skip":
            continue
        tag = {"PASS": "OK", "WARN_P95": "WARN", "FAIL": "FAIL", "CRITICAL": "CRIT"}.get(c["status"], c["status"])
        headroom = f"headroom: p50={c['p50_headroom_pct']:+.0f}% p95={c['p95_headroom_pct']:+.0f}%"
        print(f"    [{tag:4s}] {c['operation']}: "
              f"measured p50={c['measured_p50_ms']:.0f}/{c['budget_p50_ms']}ms "
              f"p95={c['measured_p95_ms']:.0f}/{c['budget_p95_ms']}ms  ({headroom})")
    print()

    return {"measurements": measurements, "comparisons": comparisons, "summary": s}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "brain":
        run_full(include_browser=False)
    elif mode == "quick":
        result = quick_check()
        tag = "OK" if result["p50_ok"] and result["p95_ok"] else ("CRIT" if result["critical"] else "WARN")
        print(f"[{tag}] brain.recall quick: p50={result['p50_ms']:.0f}ms (budget {result['budget_p50_ms']}ms) "
              f"p95={result['p95_ms']:.0f}ms (budget {result['budget_p95_ms']}ms)")
        print(json.dumps(result, indent=2))
    elif mode == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        show_trend(days)
    elif mode == "status":
        show_status()
    elif mode == "full":
        run_full(include_browser=True)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

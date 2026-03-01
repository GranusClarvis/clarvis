#!/usr/bin/env python3
"""Error Recovery Benchmark — measures browser error detection and recovery.

Tests Clarvis's ability to:
1. Navigate to broken/404/invalid URLs
2. Detect the error state accurately (HTTP status, DNS failure, timeout, etc.)
3. Recover: go back or navigate to an alternative working URL
4. Measure: detection accuracy, recovery success rate, timing

Usage:
    python3 error_recovery_benchmark.py              # Run full benchmark
    python3 error_recovery_benchmark.py --json        # JSON output only
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser_agent import BrowserAgent, BrowseResult

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RESULTS_DIR = Path("/home/agent/.openclaw/workspace/data/benchmarks")
RESULTS_FILE = RESULTS_DIR / "error_recovery_results.json"
HISTORY_FILE = RESULTS_DIR / "error_recovery_history.jsonl"

# Test scenarios: each has a broken URL and an alternative to recover to
ERROR_SCENARIOS = [
    {
        "name": "HTTP 404 — GitHub",
        "broken_url": "https://github.com/this-repo-definitely-does-not-exist-12345abc",
        "expected_error_type": "http_error",
        "recovery_url": "https://github.com/",
        "description": "Standard 404 on a reliable host",
    },
    {
        "name": "HTTP 404 — Wikipedia",
        "broken_url": "https://en.wikipedia.org/wiki/This_Page_Absolutely_Does_Not_Exist_XYZ789",
        "expected_error_type": "http_error",
        "recovery_url": "https://en.wikipedia.org/wiki/Main_Page",
        "description": "404 on Wikipedia — should detect missing page",
    },
    {
        "name": "DNS failure — nonexistent domain",
        "broken_url": "https://this-domain-does-not-exist-clarvis-test.invalid/",
        "expected_error_type": "dns_error",
        "recovery_url": "https://example.com/",
        "description": "DNS resolution failure on .invalid TLD",
    },
    {
        "name": "Connection refused — bad port",
        "broken_url": "http://127.0.0.1:19999/nonexistent",
        "expected_error_type": "connection_error",
        "recovery_url": "https://example.com/",
        "description": "Connection refused to localhost on unused port",
    },
    {
        "name": "Invalid URL scheme",
        "broken_url": "hxxp://not-a-real-protocol.test/page",
        "expected_error_type": "invalid_url",
        "recovery_url": "https://example.com/",
        "description": "Completely invalid URL scheme",
    },
    {
        "name": "HTTP 404 — httpbin",
        "broken_url": "https://httpbin.org/status/404",
        "expected_error_type": "http_error",
        "recovery_url": "https://httpbin.org/",
        "description": "httpbin deliberately returns 404",
    },
]


@dataclass
class ScenarioResult:
    name: str
    description: str
    broken_url: str
    recovery_url: str
    expected_error_type: str
    # Detection phase
    error_detected: bool
    detected_error_type: str  # http_error, dns_error, connection_error, timeout, unknown
    detected_error_detail: str
    detection_ms: float
    # Recovery phase
    recovery_attempted: bool
    recovery_success: bool
    recovery_url_reached: str
    recovery_title: str
    recovery_ms: float
    # Overall
    total_ms: float
    error: Optional[str] = None


def classify_error(result: BrowseResult) -> tuple[str, str]:
    """Classify a BrowseResult error into (type, detail).

    Returns:
        (error_type, detail_str) where error_type is one of:
        http_error, dns_error, connection_error, timeout, invalid_url, unknown
    """
    if result.ok:
        return ("none", "no error")

    err = (result.error or "").lower()

    # HTTP status errors (navigate() returns "HTTP 4xx" / "HTTP 5xx")
    if err.startswith("http "):
        return ("http_error", result.error)

    # DNS / name resolution
    if any(s in err for s in ["name not resolved", "dns", "err_name",
                               "nodename nor servname", "getaddrinfo"]):
        return ("dns_error", result.error)

    # HTTP response code failure (Playwright throws this for some 4xx/5xx)
    if "err_http_response_code_failure" in err or "response_code_failure" in err:
        return ("http_error", result.error)

    # Connection refused / reset
    if any(s in err for s in ["connection refused", "err_connection_refused",
                               "econnrefused", "connection reset",
                               "err_connection_reset"]):
        return ("connection_error", result.error)

    # Timeout
    if any(s in err for s in ["timeout", "timed out", "err_timed_out"]):
        return ("timeout", result.error)

    # Invalid URL / protocol
    if any(s in err for s in ["invalid url", "err_invalid", "protocol",
                               "err_unknown_url_scheme", "err_failed"]):
        return ("invalid_url", result.error)

    return ("unknown", result.error)


async def run_scenario(ba: BrowserAgent, scenario: dict) -> ScenarioResult:
    """Run a single error recovery scenario."""
    t_total = time.monotonic()

    # -- Phase 1: Navigate to broken URL, detect error --
    t_detect = time.monotonic()
    nav_result = await ba.navigate(scenario["broken_url"], timeout_ms=15000, retries=0)
    detection_ms = (time.monotonic() - t_detect) * 1000

    error_detected = not nav_result.ok
    error_type, error_detail = classify_error(nav_result)

    # Special case: some 404 pages still "load" with 200 but show error text.
    # For sites like Wikipedia that may return 200 with a "does not exist" page:
    if nav_result.ok and not error_detected:
        try:
            page_text = await ba.extract_text()
            lower = page_text.lower()
            if any(s in lower for s in ["does not have an article",
                                         "page not found", "404",
                                         "not found", "doesn't exist"]):
                error_detected = True
                error_type = "http_error"
                error_detail = "Soft 404 detected via page content"
        except Exception:
            pass

    # -- Phase 2: Recovery — go back or navigate to alternative --
    recovery_attempted = error_detected  # only attempt recovery if we detected error
    recovery_success = False
    recovery_url_reached = ""
    recovery_title = ""
    recovery_ms = 0

    if recovery_attempted:
        t_recovery = time.monotonic()

        # Strategy 1: Try go_back first (simulates user pressing Back)
        # Use a short timeout — if go_back doesn't resolve quickly, move on
        try:
            await asyncio.wait_for(ba.go_back(), timeout=3.0)
            await asyncio.sleep(0.3)
            info = await ba.get_page_info()
            prev_url = info.get("url", "")
            # If go_back landed somewhere useful (not blank/error)
            if prev_url and "about:blank" not in prev_url and "error" not in prev_url.lower():
                test_result = BrowseResult(url=prev_url, title=info.get("title", ""))
                if test_result.title:
                    recovery_success = True
                    recovery_url_reached = prev_url
                    recovery_title = test_result.title
        except (asyncio.TimeoutError, Exception):
            pass

        # Strategy 2: Navigate to recovery URL
        if not recovery_success:
            rec_result = await ba.navigate(scenario["recovery_url"], timeout_ms=15000)
            if rec_result.ok:
                recovery_success = True
                recovery_url_reached = rec_result.url
                recovery_title = rec_result.title
            else:
                recovery_url_reached = rec_result.url
                recovery_title = f"FAILED: {rec_result.error}"

        recovery_ms = (time.monotonic() - t_recovery) * 1000

    total_ms = (time.monotonic() - t_total) * 1000

    return ScenarioResult(
        name=scenario["name"],
        description=scenario["description"],
        broken_url=scenario["broken_url"],
        recovery_url=scenario["recovery_url"],
        expected_error_type=scenario["expected_error_type"],
        error_detected=error_detected,
        detected_error_type=error_type,
        detected_error_detail=error_detail,
        detection_ms=round(detection_ms, 1),
        recovery_attempted=recovery_attempted,
        recovery_success=recovery_success,
        recovery_url_reached=recovery_url_reached,
        recovery_title=recovery_title,
        recovery_ms=round(recovery_ms, 1),
        total_ms=round(total_ms, 1),
    )


async def run_benchmark() -> dict:
    """Run all error recovery scenarios."""
    results: list[ScenarioResult] = []
    t_start = time.monotonic()

    # Start by navigating to a known-good page (baseline)
    async with BrowserAgent() as ba:
        baseline = await ba.navigate("https://example.com/")
        if not baseline.ok:
            print(f"  WARNING: Baseline navigation failed: {baseline.error}")

        for scenario in ERROR_SCENARIOS:
            print(f"  [{scenario['name']}] ", end="", flush=True)
            result = await run_scenario(ba, scenario)

            det = "DETECTED" if result.error_detected else "MISSED"
            rec = "RECOVERED" if result.recovery_success else ("FAILED" if result.recovery_attempted else "SKIPPED")
            print(f"{det} ({result.detected_error_type}) → {rec} ({result.total_ms:.0f}ms)")
            results.append(result)

    elapsed_total = (time.monotonic() - t_start) * 1000

    # Aggregate metrics
    n = len(results)
    detections = sum(1 for r in results if r.error_detected)
    correct_type = sum(1 for r in results
                       if r.error_detected and r.detected_error_type == r.expected_error_type)
    recoveries_attempted = sum(1 for r in results if r.recovery_attempted)
    recoveries_succeeded = sum(1 for r in results if r.recovery_success)

    detection_accuracy = detections / n if n else 0.0
    type_accuracy = correct_type / n if n else 0.0
    recovery_rate = recoveries_succeeded / recoveries_attempted if recoveries_attempted else 0.0

    avg_detect_ms = sum(r.detection_ms for r in results) / n if n else 0
    avg_recover_ms = (sum(r.recovery_ms for r in results if r.recovery_attempted)
                      / recoveries_attempted if recoveries_attempted else 0)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scenarios_tested": n,
        "errors_detected": detections,
        "errors_missed": n - detections,
        "detection_accuracy": round(detection_accuracy, 2),
        "type_classification_accuracy": round(type_accuracy, 2),
        "recoveries_attempted": recoveries_attempted,
        "recoveries_succeeded": recoveries_succeeded,
        "recovery_success_rate": round(recovery_rate, 2),
        "avg_detection_ms": round(avg_detect_ms, 1),
        "avg_recovery_ms": round(avg_recover_ms, 1),
        "total_benchmark_ms": round(elapsed_total, 1),
        "results": [asdict(r) for r in results],
    }

    # Persist
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)
    with open(HISTORY_FILE, "a") as f:
        summary = {k: v for k, v in report.items() if k != "results"}
        f.write(json.dumps(summary) + "\n")

    return report


def print_report(report: dict):
    """Pretty-print error recovery benchmark results."""
    print("\n" + "=" * 70)
    print("  ERROR RECOVERY BENCHMARK RESULTS")
    print("=" * 70)
    print(f"  Timestamp:        {report['timestamp']}")
    print(f"  Scenarios tested: {report['scenarios_tested']}")
    print(f"  Detection:        {report['detection_accuracy'] * 100:.0f}% "
          f"({report['errors_detected']}/{report['scenarios_tested']})")
    print(f"  Type accuracy:    {report['type_classification_accuracy'] * 100:.0f}% "
          f"(correct error type classification)")
    print(f"  Recovery rate:    {report['recovery_success_rate'] * 100:.0f}% "
          f"({report['recoveries_succeeded']}/{report['recoveries_attempted']})")
    print(f"  Avg detect time:  {report['avg_detection_ms']:.0f}ms")
    print(f"  Avg recover time: {report['avg_recovery_ms']:.0f}ms")
    print(f"  Total benchmark:  {report['total_benchmark_ms']:.0f}ms")
    print("-" * 70)
    for r in report["results"]:
        det = "DETECT" if r["error_detected"] else "MISS  "
        rec = "RECOV " if r["recovery_success"] else ("FAIL  " if r["recovery_attempted"] else "SKIP  ")
        type_match = "=" if r["detected_error_type"] == r["expected_error_type"] else "!"
        print(f"  [{det}|{rec}] {r['name']:<35} "
              f"type:{r['detected_error_type']}{type_match} "
              f"{r['total_ms']:>6.0f}ms")
        if r.get("recovery_title") and r["recovery_success"]:
            print(f"           → recovered to: {r['recovery_title'][:50]}")
        if r.get("detected_error_detail") and not r["error_detected"]:
            print(f"           detail: {r['detected_error_detail'][:60]}")
    print("=" * 70)

    # Overall grade
    det_pct = report["detection_accuracy"] * 100
    rec_pct = report["recovery_success_rate"] * 100
    if det_pct >= 90 and rec_pct >= 90:
        grade = "EXCELLENT"
    elif det_pct >= 75 and rec_pct >= 75:
        grade = "GOOD"
    elif det_pct >= 50 and rec_pct >= 50:
        grade = "FAIR"
    else:
        grade = "NEEDS IMPROVEMENT"
    print(f"  Grade: {grade} (detect={det_pct:.0f}%, recover={rec_pct:.0f}%)")
    print(f"  Results saved: {RESULTS_FILE}")
    print()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Error recovery benchmark")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    print("Running error recovery benchmark...")
    report = await run_benchmark()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    # Exit code: 0 if detection >= 80% AND recovery >= 80%
    ok = report["detection_accuracy"] >= 0.8 and report["recovery_success_rate"] >= 0.8
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

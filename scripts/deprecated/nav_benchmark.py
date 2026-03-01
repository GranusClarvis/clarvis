#!/usr/bin/env python3
"""Navigation Benchmark — measures browser navigation success rate and extraction time.

Tests Clarvis's ability to navigate to diverse URLs, extract page title + main content,
and save structured output.  Reports success rate and per-site timing.

Usage:
    python3 nav_benchmark.py                # Run full benchmark (5 default sites)
    python3 nav_benchmark.py --url URL      # Benchmark a single URL
    python3 nav_benchmark.py --json         # Output results as JSON only
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
from browser_agent import BrowserAgent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RESULTS_DIR = Path("/home/agent/.openclaw/workspace/data/benchmarks")
RESULTS_FILE = RESULTS_DIR / "nav_benchmark_results.json"
HISTORY_FILE = RESULTS_DIR / "nav_benchmark_history.jsonl"

# 5 diverse test sites — chosen for variety and reliability
DEFAULT_SITES = [
    {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "category": "encyclopedia",
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/",
        "category": "news-aggregator",
    },
    {
        "name": "BBC Weather",
        "url": "https://www.bbc.com/weather",
        "category": "weather",
    },
    {
        "name": "Python Docs",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "category": "documentation",
    },
    {
        "name": "GitHub Blog",
        "url": "https://github.blog/",
        "category": "blog",
    },
]


@dataclass
class SiteResult:
    name: str
    url: str
    category: str
    success: bool
    title: str
    content_length: int  # chars of extracted text
    content_preview: str  # first 200 chars
    links_count: int
    navigate_ms: float
    extract_ms: float
    total_ms: float
    error: Optional[str] = None


async def benchmark_site(ba: BrowserAgent, site: dict) -> SiteResult:
    """Navigate to a site, extract content, measure timings."""
    t_total = time.monotonic()

    # 1. Navigate
    t_nav = time.monotonic()
    nav_result = await ba.navigate(site["url"], timeout_ms=20000)
    navigate_ms = (time.monotonic() - t_nav) * 1000

    if not nav_result.ok:
        total_ms = (time.monotonic() - t_total) * 1000
        return SiteResult(
            name=site["name"], url=site["url"], category=site["category"],
            success=False, title="", content_length=0, content_preview="",
            links_count=0, navigate_ms=navigate_ms, extract_ms=0,
            total_ms=total_ms, error=nav_result.error,
        )

    # 2. Extract content
    t_ext = time.monotonic()
    title = nav_result.title or ""
    text = await ba.extract_text()
    links = await ba.extract_links()
    extract_ms = (time.monotonic() - t_ext) * 1000

    total_ms = (time.monotonic() - t_total) * 1000

    # Determine success: must have title OR meaningful text
    has_content = len(text.strip()) > 50
    success = bool(title or has_content)

    return SiteResult(
        name=site["name"], url=site["url"], category=site["category"],
        success=success, title=title,
        content_length=len(text),
        content_preview=text[:200].replace("\n", " ").strip(),
        links_count=len(links),
        navigate_ms=round(navigate_ms, 1),
        extract_ms=round(extract_ms, 1),
        total_ms=round(total_ms, 1),
    )


async def run_benchmark(sites: list[dict] = None) -> dict:
    """Run the full navigation benchmark."""
    sites = sites or DEFAULT_SITES
    results: list[SiteResult] = []

    t_start = time.monotonic()

    async with BrowserAgent() as ba:
        for site in sites:
            print(f"  [{site['name']}] {site['url']} ... ", end="", flush=True)
            result = await benchmark_site(ba, site)
            status = "OK" if result.success else f"FAIL: {result.error}"
            print(f"{status} ({result.total_ms:.0f}ms, {result.content_length} chars)")
            results.append(result)

    elapsed_total = (time.monotonic() - t_start) * 1000

    # Compute aggregate metrics
    successes = sum(1 for r in results if r.success)
    success_rate = successes / len(results) if results else 0.0
    avg_nav_ms = sum(r.navigate_ms for r in results) / len(results) if results else 0
    avg_ext_ms = sum(r.extract_ms for r in results) / len(results) if results else 0
    avg_total_ms = sum(r.total_ms for r in results) / len(results) if results else 0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sites_tested": len(results),
        "successes": successes,
        "failures": len(results) - successes,
        "success_rate": round(success_rate, 2),
        "avg_navigate_ms": round(avg_nav_ms, 1),
        "avg_extract_ms": round(avg_ext_ms, 1),
        "avg_total_ms": round(avg_total_ms, 1),
        "total_benchmark_ms": round(elapsed_total, 1),
        "results": [asdict(r) for r in results],
    }

    # Persist results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)
    with open(HISTORY_FILE, "a") as f:
        summary = {k: v for k, v in report.items() if k != "results"}
        f.write(json.dumps(summary) + "\n")

    return report


def print_report(report: dict):
    """Pretty-print benchmark results."""
    print("\n" + "=" * 65)
    print("  NAVIGATION BENCHMARK RESULTS")
    print("=" * 65)
    print(f"  Timestamp:    {report['timestamp']}")
    print(f"  Sites tested: {report['sites_tested']}")
    print(f"  Success rate: {report['success_rate'] * 100:.0f}% "
          f"({report['successes']}/{report['sites_tested']})")
    print(f"  Avg navigate: {report['avg_navigate_ms']:.0f}ms")
    print(f"  Avg extract:  {report['avg_extract_ms']:.0f}ms")
    print(f"  Avg total:    {report['avg_total_ms']:.0f}ms")
    print(f"  Benchmark:    {report['total_benchmark_ms']:.0f}ms total")
    print("-" * 65)
    for r in report["results"]:
        status = "PASS" if r["success"] else "FAIL"
        print(f"  [{status}] {r['name']:<20} {r['total_ms']:>6.0f}ms  "
              f"title={r['title'][:30]!r}  chars={r['content_length']}")
        if r.get("error"):
            print(f"         error: {r['error'][:80]}")
    print("=" * 65)
    print(f"  Results saved: {RESULTS_FILE}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Navigation benchmark")
    parser.add_argument("--url", help="Benchmark a single URL")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    sites = DEFAULT_SITES
    if args.url:
        sites = [{"name": "custom", "url": args.url, "category": "custom"}]

    print("Running navigation benchmark...")
    report = await run_benchmark(sites)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    return 0 if report["success_rate"] >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

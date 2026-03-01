#!/usr/bin/env python3
"""Data Extractor — extracts tabular/structured data from web pages into JSON/CSV.

Navigates to URLs via browser, identifies tables and structured data (lists,
definition lists, key-value pairs), and outputs clean JSON or CSV.

Usage:
    python3 data_extractor.py URL                     # Extract tables → JSON
    python3 data_extractor.py URL --format csv         # Extract tables → CSV
    python3 data_extractor.py URL --output file.json   # Save to file
    python3 data_extractor.py benchmark                # Run extraction benchmark

Usage (as library):
    from data_extractor import DataExtractor
    async with DataExtractor() as de:
        result = await de.extract(url)
        print(result.tables)   # list of dicts with headers + rows
"""

import asyncio
import csv
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser_agent import BrowserAgent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RESULTS_DIR = Path("/home/agent/.openclaw/workspace/data/benchmarks")
RESULTS_FILE = RESULTS_DIR / "data_extract_results.json"
HISTORY_FILE = RESULTS_DIR / "data_extract_history.jsonl"

# JS to extract all HTML tables into structured data
TABLE_EXTRACT_JS = """
(() => {
    const tables = [];
    document.querySelectorAll('table').forEach((table, idx) => {
        // Get caption or nearest heading
        let caption = '';
        const capEl = table.querySelector('caption');
        if (capEl) {
            caption = capEl.innerText.trim();
        } else {
            // Check previous sibling headings
            let prev = table.previousElementSibling;
            for (let i = 0; i < 3 && prev; i++) {
                if (/^H[1-6]$/.test(prev.tagName)) {
                    caption = prev.innerText.trim();
                    break;
                }
                prev = prev.previousElementSibling;
            }
        }

        const rows = [];
        const headers = [];

        // Extract headers from thead or first row with th
        const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
        if (headerRow) {
            headerRow.querySelectorAll('th').forEach(th => {
                headers.push(th.innerText.trim().replace(/\\n/g, ' '));
            });
        }

        // If no th found, use first row as headers
        if (headers.length === 0 && headerRow) {
            headerRow.querySelectorAll('td').forEach(td => {
                headers.push(td.innerText.trim().replace(/\\n/g, ' '));
            });
        }

        // Extract body rows
        const bodyRows = table.querySelectorAll('tbody tr');
        const allRows = bodyRows.length > 0 ? bodyRows : table.querySelectorAll('tr');
        const startIdx = (bodyRows.length > 0) ? 0 : 1; // skip header row if no tbody

        for (let i = startIdx; i < allRows.length; i++) {
            const cells = [];
            allRows[i].querySelectorAll('td, th').forEach(cell => {
                cells.push(cell.innerText.trim().replace(/\\n/g, ' '));
            });
            if (cells.length > 0 && cells.some(c => c.length > 0)) {
                rows.push(cells);
            }
        }

        if (rows.length > 0 || headers.length > 0) {
            tables.push({
                index: idx,
                caption: caption,
                headers: headers,
                rows: rows,
                row_count: rows.length,
                col_count: Math.max(headers.length, rows.length > 0 ? rows[0].length : 0),
            });
        }
    });
    return tables;
})()
"""

# JS to extract definition lists (dl/dt/dd)
DL_EXTRACT_JS = """
(() => {
    const lists = [];
    document.querySelectorAll('dl').forEach((dl, idx) => {
        const items = [];
        let currentTerm = '';
        dl.querySelectorAll('dt, dd').forEach(el => {
            if (el.tagName === 'DT') {
                currentTerm = el.innerText.trim();
            } else if (el.tagName === 'DD') {
                items.push({term: currentTerm, definition: el.innerText.trim()});
            }
        });
        if (items.length > 0) {
            lists.push({index: idx, items: items, count: items.length});
        }
    });
    return lists;
})()
"""

# JS to extract ordered/unordered lists
LIST_EXTRACT_JS = """
(() => {
    const lists = [];
    // Only get top-level lists (not nested)
    const allLists = document.querySelectorAll('main ul, main ol, article ul, article ol, [role="main"] ul, [role="main"] ol');
    const target = allLists.length > 0 ? allLists : document.querySelectorAll('body > ul, body > ol, .content ul, .content ol');
    target.forEach((list, idx) => {
        if (idx > 20) return; // cap at 20 lists
        const items = [];
        list.querySelectorAll(':scope > li').forEach(li => {
            const text = li.innerText.trim().substring(0, 500);
            if (text.length > 0) items.push(text);
        });
        if (items.length >= 2) {
            // Get nearest heading
            let heading = '';
            let prev = list.previousElementSibling;
            for (let i = 0; i < 3 && prev; i++) {
                if (/^H[1-6]$/.test(prev.tagName)) {
                    heading = prev.innerText.trim();
                    break;
                }
                prev = prev.previousElementSibling;
            }
            lists.push({
                index: idx,
                type: list.tagName.toLowerCase(),
                heading: heading,
                items: items,
                count: items.length,
            });
        }
    });
    return lists;
})()
"""

# Benchmark sites with expected data types
BENCHMARK_SITES = [
    {
        "name": "Wikipedia - Countries by GDP",
        "url": "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)",
        "category": "wiki-table",
        "expect_tables": True,
        "min_rows": 5,
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/",
        "category": "structured-list",
        "expect_tables": True,
        "min_rows": 10,
    },
    {
        "name": "Wikipedia - Programming Languages",
        "url": "https://en.wikipedia.org/wiki/Comparison_of_programming_languages",
        "category": "wiki-table",
        "expect_tables": True,
        "min_rows": 5,
    },
    {
        "name": "Python Docs - Built-in Functions",
        "url": "https://docs.python.org/3/library/functions.html",
        "category": "api-docs",
        "expect_tables": True,
        "min_rows": 1,
    },
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class TableData:
    """A single extracted table."""
    caption: str = ""
    headers: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    row_count: int = 0
    col_count: int = 0

    def to_records(self) -> list[dict]:
        """Convert to list of dicts (one per row) using headers as keys."""
        if not self.headers:
            return [{"col_" + str(i): v for i, v in enumerate(row)} for row in self.rows]
        return [
            {self.headers[i] if i < len(self.headers) else f"col_{i}": v
             for i, v in enumerate(row)}
            for row in self.rows
        ]

    def to_csv(self) -> str:
        """Convert to CSV string."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        if self.headers:
            writer.writerow(self.headers)
        for row in self.rows:
            writer.writerow(row)
        return buf.getvalue()


@dataclass
class ExtractionResult:
    """Complete extraction result for a URL."""
    url: str
    title: str = ""
    tables: list = field(default_factory=list)       # list of TableData
    def_lists: list = field(default_factory=list)     # definition lists
    lists: list = field(default_factory=list)          # ul/ol lists
    total_tables: int = 0
    total_rows: int = 0
    elapsed_ms: float = 0
    success: bool = False
    error: Optional[str] = None

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON."""
        data = {
            "url": self.url,
            "title": self.title,
            "success": self.success,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "summary": {
                "tables": self.total_tables,
                "total_rows": self.total_rows,
                "definition_lists": len(self.def_lists),
                "lists": len(self.lists),
            },
            "tables": [
                {
                    "caption": t.caption,
                    "headers": t.headers,
                    "row_count": t.row_count,
                    "col_count": t.col_count,
                    "rows": t.rows[:50],  # cap at 50 rows in JSON output
                }
                for t in self.tables
            ],
        }
        if self.def_lists:
            data["definition_lists"] = self.def_lists
        if self.lists:
            data["lists"] = [
                {"heading": l.get("heading", ""), "type": l.get("type", ""),
                 "items": l.get("items", [])[:30]}
                for l in self.lists
            ]
        if self.error:
            data["error"] = self.error
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def to_csv(self) -> str:
        """Serialize all tables to CSV (separated by blank lines)."""
        parts = []
        for i, table in enumerate(self.tables):
            if i > 0:
                parts.append("")
            caption = table.caption or f"Table {i + 1}"
            parts.append(f"# {caption}")
            parts.append(table.to_csv().strip())
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# DataExtractor
# ---------------------------------------------------------------------------
class DataExtractor:
    """Extracts structured data from web pages via browser."""

    def __init__(self):
        self._ba: Optional[BrowserAgent] = None

    async def __aenter__(self):
        self._ba = BrowserAgent()
        await self._ba.start()
        return self

    async def __aexit__(self, *exc):
        if self._ba:
            await self._ba.stop()

    async def extract(self, url: str, timeout_ms: int = 25000) -> ExtractionResult:
        """Extract all structured data from a URL."""
        t0 = time.monotonic()

        # Navigate
        nav = await self._ba.navigate(url, timeout_ms=timeout_ms)
        if not nav.ok:
            return ExtractionResult(
                url=url, elapsed_ms=(time.monotonic() - t0) * 1000,
                error=nav.error,
            )

        title = nav.title or ""

        # Wait a moment for dynamic content
        await asyncio.sleep(0.5)

        # Extract tables
        try:
            raw_tables = await self._ba.evaluate(TABLE_EXTRACT_JS)
        except Exception as e:
            raw_tables = []

        tables = []
        total_rows = 0
        for rt in (raw_tables or []):
            td = TableData(
                caption=rt.get("caption", ""),
                headers=rt.get("headers", []),
                rows=rt.get("rows", []),
                row_count=rt.get("row_count", 0),
                col_count=rt.get("col_count", 0),
            )
            tables.append(td)
            total_rows += td.row_count

        # Extract definition lists
        try:
            def_lists = await self._ba.evaluate(DL_EXTRACT_JS) or []
        except Exception:
            def_lists = []

        # Extract lists
        try:
            lists = await self._ba.evaluate(LIST_EXTRACT_JS) or []
        except Exception:
            lists = []

        elapsed = (time.monotonic() - t0) * 1000
        success = len(tables) > 0 or len(def_lists) > 0 or len(lists) > 0

        return ExtractionResult(
            url=url, title=title, tables=tables, def_lists=def_lists,
            lists=lists, total_tables=len(tables), total_rows=total_rows,
            elapsed_ms=elapsed, success=success,
        )


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkSiteResult:
    name: str
    url: str
    category: str
    success: bool
    tables_found: int
    total_rows: int
    def_lists: int
    lists: int
    elapsed_ms: float
    meets_expectation: bool
    error: Optional[str] = None
    sample_headers: list = field(default_factory=list)


async def run_benchmark(sites: list[dict] = None) -> dict:
    """Run the data extraction benchmark."""
    sites = sites or BENCHMARK_SITES
    results: list[BenchmarkSiteResult] = []
    t_start = time.monotonic()

    async with DataExtractor() as de:
        for site in sites:
            print(f"  [{site['name']}] ... ", end="", flush=True)
            ext = await de.extract(site["url"])

            # Check expectations
            meets = True
            if site.get("expect_tables") and ext.total_tables == 0:
                meets = False
            if site.get("min_rows", 0) > ext.total_rows:
                meets = False

            # Sample headers from first table
            sample_headers = []
            if ext.tables:
                sample_headers = ext.tables[0].headers[:5]

            sr = BenchmarkSiteResult(
                name=site["name"], url=site["url"], category=site["category"],
                success=ext.success, tables_found=ext.total_tables,
                total_rows=ext.total_rows, def_lists=len(ext.def_lists),
                lists=len(ext.lists), elapsed_ms=ext.elapsed_ms,
                meets_expectation=meets, error=ext.error,
                sample_headers=sample_headers,
            )
            status = "PASS" if meets else "FAIL"
            print(f"{status} ({ext.elapsed_ms:.0f}ms, {ext.total_tables} tables, "
                  f"{ext.total_rows} rows)")
            results.append(sr)

    elapsed_total = (time.monotonic() - t_start) * 1000
    passing = sum(1 for r in results if r.meets_expectation)
    pass_rate = passing / len(results) if results else 0.0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sites_tested": len(results),
        "passing": passing,
        "failing": len(results) - passing,
        "pass_rate": round(pass_rate, 2),
        "total_benchmark_ms": round(elapsed_total, 1),
        "results": [asdict(r) for r in results],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)
    with open(HISTORY_FILE, "a") as f:
        summary = {k: v for k, v in report.items() if k != "results"}
        f.write(json.dumps(summary) + "\n")

    return report


def print_report(report: dict):
    """Pretty-print benchmark results."""
    print("\n" + "=" * 70)
    print("  DATA EXTRACTION BENCHMARK RESULTS")
    print("=" * 70)
    print(f"  Timestamp:    {report['timestamp']}")
    print(f"  Sites tested: {report['sites_tested']}")
    print(f"  Pass rate:    {report['pass_rate'] * 100:.0f}% "
          f"({report['passing']}/{report['sites_tested']})")
    print(f"  Benchmark:    {report['total_benchmark_ms']:.0f}ms total")
    print("-" * 70)
    for r in report["results"]:
        status = "PASS" if r["meets_expectation"] else "FAIL"
        print(f"  [{status}] {r['name']:<35} {r['elapsed_ms']:>6.0f}ms  "
              f"tables={r['tables_found']}  rows={r['total_rows']}")
        if r.get("sample_headers"):
            print(f"         headers: {r['sample_headers']}")
        if r.get("error"):
            print(f"         error: {r['error'][:80]}")
    print("=" * 70)
    print(f"  Results saved: {RESULTS_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract structured data from URLs")
    parser.add_argument("url", help="URL to extract from, or 'benchmark'")
    parser.add_argument("--format", choices=["json", "csv"], default="json",
                        help="Output format (default: json)")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--all", action="store_true",
                        help="Include lists and definition lists in output")
    args = parser.parse_args()

    if args.url == "benchmark":
        print("Running data extraction benchmark...")
        report = await run_benchmark()
        print_report(report)
        return 0 if report["pass_rate"] >= 0.75 else 1

    # Single URL extraction
    print(f"Extracting from: {args.url}", file=sys.stderr)
    async with DataExtractor() as de:
        result = await de.extract(args.url)

    if not result.success:
        print(f"FAIL: {result.error or 'No structured data found'}", file=sys.stderr)
        # Still output what we got
        if result.lists or result.def_lists:
            print(result.to_json())
            return 0
        return 1

    if args.format == "csv":
        output = result.to_csv()
    else:
        output = result.to_json()

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)

    print(f"\nExtracted {result.total_tables} tables, {result.total_rows} rows "
          f"in {result.elapsed_ms:.0f}ms", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

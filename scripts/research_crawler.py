#!/usr/bin/env python3
"""
research_crawler.py — Crawl4AI wrapper for automated research ingestion.

Crawls URLs to clean markdown, optionally stores in ClarvisDB brain.
Designed to supplement the existing cron_research.sh pipeline.

Usage:
    python3 research_crawler.py crawl <url>                  # Crawl URL → stdout markdown
    python3 research_crawler.py crawl <url> --save <file>    # Crawl URL → file
    python3 research_crawler.py ingest <url> [--importance 0.7]  # Crawl + store in brain
    python3 research_crawler.py batch <urls_file>            # Crawl multiple URLs from file
    python3 research_crawler.py status                       # Show crawl stats

Library:
    from research_crawler import crawl_url, crawl_and_ingest
    md = await crawl_url("https://example.com")
    result = await crawl_and_ingest("https://arxiv.org/abs/...", importance=0.7)
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
TRACKER_PATH = os.path.join(WORKSPACE, "data", "research_crawled.json")
RESEARCH_DIR = os.path.join(WORKSPACE, "memory", "research")
MAX_CONTENT_LENGTH = 50000  # Truncate very long pages


def _load_tracker() -> dict:
    """Load crawl tracker (hash-based dedup)."""
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH) as f:
            return json.load(f)
    return {"crawled": {}, "stats": {"total": 0, "ingested": 0, "errors": 0}}


def _save_tracker(tracker: dict):
    """Save crawl tracker."""
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def crawl_url(url: str, timeout: int = 60) -> Optional[str]:
    """Crawl a URL and return clean markdown content.

    Returns None on failure.
    """
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        logger.error("crawl4ai not installed: pip install crawl4ai")
        return None

    # Use existing Chromium CDP instance if available (port 18800),
    # otherwise launch a new headless browser
    cdp_url = os.environ.get("CRAWL4AI_CDP_URL")
    if not cdp_url:
        # Check if Clarvis's Chromium is running on CDP port
        try:
            import requests as _req
            r = _req.get("http://127.0.0.1:18800/json/version", timeout=2)
            if r.status_code == 200:
                cdp_url = "http://127.0.0.1:18800"
        except Exception:
            pass

    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        cdp_url=cdp_url,
    )
    crawl_config = CrawlerRunConfig(
        word_count_threshold=50,
        excluded_tags=["nav", "footer", "header", "aside"],
        exclude_external_links=True,
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)

            if not result.success:
                logger.error(f"Crawl failed for {url}: {result.error_message}")
                return None

            markdown = result.markdown_v2.raw_markdown if hasattr(result, 'markdown_v2') and result.markdown_v2 else result.markdown
            if not markdown:
                logger.warning(f"No markdown content from {url}")
                return None

            # Truncate very long content
            if len(markdown) > MAX_CONTENT_LENGTH:
                markdown = markdown[:MAX_CONTENT_LENGTH] + "\n\n[... truncated ...]"

            return markdown

    except Exception as e:
        logger.error(f"Crawl error for {url}: {e}")
        return None


async def crawl_and_ingest(url: str, importance: float = 0.7) -> dict:
    """Crawl URL and store key content in ClarvisDB brain.

    Returns: {success, url, hash, chars, error}
    """
    tracker = _load_tracker()
    url_h = _url_hash(url)

    # Dedup check
    if url_h in tracker["crawled"]:
        return {"success": True, "url": url, "hash": url_h, "chars": 0, "note": "already_ingested"}

    markdown = await crawl_url(url)
    if not markdown:
        tracker["stats"]["errors"] += 1
        _save_tracker(tracker)
        return {"success": False, "url": url, "error": "crawl_failed"}

    # Save raw markdown to research dir
    slug = url_h[:8]
    date_str = time.strftime("%Y-%m-%d")
    filename = f"{date_str}-crawl-{slug}.md"
    filepath = os.path.join(RESEARCH_DIR, filename)
    os.makedirs(RESEARCH_DIR, exist_ok=True)

    with open(filepath, "w") as f:
        f.write(f"# Crawled: {url}\n\n")
        f.write(f"Date: {date_str}\n\n")
        f.write(markdown)

    # Store in brain
    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from brain import remember

        # Extract title from first heading or URL
        title = url
        for line in markdown.split("\n")[:10]:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Store a summary entry
        summary = markdown[:500].replace("\n", " ").strip()
        remember(
            f"Research crawl [{title}]: {summary}",
            importance=importance,
        )
        logger.info(f"Stored in brain: {title}")
    except Exception as e:
        logger.warning(f"Brain storage failed (markdown still saved): {e}")

    # Update tracker
    tracker["crawled"][url_h] = {
        "url": url,
        "date": date_str,
        "file": filename,
        "chars": len(markdown),
    }
    tracker["stats"]["total"] += 1
    tracker["stats"]["ingested"] += 1
    _save_tracker(tracker)

    return {"success": True, "url": url, "hash": url_h, "chars": len(markdown), "file": filename}


async def batch_crawl(urls: list, importance: float = 0.7) -> list:
    """Crawl multiple URLs sequentially (avoids browser overload)."""
    results = []
    for url in urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        result = await crawl_and_ingest(url, importance=importance)
        results.append(result)
        print(f"  {'OK' if result['success'] else 'FAIL'}: {url} ({result.get('chars', 0)} chars)")
    return results


def cmd_status():
    """Show crawl statistics."""
    tracker = _load_tracker()
    stats = tracker["stats"]
    crawled = tracker["crawled"]
    print(f"Crawl4AI Research Crawler Status")
    print(f"  Total crawled: {stats['total']}")
    print(f"  Ingested:      {stats['ingested']}")
    print(f"  Errors:        {stats['errors']}")
    print(f"  Tracked URLs:  {len(crawled)}")
    if crawled:
        recent = sorted(crawled.values(), key=lambda x: x.get("date", ""), reverse=True)[:5]
        print(f"\nRecent crawls:")
        for entry in recent:
            print(f"  {entry['date']} | {entry['chars']:>6} chars | {entry['url'][:80]}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawl4AI research crawler")
    parser.add_argument("command", choices=["crawl", "ingest", "batch", "status"])
    parser.add_argument("target", nargs="?", help="URL or file path")
    parser.add_argument("--save", help="Save markdown to file")
    parser.add_argument("--importance", type=float, default=0.7)
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "crawl":
        if not args.target:
            parser.error("URL required for crawl")
        md = asyncio.run(crawl_url(args.target))
        if md:
            if args.save:
                with open(args.save, "w") as f:
                    f.write(md)
                print(f"Saved {len(md)} chars to {args.save}")
            else:
                print(md)
        else:
            print("Crawl failed", file=sys.stderr)
            sys.exit(1)
    elif args.command == "ingest":
        if not args.target:
            parser.error("URL required for ingest")
        result = asyncio.run(crawl_and_ingest(args.target, importance=args.importance))
        print(json.dumps(result, indent=2))
    elif args.command == "batch":
        if not args.target:
            parser.error("File path required for batch")
        with open(args.target) as f:
            urls = f.readlines()
        results = asyncio.run(batch_crawl(urls, importance=args.importance))
        ok = sum(1 for r in results if r["success"])
        print(f"\nBatch complete: {ok}/{len(results)} succeeded")

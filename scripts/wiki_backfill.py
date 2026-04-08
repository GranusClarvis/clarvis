#!/usr/bin/env python3
"""Wiki backfill — curate and ingest the first useful corpus from existing material.

Sources (in priority order):
  1. memory/research/ingested/*.md  — research notes (high-value, curated)
  2. memory/research/*.md           — standalone research docs
  3. docs/ selected files           — key architecture/design docs

Does NOT bulk-import everything. Applies quality filters:
  - Minimum content length (500 chars)
  - Excludes crawl/test artifacts
  - Excludes files already in the wiki source registry
  - Caps at a configurable batch size

Usage:
    python3 wiki_backfill.py scan                    # Preview what would be ingested
    python3 wiki_backfill.py run [--limit 30]        # Ingest + compile the first batch
    python3 wiki_backfill.py run --compile-only       # Compile already-ingested but unlinked
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
SOURCES_JSONL = KNOWLEDGE / "logs" / "sources.jsonl"
RESEARCH_DIR = WORKSPACE / "memory" / "research"
RESEARCH_INGESTED = RESEARCH_DIR / "ingested"
DOCS_DIR = WORKSPACE / "docs"

TODAY = datetime.date.today().isoformat()

# Files to skip (test artifacts, junk)
SKIP_PATTERNS = [
    re.compile(r'crawl-', re.I),
    re.compile(r'example\.com', re.I),
    re.compile(r'httpbin', re.I),
    re.compile(r'test[-_]', re.I),
]

# High-value docs worth importing from docs/
CURATED_DOCS = [
    "knowledge/llm_wiki_architecture.md",
    "ADAPTIVE_RAG_PLAN.md",
    "GRAPH_SQLITE_CUTOVER_2026-03-29.md",
]

MIN_CONTENT_LENGTH = 500


def _read_existing_registry() -> set[str]:
    """Read source registry to find already-ingested file paths."""
    seen = set()
    if SOURCES_JSONL.exists():
        with open(SOURCES_JSONL) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    # Track raw_path and source_url
                    rp = rec.get("raw_path", "")
                    if rp:
                        seen.add(rp)
                    su = rec.get("source_url", "")
                    if su:
                        seen.add(su)
                    # Also track by title to avoid re-ingesting
                    t = rec.get("title", "")
                    if t:
                        seen.add(t.lower().strip())
                except json.JSONDecodeError:
                    continue
    return seen


def _is_skip(filename: str) -> bool:
    for pat in SKIP_PATTERNS:
        if pat.search(filename):
            return True
    return False


def _detect_source_type(filepath: Path, content: str) -> str:
    """Detect source type from file content heuristics."""
    name = filepath.name.lower()
    cl = content.lower()
    if "arxiv" in cl or "abstract" in cl or "paper" in name:
        return "paper"
    if "repo" in name or "github" in cl or "repository" in cl:
        return "repo"
    return "web"  # default for markdown research notes


def _extract_title(filepath: Path, content: str) -> str:
    """Extract title from markdown file."""
    for line in content.split("\n")[:10]:
        line = line.strip()
        if line.startswith("# ") and not line.startswith("##"):
            return line[2:].strip()
    # Fallback: filename
    return filepath.stem.replace("-", " ").replace("_", " ").title()


def scan_candidates(limit: int = 50) -> list[dict]:
    """Scan for backfill candidates from research/ and docs/. Returns sorted list."""
    existing = _read_existing_registry()
    candidates = []

    # 1. Research ingested notes (highest priority)
    if RESEARCH_INGESTED.exists():
        for md in sorted(RESEARCH_INGESTED.glob("*.md")):
            if _is_skip(md.name):
                continue
            content = md.read_text(encoding="utf-8", errors="replace")
            if len(content.strip()) < MIN_CONTENT_LENGTH:
                continue
            # Check if already ingested
            rel_path = str(md.relative_to(WORKSPACE))
            title = _extract_title(md, content)
            if rel_path in existing or title.lower().strip() in existing:
                continue
            candidates.append({
                "path": md,
                "rel_path": rel_path,
                "title": title,
                "source_type": _detect_source_type(md, content),
                "size": len(content),
                "origin": "research/ingested",
                "priority": 1,
            })

    # 2. Research root docs
    for md in sorted(RESEARCH_DIR.glob("*.md")):
        if md.name == "README.md":
            continue
        content = md.read_text(encoding="utf-8", errors="replace")
        if len(content.strip()) < MIN_CONTENT_LENGTH:
            continue
        rel_path = str(md.relative_to(WORKSPACE))
        title = _extract_title(md, content)
        if rel_path in existing or title.lower().strip() in existing:
            continue
        candidates.append({
            "path": md,
            "rel_path": rel_path,
            "title": title,
            "source_type": _detect_source_type(md, content),
            "size": len(content),
            "origin": "research",
            "priority": 2,
        })

    # 3. Curated docs
    for doc_name in CURATED_DOCS:
        doc_path = DOCS_DIR / doc_name if not doc_name.startswith("knowledge/") else WORKSPACE / "docs" / doc_name
        if not doc_path.exists():
            # Try alternative locations
            alt = WORKSPACE / doc_name
            if alt.exists():
                doc_path = alt
            else:
                continue
        content = doc_path.read_text(encoding="utf-8", errors="replace")
        if len(content.strip()) < MIN_CONTENT_LENGTH:
            continue
        rel_path = str(doc_path.relative_to(WORKSPACE))
        title = _extract_title(doc_path, content)
        if rel_path in existing or title.lower().strip() in existing:
            continue
        candidates.append({
            "path": doc_path,
            "rel_path": rel_path,
            "title": title,
            "source_type": "web",
            "size": len(content),
            "origin": "docs",
            "priority": 3,
        })

    # Sort by priority then size descending (larger = more substantial)
    candidates.sort(key=lambda c: (c["priority"], -c["size"]))
    return candidates[:limit]


def backfill_ingest(candidates: list[dict], dry_run: bool = False) -> list[dict]:
    """Ingest candidates through the wiki pipeline. Returns results."""
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from wiki_ingest import ingest_file

    results = []

    for cand in candidates:
        if dry_run:
            results.append({
                "title": cand["title"],
                "action": "would_ingest",
                "origin": cand["origin"],
                "size": cand["size"],
                "type": cand["source_type"],
            })
            continue

        try:
            record = ingest_file(
                str(cand["path"]),
                source_type=cand["source_type"],
            )
            results.append({
                "title": cand["title"],
                "action": "ingested",
                "source_id": record.get("source_id", "?"),
                "origin": cand["origin"],
            })
        except Exception as e:
            results.append({
                "title": cand["title"],
                "action": "error",
                "reason": str(e)[:200],
                "origin": cand["origin"],
            })

    return results


def backfill_compile(dry_run: bool = False) -> list[dict]:
    """Compile all pending (ingested but unlinked) sources into wiki pages."""
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from wiki_compile import compile_all_pending
    return compile_all_pending(dry_run=dry_run)


def backfill_sync(dry_run: bool = False) -> list[dict]:
    """Sync newly created/updated wiki pages into ClarvisDB."""
    sys.path.insert(0, str(WORKSPACE / "scripts"))
    from wiki_brain_sync import sync_changed, sync_all
    # Sync all since backfill creates pages with today's date
    return sync_changed(dry_run=dry_run)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Wiki backfill from existing corpus")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Preview backfill candidates")
    p_scan.add_argument("--limit", type=int, default=50)

    p_run = sub.add_parser("run", help="Run backfill pipeline")
    p_run.add_argument("--limit", type=int, default=30, help="Max files to ingest")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--compile-only", action="store_true",
                       help="Skip ingest, only compile pending sources")
    p_run.add_argument("--no-sync", action="store_true",
                       help="Skip brain sync after compile")

    args = parser.parse_args()

    if args.command == "scan":
        candidates = scan_candidates(limit=args.limit)
        if not candidates:
            print("No backfill candidates found.")
            return
        print(f"Found {len(candidates)} candidates:\n")
        for i, c in enumerate(candidates, 1):
            print(f"  {i:3d}. [{c['source_type']:6s}] {c['title'][:60]:60s}  "
                  f"({c['size']:,d} chars)  [{c['origin']}]")
        print(f"\nTotal: {len(candidates)} files, "
              f"{sum(c['size'] for c in candidates):,d} chars")

    elif args.command == "run":
        if args.compile_only:
            print("Compiling pending sources...")
            results = backfill_compile(dry_run=args.dry_run)
            created = sum(1 for r in results if r.get("action") in ("created", "would_create"))
            updated = sum(1 for r in results if r.get("action") in ("updated", "would_update"))
            failed = sum(1 for r in results if r.get("action") == "failed")
            print(f"Compile: {created} created, {updated} updated, {failed} failed")
            return

        # Step 1: Scan
        candidates = scan_candidates(limit=args.limit)
        if not candidates:
            print("No backfill candidates found.")
            return

        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"{prefix}Ingesting {len(candidates)} files...\n")

        # Step 2: Ingest
        ingest_results = backfill_ingest(candidates, dry_run=args.dry_run)
        ingested = sum(1 for r in ingest_results if r["action"] == "ingested")
        errors = sum(1 for r in ingest_results if r["action"] == "error")
        for r in ingest_results:
            icon = {"ingested": "+", "would_ingest": "~", "error": "!"}.get(r["action"], "?")
            print(f"  [{icon}] {r['title'][:60]}  ({r['action']})")
        print(f"\n{prefix}Ingest: {ingested} ingested, {errors} errors")

        if args.dry_run:
            return

        # Step 3: Compile
        print("\nCompiling into wiki pages...")
        compile_results = backfill_compile()
        created = sum(1 for r in compile_results if r.get("action") == "created")
        updated = sum(1 for r in compile_results if r.get("action") == "updated")
        for r in compile_results:
            if r.get("action") in ("created", "updated"):
                print(f"  [{r['action'][0].upper()}] {r.get('slug', '?')}")
        print(f"Compile: {created} created, {updated} updated")

        # Step 4: Brain sync
        if not args.no_sync:
            print("\nSyncing to ClarvisDB...")
            sync_results = backfill_sync()
            synced = sum(1 for r in sync_results if r.get("action") == "synced")
            print(f"Brain sync: {synced} pages synced")

        print(f"\nBackfill complete: {ingested} ingested, {created} new pages, "
              f"{updated} updated pages")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

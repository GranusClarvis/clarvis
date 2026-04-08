#!/usr/bin/env python3
"""Wiki compile engine — turns raw source notes into durable wiki pages.

Reads source registry records, applies promotion quality gates, creates new
wiki pages from templates or updates existing canonical pages. Maintains
backlinks and a short change log per page.

Usage:
    python3 wiki_compile.py compile --source-id <id>       # Compile one source
    python3 wiki_compile.py compile --all-pending           # Compile all unlinked sources
    python3 wiki_compile.py compile --dry-run               # Preview without writing
    python3 wiki_compile.py status                          # Show compile pipeline status
    python3 wiki_compile.py backlinks                       # Refresh all backlinks
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
WIKI_DIR = KNOWLEDGE / "wiki"
RAW_DIR = KNOWLEDGE / "raw"
LOGS_DIR = KNOWLEDGE / "logs"
SOURCES_JSONL = LOGS_DIR / "sources.jsonl"
TEMPLATES_DIR = KNOWLEDGE / "schema" / "templates"

TODAY = datetime.date.today().isoformat()

# Type to wiki directory mapping
TYPE_DIR_MAP = {
    "paper": "concepts",   # papers go in concepts/ per schema_rules.md
    "repo": "projects",
    "web": "concepts",
    "transcript": "concepts",
}


# ============================================================
# Source Registry (read-only access — writes go through wiki_ingest.py)
# ============================================================

def read_registry() -> list[dict]:
    if not SOURCES_JSONL.exists():
        return []
    records = []
    with open(SOURCES_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def update_registry_record(source_id: str, updates: dict) -> bool:
    """Update a record in the JSONL by rewriting the file."""
    records = read_registry()
    found = False
    for r in records:
        if r.get("source_id") == source_id:
            r.update(updates)
            found = True
            break
    if not found:
        return False
    with open(SOURCES_JSONL, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return True


# ============================================================
# Wiki Page Scanner
# ============================================================

def scan_existing_pages() -> dict[str, dict]:
    """Scan all wiki pages, return {slug: {path, title, type, sources, aliases}}."""
    pages = {}
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        if not fm:
            continue
        slug = fm.get("slug", md_file.stem)
        pages[slug] = {
            "path": md_file,
            "title": fm.get("title", slug),
            "type": fm.get("type", "concept"),
            "sources": fm.get("sources", []),
            "aliases": fm.get("aliases", []),
            "status": fm.get("status", "draft"),
            "tags": fm.get("tags", []),
        }
    return pages


def _parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file (simple parser, no PyYAML needed)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm_text = text[3:end].strip()
    result = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        # List item
        if line.strip().startswith("- ") and current_key:
            val = line.strip()[2:].strip().strip('"').strip("'")
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(val)
            continue

        # Key-value
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
        if m:
            current_key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            current_list = None
            if val.startswith("[") and val.endswith("]"):
                # Inline list
                items = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                result[current_key] = items
            elif val:
                result[current_key] = val
            else:
                result[current_key] = ""
                current_list = []
                result[current_key] = current_list

    return result


# ============================================================
# Quality Gates (from promotion_policy.md)
# ============================================================

def check_quality_gates(record: dict, raw_text: str) -> list[str]:
    """Check promotion quality gates. Returns list of failures (empty = pass)."""
    failures = []
    source_type = record.get("source_type", "")

    # Gate 1: Atomicity — raw source should cover a focused topic
    # (Heuristic: if we can extract a title, it's probably atomic enough)
    title = record.get("title", "")
    if not title or title == "Untitled":
        failures.append("Gate 1 (Atomicity): No title extracted — cannot determine topic focus")

    # Gate 2: Source citation — the raw file itself is the source
    if not record.get("raw_path"):
        failures.append("Gate 2 (Citation): No raw file path recorded")

    # Gate 3: Self-containment — check minimum content length
    content_len = len(raw_text.strip()) if raw_text else 0
    if content_len < 100:
        failures.append(f"Gate 3 (Self-containment): Content too short ({content_len} chars)")

    # Gate 5: Non-duplication — checked during compile (existing page lookup)
    # Gate 6: Minimum substance
    if source_type == "paper":
        # Should have at least some abstract or extracted text
        if "abstract" not in raw_text.lower() and content_len < 500:
            failures.append("Gate 6 (Substance): Paper lacks abstract or sufficient content")
    elif source_type == "repo":
        if "readme" not in raw_text.lower() and "structure" not in raw_text.lower():
            failures.append("Gate 6 (Substance): Repo analysis lacks README or structure")

    return failures


# ============================================================
# Page Generators
# ============================================================

def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60]


def generate_repo_page(record: dict, raw_text: str) -> tuple[str, str]:
    """Generate a repo wiki page from a raw repo analysis. Returns (slug, content)."""
    title = record.get("title", "Unknown Repo")
    slug = _slugify(title)
    meta = record.get("meta", {})
    canonical_url = meta.get("canonical_url", record.get("source_url", ""))
    languages = meta.get("languages", [])
    raw_path = record.get("raw_path", "")

    # Extract description and structure from raw text
    description = ""
    structure = ""
    notable = ""
    readme_section = ""

    sections = _split_sections(raw_text)
    for sec_title, sec_body in sections:
        lower = sec_title.lower()
        if lower.startswith(title.lower()):
            description = sec_body.strip()[:500]
        elif "structure" in lower:
            structure = sec_body.strip()[:1000]
        elif "notable" in lower:
            notable = sec_body.strip()[:800]
        elif "readme" in lower:
            readme_section = sec_body.strip()[:2000]

    if not description and readme_section:
        # Take first paragraph of README section
        for para in readme_section.split("\n\n"):
            if para.strip() and not para.strip().startswith("#"):
                description = para.strip()[:500]
                break

    langs_yaml = json.dumps(languages) if languages else '["Unknown"]'
    langs_str = ", ".join(languages) if languages else "Unknown"

    content = f"""---
title: "{title}"
slug: "{slug}"
type: repo
created: {TODAY}
updated: {TODAY}
status: draft
tags:
  - project/{_slugify(title)}
aliases: []
sources:
  - {canonical_url}
  - {raw_path}
confidence: medium
repo_url: "{canonical_url}"
language: {langs_yaml}
maintained: true
---

# {title}

{description or f'Repository at {canonical_url}.'}

## Key Claims

- **Purpose**: {description[:200] if description else 'See README for details.'} [Source: README]
- **Languages**: {langs_str}. [Source: file analysis]
- **Status**: Active repository. [Source: GitHub]

## Evidence

- **[README]**: Project description and usage. [{canonical_url}]
- **[Analysis]**: Local analysis snapshot. [{raw_path}]

## Architecture

{structure or '_See raw analysis for repository structure._'}

## Notable Patterns

{notable or '_To be identified during review._'}

## Integration Points

_How this repo relates to Clarvis or other tracked projects — to be assessed._

## Related Pages

_No related pages linked yet._

## Open Questions

- What are the main architectural decisions and trade-offs?
- Are there reusable patterns or libraries worth adopting?
- How does this relate to Clarvis's architecture or goals?

## Update History

- {TODAY}: Initial page created from repo ingest ({record.get('source_id', 'unknown')}).
"""
    return slug, content


def generate_paper_page(record: dict, raw_text: str) -> tuple[str, str]:
    """Generate a paper wiki page. Returns (slug, content)."""
    title = record.get("title", "Unknown Paper")
    slug = _slugify(title)
    meta = record.get("meta", {})
    raw_path = record.get("raw_path", "")
    source_url = record.get("source_url", "")
    authors = meta.get("authors", [])
    year = meta.get("year", TODAY[:4])
    arxiv = meta.get("arxiv", "")

    # Extract abstract from raw text
    abstract = ""
    sections = _split_sections(raw_text)
    for sec_title, sec_body in sections:
        if "abstract" in sec_title.lower():
            abstract = sec_body.strip()[:2000]
            break

    if not abstract:
        # Try to grab from between title and first heading
        lines = raw_text.split("\n")
        in_abstract = False
        abs_lines = []
        for line in lines:
            if "abstract" in line.lower():
                in_abstract = True
                continue
            if in_abstract:
                if line.strip().startswith("##"):
                    break
                abs_lines.append(line)
        if abs_lines:
            abstract = "\n".join(abs_lines).strip()[:2000]

    authors_yaml = json.dumps(authors[:5]) if authors else '["Unknown"]'
    authors_str = "; ".join(authors[:3]) if authors else "Unknown"

    content = f"""---
title: "{title}"
slug: "{slug}"
type: paper
created: {TODAY}
updated: {TODAY}
status: draft
tags:
  - research/paper
aliases: []
sources:
  - {raw_path}
  - {source_url}
confidence: medium
authors: {authors_yaml}
year: {year}
venue: "Unknown"
arxiv: "{arxiv}"
---

# {title}

{abstract[:500] if abstract else f'Paper: {title}.'}

## Key Claims

- _Claims pending extraction from full paper text._

## Evidence

- **[Primary]**: The paper itself. [{source_url}]
- **[Raw]**: Ingested summary. [{raw_path}]

## Method

_To be extracted from paper._

## Results

_To be extracted from paper._

## Relevance to Clarvis

_To be assessed — how does this paper connect to Clarvis's architecture, goals, or open problems?_

## Limitations

_To be extracted from paper._

## Related Pages

_No related pages linked yet._

## Open Questions

- What are the main contributions beyond prior work?
- Which claims are directly testable in Clarvis's architecture?
- Are there follow-up papers or implementations to track?

## Update History

- {TODAY}: Initial page created from paper ingest ({record.get('source_id', 'unknown')}).
"""
    return slug, content


def generate_concept_page(record: dict, raw_text: str) -> tuple[str, str]:
    """Generate a concept wiki page from a web or generic source. Returns (slug, content)."""
    title = record.get("title", "Unknown Concept")
    slug = _slugify(title)
    raw_path = record.get("raw_path", "")
    source_url = record.get("source_url", "")
    concepts = record.get("concepts", [])

    # Extract first meaningful paragraph as summary
    summary = ""
    for para in raw_text.split("\n\n"):
        stripped = para.strip()
        if stripped and not stripped.startswith("---") and not stripped.startswith("#") and len(stripped) > 50:
            summary = stripped[:500]
            break

    tags_str = "\n".join(f"  - {t}" for t in (concepts[:3] if concepts else ["research/general"]))

    content = f"""---
title: "{title}"
slug: "{slug}"
type: concept
created: {TODAY}
updated: {TODAY}
status: draft
tags:
{tags_str}
aliases: []
sources:
  - {raw_path}
  - {source_url}
confidence: medium
---

# {title}

{summary or f'Concept derived from: {title}.'}

## Key Claims

- _Claims pending extraction from source material._

## Evidence

- **[Source]**: {title}. [{source_url or raw_path}]

## Related Pages

_No related pages linked yet._

## Open Questions

- What are the key implications of this concept?
- How does this relate to Clarvis's architecture or goals?

## Update History

- {TODAY}: Initial page created from source ingest ({record.get('source_id', 'unknown')}).
"""
    return slug, content


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown text into (heading, body) sections."""
    sections = []
    current_heading = ""
    current_body: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## ") or line.startswith("# "):
            if current_heading or current_body:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line)

    if current_heading or current_body:
        sections.append((current_heading, "\n".join(current_body)))

    return sections


# ============================================================
# Update Existing Page
# ============================================================

def update_existing_page(page_info: dict, record: dict, raw_text: str, dry_run: bool = False) -> str:
    """Add a new source to an existing wiki page. Returns description of changes."""
    page_path: Path = page_info["path"]
    existing = page_path.read_text(encoding="utf-8", errors="replace")
    raw_path = record.get("raw_path", "")
    source_url = record.get("source_url", "")
    source_id = record.get("source_id", "unknown")

    changes = []

    # Add source to frontmatter sources list
    new_source = source_url or raw_path
    if new_source and new_source not in existing:
        # Find the sources: section in frontmatter and append
        if "sources:" in existing:
            existing = existing.replace(
                "sources:\n",
                f"sources:\n  - {new_source}\n",
                1,
            )
            changes.append(f"Added source: {new_source}")

    # Add to Evidence section
    evidence_marker = "## Evidence"
    if evidence_marker in existing:
        new_evidence = f"\n- **[{record.get('source_type', 'Source')}]**: {record.get('title', 'New source')}. [{new_source}]"
        existing = existing.replace(evidence_marker, evidence_marker + new_evidence, 1)
        changes.append("Added evidence entry")

    # Update the Update History
    history_marker = "## Update History"
    if history_marker in existing:
        new_entry = f"\n- {TODAY}: Added source from {source_id}."
        existing = existing.replace(history_marker, history_marker + new_entry, 1)
        changes.append("Added update history entry")

    # Update the 'updated' date in frontmatter
    existing = re.sub(r'updated: \d{4}-\d{2}-\d{2}', f'updated: {TODAY}', existing, count=1)

    if changes and not dry_run:
        page_path.write_text(existing, encoding="utf-8")

    return "; ".join(changes) if changes else "No changes needed"


# ============================================================
# Backlink Refresh
# ============================================================

def refresh_backlinks() -> int:
    """Scan all wiki pages and ensure bidirectional links. Returns count of fixes."""
    pages = scan_existing_pages()
    # Build link graph: who links to whom
    links: dict[str, set[str]] = {slug: set() for slug in pages}

    for slug, info in pages.items():
        text = info["path"].read_text(encoding="utf-8", errors="replace")
        # Find markdown links to other wiki pages
        for m in re.finditer(r'\[([^\]]+)\]\(\.\.?/\w+/([^)]+?)\.md\)', text):
            target_slug = m.group(2)
            if target_slug in pages:
                links[slug].add(target_slug)

    # Check reverse links
    fixes = 0
    for slug, targets in links.items():
        for target in targets:
            if slug not in links.get(target, set()):
                # target page doesn't link back to slug — add backlink
                target_path = pages[target]["path"]
                text = target_path.read_text(encoding="utf-8", errors="replace")
                if "## Related Pages" in text:
                    source_title = pages[slug]["title"]
                    source_type_dir = TYPE_DIR_MAP.get(pages[slug]["type"], "concepts")
                    backlink = f"\n- [{source_title}](../{source_type_dir}/{slug}.md) — backlink"
                    text = text.replace("## Related Pages", "## Related Pages" + backlink, 1)
                    target_path.write_text(text, encoding="utf-8")
                    fixes += 1

    return fixes


# ============================================================
# Compile Pipeline
# ============================================================

def compile_source(record: dict, existing_pages: dict, dry_run: bool = False) -> dict:
    """Compile a single source registry record into a wiki page.

    Returns {action: created|updated|skipped|failed, slug, reason, gate_failures}.
    """
    source_id = record.get("source_id", "unknown")
    source_type = record.get("source_type", "web")
    raw_path = record.get("raw_path", "")

    # Skip already-linked sources
    if record.get("linked_pages"):
        return {"action": "skipped", "slug": "", "reason": "Already linked to wiki pages"}

    # Read raw content
    raw_text = ""
    if raw_path:
        full_path = KNOWLEDGE / raw_path
        if full_path.exists():
            raw_text = full_path.read_text(encoding="utf-8", errors="replace")
        else:
            return {"action": "failed", "slug": "", "reason": f"Raw file not found: {raw_path}"}

    # Quality gates
    gate_failures = check_quality_gates(record, raw_text)
    if gate_failures:
        return {
            "action": "failed",
            "slug": "",
            "reason": "Quality gate failures",
            "gate_failures": gate_failures,
        }

    # Determine target slug and check for existing pages
    title = record.get("title", "")
    candidate_slug = _slugify(title)

    # Check if a page with this slug or matching alias already exists
    matched_slug = None
    for slug, info in existing_pages.items():
        if slug == candidate_slug:
            matched_slug = slug
            break
        if title.lower() in [a.lower() for a in info.get("aliases", [])]:
            matched_slug = slug
            break

    if matched_slug:
        # Update existing page
        if dry_run:
            return {"action": "would_update", "slug": matched_slug, "reason": "Existing page found"}
        changes = update_existing_page(existing_pages[matched_slug], record, raw_text, dry_run=False)
        # Update registry to mark as linked
        update_registry_record(source_id, {"linked_pages": [matched_slug]})
        return {"action": "updated", "slug": matched_slug, "reason": changes}

    # Generate new page
    if source_type == "repo":
        slug, content = generate_repo_page(record, raw_text)
    elif source_type == "paper":
        slug, content = generate_paper_page(record, raw_text)
    else:
        slug, content = generate_concept_page(record, raw_text)

    # Determine destination directory
    type_dir = TYPE_DIR_MAP.get(source_type, "concepts")
    dest_dir = WIKI_DIR / type_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{slug}.md"

    # Final dedup check — file might exist without being in our scan
    if dest_path.exists() and not dry_run:
        changes = update_existing_page(
            {"path": dest_path, "title": title, "type": source_type},
            record, raw_text, dry_run=False,
        )
        update_registry_record(source_id, {"linked_pages": [slug]})
        return {"action": "updated", "slug": slug, "reason": f"File existed: {changes}"}

    if dry_run:
        return {"action": "would_create", "slug": slug, "reason": f"New {source_type} page"}

    dest_path.write_text(content, encoding="utf-8")
    update_registry_record(source_id, {"linked_pages": [slug]})

    return {"action": "created", "slug": slug, "reason": f"New {source_type} page at {type_dir}/{slug}.md"}


def compile_all_pending(dry_run: bool = False) -> list[dict]:
    """Compile all unlinked source records into wiki pages."""
    records = read_registry()
    existing_pages = scan_existing_pages()
    results = []

    for record in records:
        if record.get("status") != "ingested":
            continue
        if record.get("linked_pages"):
            continue
        result = compile_source(record, existing_pages, dry_run=dry_run)
        result["source_id"] = record.get("source_id", "?")
        result["title"] = record.get("title", "?")
        results.append(result)

        # Refresh existing_pages if we created a new page
        if result["action"] == "created":
            existing_pages = scan_existing_pages()

    return results


def compile_one(source_id: str, dry_run: bool = False) -> dict:
    """Compile a single source by ID."""
    records = read_registry()
    record = None
    for r in records:
        if r.get("source_id") == source_id:
            record = r
            break
    if not record:
        return {"action": "failed", "slug": "", "reason": f"Source not found: {source_id}"}

    existing_pages = scan_existing_pages()
    result = compile_source(record, existing_pages, dry_run=dry_run)
    result["source_id"] = source_id
    result["title"] = record.get("title", "?")
    return result


# ============================================================
# CLI
# ============================================================

def cmd_compile(args):
    if args.source_id:
        result = compile_one(args.source_id, dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"{prefix}{result['action'].upper()}: {result.get('title', '?')}")
        print(f"  Slug: {result.get('slug', '-')}")
        print(f"  Reason: {result.get('reason', '-')}")
        if result.get("gate_failures"):
            for gf in result["gate_failures"]:
                print(f"  GATE FAIL: {gf}")
        return 0 if result["action"] not in ("failed",) else 1

    elif args.all_pending:
        results = compile_all_pending(dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""
        if not results:
            print(f"{prefix}No pending sources to compile.")
            return 0
        created = sum(1 for r in results if r["action"] in ("created", "would_create"))
        updated = sum(1 for r in results if r["action"] in ("updated", "would_update"))
        failed = sum(1 for r in results if r["action"] == "failed")
        skipped = sum(1 for r in results if r["action"] == "skipped")
        for r in results:
            icon = {"created": "+", "would_create": "~", "updated": "^", "would_update": "~",
                    "failed": "!", "skipped": "-"}.get(r["action"], "?")
            print(f"  [{icon}] {r.get('source_id', '?')[:30]}  {r['action']}  {r.get('slug', '-')}")
            if r.get("gate_failures"):
                for gf in r["gate_failures"]:
                    print(f"      GATE: {gf}")
        print(f"\n{prefix}Summary: {created} created, {updated} updated, {failed} failed, {skipped} skipped")
        return 0

    else:
        print("Specify --source-id <id> or --all-pending")
        return 1


def cmd_status(args):
    records = read_registry()
    total = len(records)
    ingested = [r for r in records if r.get("status") == "ingested"]
    linked = [r for r in ingested if r.get("linked_pages")]
    unlinked = [r for r in ingested if not r.get("linked_pages")]
    failed = [r for r in records if r.get("status") == "failed"]

    pages = scan_existing_pages()

    print(f"Source Registry: {total} total, {len(ingested)} ingested, {len(failed)} failed")
    print(f"  Linked to wiki: {len(linked)}")
    print(f"  Pending compile: {len(unlinked)}")
    print(f"Wiki Pages: {len(pages)} total")
    for ptype in ("concept", "paper", "repo", "procedure", "question", "synthesis"):
        count = sum(1 for p in pages.values() if p.get("type") == ptype)
        if count:
            print(f"  {ptype}: {count}")

    if unlinked:
        print("\nPending sources:")
        for r in unlinked[:10]:
            print(f"  - {r['source_id']}  [{r.get('source_type', '?')}]  {r.get('title', '?')[:60]}")
    return 0


def cmd_backlinks(args):
    fixes = refresh_backlinks()
    print(f"Backlink refresh: {fixes} fixes applied")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki compile engine")
    sub = parser.add_subparsers(dest="command")

    p_compile = sub.add_parser("compile", help="Compile raw sources into wiki pages")
    p_compile.add_argument("--source-id", help="Compile a specific source by ID")
    p_compile.add_argument("--all-pending", action="store_true", help="Compile all unlinked sources")
    p_compile.add_argument("--dry-run", action="store_true", help="Preview without writing")

    sub.add_parser("status", help="Show compile pipeline status")
    sub.add_parser("backlinks", help="Refresh all backlinks")

    args = parser.parse_args()

    if args.command == "compile":
        sys.exit(cmd_compile(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))
    elif args.command == "backlinks":
        sys.exit(cmd_backlinks(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

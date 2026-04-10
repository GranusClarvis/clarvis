#!/usr/bin/env python3
"""Wiki-Brain sync — index wiki pages into ClarvisDB with embeddings and graph relations.

On page create/update, this module:
  1. Stores/updates the wiki page text as a memory in clarvis-learnings
  2. Extracts entities and concepts from page content
  3. Creates typed graph relations: mentions, supports, contradicts, derived_from,
     extends, about_project, about_person, and temporal edges

Usage:
    python3 wiki_brain_sync.py sync --slug <slug>       # Sync one page
    python3 wiki_brain_sync.py sync --all                # Sync all wiki pages
    python3 wiki_brain_sync.py sync --changed            # Sync pages changed today
    python3 wiki_brain_sync.py status                    # Show sync status
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
SYNC_LOG = KNOWLEDGE / "logs" / "brain_sync.jsonl"
TODAY = datetime.date.today().isoformat()

# Lazy brain import (avoid circular / heavy init at module load)
_brain = None


def _get_brain():
    global _brain
    if _brain is None:
        from clarvis.brain import brain as b
        _brain = b
    return _brain


# ============================================================
# Frontmatter parser (same as wiki_compile.py)
# ============================================================

def _parse_frontmatter(text: str) -> dict | None:
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
        if line.strip().startswith("- ") and current_key:
            val = line.strip()[2:].strip().strip('"').strip("'")
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(val)
            continue
        m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
        if m:
            current_key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            current_list = None
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                result[current_key] = items
            elif val:
                result[current_key] = val
            else:
                result[current_key] = ""
                current_list = []
                result[current_key] = current_list
    return result


def _strip_frontmatter(text: str) -> str:
    """Return markdown body without YAML frontmatter."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].strip()


# ============================================================
# Entity & relation extraction (heuristic, no LLM)
# ============================================================

# Relation type patterns detected from page content
_RELATION_PATTERNS = [
    # "supports X", "supports the claim"
    (re.compile(r'\bsupports?\s+(?:the\s+)?(.{5,60}?)(?:\.|,|\n|$)', re.I), "supports"),
    # "contradicts X"
    (re.compile(r'\bcontradicts?\s+(?:the\s+)?(.{5,60}?)(?:\.|,|\n|$)', re.I), "contradicts"),
    # "extends X", "extension of X"
    (re.compile(r'\b(?:extends?|extension\s+of)\s+(.{5,60}?)(?:\.|,|\n|$)', re.I), "extends"),
    # "derived from X", "based on X"
    (re.compile(r'\b(?:derived\s+from|based\s+on)\s+(.{5,60}?)(?:\.|,|\n|$)', re.I), "derived_from"),
]

# Person patterns
_PERSON_RE = re.compile(
    r'\b(?:by|authors?:?|created by|(?:et\s+al))\s+'
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
)

# Project/repo patterns
_PROJECT_RE = re.compile(
    r'\b(?:repo(?:sitory)?|project|library|framework|package)\s*:?\s*'
    r'["\']?([A-Za-z][\w.-]{2,40})["\']?',
    re.I,
)

# Year/date patterns for temporal edges
_YEAR_RE = re.compile(r'\b(20[12]\d)\b')
_DATE_RE = re.compile(r'\b(20[12]\d-\d{2}(?:-\d{2})?)\b')


def extract_entities(text: str, frontmatter: dict) -> dict:
    """Extract entities from wiki page text. Returns {persons, projects, concepts, dates}."""
    entities = {
        "persons": [],
        "projects": [],
        "concepts": [],
        "dates": [],
    }

    # From frontmatter
    if frontmatter.get("authors"):
        authors = frontmatter["authors"]
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]
        entities["persons"].extend(authors)

    page_type = frontmatter.get("type", "concept")
    if page_type == "repo" and frontmatter.get("repo_url"):
        entities["projects"].append(frontmatter["repo_url"])

    # Tags as concepts
    tags = frontmatter.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if "/" in tag:
                entities["concepts"].append(tag.split("/")[-1])
            else:
                entities["concepts"].append(tag)

    # From body text
    body = _strip_frontmatter(text)

    for m in _PERSON_RE.finditer(body):
        name = m.group(1).strip()
        if name not in entities["persons"] and len(name) > 3:
            entities["persons"].append(name)

    for m in _PROJECT_RE.finditer(body):
        proj = m.group(1).strip()
        if proj not in entities["projects"] and proj.lower() not in ("the", "this", "that"):
            entities["projects"].append(proj)

    for m in _DATE_RE.finditer(body):
        d = m.group(1)
        if d not in entities["dates"]:
            entities["dates"].append(d)

    if not entities["dates"]:
        for m in _YEAR_RE.finditer(body):
            y = m.group(1)
            if y not in entities["dates"]:
                entities["dates"].append(y)

    # Deduplicate
    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))[:10]

    return entities


def extract_relations(text: str) -> list[dict]:
    """Extract typed relations from page text (heuristic). Returns [{type, target_hint}]."""
    relations = []
    body = _strip_frontmatter(text)
    for pattern, rel_type in _RELATION_PATTERNS:
        for m in pattern.finditer(body):
            target_hint = m.group(1).strip()
            if len(target_hint) > 5:
                relations.append({"type": rel_type, "target_hint": target_hint})
    return relations[:15]


def extract_wiki_links(text: str) -> list[str]:
    """Extract internal wiki links (slugs) from markdown."""
    slugs = []
    for m in re.finditer(r'\[([^\]]+)\]\(\.\.?/\w+/([^)]+?)\.md\)', text):
        slugs.append(m.group(2))
    return list(dict.fromkeys(slugs))


# ============================================================
# Brain sync core
# ============================================================

def _make_memory_id(slug: str) -> str:
    """Deterministic memory ID for a wiki page."""
    return f"wiki_{slug}"


def _build_summary(title: str, body: str, max_len: int = 1500) -> str:
    """Build a concise text for brain embedding from wiki page content."""
    # Take title + first substantial paragraphs
    parts = [f"Wiki: {title}"]
    for para in body.split("\n\n"):
        stripped = para.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        if stripped.startswith("- _") or stripped.startswith("_No ") or stripped.startswith("_To be"):
            continue
        parts.append(stripped)
        if sum(len(p) for p in parts) > max_len:
            break
    return "\n\n".join(parts)[:max_len]


def sync_page(slug: str, page_path: Path, dry_run: bool = False) -> dict:
    """Sync a single wiki page into ClarvisDB.

    Returns {slug, action, memory_id, entities, relations, edges_added}.
    """
    text = page_path.read_text(encoding="utf-8", errors="replace")
    fm = _parse_frontmatter(text)
    if not fm:
        return {"slug": slug, "action": "skipped", "reason": "no frontmatter"}
    if fm.get("redirect"):
        return {"slug": slug, "action": "skipped", "reason": "redirect page"}

    title = fm.get("title", slug)
    page_type = fm.get("type", "concept")
    confidence = fm.get("confidence", "medium")
    status = fm.get("status", "draft")
    body = _strip_frontmatter(text)

    # Build embedding text
    summary = _build_summary(title, body)
    memory_id = _make_memory_id(slug)

    # Importance mapping
    importance_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
    importance = importance_map.get(confidence, 0.7)
    if status == "active":
        importance = min(importance + 0.1, 1.0)

    # Extract entities and relations
    entities = extract_entities(text, fm)
    relations = extract_relations(text)
    wiki_links = extract_wiki_links(text)

    if dry_run:
        return {
            "slug": slug, "action": "would_sync", "memory_id": memory_id,
            "entities": entities, "relations": len(relations),
            "wiki_links": len(wiki_links), "summary_len": len(summary),
        }

    brain = _get_brain()

    # 1. Store/update page as a brain memory
    tags = ["wiki", f"wiki/{page_type}"]
    if fm.get("tags"):
        t = fm["tags"]
        if isinstance(t, list):
            tags.extend(t[:5])

    brain.store(
        summary,
        collection="clarvis-learnings",
        importance=importance,
        tags=tags,
        source=f"wiki/{slug}",
        memory_id=memory_id,
    )

    # 2. Add graph relations
    edges_added = 0

    # a) Entity edges: about_person, about_project
    for person in entities.get("persons", [])[:5]:
        person_id = f"entity_person_{re.sub(r'[^a-z0-9]', '_', person.lower())}"
        brain.add_relationship(
            memory_id, person_id, "about_person",
            source_collection="clarvis-learnings",
        )
        edges_added += 1

    for project in entities.get("projects", [])[:5]:
        proj_id = f"entity_project_{re.sub(r'[^a-z0-9]', '_', project.lower())}"
        brain.add_relationship(
            memory_id, proj_id, "about_project",
            source_collection="clarvis-learnings",
        )
        edges_added += 1

    # b) Wiki cross-links as "mentions" edges
    for linked_slug in wiki_links[:10]:
        target_id = _make_memory_id(linked_slug)
        brain.add_relationship(
            memory_id, target_id, "mentions",
            source_collection="clarvis-learnings",
            target_collection="clarvis-learnings",
        )
        edges_added += 1

    # c) Typed content relations (supports, contradicts, extends, derived_from)
    #    Try to resolve target_hint to an existing wiki memory
    for rel in relations[:10]:
        target_hint = rel["target_hint"]
        # Search brain for a matching wiki memory
        try:
            matches = brain.recall(target_hint, n=1,
                                   collections=["clarvis-learnings"],
                                   caller="wiki_sync")
            if matches and matches[0].get("distance", 999) < 1.2:
                target_mem_id = matches[0]["id"]
                brain.add_relationship(
                    memory_id, target_mem_id, rel["type"],
                    source_collection="clarvis-learnings",
                    target_collection="clarvis-learnings",
                )
                edges_added += 1
        except Exception:
            pass

    # d) Temporal edges: link to date/year entities
    for date_str in entities.get("dates", [])[:3]:
        date_id = f"temporal_{date_str}"
        brain.add_relationship(
            memory_id, date_id, "temporal",
            source_collection="clarvis-learnings",
        )
        edges_added += 1

    # e) Source-derived edges: link wiki page to its raw sources
    sources = fm.get("sources", [])
    if isinstance(sources, list):
        for src in sources[:5]:
            if src.startswith("raw/"):
                src_id = f"raw_{re.sub(r'[^a-z0-9]', '_', src.lower())}"
                brain.add_relationship(
                    memory_id, src_id, "derived_from",
                    source_collection="clarvis-learnings",
                )
                edges_added += 1

    # Log sync event
    _log_sync(slug, memory_id, entities, edges_added)

    return {
        "slug": slug, "action": "synced", "memory_id": memory_id,
        "entities": entities, "relations": len(relations),
        "wiki_links": len(wiki_links), "edges_added": edges_added,
    }


def _log_sync(slug: str, memory_id: str, entities: dict, edges: int):
    """Append sync event to brain_sync.jsonl."""
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "slug": slug,
        "memory_id": memory_id,
        "entities_count": sum(len(v) for v in entities.values()),
        "edges_added": edges,
    }
    try:
        with open(SYNC_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ============================================================
# Scan and batch sync
# ============================================================

def scan_wiki_pages() -> dict[str, Path]:
    """Scan all wiki pages, return {slug: path}."""
    pages = {}
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        if fm:
            slug = fm.get("slug", md_file.stem)
            pages[slug] = md_file
    return pages


def sync_all(dry_run: bool = False) -> list[dict]:
    """Sync all wiki pages into ClarvisDB."""
    pages = scan_wiki_pages()
    results = []
    for slug, path in sorted(pages.items()):
        try:
            result = sync_page(slug, path, dry_run=dry_run)
            results.append(result)
        except Exception as e:
            results.append({"slug": slug, "action": "error", "reason": str(e)})
    return results


def sync_changed(dry_run: bool = False) -> list[dict]:
    """Sync wiki pages modified today."""
    pages = scan_wiki_pages()
    results = []
    for slug, path in sorted(pages.items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        if fm and fm.get("updated") == TODAY:
            try:
                result = sync_page(slug, path, dry_run=dry_run)
                results.append(result)
            except Exception as e:
                results.append({"slug": slug, "action": "error", "reason": str(e)})
    return results


def sync_status() -> dict:
    """Report sync status: pages in wiki vs synced in brain."""
    pages = scan_wiki_pages()
    synced = 0
    unsynced = []
    brain = _get_brain()
    for slug in pages:
        mid = _make_memory_id(slug)
        try:
            result = brain.collections["clarvis-learnings"].get(ids=[mid])
            if result and result["ids"]:
                synced += 1
            else:
                unsynced.append(slug)
        except Exception:
            unsynced.append(slug)
    return {
        "total_pages": len(pages),
        "synced": synced,
        "unsynced": len(unsynced),
        "unsynced_slugs": unsynced[:20],
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Wiki-Brain sync")
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="Sync wiki pages into ClarvisDB")
    p_sync.add_argument("--slug", help="Sync a specific page by slug")
    p_sync.add_argument("--all", action="store_true", help="Sync all pages")
    p_sync.add_argument("--changed", action="store_true", help="Sync pages changed today")
    p_sync.add_argument("--dry-run", action="store_true")

    sub.add_parser("status", help="Show sync status")

    args = parser.parse_args()

    if args.command == "sync":
        if args.slug:
            pages = scan_wiki_pages()
            if args.slug not in pages:
                print(f"Page not found: {args.slug}")
                sys.exit(1)
            result = sync_page(args.slug, pages[args.slug], dry_run=args.dry_run)
            print(json.dumps(result, indent=2, default=str))
        elif args.all:
            results = sync_all(dry_run=args.dry_run)
            synced = sum(1 for r in results if r["action"] == "synced")
            skipped = sum(1 for r in results if r["action"] == "skipped")
            errors = sum(1 for r in results if r["action"] == "error")
            for r in results:
                icon = {"synced": "+", "skipped": "-", "error": "!", "would_sync": "~"}.get(r["action"], "?")
                print(f"  [{icon}] {r['slug']:40s}  {r['action']:12s}  edges={r.get('edges_added', '-')}")
            print(f"\nSummary: {synced} synced, {skipped} skipped, {errors} errors")
        elif args.changed:
            results = sync_changed(dry_run=args.dry_run)
            if not results:
                print("No pages changed today.")
            for r in results:
                print(f"  {r['slug']}: {r['action']} (edges={r.get('edges_added', '-')})")
        else:
            print("Specify --slug, --all, or --changed")
            sys.exit(1)

    elif args.command == "status":
        status = sync_status()
        print(f"Wiki pages: {status['total_pages']}")
        print(f"Synced to brain: {status['synced']}")
        print(f"Unsynced: {status['unsynced']}")
        if status["unsynced_slugs"]:
            for s in status["unsynced_slugs"]:
                print(f"  - {s}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

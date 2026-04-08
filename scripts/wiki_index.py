#!/usr/bin/env python3
"""Wiki index generator — builds and maintains navigational index pages.

Generates:
  - wiki/index.md — top-level index with section summaries
  - wiki/{section}/index.md — per-section page lists
  - wiki/indexes/recent.md — recently updated pages
  - wiki/indexes/orphans.md — pages with no inbound links
  - wiki/indexes/questions.md — open research questions across all pages
  - wiki/indexes/tags.md — tag-based index

Usage:
    python3 wiki_index.py rebuild          # Rebuild all indexes
    python3 wiki_index.py rebuild --section concepts  # Rebuild one section
    python3 wiki_index.py status           # Show index stats
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
WIKI_DIR = WORKSPACE / "knowledge" / "wiki"
TODAY = datetime.date.today().isoformat()

# Sections and their descriptions
SECTIONS = {
    "concepts": "One canonical page per concept, technique, framework, or idea",
    "projects": "Project overviews and status",
    "people": "Person and organization profiles",
    "syntheses": "Cross-cutting synthesis documents",
    "questions": "Research questions and answers",
    "timelines": "Chronological event sequences",
    "procedures": "Durable how-to procedures",
}


# ============================================================
# Frontmatter parser (minimal, same as wiki_compile.py)
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


# ============================================================
# Page Scanner
# ============================================================

def scan_pages() -> list[dict]:
    """Scan all wiki pages and return metadata list."""
    pages = []
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if not fm:
            continue
        # Skip redirect pages
        if fm.get("redirect"):
            continue

        slug = fm.get("slug", md_file.stem)
        section = md_file.parent.name
        rel_path = md_file.relative_to(WIKI_DIR)

        # Extract open questions
        open_questions = []
        in_oq = False
        for line in text.split("\n"):
            if line.strip() == "## Open Questions":
                in_oq = True
                continue
            if in_oq:
                if line.startswith("## "):
                    break
                stripped = line.strip()
                if stripped.startswith("- ") and not stripped.startswith("- _"):
                    open_questions.append(stripped[2:])

        # Count inbound links (rough — will be refined in link scan)
        pages.append({
            "slug": slug,
            "title": fm.get("title", slug),
            "type": fm.get("type", "concept"),
            "status": fm.get("status", "draft"),
            "created": fm.get("created", ""),
            "updated": fm.get("updated", ""),
            "tags": fm.get("tags", []),
            "aliases": fm.get("aliases", []),
            "section": section,
            "path": md_file,
            "rel_path": str(rel_path),
            "open_questions": open_questions,
            "confidence": fm.get("confidence", "medium"),
        })
    return pages


def scan_links(pages: list[dict]) -> dict[str, set[str]]:
    """Build inbound link map: {slug: set of slugs that link to it}."""
    slug_set = {p["slug"] for p in pages}
    inbound: dict[str, set[str]] = {p["slug"]: set() for p in pages}

    for page in pages:
        text = page["path"].read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'\[([^\]]*)\]\([^)]*?/([a-z0-9-]+)\.md\)', text):
            target = m.group(2)
            if target in slug_set and target != page["slug"]:
                inbound[target].add(page["slug"])
    return inbound


# ============================================================
# Index Generators
# ============================================================

def generate_top_index(pages: list[dict]) -> str:
    """Generate the top-level wiki/index.md."""
    lines = [
        "# Wiki",
        "",
        f"_Layer 2 — compiled knowledge pages synthesized from raw sources. {len(pages)} pages total._",
        "",
        "## Sections",
        "",
    ]

    for section, desc in SECTIONS.items():
        section_pages = [p for p in pages if p["section"] == section]
        active = [p for p in section_pages if p["status"] == "active"]
        draft = [p for p in section_pages if p["status"] == "draft"]
        count_str = f"{len(section_pages)} pages"
        if active:
            count_str += f", {len(active)} active"
        if draft:
            count_str += f", {len(draft)} draft"
        lines.append(f"- **[{section}/]({section}/index.md)** — {desc} ({count_str})")

    lines += [
        "",
        "## Special Indexes",
        "",
        "- **[Recent Updates](indexes/recent.md)** — Pages updated in the last 30 days",
        "- **[Orphan Pages](indexes/orphans.md)** — Pages with no inbound links",
        "- **[Open Questions](indexes/questions.md)** — Unanswered research questions",
        "- **[Tags](indexes/tags.md)** — Browse by tag",
        "",
        "## Page Rules",
        "",
        "- One canonical page per concept (no duplicates)",
        "- Every claim cites a raw source",
        "- Pages use frontmatter schema from `schema/`",
        "",
        f"_Auto-generated {TODAY} by `wiki_index.py`._",
    ]
    return "\n".join(lines) + "\n"


def generate_section_index(section: str, pages: list[dict]) -> str:
    """Generate a section-level index (e.g., wiki/concepts/index.md)."""
    section_pages = sorted(
        [p for p in pages if p["section"] == section],
        key=lambda p: p["title"].lower()
    )
    desc = SECTIONS.get(section, section)

    lines = [
        f"# {section.title()}",
        "",
        f"_{desc}. {len(section_pages)} pages._",
        "",
    ]

    if not section_pages:
        lines.append("_No pages yet._")
    else:
        # Group by status
        active = [p for p in section_pages if p["status"] == "active"]
        draft = [p for p in section_pages if p["status"] == "draft"]
        stale = [p for p in section_pages if p["status"] == "stale"]
        archived = [p for p in section_pages if p["status"] == "archived"]

        for label, group in [("Active", active), ("Draft", draft), ("Stale", stale)]:
            if group:
                lines.append(f"## {label}")
                lines.append("")
                for p in group:
                    aliases = ""
                    if p["aliases"]:
                        alias_list = [a for a in p["aliases"] if a]
                        if alias_list:
                            aliases = f" (aka {', '.join(alias_list[:3])})"
                    lines.append(f"- [{p['title']}]({p['slug']}.md){aliases} — {p['confidence']} confidence, updated {p['updated']}")
                lines.append("")

        if archived:
            lines.append("## Archived")
            lines.append("")
            for p in archived:
                lines.append(f"- ~~[{p['title']}]({p['slug']}.md)~~ — archived")
            lines.append("")

    lines.append(f"_Auto-generated {TODAY} by `wiki_index.py`._")
    return "\n".join(lines) + "\n"


def generate_recent_index(pages: list[dict], days: int = 30) -> str:
    """Generate indexes/recent.md — recently updated pages."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    recent = sorted(
        [p for p in pages if p["updated"] >= cutoff],
        key=lambda p: p["updated"],
        reverse=True
    )

    lines = [
        "# Recent Updates",
        "",
        f"_Pages updated in the last {days} days. {len(recent)} pages._",
        "",
    ]

    if not recent:
        lines.append("_No recent updates._")
    else:
        current_date = ""
        for p in recent:
            if p["updated"] != current_date:
                current_date = p["updated"]
                lines.append(f"## {current_date}")
                lines.append("")
            section = p["section"]
            lines.append(f"- [{p['title']}](../{section}/{p['slug']}.md) ({section}, {p['status']})")
        lines.append("")

    lines.append(f"_Auto-generated {TODAY} by `wiki_index.py`._")
    return "\n".join(lines) + "\n"


def generate_orphans_index(pages: list[dict], inbound: dict[str, set[str]]) -> str:
    """Generate indexes/orphans.md — pages with no inbound links."""
    orphans = sorted(
        [p for p in pages if not inbound.get(p["slug"])],
        key=lambda p: p["title"].lower()
    )

    lines = [
        "# Orphan Pages",
        "",
        f"_Pages with no inbound links from other wiki pages. {len(orphans)} orphans._",
        "",
    ]

    if not orphans:
        lines.append("_No orphan pages — all pages are linked._")
    else:
        for p in orphans:
            section = p["section"]
            lines.append(f"- [{p['title']}](../{section}/{p['slug']}.md) ({section}, {p['status']})")
        lines.append("")
        lines.append("_Consider linking these pages from related content, or merging if redundant._")

    lines.append("")
    lines.append(f"_Auto-generated {TODAY} by `wiki_index.py`._")
    return "\n".join(lines) + "\n"


def generate_questions_index(pages: list[dict]) -> str:
    """Generate indexes/questions.md — open questions across all pages."""
    entries = []
    for p in pages:
        for q in p.get("open_questions", []):
            entries.append((p["title"], p["section"], p["slug"], q))

    lines = [
        "# Open Questions",
        "",
        f"_Unanswered research questions collected from {len(pages)} wiki pages. {len(entries)} questions._",
        "",
    ]

    if not entries:
        lines.append("_No open questions found._")
    else:
        # Group by section
        by_section: dict[str, list] = {}
        for title, section, slug, question in entries:
            by_section.setdefault(section, []).append((title, slug, question))

        for section in sorted(by_section.keys()):
            lines.append(f"## {section.title()}")
            lines.append("")
            for title, slug, question in by_section[section]:
                lines.append(f"- {question} — from [{title}](../{section}/{slug}.md)")
            lines.append("")

    lines.append(f"_Auto-generated {TODAY} by `wiki_index.py`._")
    return "\n".join(lines) + "\n"


def generate_tags_index(pages: list[dict]) -> str:
    """Generate indexes/tags.md — tag-based index."""
    tag_map: dict[str, list[dict]] = {}
    for p in pages:
        for tag in p.get("tags", []):
            if tag:
                tag_map.setdefault(tag, []).append(p)

    lines = [
        "# Tags",
        "",
        f"_Browse wiki pages by tag. {len(tag_map)} tags across {len(pages)} pages._",
        "",
    ]

    if not tag_map:
        lines.append("_No tags found._")
    else:
        for tag in sorted(tag_map.keys()):
            tag_pages = tag_map[tag]
            lines.append(f"## `{tag}`")
            lines.append("")
            for p in sorted(tag_pages, key=lambda x: x["title"].lower()):
                section = p["section"]
                lines.append(f"- [{p['title']}](../{section}/{p['slug']}.md)")
            lines.append("")

    lines.append(f"_Auto-generated {TODAY} by `wiki_index.py`._")
    return "\n".join(lines) + "\n"


# ============================================================
# Rebuild Logic
# ============================================================

def rebuild_all(section_filter: str | None = None) -> dict:
    """Rebuild all index pages. Returns summary stats."""
    pages = scan_pages()
    inbound = scan_links(pages)
    written = []

    if not section_filter:
        # Top-level index
        top_path = WIKI_DIR / "index.md"
        top_path.write_text(generate_top_index(pages), encoding="utf-8")
        written.append("wiki/index.md")

    # Section indexes
    for section in SECTIONS:
        if section_filter and section != section_filter:
            continue
        idx_path = WIKI_DIR / section / "index.md"
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(generate_section_index(section, pages), encoding="utf-8")
        written.append(f"wiki/{section}/index.md")

    if not section_filter:
        # Special indexes
        indexes_dir = WIKI_DIR / "indexes"
        indexes_dir.mkdir(parents=True, exist_ok=True)

        (indexes_dir / "recent.md").write_text(generate_recent_index(pages), encoding="utf-8")
        written.append("wiki/indexes/recent.md")

        (indexes_dir / "orphans.md").write_text(generate_orphans_index(pages, inbound), encoding="utf-8")
        written.append("wiki/indexes/orphans.md")

        (indexes_dir / "questions.md").write_text(generate_questions_index(pages), encoding="utf-8")
        written.append("wiki/indexes/questions.md")

        (indexes_dir / "tags.md").write_text(generate_tags_index(pages), encoding="utf-8")
        written.append("wiki/indexes/tags.md")

        # Indexes section index
        (indexes_dir / "index.md").write_text(
            f"# Indexes\n\n_Auto-generated navigational indexes._\n\n"
            f"- [Recent Updates](recent.md)\n"
            f"- [Orphan Pages](orphans.md)\n"
            f"- [Open Questions](questions.md)\n"
            f"- [Tags](tags.md)\n\n"
            f"_Auto-generated {TODAY} by `wiki_index.py`._\n",
            encoding="utf-8"
        )
        written.append("wiki/indexes/index.md")

    orphan_count = sum(1 for p in pages if not inbound.get(p["slug"]))
    question_count = sum(len(p.get("open_questions", [])) for p in pages)

    return {
        "pages": len(pages),
        "indexes_written": len(written),
        "files": written,
        "orphans": orphan_count,
        "open_questions": question_count,
    }


# ============================================================
# CLI
# ============================================================

def cmd_rebuild(args):
    section = args.section if hasattr(args, "section") and args.section else None
    result = rebuild_all(section_filter=section)
    print(f"Rebuilt {result['indexes_written']} index files ({result['pages']} pages scanned)")
    for f in result["files"]:
        print(f"  + {f}")
    print(f"  Orphans: {result['orphans']}")
    print(f"  Open questions: {result['open_questions']}")
    return 0


def cmd_status(args):
    pages = scan_pages()
    inbound = scan_links(pages)

    print(f"Wiki: {len(pages)} pages")
    by_section: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for p in pages:
        by_section[p["section"]] = by_section.get(p["section"], 0) + 1
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1

    for s, c in sorted(by_section.items()):
        print(f"  {s}: {c}")
    print()
    for s, c in sorted(by_status.items()):
        print(f"  {s}: {c}")

    orphans = [p for p in pages if not inbound.get(p["slug"])]
    print(f"\nOrphans: {len(orphans)}")
    for p in orphans:
        print(f"  - {p['slug']} ({p['section']})")

    questions = sum(len(p.get("open_questions", [])) for p in pages)
    print(f"Open questions: {questions}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki index generator")
    sub = parser.add_subparsers(dest="command")

    p_rebuild = sub.add_parser("rebuild", help="Rebuild all index pages")
    p_rebuild.add_argument("--section", help="Rebuild only this section")

    sub.add_parser("status", help="Show index stats")

    args = parser.parse_args()
    if args.command == "rebuild":
        sys.exit(cmd_rebuild(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wiki query-to-file — answer research questions from wiki + raw sources, save as artifacts.

Reads the wiki and linked raw sources to answer a question, then saves the
answer as a structured markdown artifact in wiki/questions/ or wiki/syntheses/.

Usage:
    python3 wiki_query.py ask "What is IIT and how does it relate to Clarvis?"
    python3 wiki_query.py ask "Compare episodic vs semantic memory" --type synthesis
    python3 wiki_query.py list                          # List saved answers
    python3 wiki_query.py show <slug>                   # Show a saved answer
"""

import argparse
import datetime
import hashlib
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"
RAW_DIR = KNOWLEDGE / "raw"
TODAY = datetime.date.today().isoformat()

sys.path.insert(0, str(Path(__file__).parent))

try:
    from wiki_canonical import CanonicalResolver, _slugify, _normalize
except ImportError:
    # Fallback if import fails
    def _slugify(text):
        s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return s[:60]
    def _normalize(text):
        s = text.lower().strip()
        s = re.sub(r"[^a-z0-9\s]", "", s)
        return re.sub(r"\s+", " ", s)
    CanonicalResolver = None


# ============================================================
# Frontmatter parser
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
# Wiki Search — find relevant pages and raw sources for a query
# ============================================================

def extract_keywords(question: str) -> list[str]:
    """Extract meaningful keywords from a question."""
    stop_words = {
        "what", "is", "are", "how", "does", "do", "the", "a", "an", "and", "or",
        "to", "in", "of", "for", "with", "this", "that", "it", "its", "can",
        "be", "has", "have", "was", "were", "will", "would", "could", "should",
        "from", "by", "on", "at", "as", "not", "but", "if", "than", "about",
        "between", "vs", "versus", "compare", "explain", "describe", "why",
    }
    words = re.findall(r'[a-zA-Z0-9]+', question.lower())
    return [w for w in words if w not in stop_words and len(w) > 2]


def search_wiki(question: str) -> list[dict]:
    """Search wiki pages for relevance to a question. Returns scored results."""
    keywords = extract_keywords(question)
    if not keywords:
        return []

    results = []
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if not fm or fm.get("redirect"):
            continue

        slug = fm.get("slug", md_file.stem)
        title = fm.get("title", slug)
        aliases = fm.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        tags = fm.get("tags", [])

        # Score by keyword matches
        text_lower = text.lower()
        title_lower = title.lower()
        score = 0.0

        for kw in keywords:
            # Title match (high weight)
            if kw in title_lower:
                score += 3.0
            # Alias match
            for alias in aliases:
                if kw in alias.lower():
                    score += 2.0
            # Tag match
            for tag in tags:
                if kw in tag.lower():
                    score += 1.5
            # Body match (count occurrences, diminishing returns)
            count = text_lower.count(kw)
            if count > 0:
                score += min(count * 0.5, 3.0)

        if score > 0:
            # Get raw source paths
            sources = fm.get("sources", [])
            results.append({
                "slug": slug,
                "title": title,
                "score": score,
                "path": md_file,
                "section": md_file.parent.name,
                "sources": sources,
                "type": fm.get("type", "concept"),
            })

    results.sort(key=lambda r: -r["score"])
    return results[:10]


def gather_context(question: str, max_pages: int = 3, max_raw: int = 2) -> dict:
    """Gather relevant wiki pages and raw sources for answering a question.

    Returns {question, wiki_pages: [{title, slug, content}], raw_sources: [{path, content}], keywords}.
    """
    keywords = extract_keywords(question)
    wiki_results = search_wiki(question)

    wiki_pages = []
    raw_sources_seen = set()
    raw_sources = []

    for result in wiki_results[:max_pages]:
        try:
            content = result["path"].read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        wiki_pages.append({
            "title": result["title"],
            "slug": result["slug"],
            "section": result["section"],
            "score": result["score"],
            "content": content[:5000],  # Truncate for context budget
        })

        # Gather linked raw sources
        for src in result.get("sources", []):
            if src in raw_sources_seen or len(raw_sources) >= max_raw:
                continue
            raw_sources_seen.add(src)
            if src.startswith("raw/") or src.startswith("knowledge/raw/"):
                raw_path = KNOWLEDGE / src if src.startswith("raw/") else WORKSPACE / src
                if raw_path.exists():
                    try:
                        raw_content = raw_path.read_text(encoding="utf-8", errors="replace")
                        raw_sources.append({
                            "path": str(src),
                            "content": raw_content[:3000],
                        })
                    except OSError:
                        pass

    return {
        "question": question,
        "keywords": keywords,
        "wiki_pages": wiki_pages,
        "raw_sources": raw_sources,
    }


# ============================================================
# Answer Generation (template-based, no LLM needed)
# ============================================================

def generate_answer_artifact(question: str, context: dict, artifact_type: str = "question") -> tuple[str, str]:
    """Generate an answer artifact from gathered context.

    Returns (slug, markdown_content). The answer synthesizes found wiki pages
    and raw sources into a structured response. Without an LLM, this creates
    a well-organized evidence brief that can be refined later.
    """
    slug = _slugify(question)[:50]
    # Add short hash for uniqueness
    h = hashlib.sha256(question.encode()).hexdigest()[:6]
    slug = f"{slug}-{h}"

    wiki_pages = context.get("wiki_pages", [])
    raw_sources = context.get("raw_sources", [])
    keywords = context.get("keywords", [])

    # Build the answer
    if artifact_type == "synthesis":
        page_type = "synthesis"
        dest_section = "syntheses"
        title = f"Synthesis: {question[:80]}"
    else:
        page_type = "question"
        dest_section = "questions"
        title = question[:120]

    # Extract key claims from wiki pages
    claims = []
    evidence_entries = []
    related_pages = []

    for wp in wiki_pages:
        related_pages.append(f"- [{wp['title']}](../{wp['section']}/{wp['slug']}.md) (relevance: {wp['score']:.1f})")

        # Extract Key Claims section from wiki page content
        content = wp["content"]
        in_claims = False
        for line in content.split("\n"):
            if line.strip() == "## Key Claims":
                in_claims = True
                continue
            if in_claims:
                if line.startswith("## "):
                    break
                stripped = line.strip()
                if stripped.startswith("- ") and not stripped.startswith("- _"):
                    claims.append(f"{stripped} — from [{wp['title']}](../{wp['section']}/{wp['slug']}.md)")

        evidence_entries.append(f"- **[Wiki: {wp['title']}]**: Canonical wiki page. [../{wp['section']}/{wp['slug']}.md]")

    for rs in raw_sources:
        evidence_entries.append(f"- **[Raw: {rs['path']}]**: Source material. [{rs['path']}]")

    # Build sources list for frontmatter
    sources_yaml = ""
    for wp in wiki_pages:
        sources_yaml += f"\n  - ../{wp['section']}/{wp['slug']}.md"
    for rs in raw_sources:
        sources_yaml += f"\n  - {rs['path']}"

    claims_section = "\n".join(claims) if claims else "- _No claims extracted from wiki pages. Consider adding relevant wiki content first._"
    evidence_section = "\n".join(evidence_entries) if evidence_entries else "- _No evidence gathered._"
    related_section = "\n".join(related_pages) if related_pages else "_No related pages found._"

    # Summary from raw source snippets
    summary_parts = []
    if wiki_pages:
        summary_parts.append(f"This {'synthesis' if artifact_type == 'synthesis' else 'answer'} draws from {len(wiki_pages)} wiki page(s) and {len(raw_sources)} raw source(s).")
    if not wiki_pages:
        summary_parts.append("No relevant wiki pages found. Consider ingesting source material first.")

    summary = " ".join(summary_parts)

    # Determine answer status
    answer_status = "partial" if wiki_pages else "open"
    if len(wiki_pages) >= 2 and claims:
        answer_status = "partial"  # Still needs human review

    extra_fm = ""
    if page_type == "question":
        extra_fm = f'answer_status: {answer_status}\npriority: medium\n'

    content = f"""---
title: "{title}"
slug: "{slug}"
type: {page_type}
created: {TODAY}
updated: {TODAY}
status: draft
tags:
  - research/question
aliases: []
sources:{sources_yaml}
confidence: low
{extra_fm}---

# {title}

{summary}

## Key Claims

{claims_section}

## Evidence

{evidence_section}

## Context Gathered

**Keywords**: {', '.join(keywords)}
**Wiki pages consulted**: {len(wiki_pages)}
**Raw sources consulted**: {len(raw_sources)}

## Related Pages

{related_section}

## Open Questions

- Does this answer fully address the original question?
- Are there additional sources that should be consulted?
- Do any claims need verification or updating?

## Update History

- {TODAY}: Initial answer generated by `wiki_query.py`.
"""
    return slug, content, dest_section


def save_artifact(slug: str, content: str, dest_section: str) -> Path:
    """Save an answer artifact to the wiki."""
    dest_dir = WIKI_DIR / dest_section
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{slug}.md"
    dest_path.write_text(content, encoding="utf-8")
    return dest_path


# ============================================================
# CLI
# ============================================================

def cmd_ask(args):
    question = args.question
    artifact_type = args.type if hasattr(args, "type") and args.type else "question"

    print(f"Searching wiki for: {question}")
    context = gather_context(question)

    print(f"  Found {len(context['wiki_pages'])} wiki pages, {len(context['raw_sources'])} raw sources")
    for wp in context["wiki_pages"]:
        print(f"    [{wp['score']:.1f}] {wp['title']} ({wp['section']})")

    slug, content, dest_section = generate_answer_artifact(question, context, artifact_type)

    if args.dry_run:
        print(f"\n[DRY RUN] Would save to wiki/{dest_section}/{slug}.md")
        print(f"\n--- Preview ---\n{content[:1000]}...")
        return 0

    dest_path = save_artifact(slug, content, dest_section)
    print(f"\nSaved: {dest_path.relative_to(WORKSPACE)}")
    print(f"  Slug: {slug}")
    print(f"  Type: {artifact_type}")
    return 0


def cmd_list(args):
    """List saved question/synthesis artifacts."""
    count = 0
    for section in ("questions", "syntheses"):
        section_dir = WIKI_DIR / section
        if not section_dir.exists():
            continue
        for md_file in sorted(section_dir.glob("*.md")):
            if md_file.name == "index.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse_frontmatter(text)
            if not fm or fm.get("redirect"):
                continue
            title = fm.get("title", md_file.stem)
            status = fm.get("status", "?")
            answer_status = fm.get("answer_status", "")
            extra = f" [{answer_status}]" if answer_status else ""
            print(f"  [{section:10s}] {md_file.stem:50s} {status:8s}{extra}  {title[:60]}")
            count += 1
    if count == 0:
        print("No saved answers found.")
    else:
        print(f"\n{count} saved answer(s).")
    return 0


def cmd_show(args):
    """Show a saved answer by slug."""
    slug = args.slug
    for section in ("questions", "syntheses"):
        path = WIKI_DIR / section / f"{slug}.md"
        if path.exists():
            print(path.read_text(encoding="utf-8", errors="replace"))
            return 0
    print(f"Not found: {slug}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki query-to-file workflow")
    sub = parser.add_subparsers(dest="command")

    p_ask = sub.add_parser("ask", help="Ask a question, save answer as wiki artifact")
    p_ask.add_argument("question", help="The research question")
    p_ask.add_argument("--type", choices=["question", "synthesis"], default="question",
                       help="Artifact type (default: question)")
    p_ask.add_argument("--dry-run", action="store_true", help="Preview without saving")

    sub.add_parser("list", help="List saved answer artifacts")

    p_show = sub.add_parser("show", help="Show a saved answer")
    p_show.add_argument("slug", help="Slug of the answer to show")

    args = parser.parse_args()
    handlers = {
        "ask": cmd_ask,
        "list": cmd_list,
        "show": cmd_show,
    }
    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

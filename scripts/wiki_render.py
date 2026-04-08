#!/usr/bin/env python3
"""Wiki output renderers — transform wiki content into presentation formats.

Reads wiki pages and gathered context, then renders into one of several
output formats. Each renderer produces a standalone file saved to
knowledge/outputs/.

Renderers:
  - markdown:   Plain markdown answer (clean, readable, citation-grounded)
  - memo:       Comparison memo (two-column pros/cons/analysis)
  - plan:       Implementation plan (phased, with tasks and gates)
  - slides:     Marp slide deck (presentation-ready)

Usage:
    python3 wiki_render.py markdown "What is IIT?"
    python3 wiki_render.py memo "Compare episodic vs semantic memory"
    python3 wiki_render.py plan "Add adaptive RAG pipeline"
    python3 wiki_render.py slides "Clarvis architecture overview"
    python3 wiki_render.py list                    # List saved outputs
    python3 wiki_render.py formats                 # Show available formats
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"
OUTPUTS_DIR = KNOWLEDGE / "outputs"
TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")

sys.path.insert(0, str(Path(__file__).parent))

try:
    from wiki_query import gather_context, search_wiki, extract_keywords, _parse_frontmatter
except ImportError:
    print("ERROR: wiki_query.py must be importable", file=sys.stderr)
    sys.exit(1)


# ============================================================
# Helpers
# ============================================================

def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60]


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:6]


def _extract_claims(wiki_pages: list[dict]) -> list[dict]:
    """Extract structured claims from wiki page content."""
    claims = []
    for wp in wiki_pages:
        content = wp.get("content", "")
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
                    claims.append({
                        "text": stripped[2:],
                        "source_title": wp.get("title", "?"),
                        "source_slug": wp.get("slug", "?"),
                        "source_section": wp.get("section", "concepts"),
                    })
    return claims


def _format_citation(claim: dict) -> str:
    return f"{claim['text']} — [{claim['source_title']}](../wiki/{claim['source_section']}/{claim['source_slug']}.md)"


def _save_output(content: str, subdir: str, slug: str, ext: str = "md") -> Path:
    """Save rendered output to knowledge/outputs/<subdir>/."""
    dest_dir = OUTPUTS_DIR / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{slug}.{ext}"
    dest_path.write_text(content, encoding="utf-8")
    return dest_path


def _link_output_to_wiki(output_path: Path, question: str, fmt: str) -> Path | None:
    """Create or update a backlink from wiki/syntheses/ to the output."""
    slug = f"output-{_slugify(question)}-{_short_hash(question)}"
    synth_dir = WIKI_DIR / "syntheses"
    synth_dir.mkdir(parents=True, exist_ok=True)
    link_path = synth_dir / f"{slug}.md"

    rel_output = os.path.relpath(output_path, synth_dir)

    if link_path.exists():
        existing = link_path.read_text(encoding="utf-8", errors="replace")
        if str(output_path.name) not in existing:
            # Append link to existing file
            existing += f"\n- [{fmt}]({rel_output}) — generated {TODAY}\n"
            link_path.write_text(existing, encoding="utf-8")
        return link_path

    content = f"""---
title: "Output: {question[:80]}"
slug: "{slug}"
type: synthesis
created: {TODAY}
updated: {TODAY}
status: draft
tags:
  - output/{fmt}
aliases: []
sources: []
confidence: medium
---

# Output: {question[:80]}

Generated outputs for this query:

- [{fmt}]({rel_output}) — generated {TODAY}

## Update History

- {TODAY}: Output link page created by `wiki_render.py`.
"""
    link_path.write_text(content, encoding="utf-8")
    return link_path


# ============================================================
# Renderer: Plain Markdown Answer
# ============================================================

def render_markdown(question: str, context: dict) -> str:
    """Render a clean, readable markdown answer with citations."""
    wiki_pages = context.get("wiki_pages", [])
    raw_sources = context.get("raw_sources", [])
    keywords = context.get("keywords", [])
    claims = _extract_claims(wiki_pages)

    # Build answer sections
    lines = [
        f"# {question}",
        "",
        f"_Generated {NOW} by Clarvis wiki renderer._",
        "",
    ]

    # Summary
    if wiki_pages:
        lines.append(f"This answer draws from **{len(wiki_pages)} wiki page(s)** "
                      f"and **{len(raw_sources)} raw source(s)**.")
    else:
        lines.append("No relevant wiki pages found for this query. "
                      "Consider ingesting source material first.")
    lines.append("")

    # Main answer body — organized by source page
    if wiki_pages:
        lines.append("## Key Findings")
        lines.append("")
        if claims:
            for c in claims:
                lines.append(f"- {_format_citation(c)}")
        else:
            lines.append("_No structured claims found in matching wiki pages. "
                          "See source pages for raw content._")
        lines.append("")

    # Context from each wiki page
    if wiki_pages:
        lines.append("## Sources Consulted")
        lines.append("")
        for wp in wiki_pages:
            score = wp.get("score", 0)
            lines.append(f"### {wp['title']} (relevance: {score:.1f})")
            lines.append("")
            # Extract first paragraph of body content (after frontmatter)
            content = wp.get("content", "")
            body = content
            if content.startswith("---"):
                end = content.find("\n---", 3)
                if end != -1:
                    body = content[end + 4:].strip()
            # Take first ~300 chars of body after title
            body_lines = body.split("\n")
            excerpt = []
            for bl in body_lines:
                if bl.startswith("# "):
                    continue
                if bl.strip():
                    excerpt.append(bl)
                if len("\n".join(excerpt)) > 300:
                    break
            if excerpt:
                lines.append("> " + " ".join(l.strip() for l in excerpt[:3]))
            lines.append("")
            lines.append(f"Source: [`wiki/{wp['section']}/{wp['slug']}.md`]"
                          f"(../wiki/{wp['section']}/{wp['slug']}.md)")
            lines.append("")

    # Raw sources
    if raw_sources:
        lines.append("## Raw Evidence")
        lines.append("")
        for rs in raw_sources:
            lines.append(f"- `{rs['path']}` — {len(rs.get('content', ''))} chars of source text")
        lines.append("")

    # Footer
    lines.extend([
        "---",
        "",
        f"**Keywords**: {', '.join(keywords)}  ",
        f"**Generated**: {NOW}  ",
        f"**Renderer**: `wiki_render.py markdown`",
    ])

    return "\n".join(lines)


# ============================================================
# Renderer: Comparison Memo
# ============================================================

def render_memo(question: str, context: dict) -> str:
    """Render a comparison memo — structured analysis of two or more options."""
    wiki_pages = context.get("wiki_pages", [])
    raw_sources = context.get("raw_sources", [])
    keywords = context.get("keywords", [])
    claims = _extract_claims(wiki_pages)

    lines = [
        f"# Comparison Memo: {question}",
        "",
        f"_Generated {NOW} by Clarvis wiki renderer._",
        "",
        "## Executive Summary",
        "",
        f"This memo compares aspects relevant to: **{question}**",
        f"Based on {len(wiki_pages)} wiki page(s) and {len(raw_sources)} raw source(s).",
        "",
        "## Comparison Matrix",
        "",
        "| Aspect | Details | Source |",
        "| ------ | ------- | ------ |",
    ]

    # Build comparison rows from claims
    if claims:
        for i, c in enumerate(claims[:15], 1):
            text = c["text"].replace("|", "\\|")[:120]
            source = c["source_title"][:30]
            lines.append(f"| {i}. | {text} | {source} |")
    else:
        lines.append("| — | _No structured claims found_ | — |")

    lines.extend([
        "",
        "## Analysis by Source",
        "",
    ])

    for wp in wiki_pages:
        lines.append(f"### {wp['title']}")
        lines.append("")
        lines.append("**Strengths / Pros:**")
        lines.append("- _To be filled based on domain analysis._")
        lines.append("")
        lines.append("**Weaknesses / Cons:**")
        lines.append("- _To be filled based on domain analysis._")
        lines.append("")
        lines.append("**Key Contribution:**")
        # Pull first claim from this source
        source_claims = [c for c in claims if c["source_slug"] == wp.get("slug")]
        if source_claims:
            lines.append(f"- {source_claims[0]['text']}")
        else:
            lines.append("- _See source page for details._")
        lines.append("")

    lines.extend([
        "## Recommendation",
        "",
        "_Based on the evidence gathered, consider:_",
        "",
        "1. Which option best fits the current architecture?",
        "2. What are the migration costs of each approach?",
        "3. Are there hybrid approaches worth exploring?",
        "",
        "## Evidence Trail",
        "",
    ])

    for wp in wiki_pages:
        lines.append(f"- [{wp['title']}](../wiki/{wp['section']}/{wp['slug']}.md)")
    for rs in raw_sources:
        lines.append(f"- `{rs['path']}`")

    lines.extend([
        "",
        "---",
        "",
        f"**Keywords**: {', '.join(keywords)}  ",
        f"**Generated**: {NOW}  ",
        f"**Renderer**: `wiki_render.py memo`",
    ])

    return "\n".join(lines)


# ============================================================
# Renderer: Implementation Plan
# ============================================================

def render_plan(question: str, context: dict) -> str:
    """Render an implementation plan — phased tasks with gates."""
    wiki_pages = context.get("wiki_pages", [])
    raw_sources = context.get("raw_sources", [])
    keywords = context.get("keywords", [])
    claims = _extract_claims(wiki_pages)

    lines = [
        f"# Implementation Plan: {question}",
        "",
        f"_Generated {NOW} by Clarvis wiki renderer._",
        "",
        "## Objective",
        "",
        f"Implement: **{question}**",
        "",
        "## Background",
        "",
    ]

    if wiki_pages:
        lines.append(f"Based on {len(wiki_pages)} wiki page(s) and "
                      f"{len(raw_sources)} raw source(s):")
        lines.append("")
        for wp in wiki_pages:
            lines.append(f"- **{wp['title']}** — relevance {wp.get('score', 0):.1f}")
    else:
        lines.append("_No relevant wiki pages found. Plan is based on the objective alone._")

    lines.extend([
        "",
        "## Relevant Claims",
        "",
    ])

    if claims:
        for c in claims[:10]:
            lines.append(f"- {_format_citation(c)}")
    else:
        lines.append("- _No structured claims available._")

    lines.extend([
        "",
        "## Phase 1: Foundation",
        "",
        "**Goal**: Establish the minimal viable structure.",
        "",
        "- [ ] Task 1.1: Read existing code and interfaces",
        "- [ ] Task 1.2: Identify insertion points and dependencies",
        "- [ ] Task 1.3: Write unit tests for core logic",
        "",
        "**Gate**: Tests pass, no regressions.",
        "",
        "## Phase 2: Core Implementation",
        "",
        "**Goal**: Build the main functionality.",
        "",
        "- [ ] Task 2.1: Implement core module/function",
        "- [ ] Task 2.2: Wire into existing callers",
        "- [ ] Task 2.3: Add error handling at system boundaries",
        "",
        "**Gate**: Integration tests pass, manual verification.",
        "",
        "## Phase 3: Integration & Polish",
        "",
        "**Goal**: Connect to the broader system.",
        "",
        "- [ ] Task 3.1: Add CLI/API surface",
        "- [ ] Task 3.2: Update documentation",
        "- [ ] Task 3.3: Run full test suite",
        "",
        "**Gate**: All tests green, no scope creep.",
        "",
        "## Risks & Mitigations",
        "",
        "| Risk | Impact | Mitigation |",
        "| ---- | ------ | ---------- |",
        "| Scope creep | High | Stick to phase gates |",
        "| Breaking existing callers | High | Grep for usages first |",
        "| Missing test coverage | Medium | Write tests before code |",
        "",
        "## Related Resources",
        "",
    ])

    for wp in wiki_pages:
        lines.append(f"- [{wp['title']}](../wiki/{wp['section']}/{wp['slug']}.md)")
    for rs in raw_sources:
        lines.append(f"- `{rs['path']}`")

    lines.extend([
        "",
        "---",
        "",
        f"**Keywords**: {', '.join(keywords)}  ",
        f"**Generated**: {NOW}  ",
        f"**Renderer**: `wiki_render.py plan`",
    ])

    return "\n".join(lines)


# ============================================================
# Renderer: Marp Slide Deck
# ============================================================

def render_slides(question: str, context: dict) -> str:
    """Render a Marp-compatible slide deck."""
    wiki_pages = context.get("wiki_pages", [])
    raw_sources = context.get("raw_sources", [])
    claims = _extract_claims(wiki_pages)

    lines = [
        "---",
        "marp: true",
        "theme: default",
        "paginate: true",
        f"title: \"{question}\"",
        f"date: {TODAY}",
        "---",
        "",
        f"# {question}",
        "",
        f"*Clarvis Knowledge Wiki — {TODAY}*",
        "",
        "---",
        "",
        "## Overview",
        "",
    ]

    if wiki_pages:
        lines.append(f"- **{len(wiki_pages)}** wiki pages consulted")
        lines.append(f"- **{len(raw_sources)}** raw sources reviewed")
        lines.append(f"- **{len(claims)}** key claims extracted")
    else:
        lines.append("- No wiki pages matched this query")
        lines.append("- Consider ingesting sources first")

    lines.extend(["", "---", ""])

    # One slide per wiki page (max 5)
    for wp in wiki_pages[:5]:
        lines.append(f"## {wp['title']}")
        lines.append("")

        # Get claims from this page
        page_claims = [c for c in claims if c["source_slug"] == wp.get("slug")]
        if page_claims:
            for c in page_claims[:4]:
                lines.append(f"- {c['text'][:120]}")
        else:
            lines.append(f"- See wiki page for details")
        lines.append("")
        lines.append(f"*Source: wiki/{wp['section']}/{wp['slug']}.md*")
        lines.extend(["", "---", ""])

    # Key claims summary slide
    if claims:
        lines.append("## Key Claims Summary")
        lines.append("")
        for c in claims[:8]:
            text = c["text"][:100]
            lines.append(f"1. {text}")
        lines.extend(["", "---", ""])

    # Closing slide
    lines.extend([
        "## Next Steps",
        "",
        "- Review source pages for full evidence",
        "- Identify gaps in coverage",
        "- Update wiki with new findings",
        "",
        f"*Generated {NOW} by `wiki_render.py slides`*",
    ])

    return "\n".join(lines)


# ============================================================
# Format Registry
# ============================================================

RENDERERS = {
    "markdown": {
        "func": render_markdown,
        "subdir": "answers",
        "ext": "md",
        "description": "Plain markdown answer with citations",
    },
    "memo": {
        "func": render_memo,
        "subdir": "memos",
        "ext": "md",
        "description": "Comparison memo with pros/cons matrix",
    },
    "plan": {
        "func": render_plan,
        "subdir": "plans",
        "ext": "md",
        "description": "Phased implementation plan with gates",
    },
    "slides": {
        "func": render_slides,
        "subdir": "slides",
        "ext": "md",
        "description": "Marp-compatible slide deck",
    },
}


def render_and_save(fmt: str, question: str, dry_run: bool = False, link: bool = True) -> dict:
    """Render a question in the given format and save to outputs/.

    Returns {format, slug, path, linked_page, error}.
    """
    if fmt not in RENDERERS:
        return {"format": fmt, "error": f"Unknown format: {fmt}. Available: {', '.join(RENDERERS)}"}

    renderer = RENDERERS[fmt]
    context = gather_context(question)
    content = renderer["func"](question, context)

    slug = f"{_slugify(question)}-{_short_hash(question)}"
    subdir = renderer["subdir"]
    ext = renderer["ext"]

    if dry_run:
        return {
            "format": fmt,
            "slug": slug,
            "path": f"knowledge/outputs/{subdir}/{slug}.{ext}",
            "preview": content[:500],
            "wiki_pages": len(context.get("wiki_pages", [])),
            "raw_sources": len(context.get("raw_sources", [])),
        }

    output_path = _save_output(content, subdir, slug, ext)

    linked_page = None
    if link:
        lp = _link_output_to_wiki(output_path, question, fmt)
        if lp:
            linked_page = str(lp.relative_to(WORKSPACE))

    return {
        "format": fmt,
        "slug": slug,
        "path": str(output_path.relative_to(WORKSPACE)),
        "linked_page": linked_page,
        "wiki_pages": len(context.get("wiki_pages", [])),
        "raw_sources": len(context.get("raw_sources", [])),
    }


# ============================================================
# CLI
# ============================================================

def cmd_render(args):
    fmt = args.command  # The format name is the subcommand
    question = args.question
    result = render_and_save(fmt, question, dry_run=args.dry_run, link=not args.no_link)

    if result.get("error"):
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}Rendered {fmt}: {result.get('path', '?')}")
    print(f"  Wiki pages consulted: {result.get('wiki_pages', 0)}")
    print(f"  Raw sources consulted: {result.get('raw_sources', 0)}")
    if result.get("linked_page"):
        print(f"  Linked from: {result['linked_page']}")
    if args.dry_run and result.get("preview"):
        print(f"\n--- Preview ---\n{result['preview']}...")
    return 0


def cmd_list(args):
    count = 0
    for subdir in ("answers", "memos", "plans", "slides"):
        out_dir = OUTPUTS_DIR / subdir
        if not out_dir.exists():
            continue
        for f in sorted(out_dir.glob("*.md")):
            stat = f.stat()
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            size = stat.st_size
            print(f"  [{subdir:8s}] {f.stem:50s} {size:6d}B  {mtime}")
            count += 1
    if count == 0:
        print("No rendered outputs found.")
    else:
        print(f"\n{count} output(s) total.")
    return 0


def cmd_formats(args):
    print("Available output formats:\n")
    for name, info in RENDERERS.items():
        print(f"  {name:12s} — {info['description']}")
        print(f"               Saves to: knowledge/outputs/{info['subdir']}/")
    print(f"\nUsage: python3 wiki_render.py <format> \"<question>\"")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Clarvis wiki output renderer — transform wiki content into presentation formats"
    )
    sub = parser.add_subparsers(dest="command")

    # One subcommand per format
    for name, info in RENDERERS.items():
        p = sub.add_parser(name, help=info["description"])
        p.add_argument("question", help="Topic or question to render")
        p.add_argument("--dry-run", action="store_true", help="Preview without saving")
        p.add_argument("--no-link", action="store_true", help="Don't create wiki backlink")

    sub.add_parser("list", help="List saved rendered outputs")
    sub.add_parser("formats", help="Show available output formats")

    args = parser.parse_args()

    if args.command in RENDERERS:
        sys.exit(cmd_render(args))
    elif args.command == "list":
        sys.exit(cmd_list(args))
    elif args.command == "formats":
        sys.exit(cmd_formats(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

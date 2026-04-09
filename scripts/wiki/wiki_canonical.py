#!/usr/bin/env python3
"""Wiki canonical page resolution — CLI wrapper.

Library logic lives in clarvis.wiki.canonical. This file provides the CLI.

Usage:
    python3 wiki_canonical.py resolve "IIT"
    python3 wiki_canonical.py resolve "Integrated Information Theory"
    python3 wiki_canonical.py detect                    # Find duplicate groups
    python3 wiki_canonical.py merge <source> <target>   # Merge source into target
    python3 wiki_canonical.py redirects                 # List all redirect pages
    python3 wiki_canonical.py aliases                   # Dump full alias index
    python3 wiki_canonical.py add-alias <slug> "alias"  # Add alias to a page
"""

import argparse
import sys

from clarvis.wiki.canonical import (
    CanonicalResolver,
    _normalize,
)


def cmd_resolve(args):
    resolver = CanonicalResolver()
    name = args.name
    slug, suggestions = resolver.resolve_or_suggest(name, threshold=0.4)
    if slug:
        info = resolver.pages.get(slug, {})
        print(f"✓ '{name}' → {slug}")
        print(f"  Title: {info.get('title', slug)}")
        print(f"  Path: {info.get('path', '?')}")
        print(f"  Type: {info.get('type', '?')}")
        aliases = info.get("aliases", [])
        if aliases:
            print(f"  Aliases: {', '.join(aliases)}")
        return 0
    else:
        print(f"✗ '{name}' — no canonical page found")
        if suggestions:
            print("  Did you mean:")
            for s_slug, sim in suggestions:
                s_title = resolver.pages[s_slug]["title"]
                print(f"    {s_slug} ({s_title}) — {sim:.0%} similar")
        return 1


def cmd_detect(args):
    resolver = CanonicalResolver()
    threshold = args.threshold if hasattr(args, "threshold") and args.threshold else 0.5
    groups = resolver.find_duplicates(threshold=threshold)
    if not groups:
        print("No duplicate groups detected.")
        return 0
    print(f"Found {len(groups)} potential duplicate group(s):\n")
    for i, group in enumerate(groups, 1):
        print(f"Group {i}:")
        for slug, title, sim in group:
            path = resolver.pages[slug]["path"]
            print(f"  {slug:40s} {title:40s} (sim={sim:.0%})  {path}")
        print(f"  Suggestion: merge into '{group[0][0]}' (or the more complete page)\n")
    return 0


def cmd_merge(args):
    resolver = CanonicalResolver()
    result = resolver.merge_pages(args.source, args.target, dry_run=args.dry_run)
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}{result.get('action', 'failed').upper()}")
    for c in result.get("changes", []):
        print(f"  {c}")
    if result.get("reason"):
        print(f"  Reason: {result['reason']}")
    return 0 if result.get("action") not in ("failed",) else 1


def cmd_redirects(args):
    resolver = CanonicalResolver()
    if not resolver.redirects:
        print("No redirect pages.")
        return 0
    print(f"Redirects ({len(resolver.redirects)}):")
    for old, new in sorted(resolver.redirects.items()):
        print(f"  {old} → {new}")
    return 0


def cmd_aliases(args):
    resolver = CanonicalResolver()
    if not resolver.alias_index:
        print("No aliases registered.")
        return 0

    # Group by target slug
    by_slug: dict[str, list[str]] = {}
    for alias, slug in sorted(resolver.alias_index.items()):
        by_slug.setdefault(slug, []).append(alias)

    print(f"Alias index ({len(resolver.alias_index)} entries, {len(by_slug)} pages):\n")
    for slug in sorted(by_slug.keys()):
        title = resolver.pages.get(slug, {}).get("title", slug)
        aliases = [a for a in by_slug[slug] if a != slug and a != _normalize(slug)]
        print(f"  {slug}: {title}")
        for a in sorted(set(aliases)):
            print(f"    ← {a}")
    return 0


def cmd_add_alias(args):
    resolver = CanonicalResolver()
    ok = resolver.add_alias(args.slug, args.alias)
    if ok:
        print(f"Added alias '{args.alias}' → {args.slug}")
        return 0
    else:
        print(f"Failed to add alias '{args.alias}' to '{args.slug}'")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Clarvis wiki canonical page resolver")
    sub = parser.add_subparsers(dest="command")

    p_resolve = sub.add_parser("resolve", help="Resolve a name to its canonical wiki page")
    p_resolve.add_argument("name", help="Name, alias, or slug to resolve")

    p_detect = sub.add_parser("detect", help="Detect duplicate page groups")
    p_detect.add_argument("--threshold", type=float, default=0.5, help="Similarity threshold (0-1)")

    p_merge = sub.add_parser("merge", help="Merge source page into target")
    p_merge.add_argument("source", help="Source slug (will become redirect)")
    p_merge.add_argument("target", help="Target slug (canonical page)")
    p_merge.add_argument("--dry-run", action="store_true")

    sub.add_parser("redirects", help="List all redirect pages")
    sub.add_parser("aliases", help="Dump the full alias index")

    p_add = sub.add_parser("add-alias", help="Add an alias to a page")
    p_add.add_argument("slug", help="Canonical page slug")
    p_add.add_argument("alias", help="Alias to add")

    args = parser.parse_args()
    handlers = {
        "resolve": cmd_resolve,
        "detect": cmd_detect,
        "merge": cmd_merge,
        "redirects": cmd_redirects,
        "aliases": cmd_aliases,
        "add-alias": cmd_add_alias,
    }
    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

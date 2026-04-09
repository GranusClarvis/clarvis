"""Wiki canonical page resolution — duplicate detection, alias index, redirects, merges.

Spine module: shared library logic for wiki canonical resolution.
CLI wrapper remains at scripts/wiki/wiki_canonical.py.

Ensures one canonical page per concept/entity in the wiki. Handles:
  - Alias resolution: "IIT" → "integrated-information-theory"
  - Duplicate detection: fuzzy title matching + slug similarity
  - Redirect pages: old slugs point to canonical slugs
  - Merge suggestions: groups near-duplicate pages for review
  - Merge execution: combines two pages into one canonical page

Usage (Python):
    from clarvis.wiki.canonical import CanonicalResolver, get_resolver
    resolver = get_resolver()
    slug = resolver.resolve("IIT")
"""

import datetime
import os
import re
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"

TODAY = datetime.date.today().isoformat()

# Type to wiki directory mapping (shared with wiki_compile.py)
TYPE_DIR_MAP = {
    "paper": "concepts",
    "repo": "projects",
    "web": "concepts",
    "transcript": "concepts",
    "concept": "concepts",
    "person": "people",
    "question": "questions",
    "synthesis": "syntheses",
    "timeline": "timelines",
    "procedure": "procedures",
}


# ============================================================
# Text normalization
# ============================================================

def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60]


def _trigrams(text: str) -> set[str]:
    """Generate character trigrams for fuzzy matching."""
    s = _normalize(text)
    if len(s) < 3:
        return {s}
    return {s[i:i+3] for i in range(len(s) - 2)}


def _trigram_similarity(a: str, b: str) -> float:
    """Jaccard similarity of trigram sets. Returns 0.0-1.0."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union) if union else 0.0


# ============================================================
# Frontmatter parser (shared with wiki_compile.py)
# ============================================================

def _parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file."""
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
# CanonicalResolver
# ============================================================

class CanonicalResolver:
    """Builds an alias index from all wiki pages and resolves names to canonical slugs.

    The alias index maps normalized names to canonical slugs:
      - Page title → slug
      - Each alias in frontmatter → slug
      - The slug itself → slug
      - Redirect pages: redirect target → canonical slug
    """

    def __init__(self, wiki_dir: Path = WIKI_DIR):
        self.wiki_dir = wiki_dir
        self.pages: dict[str, dict] = {}       # slug → {path, title, type, aliases, ...}
        self.alias_index: dict[str, str] = {}   # normalized_name → canonical slug
        self.redirects: dict[str, str] = {}     # old_slug → new_slug
        self._build()

    def _build(self):
        """Scan all wiki pages and build the alias index."""
        for md_file in self.wiki_dir.rglob("*.md"):
            if md_file.name == "index.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse_frontmatter(text)
            if not fm:
                continue

            slug = fm.get("slug", md_file.stem)

            # Handle redirect pages
            if fm.get("redirect"):
                self.redirects[slug] = fm["redirect"]
                continue

            title = fm.get("title", slug)
            aliases = fm.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases] if aliases else []

            self.pages[slug] = {
                "path": md_file,
                "title": title,
                "type": fm.get("type", "concept"),
                "aliases": aliases,
                "status": fm.get("status", "draft"),
                "sources": fm.get("sources", []),
                "tags": fm.get("tags", []),
            }

            # Register in alias index
            self.alias_index[_normalize(title)] = slug
            self.alias_index[_normalize(slug)] = slug
            self.alias_index[slug] = slug  # exact slug always maps
            for alias in aliases:
                if alias:
                    self.alias_index[_normalize(alias)] = slug

        # Resolve redirect chains (max 5 hops)
        for old_slug in list(self.redirects.keys()):
            target = self.redirects[old_slug]
            for _ in range(5):
                if target in self.redirects:
                    target = self.redirects[target]
                else:
                    break
            self.redirects[old_slug] = target
            self.alias_index[_normalize(old_slug)] = target
            self.alias_index[old_slug] = target

    def resolve(self, name: str) -> str | None:
        """Resolve a name/alias/slug to its canonical slug. Returns None if not found.

        Tries exact match, then normalized match, then slug-form match.
        """
        # Direct slug match
        if name in self.pages:
            return name
        if name in self.redirects:
            return self.redirects[name]

        # Normalized match
        norm = _normalize(name)
        if norm in self.alias_index:
            return self.alias_index[norm]

        # Try slugified form
        slug_form = _slugify(name)
        if slug_form in self.alias_index:
            return self.alias_index[slug_form]
        if slug_form in self.pages:
            return slug_form

        return None

    def resolve_or_suggest(self, name: str, threshold: float = 0.5) -> tuple[str | None, list[tuple[str, float]]]:
        """Resolve a name, or suggest similar pages if no exact match.

        Returns (canonical_slug_or_None, [(slug, similarity_score), ...]).
        """
        exact = self.resolve(name)
        if exact:
            return exact, []

        # Fuzzy match against all titles and aliases
        candidates = []
        norm = _normalize(name)
        seen = set()

        for reg_name, slug in self.alias_index.items():
            if slug in seen:
                continue
            sim = _trigram_similarity(norm, reg_name)
            if sim >= threshold:
                candidates.append((slug, sim))
                seen.add(slug)

        candidates.sort(key=lambda x: -x[1])
        return None, candidates[:5]

    def find_duplicates(self, threshold: float = 0.6) -> list[list[tuple[str, str, float]]]:
        """Find groups of potentially duplicate pages.

        Returns list of groups, each group is [(slug, title, similarity), ...].
        """
        slugs = list(self.pages.keys())
        if len(slugs) < 2:
            return []

        # Compare all pairs
        pairs: list[tuple[str, str, float]] = []
        for i in range(len(slugs)):
            for j in range(i + 1, len(slugs)):
                s1, s2 = slugs[i], slugs[j]
                t1, t2 = self.pages[s1]["title"], self.pages[s2]["title"]

                # Title similarity
                title_sim = _trigram_similarity(t1, t2)

                # Also check if one title is an alias of the other
                alias_match = False
                for a in self.pages[s1].get("aliases", []):
                    if _normalize(a) == _normalize(t2):
                        alias_match = True
                        break
                for a in self.pages[s2].get("aliases", []):
                    if _normalize(a) == _normalize(t1):
                        alias_match = True
                        break

                # Normalized title equality
                if _normalize(t1) == _normalize(t2):
                    title_sim = 1.0

                effective_sim = max(title_sim, 1.0 if alias_match else 0.0)

                if effective_sim >= threshold:
                    pairs.append((s1, s2, effective_sim))

        if not pairs:
            return []

        # Group connected pairs using union-find
        parent: dict[str, str] = {}

        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for s1, s2, _ in pairs:
            union(s1, s2)

        # Build groups
        groups_map: dict[str, list[tuple[str, str, float]]] = {}
        all_slugs_in_pairs = set()
        for s1, s2, sim in pairs:
            all_slugs_in_pairs.add(s1)
            all_slugs_in_pairs.add(s2)

        for slug in all_slugs_in_pairs:
            root = find(slug)
            if root not in groups_map:
                groups_map[root] = []

        for slug in all_slugs_in_pairs:
            root = find(slug)
            title = self.pages[slug]["title"]
            # Find max similarity with any other member
            max_sim = 0.0
            for s1, s2, sim in pairs:
                if s1 == slug or s2 == slug:
                    max_sim = max(max_sim, sim)
            groups_map[root].append((slug, title, max_sim))

        return [g for g in groups_map.values() if len(g) >= 2]

    def add_alias(self, slug: str, alias: str) -> bool:
        """Add an alias to an existing wiki page's frontmatter."""
        if slug not in self.pages:
            return False

        page_path = self.pages[slug]["path"]
        text = page_path.read_text(encoding="utf-8", errors="replace")

        # Check alias isn't already registered
        norm_alias = _normalize(alias)
        if norm_alias in self.alias_index:
            existing = self.alias_index[norm_alias]
            if existing != slug:
                print(f"Warning: alias '{alias}' already maps to '{existing}'")
                return False
            # Already mapped to this slug
            return True

        # Add to frontmatter aliases list
        if "aliases:" in text:
            # Find the aliases section and add the new one
            lines = text.split("\n")
            new_lines = []
            in_aliases = False
            inserted = False
            for line in lines:
                new_lines.append(line)
                if line.strip().startswith("aliases:"):
                    in_aliases = True
                    # Check if it's an empty list: aliases: []
                    if "[]" in line:
                        new_lines[-1] = "aliases:"
                        new_lines.append(f'  - "{alias}"')
                        inserted = True
                        in_aliases = False
                elif in_aliases and not line.strip().startswith("- "):
                    # End of aliases list — insert before this line
                    new_lines.insert(-1, f'  - "{alias}"')
                    inserted = True
                    in_aliases = False

            if in_aliases and not inserted:
                # Aliases was last in frontmatter
                new_lines.append(f'  - "{alias}"')
                inserted = True

            if inserted:
                page_path.write_text("\n".join(new_lines), encoding="utf-8")
                self.alias_index[norm_alias] = slug
                self.pages[slug]["aliases"].append(alias)
                return True

        return False

    def create_redirect(self, old_slug: str, target_slug: str, page_type: str = "concept") -> Path:
        """Create a redirect page pointing old_slug to target_slug."""
        type_dir = TYPE_DIR_MAP.get(page_type, "concepts")
        redirect_path = self.wiki_dir / type_dir / f"{old_slug}.md"
        redirect_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""---
redirect: "{target_slug}"
title: "Redirect → {target_slug}"
slug: "{old_slug}"
type: {page_type}
created: {TODAY}
---

This page redirects to [{target_slug}](../{type_dir}/{target_slug}.md).
"""
        redirect_path.write_text(content, encoding="utf-8")
        self.redirects[old_slug] = target_slug
        self.alias_index[_normalize(old_slug)] = target_slug
        self.alias_index[old_slug] = target_slug
        return redirect_path

    def merge_pages(self, source_slug: str, target_slug: str, dry_run: bool = False) -> dict:
        """Merge source page into target page.

        - Combines sources lists
        - Merges aliases (source title becomes alias of target)
        - Moves evidence entries
        - Creates redirect from source slug
        - Updates backlinks across the wiki

        Returns {action, changes, redirect_path}.
        """
        if source_slug not in self.pages:
            return {"action": "failed", "reason": f"Source '{source_slug}' not found"}
        if target_slug not in self.pages:
            return {"action": "failed", "reason": f"Target '{target_slug}' not found"}

        source = self.pages[source_slug]
        target = self.pages[target_slug]

        source_path: Path = source["path"]
        target_path: Path = target["path"]

        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        target_text = target_path.read_text(encoding="utf-8", errors="replace")

        changes = []

        # 1. Merge sources into target frontmatter
        for src in source.get("sources", []):
            if src and src not in target_text:
                if "sources:" in target_text:
                    target_text = target_text.replace(
                        "sources:\n", f"sources:\n  - {src}\n", 1
                    )
                    changes.append(f"Added source: {src}")

        # 2. Add source title as alias of target
        source_title = source["title"]
        norm_src = _normalize(source_title)
        norm_tgt = _normalize(target["title"])
        if norm_src != norm_tgt:
            if "aliases:" in target_text:
                if source_title not in target_text:
                    target_text = target_text.replace(
                        "aliases:", f'aliases:\n  - "{source_title}"', 1
                    )
                    # Fix empty list marker if present
                    target_text = target_text.replace('aliases:\n  - "' + source_title + '"\n[]',
                                                       'aliases:\n  - "' + source_title + '"')
                    changes.append(f"Added alias: {source_title}")

        # Add source's aliases to target too
        for alias in source.get("aliases", []):
            if alias and alias not in target_text:
                # Find end of aliases section
                if "aliases:" in target_text:
                    target_text = target_text.replace(
                        "aliases:", f'aliases:\n  - "{alias}"', 1
                    )
                    changes.append(f"Added alias: {alias}")

        # 3. Merge evidence sections
        source_evidence = _extract_section(source_text, "## Evidence")
        if source_evidence:
            evidence_marker = "## Evidence"
            if evidence_marker in target_text:
                target_text = target_text.replace(
                    evidence_marker, evidence_marker + "\n" + source_evidence.strip(), 1
                )
                changes.append("Merged evidence entries")

        # 4. Update date and add history entry
        target_text = re.sub(r'updated: \d{4}-\d{2}-\d{2}', f'updated: {TODAY}', target_text, count=1)
        history_marker = "## Update History"
        if history_marker in target_text:
            merge_note = f"\n- {TODAY}: Merged content from '{source_title}' ({source_slug})."
            target_text = target_text.replace(history_marker, history_marker + merge_note, 1)
            changes.append("Added merge note to update history")

        if dry_run:
            return {"action": "would_merge", "changes": changes}

        # Write updated target
        target_text = _clean_empty_aliases(target_text)
        target_path.write_text(target_text, encoding="utf-8")

        # 5. Replace source file with redirect content
        source_type = source.get("type", "concept")
        type_dir = TYPE_DIR_MAP.get(target.get("type", "concept"), "concepts")
        redirect_content = f"""---
redirect: "{target_slug}"
title: "Redirect → {target_slug}"
slug: "{source_slug}"
type: {source_type}
created: {TODAY}
---

This page redirects to [{target_slug}](../{type_dir}/{target_slug}.md).
"""
        source_path.write_text(redirect_content, encoding="utf-8")
        self.redirects[source_slug] = target_slug
        self.alias_index[_normalize(source_slug)] = target_slug
        self.alias_index[source_slug] = target_slug
        redirect_path = source_path

        changes.append(f"Created redirect: {source_slug} → {target_slug}")

        # 6. Update backlinks across wiki
        link_fixes = self._update_backlinks(source_slug, target_slug)
        if link_fixes:
            changes.append(f"Updated {link_fixes} backlinks")

        return {"action": "merged", "changes": changes, "redirect_path": str(redirect_path)}

    def _update_backlinks(self, old_slug: str, new_slug: str) -> int:
        """Update all wiki pages that link to old_slug to point to new_slug."""
        fixes = 0
        for md_file in self.wiki_dir.rglob("*.md"):
            if md_file.name == "index.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if old_slug not in text:
                continue
            # Replace links like ../concepts/old-slug.md with ../concepts/new-slug.md
            new_text = re.sub(
                rf'(\.\./\w+/){re.escape(old_slug)}(\.md)',
                rf'\g<1>{new_slug}\2',
                text
            )
            if new_text != text:
                md_file.write_text(new_text, encoding="utf-8")
                fixes += 1
        return fixes


def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a markdown section (between heading and next ##)."""
    idx = text.find(heading)
    if idx == -1:
        return ""
    start = idx + len(heading)
    # Find next heading
    next_heading = re.search(r'\n## ', text[start:])
    if next_heading:
        return text[start:start + next_heading.start()]
    return text[start:]


def _clean_empty_aliases(text: str) -> str:
    """Remove stray [] after aliases: if present."""
    text = re.sub(r'aliases:\n(\s+- [^\n]+\n)+\[\]', lambda m: m.group(0).replace('[]', ''), text)
    text = re.sub(r'aliases: \[\]\n', 'aliases:\n', text)
    return text


# ============================================================
# Public API (for use by wiki_compile.py and other scripts)
# ============================================================

_resolver_cache: CanonicalResolver | None = None


def get_resolver(wiki_dir: Path = WIKI_DIR) -> CanonicalResolver:
    """Get or create a cached CanonicalResolver instance."""
    global _resolver_cache
    if _resolver_cache is None or _resolver_cache.wiki_dir != wiki_dir:
        _resolver_cache = CanonicalResolver(wiki_dir)
    return _resolver_cache


def resolve_canonical(name: str) -> str | None:
    """Resolve a name/alias to its canonical wiki slug."""
    return get_resolver().resolve(name)


def find_duplicates(threshold: float = 0.6) -> list:
    """Find groups of potentially duplicate wiki pages."""
    return get_resolver().find_duplicates(threshold)

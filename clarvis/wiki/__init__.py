"""Clarvis wiki subsystem — canonical resolution, shared utilities."""

from clarvis.wiki.canonical import (
    CanonicalResolver,
    get_resolver,
    resolve_canonical,
    find_duplicates,
    TYPE_DIR_MAP,
    WIKI_DIR,
    KNOWLEDGE,
    _normalize,
    _slugify,
    _trigram_similarity,
    _parse_frontmatter,
)

__all__ = [
    "CanonicalResolver",
    "get_resolver",
    "resolve_canonical",
    "find_duplicates",
    "TYPE_DIR_MAP",
    "WIKI_DIR",
    "KNOWLEDGE",
    "_normalize",
    "_slugify",
    "_trigram_similarity",
    "_parse_frontmatter",
]

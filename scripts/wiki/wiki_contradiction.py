#!/usr/bin/env python3
"""Wiki contradiction detector — find conflicting claims across wiki pages.

For each pair of wiki pages that share a tag, compare their Key Claims via
embedding similarity. Flag pairs where claims are semantically similar but
contain negation or opposition patterns.

Usage:
    python3 scripts/wiki/wiki_contradiction.py detect [--threshold 0.65] [--json]
    python3 scripts/wiki/wiki_contradiction.py summary
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from itertools import combinations
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
WIKI_DIR = WORKSPACE / "knowledge" / "wiki"

# ── Negation / opposition lexicon ────────────────────────────────

NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "cannot", "can't", "don't",
    "doesn't", "didn't", "won't", "wouldn't", "shouldn't", "isn't",
    "aren't", "wasn't", "weren't", "hardly", "barely", "scarcely",
    "without", "lack", "lacks", "lacking", "absence", "absent",
    "impossible", "unable", "unlikely", "unnecessary", "none",
}

OPPOSITION_PAIRS = [
    ("increase", "decrease"), ("improve", "worsen"), ("better", "worse"),
    ("more", "less"), ("faster", "slower"), ("higher", "lower"),
    ("stronger", "weaker"), ("enable", "disable"), ("support", "oppose"),
    ("accept", "reject"), ("agree", "disagree"), ("include", "exclude"),
    ("success", "failure"), ("benefit", "harm"), ("advantage", "disadvantage"),
    ("efficient", "inefficient"), ("effective", "ineffective"),
    ("sufficient", "insufficient"), ("possible", "impossible"),
    ("necessary", "unnecessary"), ("relevant", "irrelevant"),
    ("consistent", "inconsistent"), ("complete", "incomplete"),
    ("correct", "incorrect"), ("accurate", "inaccurate"),
    ("true", "false"), ("positive", "negative"),
    ("internal", "external"), ("centralized", "decentralized"),
    ("simple", "complex"), ("static", "dynamic"),
    ("synchronous", "asynchronous"), ("conservative", "radical"),
]


# ── Data structures ──────────────────────────────────────────────

@dataclass
class WikiPage:
    slug: str
    title: str
    path: Path
    tags: list[str]
    claims: list[str]
    status: str = "active"


@dataclass
class Contradiction:
    page_a_slug: str
    page_a_title: str
    claim_a: str
    page_b_slug: str
    page_b_title: str
    claim_b: str
    similarity: float
    opposition_score: float
    shared_tags: list[str]
    evidence: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        """Combined confidence: embedding similarity * opposition evidence."""
        return min(1.0, self.similarity * (0.5 + 0.5 * self.opposition_score))


# ── Parsing ──────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from wiki page text."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    block = text[3:end].strip()
    result: dict[str, Any] = {}
    current_key = None
    current_list: list[str] | None = None

    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list is not None:
                val = stripped[2:].strip().strip('"').strip("'")
                current_list.append(val)
            continue
        if ":" in stripped:
            if current_key and current_list is not None:
                result[current_key] = current_list
                current_list = None
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            current_key = key
            if val == "" or val == "[]":
                current_list = []
            elif val.startswith("[") and val.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                result[key] = items
                current_list = None
            else:
                result[key] = val
                current_list = None

    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _extract_claims(content: str) -> list[str]:
    """Extract Key Claims bullet points from wiki page markdown."""
    claims = []
    in_claims = False
    for line in content.split("\n"):
        if line.strip() == "## Key Claims":
            in_claims = True
            continue
        if in_claims:
            if line.startswith("## "):
                break
            stripped = line.strip()
            # Skip placeholder claims
            if stripped.startswith("- _") and stripped.endswith("_"):
                continue
            if stripped.startswith("- "):
                claim_text = stripped[2:].strip()
                # Strip citation markers
                claim_text = re.sub(r"\[Source:.*?\]", "", claim_text).strip()
                if len(claim_text) > 10:
                    claims.append(claim_text)
    return claims


def _extract_body_claims(content: str) -> list[str]:
    """Fallback: extract claim-like bullet points from body when Key Claims is empty."""
    claims = []
    skip_sections = {"## Update History", "## Open Questions", "## Evidence", "## Related Pages"}
    in_skip = False

    for line in content.split("\n"):
        if line.startswith("## "):
            in_skip = line.strip() in skip_sections
            continue
        if in_skip:
            continue
        stripped = line.strip()
        if stripped.startswith("- **") and ":" in stripped:
            # Bold-prefixed claim like "- **Conservative**: Rich internal models..."
            claim_text = re.sub(r"\*\*.*?\*\*:?\s*", "", stripped[2:]).strip()
            if len(claim_text) > 15:
                claims.append(claim_text)
    return claims


def load_wiki_pages() -> list[WikiPage]:
    """Load all wiki pages with their frontmatter and claims."""
    pages = []
    for md_file in sorted(WIKI_DIR.rglob("*.md")):
        if md_file.name == "index.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm = _parse_frontmatter(text)
        if fm is None:
            continue

        slug = fm.get("slug", md_file.stem)
        title = fm.get("title", slug)
        tags_raw = fm.get("tags", [])
        if isinstance(tags_raw, str):
            tags_raw = [tags_raw]
        # Normalize tags
        tags = [t.strip().lower() for t in tags_raw if t.strip() and not t.strip().startswith("_")]
        status = fm.get("status", "active")

        # Skip redirects and archived pages
        if fm.get("redirect") or status == "archived":
            continue

        claims = _extract_claims(text)
        if not claims:
            claims = _extract_body_claims(text)

        pages.append(WikiPage(
            slug=slug,
            title=title,
            path=md_file,
            tags=tags,
            claims=claims,
            status=status,
        ))

    return pages


# ── Embedding & similarity ───────────────────────────────────────

def _get_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed texts using the brain's ONNX MiniLM model."""
    if not texts:
        return []
    try:
        from clarvis.brain.factory import get_embedding_function
        ef = get_embedding_function(use_onnx=True)
        return ef(texts)
    except ImportError:
        # Fallback: try constants
        from clarvis.brain.constants import get_local_embedding_function
        ef = get_local_embedding_function()
        return ef(texts)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Opposition detection ─────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Simple word tokenization."""
    return set(re.findall(r"[a-z']+", text.lower()))


def _stem_match(token_set: set[str], word: str) -> bool:
    """Check if any token in the set starts with the given word (poor-man's stemming)."""
    for t in token_set:
        if t == word or (len(t) > len(word) and t.startswith(word)):
            return True
    return False


def _negation_score(claim_a: str, claim_b: str) -> tuple[float, list[str]]:
    """Score how likely two claims contradict based on negation/opposition patterns.

    Returns (score 0-1, list of evidence strings).
    """
    tokens_a = _tokenize(claim_a)
    tokens_b = _tokenize(claim_b)
    evidence = []
    score = 0.0

    # Check if one claim has negation words the other lacks
    neg_a = tokens_a & NEGATION_WORDS
    neg_b = tokens_b & NEGATION_WORDS

    if neg_a and not neg_b:
        score += 0.4
        evidence.append(f"negation in A: {', '.join(sorted(neg_a))}")
    elif neg_b and not neg_a:
        score += 0.4
        evidence.append(f"negation in B: {', '.join(sorted(neg_b))}")
    elif neg_a != neg_b and (neg_a or neg_b):
        # Different negation patterns
        score += 0.2
        evidence.append(f"asymmetric negation: A={sorted(neg_a)}, B={sorted(neg_b)}")

    # Check opposition pairs (with stem matching for inflected forms)
    for word_x, word_y in OPPOSITION_PAIRS:
        if (_stem_match(tokens_a, word_x) and _stem_match(tokens_b, word_y)) or \
           (_stem_match(tokens_a, word_y) and _stem_match(tokens_b, word_x)):
            score += 0.3
            evidence.append(f"opposition: {word_x} vs {word_y}")
            break  # One opposition pair is enough signal

    # Check "but" / "however" / "although" — hedging markers
    hedging = {"but", "however", "although", "despite", "whereas", "contrary", "conversely"}
    hedge_a = tokens_a & hedging
    hedge_b = tokens_b & hedging
    if hedge_a or hedge_b:
        score += 0.1
        evidence.append(f"hedging markers: {sorted(hedge_a | hedge_b)}")

    return min(1.0, score), evidence


# ── Core detector ────────────────────────────────────────────────

def find_tag_pairs(pages: list[WikiPage]) -> dict[str, list[WikiPage]]:
    """Group pages by shared tags."""
    tag_index: dict[str, list[WikiPage]] = defaultdict(list)
    for page in pages:
        for tag in page.tags:
            tag_index[tag].append(page)
    # Filter to tags with 2+ pages
    return {tag: pgs for tag, pgs in tag_index.items() if len(pgs) >= 2}


def detect_contradictions(
    pages: list[WikiPage],
    similarity_threshold: float = 0.65,
    min_opposition: float = 0.1,
) -> list[Contradiction]:
    """Detect contradictions across wiki pages sharing tags.

    For each pair of pages sharing a tag, compare claims via embedding
    similarity. Flag pairs where claims are semantically close but contain
    negation or opposition patterns.
    """
    tag_groups = find_tag_pairs(pages)

    if not tag_groups:
        return []

    # Collect all unique claims for batch embedding
    all_claims: list[str] = []
    claim_to_idx: dict[str, int] = {}
    for page in pages:
        for claim in page.claims:
            if claim not in claim_to_idx:
                claim_to_idx[claim] = len(all_claims)
                all_claims.append(claim)

    if not all_claims:
        return []

    # Batch embed all claims
    embeddings = _get_embeddings(all_claims)

    # Compare pairs within each tag group
    contradictions: list[Contradiction] = []
    seen_pairs: set[tuple[str, str, str, str]] = set()  # (slug_a, claim_a, slug_b, claim_b)

    for tag, group_pages in tag_groups.items():
        for page_a, page_b in combinations(group_pages, 2):
            if not page_a.claims or not page_b.claims:
                continue

            # Find shared tags between this pair
            shared_tags = sorted(set(page_a.tags) & set(page_b.tags))

            for claim_a in page_a.claims:
                idx_a = claim_to_idx[claim_a]
                emb_a = embeddings[idx_a]

                for claim_b in page_b.claims:
                    # Deduplicate
                    pair_key = (page_a.slug, claim_a, page_b.slug, claim_b)
                    reverse_key = (page_b.slug, claim_b, page_a.slug, claim_a)
                    if pair_key in seen_pairs or reverse_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    idx_b = claim_to_idx[claim_b]
                    emb_b = embeddings[idx_b]

                    sim = _cosine_similarity(emb_a, emb_b)

                    if sim < similarity_threshold:
                        continue

                    # Check for opposition signals
                    opp_score, evidence = _negation_score(claim_a, claim_b)

                    if opp_score < min_opposition:
                        continue

                    contradictions.append(Contradiction(
                        page_a_slug=page_a.slug,
                        page_a_title=page_a.title,
                        claim_a=claim_a,
                        page_b_slug=page_b.slug,
                        page_b_title=page_b.title,
                        claim_b=claim_b,
                        similarity=round(sim, 4),
                        opposition_score=round(opp_score, 4),
                        shared_tags=shared_tags,
                        evidence=evidence,
                    ))

    # Sort by confidence descending
    contradictions.sort(key=lambda c: c.confidence, reverse=True)
    return contradictions


# ── Report formatting ────────────────────────────────────────────

def format_report(contradictions: list[Contradiction], pages: list[WikiPage]) -> str:
    """Format a human-readable contradiction report."""
    lines = [
        "# Wiki Contradiction Report",
        "",
        f"Pages scanned: {len(pages)}",
        f"Pages with claims: {sum(1 for p in pages if p.claims)}",
        f"Total claims: {sum(len(p.claims) for p in pages)}",
        f"Contradictions found: {len(contradictions)}",
        "",
    ]

    if not contradictions:
        lines.append("No contradictions detected. This could mean:")
        lines.append("- Pages are consistent")
        lines.append("- Most pages have placeholder claims (need extraction)")
        lines.append("- Pages don't share enough tags to be compared")
        lines.append("")

        # Show stats about tag overlap
        tag_groups = find_tag_pairs(pages)
        if tag_groups:
            lines.append(f"Tag groups with 2+ pages: {len(tag_groups)}")
            for tag, pgs in sorted(tag_groups.items(), key=lambda x: -len(x[1])):
                lines.append(f"  [{tag}] {len(pgs)} pages: {', '.join(p.slug for p in pgs)}")
        else:
            lines.append("No tags shared across multiple pages.")
        return "\n".join(lines)

    lines.append("---")
    lines.append("")

    for i, c in enumerate(contradictions, 1):
        lines.extend([
            f"## Contradiction #{i} (confidence: {c.confidence:.2f})",
            "",
            f"**Page A**: {c.page_a_title} (`{c.page_a_slug}`)",
            f"> {c.claim_a}",
            "",
            f"**Page B**: {c.page_b_title} (`{c.page_b_slug}`)",
            f"> {c.claim_b}",
            "",
            f"- Semantic similarity: {c.similarity:.3f}",
            f"- Opposition score: {c.opposition_score:.3f}",
            f"- Shared tags: {', '.join(c.shared_tags)}",
            f"- Evidence: {'; '.join(c.evidence)}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wiki contradiction detector")
    sub = parser.add_subparsers(dest="command", required=True)

    detect_p = sub.add_parser("detect", help="Detect contradictions across wiki pages")
    detect_p.add_argument("--threshold", type=float, default=0.65,
                          help="Minimum embedding similarity to consider (default: 0.65)")
    detect_p.add_argument("--min-opposition", type=float, default=0.1,
                          help="Minimum opposition score to flag (default: 0.1)")
    detect_p.add_argument("--json", action="store_true", dest="json_output",
                          help="Output as JSON")

    sub.add_parser("summary", help="Show wiki claim statistics")

    args = parser.parse_args()

    if args.command == "summary":
        pages = load_wiki_pages()
        tag_groups = find_tag_pairs(pages)
        total_claims = sum(len(p.claims) for p in pages)
        with_claims = [p for p in pages if p.claims]

        print(f"Wiki pages: {len(pages)}")
        print(f"Pages with claims: {len(with_claims)}")
        print(f"Total claims: {total_claims}")
        print(f"Tag groups (2+ pages): {len(tag_groups)}")
        print()
        for tag, pgs in sorted(tag_groups.items(), key=lambda x: -len(x[1])):
            claim_count = sum(len(p.claims) for p in pgs)
            print(f"  [{tag}] {len(pgs)} pages, {claim_count} claims")
            for p in pgs:
                print(f"    - {p.slug} ({len(p.claims)} claims)")
        if not with_claims:
            print("\nNote: No pages have extracted claims. Run claim extraction first.")
        return

    if args.command == "detect":
        pages = load_wiki_pages()
        print(f"Loaded {len(pages)} wiki pages", file=sys.stderr)

        contradictions = detect_contradictions(
            pages,
            similarity_threshold=args.threshold,
            min_opposition=args.min_opposition,
        )

        if args.json_output:
            output = {
                "pages_scanned": len(pages),
                "pages_with_claims": sum(1 for p in pages if p.claims),
                "total_claims": sum(len(p.claims) for p in pages),
                "contradictions": [
                    {**asdict(c), "confidence": c.confidence}
                    for c in contradictions
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_report(contradictions, pages))


if __name__ == "__main__":
    main()

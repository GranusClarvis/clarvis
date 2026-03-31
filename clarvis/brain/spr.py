"""Sparse Priming Representations (SPR) for brain memory compression.

Compresses long memories into minimal token priming representations that
reconstruct meaning when fed to an LLM.  Based on the SPR concept: extract
core semantic primitives (entities, relationships, assertions, actions) so
an LLM can expand them back into full context.

Usage:
    from clarvis.brain.spr import encode_spr, decode_spr, batch_encode

    encoded = encode_spr("Long memory text about system architecture...")
    # => {"primitives": [...], "entities": [...], "relations": [...],
    #     "tokens_original": 42, "tokens_spr": 18, "compression_ratio": 0.57}

    decoded = decode_spr(encoded)
    # => Reconstructed prose from primitives

CLI:
    python3 -m clarvis.brain.spr encode "text to compress"
    python3 -m clarvis.brain.spr decode '{"primitives": [...]}'
    python3 -m clarvis.brain.spr test          # Test on 20 brain memories
    python3 -m clarvis.brain.spr stats         # Compression stats across brain
"""

import json
import re
import sys
from collections import Counter
from typing import Any

# ---------------------------------------------------------------------------
# Token estimation (whitespace-split approximation, no tokenizer dependency)
# ---------------------------------------------------------------------------

def _token_count(text: str) -> int:
    """Estimate token count via whitespace split (good enough for ratios)."""
    return len(text.split())


# ---------------------------------------------------------------------------
# SPR Extraction Pipeline
# ---------------------------------------------------------------------------

# Common stopwords to filter from entity/keyword extraction
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "out off over under again further then once that this these those "
    "and but or nor not so yet both either neither each every all any "
    "few more most other some such no only same than too very it its "
    "i me my we our you your he him his she her they them their what "
    "which who whom how when where why here there also just about up if".split()
)

# Patterns for structured memory formats
_EPISODE_PAT = re.compile(r"^Episode:\s*(.+?)\s*->\s*(\w+)", re.IGNORECASE)
_PROCEDURE_PAT = re.compile(r"^Procedure:\s*(\S+)\s*[—–-]\s*(.+)", re.IGNORECASE)
_GOAL_PAT = re.compile(r"^(?:Goal:\s*)?(.+?):\s*(\d+)%", re.IGNORECASE)
_INSIGHT_PAT = re.compile(r"^Cross-domain insight:\s*Concept\s+'(\w+)'\s+bridges\s+(\d+)\s+domains", re.IGNORECASE)
_REASONING_PAT = re.compile(r"^Reasoning chain(?:\s*:)?\s*(?:Task:\s*)?(.+?)(?:\.\s*Initial thought:|$)", re.IGNORECASE)
_META_PAT = re.compile(r"^Meta-cognition:\s*Completed\s+'(.+?)'\s+successfully\s+in\s+(\d+)s", re.IGNORECASE)
_SOFT_FAIL_PAT = re.compile(r"^Soft failure:\s*Task:\s*(.+?)\s*[—–-]\s*(.+)", re.IGNORECASE)
_CAPABILITY_PAT = re.compile(r"^Capability assessment", re.IGNORECASE)
_RESEARCH_PAT = re.compile(r"^\[RESEARCH.*?\]\s*References?:\s*(.+)", re.IGNORECASE | re.DOTALL)
_PRIORITIES_PAT = re.compile(r"^Current priorities", re.IGNORECASE)


def _extract_entities(text: str) -> list[str]:
    """Extract key entities (capitalized phrases, technical terms)."""
    # Find capitalized multi-word phrases
    caps = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
    # Find technical terms (camelCase, snake_case, dotted.paths)
    tech = re.findall(r"\b([a-z]+_[a-z_]+|[a-z]+\.[a-z_.]+|[a-z]+[A-Z]\w+)\b", text)
    # Find quoted terms
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", text)
    quoted_flat = [q[0] or q[1] for q in quoted]

    seen = set()
    entities = []
    for e in caps + tech + quoted_flat:
        e_lower = e.lower()
        if e_lower not in _STOPWORDS and e_lower not in seen and len(e) > 2:
            seen.add(e_lower)
            entities.append(e)
    return entities[:15]  # Cap to avoid bloat


def _extract_relations(text: str) -> list[str]:
    """Extract key relationships and assertions as compact statements."""
    relations = []

    # "X connects to Y", "X bridges Y", "X links to Y"
    for pat in [
        r"(\w[\w\s]{1,30})\s+(?:connects?|bridges?|links?)\s+(?:to\s+)?(\w[\w\s]{1,30})",
        r"(\w[\w\s]{1,30})\s+(?:depends?\s+on|requires?|imports?)\s+(\w[\w\s]{1,30})",
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            relations.append(f"{m.group(1).strip()} -> {m.group(2).strip()}")

    # "X is/are Y" assertions
    for m in re.finditer(r"(\w[\w\s]{1,20})\s+(?:is|are)\s+([\w\s]{3,30}?)(?:\.|,|$)", text):
        subj, obj = m.group(1).strip(), m.group(2).strip()
        if subj.lower() not in _STOPWORDS and len(subj) > 2:
            relations.append(f"{subj} = {obj}")

    return relations[:10]


def _extract_actions(text: str) -> list[str]:
    """Extract action/outcome statements."""
    actions = []
    for pat in [
        r"(?:implement|create|add|fix|remove|update|migrate|refactor|test|run|build)\w*\s+(.{5,60}?)(?:\.|,|$)",
        r"(?:completed?|succeeded?|failed?|resolved?)\s+(.{5,60}?)(?:\.|,|$)",
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            actions.append(m.group(0).strip().rstrip(".,"))
    return actions[:8]


def _extract_keywords(text: str) -> list[str]:
    """Extract top keywords by frequency (excluding stopwords)."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(8)]


def _compress_structured(text: str) -> dict[str, Any] | None:
    """Try to compress known structured memory formats directly."""

    # Episode format
    m = _EPISODE_PAT.match(text)
    if m:
        return {
            "type": "episode",
            "primitives": [f"EPISODE: {m.group(1).strip()}"],
            "outcome": m.group(2),
            "entities": _extract_entities(m.group(1)),
        }

    # Procedure format
    m = _PROCEDURE_PAT.match(text)
    if m:
        return {
            "type": "procedure",
            "primitives": [f"PROC({m.group(1)}): {m.group(2).strip()}"],
            "entities": _extract_entities(text),
        }

    # Goal format
    m = _GOAL_PAT.match(text)
    if m:
        return {
            "type": "goal",
            "primitives": [f"GOAL: {m.group(1).strip()} @ {m.group(2)}%"],
            "entities": _extract_entities(m.group(1)),
        }

    # Cross-domain insight
    m = _INSIGHT_PAT.match(text)
    if m:
        return {
            "type": "insight",
            "primitives": [f"BRIDGE: '{m.group(1)}' spans {m.group(2)} domains"],
            "entities": [m.group(1)],
        }

    # Meta-cognition completion
    m = _META_PAT.match(text)
    if m:
        return {
            "type": "meta",
            "primitives": [f"DONE: {m.group(1).strip()} ({m.group(2)}s)"],
            "entities": _extract_entities(m.group(1)),
        }

    # Soft failure
    m = _SOFT_FAIL_PAT.match(text)
    if m:
        return {
            "type": "failure",
            "primitives": [f"FAIL: {m.group(1).strip()}", f"REASON: {m.group(2).strip()}"],
            "entities": _extract_entities(text),
        }

    # Reasoning chain
    m = _REASONING_PAT.match(text)
    if m:
        return {
            "type": "reasoning",
            "primitives": [f"CHAIN: {m.group(1).strip()[:120]}"],
            "entities": _extract_entities(text),
        }

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_spr(text: str) -> dict[str, Any]:
    """Encode text into a Sparse Priming Representation.

    Returns dict with:
        primitives: list[str]   — core semantic statements (the SPR)
        entities: list[str]     — key entities mentioned
        relations: list[str]    — relationships between entities
        keywords: list[str]     — top frequency keywords
        tokens_original: int    — estimated original token count
        tokens_spr: int         — estimated SPR token count
        compression_ratio: float — tokens_spr / tokens_original
        type: str               — detected memory type or 'general'
    """
    if not text or not text.strip():
        return {
            "primitives": [], "entities": [], "relations": [],
            "keywords": [], "tokens_original": 0, "tokens_spr": 0,
            "compression_ratio": 1.0, "type": "empty",
        }

    text = text.strip()
    tokens_orig = _token_count(text)

    # Very short texts: no compression benefit, pass through
    if tokens_orig < 25:
        return {
            "primitives": [text], "entities": _extract_entities(text),
            "relations": [], "keywords": _extract_keywords(text),
            "tokens_original": tokens_orig, "tokens_spr": tokens_orig,
            "compression_ratio": 1.0, "type": "passthrough",
        }

    # Try structured extraction first (known memory formats)
    structured = _compress_structured(text)
    if structured:
        primitives = structured["primitives"]
        entities = structured.get("entities", [])
        relations = structured.get("relations", [])
        keywords = _extract_keywords(text)
        mem_type = structured["type"]
    else:
        # General extraction pipeline
        mem_type = "general"

        # Split into sentences for primitive extraction
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # For short texts (< 30 tokens), the text IS the primitive
        if tokens_orig < 30:
            primitives = [text]
        else:
            # Extract the most informative sentences as primitives
            # Score by: information density (unique non-stopword ratio)
            scored = []
            for sent in sentences:
                words = sent.lower().split()
                if not words:
                    continue
                info_words = [w for w in words if w.strip(".,;:!?()[]") not in _STOPWORDS]
                density = len(set(info_words)) / max(len(words), 1)
                scored.append((density, sent.strip()))

            scored.sort(key=lambda x: -x[0])

            # Take top sentences, up to ~40% of original token budget
            budget = max(tokens_orig * 0.4, 10)
            primitives = []
            used = 0
            for _, sent in scored:
                stokens = _token_count(sent)
                if used + stokens > budget and primitives:
                    break
                primitives.append(sent)
                used += stokens

        entities = _extract_entities(text)
        relations = _extract_relations(text)
        keywords = _extract_keywords(text)

    # Build SPR text for token counting
    spr_text = " | ".join(primitives)
    if entities:
        spr_text += " [" + ", ".join(entities[:8]) + "]"
    tokens_spr = _token_count(spr_text)

    # Safety: if SPR is longer than original, fall back to passthrough
    if tokens_spr >= tokens_orig:
        return {
            "primitives": [text], "entities": entities,
            "relations": relations, "keywords": keywords,
            "tokens_original": tokens_orig, "tokens_spr": tokens_orig,
            "compression_ratio": 1.0, "type": "passthrough",
        }

    return {
        "primitives": primitives,
        "entities": entities,
        "relations": relations,
        "keywords": keywords,
        "tokens_original": tokens_orig,
        "tokens_spr": tokens_spr,
        "compression_ratio": round(tokens_spr / max(tokens_orig, 1), 3),
        "type": mem_type,
    }


def decode_spr(spr: dict[str, Any]) -> str:
    """Reconstruct prose from an SPR encoding.

    This produces a compact but readable reconstruction from the primitives,
    entities, and relations. For full semantic reconstruction, feed the SPR
    to an LLM with: "Expand this SPR into full context: {spr}"
    """
    parts = []

    # Reconstruct from primitives
    primitives = spr.get("primitives", [])
    if primitives:
        parts.append(". ".join(primitives))

    # Add entity context
    entities = spr.get("entities", [])
    if entities:
        parts.append(f"Key entities: {', '.join(entities)}")

    # Add relationships
    relations = spr.get("relations", [])
    if relations:
        parts.append("Relations: " + "; ".join(relations))

    if not parts:
        return ""

    return ". ".join(parts) + "."


def batch_encode(memories: list[dict], text_key: str = "document") -> list[dict[str, Any]]:
    """Encode a batch of memory dicts, returning SPR encodings with IDs.

    Args:
        memories: list of memory dicts (from brain.recall())
        text_key: key to extract text from (default: 'document')

    Returns:
        list of dicts with 'id', 'collection', 'spr', and 'original_tokens'
    """
    results = []
    for mem in memories:
        text = mem.get(text_key, "")
        spr = encode_spr(text)
        results.append({
            "id": mem.get("id", ""),
            "collection": mem.get("collection", ""),
            "spr": spr,
            "original_tokens": spr["tokens_original"],
            "spr_tokens": spr["tokens_spr"],
        })
    return results


def spr_stats(encodings: list[dict]) -> dict[str, Any]:
    """Compute aggregate statistics from batch encoding results."""
    if not encodings:
        return {"count": 0}

    total_orig = sum(e["original_tokens"] for e in encodings)
    total_spr = sum(e["spr_tokens"] for e in encodings)
    ratios = [e["spr"]["compression_ratio"] for e in encodings]
    types = Counter(e["spr"]["type"] for e in encodings)

    return {
        "count": len(encodings),
        "total_original_tokens": total_orig,
        "total_spr_tokens": total_spr,
        "tokens_saved": total_orig - total_spr,
        "overall_compression_ratio": round(total_spr / max(total_orig, 1), 3),
        "mean_compression_ratio": round(sum(ratios) / len(ratios), 3),
        "min_ratio": round(min(ratios), 3),
        "max_ratio": round(max(ratios), 3),
        "type_distribution": dict(types),
    }


# ---------------------------------------------------------------------------
# Test harness: encode 20 diverse brain memories
# ---------------------------------------------------------------------------

def _test_on_brain(n: int = 20) -> dict[str, Any]:
    """Test SPR encoding on n diverse memories from the brain."""
    from clarvis.brain import brain

    collections = [
        "clarvis-learnings", "clarvis-procedures", "clarvis-episodes",
        "clarvis-goals", "clarvis-identity", "clarvis-context",
        "autonomous-learning",
    ]

    all_memories = []
    queries = [
        "system architecture cognitive memory reasoning",
        "performance optimization benchmark metrics",
        "goal progress capability assessment",
    ]

    for col in collections:
        for q in queries:
            try:
                results = brain.recall(q, n=3, collections=[col])
                all_memories.extend(results)
            except Exception:
                pass

    # Deduplicate by ID, take first n
    seen_ids = set()
    unique = []
    for m in all_memories:
        mid = m.get("id", id(m))
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique.append(m)
    unique = unique[:n]

    # Encode all
    encodings = batch_encode(unique)
    stats = spr_stats(encodings)

    # Print detailed results
    print(f"\n{'='*70}")
    print(f"SPR Test Results — {len(encodings)} memories encoded")
    print(f"{'='*70}\n")

    for i, enc in enumerate(encodings):
        spr = enc["spr"]
        print(f"  {i+1:2d}. [{enc['collection']:<25s}] type={spr['type']:<12s} "
              f"tokens: {enc['original_tokens']:>4d} -> {enc['spr_tokens']:>3d} "
              f"(ratio={spr['compression_ratio']:.2f})")
        for p in spr["primitives"][:2]:
            print(f"      SPR: {p[:100]}")
        print()

    print(f"{'='*70}")
    print(f"  Total original tokens: {stats['total_original_tokens']}")
    print(f"  Total SPR tokens:      {stats['total_spr_tokens']}")
    print(f"  Tokens saved:          {stats['tokens_saved']}")
    print(f"  Overall compression:   {stats['overall_compression_ratio']:.3f}")
    print(f"  Mean compression:      {stats['mean_compression_ratio']:.3f}")
    print(f"  Range:                 {stats['min_ratio']:.3f} - {stats['max_ratio']:.3f}")
    print(f"  Type distribution:     {stats['type_distribution']}")
    print(f"{'='*70}\n")

    # Roundtrip test: decode and check non-empty
    decoded_ok = 0
    for enc in encodings:
        decoded = decode_spr(enc["spr"])
        if decoded and len(decoded) > 10:
            decoded_ok += 1

    print(f"  Decode roundtrip: {decoded_ok}/{len(encodings)} produced readable output")

    return {"stats": stats, "encodings": encodings, "decode_ok": decoded_ok}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m clarvis.brain.spr <command> [args]")
        print("Commands: encode <text>, decode <json>, test [n], stats")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "encode":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read()
        result = encode_spr(text)
        print(json.dumps(result, indent=2))

    elif cmd == "decode":
        data = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read()
        spr = json.loads(data)
        print(decode_spr(spr))

    elif cmd == "test":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        result = _test_on_brain(n)
        ok = result["decode_ok"] == len(result["encodings"])
        ratio = result["stats"]["overall_compression_ratio"]
        print(f"\nPASS: compression={ratio:.3f}, decode={result['decode_ok']}/{len(result['encodings'])}"
              if ok and ratio < 0.85
              else f"\nWARN: compression={ratio:.3f}, decode={result['decode_ok']}/{len(result['encodings'])}")

    elif cmd == "stats":
        result = _test_on_brain(50)
        print(json.dumps(result["stats"], indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wiki-first retrieval bridge — answer from wiki pages, expand via graph neighbors.

Preferred retrieval path for research Q&A:
  1. Semantic search wiki memories in ClarvisDB (clarvis-learnings, source=wiki/*)
  2. Expand top hits via graph-neighbor traversal (mentions, supports, derived_from, etc.)
  3. Load linked raw evidence from wiki page sources
  4. Fall back to broad brain recall if wiki coverage is insufficient

Usage:
    python3 wiki_retrieval.py query "What is IIT?"
    python3 wiki_retrieval.py query "episodic memory architectures" --expand
    python3 wiki_retrieval.py query "compare ACT-R and GWT" --raw --max-pages 5
"""

import argparse
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
KNOWLEDGE = WORKSPACE / "knowledge"
WIKI_DIR = KNOWLEDGE / "wiki"

# Lazy brain import
_brain = None


def _get_brain():
    global _brain
    if _brain is None:
        from clarvis.brain import brain as b
        _brain = b
    return _brain


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
# Wiki-first retrieval
# ============================================================

def _is_wiki_memory(result: dict) -> bool:
    """Check if a brain recall result is from a wiki page."""
    source = result.get("metadata", {}).get("source", "")
    mem_id = result.get("id", "")
    return source.startswith("wiki/") or mem_id.startswith("wiki_")


def _slug_from_result(result: dict) -> str | None:
    """Extract wiki slug from a brain result."""
    mem_id = result.get("id", "")
    if mem_id.startswith("wiki_"):
        return mem_id[5:]
    source = result.get("metadata", {}).get("source", "")
    if source.startswith("wiki/"):
        return source[5:]
    return None


def _find_page_path(slug: str) -> Path | None:
    """Find the wiki page file for a slug."""
    for md_file in WIKI_DIR.rglob(f"{slug}.md"):
        if md_file.name != "index.md":
            return md_file
    return None


def _load_page_content(slug: str) -> dict | None:
    """Load a wiki page by slug. Returns {slug, title, type, content, sources, path}."""
    path = _find_page_path(slug)
    if not path:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = _parse_frontmatter(text)
    if not fm:
        return None
    return {
        "slug": slug,
        "title": fm.get("title", slug),
        "type": fm.get("type", "concept"),
        "confidence": fm.get("confidence", "medium"),
        "sources": fm.get("sources", []),
        "content": text,
        "path": str(path),
    }


def _load_raw_source(src_path: str, max_len: int = 3000) -> dict | None:
    """Load a raw source file. Returns {path, content} or None."""
    if src_path.startswith("raw/"):
        full = KNOWLEDGE / src_path
    elif src_path.startswith("knowledge/raw/"):
        full = WORKSPACE / src_path
    else:
        return None
    if not full.exists():
        return None
    try:
        content = full.read_text(encoding="utf-8", errors="replace")[:max_len]
        return {"path": src_path, "content": content}
    except OSError:
        return None


def _get_graph_neighbors(memory_id: str, max_hops: int = 1) -> list[dict]:
    """Get graph neighbors of a memory via brain graph traversal."""
    brain = _get_brain()
    neighbors = []
    try:
        if brain._sqlite_store is not None:
            edges = brain._sqlite_store.get_edges(from_id=memory_id)
            edges += brain._sqlite_store.get_edges(to_id=memory_id)
            for edge in edges:
                neighbor_id = edge["to_id"] if edge["from_id"] == memory_id else edge["from_id"]
                neighbors.append({
                    "id": neighbor_id,
                    "relation": edge.get("type", "related"),
                    "direction": "outgoing" if edge["from_id"] == memory_id else "incoming",
                })
    except Exception:
        pass
    return neighbors[:20]


def _wiki_filtered_query(query: str, max_pages: int) -> list[dict]:
    """Query ChromaDB directly with document filter to find wiki memories only.

    Uses where_document={"$contains": "Wiki:"} to restrict to wiki memories
    (all wiki summaries start with "Wiki: {title}" from _build_summary).
    This avoids post-hoc filtering which loses wiki results to non-wiki competition.
    """
    brain = _get_brain()
    col = brain.collections.get("clarvis-learnings")
    if col is None:
        return []

    try:
        results = col.query(
            query_texts=[query],
            n_results=max_pages,
            where_document={"$contains": "Wiki:"},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    hits = []
    if not (results.get("ids") and results["ids"][0]):
        return hits

    for i, mid in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i] if results.get("metadatas") else {}
        distance = results["distances"][0][i] if results.get("distances") else 999
        slug = None
        if mid.startswith("wiki_"):
            slug = mid[5:]
        elif meta.get("source", "").startswith("wiki/"):
            slug = meta["source"][5:]
        if slug:
            hits.append({
                "slug": slug,
                "distance": distance,
                "memory_id": mid,
            })
    return hits


def wiki_retrieve(query: str, max_pages: int = 5, expand_graph: bool = True,
                  include_raw: bool = False, fallback_broad: bool = True) -> dict:
    """Wiki-first retrieval: search wiki memories, expand via graph, load evidence.

    Returns {
        query, wiki_hits: [{slug, title, type, confidence, distance, content?}],
        graph_neighbors: [{id, relation, slug?, title?}],
        raw_sources: [{path, content}],
        broad_hits: [{id, document, distance}],  # only if fallback_broad and wiki insufficient
        coverage: "wiki"|"wiki+graph"|"broad"|"none"
    }
    """
    brain = _get_brain()

    # Step 1: Wiki-filtered semantic search (direct ChromaDB query with document filter)
    wiki_hits = _wiki_filtered_query(query, max_pages)
    seen_slugs = {h["slug"] for h in wiki_hits}

    # Enrich wiki hits with page content
    enriched_hits = []
    for hit in wiki_hits:
        page = _load_page_content(hit["slug"])
        if page:
            enriched_hits.append({
                **page,
                "distance": hit["distance"],
                "memory_id": hit["memory_id"],
            })
        else:
            enriched_hits.append(hit)

    # Step 2: Graph expansion
    graph_neighbors = []
    neighbor_slugs = set()
    if expand_graph and enriched_hits:
        for hit in enriched_hits[:3]:  # Expand top 3 hits
            mid = hit.get("memory_id", f"wiki_{hit['slug']}")
            for neighbor in _get_graph_neighbors(mid):
                nid = neighbor["id"]
                if nid.startswith("wiki_"):
                    n_slug = nid[5:]
                    if n_slug not in seen_slugs and n_slug not in neighbor_slugs:
                        neighbor_slugs.add(n_slug)
                        n_page = _load_page_content(n_slug)
                        graph_neighbors.append({
                            "id": nid,
                            "relation": neighbor["relation"],
                            "direction": neighbor["direction"],
                            "slug": n_slug,
                            "title": n_page["title"] if n_page else n_slug,
                        })

    # Step 3: Load raw evidence from top wiki hits
    raw_sources = []
    if include_raw:
        raw_seen = set()
        for hit in enriched_hits[:3]:
            for src in hit.get("sources", []):
                if src not in raw_seen and src.startswith("raw/"):
                    raw_seen.add(src)
                    loaded = _load_raw_source(src)
                    if loaded:
                        raw_sources.append(loaded)

    # Step 4: Broad fallback if wiki coverage is weak
    broad_hits = []
    if fallback_broad and len(enriched_hits) < 2:
        broad_results = brain.recall(query, n=5, caller="wiki_retrieval_fallback")
        for r in broad_results:
            if not _is_wiki_memory(r):
                broad_hits.append({
                    "id": r.get("id", ""),
                    "document": r.get("document", "")[:500],
                    "distance": r.get("distance", 999),
                    "collection": r.get("collection", ""),
                })
                if len(broad_hits) >= 3:
                    break

    # Determine coverage level
    if enriched_hits and graph_neighbors:
        coverage = "wiki+graph"
    elif enriched_hits:
        coverage = "wiki"
    elif broad_hits:
        coverage = "broad"
    else:
        coverage = "none"

    return {
        "query": query,
        "wiki_hits": enriched_hits,
        "graph_neighbors": graph_neighbors,
        "raw_sources": raw_sources,
        "broad_hits": broad_hits,
        "coverage": coverage,
    }


def format_context(result: dict, max_tokens: int = 4000) -> str:
    """Format retrieval result into a context string for LLM or answer generation.

    Prioritizes wiki content, then graph neighbors, then raw, then broad.
    """
    parts = []
    budget = max_tokens

    # Wiki pages (highest priority)
    for hit in result.get("wiki_hits", []):
        if budget <= 0:
            break
        title = hit.get("title", hit.get("slug", "?"))
        confidence = hit.get("confidence", "?")
        content = hit.get("content", "")
        # Strip frontmatter for cleaner context
        if content.startswith("---"):
            end = content.find("\n---", 3)
            if end != -1:
                content = content[end + 4:].strip()
        snippet = content[:min(1500, budget)]
        block = f"## Wiki: {title} (confidence: {confidence})\n{snippet}\n"
        parts.append(block)
        budget -= len(block)

    # Graph neighbors (mention titles)
    if result.get("graph_neighbors") and budget > 200:
        neighbor_lines = []
        for n in result["graph_neighbors"][:5]:
            neighbor_lines.append(f"- [{n['relation']}] {n.get('title', n['id'])}")
        block = "## Related (graph neighbors)\n" + "\n".join(neighbor_lines) + "\n"
        parts.append(block)
        budget -= len(block)

    # Raw sources
    for src in result.get("raw_sources", []):
        if budget <= 0:
            break
        snippet = src["content"][:min(1000, budget)]
        block = f"## Raw: {src['path']}\n{snippet}\n"
        parts.append(block)
        budget -= len(block)

    # Broad fallback
    for hit in result.get("broad_hits", []):
        if budget <= 0:
            break
        block = f"## Brain: {hit.get('collection', '?')}\n{hit['document']}\n"
        parts.append(block)
        budget -= len(block)

    return "\n".join(parts)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Wiki-first retrieval bridge")
    sub = parser.add_subparsers(dest="command")

    p_query = sub.add_parser("query", help="Query wiki-first retrieval")
    p_query.add_argument("question", help="The query")
    p_query.add_argument("--max-pages", type=int, default=5)
    p_query.add_argument("--expand", action="store_true", default=True,
                         help="Expand via graph neighbors (default: true)")
    p_query.add_argument("--no-expand", action="store_true", help="Disable graph expansion")
    p_query.add_argument("--raw", action="store_true", help="Include raw source content")
    p_query.add_argument("--context", action="store_true",
                         help="Output formatted context string instead of JSON")

    args = parser.parse_args()

    if args.command == "query":
        expand = not args.no_expand
        result = wiki_retrieve(
            args.question,
            max_pages=args.max_pages,
            expand_graph=expand,
            include_raw=args.raw,
        )

        if args.context:
            print(format_context(result))
        else:
            # Print summary
            print(f"Query: {result['query']}")
            print(f"Coverage: {result['coverage']}")
            print(f"Wiki hits: {len(result['wiki_hits'])}")
            for h in result["wiki_hits"]:
                title = h.get("title", h.get("slug", "?"))
                dist = h.get("distance", "?")
                print(f"  [{dist:.3f}] {title}" if isinstance(dist, float) else f"  [{dist}] {title}")
            if result["graph_neighbors"]:
                print(f"Graph neighbors: {len(result['graph_neighbors'])}")
                for n in result["graph_neighbors"][:5]:
                    print(f"  [{n['relation']}] {n.get('title', n['id'])}")
            if result["raw_sources"]:
                print(f"Raw sources: {len(result['raw_sources'])}")
            if result["broad_hits"]:
                print(f"Broad fallback hits: {len(result['broad_hits'])}")
                for h in result["broad_hits"]:
                    print(f"  [{h.get('distance', '?'):.3f}] {h['document'][:80]}...")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wiki argument mapper — extract argument structure from wiki page claims.

Given a wiki page with Key Claims, extract the argument structure:
premises → conclusion, supports/rebuts relations. Output a directed graph
of arguments and optionally visualize as ASCII.

Usage:
    python3 scripts/wiki/wiki_argument_map.py map <slug>
    python3 scripts/wiki/wiki_argument_map.py map-all [--min-claims 2]
    python3 scripts/wiki/wiki_argument_map.py ascii <slug>
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"))
WIKI_DIR = WORKSPACE / "knowledge" / "wiki"


# ── Types ────────────────────────────────────────────────────────

class RelationType(str, Enum):
    SUPPORTS = "supports"
    REBUTS = "rebuts"
    QUALIFIES = "qualifies"  # "but", "however", partial agreement


@dataclass
class ArgumentNode:
    """A single claim/premise/conclusion in the argument graph."""
    id: str
    text: str
    role: str  # "premise", "conclusion", "claim", "qualifier"
    page_slug: str = ""

    def short(self, max_len: int = 60) -> str:
        t = self.text[:max_len]
        return t + "..." if len(self.text) > max_len else t


@dataclass
class ArgumentEdge:
    """A directed relation between argument nodes."""
    source_id: str
    target_id: str
    relation: RelationType
    confidence: float = 0.5


@dataclass
class ArgumentGraph:
    """Directed graph of arguments extracted from a wiki page."""
    page_slug: str
    page_title: str
    nodes: list[ArgumentNode] = field(default_factory=list)
    edges: list[ArgumentEdge] = field(default_factory=list)

    def add_node(self, node: ArgumentNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: ArgumentEdge) -> None:
        self.edges.append(edge)

    def to_dict(self) -> dict:
        return {
            "page_slug": self.page_slug,
            "page_title": self.page_title,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [
                {**asdict(e), "relation": e.relation.value}
                for e in self.edges
            ],
        }


# ── Parsing (reuse from contradiction detector) ─────────────────

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
                current_list.append(stripped[2:].strip().strip('"').strip("'"))
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
                result[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                current_list = None
            else:
                result[key] = val
                current_list = None
    if current_key and current_list is not None:
        result[current_key] = current_list
    return result


def _extract_sections(content: str) -> dict[str, list[str]]:
    """Extract all sections and their bullet points."""
    sections: dict[str, list[str]] = {}
    current_section = ""
    for line in content.split("\n"):
        if line.startswith("## "):
            current_section = line.strip()[3:].strip()
            sections[current_section] = []
            continue
        if current_section:
            stripped = line.strip()
            if stripped.startswith("- ") and not stripped.startswith("- _"):
                text = stripped[2:].strip()
                # Strip citations
                text = re.sub(r"\[Source:.*?\]", "", text).strip()
                if len(text) > 5:
                    sections[current_section].append(text)
    return sections


# ── Heuristic argument structure detection ───────────────────────

# Signal words for different argument roles
CONCLUSION_SIGNALS = {
    "therefore", "thus", "hence", "consequently", "so", "implies",
    "suggests", "demonstrates", "shows", "proves", "concludes",
    "overall", "in conclusion", "as a result", "it follows",
}

PREMISE_SIGNALS = {
    "because", "since", "given", "assuming", "if", "based on",
    "evidence", "data shows", "research indicates", "studies show",
    "according to", "empirically",
}

REBUTTAL_SIGNALS = {
    "however", "but", "although", "despite", "nevertheless",
    "contrary", "conversely", "on the other hand", "yet",
    "challenges", "contradicts", "undermines", "weakens",
    "limitation", "critique", "problem",
}

QUALIFIER_SIGNALS = {
    "unless", "except", "only if", "provided that", "in some cases",
    "sometimes", "partially", "to some extent", "with caveats",
    "under certain conditions", "when", "in the context of",
}


def _classify_claim_role(text: str) -> str:
    """Classify a claim as premise, conclusion, qualifier, or claim (generic)."""
    lower = text.lower()

    # Check for conclusion signals
    for sig in CONCLUSION_SIGNALS:
        if sig in lower:
            return "conclusion"

    # Check for qualifier signals
    for sig in QUALIFIER_SIGNALS:
        if sig in lower:
            return "qualifier"

    # Check for premise signals
    for sig in PREMISE_SIGNALS:
        if sig in lower:
            return "premise"

    return "claim"


def _detect_relation(source_text: str, target_text: str) -> tuple[RelationType, float]:
    """Detect the relation between two claims using heuristic signals.

    Returns (relation_type, confidence).
    """
    target_lower = target_text.lower()
    source_lower = source_text.lower()

    # Check for rebuttal signals in target
    for sig in REBUTTAL_SIGNALS:
        if sig in target_lower:
            return RelationType.REBUTS, 0.6

    # Check for qualifier signals
    for sig in QUALIFIER_SIGNALS:
        if sig in target_lower:
            return RelationType.QUALIFIES, 0.5

    # Default: claims in the same argument structure support each other
    # unless they have rebuttal signals
    return RelationType.SUPPORTS, 0.4


def _compute_embedding_similarity(texts: list[str]) -> list[list[float]]:
    """Compute pairwise similarity matrix for texts."""
    if len(texts) < 2:
        return [[1.0]]

    try:
        from clarvis.brain.factory import get_embedding_function
        ef = get_embedding_function(use_onnx=True)
        embeddings = ef(texts)
    except ImportError:
        # Return identity matrix if no embeddings available
        n = len(texts)
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    n = len(embeddings)
    sim_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                sim_matrix[i][j] = 1.0
            else:
                dot = sum(a * b for a, b in zip(embeddings[i], embeddings[j]))
                na = math.sqrt(sum(a * a for a in embeddings[i]))
                nb = math.sqrt(sum(b * b for b in embeddings[j]))
                sim_matrix[i][j] = dot / (na * nb) if na > 0 and nb > 0 else 0.0
    return sim_matrix


# ── Core mapper ──────────────────────────────────────────────────

def extract_argument_graph(
    page_slug: str,
    page_title: str,
    content: str,
    use_embeddings: bool = True,
    min_similarity: float = 0.3,
) -> ArgumentGraph:
    """Extract argument structure from a wiki page.

    Strategy:
    1. Extract claims from Key Claims section
    2. Extract supporting evidence from Evidence section
    3. Extract limitations/rebuttals from Limitations section
    4. Classify each claim's role (premise/conclusion/qualifier)
    5. Connect claims using:
       a. Heuristic signal words
       b. Embedding similarity (semantically related claims are likely connected)
    6. Add rebuttal edges from limitations
    """
    graph = ArgumentGraph(page_slug=page_slug, page_title=page_title)
    sections = _extract_sections(content)

    claims = sections.get("Key Claims", [])
    evidence = sections.get("Evidence", [])
    limitations = sections.get("Limitations", [])
    results = sections.get("Results", [])

    if not claims and not evidence and not results:
        return graph

    # Create nodes
    node_texts = []

    for i, claim in enumerate(claims):
        node_id = f"claim_{i}"
        role = _classify_claim_role(claim)
        graph.add_node(ArgumentNode(id=node_id, text=claim, role=role, page_slug=page_slug))
        node_texts.append(claim)

    for i, ev in enumerate(evidence):
        node_id = f"evidence_{i}"
        graph.add_node(ArgumentNode(id=node_id, text=ev, role="premise", page_slug=page_slug))
        node_texts.append(ev)

    for i, lim in enumerate(limitations):
        node_id = f"limitation_{i}"
        graph.add_node(ArgumentNode(id=node_id, text=lim, role="qualifier", page_slug=page_slug))
        node_texts.append(lim)

    for i, res in enumerate(results):
        node_id = f"result_{i}"
        role = _classify_claim_role(res)
        graph.add_node(ArgumentNode(id=node_id, text=res, role=role if role != "claim" else "conclusion", page_slug=page_slug))
        node_texts.append(res)

    if len(graph.nodes) < 2:
        return graph

    # Connect nodes: evidence → claims (supports)
    for ev_node in graph.nodes:
        if ev_node.id.startswith("evidence_"):
            for claim_node in graph.nodes:
                if claim_node.id.startswith("claim_"):
                    graph.add_edge(ArgumentEdge(
                        source_id=ev_node.id,
                        target_id=claim_node.id,
                        relation=RelationType.SUPPORTS,
                        confidence=0.3,
                    ))

    # Connect nodes: limitations → claims (rebuts)
    for lim_node in graph.nodes:
        if lim_node.id.startswith("limitation_"):
            for claim_node in graph.nodes:
                if claim_node.id.startswith("claim_"):
                    graph.add_edge(ArgumentEdge(
                        source_id=lim_node.id,
                        target_id=claim_node.id,
                        relation=RelationType.REBUTS,
                        confidence=0.4,
                    ))

    # Connect claims to each other using heuristic signals
    claim_nodes = [n for n in graph.nodes if n.id.startswith("claim_")]
    for i, node_a in enumerate(claim_nodes):
        for j, node_b in enumerate(claim_nodes):
            if i >= j:
                continue
            rel, conf = _detect_relation(node_a.text, node_b.text)
            if rel == RelationType.REBUTS or rel == RelationType.QUALIFIES:
                graph.add_edge(ArgumentEdge(
                    source_id=node_a.id, target_id=node_b.id,
                    relation=rel, confidence=conf,
                ))

    # Use embedding similarity to identify connected claims
    if use_embeddings and len(node_texts) >= 2:
        sim_matrix = _compute_embedding_similarity(node_texts)
        for i in range(len(graph.nodes)):
            for j in range(i + 1, len(graph.nodes)):
                if sim_matrix[i][j] >= min_similarity:
                    # Check if edge already exists
                    existing = any(
                        (e.source_id == graph.nodes[i].id and e.target_id == graph.nodes[j].id) or
                        (e.source_id == graph.nodes[j].id and e.target_id == graph.nodes[i].id)
                        for e in graph.edges
                    )
                    if not existing:
                        # Determine direction: premises support conclusions
                        src, tgt = graph.nodes[i], graph.nodes[j]
                        if src.role == "conclusion" and tgt.role != "conclusion":
                            src, tgt = tgt, src
                        rel, conf = _detect_relation(src.text, tgt.text)
                        conf = max(conf, sim_matrix[i][j] * 0.5)
                        graph.add_edge(ArgumentEdge(
                            source_id=src.id, target_id=tgt.id,
                            relation=rel, confidence=round(conf, 3),
                        ))

    # Identify conclusions: nodes with only incoming edges (or claims with conclusion signals)
    outgoing = {e.source_id for e in graph.edges}
    incoming = {e.target_id for e in graph.edges}
    for node in graph.nodes:
        if node.id in incoming and node.id not in outgoing:
            if node.role == "claim":
                node.role = "conclusion"

    return graph


# ── ASCII visualization ──────────────────────────────────────────

def render_ascii(graph: ArgumentGraph) -> str:
    """Render argument graph as ASCII art."""
    if not graph.nodes:
        return f"[{graph.page_title}] — No argument structure extracted."

    lines = [
        f"Argument Map: {graph.page_title}",
        f"{'=' * (15 + len(graph.page_title))}",
        "",
    ]

    # Group nodes by role
    roles = {"premise": [], "evidence": [], "claim": [], "qualifier": [], "conclusion": []}
    for node in graph.nodes:
        bucket = node.role if node.role in roles else "claim"
        roles[bucket].append(node)

    # Build adjacency for display
    outgoing: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.edges:
        outgoing.setdefault(edge.source_id, []).append(
            (edge.target_id, edge.relation.value)
        )

    node_by_id = {n.id: n for n in graph.nodes}

    # Render premises/evidence first
    for role_name in ["premise", "evidence"]:
        if not roles.get(role_name):
            continue
        lines.append(f"  [{role_name.upper()}S]")
        for node in roles[role_name]:
            lines.append(f"    ({node.id}) {node.short(70)}")
            if node.id in outgoing:
                for target_id, rel in outgoing[node.id]:
                    target = node_by_id.get(target_id)
                    if target:
                        arrow = "──>" if rel == "supports" else "──X" if rel == "rebuts" else "──?"
                        lines.append(f"      {arrow} ({target_id}) {target.short(50)}")
        lines.append("")

    # Render claims
    if roles.get("claim"):
        lines.append("  [CLAIMS]")
        for node in roles["claim"]:
            lines.append(f"    ({node.id}) {node.short(70)}")
            if node.id in outgoing:
                for target_id, rel in outgoing[node.id]:
                    target = node_by_id.get(target_id)
                    if target:
                        arrow = "──>" if rel == "supports" else "──X" if rel == "rebuts" else "──~"
                        lines.append(f"      {arrow} ({target_id}) {target.short(50)}")
        lines.append("")

    # Render qualifiers
    if roles.get("qualifier"):
        lines.append("  [QUALIFIERS]")
        for node in roles["qualifier"]:
            lines.append(f"    ({node.id}) {node.short(70)}")
            if node.id in outgoing:
                for target_id, rel in outgoing[node.id]:
                    target = node_by_id.get(target_id)
                    if target:
                        lines.append(f"      ──~ ({target_id}) {target.short(50)}")
        lines.append("")

    # Render conclusions
    if roles.get("conclusion"):
        lines.append("  [CONCLUSIONS]")
        for node in roles["conclusion"]:
            lines.append(f"    ==> ({node.id}) {node.short(70)}")
        lines.append("")

    # Summary
    lines.extend([
        "---",
        f"Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}",
        f"  supports: {sum(1 for e in graph.edges if e.relation == RelationType.SUPPORTS)}",
        f"  rebuts:   {sum(1 for e in graph.edges if e.relation == RelationType.REBUTS)}",
        f"  qualifies:{sum(1 for e in graph.edges if e.relation == RelationType.QUALIFIES)}",
    ])

    return "\n".join(lines)


# ── Page loading ─────────────────────────────────────────────────

def load_page(slug: str) -> tuple[str, str, str] | None:
    """Load a wiki page by slug. Returns (slug, title, content) or None."""
    for md_file in WIKI_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        if fm and fm.get("slug") == slug:
            return slug, fm.get("title", slug), text
        if md_file.stem == slug:
            title = fm.get("title", slug) if fm else slug
            return slug, title, text
    return None


def load_all_pages() -> list[tuple[str, str, str]]:
    """Load all wiki pages. Returns list of (slug, title, content)."""
    pages = []
    for md_file in sorted(WIKI_DIR.rglob("*.md")):
        if md_file.name == "index.md":
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        if fm is None:
            continue
        slug = fm.get("slug", md_file.stem)
        title = fm.get("title", slug)
        pages.append((slug, title, text))
    return pages


# ── CLI ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wiki argument mapper")
    sub = parser.add_subparsers(dest="command", required=True)

    map_p = sub.add_parser("map", help="Extract argument structure from a wiki page")
    map_p.add_argument("slug", help="Wiki page slug")
    map_p.add_argument("--json", action="store_true", dest="json_output")
    map_p.add_argument("--no-embeddings", action="store_true",
                       help="Skip embedding-based relation detection")

    ascii_p = sub.add_parser("ascii", help="Show ASCII argument map for a page")
    ascii_p.add_argument("slug", help="Wiki page slug")

    all_p = sub.add_parser("map-all", help="Map all wiki pages with sufficient claims")
    all_p.add_argument("--min-claims", type=int, default=2, help="Minimum claims (default: 2)")
    all_p.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()

    if args.command == "map":
        result = load_page(args.slug)
        if not result:
            print(f"Page not found: {args.slug}", file=sys.stderr)
            sys.exit(1)
        slug, title, content = result
        graph = extract_argument_graph(
            slug, title, content,
            use_embeddings=not args.no_embeddings,
        )
        if args.json_output:
            print(json.dumps(graph.to_dict(), indent=2))
        else:
            print(render_ascii(graph))

    elif args.command == "ascii":
        result = load_page(args.slug)
        if not result:
            print(f"Page not found: {args.slug}", file=sys.stderr)
            sys.exit(1)
        slug, title, content = result
        graph = extract_argument_graph(slug, title, content)
        print(render_ascii(graph))

    elif args.command == "map-all":
        pages = load_all_pages()
        results = []
        for slug, title, content in pages:
            graph = extract_argument_graph(
                slug, title, content,
                use_embeddings=False,  # Skip embeddings for speed in batch
            )
            if len(graph.nodes) >= args.min_claims:
                results.append(graph)
                if not args.json_output:
                    print(render_ascii(graph))
                    print()

        if args.json_output:
            print(json.dumps([g.to_dict() for g in results], indent=2))
        else:
            print(f"\n{'='*40}")
            print(f"Pages with argument structure: {len(results)}/{len(pages)}")


if __name__ == "__main__":
    main()

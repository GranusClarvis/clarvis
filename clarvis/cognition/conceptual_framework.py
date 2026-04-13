"""Conceptual Framework — Semantic clustering and concept graph for Clarvis brain.

Goes beyond keyword matching by:
  1. Clustering brain memories using ONNX embedding similarity
  2. Extracting concept labels from clusters (TF-IDF-like)
  3. Building inter-concept relationships (co-occurrence + embedding proximity)
  4. Providing concept-aware retrieval: find memories via concept, not just keywords

Complements the existing keyword-bridge synthesis in knowledge_synthesis.py
by adding structured concept representations as first-class objects.

Data:
  data/conceptual_framework/concepts.json      — concept registry
  data/conceptual_framework/concept_graph.json  — inter-concept edges
  data/conceptual_framework/cluster_log.jsonl   — clustering history

Usage:
    from clarvis.cognition.conceptual_framework import (
        build_concepts, get_concepts, find_concept, concept_search,
        concept_neighbors, stats,
    )
    build_concepts()                  # Full rebuild from brain memories
    find_concept("retrieval")         # Find concept by name or query
    concept_search("adaptive RAG")    # Concept-aware brain search
    concept_neighbors("retrieval")    # Related concepts
    stats()                           # Framework health
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
DATA_DIR = BASE / "data" / "conceptual_framework"
CONCEPTS_FILE = DATA_DIR / "concepts.json"
GRAPH_FILE = DATA_DIR / "concept_graph.json"
HISTORY_FILE = DATA_DIR / "cluster_log.jsonl"

# Clustering
MIN_CLUSTER_SIZE = 3       # Minimum memories to form a concept
MAX_CONCEPTS = 60          # Cap on total concepts
SIMILARITY_THRESHOLD = 0.6 # Cosine similarity for same-cluster membership
EDGE_THRESHOLD = 0.35      # Min similarity for inter-concept edge

# Stopwords for label extraction (beyond the basics)
_LABEL_STOPS = {
    "the", "and", "for", "from", "with", "that", "this", "was", "were",
    "been", "being", "have", "has", "had", "not", "but", "are", "can",
    "will", "would", "could", "should", "may", "might", "into", "also",
    "about", "more", "when", "than", "then", "very", "just", "only",
    "some", "other", "each", "which", "their", "does", "through",
    "using", "used", "based", "added", "created", "stored", "updated",
    "working", "across", "within", "between", "after", "before", "during",
    "first", "already", "need", "make", "like", "well", "much", "many",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Concept:
    """A semantic concept extracted from brain memory clusters."""
    id: str                           # slug: "adaptive_retrieval"
    label: str                        # human-readable: "Adaptive Retrieval"
    keywords: List[str]               # top discriminative terms
    collections: List[str]            # which brain collections contribute
    memory_count: int = 0             # memories in this cluster
    centroid_text: str = ""           # representative memory text
    cross_domain: bool = False        # spans 2+ collections
    created: str = ""
    updated: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ConceptEdge:
    """Relationship between two concepts."""
    source: str       # concept id
    target: str       # concept id
    weight: float     # 0.0-1.0 similarity
    relation: str     # "similar" | "co-occurs" | "subsumes"

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _get_embedder():
    """Get the ONNX MiniLM embedder used by ClarvisDB."""
    try:
        from clarvis.brain import brain
        if hasattr(brain, '_ef') and brain._ef is not None:
            return brain._ef
        # Try to get it from the underlying ChromaDB
        if hasattr(brain, '_brain') and hasattr(brain._brain, '_ef'):
            return brain._brain._ef
    except Exception:
        pass

    # Fallback: create our own
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        return ONNXMiniLM_L6_V2()
    except ImportError:
        return None


def _cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mean_vector(vectors):
    """Compute mean of a list of vectors."""
    if not vectors:
        return []
    n = len(vectors)
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / n for i in range(dim)]


# ---------------------------------------------------------------------------
# Core: clustering & concept extraction
# ---------------------------------------------------------------------------

def _extract_terms(text: str) -> List[str]:
    """Extract meaningful terms from text."""
    words = re.findall(r'[a-z][a-z_]{2,}', text.lower())
    return [w for w in words if w not in _LABEL_STOPS and len(w) > 3]


def _tfidf_keywords(cluster_docs: List[str], all_docs: List[str], top_k: int = 5) -> List[str]:
    """Extract top-k discriminative keywords for a cluster using TF-IDF-like scoring."""
    # Term frequency in cluster
    cluster_terms = Counter()
    for doc in cluster_docs:
        terms = _extract_terms(doc)
        cluster_terms.update(set(terms))  # Binary TF per document

    # Document frequency across all docs
    doc_freq = Counter()
    for doc in all_docs:
        terms = _extract_terms(doc)
        doc_freq.update(set(terms))

    n_docs = len(all_docs)
    n_cluster = len(cluster_docs)

    # TF-IDF: (cluster_freq / cluster_size) * log(total_docs / doc_freq)
    scores = {}
    for term, cf in cluster_terms.items():
        df = doc_freq.get(term, 1)
        tf = cf / n_cluster
        idf = math.log((n_docs + 1) / (df + 1))
        scores[term] = tf * idf

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [term for term, _ in ranked[:top_k]]


def _greedy_cluster(embeddings, texts, threshold=SIMILARITY_THRESHOLD):
    """Greedy clustering by cosine similarity to centroids.

    Simple and fast — avoids scipy/sklearn dependency.
    Assigns each memory to the most similar existing centroid,
    or creates a new cluster if similarity is below threshold.
    """
    clusters = []  # list of (centroid_vector, member_indices)

    for i, emb in enumerate(embeddings):
        best_sim = -1.0
        best_idx = -1
        for j, (centroid, _) in enumerate(clusters):
            sim = _cosine_sim(emb, centroid)
            if sim > best_sim:
                best_sim = sim
                best_idx = j

        if best_sim >= threshold and best_idx >= 0:
            # Add to existing cluster, update centroid (running mean)
            centroid, members = clusters[best_idx]
            members.append(i)
            new_centroid = _mean_vector([embeddings[m] for m in members])
            clusters[best_idx] = (new_centroid, members)
        else:
            # New cluster
            clusters.append((list(emb), [i]))

    return clusters


def _make_concept_id(keywords: List[str]) -> str:
    """Generate a slug ID from keywords."""
    if not keywords:
        return "unknown"
    slug = "_".join(keywords[:3])
    return re.sub(r'[^a-z0-9_]', '', slug)


def build_concepts(max_per_collection: int = 200) -> Dict:
    """Build concept framework from brain memories.

    Loads memories from all collections, embeds them, clusters by
    semantic similarity, and extracts concept labels.

    Returns:
        Dict with concepts, edges, and build stats.
    """
    try:
        from clarvis.brain import brain, ALL_COLLECTIONS
    except ImportError:
        return {"error": "Brain not available"}

    embedder = _get_embedder()
    if embedder is None:
        return {"error": "No embedder available"}

    t0 = time.monotonic()

    # Load all memories
    all_docs = []
    all_meta = []
    for col in ALL_COLLECTIONS:
        try:
            memories = brain.get(col, n=max_per_collection)
        except Exception:
            continue
        for mem in memories:
            doc = mem.get("document", "")
            if not doc or len(doc) < 20:
                continue
            all_docs.append(doc)
            all_meta.append({
                "collection": col,
                "id": mem.get("id", ""),
                "importance": mem.get("metadata", {}).get("importance", 0.5)
                              if isinstance(mem.get("metadata"), dict) else 0.5,
            })

    if len(all_docs) < MIN_CLUSTER_SIZE:
        return {"error": f"Too few memories ({len(all_docs)})"}

    # Embed all documents
    try:
        embeddings = embedder(all_docs)
    except Exception as e:
        return {"error": f"Embedding failed: {e}"}

    # Cluster
    clusters = _greedy_cluster(embeddings, all_docs, SIMILARITY_THRESHOLD)

    # Filter small clusters
    valid_clusters = [(c, m) for c, m in clusters if len(m) >= MIN_CLUSTER_SIZE]

    # Sort by size (largest first), cap at MAX_CONCEPTS
    valid_clusters.sort(key=lambda x: len(x[1]), reverse=True)
    valid_clusters = valid_clusters[:MAX_CONCEPTS]

    # Extract concepts
    concepts = []
    concept_centroids = []
    all_doc_texts = all_docs  # for IDF computation

    for centroid, members in valid_clusters:
        member_docs = [all_docs[i] for i in members]
        member_meta = [all_meta[i] for i in members]

        # Keywords via TF-IDF
        keywords = _tfidf_keywords(member_docs, all_doc_texts)

        # Collections present
        collections = list(set(m["collection"] for m in member_meta))
        cross_domain = len(collections) >= 2

        # Representative text (highest importance or closest to centroid)
        best_idx = 0
        best_sim = -1
        for j, mi in enumerate(members):
            sim = _cosine_sim(embeddings[mi], centroid)
            if sim > best_sim:
                best_sim = sim
                best_idx = j
        centroid_text = member_docs[best_idx][:200]

        concept_id = _make_concept_id(keywords)
        # Deduplicate IDs
        existing_ids = {c.id for c in concepts}
        if concept_id in existing_ids:
            concept_id = f"{concept_id}_{len(concepts)}"

        label = " ".join(w.capitalize() for w in keywords[:3])

        concept = Concept(
            id=concept_id,
            label=label,
            keywords=keywords,
            collections=collections,
            memory_count=len(members),
            centroid_text=centroid_text,
            cross_domain=cross_domain,
            created=datetime.now(timezone.utc).isoformat(),
            updated=datetime.now(timezone.utc).isoformat(),
        )
        concepts.append(concept)
        concept_centroids.append(centroid)

    # Build inter-concept edges
    edges = []
    for i, ci in enumerate(concepts):
        for j in range(i + 1, len(concepts)):
            cj = concepts[j]
            sim = _cosine_sim(concept_centroids[i], concept_centroids[j])
            if sim >= EDGE_THRESHOLD:
                # Determine relation type
                keyword_overlap = set(ci.keywords) & set(cj.keywords)
                if keyword_overlap:
                    relation = "co-occurs"
                elif ci.memory_count > 3 * cj.memory_count:
                    relation = "subsumes"
                elif cj.memory_count > 3 * ci.memory_count:
                    relation = "subsumes"
                else:
                    relation = "similar"

                edge = ConceptEdge(
                    source=ci.id,
                    target=cj.id,
                    weight=round(sim, 4),
                    relation=relation,
                )
                edges.append(edge)

    elapsed = round(time.monotonic() - t0, 2)

    # Save
    result = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total_memories": len(all_docs),
        "total_clusters": len(clusters),
        "valid_concepts": len(concepts),
        "cross_domain_concepts": sum(1 for c in concepts if c.cross_domain),
        "edges": len(edges),
        "elapsed_s": elapsed,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    concepts_data = {
        "version": 1,
        "built_at": result["built_at"],
        "concepts": [c.to_dict() for c in concepts],
    }
    _atomic_write(CONCEPTS_FILE, concepts_data)

    graph_data = {
        "version": 1,
        "built_at": result["built_at"],
        "edges": [e.to_dict() for e in edges],
    }
    _atomic_write(GRAPH_FILE, graph_data)

    # Append to history
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------

def get_concepts() -> List[Dict]:
    """Load all concepts from disk."""
    if not CONCEPTS_FILE.exists():
        return []
    try:
        data = json.loads(CONCEPTS_FILE.read_text())
        return data.get("concepts", [])
    except (json.JSONDecodeError, IOError):
        return []


def find_concept(query: str) -> Optional[Dict]:
    """Find a concept by name, keyword, or query text.

    Tries exact ID match, then keyword match, then substring match.
    """
    concepts = get_concepts()
    if not concepts:
        return None

    q = query.lower().strip()

    # Exact ID match
    for c in concepts:
        if c["id"] == q:
            return c

    # Keyword match
    for c in concepts:
        if q in c.get("keywords", []):
            return c

    # Substring match in label or keywords
    for c in concepts:
        if q in c.get("label", "").lower():
            return c
        if any(q in kw for kw in c.get("keywords", [])):
            return c

    return None


def concept_search(query: str, n: int = 5) -> List[Dict]:
    """Concept-aware brain search.

    Finds the most relevant concept for the query, then searches
    the brain within that concept's collections with boosted keywords.

    Falls back to regular search if no concept matches.
    """
    concept = find_concept(query)

    try:
        from clarvis.brain import brain
    except ImportError:
        return []

    if concept:
        # Build enhanced query with concept keywords
        keywords = concept.get("keywords", [])
        enhanced_query = f"{query} {' '.join(keywords)}"
        collections = concept.get("collections", None)

        results = brain.recall(
            enhanced_query,
            collections=collections if collections else None,
            n=n,
            caller="concept_search",
        )
        # Tag results with concept info
        for r in results:
            r["_concept"] = concept["id"]
            r["_concept_label"] = concept["label"]
        return results
    else:
        # Fallback: regular search
        return brain.recall(query, n=n, caller="concept_search")


def concept_neighbors(concept_id: str) -> List[Dict]:
    """Find concepts related to the given concept via the concept graph."""
    if not GRAPH_FILE.exists():
        return []

    try:
        data = json.loads(GRAPH_FILE.read_text())
        edges = data.get("edges", [])
    except (json.JSONDecodeError, IOError):
        return []

    neighbors = []
    for edge in edges:
        if edge["source"] == concept_id:
            neighbors.append({"concept": edge["target"], "weight": edge["weight"], "relation": edge["relation"]})
        elif edge["target"] == concept_id:
            neighbors.append({"concept": edge["source"], "weight": edge["weight"], "relation": edge["relation"]})

    neighbors.sort(key=lambda x: x["weight"], reverse=True)
    return neighbors


def get_relevant_frameworks(task: str, max_frameworks: int = 3) -> str:
    """Find concepts relevant to a task and format as context for reasoning.

    Returns a compact text block listing relevant concepts, their keywords,
    and cross-domain connections — suitable for inclusion in a context brief.
    Returns empty string if no concepts are available or relevant.
    """
    concepts = get_concepts()
    if not concepts:
        return ""

    task_lower = task.lower()
    task_terms = set(_extract_terms(task_lower))

    # Score each concept by keyword overlap with task
    scored = []
    for c in concepts:
        kws = set(c.get("keywords", []))
        overlap = len(task_terms & kws)
        # Also check substring match of concept label in task
        label_match = 1 if c.get("label", "").lower() in task_lower else 0
        # Cross-domain concepts get a small bonus (they bridge knowledge)
        cross_bonus = 0.5 if c.get("cross_domain") else 0
        score = overlap + label_match + cross_bonus
        if score > 0:
            scored.append((score, c))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_frameworks]

    lines = []
    for score, c in top:
        kws = ", ".join(c.get("keywords", [])[:5])
        cols = ", ".join(c.get("collections", []))
        label = c.get("label", c.get("id", "?"))
        line = f"  [{label}] keywords={kws}"
        if c.get("cross_domain"):
            line += f" (cross-domain: {cols})"
        lines.append(line)

    # Add neighbor info for top concept
    top_id = top[0][1].get("id", "")
    neighbors = concept_neighbors(top_id)
    if neighbors:
        neighbor_names = [n["concept"] for n in neighbors[:3]]
        lines.append(f"  Related concepts: {', '.join(neighbor_names)}")

    return "\n".join(lines)


def stats() -> Dict:
    """Return framework health stats."""
    concepts = get_concepts()
    edges = []
    if GRAPH_FILE.exists():
        try:
            data = json.loads(GRAPH_FILE.read_text())
            edges = data.get("edges", [])
        except Exception:
            pass

    built_at = None
    if CONCEPTS_FILE.exists():
        try:
            data = json.loads(CONCEPTS_FILE.read_text())
            built_at = data.get("built_at")
        except Exception:
            pass

    cross_domain = sum(1 for c in concepts if c.get("cross_domain"))
    total_memories = sum(c.get("memory_count", 0) for c in concepts)
    avg_size = total_memories / len(concepts) if concepts else 0

    return {
        "total_concepts": len(concepts),
        "cross_domain_concepts": cross_domain,
        "total_edges": len(edges),
        "total_clustered_memories": total_memories,
        "avg_cluster_size": round(avg_size, 1),
        "built_at": built_at,
        "status": "ready" if concepts else "empty",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FloatEncoder(json.JSONEncoder):
    """Handle numpy float32/float64 in JSON output."""
    def default(self, obj):
        try:
            return float(obj)
        except (TypeError, ValueError):
            return super().default(obj)


def _atomic_write(path: Path, data: dict):
    """Write JSON atomically via tmp+rename."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, cls=_FloatEncoder)
    tmp.rename(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m clarvis.cognition.conceptual_framework build|stats|find <query>|search <query>|neighbors <id>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "build":
        result = build_concepts()
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        s = stats()
        print(json.dumps(s, indent=2))

    elif cmd == "find" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        c = find_concept(query)
        if c:
            print(json.dumps(c, indent=2))
        else:
            print(f"No concept found for: {query}")

    elif cmd == "search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        results = concept_search(query)
        for r in results:
            doc = r.get("document", "")[:100]
            concept = r.get("_concept", "none")
            print(f"  [{concept}] {doc}")

    elif cmd == "neighbors" and len(sys.argv) >= 3:
        cid = sys.argv[2]
        neighbors = concept_neighbors(cid)
        for n in neighbors:
            print(f"  {n['concept']} ({n['relation']}, weight={n['weight']:.3f})")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

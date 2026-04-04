#!/usr/bin/env python3
"""
GraphRAG Community Detection & Global Search for ClarvisDB.

Implements the core ideas from Microsoft's GraphRAG paper (arXiv 2404.16130):
  1. Hierarchical Leiden community detection over the 122k+ edge memory graph
  2. Community summary generation (LLM-free: extractive keyword/theme summaries)
  3. Global search: map-reduce over community summaries for holistic queries
  4. Local search enhancement: community context alongside vector results

The Leiden algorithm partitions the graph into communities at multiple resolution
levels. Each community gets an extractive summary derived from its member memories.
Global search scores these summaries against a query and returns the most relevant
community context — enabling questions like "What are the main themes I've learned?"
that pure vector search cannot answer well.

Usage:
    python3 graphrag_communities.py detect          # Run community detection
    python3 graphrag_communities.py summarize       # Generate community summaries
    python3 graphrag_communities.py build           # detect + summarize (full pipeline)
    python3 graphrag_communities.py global "query"  # Global search
    python3 graphrag_communities.py local "query"   # Enhanced local search
    python3 graphrag_communities.py stats           # Show community statistics
    python3 graphrag_communities.py info <id>       # Show community details

Dependencies: python-igraph, leidenalg (pip install python-igraph leidenalg)
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
DATA_DIR = Path(_WS) / "data" / "clarvisdb"
COMMUNITIES_FILE = DATA_DIR / "communities.json"
SUMMARIES_FILE = DATA_DIR / "community_summaries.json"

# Leiden resolution parameters for each hierarchy level
# Higher resolution = more, smaller communities
RESOLUTIONS = [0.5, 1.0, 2.0, 4.0]
LEVEL_NAMES = ["C0", "C1", "C2", "C3"]

# Summary generation parameters
MAX_KEYWORDS_PER_COMMUNITY = 12
MAX_REPRESENTATIVE_TEXTS = 5
MIN_COMMUNITY_SIZE = 2  # Skip singleton communities


def _load_graph():
    """Load the ClarvisDB relationship graph.

    Uses SQLite export when CLARVIS_GRAPH_BACKEND=sqlite and graph.db exists,
    otherwise falls back to reading relationships.json directly.
    """
    backend = os.environ.get("CLARVIS_GRAPH_BACKEND", "json")
    sqlite_path = DATA_DIR / "graph.db"
    if backend == "sqlite" and sqlite_path.exists():
        from clarvis.brain.graph_store_sqlite import GraphStoreSQLite
        store = GraphStoreSQLite(str(sqlite_path))
        # Build in-memory dict matching JSON schema
        nodes = {}
        for row in store._conn.execute("SELECT id, collection, added_at, backfilled FROM nodes").fetchall():
            nodes[row[0]] = {"collection": row[1], "added_at": row[2]}
            if row[3]:
                nodes[row[0]]["backfilled"] = True
        edges = []
        for row in store._conn.execute(
            "SELECT from_id, to_id, type, created_at, source_collection, target_collection, weight FROM edges"
        ).fetchall():
            edge = {"from": row[0], "to": row[1], "type": row[2], "created_at": row[3]}
            if row[4]:
                edge["source_collection"] = row[4]
            if row[5]:
                edge["target_collection"] = row[5]
            if row[6] is not None and row[6] != 1.0:
                edge["weight"] = row[6]
            edges.append(edge)
        store.close()
        return {"nodes": nodes, "edges": edges}

    graph_file = DATA_DIR / "relationships.json"
    with open(graph_file, 'r') as f:
        return json.load(f)


def _build_igraph(graph_data):
    """Convert ClarvisDB graph to igraph format for Leiden algorithm.

    Returns (ig.Graph, node_id_list) where node_id_list[i] is the ClarvisDB
    memory ID for igraph vertex i.
    """
    import igraph as ig

    edges_raw = graph_data.get("edges", [])
    nodes_dict = graph_data.get("nodes", {})

    # Collect all unique node IDs
    node_ids = set(nodes_dict.keys())
    for e in edges_raw:
        node_ids.add(e["from"])
        node_ids.add(e["to"])

    node_list = sorted(node_ids)
    node_index = {nid: i for i, nid in enumerate(node_list)}

    # Build edges with weights
    edges = []
    weights = []
    seen = set()
    for e in edges_raw:
        f_idx = node_index[e["from"]]
        t_idx = node_index[e["to"]]
        if f_idx == t_idx:
            continue  # skip self-loops
        pair = (min(f_idx, t_idx), max(f_idx, t_idx))
        if pair in seen:
            continue  # deduplicate for undirected graph
        seen.add(pair)
        edges.append(pair)
        # Use edge weight if available, otherwise weight by type
        w = e.get("weight", None)
        if w is None:
            etype = e.get("type", "unknown")
            w = {
                "hebbian_association": 0.6,
                "cross_collection": 0.8,
                "similar_to": 0.5,
                "concept_link": 0.9,
                "semantic_bridge": 0.85,
                "synthesized_with": 0.7,
                "boosted_bridge": 0.75,
                "bridged_similarity": 0.5,
            }.get(etype, 0.4)
        weights.append(float(w))

    G = ig.Graph(n=len(node_list), edges=edges, directed=False)
    G.es["weight"] = weights

    # Store collection info as vertex attribute
    collections = []
    for nid in node_list:
        node_info = nodes_dict.get(nid, {})
        collections.append(node_info.get("collection", "unknown"))
    G.vs["collection"] = collections
    G.vs["memory_id"] = node_list

    return G, node_list


def detect_communities(graph_data=None, save=True):
    """Run hierarchical Leiden community detection.

    Returns community assignments dict:
    {
        "levels": {"C0": {comm_id: [node_ids]}, ...},
        "node_community": {node_id: {"C0": id, "C1": id, ...}},
        "metadata": {...}
    }
    """
    import leidenalg

    if graph_data is None:
        graph_data = _load_graph()

    t0 = time.time()
    G, node_list = _build_igraph(graph_data)
    print(f"  Built igraph: {G.vcount()} vertices, {G.ecount()} edges ({time.time()-t0:.1f}s)")

    communities = {
        "levels": {},
        "node_community": defaultdict(dict),
        "metadata": {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_nodes": G.vcount(),
            "total_edges": G.ecount(),
        }
    }

    level_stats = []

    for level_idx, (resolution, level_name) in enumerate(zip(RESOLUTIONS, LEVEL_NAMES)):
        t1 = time.time()
        partition = leidenalg.find_partition(
            G,
            leidenalg.RBConfigurationVertexPartition,
            weights=G.es["weight"],
            resolution_parameter=resolution,
            seed=42,
        )

        # Map partition to ClarvisDB node IDs
        comm_members = defaultdict(list)
        for vertex_idx, comm_id in enumerate(partition.membership):
            nid = node_list[vertex_idx]
            comm_key = f"{level_name}_{comm_id}"
            comm_members[comm_key].append(nid)
            communities["node_community"][nid][level_name] = comm_key

        # Filter out singletons
        comm_members = {k: v for k, v in comm_members.items() if len(v) >= MIN_COMMUNITY_SIZE}
        communities["levels"][level_name] = comm_members

        n_comms = len(comm_members)
        sizes = [len(v) for v in comm_members.values()]
        avg_size = sum(sizes) / n_comms if n_comms else 0
        max_size = max(sizes) if sizes else 0
        modularity = partition.modularity

        stat = {
            "level": level_name,
            "resolution": resolution,
            "n_communities": n_comms,
            "avg_size": round(avg_size, 1),
            "max_size": max_size,
            "modularity": round(modularity, 4),
            "time_s": round(time.time() - t1, 2),
        }
        level_stats.append(stat)
        print(f"  {level_name} (res={resolution}): {n_comms} communities, "
              f"avg={avg_size:.1f}, max={max_size}, Q={modularity:.4f} ({stat['time_s']}s)")

    communities["metadata"]["level_stats"] = level_stats
    communities["metadata"]["total_time_s"] = round(time.time() - t0, 2)

    # Convert defaultdict for JSON serialization
    communities["node_community"] = dict(communities["node_community"])

    if save:
        with open(COMMUNITIES_FILE, 'w') as f:
            json.dump(communities, f, indent=2)
        print(f"  Saved to {COMMUNITIES_FILE}")

    return communities


def _get_memory_texts(brain, node_ids, max_texts=None):
    """Fetch memory texts for a list of node IDs from ChromaDB."""
    texts = []
    for col_name, col in brain.collections.items():
        # Get IDs that are in this collection
        try:
            result = col.get(ids=[nid for nid in node_ids],
                             include=["documents", "metadatas"])
            for i, doc in enumerate(result.get("documents", [])):
                if doc:
                    meta = result["metadatas"][i] if result.get("metadatas") else {}
                    texts.append({
                        "text": doc,
                        "id": result["ids"][i],
                        "importance": meta.get("importance", 0.5),
                        "collection": col_name,
                    })
        except Exception:
            continue  # IDs not in this collection

    # Sort by importance descending
    texts.sort(key=lambda x: x["importance"], reverse=True)
    if max_texts:
        texts = texts[:max_texts]
    return texts


def _extract_keywords(texts, max_keywords=MAX_KEYWORDS_PER_COMMUNITY):
    """Extract representative keywords from a set of texts.

    Uses TF-based extraction (no LLM needed). Filters stopwords and short tokens.
    """
    import re

    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "that", "this", "was", "are",
        "be", "has", "had", "have", "not", "no", "can", "will", "would", "could",
        "should", "may", "might", "do", "does", "did", "been", "being", "its",
        "as", "if", "than", "then", "so", "very", "just", "about", "also", "more",
        "all", "any", "each", "every", "some", "into", "over", "after", "before",
        "between", "through", "during", "when", "where", "how", "what", "which",
        "who", "whom", "their", "them", "they", "we", "our", "you", "your",
        "he", "she", "his", "her", "my", "me", "i", "up", "out", "one", "two",
        "new", "use", "used", "using", "these", "those",
    }

    word_freq = Counter()
    for entry in texts:
        words = re.findall(r'\b[a-z][a-z_-]+\b', entry["text"].lower())
        for w in words:
            if len(w) > 3 and w not in STOPWORDS:
                word_freq[w] += 1

    return [w for w, _ in word_freq.most_common(max_keywords)]


def generate_summaries(communities=None, save=True):
    """Generate extractive summaries for each community.

    LLM-free: uses keyword extraction and representative text selection.
    These summaries enable global search without per-query LLM calls.
    """
    from clarvis.brain import get_brain
    brain = get_brain()

    if communities is None:
        with open(COMMUNITIES_FILE, 'r') as f:
            communities = json.load(f)

    t0 = time.time()
    summaries = {"levels": {}, "metadata": {"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}

    total_communities = 0
    for level_name in LEVEL_NAMES:
        level_comms = communities["levels"].get(level_name, {})
        level_summaries = {}

        for comm_id, node_ids in level_comms.items():
            texts = _get_memory_texts(brain, node_ids, max_texts=MAX_REPRESENTATIVE_TEXTS * 3)
            if not texts:
                continue

            keywords = _extract_keywords(texts)

            # Collection distribution within this community
            col_dist = Counter(t["collection"] for t in texts)
            dominant_collection = col_dist.most_common(1)[0][0] if col_dist else "unknown"

            # Representative texts (top by importance, deduplicated)
            seen = set()
            representatives = []
            for t in texts[:MAX_REPRESENTATIVE_TEXTS * 2]:
                # Skip near-duplicate texts
                text_key = t["text"][:80]
                if text_key not in seen:
                    seen.add(text_key)
                    representatives.append(t["text"][:300])
                    if len(representatives) >= MAX_REPRESENTATIVE_TEXTS:
                        break

            # Build extractive summary
            theme = ", ".join(keywords[:6]) if keywords else "miscellaneous"
            summary_text = (
                f"Community {comm_id} ({len(node_ids)} memories, "
                f"dominant: {dominant_collection}). "
                f"Key themes: {theme}. "
            )
            if representatives:
                summary_text += "Representative: " + representatives[0][:200]

            level_summaries[comm_id] = {
                "summary": summary_text,
                "keywords": keywords,
                "size": len(node_ids),
                "collection_distribution": dict(col_dist),
                "dominant_collection": dominant_collection,
                "representative_texts": representatives,
            }
            total_communities += 1

        summaries["levels"][level_name] = level_summaries
        print(f"  {level_name}: {len(level_summaries)} community summaries generated")

    summaries["metadata"]["total_communities"] = total_communities
    summaries["metadata"]["total_time_s"] = round(time.time() - t0, 2)

    if save:
        with open(SUMMARIES_FILE, 'w') as f:
            json.dump(summaries, f, indent=2)
        print(f"  Saved to {SUMMARIES_FILE}")

    return summaries


def global_search(query, level="C1", top_k=5):
    """GraphRAG-style global search: score community summaries against query.

    Uses embedding similarity (free, local ONNX) to rank communities,
    then returns the most relevant community contexts.

    Args:
        query: Natural language query
        level: Community level (C0=broadest, C3=most granular)
        top_k: Number of top communities to return

    Returns:
        List of {community_id, score, summary, keywords, representative_texts, size}
    """
    from clarvis.brain import get_brain
    brain = get_brain()

    if not os.path.exists(SUMMARIES_FILE):
        print("No community summaries found. Run: python3 graphrag_communities.py build")
        return []

    with open(SUMMARIES_FILE, 'r') as f:
        summaries = json.load(f)

    level_summaries = summaries.get("levels", {}).get(level, {})
    if not level_summaries:
        print(f"No summaries for level {level}")
        return []

    # Score each community summary against the query using embedding similarity
    # Use ChromaDB's built-in embedding function for consistency
    try:
        # Get query embedding via any collection's embedding function
        any_col = next(iter(brain.collections.values()))
        q_emb = any_col._embedding_function([query])[0]
    except Exception:
        # Fallback: keyword matching
        q_emb = None

    scored = []
    for comm_id, comm_data in level_summaries.items():
        if q_emb is not None:
            # Embedding similarity between query and community summary
            try:
                s_emb = any_col._embedding_function([comm_data["summary"]])[0]
                # Cosine similarity
                dot = sum(a * b for a, b in zip(q_emb, s_emb))
                norm_q = sum(a * a for a in q_emb) ** 0.5
                norm_s = sum(a * a for a in s_emb) ** 0.5
                similarity = dot / (norm_q * norm_s) if norm_q * norm_s > 0 else 0
            except Exception:
                similarity = 0
        else:
            # Fallback: keyword overlap scoring
            query_words = set(query.lower().split())
            kw_set = set(comm_data.get("keywords", []))
            overlap = len(query_words & kw_set)
            similarity = overlap / max(len(query_words), 1) * 0.5

        scored.append({
            "community_id": comm_id,
            "score": round(similarity, 4),
            "summary": comm_data["summary"],
            "keywords": comm_data.get("keywords", []),
            "representative_texts": comm_data.get("representative_texts", []),
            "size": comm_data.get("size", 0),
            "dominant_collection": comm_data.get("dominant_collection", "unknown"),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def enhanced_local_search(query, n=10, community_context_ratio=0.2):
    """Enhanced local search: standard vector recall + community context.

    Mirrors GraphRAG's local search pattern: after retrieving specific memories,
    also include the community summaries those memories belong to.

    Args:
        query: Search query
        n: Number of vector results
        community_context_ratio: Fraction of results to replace with community context

    Returns:
        Dict with "vector_results", "community_context", "merged"
    """
    from clarvis.brain import get_brain
    brain = get_brain()

    # Standard vector recall
    vector_results = brain.recall(query, n=n)

    # Find which communities the top results belong to
    if not os.path.exists(COMMUNITIES_FILE) or not os.path.exists(SUMMARIES_FILE):
        return {
            "vector_results": vector_results,
            "community_context": [],
            "merged": vector_results,
        }

    with open(COMMUNITIES_FILE, 'r') as f:
        communities = json.load(f)
    with open(SUMMARIES_FILE, 'r') as f:
        summaries = json.load(f)

    node_comms = communities.get("node_community", {})
    level = "C1"  # Medium granularity

    # Collect unique community IDs from results
    seen_communities = set()
    community_context = []
    for result in vector_results:
        rid = result.get("id", "")
        comm_info = node_comms.get(rid, {})
        comm_id = comm_info.get(level)
        if comm_id and comm_id not in seen_communities:
            seen_communities.add(comm_id)
            level_summaries = summaries.get("levels", {}).get(level, {})
            comm_summary = level_summaries.get(comm_id)
            if comm_summary:
                community_context.append({
                    "community_id": comm_id,
                    "summary": comm_summary["summary"],
                    "keywords": comm_summary.get("keywords", []),
                    "size": comm_summary.get("size", 0),
                })

    return {
        "vector_results": vector_results,
        "community_context": community_context,
        "merged": vector_results,  # Caller decides how to interleave
    }


def show_stats():
    """Display community statistics."""
    if not os.path.exists(COMMUNITIES_FILE):
        print("No communities detected yet. Run: python3 graphrag_communities.py detect")
        return

    with open(COMMUNITIES_FILE, 'r') as f:
        communities = json.load(f)

    meta = communities.get("metadata", {})
    print("=== GraphRAG Community Statistics ===")
    print(f"Created: {meta.get('created_at', '?')}")
    print(f"Nodes: {meta.get('total_nodes', '?')}, Edges: {meta.get('total_edges', '?')}")
    print()

    for stat in meta.get("level_stats", []):
        print(f"  {stat['level']} (resolution={stat['resolution']}): "
              f"{stat['n_communities']} communities, "
              f"avg size={stat['avg_size']}, "
              f"max size={stat['max_size']}, "
              f"modularity={stat['modularity']}")

    # Show summaries stats if available
    if os.path.exists(SUMMARIES_FILE):
        with open(SUMMARIES_FILE, 'r') as f:
            summaries = json.load(f)
        print(f"\nSummaries: {summaries.get('metadata', {}).get('total_communities', '?')} total")
        for level_name in LEVEL_NAMES:
            level_sums = summaries.get("levels", {}).get(level_name, {})
            if level_sums:
                avg_kw = sum(len(s.get("keywords", [])) for s in level_sums.values()) / len(level_sums)
                print(f"  {level_name}: {len(level_sums)} summaries, avg {avg_kw:.1f} keywords")


def show_community_info(comm_id):
    """Show detailed information about a specific community."""
    if not os.path.exists(SUMMARIES_FILE):
        print("No summaries available. Run: python3 graphrag_communities.py build")
        return

    with open(SUMMARIES_FILE, 'r') as f:
        summaries = json.load(f)

    # Search across all levels
    for level_name in LEVEL_NAMES:
        level_sums = summaries.get("levels", {}).get(level_name, {})
        if comm_id in level_sums:
            data = level_sums[comm_id]
            print(f"=== Community {comm_id} ===")
            print(f"Level: {level_name}")
            print(f"Size: {data.get('size', '?')} memories")
            print(f"Dominant collection: {data.get('dominant_collection', '?')}")
            print(f"Collection dist: {data.get('collection_distribution', {})}")
            print(f"Keywords: {', '.join(data.get('keywords', []))}")
            print(f"\nSummary: {data.get('summary', 'N/A')}")
            print("\nRepresentative texts:")
            for i, txt in enumerate(data.get("representative_texts", []), 1):
                print(f"  {i}. {txt[:200]}")
            return

    print(f"Community {comm_id} not found")


# === CLI ===
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "detect":
        print("Running Leiden community detection...")
        detect_communities()

    elif cmd == "summarize":
        print("Generating community summaries...")
        generate_summaries()

    elif cmd == "build":
        print("Full GraphRAG pipeline: detect + summarize")
        comms = detect_communities()
        generate_summaries(communities=comms)
        print("\nDone. Run 'global \"query\"' to test global search.")

    elif cmd == "global":
        query = sys.argv[2] if len(sys.argv) > 2 else "What are the main themes of my knowledge?"
        level = sys.argv[3] if len(sys.argv) > 3 else "C1"
        print(f"Global search (level={level}): {query}\n")
        results = global_search(query, level=level)
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['score']:.3f}] {r['community_id']} ({r['size']} memories)")
            print(f"   Keywords: {', '.join(r['keywords'][:8])}")
            print(f"   {r['summary'][:200]}")
            print()

    elif cmd == "local":
        query = sys.argv[2] if len(sys.argv) > 2 else "cognitive architecture"
        print(f"Enhanced local search: {query}\n")
        results = enhanced_local_search(query)
        print(f"Vector results: {len(results['vector_results'])}")
        print(f"Community context: {len(results['community_context'])}")
        for ctx in results["community_context"]:
            print(f"  {ctx['community_id']}: {', '.join(ctx['keywords'][:6])}")

    elif cmd == "stats":
        show_stats()

    elif cmd == "info":
        cid = sys.argv[2] if len(sys.argv) > 2 else ""
        show_community_info(cid)

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: detect, summarize, build, global, local, stats, info")

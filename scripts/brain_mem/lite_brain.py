#!/usr/bin/env python3
"""Lite Brain — lightweight vector DB for project agents.

A stripped-down version of brain.py for project agents. Uses the same
ChromaDB + ONNX stack but with fewer collections and no cross-agent leakage.

Each project agent gets its own data directory at:
  ~/agents/<name>/data/brain/

Collections (6 vs Clarvis's 10):
  project-learnings   — what the agent learned about this repo
  project-procedures  — how-to for this repo (build, test, deploy)
  project-context     — current state, recent work
  project-episodes    — task outcomes with timestamps
  project-goals       — project-specific objectives
  project-sector      — domain/product playbook constraints (Layer E)

Usage (from a project agent's scripts/):
    from lite_brain import LiteBrain
    brain = LiteBrain("~/agents/my-project/data/brain")
    brain.store("npm run build is the build command", "project-procedures")
    results = brain.recall("how to build")

Also auto-detects agent context:
    from lite_brain import brain  # uses AGENT_BRAIN_DIR env var
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ONNX embeddings — same as Clarvis brain
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

COLLECTIONS = [
    "project-learnings",
    "project-procedures",
    "project-context",
    "project-episodes",
    "project-goals",
    "project-sector",
]

DEFAULT_COLLECTION = "project-learnings"


class LiteBrain:
    """Lightweight vector brain for project agents."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collections = {}
        self._embed_fn = None
        self.graph_file = self.data_dir / "relationships.json"

    def _get_client(self):
        if self._client is None:
            from clarvis.brain.factory import get_chroma_client
            self._client = get_chroma_client(str(self.data_dir))
        return self._client

    def _get_collection(self, name: str):
        if name not in self._collections:
            client = self._get_client()
            embed_fn = self._get_embed_fn()
            self._collections[name] = client.get_or_create_collection(
                name=name,
                embedding_function=embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def _get_embed_fn(self):
        if self._embed_fn is None:
            from clarvis.brain.factory import get_embedding_function
            self._embed_fn = get_embedding_function(use_onnx=True)
        return self._embed_fn

    def _gen_id(self, text: str) -> str:
        h = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:12]
        return f"lb-{h}"

    def store(self, text: str, collection: str = DEFAULT_COLLECTION,
              importance: float = 0.5, tags: Optional[list] = None,
              source: str = "agent") -> str:
        """Store a memory in the project brain."""
        if collection not in COLLECTIONS:
            collection = DEFAULT_COLLECTION

        col = self._get_collection(collection)
        doc_id = self._gen_id(text)

        metadata = {
            "importance": importance,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
        }
        if tags:
            metadata["tags"] = ",".join(tags)

        col.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[metadata],
        )

        return doc_id

    def recall(self, query: str, n_results: int = 5,
               collection: Optional[str] = None) -> list:
        """Recall memories relevant to a query."""
        collections_to_search = [collection] if collection else COLLECTIONS
        all_results = []

        for col_name in collections_to_search:
            try:
                col = self._get_collection(col_name)
                if col.count() == 0:
                    continue

                results = col.query(
                    query_texts=[query],
                    n_results=min(n_results, col.count()),
                )

                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    dist = results["distances"][0][i] if results["distances"] else 1.0
                    all_results.append({
                        "document": doc,
                        "id": results["ids"][0][i],
                        "collection": col_name,
                        "metadata": meta,
                        "distance": dist,
                        "relevance": max(0, 1.0 - dist),
                    })
            except Exception:
                continue

        # Sort by relevance
        all_results.sort(key=lambda x: x["relevance"], reverse=True)
        return all_results[:n_results]

    def search(self, query: str, n_results: int = 10) -> list:
        """Search all collections."""
        return self.recall(query, n_results=n_results)

    def sector_recall(self, query: str, n_results: int = 5) -> list:
        """Retrieve sector/domain playbook constraints relevant to query.

        Searches the project-sector collection for domain-specific knowledge
        (governance rules, product constraints, safety invariants, etc.).
        Returns list of dicts with document, relevance, metadata.
        """
        return self.recall(query, n_results=n_results, collection="project-sector")

    def store_sector(self, text: str, constraint_type: str = "domain",
                     importance: float = 0.7, source: str = "sector_playbook") -> str:
        """Store a sector/domain constraint in the project-sector collection.

        Args:
            text: The constraint or domain knowledge text.
            constraint_type: One of: domain, governance, safety, product, invariant.
            importance: Priority weight (default 0.7 for sector constraints).
            source: Origin identifier.

        Returns: The stored document ID.
        """
        tags = ["sector", f"type:{constraint_type}"]
        return self.store(text, "project-sector", importance=importance,
                          tags=tags, source=source)

    def stats(self) -> dict:
        """Get brain statistics."""
        counts = {}
        total = 0
        for col_name in COLLECTIONS:
            try:
                col = self._get_collection(col_name)
                c = col.count()
                counts[col_name] = c
                total += c
            except Exception:
                counts[col_name] = 0

        graph_edges = 0
        if self.graph_file.exists():
            try:
                g = json.loads(self.graph_file.read_text())
                graph_edges = len(g.get("edges", []))
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "total_memories": total,
            "collections": counts,
            "graph_edges": graph_edges,
            "data_dir": str(self.data_dir),
        }

    def health_check(self) -> dict:
        """Quick store/recall health check."""
        test_text = f"health_check_{time.time()}"
        try:
            doc_id = self.store(test_text, "project-context", importance=0.1)
            results = self.recall(test_text, n_results=1, collection="project-context")
            found = any(r["id"] == doc_id for r in results)

            # Clean up test
            col = self._get_collection("project-context")
            col.delete(ids=[doc_id])

            return {"status": "healthy" if found else "degraded", "store": True, "recall": found}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def seed_from_file(self, golden_qa_path: str) -> int:
        """Seed brain from a golden_qa.json file. Returns count of seeded items."""
        qa_path = Path(golden_qa_path)
        if not qa_path.exists():
            return 0

        golden = json.loads(qa_path.read_text())
        count = 0
        for qa in golden:
            answer = qa.get("answer", "")
            collection = qa.get("collection", "project-procedures")
            if answer:
                self.store(answer, collection, importance=0.8,
                           tags=qa.get("tags", ["golden_qa"]),
                           source="golden_qa_seed")
                count += 1
        return count

    def benchmark_retrieval(self, golden_qa_path: str) -> dict:
        """Benchmark retrieval quality using golden Q/A pairs.

        Returns P@1, P@3, MRR, and per-query details.
        """
        qa_path = Path(golden_qa_path)
        if not qa_path.exists():
            return {"status": "no_golden_qa", "path": golden_qa_path}

        golden = json.loads(qa_path.read_text())
        hits_1 = 0
        hits_3 = 0
        reciprocal_ranks = []
        details = []

        for qa in golden:
            query = qa["query"]
            expected_keywords = qa.get("expected_docs", [])

            results = self.recall(query, n_results=5)
            top_texts = [r["document"].lower() for r in results[:5]]

            # Check P@1
            hit_1 = any(kw.lower() in top_texts[0] for kw in expected_keywords) if top_texts else False
            if hit_1:
                hits_1 += 1

            # Check P@3
            top3_text = " ".join(top_texts[:3])
            hit_3 = any(kw.lower() in top3_text for kw in expected_keywords)
            if hit_3:
                hits_3 += 1

            # MRR
            rr = 0.0
            for i, text in enumerate(top_texts):
                if any(kw.lower() in text for kw in expected_keywords):
                    rr = 1.0 / (i + 1)
                    break
            reciprocal_ranks.append(rr)

            details.append({
                "query": query[:80],
                "hit_at_1": hit_1,
                "hit_at_3": hit_3,
                "rr": round(rr, 3),
            })

        total = max(len(golden), 1)
        return {
            "total_queries": len(golden),
            "p_at_1": round(hits_1 / total, 3),
            "p_at_3": round(hits_3 / total, 3),
            "mrr": round(sum(reciprocal_ranks) / total, 3),
            "pass": hits_3 / total > 0.6,
            "details": details,
        }

    def add_edge(self, source_id: str, target_id: str, edge_type: str = "related",
                 weight: float = 0.5):
        """Add a semantic link between two memories."""
        graph = self._load_graph()

        graph["nodes"].setdefault(source_id, {"created": datetime.now(timezone.utc).isoformat()})
        graph["nodes"].setdefault(target_id, {"created": datetime.now(timezone.utc).isoformat()})

        # Check for existing edge
        for edge in graph["edges"]:
            if edge["source"] == source_id and edge["target"] == target_id and edge.get("type") == edge_type:
                edge["weight"] = min(1.0, edge["weight"] + 0.1)
                break
        else:
            graph["edges"].append({
                "source": source_id,
                "target": target_id,
                "type": edge_type,
                "weight": weight,
                "created": datetime.now(timezone.utc).isoformat(),
            })

        self._save_graph(graph)

    def _load_graph(self) -> dict:
        """Load the graph from disk."""
        if self.graph_file.exists():
            try:
                return json.loads(self.graph_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"nodes": {}, "edges": []}

    def _save_graph(self, graph: dict):
        """Atomically save graph to disk."""
        tmp = self.graph_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(graph, indent=2))
        tmp.replace(self.graph_file)

    def get_edges_by_type(self, edge_type: str) -> list:
        """Get all edges of a specific type."""
        graph = self._load_graph()
        return [e for e in graph["edges"] if e.get("type") == edge_type]

    def get_related(self, node_id: str, edge_types: Optional[list] = None) -> list:
        """Get nodes related to node_id, optionally filtered by edge types."""
        graph = self._load_graph()
        related = []
        for edge in graph["edges"]:
            if edge_types and edge.get("type") not in edge_types:
                continue
            if edge["source"] == node_id:
                related.append({"id": edge["target"], "type": edge.get("type", "related"),
                                "weight": edge.get("weight", 0.5), "direction": "outgoing"})
            elif edge["target"] == node_id:
                related.append({"id": edge["source"], "type": edge.get("type", "related"),
                                "weight": edge.get("weight", 0.5), "direction": "incoming"})
        return related

    def build_typed_edges(self, indexes: dict) -> dict:
        """Build typed relationship edges from precision indexes.

        Creates edges: route→file, symbol→file, test→module.
        Returns counts of edges created per type.
        """
        counts = {"route_file": 0, "symbol_file": 0, "test_module": 0}
        graph = self._load_graph()

        # Existing edge set for dedup
        existing = {(e["source"], e["target"], e.get("type", "related")) for e in graph["edges"]}
        now = datetime.now(timezone.utc).isoformat()

        # route→file edges from route_index
        route_idx = indexes.get("route_index", {})
        routes = route_idx.get("routes", []) if isinstance(route_idx, dict) else []
        for r in routes:
            route_path = r.get("path", "")
            file_path = r.get("file", "")
            if route_path and file_path:
                src = f"route:{route_path}"
                tgt = f"file:{file_path}"
                if (src, tgt, "route_file") not in existing:
                    graph["nodes"].setdefault(src, {"created": now})
                    graph["nodes"].setdefault(tgt, {"created": now})
                    graph["edges"].append({
                        "source": src, "target": tgt, "type": "route_file",
                        "weight": 0.9, "created": now,
                    })
                    existing.add((src, tgt, "route_file"))
                    counts["route_file"] += 1

        # symbol→file edges from symbol_index
        sym_idx = indexes.get("symbol_index", {})
        symbols = sym_idx.get("symbols", []) if isinstance(sym_idx, dict) else []
        for entry in symbols:
            file_path = entry.get("file", "")
            for sym in entry.get("symbols", [])[:20]:
                sym_name = sym.get("name", "")
                if sym_name and file_path:
                    src = f"symbol:{sym_name}"
                    tgt = f"file:{file_path}"
                    if (src, tgt, "symbol_file") not in existing:
                        graph["nodes"].setdefault(src, {"created": now})
                        graph["nodes"].setdefault(tgt, {"created": now})
                        graph["edges"].append({
                            "source": src, "target": tgt, "type": "symbol_file",
                            "weight": 0.8, "created": now,
                        })
                        existing.add((src, tgt, "symbol_file"))
                        counts["symbol_file"] += 1

        # test→module edges from test_index
        test_idx = indexes.get("test_index", {})
        tests = test_idx.get("tests", []) if isinstance(test_idx, dict) else []
        for t in tests:
            test_file = t.get("test_file", "")
            source_module = t.get("likely_source", "")
            if test_file and source_module:
                src = f"test:{test_file}"
                tgt = f"module:{source_module}"
                if (src, tgt, "test_module") not in existing:
                    graph["nodes"].setdefault(src, {"created": now})
                    graph["nodes"].setdefault(tgt, {"created": now})
                    graph["edges"].append({
                        "source": src, "target": tgt, "type": "test_module",
                        "weight": 0.85, "created": now,
                    })
                    existing.add((src, tgt, "test_module"))
                    counts["test_module"] += 1

        self._save_graph(graph)
        return counts

    def hybrid_recall(self, query: str, indexes: Optional[dict] = None,
                      n_results: int = 5) -> dict:
        """Hybrid retrieval combining vector recall with typed edge expansion.

        Returns:
            {
                "memories": [...],        # from vector recall
                "related_files": [...],   # from typed edges (route→file, symbol→file)
                "related_tests": [...],   # test files for matched modules
            }
        """
        # 1. Vector recall from brain
        memories = self.recall(query, n_results=n_results)

        # 1b. Sector constraints (always retrieved, independent of indexes)
        sector_constraints = self.sector_recall(query, n_results=3)
        sector_texts = [s["document"] for s in sector_constraints
                        if s.get("relevance", 0) > 0.15]

        result = {
            "memories": memories,
            "related_files": [],
            "related_tests": [],
            "sector_constraints": sector_texts,
        }

        if not indexes:
            return result

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 3]
        graph = self._load_graph()

        # 2. Route-based file lookup: match query words against route paths
        seen_files = set()
        for edge in graph["edges"]:
            if edge.get("type") != "route_file":
                continue
            route = edge["source"].replace("route:", "")
            if any(w in route.lower() for w in query_words):
                file_path = edge["target"].replace("file:", "")
                if file_path not in seen_files:
                    result["related_files"].append(file_path)
                    seen_files.add(file_path)

        # 3. Symbol-based file lookup: match query words against symbol names
        for edge in graph["edges"]:
            if edge.get("type") != "symbol_file":
                continue
            symbol = edge["source"].replace("symbol:", "").lower()
            if any(w in symbol for w in query_words):
                file_path = edge["target"].replace("file:", "")
                if file_path not in seen_files:
                    result["related_files"].append(file_path)
                    seen_files.add(file_path)

        # 4. Test lookup: for each matched file, find its tests
        for file_path in list(result["related_files"]):
            # Derive module name from file path
            module_name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
            for edge in graph["edges"]:
                if edge.get("type") != "test_module":
                    continue
                if module_name in edge["target"]:
                    test_file = edge["source"].replace("test:", "")
                    if test_file not in result["related_tests"]:
                        result["related_tests"].append(test_file)

        # Cap results
        result["related_files"] = result["related_files"][:10]
        result["related_tests"] = result["related_tests"][:5]

        return result


# Auto-detect brain directory from environment
def _auto_brain() -> Optional[LiteBrain]:
    brain_dir = os.environ.get("AGENT_BRAIN_DIR")
    if brain_dir:
        return LiteBrain(brain_dir)

    # Try to detect from CWD
    cwd = Path.cwd()
    # Check if we're inside an agent workspace
    for parent in [cwd] + list(cwd.parents):
        agent_brain = parent.parent / "data" / "brain"
        if agent_brain.exists() and (parent.parent / "configs" / "agent.json").exists():
            return LiteBrain(str(agent_brain))

    return None


# Singleton (lazy — no filesystem probing until first access)
class _LazyLiteBrain:
    def __getattr__(self, name):
        real = _auto_brain()
        global brain
        brain = real
        if real is None:
            raise AttributeError(f"No agent brain detected and attribute '{name}' accessed")
        return getattr(real, name)
    def __repr__(self):
        return "<LazyLiteBrain (not yet initialized)>"

brain = _LazyLiteBrain()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Lite Brain for project agents")
    parser.add_argument("command", choices=["stats", "health", "search", "seed", "benchmark"],
                        help="Command to run")
    parser.add_argument("--dir", help="Brain data directory")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--golden-qa", help="Path to golden_qa.json (for seed/benchmark)")
    args = parser.parse_args()

    b = LiteBrain(args.dir) if args.dir else brain
    if not b:
        print("ERROR: No brain directory found. Set AGENT_BRAIN_DIR or use --dir", file=sys.stderr)
        sys.exit(1)

    if args.command == "stats":
        print(json.dumps(b.stats(), indent=2))
    elif args.command == "health":
        print(json.dumps(b.health_check(), indent=2))
    elif args.command == "search":
        if not args.query:
            print("ERROR: --query required for search", file=sys.stderr)
            sys.exit(1)
        results = b.search(args.query)
        for r in results:
            print(f"  [{r['collection']}] {r['relevance']:.2f} — {r['document'][:100]}")
    elif args.command == "seed":
        if not args.golden_qa:
            print("ERROR: --golden-qa required for seed", file=sys.stderr)
            sys.exit(1)
        count = b.seed_from_file(args.golden_qa)
        print(f"Seeded {count} memories from {args.golden_qa}")
    elif args.command == "benchmark":
        if not args.golden_qa:
            print("ERROR: --golden-qa required for benchmark", file=sys.stderr)
            sys.exit(1)
        result = b.benchmark_retrieval(args.golden_qa)
        print(json.dumps(result, indent=2))

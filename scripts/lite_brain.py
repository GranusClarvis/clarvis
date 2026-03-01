#!/usr/bin/env python3
"""Lite Brain — lightweight vector DB for project agents.

A stripped-down version of brain.py for project agents. Uses the same
ChromaDB + ONNX stack but with fewer collections and no cross-agent leakage.

Each project agent gets its own data directory at:
  /home/agent/agents/<name>/data/brain/

Collections (5 vs Clarvis's 10):
  project-learnings   — what the agent learned about this repo
  project-procedures  — how-to for this repo (build, test, deploy)
  project-context     — current state, recent work
  project-episodes    — task outcomes with timestamps
  project-goals       — project-specific objectives

Usage (from a project agent's scripts/):
    from lite_brain import LiteBrain
    brain = LiteBrain("/home/agent/agents/my-project/data/brain")
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
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(self.data_dir),
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
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
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            self._embed_fn = ONNXMiniLM_L6_V2()
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
        graph = {"nodes": {}, "edges": []}
        if self.graph_file.exists():
            try:
                graph = json.loads(self.graph_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        graph["nodes"].setdefault(source_id, {"created": datetime.now(timezone.utc).isoformat()})
        graph["nodes"].setdefault(target_id, {"created": datetime.now(timezone.utc).isoformat()})

        # Check for existing edge
        for edge in graph["edges"]:
            if edge["source"] == source_id and edge["target"] == target_id:
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

        tmp = self.graph_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(graph, indent=2))
        tmp.replace(self.graph_file)


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


# Singleton for easy import
brain = _auto_brain()

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

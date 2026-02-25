"""
VectorStore — the core ClarvisDB vector memory store.

ChromaDB-backed vector store with:
- Local ONNX MiniLM embeddings (no cloud dependency)
- Named collections with metadata
- Relationship graph (JSON-backed)
- Importance-weighted recall with semantic ranking
- Auto-linking within and across collections

Standalone: ChromaDB and ONNX are optional. Falls back to keyword matching.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from clarvis_db.hebbian import HebbianEngine
from clarvis_db.stdp import SynapticEngine


class VectorStore:
    """ChromaDB-backed vector memory with Hebbian learning + STDP synapses.

    Args:
        data_dir: Root directory for all data (ChromaDB, graph, hebbian, synaptic).
        collections: List of collection names to create.
        use_onnx: Use local ONNX MiniLM embeddings (default True).
        enable_hebbian: Enable Hebbian importance evolution.
        enable_stdp: Enable STDP synaptic learning.
        on_store: Callback(memory_id, text, collection) after store.
        on_recall: Callback(query, results) after recall.
    """

    def __init__(
        self,
        data_dir: str = "./data/clarvisdb",
        collections: Optional[List[str]] = None,
        use_onnx: bool = True,
        enable_hebbian: bool = True,
        enable_stdp: bool = True,
        on_store: Optional[Callable] = None,
        on_recall: Optional[Callable] = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.data_dir / "relationships.json"
        self.on_store = on_store
        self.on_recall_cb = on_recall
        self._use_onnx = use_onnx
        self._chroma_available = False

        # Initialize ChromaDB
        self._client = None
        self._embedding_fn = None
        self._collections: Dict[str, Any] = {}
        collection_names = collections or ["memories"]

        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.data_dir / "chroma"))

            if use_onnx:
                try:
                    from chromadb.utils import embedding_functions
                    self._embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
                except Exception:
                    self._embedding_fn = None

            for name in collection_names:
                if self._embedding_fn:
                    self._collections[name] = self._client.get_or_create_collection(
                        name, embedding_function=self._embedding_fn
                    )
                else:
                    self._collections[name] = self._client.get_or_create_collection(name)

            self._chroma_available = True
        except ImportError:
            pass  # ChromaDB not installed — keyword fallback

        # Load relationship graph
        self.graph = self._load_graph()

        # Hebbian engine
        self.hebbian: Optional[HebbianEngine] = None
        if enable_hebbian:
            self.hebbian = HebbianEngine(data_dir=str(self.data_dir / "hebbian"))

        # STDP engine
        self.synaptic: Optional[SynapticEngine] = None
        if enable_stdp:
            self.synaptic = SynapticEngine(
                db_path=str(self.data_dir / "synaptic" / "synapses.db")
            )

    # === CORE API ===

    def store(
        self,
        text: str,
        collection: str = "memories",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        source: str = "api",
        memory_id: Optional[str] = None,
    ) -> str:
        """Store a memory.

        Args:
            text: Memory content.
            collection: Target collection name.
            importance: 0-1 importance score.
            tags: Categorization tags.
            source: Origin of this memory.
            memory_id: Custom ID (auto-generated if None).

        Returns:
            The memory ID.
        """
        if memory_id is None:
            memory_id = f"{collection}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        metadata = {
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
            "importance": importance,
            "source": source,
        }
        if tags:
            metadata["tags"] = json.dumps(tags)

        if self._chroma_available and collection in self._collections:
            self._collections[collection].upsert(
                ids=[memory_id], documents=[text], metadatas=[metadata]
            )
            self._auto_link(memory_id, text, collection)
        else:
            # Fallback: store in graph as a node
            self.graph["nodes"][memory_id] = {
                "collection": collection,
                "text": text,
                "metadata": metadata,
            }
            self._save_graph()

        if self.on_store:
            try:
                self.on_store(memory_id, text, collection)
            except Exception:
                pass

        return memory_id

    def recall(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        n: int = 5,
        min_importance: Optional[float] = None,
        since_days: Optional[int] = None,
        caller: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recall memories matching a query.

        Args:
            query: Search query.
            collections: Collections to search (None = all).
            n: Max results per collection.
            min_importance: Filter threshold.
            since_days: Only recent memories.
            caller: Who is calling (for tracking).

        Returns:
            List of result dicts with document, metadata, collection, id, distance.
        """
        if collections is None:
            collections = list(self._collections.keys())

        cutoff = None
        if since_days:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

        results = []

        if self._chroma_available:
            for col_name in collections:
                if col_name not in self._collections:
                    continue
                col = self._collections[col_name]
                try:
                    r = col.query(query_texts=[query], n_results=n)
                except Exception:
                    continue

                if not r["documents"] or not r["documents"][0]:
                    continue

                for i, doc in enumerate(r["documents"][0]):
                    meta = r["metadatas"][0][i] if r.get("metadatas") else {}

                    if min_importance is not None:
                        if meta.get("importance", 0) < min_importance:
                            continue
                    if cutoff and meta.get("created_at", "") < cutoff:
                        continue

                    dist = r["distances"][0][i] if r.get("distances") else None
                    results.append({
                        "document": doc,
                        "metadata": meta,
                        "collection": col_name,
                        "id": r["ids"][0][i],
                        "distance": dist,
                    })

        # Sort by combined relevance
        def sort_key(x):
            d = x.get("distance")
            sem = 1.0 / (1.0 + d) if d is not None else 0.5
            imp = x["metadata"].get("importance", 0.5)
            if isinstance(imp, str):
                try:
                    imp = float(imp)
                except ValueError:
                    imp = 0.5
            return sem * 0.7 + imp * 0.3

        results.sort(key=sort_key, reverse=True)
        final = results[:n * len(collections)]

        # Hebbian tracking
        if self.hebbian and final:
            try:
                ids = [r["id"] for r in final]
                self.hebbian.on_recall(query, ids, caller=caller)
            except Exception:
                pass

        # STDP tracking
        if self.synaptic and final:
            try:
                ids = [r["id"] for r in final]
                self.synaptic.on_recall(ids, caller=caller)
            except Exception:
                pass

        if self.on_recall_cb:
            try:
                self.on_recall_cb(query, final)
            except Exception:
                pass

        return final

    def get(self, collection: str, n: int = 100) -> List[Dict[str, Any]]:
        """Get all memories from a collection."""
        if not self._chroma_available or collection not in self._collections:
            return []
        col = self._collections[collection]
        results = col.get(limit=n)
        out = []
        for i, doc in enumerate(results.get("documents", [])):
            out.append({
                "document": doc,
                "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                "id": results["ids"][i],
            })
        return out

    def delete(self, memory_id: str, collection: str = "memories") -> bool:
        """Delete a memory by ID."""
        if self._chroma_available and collection in self._collections:
            try:
                self._collections[collection].delete(ids=[memory_id])
                return True
            except Exception:
                return False
        return False

    # === GRAPH ===

    def add_relationship(self, from_id: str, to_id: str, rel_type: str = "related"):
        """Add a graph relationship between memories."""
        for existing in self.graph["edges"]:
            if existing["from"] == from_id and existing["to"] == to_id and existing["type"] == rel_type:
                return existing
        edge = {
            "from": from_id, "to": to_id, "type": rel_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if from_id not in self.graph["nodes"]:
            self.graph["nodes"][from_id] = {"added_at": edge["created_at"]}
        if to_id not in self.graph["nodes"]:
            self.graph["nodes"][to_id] = {"added_at": edge["created_at"]}
        self.graph["edges"].append(edge)
        self._save_graph()
        return edge

    def get_related(self, memory_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get memories related via graph edges."""
        related = []
        visited = set()

        def traverse(node_id, d):
            if d > depth or node_id in visited:
                return
            visited.add(node_id)
            for e in self.graph["edges"]:
                if e["from"] == node_id:
                    related.append({"id": e["to"], "relationship": e["type"], "depth": d})
                    traverse(e["to"], d + 1)
                elif e["to"] == node_id:
                    related.append({"id": e["from"], "relationship": f"inverse-{e['type']}", "depth": d})
                    traverse(e["from"], d + 1)

        traverse(memory_id, 1)
        return related

    # === SPREADING ACTIVATION (via STDP) ===

    def associative_recall(self, memory_ids: List[str], n: int = 5) -> List[Dict[str, Any]]:
        """Recall memories associated with given IDs via STDP spreading activation.

        Returns full memory dicts (not just IDs) by looking up spread results
        in ChromaDB collections.
        """
        if not self.synaptic:
            return []

        spread = self.synaptic.spread(memory_ids, n=n)
        results = []
        for mem_id, activation in spread:
            # Try to find this memory in collections
            for col_name, col in self._collections.items():
                try:
                    r = col.get(ids=[mem_id])
                    if r["ids"]:
                        results.append({
                            "id": mem_id,
                            "document": r["documents"][0] if r["documents"] else "",
                            "metadata": r["metadatas"][0] if r.get("metadatas") else {},
                            "collection": col_name,
                            "activation": activation,
                        })
                        break
                except Exception:
                    continue
        return results

    # === EVOLUTION ===

    def evolve(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run full evolution: Hebbian decay + STDP consolidation.

        Returns combined stats from both engines.
        """
        result = {}

        # Hebbian evolution
        if self.hebbian and self._chroma_available:
            all_mems = []
            for col_name, col in self._collections.items():
                try:
                    r = col.get()
                    for i, mem_id in enumerate(r.get("ids", [])):
                        meta = r["metadatas"][i] if r.get("metadatas") else {}
                        meta["id"] = mem_id
                        meta["_collection"] = col_name
                        meta["_document"] = r["documents"][i] if r.get("documents") else ""
                        all_mems.append(meta)
                except Exception:
                    continue

            heb_stats = self.hebbian.evolve(all_mems, dry_run=dry_run)
            result["hebbian"] = heb_stats

            # Write back mutations
            if not dry_run:
                for mem in all_mems:
                    col_name = mem.pop("_collection", None)
                    doc = mem.pop("_document", "")
                    mem_id = mem.pop("id", None)
                    if col_name and mem_id and col_name in self._collections:
                        try:
                            self._collections[col_name].upsert(
                                ids=[mem_id], documents=[doc], metadatas=[mem]
                            )
                        except Exception:
                            pass

        # STDP consolidation
        if self.synaptic:
            result["stdp"] = self.synaptic.consolidate()

        return result

    # === STATS ===

    def stats(self) -> Dict[str, Any]:
        """Get comprehensive store statistics."""
        s = {
            "collections": {},
            "total_memories": 0,
            "graph_nodes": len(self.graph["nodes"]),
            "graph_edges": len(self.graph["edges"]),
            "chroma_available": self._chroma_available,
            "onnx_embeddings": self._embedding_fn is not None,
        }
        if self._chroma_available:
            for name, col in self._collections.items():
                count = col.count()
                s["collections"][name] = count
                s["total_memories"] += count

        if self.hebbian:
            s["hebbian"] = self.hebbian.coactivation_stats()
        if self.synaptic:
            s["synaptic"] = self.synaptic.stats()

        return s

    # === INTERNAL ===

    def _load_graph(self):
        if self.graph_file.exists():
            try:
                with open(self.graph_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"nodes": {}, "edges": []}

    def _save_graph(self):
        # Atomic write: write to temp file, then replace
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.graph_file) or ".", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(self.graph, f, indent=2)
            os.replace(tmp_path, self.graph_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _auto_link(self, memory_id, text, collection):
        """Auto-link to similar memories within and across collections."""
        try:
            # Same-collection links
            col = self._collections[collection]
            results = col.query(query_texts=[text], n_results=4)
            if results["ids"] and results["ids"][0]:
                linked = 0
                for rid in results["ids"][0]:
                    if rid == memory_id:
                        continue
                    self.add_relationship(memory_id, rid, "similar_to")
                    linked += 1
                    if linked >= 3:
                        break

            # Cross-collection links
            cross = 0
            for other_name, other_col in self._collections.items():
                if other_name == collection:
                    continue
                try:
                    xr = other_col.query(query_texts=[text], n_results=1)
                    if xr["ids"] and xr["ids"][0] and xr["distances"] and xr["distances"][0]:
                        if xr["distances"][0][0] < 1.5:
                            self.add_relationship(memory_id, xr["ids"][0][0], "cross_collection")
                            cross += 1
                            if cross >= 4:
                                break
                except Exception:
                    continue
        except Exception:
            pass

#!/usr/bin/env python3
"""
Clarvis Brain - Unified Memory System
Single source of truth for all Clarvis memories

Usage:
    from brain import brain
    
    brain.store("important fact", importance=0.9, tags=["learning"])
    brain.recall("what do I know about X")
    brain.get_goals()
    brain.set_context("working on ClarvisDB")
    
    # Use local embeddings (no cloud dependency)
    from brain import LocalBrain
    local_brain = LocalBrain()
"""

import chromadb
import json
import os
from datetime import datetime, timezone

# Single database location
DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb"
LOCAL_DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb-local"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

# Graph file
GRAPH_FILE = os.path.join(DATA_DIR, "relationships.json")
LOCAL_GRAPH_FILE = os.path.join(LOCAL_DATA_DIR, "relationships.json")

# Collection names
IDENTITY = "clarvis-identity"
PREFERENCES = "clarvis-preferences"
LEARNINGS = "clarvis-learnings"
INFRASTRUCTURE = "clarvis-infrastructure"
GOALS = "clarvis-goals"
CONTEXT = "clarvis-context"
MEMORIES = "clarvis-memories"

ALL_COLLECTIONS = [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, CONTEXT, MEMORIES]


def get_local_embedding_function():
    """Get ONNX MiniLM embedding function (fully local, no cloud)"""
    from chromadb.utils import embedding_functions
    return embedding_functions.ONNXMiniLM_L6_V2()


class ClarvisBrain:
    """Unified brain for Clarvis - single source of truth"""
    
    def __init__(self, use_local_embeddings=False):
        self.use_local_embeddings = use_local_embeddings
        
        if use_local_embeddings:
            self.data_dir = LOCAL_DATA_DIR
            self.graph_file = LOCAL_GRAPH_FILE
            self.embedding_function = get_local_embedding_function()
        else:
            self.data_dir = DATA_DIR
            self.graph_file = GRAPH_FILE
            self.embedding_function = None  # Use ChromaDB default
        
        self.client = chromadb.PersistentClient(path=self.data_dir)
        self._init_collections()
        self._load_graph()
    
    def _init_collections(self):
        """Ensure all collections exist"""
        self.collections = {}
        for name in ALL_COLLECTIONS:
            if self.embedding_function:
                self.collections[name] = self.client.get_or_create_collection(
                    name, 
                    embedding_function=self.embedding_function
                )
            else:
                self.collections[name] = self.client.get_or_create_collection(name)
    
    def _load_graph(self):
        """Load relationship graph"""
        if os.path.exists(self.graph_file):
            with open(self.graph_file, 'r') as f:
                self.graph = json.load(f)
        else:
            self.graph = {"nodes": {}, "edges": []}
    
    def _save_graph(self):
        """Save relationship graph"""
        with open(self.graph_file, 'w') as f:
            json.dump(self.graph, f, indent=2)
    
    # === CORE OPERATIONS ===
    
    def store(self, text, collection=MEMORIES, importance=0.5, tags=None, source="conversation", memory_id=None):
        """
        Store a memory with rich metadata
        
        Args:
            text: The memory content
            collection: Which collection (identity, preferences, learnings, etc.)
            importance: 0-1, how important this memory is
            tags: List of tags for categorization
            source: Where this memory came from
            memory_id: Optional custom ID
        
        Returns:
            The memory ID
        """
        if collection not in self.collections:
            collection = MEMORIES
        
        col = self.collections[collection]
        
        if memory_id is None:
            memory_id = f"{collection}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        tags = tags or []
        
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
        
        col.upsert(
            ids=[memory_id],
            documents=[text],
            metadatas=[metadata]
        )

        # Auto-link to similar memories
        self.auto_link(memory_id, text, collection)

        return memory_id
    
    def auto_link(self, memory_id, text, collection):
        """
        Automatically link a memory to its top-3 most similar existing memories.

        Uses recall() to find similar memories and add_relationship() to create
        graph edges of type 'similar_to'.

        Args:
            memory_id: ID of the newly stored memory
            text: The memory text (used as the search query)
            collection: The collection the memory was stored in
        """
        try:
            # Search the same collection for similar memories
            results = self.collections[collection].query(
                query_texts=[text],
                n_results=4  # top 4 because one will be the memory itself
            )

            if not results["ids"] or not results["ids"][0]:
                return

            linked = 0
            for rid in results["ids"][0]:
                if rid == memory_id:
                    continue  # skip self
                self.add_relationship(memory_id, rid, "similar_to")
                linked += 1
                if linked >= 3:
                    break
        except Exception:
            pass  # Don't let linking failures break store()

    def recall(self, query, collections=None, n=5, min_importance=None, include_related=False, since_days=None):
        """
        Recall memories matching a query
        
        Args:
            query: Search query
            collections: List of collections to search (None = all)
            n: Max results per collection
            min_importance: Minimum importance filter (None = no filter)
            include_related: Include graph-related memories
            since_days: Only memories from last N days (None = all time)
        
        Returns:
            List of matching documents
        """
        if collections is None:
            collections = ALL_COLLECTIONS
        
        all_results = []
        cutoff_date = None
        if since_days:
            from datetime import timedelta
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        
        for col_name in collections:
            if col_name not in self.collections:
                continue
            
            col = self.collections[col_name]
            results = col.query(query_texts=[query], n_results=n)
            
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    
                    # Filter by importance if specified
                    if min_importance is not None:
                        if meta.get("importance", 0) < min_importance:
                            continue
                    
                    # Filter by date if specified
                    if cutoff_date and meta.get("created_at"):
                        if meta["created_at"] < cutoff_date:
                            continue
                    
                    result_item = {
                        "document": doc,
                        "metadata": meta,
                        "collection": col_name,
                        "id": results["ids"][0][i],
                        "related": []
                    }
                    
                    # Include related memories via graph
                    if include_related:
                        related = self.get_related(results["ids"][0][i], depth=1)
                        result_item["related"] = related
                    
                    all_results.append(result_item)
        
        # Sort by importance (highest first)
        all_results.sort(key=lambda x: x["metadata"].get("importance", 0), reverse=True)
        
        return all_results[:n * len(collections)]
    
    def get(self, collection, n=100):
        """Get all memories from a collection"""
        if collection not in self.collections:
            return []
        
        col = self.collections[collection]
        results = col.get(limit=n)
        
        memories = []
        for i, doc in enumerate(results.get("documents", [])):
            memories.append({
                "document": doc,
                "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                "id": results["ids"][i]
            })
        
        return memories
    
    # === GOAL TRACKING ===
    
    def get_goals(self):
        """Get all tracked goals"""
        return self.get(GOALS)
    
    def set_goal(self, goal_name, progress, subtasks=None):
        """Set or update a goal"""
        goal_data = {
            "goal": goal_name,
            "progress": progress,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        if subtasks:
            goal_data["subtasks"] = json.dumps(subtasks)
        
        col = self.collections[GOALS]
        col.upsert(
            ids=[goal_name],
            documents=[f"{goal_name}: {progress}%"],
            metadatas=[goal_data]
        )
    
    # === CONTEXT MANAGEMENT ===
    
    def get_context(self):
        """Get current working context"""
        memories = self.get(CONTEXT, n=1)
        if memories:
            return memories[0]["document"]
        return "idle"
    
    def set_context(self, context):
        """Set current working context"""
        col = self.collections[CONTEXT]
        col.upsert(
            ids=["current"],
            documents=[context],
            metadatas=[{"updated": datetime.now(timezone.utc).isoformat()}]
        )
    
    # === GRAPH OPERATIONS ===
    
    def add_relationship(self, from_id, to_id, relationship_type):
        """Add a relationship between two memories"""
        edge = {
            "from": from_id,
            "to": to_id,
            "type": relationship_type,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Avoid duplicates
        if edge not in self.graph["edges"]:
            self.graph["edges"].append(edge)
            self._save_graph()
        
        return edge
    
    def get_related(self, memory_id, depth=1):
        """Get memories related to a given memory"""
        related = []
        visited = set()
        
        def traverse(node_id, current_depth):
            if current_depth > depth or node_id in visited:
                return
            visited.add(node_id)
            
            for edge in self.graph["edges"]:
                if edge["from"] == node_id:
                    related.append({
                        "id": edge["to"],
                        "relationship": edge["type"],
                        "depth": current_depth
                    })
                    traverse(edge["to"], current_depth + 1)
                elif edge["to"] == node_id:
                    related.append({
                        "id": edge["from"],
                        "relationship": f"inverse-{edge['type']}",
                        "depth": current_depth
                    })
                    traverse(edge["from"], current_depth + 1)
        
        traverse(memory_id, 1)
        return related
    
    # === TEMPORAL QUERIES ===
    
    def recall_recent(self, days=7, collections=None, n=20):
        """Get memories from the last N days"""
        return self.recall("", collections=collections, n=n, since_days=days)
    
    def recall_from_date(self, start_date, end_date=None, collections=None, n=20):
        """
        Get memories from a date range
        
        Args:
            start_date: ISO date string (e.g., "2026-02-01")
            end_date: ISO date string (optional, defaults to now)
            collections: Which collections to search
            n: Max results
        """
        from datetime import datetime
        
        if collections is None:
            collections = ALL_COLLECTIONS
        
        all_results = []
        
        for col_name in collections:
            if col_name not in self.collections:
                continue
            
            col = self.collections[col_name]
            results = col.get()
            
            for i, doc in enumerate(results.get("documents", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                created = meta.get("created_at", "")
                
                if created:
                    # Parse date and check range
                    try:
                        mem_date = created[:10]  # Get YYYY-MM-DD
                        if mem_date >= start_date:
                            if end_date is None or mem_date <= end_date:
                                all_results.append({
                                    "document": doc,
                                    "metadata": meta,
                                    "collection": col_name,
                                    "id": results["ids"][i]
                                })
                    except:
                        pass
        
        # Sort by date (newest first)
        all_results.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
        
        return all_results[:n]
    
    # === MEMORY DECAY & PRUNING ===
    
    def decay_importance(self, decay_rate=0.01, min_importance=0.1):
        """
        Decay importance of all memories over time.
        Memories accessed less recently decay faster.
        
        Args:
            decay_rate: How much to decay per day unused (default 1%)
            min_importance: Floor for importance (don't decay below this)
        
        Returns:
            Number of memories decayed
        """
        from datetime import timedelta
        
        decayed = 0
        now = datetime.now(timezone.utc)
        
        for col_name, col in self.collections.items():
            results = col.get()
            
            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                
                last_accessed = meta.get("last_accessed")
                if not last_accessed:
                    continue
                
                try:
                    last_dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                    days_unused = (now - last_dt).days
                    
                    if days_unused > 0:
                        current_importance = meta.get("importance", 0.5)
                        new_importance = current_importance * ((1 - decay_rate) ** days_unused)
                        new_importance = max(min_importance, new_importance)
                        
                        if new_importance < current_importance:
                            meta["importance"] = new_importance
                            col.upsert(
                                ids=[mem_id],
                                documents=[results["documents"][i]],
                                metadatas=[meta]
                            )
                            decayed += 1
                except:
                    pass
        
        return decayed
    
    def prune_low_importance(self, threshold=0.15, preserve_tags=None):
        """
        Remove memories below importance threshold.
        
        Args:
            threshold: Importance below which to delete (default 0.15)
            preserve_tags: Tags that prevent deletion (e.g., ["genesis", "critical"])
        
        Returns:
            Number of memories deleted
        """
        if preserve_tags is None:
            preserve_tags = ["genesis", "critical", "identity"]
        
        deleted = 0
        
        for col_name, col in self.collections.items():
            results = col.get()
            
            to_delete = []
            
            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                importance = meta.get("importance", 0.5)
                
                if importance < threshold:
                    # Check if has preserve tag
                    tags_json = meta.get("tags", "[]")
                    try:
                        tags = json.loads(tags_json) if isinstance(tags_json, str) else tags_json
                    except:
                        tags = []
                    
                    if not any(t in tags for t in preserve_tags):
                        to_delete.append(mem_id)
            
            if to_delete:
                col.delete(ids=to_delete)
                deleted += len(to_delete)
        
        return deleted
    
    def get_stale_memories(self, days=30):
        """Get memories not accessed in N days"""
        from datetime import timedelta
        
        stale = []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        for col_name, col in self.collections.items():
            results = col.get()
            
            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                last_accessed = meta.get("last_accessed", "")
                
                if last_accessed and last_accessed < cutoff:
                    stale.append({
                        "id": mem_id,
                        "document": results["documents"][i][:50],
                        "collection": col_name,
                        "last_accessed": last_accessed[:10]
                    })
        
        return stale
    
    def optimize(self):
        """
        Run brain optimization: decay, prune, clean.
        Call periodically (e.g., once per day).
        
        Returns:
            Dict with optimization stats
        """
        decayed = self.decay_importance()
        pruned = self.prune_low_importance()
        stale = self.get_stale_memories(days=60)
        
        return {
            "decayed": decayed,
            "pruned": pruned,
            "stale_count": len(stale),
            "stats": self.stats()
        }
    
    # === STATISTICS ===
    
    def stats(self):
        """Get brain statistics"""
        stats = {
            "collections": {},
            "total_memories": 0,
            "graph_nodes": len(self.graph["nodes"]),
            "graph_edges": len(self.graph["edges"])
        }
        
        for name, col in self.collections.items():
            count = col.count()
            stats["collections"][name] = count
            stats["total_memories"] += count
        
        return stats
    
    def health_check(self):
        """Verify brain is working"""
        try:
            # Test store
            test_id = self.store("health check test", collection=MEMORIES, importance=0.1)
            
            # Test recall
            results = self.recall("health check test", n=1)
            
            # Test stats
            s = self.stats()
            
            return {
                "status": "healthy",
                "total_memories": s["total_memories"],
                "collections": len(s["collections"]),
                "graph_edges": s["graph_edges"]
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


class LocalBrain(ClarvisBrain):
    """
    Brain with local embeddings (ONNX MiniLM).
    No cloud dependency - fully self-contained.
    
    Usage:
        from brain import LocalBrain
        brain = LocalBrain()
        brain.store("memory")
        brain.recall("query")
    """
    
    def __init__(self):
        super().__init__(use_local_embeddings=True)
    
    def migrate_from_cloud(self, source_path=None):
        """
        Migrate memories from cloud-based brain to local.
        
        Args:
            source_path: Path to cloud brain data (default: DATA_DIR)
        
        Returns:
            Number of memories migrated
        """
        import shutil
        
        if source_path is None:
            source_path = DATA_DIR
        
        migrated = 0
        
        # Connect to source
        source_client = chromadb.PersistentClient(path=source_path)
        
        for col_name in ALL_COLLECTIONS:
            try:
                source_col = source_client.get_collection(col_name)
                results = source_col.get()
                
                if results["ids"]:
                    # Batch insert to local
                    target_col = self.collections[col_name]
                    target_col.add(
                        ids=results["ids"],
                        documents=results["documents"],
                        metadatas=results.get("metadatas")
                    )
                    migrated += len(results["ids"])
                    print(f"Migrated {col_name}: {len(results['ids'])} memories")
            except Exception as e:
                print(f"Skipped {col_name}: {e}")
        
        return migrated
    
    def get_embedding_info(self):
        """Get info about the embedding model"""
        return {
            "type": "ONNXMiniLM_L6_V2",
            "dimension": 384,
            "cloud_dependency": False,
            "model": "all-MiniLM-L6-v2 (local)",
            "performance": "~10ms per query (CPU)"
        }


# Singleton instance
_brain = None
_local_brain = None

def get_brain():
    """Get the brain singleton (cloud embeddings)"""
    global _brain
    if _brain is None:
        _brain = ClarvisBrain()
    return _brain

def get_local_brain():
    """Get local brain singleton (no cloud dependency)"""
    global _local_brain
    if _local_brain is None:
        _local_brain = LocalBrain()
    return _local_brain

# Convenience exports
brain = get_brain()
local_brain = None  # Initialize on demand

# Legacy compatibility - these match old API
store_important = lambda text, collection=None, importance=0.7, source="conversation", tags=None: brain.store(text, collection or MEMORIES, importance, tags, source)
recall = lambda query, n=5: [r["document"] for r in brain.recall(query, n=n)]

# Re-export from auto_capture for single-import convenience
def remember(text, importance=0.9, category=None):
    """Quick remember - high importance store"""
    from auto_capture import remember as _remember
    return _remember(text, importance, category)

def capture(text):
    """Auto-capture - assess importance and store if relevant"""
    from auto_capture import process
    return process(text)


# ClarvisDB-native search (replaces OpenClaw memory_search)
def search(query, n=5, min_importance=None, collections=None):
    """
    Search ClarvisDB - use this instead of OpenClaw's memory_search.
    
    This queries YOUR brain, not Google Gemini.
    
    Args:
        query: What to search for
        n: Max results
        min_importance: Filter by importance (0-1)
        collections: List of collections to search
    
    Returns:
        List of matching memories
    """
    return brain.recall(query, n=n, min_importance=min_importance, collections=collections)


if __name__ == "__main__":
    # CLI interface
    import sys
    
    b = get_brain()
    
    if len(sys.argv) < 2:
        print("Usage: brain.py <command> [args]")
        print("Commands:")
        print("  stats              - Show brain statistics")
        print("  health             - Run health check")
        print("  recall <query>     - Search memories")
        print("  recent [days]      - Recent memories (default 7 days)")
        print("  store <text>       - Store a memory")
        print("  optimize           - Run decay and prune")
        print("  stale              - Show stale memories")
        print("  context            - Show current context")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        print(json.dumps(b.stats(), indent=2))
    elif cmd == "health":
        print(json.dumps(b.health_check(), indent=2))
    elif cmd == "recall" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = b.recall(query, include_related=True)
        for r in results:
            print(f"[{r['collection']}] {r['document'][:80]}...")
            if r.get('related'):
                print(f"  └─ Related: {len(r['related'])} memories")
    elif cmd == "recent":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        results = b.recall_recent(days=days)
        print(f"Memories from last {days} days:")
        for r in results:
            print(f"  [{r['collection']}] {r['document'][:60]}...")
    elif cmd == "store" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        mem_id = b.store(text)
        print(f"Stored: {mem_id}")
    elif cmd == "optimize":
        result = b.optimize()
        print(f"Optimization complete:")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Stale: {result['stale_count']}")
        print(f"  Total memories: {result['stats']['total_memories']}")
    elif cmd == "stale":
        stale = b.get_stale_memories(days=30)
        print(f"Memories not accessed in 30 days: {len(stale)}")
        for s in stale[:10]:
            print(f"  {s['last_accessed']} [{s['collection']}] {s['document']}...")
    elif cmd == "context":
        print(f"Current context: {b.get_context()}")
    else:
        print(f"Unknown command: {cmd}")
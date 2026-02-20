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
"""

import chromadb
import json
import os
from datetime import datetime, timezone

# Single database location
DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb"
os.makedirs(DATA_DIR, exist_ok=True)

# Graph file
GRAPH_FILE = os.path.join(DATA_DIR, "relationships.json")

# Collection names
IDENTITY = "clarvis-identity"
PREFERENCES = "clarvis-preferences"
LEARNINGS = "clarvis-learnings"
INFRASTRUCTURE = "clarvis-infrastructure"
GOALS = "clarvis-goals"
CONTEXT = "clarvis-context"
MEMORIES = "clarvis-memories"

ALL_COLLECTIONS = [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, CONTEXT, MEMORIES]


class ClarvisBrain:
    """Unified brain for Clarvis - single source of truth"""
    
    def __init__(self):
        self.client = chromadb.PersistentClient(path=DATA_DIR)
        self._init_collections()
        self._load_graph()
    
    def _init_collections(self):
        """Ensure all collections exist"""
        self.collections = {}
        for name in ALL_COLLECTIONS:
            self.collections[name] = self.client.get_or_create_collection(name)
    
    def _load_graph(self):
        """Load relationship graph"""
        if os.path.exists(GRAPH_FILE):
            with open(GRAPH_FILE, 'r') as f:
                self.graph = json.load(f)
        else:
            self.graph = {"nodes": {}, "edges": []}
    
    def _save_graph(self):
        """Save relationship graph"""
        with open(GRAPH_FILE, 'w') as f:
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
        
        return memory_id
    
    def recall(self, query, collections=None, n=5, min_importance=None):
        """
        Recall memories matching a query
        
        Args:
            query: Search query
            collections: List of collections to search (None = all)
            n: Max results per collection
            min_importance: Minimum importance filter (None = no filter)
        
        Returns:
            List of matching documents
        """
        if collections is None:
            collections = ALL_COLLECTIONS
        
        all_results = []
        
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
                    
                    all_results.append({
                        "document": doc,
                        "metadata": meta,
                        "collection": col_name,
                        "id": results["ids"][0][i]
                    })
        
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


# Singleton instance
_brain = None

def get_brain():
    """Get the brain singleton"""
    global _brain
    if _brain is None:
        _brain = ClarvisBrain()
    return _brain

# Convenience exports
brain = get_brain()

# Legacy compatibility - these match old API
store_important = lambda text, collection=None, importance=0.7, source="conversation", tags=None: brain.store(text, collection or MEMORIES, importance, tags, source)
recall = lambda query, n=5: [r["document"] for r in brain.recall(query, n=n)]


if __name__ == "__main__":
    # CLI interface
    import sys
    
    b = get_brain()
    
    if len(sys.argv) < 2:
        print("Usage: brain.py <command> [args]")
        print("Commands: stats, health, recall <query>, store <text>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        print(json.dumps(b.stats(), indent=2))
    elif cmd == "health":
        print(json.dumps(b.health_check(), indent=2))
    elif cmd == "recall" and len(sys.argv) > 2:
        results = b.recall(" ".join(sys.argv[2:]))
        for r in results:
            print(f"[{r['collection']}] {r['document'][:80]}...")
    elif cmd == "store" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        mem_id = b.store(text)
        print(f"Stored: {mem_id}")
    else:
        print(f"Unknown command: {cmd}")
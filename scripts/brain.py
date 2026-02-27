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
import time
import fcntl
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
PROCEDURES = "clarvis-procedures"
AUTONOMOUS_LEARNING = "autonomous-learning"
EPISODES = "clarvis-episodes"

ALL_COLLECTIONS = [IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS, CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES]
# Fast defaults - includes identity/procedures (needed for accurate recall)
DEFAULT_COLLECTIONS = [IDENTITY, LEARNINGS, MEMORIES, GOALS, CONTEXT, PREFERENCES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES]

# === QUERY ROUTING ===
# Route queries to the most relevant collections for better hit rates.
import re as _re
_ROUTE_PATTERNS = [
    (_re.compile(r'\b(goals?|objectives?|targets?|milestones?|progress)\b', _re.I), [GOALS]),
    (_re.compile(r'\b(procedur\w*|how to|steps? for|recipe|workflow)\b', _re.I), [PROCEDURES, LEARNINGS]),
    (_re.compile(r'\b(who am i|my identity|my name|about me|self model|who created|creator|capabilit\w+|what am i)\b', _re.I), [IDENTITY, MEMORIES]),
    (_re.compile(r'\b(cron|script|server|system|infra|config)\b', _re.I), [INFRASTRUCTURE, LEARNINGS]),
    (_re.compile(r'\b(current|right now|working on|context|today|last|recent|previous|heartbeat)\b', _re.I), [CONTEXT, MEMORIES]),
    (_re.compile(r'\b(learned|lesson|insight|pattern|discovery|found that)\b', _re.I), [LEARNINGS]),
    (_re.compile(r'\b(prefer|like|style|format|convention)\b', _re.I), [PREFERENCES]),
    (_re.compile(r'\b(episode|session|conversation|happened|did|bug|fixed|error)\b', _re.I), [EPISODES, MEMORIES]),
]

def route_query(query: str) -> list:
    """Route query to relevant collections. Returns None if no specific route matches."""
    matched = set()
    for pattern, collections in _ROUTE_PATTERNS:
        if pattern.search(query):
            matched.update(collections)
    if matched:
        # Always include LEARNINGS and MEMORIES as broad fallback
        matched.add(LEARNINGS)
        matched.add(MEMORIES)
        return list(matched)
    return None  # No routing — use default


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

        # Caches with TTL
        self._stats_cache = None
        self._stats_cache_time = 0
        self._stats_cache_ttl = 30  # seconds
        self._collection_cache = {}  # col_name -> (time, results)
        self._collection_cache_ttl = 60  # seconds
    
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
        """Load relationship graph with corruption recovery + file locking"""
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    self.graph = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return
            except (json.JSONDecodeError, IOError, OSError):
                # Rename corrupt file and attempt partial recovery
                broken_path = self.graph_file + ".broken"
                os.rename(self.graph_file, broken_path)
                try:
                    with open(broken_path, 'r') as f:
                        raw = f.read()
                    last_brace = raw.rfind('},')
                    if last_brace > 0:
                        valid = raw[:last_brace+1] + '\n  ]\n}'
                        self.graph = json.loads(valid)
                        self._save_graph()  # persist the recovered version
                        return
                except Exception:
                    pass
        self.graph = {"nodes": {}, "edges": []}

    def _save_graph(self):
        """Save relationship graph atomically with file locking to prevent race conditions"""
        # Read current file to detect concurrent modifications
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    on_disk = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # Merge: add edges from on-disk that we don't have
                on_disk_edges = {(e['from'], e['to'], e.get('type')) for e in on_disk.get('edges', [])}
                our_edges = {(e['from'], e['to'], e.get('type')) for e in self.graph.get('edges', [])}
                merged_edges = on_disk_edges | our_edges
                
                if len(merged_edges) > len(our_edges):
                    # Reconstruct edge list with merged set
                    edge_map = {(e['from'], e['to'], e.get('type')): e for e in self.graph.get('edges', [])}
                    for e in on_disk.get('edges', []):
                        key = (e['from'], e['to'], e.get('type'))
                        if key not in edge_map:
                            edge_map[key] = e
                    self.graph['edges'] = list(edge_map.values())
            except (json.JSONDecodeError, IOError, OSError):
                pass  # Proceed with our version if read fails
        
        # Atomic write with exclusive lock
        tmp_path = self.graph_file + ".tmp"
        with open(tmp_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
            json.dump(self.graph, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, self.graph_file)
    
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

        # Invalidate caches for this collection
        self._invalidate_cache(collection)

        # Auto-link to similar memories
        self.auto_link(memory_id, text, collection)

        return memory_id
    
    def auto_link(self, memory_id, text, collection):
        """
        Automatically link a memory to similar memories, both within
        the same collection and across other collections.

        Args:
            memory_id: ID of the newly stored memory
            text: The memory text (used as the search query)
            collection: The collection the memory was stored in
        """
        try:
            linked = 0
            # 1) Same-collection links (top 3)
            results = self.collections[collection].query(
                query_texts=[text],
                n_results=4  # top 4 because one will be the memory itself
            )
            if results["ids"] and results["ids"][0]:
                for rid in results["ids"][0]:
                    if rid == memory_id:
                        continue
                    self.add_relationship(memory_id, rid, "similar_to",
                                          source_collection=collection, target_collection=collection)
                    linked += 1
                    if linked >= 3:
                        break

            # 2) Cross-collection links (best match from each other collection, up to 4)
            cross_linked = 0
            for other_col in DEFAULT_COLLECTIONS:
                if other_col == collection or other_col not in self.collections:
                    continue
                try:
                    xresults = self.collections[other_col].query(
                        query_texts=[text],
                        n_results=1
                    )
                    if xresults["ids"] and xresults["ids"][0] and xresults["distances"] and xresults["distances"][0]:
                        dist = xresults["distances"][0][0]
                        # Link if semantically related (distance < 1.5)
                        if dist < 1.5:
                            self.add_relationship(memory_id, xresults["ids"][0][0], "cross_collection",
                                                  source_collection=collection, target_collection=other_col)
                            cross_linked += 1
                            if cross_linked >= 4:
                                break
                except Exception:
                    continue
        except Exception:
            pass  # Don't let linking failures break store()

    def recall(self, query, collections=None, n=5, min_importance=None, include_related=False, since_days=None, attention_boost=False, caller=None):
        """
        Recall memories matching a query

        Args:
            query: Search query
            collections: List of collections to search (None = all)
            n: Max results per collection
            min_importance: Minimum importance filter (None = no filter)
            include_related: Include graph-related memories
            since_days: Only memories from last N days (None = all time)
            attention_boost: Boost results that match current spotlight focus
            caller: Who is calling recall (for retrieval quality tracking)

        Returns:
            List of matching documents
        """
        if collections is None:
            # Try query routing first — directs to relevant collections
            routed = route_query(query)
            collections = routed if routed else DEFAULT_COLLECTIONS
        
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
                    
                    # ChromaDB distance (lower = more similar)
                    distance = results["distances"][0][i] if results.get("distances") else None

                    result_item = {
                        "document": doc,
                        "metadata": meta,
                        "collection": col_name,
                        "id": results["ids"][0][i],
                        "distance": distance,
                        "related": []
                    }
                    
                    # Include related memories via graph
                    if include_related:
                        related = self.get_related(results["ids"][0][i], depth=1)
                        result_item["related"] = related
                    
                    all_results.append(result_item)
        
        # Attention boost: items matching spotlight focus get a salience bump
        if attention_boost:
            try:
                from attention import attention as attn
                spotlight_words = set()
                for s_item in attn.focus():
                    spotlight_words.update(s_item["content"].lower().split())
                for result in all_results:
                    doc_words = set(result["document"].lower().split())
                    overlap = len(spotlight_words & doc_words)
                    if overlap > 0:
                        boost = min(0.3, overlap * 0.05)
                        result["metadata"]["_attention_boost"] = boost
            except Exception:
                pass  # Don't let attention failures break recall

        # Sort by combined relevance score:
        # Primary signal: semantic distance (lower = more relevant)
        # Secondary signal: importance + attention boost
        # Formula: relevance = (1 / (1 + distance)) * 0.85 + importance * 0.15
        # Distance-heavy weighting prevents importance from overriding semantic match
        def sort_key(x):
            distance = x.get("distance")
            if distance is not None:
                # Normalize distance to 0-1 relevance (inverse)
                semantic_relevance = 1.0 / (1.0 + distance)
            else:
                semantic_relevance = 0.5  # Unknown distance = neutral
            importance = x["metadata"].get("importance", 0.5)
            boost = x["metadata"].get("_attention_boost", 0)
            return semantic_relevance * 0.85 + (importance + boost) * 0.15
        all_results.sort(key=sort_key, reverse=True)

        final_results = all_results[:n * len(collections)]

        # Log retrieval event for quality tracking (non-blocking, fail-safe)
        if caller and query:
            try:
                from retrieval_quality import tracker
                tracker.on_recall(query, final_results, caller=caller)
            except Exception:
                pass  # Never let tracking break recall

        # Hebbian memory evolution: strengthen retrieved memories (non-blocking)
        if final_results and query:
            try:
                from hebbian_memory import hebbian
                hebbian.on_recall(query, final_results, caller=caller)
            except Exception:
                pass  # Never let Hebbian tracking break recall

        # Synaptic memory: memristor-inspired STDP weight updates (non-blocking)
        if final_results and query:
            try:
                from synaptic_memory import synaptic
                synaptic.on_recall(query, final_results, caller=caller)

                # Spreading activation: use top-5 result IDs to find
                # synaptically connected memories not already in results
                top_ids = [r["id"] for r in final_results[:5] if r.get("id")]
                if top_ids:
                    spread_results = synaptic.spread(top_ids, n=3, min_weight=0.15)
                    if spread_results:
                        existing_ids = {r["id"] for r in final_results}
                        for spread_id, activation in spread_results:
                            if spread_id in existing_ids:
                                continue
                            # Retrieve the actual memory from ChromaDB
                            for col_name in (collections or DEFAULT_COLLECTIONS):
                                if col_name not in self.collections:
                                    continue
                                try:
                                    col = self.collections[col_name]
                                    got = col.get(ids=[spread_id])
                                    if got["ids"] and got["documents"] and got["documents"][0]:
                                        meta = got["metadatas"][0] if got.get("metadatas") else {}
                                        final_results.append({
                                            "document": got["documents"][0],
                                            "metadata": meta,
                                            "collection": col_name,
                                            "id": spread_id,
                                            "distance": None,
                                            "related": [],
                                            "spread_activated": True,
                                            "spread_weight": activation,
                                        })
                                        existing_ids.add(spread_id)
                                        break
                                except Exception:
                                    continue
            except Exception:
                pass  # Never let synaptic tracking break recall

        return final_results
    
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

    def get_goals(self, include_archived=False):
        """Get all tracked goals with normalized name/progress fields.

        Every goal is returned with metadata containing 'goal' (str) and
        'progress' (int), regardless of how it was originally stored.

        Args:
            include_archived: If False (default), excludes goals with
                metadata 'archived': 'true'. Archived = 0% for >7 days.

        Returns list of dicts with 'document', 'metadata', 'id'.
        """
        raw = self.get(GOALS)
        for g in raw:
            meta = g.get("metadata", {})
            if "goal" in meta and "progress" in meta:
                continue
            doc = g.get("document", "")
            goal_id = g.get("id", "")
            if ":" in doc and "%" in doc:
                name = doc.split(":")[0].strip()
                try:
                    progress = int(doc.split(":")[1].split("%")[0].strip())
                except (ValueError, IndexError):
                    progress = 0
            else:
                name = goal_id.replace("goal-", "").replace("-", " ").replace("_", " ").title()
                progress = 0
            meta["goal"] = name
            meta["progress"] = progress

        if not include_archived:
            raw = [g for g in raw if str(g.get("metadata", {}).get("archived", "")).lower() != "true"]
        return raw

    def migrate_goals(self):
        """One-time migration: convert store()-based goals to set_goal() format.

        Goals stored via store() lack structured 'goal'/'progress' metadata.
        This re-saves them via set_goal() so progress can be tracked, then
        deletes the old unstructured entries.

        Returns number of goals migrated.
        """
        col = self.collections[GOALS]
        results = col.get()
        migrated = 0
        to_delete = []

        for i, mem_id in enumerate(results.get("ids", [])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            if "goal" in meta and "progress" in meta:
                continue  # Already structured

            doc = results["documents"][i] if results.get("documents") else ""
            # Derive a clean name from the id
            name = mem_id.replace("goal-", "").replace("-", " ").replace("_", " ").title()

            self.set_goal(name, 0, subtasks={"description": doc[:200]})
            to_delete.append(mem_id)
            migrated += 1

        if to_delete:
            col.delete(ids=to_delete)

        return migrated

    def set_goal(self, goal_name, progress, subtasks=None):
        """Set or update a goal. Rejects garbage goals (too short, bridge artifacts).

        Guardrails:
        - Rejects goals shorter than 10 chars or matching bridge patterns
        - Max 25 active goals — new goals rejected if cap reached (updates still allowed)
        - Goals at 0% for >7 days auto-archived on next get_goals() call
        """
        # Validate: reject garbage goals
        if not goal_name or len(goal_name.strip()) < 10:
            return
        reject_patterns = ["bridge", "sbridge", "BRIDGE", "Sbridge", "Connection between"]
        if any(p.lower() in goal_name.lower() for p in reject_patterns):
            return

        col = self.collections[GOALS]

        # Check if this is an update (goal already exists) vs new goal
        existing = col.get(ids=[goal_name])
        is_update = bool(existing and existing.get("ids"))

        # Max goal cap: reject NEW goals if over 25 active (non-archived)
        if not is_update:
            all_goals = col.get()
            active_count = 0
            for i, gid in enumerate(all_goals.get("ids", [])):
                meta = all_goals["metadatas"][i] if all_goals.get("metadatas") else {}
                if str(meta.get("archived", "")).lower() != "true":
                    active_count += 1
            if active_count >= 25:
                return  # Cap reached, reject new goal

        goal_data = {
            "goal": goal_name,
            "progress": progress,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        if subtasks:
            goal_data["subtasks"] = json.dumps(subtasks)

        col.upsert(
            ids=[goal_name],
            documents=[f"{goal_name}: {progress}%"],
            metadatas=[goal_data]
        )

    def archive_stale_goals(self, max_age_days=7):
        """Archive goals stuck at 0% for more than max_age_days.

        Sets metadata 'archived': 'true' so get_goals() excludes them.
        Returns number of goals archived.
        """
        col = self.collections[GOALS]
        all_goals = col.get()
        now = datetime.now(timezone.utc)
        archived = 0

        for i, gid in enumerate(all_goals.get("ids", [])):
            meta = all_goals["metadatas"][i] if all_goals.get("metadatas") else {}
            if str(meta.get("archived", "")).lower() == "true":
                continue
            progress = meta.get("progress", 0)
            if isinstance(progress, str):
                try:
                    progress = int(progress)
                except ValueError:
                    progress = 0
            if progress > 0:
                continue
            updated = meta.get("updated", "")
            if not updated:
                continue
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_days = (now - updated_dt).days
                if age_days >= max_age_days:
                    meta["archived"] = "true"
                    col.update(ids=[gid], metadatas=[meta])
                    archived += 1
            except (ValueError, TypeError):
                continue

        return archived
    
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
    
    def add_relationship(self, from_id, to_id, relationship_type,
                         source_collection=None, target_collection=None):
        """Add a relationship between two memories.

        Args:
            from_id: Source memory ID
            to_id: Target memory ID
            relationship_type: Edge type (e.g. 'similar_to', 'cross_collection')
            source_collection: Collection the from_id belongs to (optional)
            target_collection: Collection the to_id belongs to (optional)
        """
        # Ensure both nodes are registered in the graph
        if from_id not in self.graph["nodes"]:
            self.graph["nodes"][from_id] = {
                "collection": source_collection or self._infer_collection(from_id),
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
        if to_id not in self.graph["nodes"]:
            self.graph["nodes"][to_id] = {
                "collection": target_collection or self._infer_collection(to_id),
                "added_at": datetime.now(timezone.utc).isoformat(),
            }

        edge = {
            "from": from_id,
            "to": to_id,
            "type": relationship_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if source_collection:
            edge["source_collection"] = source_collection
        if target_collection:
            edge["target_collection"] = target_collection

        # Avoid duplicates (check from/to/type only, ignore timestamps)
        for existing in self.graph["edges"]:
            if (existing["from"] == from_id and
                    existing["to"] == to_id and
                    existing["type"] == relationship_type):
                return existing

        self.graph["edges"].append(edge)
        self._save_graph()

        return edge

    def _infer_collection(self, memory_id):
        """Infer which collection a memory ID belongs to."""
        for col_name, col in self.collections.items():
            if memory_id.startswith(col_name):
                return col_name
        # Try prefix matching
        prefix = memory_id.split("_")[0].split("-")[0]
        prefix_map = {
            "proc": PROCEDURES,
            "bridge": MEMORIES,
            "sbridge": MEMORIES,
            "goal": GOALS,
            "mem": MEMORIES,
        }
        return prefix_map.get(prefix, "unknown")
    
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
    
    def prune_low_importance(self, threshold=0.12, preserve_tags=None):
        """
        Remove memories below importance threshold.
        Conservative: only prune genuinely low-value entries.

        Args:
            threshold: Importance below which to delete (default 0.12, lowered from 0.15)
            preserve_tags: Tags that prevent deletion

        Returns:
            Number of memories deleted
        """
        if preserve_tags is None:
            preserve_tags = ["genesis", "critical", "identity", "learning", "insight"]

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
                # Log what we're pruning for auditability
                import sys
                for mid in to_delete:
                    idx = results["ids"].index(mid)
                    doc_preview = (results["documents"][idx] or "")[:80]
                    meta_i = results["metadatas"][idx] if results.get("metadatas") else {}
                    print(f"PRUNE: {col_name}/{mid} imp={meta_i.get('importance','?')} '{doc_preview}'", file=sys.stderr)
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
    
    def optimize(self, full=False):
        """
        Run brain optimization: decay, prune, clean.
        Call periodically (e.g., once per day).

        Args:
            full: If True, also run dedup, noise prune, and stale archive
                  via memory_consolidation.py.

        Returns:
            Dict with optimization stats
        """
        decayed = self.decay_importance()
        pruned = self.prune_low_importance()
        stale = self.get_stale_memories(days=60)

        result = {
            "decayed": decayed,
            "pruned": pruned,
            "stale_count": len(stale),
        }

        if full:
            try:
                from memory_consolidation import deduplicate, prune_noise, archive_stale
                dedup_result = deduplicate(dry_run=False)
                noise_result = prune_noise(dry_run=False)
                archive_result = archive_stale(dry_run=False)
                result["duplicates_removed"] = dedup_result.get("duplicates_removed", 0)
                result["noise_pruned"] = noise_result.get("pruned", 0)
                result["archived"] = archive_result.get("archived", 0)
            except Exception as e:
                result["consolidation_error"] = str(e)

        result["stats"] = self.stats()
        return result

    def backfill_graph_nodes(self):
        """
        Register all nodes referenced by existing edges but missing from the nodes dict.
        Fixes the orphan-edge problem where edges reference IDs not in graph["nodes"].

        Returns:
            int: Number of nodes backfilled
        """
        backfilled = 0
        for edge in self.graph.get("edges", []):
            for key in ("from", "to"):
                node_id = edge.get(key)
                if node_id and node_id not in self.graph["nodes"]:
                    collection = edge.get(f"{'source' if key == 'from' else 'target'}_collection")
                    self.graph["nodes"][node_id] = {
                        "collection": collection or self._infer_collection(node_id),
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "backfilled": True,
                    }
                    backfilled += 1
        if backfilled > 0:
            self._save_graph()
        return backfilled
    
    # === BULK CROSS-COLLECTION LINKING ===

    def bulk_cross_link(self, max_distance=1.5, max_links_per_memory=3, verbose=False):
        """
        Scan all memories and create cross-collection edges where missing.

        This retroactively builds cross-collection connectivity for memories
        that were stored before cross-linking was added or with stricter thresholds.

        Args:
            max_distance: Maximum embedding distance to create a link (default 1.5)
            max_links_per_memory: Max new cross-collection links per memory
            verbose: Print progress details

        Returns:
            Dict with stats: new_edges, memories_scanned, collections_linked
        """
        new_edges = 0
        memories_scanned = 0

        # Build set of existing cross-collection edges for dedup
        existing_pairs = set()
        for e in self.graph.get("edges", []):
            if e.get("type") == "cross_collection":
                existing_pairs.add((e["from"], e["to"]))
                existing_pairs.add((e["to"], e["from"]))

        for col_name, col in self.collections.items():
            results = col.get()
            ids = results.get("ids", [])
            docs = results.get("documents", [])

            for idx, (mem_id, doc) in enumerate(zip(ids, docs)):
                if not doc or len(doc) < 10:
                    continue

                memories_scanned += 1
                links_added = 0

                for other_col_name, other_col in self.collections.items():
                    if other_col_name == col_name:
                        continue
                    if other_col.count() == 0:
                        continue

                    try:
                        xresults = other_col.query(
                            query_texts=[doc],
                            n_results=1
                        )
                        if (xresults["ids"] and xresults["ids"][0] and
                            xresults["distances"] and xresults["distances"][0]):
                            target_id = xresults["ids"][0][0]
                            dist = xresults["distances"][0][0]

                            if dist < max_distance and (mem_id, target_id) not in existing_pairs:
                                self.add_relationship(mem_id, target_id, "cross_collection",
                                                      source_collection=col_name, target_collection=other_col_name)
                                existing_pairs.add((mem_id, target_id))
                                existing_pairs.add((target_id, mem_id))
                                new_edges += 1
                                links_added += 1

                                if verbose:
                                    print(f"  {col_name} -> {other_col_name} (dist={dist:.3f})")

                                if links_added >= max_links_per_memory:
                                    break
                    except Exception:
                        continue

            if verbose and ids:
                print(f"  Scanned {col_name}: {len(ids)} memories")

        return {
            "new_edges": new_edges,
            "memories_scanned": memories_scanned,
            "total_edges": len(self.graph.get("edges", [])),
        }

    # === CACHE MANAGEMENT ===

    def _invalidate_cache(self, collection=None):
        """Invalidate caches after writes."""
        self._stats_cache = None
        self._stats_cache_time = 0
        if collection:
            self._collection_cache.pop(collection, None)
        else:
            self._collection_cache.clear()

    def get_all_cached(self, collection_name):
        """Get all memories from a collection, with TTL caching.

        Use this for read-heavy bulk operations (consolidation, stats, decay).
        The cache is invalidated on store() and expires after _collection_cache_ttl seconds.
        """
        now = time.monotonic()
        cached = self._collection_cache.get(collection_name)
        if cached and (now - cached[0]) < self._collection_cache_ttl:
            return cached[1]

        result = self.get(collection_name, n=10000)
        self._collection_cache[collection_name] = (now, result)
        return result

    # === STATISTICS ===

    def stats(self):
        """Get brain statistics (cached for 30s)"""
        now = time.monotonic()
        if self._stats_cache and (now - self._stats_cache_time) < self._stats_cache_ttl:
            return self._stats_cache

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

        self._stats_cache = stats
        self._stats_cache_time = now
        return stats
    
    def health(self):
        """Alias for health_check — verify brain is working."""
        return self.health_check()

    def health_check(self):
        """Verify brain is working"""
        try:
            # Test store
            self.store("health check test", collection=MEMORIES, importance=0.1)

            # Test recall
            self.recall("health check test", n=1)
            
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


class _LazyBrain:
    """Lazy proxy for ClarvisBrain — delays ChromaDB initialization until first access.

    This avoids the ~200ms startup cost when importing brain.py from scripts
    that may not need the brain at all (e.g., queue_writer, CLI tools).
    """

    def __getattr__(self, name):
        # On first attribute access, initialize the real brain and replace ourselves
        real = get_brain()
        # Replace module-level 'brain' so future accesses skip the proxy
        import brain as _module
        _module.brain = real
        return getattr(real, name)

    def __repr__(self):
        return "<LazyBrain (not yet initialized)>"


# Convenience exports — lazy so importing brain.py doesn't trigger ChromaDB init
brain = _LazyBrain()
local_brain = None  # Initialize on demand

# Legacy compatibility - these match old API
store_important = lambda text, collection=None, importance=0.7, source="conversation", tags=None: brain.store(text, collection or MEMORIES, importance, tags, source)
recall = lambda query, n=5: [r["document"] for r in brain.recall(query, n=n)]

# High-importance store — inlined from deprecated auto_capture.py
def remember(text, importance=0.9, category=None):
    """Manually remember something important. Auto-detects collection if category=None."""
    import re as _re
    if category is None:
        # Simple category detection from text content
        tl = text.lower()
        if _re.search(r'\b(prefer|hate|love|like|dislike|want|don\'?t want)\b', tl):
            category = PREFERENCES
        elif _re.search(r'\b(learned|lesson|mistake|fixed|solved|research|insight)\b', tl):
            category = LEARNINGS
        elif _re.search(r'\b(my name is|i am|creator|made me)\b', tl):
            category = IDENTITY
        elif _re.search(r'\b(server|host|port|database|api|config|running on)\b', tl):
            category = INFRASTRUCTURE
        elif _re.search(r'\b(goal|objective|target|deadline|milestone)\b', tl):
            category = GOALS
        else:
            category = MEMORIES
    # Extract tags
    tags = []
    tl = text.lower()
    if _re.search(r'\b(code|script|python|js|rust)\b', tl):
        tags.append("technical")
    if _re.search(r'\b(bug|fix|error|issue)\b', tl):
        tags.append("bug")
    if _re.search(r'\b(goal|objective)\b', tl):
        tags.append("goal")
    if _re.search(r'\b(research|paper|study|theory)\b', tl):
        tags.append("research")
    return brain.store(text, collection=category, importance=importance,
                       tags=tags or None, source="manual")

def capture(text):
    """Auto-capture — assess importance and store if relevant (>= 0.6)."""
    import re as _re
    tl = text.lower()
    score = 0.5
    # Boost for important patterns
    for pat in [r'\b(remember|important|critical|note that)\b',
                r'\b(prefer|hate|love|always|never)\b',
                r'\b(goal|objective|target|deadline)\b',
                r'\b(bug|fix|issue|problem|error)\b']:
        if _re.search(pat, tl):
            score += 0.1
    # Penalize low-value
    if _re.match(r'^(ok|okay|sure|yes|no|thanks|nice|cool|good|hmm|uh)\.?$', tl):
        score -= 0.2
    score = max(0.0, min(1.0, score))
    if score < 0.6:
        return {"captured": False, "reason": f"low importance ({score:.2f})", "importance": score}
    mem_id = remember(text, importance=score)
    return {"captured": True, "memory_id": mem_id, "importance": score}


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
        print("  health             - Full health report (stats + consolidation + graph)")
        print("  recall <query>     - Search memories")
        print("  recent [days]      - Recent memories (default 7 days)")
        print("  store <text>       - Store a memory")
        print("  optimize           - Run decay and prune")
        print("  optimize-full      - Run decay, prune, dedup, noise clean, archive")
        print("  backfill           - Backfill missing graph nodes from edges")
        print("  stale              - Show stale memories")
        print("  context            - Show current context")
        print("  crosslink          - Build cross-collection edges for all memories")
        print("  remember <text>    - High-importance store (--importance 0.8 --collection clarvis-learnings --tags t1,t2)")
        print("  ingest-research [file] - Ingest research markdown into brain (all files if no arg)")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        print(json.dumps(b.stats(), indent=2))
    elif cmd == "health":
        print("=== Clarvis Brain Health Report ===\n")

        # 1. Basic stats
        s = b.stats()
        print(f"Memories: {s['total_memories']} across {len(s['collections'])} collections")
        for name, count in s["collections"].items():
            print(f"  {name}: {count}")
        print(f"\nGraph: {s['graph_nodes']} nodes, {s['graph_edges']} edges")

        # 2. Check orphan ratio
        referenced_nodes = set()
        for e in b.graph.get("edges", []):
            referenced_nodes.add(e.get("from", ""))
            referenced_nodes.add(e.get("to", ""))
        referenced_nodes.discard("")
        orphan_count = len(referenced_nodes - set(b.graph.get("nodes", {}).keys()))
        if orphan_count > 0:
            print(f"  WARNING: {orphan_count} nodes referenced by edges but not in graph (run: brain.py backfill)")
        else:
            print("  Graph nodes: OK (all edge references resolved)")

        # 3. Consolidation preview
        try:
            from memory_consolidation import get_consolidation_stats
            cs = get_consolidation_stats()
            print("\nConsolidation status:")
            print(f"  Potential duplicates: {cs['potential_duplicates']}")
            print(f"  Potential noise: {cs['potential_noise']}")
            print(f"  Stale (archivable): {cs['stale_archivable']}")
            print(f"  Archived: {cs['archive_count']}")
            if cs['potential_duplicates'] > 0 or cs['potential_noise'] > 0:
                print("  Recommendation: run 'brain.py optimize-full' to clean")
        except Exception as e:
            print(f"\nConsolidation check failed: {e}")

        # 4. Stale check
        stale = b.get_stale_memories(days=30)
        print(f"\nStale memories (>30 days unaccessed): {len(stale)}")

        # 5. Basic store/recall test
        hc = b.health_check()
        print(f"\nStore/recall test: {hc['status']}")
        print("\n=== Health check complete ===")
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
        print("Optimization complete:")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Stale: {result['stale_count']}")
        print(f"  Total memories: {result['stats']['total_memories']}")
    elif cmd == "optimize-full":
        result = b.optimize(full=True)
        print("Full optimization complete:")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Stale: {result['stale_count']}")
        print(f"  Duplicates removed: {result.get('duplicates_removed', 'N/A')}")
        print(f"  Noise pruned: {result.get('noise_pruned', 'N/A')}")
        print(f"  Archived: {result.get('archived', 'N/A')}")
        if result.get('consolidation_error'):
            print(f"  WARNING: {result['consolidation_error']}")
        print(f"  Total memories: {result['stats']['total_memories']}")
    elif cmd == "backfill":
        count = b.backfill_graph_nodes()
        s = b.stats()
        print("Graph node backfill complete:")
        print(f"  Nodes backfilled: {count}")
        print(f"  Total nodes now: {s['graph_nodes']}")
        print(f"  Total edges: {s['graph_edges']}")
    elif cmd == "stale":
        stale = b.get_stale_memories(days=30)
        print(f"Memories not accessed in 30 days: {len(stale)}")
        for s in stale[:10]:
            print(f"  {s['last_accessed']} [{s['collection']}] {s['document']}...")
    elif cmd == "context":
        print(f"Current context: {b.get_context()}")
    elif cmd == "crosslink":
        result = b.bulk_cross_link(verbose=True)
        print("\nCross-linking complete:")
        print(f"  New edges: {result['new_edges']}")
        print(f"  Scanned: {result['memories_scanned']} memories")
        print(f"  Total edges: {result['total_edges']}")
    elif cmd == "remember" and len(sys.argv) > 2:
        # Parse flags: --importance FLOAT, --collection NAME, --tags tag1,tag2
        text_parts = []
        importance = 0.9
        collection = LEARNINGS
        tags = None
        source = "research"
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--importance" and i + 1 < len(sys.argv):
                try:
                    importance = float(sys.argv[i + 1])
                except ValueError:
                    pass
                i += 2
            elif sys.argv[i] == "--collection" and i + 1 < len(sys.argv):
                collection = sys.argv[i + 1]
                # Normalize: accept short names like "clarvis-learnings" or just "learnings"
                if not collection.startswith("clarvis-"):
                    collection = f"clarvis-{collection}"
                i += 2
            elif sys.argv[i] == "--tags" and i + 1 < len(sys.argv):
                tags = [t.strip() for t in sys.argv[i + 1].split(",")]
                i += 2
            elif sys.argv[i] == "--source" and i + 1 < len(sys.argv):
                source = sys.argv[i + 1]
                i += 2
            else:
                text_parts.append(sys.argv[i])
                i += 1
        text = " ".join(text_parts)
        if text:
            mem_id = b.store(text, collection=collection, importance=importance,
                             tags=tags, source=source)
            print(f"Remembered: {mem_id} (importance={importance}, collection={collection})")
        else:
            print("Error: no text provided")
            sys.exit(1)
    elif cmd == "ingest-research":
        # Ingest a research markdown file into brain with file-hash dedup
        import glob as glob_mod
        import hashlib
        research_dir = "/home/agent/.openclaw/workspace/memory/research"
        tracker_file = "/home/agent/.openclaw/workspace/data/research_ingested.json"
        force = "--force" in sys.argv

        # Load tracker
        tracker = {}
        if os.path.exists(tracker_file):
            try:
                with open(tracker_file) as tf:
                    tracker = json.load(tf)
            except Exception:
                tracker = {}

        if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
            files = [sys.argv[2]]
        else:
            files = sorted(glob_mod.glob(os.path.join(research_dir, "*.md")))

        if not files:
            print("No research files found")
            sys.exit(0)

        total_stored = 0
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"File not found: {filepath}")
                continue

            filename = os.path.basename(filepath)

            # Hash-based dedup
            with open(filepath, "rb") as hf:
                file_hash = hashlib.sha256(hf.read()).hexdigest()[:16]

            prev = tracker.get(filename, {})
            if not force and prev.get("hash") == file_hash:
                print(f"\nSkipping: {filename} (already ingested, hash match)")
                continue

            with open(filepath) as f:
                content = f.read()

            print(f"\nIngesting: {filename} (hash={file_hash})")

            # Split into sections and store each meaningful section
            sections = content.split("\n## ")
            title = sections[0].strip().split("\n")[0].replace("# ", "")
            memory_ids = []

            for section in sections[1:]:
                section_lines = section.strip().split("\n")
                section_title = section_lines[0].strip()
                section_body = "\n".join(section_lines[1:]).strip()

                if len(section_body) < 30:
                    continue

                memory_text = f"[RESEARCH: {title}] {section_title}: {section_body[:500]}"
                mem_id = b.store(
                    memory_text,
                    collection=LEARNINGS,
                    importance=0.8,
                    tags=["research", "paper", filename.replace(".md", "")],
                    source="research_ingest"
                )
                memory_ids.append(mem_id)
                total_stored += 1
                print(f"  Stored: {section_title[:60]} → {mem_id}")

            summary = f"[RESEARCH SUMMARY] {title} — ingested from {filename}, {len(memory_ids)} sections"
            mid = b.store(summary, collection=LEARNINGS, importance=0.85,
                    tags=["research", "summary"], source="research_ingest")
            memory_ids.append(mid)
            total_stored += 1

            # Record in tracker
            import time as _time
            tracker[filename] = {
                "hash": file_hash,
                "ingested_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                "memory_count": len(memory_ids),
                "memory_ids": memory_ids,
            }

        # Move ingested files to ingested/ subfolder
        import shutil as _shutil
        ingested_dir = os.path.join(research_dir, "ingested")
        os.makedirs(ingested_dir, exist_ok=True)
        for filepath in files:
            filename = os.path.basename(filepath)
            if filename in tracker and tracker[filename].get("memory_count", 0) > 0:
                dest = os.path.join(ingested_dir, filename)
                if os.path.exists(filepath) and not os.path.exists(dest):
                    _shutil.move(filepath, dest)
                    print(f"  Moved {filename} → ingested/")

        # Save tracker
        os.makedirs(os.path.dirname(tracker_file), exist_ok=True)
        with open(tracker_file, "w") as tf:
            json.dump(tracker, tf, indent=2)
        print(f"\nIngestion complete: {total_stored} memories stored (tracker updated)")
    else:
        print(f"Unknown command: {cmd}")
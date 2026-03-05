"""Clarvis Brain — unified memory system.

Split into:
  - constants.py: paths, collection names, query routing
  - graph.py: GraphMixin (relationships, traversal, backfill)
  - search.py: SearchMixin (recall, embedding cache, temporal queries)
  - store.py: StoreMixin (storage, goals, context, decay, stats, reconsolidation)

External modules (hebbian, actr, attention, retrieval_quality, memory_consolidation)
register hooks instead of being imported by brain — dependency inversion breaks the SCC.
"""

import re
import chromadb
import time

from .constants import (
    DATA_DIR, LOCAL_DATA_DIR, GRAPH_FILE, LOCAL_GRAPH_FILE,
    GRAPH_SQLITE_FILE, LOCAL_GRAPH_SQLITE_FILE, GRAPH_BACKEND,
    IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS,
    CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
    ALL_COLLECTIONS, DEFAULT_COLLECTIONS,
    route_query, get_local_embedding_function,
)
from .graph import GraphMixin
from .search import SearchMixin
from .store import StoreMixin


class ClarvisBrain(StoreMixin, GraphMixin, SearchMixin):
    """Unified brain for Clarvis — single source of truth.

    Hook registries (dependency inversion):
      _recall_scorers:   [fn(results)] — mutate results with _actr_score
      _recall_boosters:  [fn(results)] — mutate results with _attention_boost
      _recall_observers: [fn(query, results, *, caller, rate_limit_mono, last_mono)] — side effects
      _optimize_hooks:   [fn(dry_run=False)] — return dict with consolidation stats
    """

    def __init__(self, use_local_embeddings=False):
        self.use_local_embeddings = use_local_embeddings

        if use_local_embeddings:
            self.data_dir = LOCAL_DATA_DIR
            self.graph_file = LOCAL_GRAPH_FILE
            self.embedding_function = get_local_embedding_function()
        else:
            self.data_dir = DATA_DIR
            self.graph_file = GRAPH_FILE
            self.embedding_function = None

        self.client = chromadb.PersistentClient(path=self.data_dir)
        self._init_collections()
        self._load_graph()

        # Caches
        self._stats_cache = None
        self._stats_cache_time = 0
        self._stats_cache_ttl = 30
        self._collection_cache = {}
        self._collection_cache_ttl = 60
        self._embedding_cache = {}
        self._embedding_cache_ttl = 60

        # Result-level recall cache (TTL 30s, avoids repeated ChromaDB queries)
        self._recall_cache = {}
        self._recall_cache_ttl = 30

        # Reconsolidation state
        self._labile_memories = {}
        self._lability_window = 300

        # Hook registries (dependency inversion — external modules register here)
        self._recall_scorers = []
        self._recall_boosters = []
        self._recall_observers = []
        self._optimize_hooks = []

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

    # --- Hook registration API ---

    def register_recall_scorer(self, fn):
        """Register a scoring function: fn(results) — mutates items with _actr_score."""
        self._recall_scorers.append(fn)

    def register_recall_booster(self, fn):
        """Register an attention boost function: fn(results) — mutates items with _attention_boost."""
        self._recall_boosters.append(fn)

    def register_recall_observer(self, fn):
        """Register a recall observer: fn(query, results, *, caller, rate_limit_mono, last_mono)."""
        self._recall_observers.append(fn)

    def register_optimize_hook(self, fn):
        """Register an optimization hook: fn(dry_run=False) -> dict."""
        self._optimize_hooks.append(fn)


class LocalBrain(ClarvisBrain):
    """Brain with local embeddings (ONNX MiniLM). No cloud dependency."""

    def __init__(self):
        super().__init__(use_local_embeddings=True)

    def migrate_from_cloud(self, source_path=None):
        """Migrate memories from cloud-based brain to local."""
        if source_path is None:
            source_path = DATA_DIR

        migrated = 0
        source_client = chromadb.PersistentClient(path=source_path)

        for col_name in ALL_COLLECTIONS:
            try:
                source_col = source_client.get_collection(col_name)
                results = source_col.get()

                if results["ids"]:
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


# === Singletons ===

_brain = None
_local_brain = None


def get_brain():
    """Get the brain singleton (cloud embeddings)"""
    global _brain
    if _brain is None:
        _brain = ClarvisBrain()
        # Auto-register hooks (actr scorer, attention, hebbian, etc.)
        try:
            from .hooks import register_default_hooks
            register_default_hooks(_brain)
        except Exception:
            pass  # Hooks are optional — missing modules silently skipped
    return _brain


def get_local_brain():
    """Get local brain singleton (no cloud dependency)"""
    global _local_brain
    if _local_brain is None:
        _local_brain = LocalBrain()
    return _local_brain


class _LazyBrain:
    """Lazy proxy for ClarvisBrain — delays ChromaDB init until first access."""

    def __getattr__(self, name):
        real = get_brain()
        # Replace module-level 'brain' so future accesses skip the proxy
        import clarvis.brain as _module
        _module.brain = real
        return getattr(real, name)

    def __repr__(self):
        return "<LazyBrain (not yet initialized)>"


# Convenience exports — lazy singleton
brain = _LazyBrain()
local_brain = None

# Legacy compatibility
store_important = lambda text, collection=None, importance=0.7, source="conversation", tags=None: brain.store(text, collection or MEMORIES, importance, tags, source)
recall = lambda query, n=5: [r["document"] for r in brain.recall(query, n=n)]


def remember(text, importance=0.9, category=None):
    """Manually remember something important. Auto-detects collection if category=None."""
    if category is None:
        tl = text.lower()
        if re.search(r'\b(prefer|hate|love|like|dislike|want|don\'?t want)\b', tl):
            category = PREFERENCES
        elif re.search(r'\b(learned|lesson|mistake|fixed|solved|research|insight)\b', tl):
            category = LEARNINGS
        elif re.search(r'\b(my name is|i am|creator|made me)\b', tl):
            category = IDENTITY
        elif re.search(r'\b(server|host|port|database|api|config|running on)\b', tl):
            category = INFRASTRUCTURE
        elif re.search(r'\b(goal|objective|target|deadline|milestone)\b', tl):
            category = GOALS
        else:
            category = MEMORIES
    tags = []
    tl = text.lower()
    if re.search(r'\b(code|script|python|js|rust)\b', tl):
        tags.append("technical")
    if re.search(r'\b(bug|fix|error|issue)\b', tl):
        tags.append("bug")
    if re.search(r'\b(goal|objective)\b', tl):
        tags.append("goal")
    if re.search(r'\b(research|paper|study|theory)\b', tl):
        tags.append("research")
    return brain.store(text, collection=category, importance=importance,
                       tags=tags or None, source="manual")


def capture(text):
    """Auto-capture — assess importance and store if relevant (>= 0.6)."""
    tl = text.lower()
    score = 0.5
    for pat in [r'\b(remember|important|critical|note that)\b',
                r'\b(prefer|hate|love|always|never)\b',
                r'\b(goal|objective|target|deadline)\b',
                r'\b(bug|fix|issue|problem|error)\b']:
        if re.search(pat, tl):
            score += 0.1
    if re.match(r'^(ok|okay|sure|yes|no|thanks|nice|cool|good|hmm|uh)\.?$', tl):
        score -= 0.2
    score = max(0.0, min(1.0, score))
    if score < 0.6:
        return {"captured": False, "reason": f"low importance ({score:.2f})", "importance": score}
    mem_id = remember(text, importance=score)
    return {"captured": True, "memory_id": mem_id, "importance": score}


def search(query, n=5, min_importance=None, collections=None):
    """Search ClarvisDB — use this instead of OpenClaw's memory_search."""
    return brain.recall(query, n=n, min_importance=min_importance, collections=collections)


def global_search(query, level="C1", top_k=5):
    """GraphRAG-style global search over community summaries."""
    from clarvis.brain.graphrag import global_search as _gs
    return _gs(query, level=level, top_k=top_k)

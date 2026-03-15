"""Clarvis Brain — unified memory system.

Split into:
  - constants.py: paths, collection names, query routing
  - graph.py: GraphMixin (relationships, traversal, backfill)
  - search.py: SearchMixin (recall, embedding cache, temporal queries)
  - store.py: StoreMixin (storage, goals, context, decay, stats, reconsolidation)

External modules (hebbian, actr, attention, retrieval_quality, memory_consolidation)
register hooks instead of being imported by brain — dependency inversion breaks the SCC.
"""

import json as _json
import logging
import os
import re
import time
import uuid

from .constants import (
    DATA_DIR, LOCAL_DATA_DIR, GRAPH_FILE, LOCAL_GRAPH_FILE,
    GRAPH_SQLITE_FILE, LOCAL_GRAPH_SQLITE_FILE, GRAPH_BACKEND,
    IDENTITY, PREFERENCES, LEARNINGS, INFRASTRUCTURE, GOALS,
    CONTEXT, MEMORIES, PROCEDURES, AUTONOMOUS_LEARNING, EPISODES,
    ALL_COLLECTIONS, DEFAULT_COLLECTIONS,
    route_query, get_local_embedding_function,
)
from .factory import get_chroma_client, get_embedding_function
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
            self.graph_sqlite_file = LOCAL_GRAPH_SQLITE_FILE
            self.embedding_function = get_embedding_function(use_onnx=True)
        else:
            self.data_dir = DATA_DIR
            self.graph_file = GRAPH_FILE
            self.graph_sqlite_file = GRAPH_SQLITE_FILE
            self.embedding_function = None

        self.graph_backend = GRAPH_BACKEND

        self.client = get_chroma_client(self.data_dir)
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
        """Ensure all collections exist. Raises RuntimeError if any fail."""
        self.collections = {}
        failed = []
        for name in ALL_COLLECTIONS:
            try:
                if self.embedding_function:
                    self.collections[name] = self.client.get_or_create_collection(
                        name,
                        embedding_function=self.embedding_function
                    )
                else:
                    self.collections[name] = self.client.get_or_create_collection(name)
            except Exception as e:
                failed.append((name, str(e)))

        if failed:
            names = [f[0] for f in failed]
            raise RuntimeError(
                f"Brain init failed: {len(failed)}/{len(ALL_COLLECTIONS)} collections "
                f"could not be created: {names}. Errors: {failed}"
            )

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
        source_client = get_chroma_client(source_path)

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


_conflict_log = logging.getLogger("clarvis.brain.conflicts")

_CONFLICT_LOG_PATH = os.path.join(
    os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace"),
    "data", "conflict_log.jsonl",
)


def _log_conflict(conflict, action, new_text, category):
    """Append a conflict event to data/conflict_log.jsonl."""
    from datetime import datetime, timezone
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "category": category,
        "new_text": new_text[:200],
        "existing_id": conflict.get("id"),
        "existing_text": conflict.get("document", "")[:200],
        "distance": conflict.get("distance"),
        "contradiction_signal": conflict.get("contradiction_signal", []),
    }
    try:
        os.makedirs(os.path.dirname(_CONFLICT_LOG_PATH), exist_ok=True)
        with open(_CONFLICT_LOG_PATH, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception as exc:
        _conflict_log.debug("Failed to write conflict log: %s", exc)


def _detect_and_resolve_conflicts(text, category, importance):
    """Pre-storage conflict detection: find contradictions, apply temporal precedence.

    Returns (resolved_ids, conflict_count) — resolved_ids are the old memory IDs
    that were superseded via evolve_memory.
    """
    from .memory_evolution import find_contradictions, evolve_memory

    resolved_ids = []
    try:
        contradictions = find_contradictions(brain, text, category,
                                             threshold=1.0, top_n=5)
    except Exception:
        return [], 0

    for conflict in contradictions:
        old_id = conflict.get("id")
        old_col = conflict.get("collection", category)
        if not old_id:
            continue

        # Temporal precedence: newer always supersedes older
        try:
            evolve_result = evolve_memory(
                brain, old_id, old_col, text, reason="contradiction"
            )
            action = "evolved" if evolve_result.get("evolved") else "log_only"
        except Exception:
            action = "log_only"

        _log_conflict(conflict, action, text, category)
        if action == "evolved":
            resolved_ids.append(old_id)
            _conflict_log.info(
                "Conflict resolved: superseded %s in %s (d=%.3f, signals=%s)",
                old_id, old_col, conflict.get("distance", -1),
                conflict.get("contradiction_signal", []),
            )

    return resolved_ids, len(contradictions)


def _detect_category(text):
    """Auto-detect collection from text content."""
    tl = text.lower()
    if re.search(r'\b(prefer|hate|love|like|dislike|want|don\'?t want)\b', tl):
        return PREFERENCES
    if re.search(r'\b(learned|lesson|mistake|fixed|solved|research|insight)\b', tl):
        return LEARNINGS
    if re.search(r'\b(my name is|i am|creator|made me)\b', tl):
        return IDENTITY
    if re.search(r'\b(server|host|port|database|api|config|running on)\b', tl):
        return INFRASTRUCTURE
    if re.search(r'\b(goal|objective|target|deadline|milestone)\b', tl):
        return GOALS
    return MEMORIES


def _detect_tags(text):
    """Auto-detect tags from text content."""
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
    return tags


def remember(text, importance=0.9, category=None):
    """Manually remember something important. Auto-detects collection if category=None.

    Pre-storage conflict detection: queries existing memories for contradictions.
    If a highly similar memory exists with conflicting content, the old memory
    is superseded (temporal precedence) and a conflict is logged.
    """
    if category is None:
        category = _detect_category(text)
    tags = _detect_tags(text)

    # --- Conflict detection (pre-storage) ---
    _detect_and_resolve_conflicts(text, category, importance)

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


# === Two-Stage Memory Commitment ===
# Pattern 2: Three-Stage Memory Commitment (propose → evaluate → commit)
# Reduces memory bloat by filtering low-utility memories pre-storage.

_pending_proposals = {}  # candidate_id → proposal dict


def propose(text, importance=0.7, category=None, source="proposal"):
    """Stage 1: Propose a memory for storage without committing it.

    Evaluates utility via dedup check, goal relevance, and importance
    threshold. Returns a candidate dict with evaluation results.

    Usage:
        candidate = propose("Learned that X improves Y", importance=0.8)
        if candidate["recommendation"] == "commit":
            commit(candidate["candidate_id"])
    """
    candidate_id = f"prop_{uuid.uuid4().hex[:12]}"

    # Auto-detect category
    if category is None:
        category = _detect_category(text)

    evaluation = {
        "dedup_similar": None,
        "conflicts": [],
        "goal_relevance": 0.0,
        "importance_ok": importance >= 0.3,
        "text_quality": len(text.strip()) >= 20,
    }
    reasons = []

    # 0. Conflict detection: find contradictions in target collection
    try:
        from .memory_evolution import find_contradictions
        contradictions = find_contradictions(brain, text, category,
                                             threshold=1.0, top_n=5)
        if contradictions:
            evaluation["conflicts"] = [
                {
                    "id": c["id"],
                    "distance": round(c.get("distance", 0), 4),
                    "signals": c.get("contradiction_signal", []),
                    "text_preview": c.get("document", "")[:100],
                }
                for c in contradictions
            ]
            reasons.append(f"conflicts detected ({len(contradictions)})")
    except Exception:
        pass

    # 1. Dedup check: find similar existing memories
    try:
        similar = brain.recall(text, collections=[category], n=3, caller="proposal_dedup")
        if similar:
            top_dist = similar[0].get("distance")
            if top_dist is not None and top_dist < 0.3:
                evaluation["dedup_similar"] = {
                    "distance": round(top_dist, 4),
                    "existing_id": similar[0].get("id"),
                    "existing_text": similar[0].get("document", "")[:100],
                }
                reasons.append(f"near-duplicate (d={top_dist:.3f})")
            elif top_dist is not None and top_dist < 0.5:
                evaluation["dedup_similar"] = {
                    "distance": round(top_dist, 4),
                    "existing_id": similar[0].get("id"),
                    "existing_text": similar[0].get("document", "")[:100],
                }
                reasons.append(f"similar exists (d={top_dist:.3f})")
    except Exception:
        pass

    # 2. Goal relevance: check if text relates to active goals
    try:
        goals = brain.recall(text, collections=[GOALS], n=2, caller="proposal_goals")
        if goals:
            top_goal_dist = goals[0].get("distance")
            if top_goal_dist is not None and top_goal_dist < 1.0:
                evaluation["goal_relevance"] = round(1.0 - top_goal_dist, 3)
                reasons.append(f"goal-aligned ({evaluation['goal_relevance']:.2f})")
    except Exception:
        pass

    # 3. Recommendation logic
    is_duplicate = (evaluation["dedup_similar"] is not None
                    and evaluation["dedup_similar"]["distance"] < 0.3)
    is_low_quality = not evaluation["text_quality"]
    is_low_importance = not evaluation["importance_ok"]

    if is_duplicate:
        recommendation = "reject"
        reasons.insert(0, "REJECT: near-duplicate")
    elif is_low_quality:
        recommendation = "reject"
        reasons.insert(0, "REJECT: text too short (<20 chars)")
    elif is_low_importance:
        recommendation = "reject"
        reasons.insert(0, "REJECT: importance below threshold (0.3)")
    elif (evaluation["dedup_similar"] is not None
          and evaluation["dedup_similar"]["distance"] < 0.5):
        recommendation = "review"
        reasons.insert(0, "REVIEW: similar memory exists — consider reconsolidation")
    else:
        recommendation = "commit"
        reasons.insert(0, "OK: passes all checks")

    proposal = {
        "candidate_id": candidate_id,
        "text": text,
        "importance": importance,
        "category": category,
        "source": source,
        "evaluation": evaluation,
        "recommendation": recommendation,
        "reasons": reasons,
        "proposed_at": time.time(),
    }

    _pending_proposals[candidate_id] = proposal

    # Auto-expire old proposals (keep max 100, drop oldest)
    if len(_pending_proposals) > 100:
        oldest = min(_pending_proposals, key=lambda k: _pending_proposals[k]["proposed_at"])
        del _pending_proposals[oldest]

    return proposal


def commit(candidate_id):
    """Stage 2: Commit a proposed memory to persistent storage.

    Args:
        candidate_id: The ID returned by propose()

    Returns:
        Dict with memory_id on success, or error on failure.
    """
    proposal = _pending_proposals.pop(candidate_id, None)
    if proposal is None:
        return {"committed": False, "error": f"No pending proposal with id '{candidate_id}'"}

    # Auto-detect tags (same logic as remember())
    tags = []
    tl = proposal["text"].lower()
    if re.search(r'\b(code|script|python|js|rust)\b', tl):
        tags.append("technical")
    if re.search(r'\b(bug|fix|error|issue)\b', tl):
        tags.append("bug")
    if re.search(r'\b(goal|objective)\b', tl):
        tags.append("goal")
    if re.search(r'\b(research|paper|study|theory)\b', tl):
        tags.append("research")

    memory_id = brain.store(
        proposal["text"],
        collection=proposal["category"],
        importance=proposal["importance"],
        tags=tags or None,
        source=proposal["source"],
    )

    return {
        "committed": True,
        "memory_id": memory_id,
        "category": proposal["category"],
        "importance": proposal["importance"],
        "evaluation": proposal["evaluation"],
    }


def propose_and_commit(text, importance=0.7, category=None, source="auto",
                       auto_commit=True):
    """Convenience: propose + auto-commit if recommended.

    Returns the proposal with commit result if auto-committed.
    Use this as a drop-in replacement for remember() with pre-storage filtering.
    """
    proposal = propose(text, importance=importance, category=category, source=source)

    if auto_commit and proposal["recommendation"] == "commit":
        result = commit(proposal["candidate_id"])
        proposal["commit_result"] = result
    elif auto_commit and proposal["recommendation"] == "review":
        # For "review" recommendations, still commit but flag it
        result = commit(proposal["candidate_id"])
        proposal["commit_result"] = result
    else:
        proposal["commit_result"] = None

    return proposal


def get_pending_proposals():
    """List all pending proposals awaiting commit/reject."""
    now = time.time()
    return [
        {**p, "age_s": round(now - p["proposed_at"], 1)}
        for p in _pending_proposals.values()
    ]


def reject_proposal(candidate_id):
    """Explicitly reject a pending proposal."""
    proposal = _pending_proposals.pop(candidate_id, None)
    if proposal is None:
        return {"rejected": False, "error": f"No pending proposal with id '{candidate_id}'"}
    return {"rejected": True, "candidate_id": candidate_id, "text": proposal["text"][:100]}


def evolve(old_id, old_collection, new_text, reason="contradiction"):
    """Evolve a memory — create a revised version linked to the original."""
    from .memory_evolution import evolve_memory
    return evolve_memory(brain, old_id, old_collection, new_text, reason)


def search(query, n=5, min_importance=None, collections=None):
    """Search ClarvisDB — use this instead of OpenClaw's memory_search."""
    return brain.recall(query, n=n, min_importance=min_importance, collections=collections)


def synthesize(query, n=10, collections=None):
    """Synthesize conclusions across multiple memories for a topic.

    Groups evidence into bundles, detects contradictions, and returns
    structured synthesis instead of loosely related top hits.
    """
    return brain.synthesize(query, n=n, collections=collections)


def global_search(query, level="C1", top_k=5):
    """GraphRAG-style global search over community summaries."""
    from clarvis.brain.graphrag import global_search as _gs
    return _gs(query, level=level, top_k=top_k)

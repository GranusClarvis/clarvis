import os
"""Brain search operations — recall, query routing, embedding cache, synthesis.

import os
Belief revision filtering:
  - Superseded memories (status='superseded') are excluded from recall by default.
  - Low-confidence memories (confidence < 0.3) are deprioritized.
  - Expired memories (valid_until < now) are deprioritized.

Conclusion synthesis:
  - synthesize() draws conclusions across multiple memories.
  - Groups results into evidence bundles by semantic proximity.
  - Detects contradictions within bundles.
  - Returns structured synthesis with supporting/contradicting evidence.
"""

import copy
import logging
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .constants import DEFAULT_COLLECTIONS, ALL_COLLECTIONS, route_query

# ---------------------------------------------------------------------------
# Hook safety: per-hook timeout + circuit breaker (Phase 4: Safety Hardening)
# ---------------------------------------------------------------------------

# Per-hook failure tracking: {fn_id: {"consecutive_failures": int, "disabled_at": float}}
_hook_state = {}
_HOOK_FAILURE_THRESHOLD = 3
_HOOK_COOLDOWN_S = 300  # re-enable after 5 minutes
# Timeouts: brain hooks (scorers/boosters) are latency-sensitive; observers run in bg
_BRAIN_HOOK_TIMEOUT_S = 0.5   # 500ms for inline recall hooks
_HEARTBEAT_HOOK_TIMEOUT_S = 10.0  # 10s for heartbeat/observer hooks


def _hook_id(fn):
    """Stable identifier for a hook function."""
    return getattr(fn, "__qualname__", None) or id(fn)


def _is_hook_disabled(fn) -> bool:
    """Check if a hook is circuit-broken (disabled after repeated failures)."""
    hid = _hook_id(fn)
    state = _hook_state.get(hid)
    if state and state.get("disabled_at"):
        import time as _t
        elapsed = _t.time() - state["disabled_at"]
        if elapsed < _HOOK_COOLDOWN_S:
            return True
        # Cooldown expired — half-open: re-enable for one try
        state["disabled_at"] = None
        state["consecutive_failures"] = 0
    return False


def _record_hook_result(fn, success: bool):
    """Track hook success/failure for circuit-breaker logic."""
    hid = _hook_id(fn)
    state = _hook_state.setdefault(hid, {"consecutive_failures": 0, "disabled_at": None})
    if success:
        state["consecutive_failures"] = 0
        state["disabled_at"] = None
    else:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= _HOOK_FAILURE_THRESHOLD:
            import time as _t
            state["disabled_at"] = _t.time()
            _log.warning(
                "Hook circuit breaker OPEN for %s (%d consecutive failures, "
                "cooldown %ds)", _hook_id(fn), state["consecutive_failures"],
                _HOOK_COOLDOWN_S,
            )


def _run_hook_with_timeout(fn, args, timeout_s):
    """Run a hook function with a timeout. Returns True on success."""
    if _is_hook_disabled(fn):
        return False
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="hook-to") as ex:
        future = ex.submit(fn, *args)
        try:
            future.result(timeout=timeout_s)
            _record_hook_result(fn, True)
            return True
        except FuturesTimeout:
            _log.warning("Hook %s timed out after %.1fs", _hook_id(fn), timeout_s)
            _record_hook_result(fn, False)
            future.cancel()
            return False
        except Exception:
            _log.debug("Hook %s failed", _hook_id(fn), exc_info=True)
            _record_hook_result(fn, False)
            return False


# Patterns that identify synthetic bridge/boost memories by ID or content
_BRIDGE_ID_PREFIXES = ("bridge_", "sbridge_", "cross_link_", "xlink_", "boost_", "tm_")
_BRIDGE_TEXT_PREFIXES = (
    "BRIDGE [", "Connection between", "Phi action:", "Phi integration",
    "Cross-domain link:", "Cross-domain insight:", "Semantic bridge between",
)

_log = logging.getLogger("clarvis.brain.search")

# --- Temporal intent detection ---
# Patterns that indicate the caller wants recency-biased results.
# Returns (since_days, recency_weight) or None if no temporal intent detected.

_TEMPORAL_PATTERNS = [
    # "last N hours/days/weeks"
    (re.compile(r'\blast\s+(\d+)\s+hours?\b', re.I), lambda m: (max(1, int(m.group(1)) // 24) or 1, 0.7)),
    (re.compile(r'\blast\s+(\d+)\s+days?\b', re.I), lambda m: (int(m.group(1)), 0.6)),
    (re.compile(r'\blast\s+(\d+)\s+weeks?\b', re.I), lambda m: (int(m.group(1)) * 7, 0.5)),
    # "past N days/hours/weeks"
    (re.compile(r'\bpast\s+(\d+)\s+hours?\b', re.I), lambda m: (max(1, int(m.group(1)) // 24) or 1, 0.7)),
    (re.compile(r'\bpast\s+(\d+)\s+days?\b', re.I), lambda m: (int(m.group(1)), 0.6)),
    (re.compile(r'\bpast\s+(\d+)\s+weeks?\b', re.I), lambda m: (int(m.group(1)) * 7, 0.5)),
    # "today", "last 24 hours" — calendar-day aware (use_calendar_day flag)
    (re.compile(r'\btoday\b', re.I), lambda m: (1, 0.9)),
    (re.compile(r'\blast\s+24\s+hours?\b', re.I), lambda m: (1, 0.8)),
    # "yesterday"
    (re.compile(r'\byesterday\b', re.I), lambda m: (2, 0.7)),
    # "this week"
    (re.compile(r'\bthis\s+week\b', re.I), lambda m: (7, 0.5)),
    # "this month"
    (re.compile(r'\bthis\s+month\b', re.I), lambda m: (30, 0.4)),
    # "recently", "recent", "latest"
    (re.compile(r'\brecently\b', re.I), lambda m: (7, 0.6)),
    (re.compile(r'\brecent\b', re.I), lambda m: (7, 0.6)),
    (re.compile(r'\blatest\b', re.I), lambda m: (7, 0.6)),
    # "what happened" (implicitly temporal)
    (re.compile(r'\bwhat\s+happened\b', re.I), lambda m: (7, 0.5)),
]

# Calendar-aware patterns: "today" and "yesterday" use calendar-day boundaries
# instead of rolling 24h/48h windows. This returns an epoch cutoff directly.
_CALENDAR_PATTERNS = [
    (re.compile(r'\btoday\b', re.I), 0),       # 0 = start of today
    (re.compile(r'\byesterday\b', re.I), 1),    # 1 = start of yesterday
]


def detect_temporal_intent(query):
    """Detect temporal intent in a query string.

    Returns (since_days, recency_weight, calendar_epoch) where:
      - since_days: int or None — rolling window cutoff in days
      - recency_weight: float 0.0-1.0 — how much to bias ranking by recency
      - calendar_epoch: int or None — if set, use this epoch as the hard cutoff
        instead of since_days (for calendar-day precision like "today"/"yesterday")

    Examples:
        "what happened recently" → (7, 0.6, None)
        "last 3 days progress" → (3, 0.6, None)
        "today's events" → (1, 0.9, <epoch of midnight today>)
        "search architecture" → (None, 0.0, None)
    """
    # Check calendar-day patterns first (more precise than rolling windows)
    for pattern, days_back in _CALENDAR_PATTERNS:
        if pattern.search(query):
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
            cal_epoch = int(day_start.timestamp())
            # Match recency_weight from _TEMPORAL_PATTERNS for consistency
            rw = 0.9 if days_back == 0 else 0.7
            sd = days_back + 1  # fallback since_days for memories without created_epoch
            return sd, rw, cal_epoch

    for pattern, extractor in _TEMPORAL_PATTERNS:
        m = pattern.search(query)
        if m:
            since_days, recency_weight = extractor(m)
            return since_days, recency_weight, None
    return None, 0.0, None


# --- Contextual Retrieval: collection-level metadata synthesis ---
# Pilot collections for chunk-level contextual enrichment (2026-03-19).
# Adds collection purpose + metadata summary as a prefix to each result's
# document text, so downstream consumers (context assembly) get
# self-contextualizing chunks.  Inspired by Anthropic's Contextual Retrieval
# benchmark (49% fewer failed retrievals with contextual embeddings).
_CONTEXTUAL_PILOT_COLLECTIONS = frozenset({
    "clarvis-learnings",
    "clarvis-context",
})

_COLLECTION_DESCRIPTIONS = {
    "clarvis-learnings": "Insight/lesson learned",
    "clarvis-context": "Current working context",
}


def contextual_enrich(results):
    """Add collection-level contextual prefix to recall results (pilot collections).

    For each result from a pilot collection, synthesizes a short metadata
    prefix from: collection purpose, source, creation date, and tags.
    Stores the enriched text in ``_contextual_document`` (original ``document``
    is preserved).  Non-pilot results get ``_contextual_document = document``.

    This is read-time enrichment — cheaper than re-embedding but gives the LLM
    self-contextualizing chunks when they appear in the context brief.
    """
    for r in results:
        col = r.get("collection", "")
        doc = r.get("document", "")

        if col not in _CONTEXTUAL_PILOT_COLLECTIONS:
            r["_contextual_document"] = doc
            continue

        meta = r.get("metadata", {})
        parts = []

        # Collection purpose
        desc = _COLLECTION_DESCRIPTIONS.get(col, col)
        parts.append(desc)

        # Source attribution
        source = meta.get("source", "")
        if source:
            parts.append(f"src={source}")

        # Temporal anchor
        created = meta.get("created_at", "")
        if created:
            parts.append(created[:10])  # date only

        # Tags for topical grounding
        tags = meta.get("tags", "")
        if tags:
            if isinstance(tags, list):
                tags = ",".join(tags[:3])
            elif isinstance(tags, str) and len(tags) > 60:
                tags = tags[:60]
            parts.append(f"[{tags}]")

        prefix = " | ".join(parts)
        r["_contextual_document"] = f"({prefix}) {doc}"

    return results


# Shared daemon executor for fire-and-forget observer hooks.
# Daemon threads die with the process — no need for explicit shutdown.
_observer_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="brain-obs")

# Pre-warmed executor for parallel collection queries.
# Avoids thread pool creation overhead on every recall() call.
# 6 workers covers DEFAULT_COLLECTIONS (6 collections); ALL_COLLECTIONS (10) reuses them.
_recall_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="brain-recall")


def _is_bridge_memory(result: dict) -> bool:
    """Check if a recall result is a synthetic bridge/boost memory."""
    mem_id = result.get("id", "")
    if any(mem_id.startswith(p) for p in _BRIDGE_ID_PREFIXES):
        return True
    doc = result.get("document", "")
    if any(doc.startswith(p) for p in _BRIDGE_TEXT_PREFIXES):
        return True
    return False


def _deprioritize_bridges(results: list) -> list:
    """Move bridge memories to end of results (don't remove — may still be useful)."""
    organic = []
    bridges = []
    for r in results:
        if _is_bridge_memory(r):
            bridges.append(r)
        else:
            organic.append(r)
    return organic + bridges


def _filter_belief_revision(results: list) -> list:
    """Filter out superseded memories and deprioritize low-confidence/expired ones.

    - status='superseded' → removed entirely (replaced by newer memory)
    - confidence < 0.3 → moved to end (uncertain, might still be useful)
    - valid_until < now → moved to end (expired, needs re-evaluation)
    """
    active = []
    deprioritized = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for r in results:
        meta = r.get("metadata", {})

        # Skip superseded/deleted memories entirely
        status = str(meta.get("status", "")).lower()
        if status in {"superseded", "deleted"}:
            continue

        # Deprioritize low-confidence memories
        confidence = meta.get("confidence")
        if confidence is not None:
            try:
                if float(confidence) < 0.3:
                    deprioritized.append(r)
                    continue
            except (ValueError, TypeError):
                pass

        # Deprioritize expired memories
        valid_until = meta.get("valid_until")
        if valid_until and valid_until < now_iso:
            deprioritized.append(r)
            continue

        active.append(r)

    return active + deprioritized


class SearchMixin:
    """Search operations for ClarvisBrain (mixed into the main class)."""

    # --- recall helper: resolve params ---

    def _resolve_recall_params(self, query, collections, n, since_days, recency_weight):
        """Resolve collection routing and temporal intent for recall."""
        if collections is None:
            routed = route_query(query)
            collections = routed if routed else DEFAULT_COLLECTIONS

        calendar_epoch = None
        auto_since, auto_recency, auto_cal_epoch = detect_temporal_intent(query)
        if since_days is None and auto_since is not None:
            since_days = auto_since
        if recency_weight == 0.0 and auto_recency > 0.0:
            recency_weight = auto_recency
        if auto_cal_epoch is not None:
            calendar_epoch = auto_cal_epoch

        # Temporal queries benefit from more results (timeline, not single answer)
        if since_days is not None and n <= 5:
            n = 15

        return collections, n, since_days, recency_weight, calendar_epoch

    # --- recall helper: compute temporal cutoff ---

    @staticmethod
    def _compute_temporal_cutoff(since_days, calendar_epoch):
        """Compute cutoff_date and cutoff_epoch from temporal params."""
        if calendar_epoch is not None:
            cutoff_epoch = calendar_epoch
            cutoff_date = datetime.fromtimestamp(calendar_epoch, tz=timezone.utc).isoformat()
        elif since_days:
            from datetime import timedelta
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=since_days)
            cutoff_date = cutoff_dt.isoformat()
            cutoff_epoch = int(cutoff_dt.timestamp())
        else:
            cutoff_date = None
            cutoff_epoch = None
        return cutoff_date, cutoff_epoch

    # --- recall helper: embedding ---

    def _get_or_compute_embedding(self, query, valid_collections):
        """Get cached embedding or compute from first valid collection's EF."""
        now = time.monotonic()
        cached = self._embedding_cache.get(query)
        if cached and (now - cached[0]) < self._embedding_cache_ttl:
            return cached[1]

        if not valid_collections:
            return None

        col0 = self.collections[valid_collections[0]]
        ef = col0._embedding_function
        if ef is None:
            return None
        try:
            vecs = ef([query])
            if vecs and len(vecs) > 0:
                emb = vecs[0]
                if hasattr(emb, 'tolist'):
                    emb = emb.tolist()
                self._embedding_cache[query] = (now, emb)
                if len(self._embedding_cache) > 50:
                    oldest_key = min(self._embedding_cache, key=lambda k: self._embedding_cache[k][0])
                    del self._embedding_cache[oldest_key]
                return emb
        except Exception:
            pass
        return None

    # --- recall helper: query single collection ---

    def _query_single_collection(self, col_name, query, query_embedding, n,
                                 cutoff_epoch, cutoff_date, min_importance,
                                 include_related):
        """Query a single ChromaDB collection. Designed for parallel execution."""
        col = self.collections[col_name]
        fetch_n = n * 3 if cutoff_epoch else n

        where_clause = {"created_epoch": {"$gte": cutoff_epoch}} if cutoff_epoch else None
        try:
            if query_embedding is not None:
                results = col.query(query_embeddings=[query_embedding],
                                    n_results=fetch_n, where=where_clause)
            else:
                results = col.query(query_texts=[query], n_results=fetch_n,
                                    where=where_clause)
        except Exception:
            if query_embedding is not None:
                results = col.query(query_embeddings=[query_embedding], n_results=fetch_n)
            else:
                results = col.query(query_texts=[query], n_results=fetch_n)

        items = []
        if not (results["documents"] and results["documents"][0]):
            return items

        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            if min_importance is not None and meta.get("importance", 0) < min_importance:
                continue
            if cutoff_date and not meta.get("created_epoch") and meta.get("created_at"):
                if meta["created_at"] < cutoff_date:
                    continue
            distance = results["distances"][0][i] if results.get("distances") else None
            item = {
                "document": doc, "metadata": meta, "collection": col_name,
                "id": results["ids"][0][i], "distance": distance, "related": [],
            }
            if include_related:
                item["related"] = self.get_related(results["ids"][0][i], depth=1)
            items.append(item)
        return items

    # --- recall helper: dispatch queries across collections ---

    def _dispatch_collection_queries(self, valid_collections, query, query_embedding, n,
                                     cutoff_epoch, cutoff_date, min_importance,
                                     include_related):
        """Query all collections (parallel when >=3, sequential otherwise)."""
        import os as _os
        from functools import partial

        _parallel_env = _os.environ.get("CLARVIS_PARALLEL_RECALL")
        if _parallel_env == "0":
            use_parallel = False
        elif _parallel_env == "1":
            use_parallel = len(valid_collections) > 1
        else:
            use_parallel = len(valid_collections) >= 3

        query_fn = partial(self._query_single_collection,
                           query=query, query_embedding=query_embedding, n=n,
                           cutoff_epoch=cutoff_epoch, cutoff_date=cutoff_date,
                           min_importance=min_importance, include_related=include_related)

        all_results = []
        if use_parallel:
            from concurrent.futures import as_completed
            futures = {_recall_executor.submit(query_fn, c): c for c in valid_collections}
            for future in as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass
        else:
            for c in valid_collections:
                try:
                    all_results.extend(query_fn(c))
                except Exception:
                    pass
        return all_results

    # --- recall helper: chronological fallback ---

    def _supplement_chronological(self, all_results, valid_collections, cutoff_epoch, n):
        """Supplement semantic results with reverse-chronological retrieval."""
        existing_ids = {r.get("id") for r in all_results}
        for col_name in valid_collections:
            col = self.collections[col_name]
            try:
                chrono = col.get(where={"created_epoch": {"$gte": cutoff_epoch}},
                                 limit=n * 3, include=["documents", "metadatas"])
            except Exception:
                continue
            if not chrono.get("ids"):
                continue
            for i, mid in enumerate(chrono["ids"]):
                if mid in existing_ids:
                    continue
                existing_ids.add(mid)
                meta = chrono["metadatas"][i] if chrono.get("metadatas") else {}
                doc = chrono["documents"][i] if chrono.get("documents") else ""
                all_results.append({
                    "document": doc, "metadata": meta, "collection": col_name,
                    "id": mid, "distance": None, "related": [],
                    "_chrono_fallback": True,
                })

    # --- recall helper: score + sort ---

    def _score_and_sort(self, all_results, recency_weight, attention_boost, filter_bridges):
        """Apply hooks, recency scoring, sorting, and filtering to results."""
        # Hook: attention boost (with timeout + circuit breaker)
        if attention_boost:
            for fn in self._recall_boosters:
                _run_hook_with_timeout(fn, (all_results,), _BRAIN_HOOK_TIMEOUT_S)

        # Hook: scoring (actr or fallback, with timeout + circuit breaker)
        scored = False
        for fn in self._recall_scorers:
            if _run_hook_with_timeout(fn, (all_results,), _BRAIN_HOOK_TIMEOUT_S):
                scored = True
                break

        rw = max(0.0, min(1.0, recency_weight))

        # Compute recency scores
        if rw > 0:
            now_ts = datetime.now(timezone.utc).timestamp()
            if rw >= 0.8:
                max_age = 7 * 86400
            elif rw >= 0.6:
                max_age = 30 * 86400
            else:
                max_age = 90 * 86400
            for r in all_results:
                created = r["metadata"].get("created_at", "")
                try:
                    age_s = now_ts - datetime.fromisoformat(created).timestamp()
                    r["_recency_score"] = max(0.0, 1.0 - age_s / max_age)
                except (ValueError, TypeError):
                    r["_recency_score"] = 0.0

        # Recency blending factor
        if rw >= 0.8:
            blend = 0.7
        elif rw >= 0.5:
            blend = rw * 0.65
        else:
            blend = rw * 0.4

        # Sort by actr score or distance-based fallback, blended with recency
        if scored:
            if rw > 0:
                all_results.sort(
                    key=lambda x: x.get("_actr_score", 0) * (1 - blend)
                    + x.get("_recency_score", 0) * blend, reverse=True)
            else:
                all_results.sort(key=lambda x: x.get("_actr_score", 0), reverse=True)
        else:
            def sort_key(x):
                dist = x.get("distance")
                sem = 1.0 / (1.0 + dist) if dist is not None else 0.5
                imp = x["metadata"].get("importance", 0.5)
                boost = x["metadata"].get("_attention_boost", 0)
                base = sem * 0.85 + (imp + boost) * 0.15
                if rw > 0:
                    return base * (1 - blend) + x.get("_recency_score", 0.0) * blend
                return base
            all_results.sort(key=sort_key, reverse=True)

        if filter_bridges:
            all_results = _deprioritize_bridges(all_results)
        return _filter_belief_revision(all_results)

    # --- recall helper: fire observers ---

    def _fire_recall_observers(self, query, final_results, caller):
        """Fire recall observers in background thread (hebbian, synaptic, etc.)."""
        if not (final_results and query and self._recall_observers):
            return
        now_mono = time.monotonic()
        last_obs = getattr(self, '_last_observer_time', 0)
        if (now_mono - last_obs) >= 5.0:
            self._last_observer_time = now_mono

        obs_snapshot = copy.deepcopy(final_results)
        observers = list(self._recall_observers)

        def _run():
            for fn in observers:
                if _is_hook_disabled(fn):
                    continue
                try:
                    fn(query, obs_snapshot, caller=caller,
                       rate_limit_mono=now_mono, last_mono=last_obs)
                    _record_hook_result(fn, True)
                except Exception:
                    _log.debug("Observer %s failed", fn.__qualname__, exc_info=True)
                    _record_hook_result(fn, False)
        _observer_executor.submit(_run)

    # --- recall: main entry point ---

    def recall(self, query, collections=None, n=5, min_importance=None,
               include_related=False, since_days=None, attention_boost=False,
               caller=None, graph_expand=False, filter_bridges=True,
               cross_collection_expand=False, recency_weight=0.0):
        """Recall memories matching a query.

        Uses registered hooks for scoring (actr), boosting (attention/hebbian),
        and observation (retrieval_quality) via dependency inversion.

        Set CLARVIS_RECALL_TELEMETRY=1 to log per-step timings.
        """
        import os as _os
        _telemetry = _os.environ.get("CLARVIS_RECALL_TELEMETRY") == "1"
        _t0 = time.monotonic()

        # Phase 1: Resolve parameters
        collections, n, since_days, recency_weight, calendar_epoch = \
            self._resolve_recall_params(query, collections, n, since_days, recency_weight)

        # Phase 2: Cache check
        cache_key = (query, tuple(sorted(collections)), n, min_importance,
                     since_days, attention_boost, recency_weight)
        now_cache = time.monotonic()
        cached_result = self._recall_cache.get(cache_key)
        if cached_result and (now_cache - cached_result[0]) < self._recall_cache_ttl:
            return cached_result[1]

        # Phase 3: Compute cutoffs and embedding
        _t_emb = time.monotonic()
        cutoff_date, cutoff_epoch = self._compute_temporal_cutoff(since_days, calendar_epoch)
        valid_collections = [c for c in collections if c in self.collections]
        query_embedding = self._get_or_compute_embedding(query, valid_collections)
        _t_emb_done = time.monotonic()

        # Phase 4: Fetch from collections
        _t_fetch = time.monotonic()
        all_results = self._dispatch_collection_queries(
            valid_collections, query, query_embedding, n,
            cutoff_epoch, cutoff_date, min_importance, include_related)

        # Phase 4b: Chronological fallback for strong temporal queries
        temporal_target = n * len(valid_collections)
        if cutoff_epoch and recency_weight >= 0.5 and len(all_results) < temporal_target:
            self._supplement_chronological(all_results, valid_collections, cutoff_epoch, n)

        # Phase 4c: Cross-collection dedup — same document text from
        # multiple collections should appear only once (keep best distance)
        if len(valid_collections) > 1 and all_results:
            seen_texts = {}  # normalized_text -> index in deduped list
            deduped = []
            for r in all_results:
                txt = r.get("document", "").strip()[:500].lower()
                if txt in seen_texts:
                    existing = deduped[seen_texts[txt]]
                    ed = existing.get("distance")
                    rd = r.get("distance")
                    if rd is not None and (ed is None or rd < ed):
                        deduped[seen_texts[txt]] = r
                else:
                    seen_texts[txt] = len(deduped)
                    deduped.append(r)
            all_results = deduped

        _t_fetch_done = time.monotonic()

        # Phase 5: Score, sort, filter
        all_results = self._score_and_sort(
            all_results, recency_weight, attention_boost, filter_bridges)
        final_results = all_results[:n * len(collections)]

        # Phase 6: Expansions
        if cross_collection_expand and query_embedding is not None:
            try:
                final_results = self._cross_collection_expand(
                    query, query_embedding, final_results, collections, n)
            except Exception:
                _log.debug("Cross-collection expansion failed", exc_info=True)
        if graph_expand and final_results:
            try:
                final_results = self._expand_with_graph_neighbors(final_results, n)
            except Exception:
                _log.debug("Graph expansion failed", exc_info=True)

        # Phase 7: Observers + reconsolidation + cache
        self._fire_recall_observers(query, final_results, caller)
        now_mono = time.monotonic()
        for result in final_results:
            mem_id = result.get("id")
            col_name = result.get("collection")
            if mem_id and col_name:
                self._labile_memories[mem_id] = {
                    "retrieved_at": now_mono, "collection": col_name,
                }
        # Cap _labile_memories: evict expired entries first, then oldest if > 500
        if len(self._labile_memories) > 500:
            expired = [k for k, v in self._labile_memories.items()
                       if (now_mono - v["retrieved_at"]) > self._lability_window]
            for k in expired:
                del self._labile_memories[k]
        if len(self._labile_memories) > 500:
            oldest = sorted(self._labile_memories,
                            key=lambda k: self._labile_memories[k]["retrieved_at"])
            for k in oldest[:len(self._labile_memories) - 500]:
                del self._labile_memories[k]
        self._recall_cache[cache_key] = (time.monotonic(), final_results)
        if len(self._recall_cache) > 50:
            oldest = min(self._recall_cache, key=lambda k: self._recall_cache[k][0])
            del self._recall_cache[oldest]

        if _telemetry:
            _t_end = time.monotonic()
            _log.info(
                "recall telemetry n=%d cols=%d results=%d | "
                "embed=%.1fms fetch=%.1fms sort+filter=%.1fms total=%.1fms",
                n, len(valid_collections), len(final_results),
                (_t_emb_done - _t_emb) * 1000,
                (_t_fetch_done - _t_fetch) * 1000,
                (_t_end - _t_fetch_done) * 1000,
                (_t_end - _t0) * 1000,
            )

        return final_results

    def _expand_with_graph_neighbors(self, results, n, max_seed=3, max_neighbors=5):
        """Expand results with 1-hop graph neighbor documents.

        For each of the top max_seed results, fetch graph neighbors and
        resolve their documents. Neighbors not already in results are
        appended with a penalty multiplier on their score.

        Args:
            results: Existing recall results (already sorted)
            n: Original n parameter (caps total expanded results)
            max_seed: How many top results to expand from (default 3)
            max_neighbors: Max neighbors per seed result (default 5)

        Returns:
            Expanded results list (originals + neighbors).
        """
        existing_ids = {r.get("id") for r in results if r.get("id")}
        neighbor_entries = []

        for seed in results[:max_seed]:
            seed_id = seed.get("id")
            if not seed_id:
                continue

            related = self.get_related(seed_id, depth=1)
            if not related:
                continue

            for rel in related[:max_neighbors]:
                neighbor_id = rel.get("id", "")
                if neighbor_id in existing_ids:
                    continue
                existing_ids.add(neighbor_id)

                # Resolve document from the appropriate collection
                neighbor_col = rel.get("collection") or self._infer_collection(neighbor_id)
                col_obj = self.collections.get(neighbor_col)
                if col_obj is None:
                    continue

                try:
                    doc_result = col_obj.get(ids=[neighbor_id], include=["documents", "metadatas"])
                    if not (doc_result["ids"] and doc_result["documents"] and doc_result["documents"][0]):
                        continue
                    doc_text = doc_result["documents"][0]
                    meta = doc_result["metadatas"][0] if doc_result.get("metadatas") else {}
                except Exception:
                    continue

                # Use seed's distance with a penalty (neighbor is less directly relevant)
                seed_distance = seed.get("distance", 1.0)
                neighbor_distance = seed_distance * 1.5 if seed_distance else 2.0

                neighbor_entries.append({
                    "document": doc_text,
                    "metadata": meta,
                    "collection": neighbor_col,
                    "id": neighbor_id,
                    "distance": neighbor_distance,
                    "related": [],
                    "_graph_expanded": True,
                    "_expanded_from": seed_id,
                    "_relationship": rel.get("relationship", "unknown"),
                })

        if neighbor_entries:
            results = list(results) + neighbor_entries

        return results

    def _cross_collection_expand(self, query, query_embedding, results,
                                   queried_collections, n, max_extra=3):
        """Dynamically query adjacent collections not in the original set.

        This replaces static bridge memories: instead of permanent synthetic
        memories linking collections, we do a lightweight probe of unqueried
        collections at query time. Only top-scoring cross-collection hits
        (distance < median of primary results) are included.

        Args:
            query: Original query text
            query_embedding: Pre-computed embedding vector
            results: Current results from primary collections
            queried_collections: Collections already searched
            n: Original n parameter
            max_extra: Max results to add from expansion (default 3)
        """
        # Find collections NOT already queried
        adjacent = [c for c in ALL_COLLECTIONS
                    if c not in queried_collections and c in self.collections]
        if not adjacent:
            return results

        # Compute distance threshold from primary results (median distance)
        distances = [r.get("distance") for r in results if r.get("distance") is not None]
        if not distances:
            return results
        distances.sort()
        threshold = distances[len(distances) // 2]  # median

        existing_ids = {r.get("id") for r in results}
        extra = []

        from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed

        def _probe_collection(col_name):
            """Query one adjacent collection for cross-domain matches."""
            col = self.collections[col_name]
            try:
                res = col.query(query_embeddings=[query_embedding], n_results=2)
            except Exception:
                return []
            hits = []
            if res["documents"] and res["documents"][0]:
                for i, doc in enumerate(res["documents"][0]):
                    dist = res["distances"][0][i] if res.get("distances") else None
                    rid = res["ids"][0][i]
                    if rid in existing_ids:
                        continue
                    # Only include if closer than median primary distance
                    if dist is not None and dist <= threshold:
                        meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                        hits.append({
                            "document": doc,
                            "metadata": meta,
                            "collection": col_name,
                            "id": rid,
                            "distance": dist,
                            "related": [],
                            "_cross_collection_expanded": True,
                        })
            return hits

        with _TPE(max_workers=min(len(adjacent), 6)) as executor:
            futures = {executor.submit(_probe_collection, c): c for c in adjacent}
            for future in as_completed(futures):
                try:
                    extra.extend(future.result())
                except Exception:
                    pass

        if extra:
            # Sort by distance, take best max_extra
            extra.sort(key=lambda x: x.get("distance", 999))
            results = list(results) + extra[:max_extra]

        return results

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

    def recall_recent(self, days=7, collections=None, n=20):
        """Get memories from the last N days"""
        return self.recall("", collections=collections, n=n, since_days=days)

    def recall_from_date(self, start_date, end_date=None, collections=None, n=20):
        """Get memories from a date range (parallel collection scan)."""
        if collections is None:
            collections = ALL_COLLECTIONS

        valid = [c for c in collections if c in self.collections]
        if not valid:
            return []

        def _scan_collection(col_name):
            col = self.collections[col_name]
            results = col.get()
            items = []
            for i, doc in enumerate(results.get("documents", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                created = meta.get("created_at", "")
                if created:
                    try:
                        mem_date = created[:10]
                        if mem_date >= start_date:
                            if end_date is None or mem_date <= end_date:
                                items.append({
                                    "document": doc,
                                    "metadata": meta,
                                    "collection": col_name,
                                    "id": results["ids"][i],
                                })
                    except Exception:
                        pass
            return items

        from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed
        all_results = []
        with _TPE(max_workers=min(len(valid), 6)) as executor:
            futures = {executor.submit(_scan_collection, c): c for c in valid}
            for future in as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass

        all_results.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
        return all_results[:n]

    def get_all_cached(self, collection_name):
        """Get all memories from a collection, with TTL caching."""
        now = time.monotonic()
        cached = self._collection_cache.get(collection_name)
        if cached and (now - cached[0]) < self._collection_cache_ttl:
            return cached[1]

        result = self.get(collection_name, n=10000)
        self._collection_cache[collection_name] = (now, result)
        return result

    # === Conclusion Synthesis ===

    def synthesize(self, query, n=10, collections=None,
                   contradiction_threshold=0.7, bundle_distance=1.2):
        """Draw conclusions across multiple memories for a query.

        Recalls memories, groups into evidence bundles by semantic proximity,
        detects contradictions within/across bundles, returns structured synthesis.

        Returns dict with: query, bundles, cross_bundle_contradictions,
        conclusion, confidence (0-1), n_memories, n_bundles, n_contradictions.
        """
        if collections is None:
            collections = ALL_COLLECTIONS

        # Step 1: Broad recall across all requested collections
        results = self.recall(
            query, collections=collections, n=n,
            attention_boost=True, filter_bridges=True,
            caller="synthesize",
        )

        if not results:
            return {
                "query": query,
                "bundles": [],
                "cross_bundle_contradictions": [],
                "conclusion": "No relevant memories found.",
                "confidence": 0.0,
                "n_memories": 0,
                "n_bundles": 0,
                "n_contradictions": 0,
            }

        # Step 2: Group into evidence bundles by semantic proximity
        bundles = _build_evidence_bundles(results, bundle_distance)

        # Step 3: Detect contradictions within each bundle
        all_contradictions = []
        for bundle in bundles:
            contras = _detect_contradictions(bundle["evidence"],
                                             contradiction_threshold)
            bundle["contradictions"] = contras
            all_contradictions.extend(contras)

        # Step 4: Cross-bundle contradiction check (compare bundle themes)
        cross_contradictions = _detect_cross_bundle_contradictions(bundles)

        # Step 5: Synthesize conclusion
        conclusion, confidence = _synthesize_conclusion(
            bundles, all_contradictions + cross_contradictions
        )

        return {
            "query": query,
            "bundles": bundles,
            "cross_bundle_contradictions": cross_contradictions,
            "conclusion": conclusion,
            "confidence": round(confidence, 3),
            "n_memories": len(results),
            "n_bundles": len(bundles),
            "n_contradictions": len(all_contradictions) + len(cross_contradictions),
        }


# === Synthesis helpers (module-level for testability) ===

# Contradiction signal words — pairs of opposing concepts
_CONTRADICTION_PAIRS = [
    ({"always", "must", "required", "mandatory"}, {"never", "optional", "unnecessary"}),
    ({"increase", "higher", "more", "grow"}, {"decrease", "lower", "less", "shrink"}),
    ({"enable", "activate", "start", "on"}, {"disable", "deactivate", "stop", "off"}),
    ({"true", "yes", "correct"}, {"false", "no", "incorrect", "wrong"}),
    ({"add", "include", "install"}, {"remove", "exclude", "uninstall"}),
    ({"success", "working", "fixed"}, {"failure", "broken", "bug"}),
]


def _tokenize_lower(text):
    """Lowercase tokenize for contradiction detection."""
    return set(re.findall(r"[a-z][a-z0-9_]+", text.lower()))


def _stem_match(tokens, target_set):
    """Check if any token starts with a word in the target set (simple stemming)."""
    for token in tokens:
        for target in target_set:
            if token.startswith(target) or target.startswith(token):
                return True
    return False


def _has_opposing_signals(tokens_a, tokens_b):
    """Check if two token sets contain opposing concepts."""
    for pos_set, neg_set in _CONTRADICTION_PAIRS:
        a_pos = _stem_match(tokens_a, pos_set)
        a_neg = _stem_match(tokens_a, neg_set)
        b_pos = _stem_match(tokens_b, pos_set)
        b_neg = _stem_match(tokens_b, neg_set)
        # One says positive, other says negative
        if (a_pos and b_neg) or (a_neg and b_pos):
            return True
    return False


def _build_evidence_bundles(results, max_distance=1.2):
    """Group recall results into evidence bundles by semantic proximity.

    Uses single-linkage clustering: assign each result to the nearest
    existing bundle (if within max_distance), or start a new bundle.
    """
    bundles = []  # list of {"theme": str, "evidence": [result], "distances": [float]}

    for r in results:
        doc = r.get("document", "")
        dist = r.get("distance", 999)
        assigned = False

        # Try to assign to existing bundle
        for bundle in bundles:
            # Compare with first item in bundle (centroid proxy)
            bundle_doc = bundle["evidence"][0].get("document", "")
            tokens_r = _tokenize_lower(doc)
            tokens_b = _tokenize_lower(bundle_doc)

            if not tokens_r or not tokens_b:
                continue

            # Jaccard similarity as clustering metric
            intersection = len(tokens_r & tokens_b)
            union = len(tokens_r | tokens_b)
            jaccard_sim = intersection / union if union > 0 else 0

            if jaccard_sim > 0.15:  # Threshold for "same topic"
                bundle["evidence"].append(r)
                bundle["distances"].append(dist)
                assigned = True
                break

        if not assigned:
            # Extract theme from first ~50 chars of document
            theme = doc[:80].split(".")[0].strip() if doc else "Unknown"
            bundles.append({
                "theme": theme,
                "evidence": [r],
                "distances": [dist],
                "contradictions": [],
            })

    # Clean up internal distances field (not needed in output)
    for bundle in bundles:
        del bundle["distances"]

    return bundles


def _detect_contradictions(evidence, distance_threshold=0.7):
    """Find contradictions within an evidence bundle.

    Two memories contradict if they are semantically close (low distance)
    but contain opposing signal words.

    Returns list of contradiction dicts.
    """
    contradictions = []
    for i, a in enumerate(evidence):
        tokens_a = _tokenize_lower(a.get("document", ""))
        for b in evidence[i + 1:]:
            tokens_b = _tokenize_lower(b.get("document", ""))

            if _has_opposing_signals(tokens_a, tokens_b):
                contradictions.append({
                    "memory_a": {
                        "id": a.get("id", ""),
                        "text": a.get("document", "")[:150],
                        "collection": a.get("collection", ""),
                    },
                    "memory_b": {
                        "id": b.get("id", ""),
                        "text": b.get("document", "")[:150],
                        "collection": b.get("collection", ""),
                    },
                    "type": "opposing_signals",
                })

    return contradictions


def _detect_cross_bundle_contradictions(bundles):
    """Detect contradictions between different evidence bundles."""
    contradictions = []
    for i, ba in enumerate(bundles):
        # Use all evidence tokens from bundle A
        tokens_a = set()
        for e in ba["evidence"]:
            tokens_a |= _tokenize_lower(e.get("document", ""))

        for bb in bundles[i + 1:]:
            tokens_b = set()
            for e in bb["evidence"]:
                tokens_b |= _tokenize_lower(e.get("document", ""))

            if _has_opposing_signals(tokens_a, tokens_b):
                contradictions.append({
                    "bundle_a_theme": ba["theme"],
                    "bundle_b_theme": bb["theme"],
                    "type": "cross_bundle_opposition",
                })

    return contradictions


def _synthesize_conclusion(bundles, contradictions):
    """Produce a textual conclusion and confidence score from evidence bundles.

    Confidence is based on:
    - Number of supporting memories (more = higher)
    - Consistency (fewer contradictions = higher)
    - Evidence quality (lower distances = higher)
    """
    if not bundles:
        return "Insufficient evidence for synthesis.", 0.0

    # Count total evidence
    total_evidence = sum(len(b["evidence"]) for b in bundles)
    n_contradictions = len(contradictions)

    # Evidence volume factor: 1 memory = 0.3, 5+ = 0.8, 10+ = 1.0
    volume_factor = min(1.0, 0.3 + total_evidence * 0.07)

    # Consistency factor: penalize contradictions
    if total_evidence > 0:
        contradiction_ratio = n_contradictions / total_evidence
        consistency_factor = max(0.0, 1.0 - contradiction_ratio * 2)
    else:
        consistency_factor = 0.0

    # Quality factor: average semantic similarity of top results
    all_distances = []
    for b in bundles:
        for e in b["evidence"]:
            d = e.get("distance")
            if d is not None:
                all_distances.append(d)

    if all_distances:
        avg_sim = 1.0 / (1.0 + sum(all_distances) / len(all_distances))
        quality_factor = avg_sim
    else:
        quality_factor = 0.5

    confidence = (
        0.35 * volume_factor +
        0.35 * consistency_factor +
        0.30 * quality_factor
    )

    # Build conclusion text
    parts = []

    # Summarize each bundle
    for b in bundles:
        n_ev = len(b["evidence"])
        theme = b["theme"]
        collections = set(e.get("collection", "") for e in b["evidence"])
        col_str = ", ".join(sorted(collections)) if collections else "unknown"
        parts.append(f"[{n_ev} memories, from {col_str}] {theme}")

    conclusion_lines = [f"Synthesis across {total_evidence} memories in {len(bundles)} evidence bundles:"]
    for p in parts[:5]:  # Cap at 5 bundles in summary
        conclusion_lines.append(f"  - {p}")

    if n_contradictions > 0:
        conclusion_lines.append(
            f"  WARNING: {n_contradictions} contradiction(s) detected — "
            f"review evidence before acting."
        )

    if confidence < 0.4:
        conclusion_lines.append("  NOTE: Low confidence — evidence is sparse or inconsistent.")

    conclusion = "\n".join(conclusion_lines)
    return conclusion, confidence

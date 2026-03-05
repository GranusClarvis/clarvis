"""Brain search operations — recall, query routing, embedding cache."""

import copy
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .constants import DEFAULT_COLLECTIONS, ALL_COLLECTIONS, route_query

_log = logging.getLogger("clarvis.brain.search")

# Shared daemon executor for fire-and-forget observer hooks.
# Daemon threads die with the process — no need for explicit shutdown.
_observer_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="brain-obs")


class SearchMixin:
    """Search operations for ClarvisBrain (mixed into the main class)."""

    def recall(self, query, collections=None, n=5, min_importance=None,
               include_related=False, since_days=None, attention_boost=False, caller=None):
        """Recall memories matching a query.

        Uses registered hooks for scoring (actr), boosting (attention/hebbian),
        and observation (retrieval_quality) instead of importing those modules
        directly — dependency inversion breaks the circular import SCC.
        """
        if collections is None:
            routed = route_query(query)
            collections = routed if routed else DEFAULT_COLLECTIONS

        # Result-level cache (30s TTL) — avoids repeated ChromaDB queries
        cache_key = (query, tuple(sorted(collections)), n, min_importance, since_days, attention_boost)
        now_cache = time.monotonic()
        cached_result = self._recall_cache.get(cache_key)
        if cached_result and (now_cache - cached_result[0]) < self._recall_cache_ttl:
            return cached_result[1]

        all_results = []
        cutoff_date = None
        if since_days:
            from datetime import timedelta
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

        # Pre-compute embedding once
        query_embedding = None
        valid_collections = [c for c in collections if c in self.collections]
        if valid_collections:
            now = time.monotonic()
            cached = self._embedding_cache.get(query)
            if cached and (now - cached[0]) < self._embedding_cache_ttl:
                query_embedding = cached[1]
            else:
                col0 = self.collections[valid_collections[0]]
                ef = col0._embedding_function
                if ef is not None:
                    try:
                        vecs = ef([query])
                        if vecs and len(vecs) > 0:
                            query_embedding = vecs[0]
                            if hasattr(query_embedding, 'tolist'):
                                query_embedding = query_embedding.tolist()
                            self._embedding_cache[query] = (now, query_embedding)
                            if len(self._embedding_cache) > 50:
                                oldest_key = min(self._embedding_cache, key=lambda k: self._embedding_cache[k][0])
                                del self._embedding_cache[oldest_key]
                    except Exception:
                        pass

        def _query_collection(col_name):
            """Query a single collection — designed for parallel execution."""
            col = self.collections[col_name]
            if query_embedding is not None:
                results = col.query(query_embeddings=[query_embedding], n_results=n)
            else:
                results = col.query(query_texts=[query], n_results=n)

            items = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}

                    if min_importance is not None:
                        if meta.get("importance", 0) < min_importance:
                            continue

                    if cutoff_date and meta.get("created_at"):
                        if meta["created_at"] < cutoff_date:
                            continue

                    distance = results["distances"][0][i] if results.get("distances") else None

                    result_item = {
                        "document": doc,
                        "metadata": meta,
                        "collection": col_name,
                        "id": results["ids"][0][i],
                        "distance": distance,
                        "related": []
                    }

                    if include_related:
                        related = self.get_related(results["ids"][0][i], depth=1)
                        result_item["related"] = related

                    items.append(result_item)
            return items

        # Query all collections in parallel (up to 10 workers to cover all collections)
        from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed
        with _TPE(max_workers=min(len(valid_collections), 10)) as executor:
            futures = {executor.submit(_query_collection, c): c for c in valid_collections}
            for future in as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass

        # --- Hook: attention boost ---
        if attention_boost:
            for fn in self._recall_boosters:
                try:
                    fn(all_results)
                except Exception:
                    pass

        # --- Hook: scoring (actr or fallback) ---
        scored = False
        for fn in self._recall_scorers:
            try:
                fn(all_results)
                scored = True
                break  # Use first successful scorer
            except Exception:
                continue

        if scored:
            all_results.sort(key=lambda x: x.get("_actr_score", 0), reverse=True)
        else:
            # Fallback: distance + importance scoring
            def sort_key(x):
                distance = x.get("distance")
                if distance is not None:
                    semantic_relevance = 1.0 / (1.0 + distance)
                else:
                    semantic_relevance = 0.5
                importance = x["metadata"].get("importance", 0.5)
                boost = x["metadata"].get("_attention_boost", 0)
                return semantic_relevance * 0.85 + (importance + boost) * 0.15
            all_results.sort(key=sort_key, reverse=True)

        final_results = all_results[:n * len(collections)]

        # --- Hook: recall observers (async fire-and-forget) ---
        # Observers (hebbian, synaptic, retrieval_quality) are side-effects that
        # don't affect query results. Run them in a background thread to avoid
        # blocking recall (saves ~1-5s per query).
        if final_results and query and self._recall_observers:
            now_mono = time.monotonic()
            last_obs = getattr(self, '_last_observer_time', 0)
            if (now_mono - last_obs) >= 5.0:
                self._last_observer_time = now_mono

            # Deep-copy results snapshot so observers don't race with caller
            obs_snapshot = copy.deepcopy(final_results)
            observers = list(self._recall_observers)

            def _run_observers():
                for fn in observers:
                    try:
                        fn(query, obs_snapshot, caller=caller,
                           rate_limit_mono=now_mono, last_mono=last_obs)
                    except Exception:
                        _log.debug("Observer %s failed", fn.__qualname__, exc_info=True)

            _observer_executor.submit(_run_observers)

        # Reconsolidation: mark retrieved memories as labile
        for result in final_results:
            mem_id = result.get("id")
            col_name = result.get("collection")
            if mem_id and col_name:
                self._labile_memories[mem_id] = {
                    "retrieved_at": time.monotonic(),
                    "collection": col_name,
                }

        # Cache result (evict oldest if > 50 entries)
        self._recall_cache[cache_key] = (time.monotonic(), final_results)
        if len(self._recall_cache) > 50:
            oldest = min(self._recall_cache, key=lambda k: self._recall_cache[k][0])
            del self._recall_cache[oldest]

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

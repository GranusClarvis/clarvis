
"""Brain store operations — memory storage, goals, context, decay, stats."""

import json
import time
from datetime import datetime, timezone

from .constants import (
    MEMORIES, GOALS, CONTEXT, DEFAULT_COLLECTIONS, ALL_COLLECTIONS,
)


class StoreMixin:
    """Store operations for ClarvisBrain (mixed into the main class)."""

    def store(self, text, collection=MEMORIES, importance=0.5, tags=None, source="conversation", memory_id=None):
        """Store a memory with rich metadata. Returns the memory ID."""
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

        self._invalidate_cache(collection)
        self.auto_link(memory_id, text, collection)
        return memory_id

    def auto_link(self, memory_id, text, collection):
        """Automatically link a memory to similar memories."""
        try:
            linked = 0
            results = self.collections[collection].query(
                query_texts=[text],
                n_results=4
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
                        if dist < 1.5:
                            self.add_relationship(memory_id, xresults["ids"][0][0], "cross_collection",
                                                  source_collection=collection, target_collection=other_col)
                            cross_linked += 1
                            if cross_linked >= 4:
                                break
                except Exception:
                    continue
        except Exception:
            pass

    # === GOAL TRACKING ===

    def get_goals(self, include_archived=False):
        """Get all tracked goals with normalized name/progress fields."""
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
        """One-time migration: convert store()-based goals to set_goal() format."""
        col = self.collections[GOALS]
        results = col.get()
        migrated = 0
        to_delete = []

        for i, mem_id in enumerate(results.get("ids", [])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            if "goal" in meta and "progress" in meta:
                continue

            doc = results["documents"][i] if results.get("documents") else ""
            name = mem_id.replace("goal-", "").replace("-", " ").replace("_", " ").title()

            self.set_goal(name, 0, subtasks={"description": doc[:200]})
            to_delete.append(mem_id)
            migrated += 1

        if to_delete:
            col.delete(ids=to_delete)

        return migrated

    def set_goal(self, goal_name, progress, subtasks=None):
        """Set or update a goal. Rejects garbage goals."""
        if not goal_name or len(goal_name.strip()) < 10:
            return
        reject_patterns = ["bridge", "sbridge", "BRIDGE", "Sbridge", "Connection between"]
        if any(p.lower() in goal_name.lower() for p in reject_patterns):
            return

        col = self.collections[GOALS]

        existing = col.get(ids=[goal_name])
        is_update = bool(existing and existing.get("ids"))

        if not is_update:
            all_goals = col.get()
            active_count = 0
            for i, gid in enumerate(all_goals.get("ids", [])):
                meta = all_goals["metadatas"][i] if all_goals.get("metadatas") else {}
                if str(meta.get("archived", "")).lower() != "true":
                    active_count += 1
            if active_count >= 25:
                return

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
        """Archive goals stuck at 0% for more than max_age_days."""
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

    # === MEMORY DECAY & PRUNING ===

    def decay_importance(self, decay_rate=0.01, min_importance=0.1):
        """Decay importance of all memories over time.

        Batches upserts per collection for efficiency (~10 calls instead of 1000+).
        """
        decayed = 0
        now = datetime.now(timezone.utc)

        for col_name, col in self.collections.items():
            results = col.get()

            batch_ids = []
            batch_docs = []
            batch_metas = []

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
                            batch_ids.append(mem_id)
                            batch_docs.append(results["documents"][i])
                            batch_metas.append(meta)
                except Exception:
                    pass

            if batch_ids:
                col.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                decayed += len(batch_ids)

        return decayed

    def prune_low_importance(self, threshold=0.12, preserve_tags=None):
        """Remove memories below importance threshold."""
        import sys

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
                    tags_json = meta.get("tags", "[]")
                    try:
                        tags = json.loads(tags_json) if isinstance(tags_json, str) else tags_json
                    except Exception:
                        tags = []

                    if not any(t in tags for t in preserve_tags):
                        to_delete.append(mem_id)

            if to_delete:
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
        """Run brain optimization: decay, prune, clean.

        Uses registered hooks for full consolidation (memory_consolidation)
        instead of importing directly — dependency inversion.
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
            for fn in self._optimize_hooks:
                try:
                    hook_result = fn(dry_run=False)
                    result.update(hook_result)
                except Exception as e:
                    result["consolidation_error"] = str(e)

        result["stats"] = self.stats()
        return result

    # === CACHE MANAGEMENT ===

    def _invalidate_cache(self, collection=None):
        """Invalidate caches after writes."""
        self._stats_cache = None
        self._stats_cache_time = 0
        if collection:
            self._collection_cache.pop(collection, None)
        else:
            self._collection_cache.clear()

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
        """Alias for health_check."""
        return self.health_check()

    def health_check(self):
        """Verify brain is working: store, recall, validate retrieval, check collections."""
        issues = []
        timings = {}

        # 1. Validate all collections initialized
        missing = [c for c in ALL_COLLECTIONS if c not in self.collections]
        if missing:
            issues.append(f"missing collections: {missing}")

        # 2. Store + recall roundtrip with retrieval verification
        try:
            t0 = time.monotonic()
            probe = f"health_probe_{int(time.time())}"
            self.store(probe, collection=MEMORIES, importance=0.1)
            timings["store_ms"] = round((time.monotonic() - t0) * 1000)

            t0 = time.monotonic()
            results = self.recall(probe, n=3)
            timings["recall_ms"] = round((time.monotonic() - t0) * 1000)

            # Verify the probe was actually retrieved
            found = any(probe in r.get("document", "") for r in results)
            if not found:
                issues.append("retrieval failed: probe memory not in recall results")
        except Exception as e:
            issues.append(f"store/recall error: {e}")

        # 3. Stats
        try:
            t0 = time.monotonic()
            s = self.stats()
            timings["stats_ms"] = round((time.monotonic() - t0) * 1000)
        except Exception as e:
            issues.append(f"stats error: {e}")
            s = {"total_memories": 0, "collections": {}, "graph_edges": 0}

        status = "unhealthy" if issues else "healthy"
        return {
            "status": status,
            "total_memories": s["total_memories"],
            "collections": len(s["collections"]),
            "graph_edges": s.get("graph_edges", 0),
            "timings": timings,
            **({"issues": issues} if issues else {}),
        }

    # === RECONSOLIDATION ===

    def reconsolidate(self, memory_id, updated_text, importance_delta=0.0):
        """Update a retrieved memory during its lability window."""
        labile = self._labile_memories.get(memory_id)
        if not labile:
            return {
                "success": False,
                "message": f"Memory '{memory_id}' is not labile — retrieve it first via recall()."
            }

        elapsed = time.monotonic() - labile["retrieved_at"]
        if elapsed > self._lability_window:
            del self._labile_memories[memory_id]
            return {
                "success": False,
                "message": f"Lability window expired ({elapsed:.0f}s > {self._lability_window}s). "
                           f"Memory has reconsolidated. Retrieve it again to reopen the window."
            }

        collection = labile["collection"]
        if collection not in self.collections:
            return {"success": False, "message": f"Collection '{collection}' not found."}

        col = self.collections[collection]

        try:
            current = col.get(ids=[memory_id])
        except Exception as e:
            return {"success": False, "message": f"Failed to fetch memory: {e}"}

        if not current["ids"]:
            del self._labile_memories[memory_id]
            return {"success": False, "message": f"Memory '{memory_id}' not found in ChromaDB."}

        old_text = current["documents"][0]
        meta = current["metadatas"][0] if current.get("metadatas") else {}

        meta["text"] = updated_text
        meta["last_accessed"] = datetime.now(timezone.utc).isoformat()
        meta["access_count"] = meta.get("access_count", 0) + 1

        recon_count = meta.get("reconsolidation_count", 0) + 1
        meta["reconsolidation_count"] = recon_count
        meta["last_reconsolidated"] = datetime.now(timezone.utc).isoformat()

        if importance_delta != 0.0:
            old_imp = meta.get("importance", 0.5)
            meta["importance"] = max(0.0, min(1.0, old_imp + importance_delta))

        col.upsert(
            ids=[memory_id],
            documents=[updated_text],
            metadatas=[meta]
        )

        self._invalidate_cache(collection)
        del self._labile_memories[memory_id]

        try:
            self.auto_link(memory_id, updated_text, collection)
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Memory reconsolidated after {elapsed:.1f}s labile window.",
            "old_text": old_text,
            "new_text": updated_text,
            "time_since_retrieval": round(elapsed, 1),
            "reconsolidation_count": recon_count,
            "importance": meta.get("importance", 0.5),
        }

    def get_labile_memories(self):
        """List currently labile memories and their remaining window time."""
        now = time.monotonic()
        result = []
        expired = []

        for mem_id, info in self._labile_memories.items():
            elapsed = now - info["retrieved_at"]
            if elapsed > self._lability_window:
                expired.append(mem_id)
            else:
                result.append({
                    "memory_id": mem_id,
                    "collection": info["collection"],
                    "elapsed_s": round(elapsed, 1),
                    "remaining_s": round(self._lability_window - elapsed, 1),
                })

        for mem_id in expired:
            del self._labile_memories[mem_id]

        return result


"""Brain store operations — memory storage, goals, context, decay, stats."""

import json
import os
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

        now_utc = datetime.now(timezone.utc)
        metadata = {
            "text": text,
            "created_at": now_utc.isoformat(),
            "created_epoch": int(now_utc.timestamp()),
            "last_accessed": now_utc.isoformat(),
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

    # === BELIEF REVISION ===

    def revise(self, old_memory_id, new_text, collection=None, reason="updated",
               confidence=None, valid_until=None):
        """Store a new memory that supersedes an old one.

        The old memory gets metadata status='superseded' and superseded_by=<new_id>.
        The new memory gets metadata supersedes=<old_id> plus optional confidence
        and valid_until fields.

        Args:
            old_memory_id: ID of the memory being revised
            new_text: Updated belief text
            collection: Collection to search (auto-detected if None)
            reason: Why the revision happened (e.g. "corrected", "updated", "refined")
            confidence: 0.0-1.0 certainty level (None = default 0.5)
            valid_until: ISO date string after which this belief should be re-evaluated

        Returns:
            dict with old_id, new_id, and status
        """
        # Find the old memory
        old_meta = None
        old_col = collection
        if old_col:
            cols_to_check = [old_col]
        else:
            cols_to_check = list(self.collections.keys())

        for col_name in cols_to_check:
            if col_name not in self.collections:
                continue
            try:
                result = self.collections[col_name].get(ids=[old_memory_id])
                if result["ids"]:
                    old_meta = result["metadatas"][0] if result.get("metadatas") else {}
                    old_col = col_name
                    break
            except Exception:
                continue

        if old_meta is None:
            return {"success": False, "message": f"Memory '{old_memory_id}' not found"}

        # Store the new memory
        importance = old_meta.get("importance", 0.5)
        tags = []
        try:
            tags_raw = old_meta.get("tags", "[]")
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
        except Exception:
            pass

        new_id = self.store(
            new_text,
            collection=old_col,
            importance=importance,
            tags=tags,
            source=f"revision:{reason}",
        )

        # Add revision metadata to new memory
        new_result = self.collections[old_col].get(ids=[new_id])
        if new_result["ids"]:
            new_meta = new_result["metadatas"][0] if new_result.get("metadatas") else {}
            new_meta["supersedes"] = old_memory_id
            new_meta["revision_reason"] = reason
            if confidence is not None:
                new_meta["confidence"] = max(0.0, min(1.0, float(confidence)))
            if valid_until:
                new_meta["valid_until"] = valid_until
            self.collections[old_col].update(
                ids=[new_id], metadatas=[new_meta]
            )

        # Mark old memory as superseded
        old_meta["status"] = "superseded"
        old_meta["superseded_by"] = new_id
        old_meta["superseded_at"] = datetime.now(timezone.utc).isoformat()
        self.collections[old_col].update(
            ids=[old_memory_id], metadatas=[old_meta]
        )

        self._invalidate_cache(old_col)

        return {
            "success": True,
            "old_id": old_memory_id,
            "new_id": new_id,
            "collection": old_col,
            "reason": reason,
        }

    def mark_uncertain(self, memory_id, confidence, collection=None):
        """Mark a memory with a confidence level (0.0=uncertain, 1.0=certain).

        Low-confidence memories are deprioritized in recall.
        """
        for col_name in ([collection] if collection else list(self.collections.keys())):
            if col_name not in self.collections:
                continue
            try:
                result = self.collections[col_name].get(ids=[memory_id])
                if result["ids"]:
                    meta = result["metadatas"][0] if result.get("metadatas") else {}
                    meta["confidence"] = max(0.0, min(1.0, float(confidence)))
                    self.collections[col_name].update(ids=[memory_id], metadatas=[meta])
                    self._invalidate_cache(col_name)
                    return {"success": True, "memory_id": memory_id, "confidence": confidence}
            except Exception:
                continue
        return {"success": False, "message": f"Memory '{memory_id}' not found"}

    def set_valid_until(self, memory_id, valid_until, collection=None):
        """Set a time bound on a memory — it should be re-evaluated after this date."""
        for col_name in ([collection] if collection else list(self.collections.keys())):
            if col_name not in self.collections:
                continue
            try:
                result = self.collections[col_name].get(ids=[memory_id])
                if result["ids"]:
                    meta = result["metadatas"][0] if result.get("metadatas") else {}
                    meta["valid_until"] = valid_until
                    self.collections[col_name].update(ids=[memory_id], metadatas=[meta])
                    self._invalidate_cache(col_name)
                    return {"success": True, "memory_id": memory_id, "valid_until": valid_until}
            except Exception:
                continue
        return {"success": False, "message": f"Memory '{memory_id}' not found"}

    # === MEMORY TUNING / MAINTENANCE ===

    def get_memory(self, memory_id, collection=None):
        """Fetch one memory by id with collection + metadata."""
        cols = [collection] if collection else list(self.collections.keys())
        for col_name in cols:
            if col_name not in self.collections:
                continue
            try:
                result = self.collections[col_name].get(ids=[memory_id])
                if result.get("ids"):
                    return {
                        "id": result["ids"][0],
                        "collection": col_name,
                        "document": result["documents"][0] if result.get("documents") else "",
                        "metadata": result["metadatas"][0] if result.get("metadatas") else {},
                    }
            except Exception:
                continue
        return None

    def update_memory(self, memory_id, *, text=None, metadata_patch=None, collection=None):
        """Update memory text and/or metadata in place."""
        current = self.get_memory(memory_id, collection=collection)
        if not current:
            return {"success": False, "message": f"Memory '{memory_id}' not found"}

        meta = dict(current.get("metadata") or {})
        if metadata_patch:
            meta.update(metadata_patch)
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()

        doc = current["document"] if text is None else text
        col = self.collections[current["collection"]]
        col.update(ids=[memory_id], documents=[doc], metadatas=[meta])
        self._invalidate_cache(current["collection"])
        return {
            "success": True,
            "memory_id": memory_id,
            "collection": current["collection"],
            "updated_text": text is not None,
            "metadata_keys": sorted(metadata_patch.keys()) if metadata_patch else [],
        }

    def _record_memory_mutation(self, action, payload):
        """Append a mutation record for auditability."""
        try:
            path = os.path.join(self.data_dir, "brain_mutations.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                **payload,
            }
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def delete_memory(self, memory_id, collection=None, reason="manual", hard=False):
        """Delete or soft-retire a memory.

        hard=False performs a safe soft delete by setting status=deleted and
        confidence=0.0 so recall deprioritizes/hides it for most flows.
        hard=True removes it from Chroma and graph stores.
        """
        current = self.get_memory(memory_id, collection=collection)
        if not current:
            return {"success": False, "message": f"Memory '{memory_id}' not found"}

        if not hard:
            meta = dict(current.get("metadata") or {})
            meta.update({
                "status": "deleted",
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deletion_reason": reason,
                "confidence": 0.0,
            })
            self.collections[current["collection"]].update(
                ids=[memory_id], metadatas=[meta]
            )
            self._invalidate_cache(current["collection"])
            self._record_memory_mutation("soft_delete", {
                "memory_id": memory_id,
                "collection": current["collection"],
                "reason": reason,
                "document": current["document"][:400],
            })
            return {"success": True, "mode": "soft", "memory_id": memory_id, "collection": current["collection"]}

        self.collections[current["collection"]].delete(ids=[memory_id])

        # Remove from JSON graph
        graph_changed = False
        if memory_id in self.graph.get("nodes", {}):
            del self.graph["nodes"][memory_id]
            graph_changed = True
        edges = self.graph.get("edges", [])
        filtered = [e for e in edges if e.get("from") != memory_id and e.get("to") != memory_id]
        if len(filtered) != len(edges):
            self.graph["edges"] = filtered
            graph_changed = True
        if graph_changed:
            self._save_graph()

        # Remove from SQLite graph store if enabled
        if getattr(self, "_sqlite_store", None) is not None:
            try:
                self._sqlite_store.remove_edges(where_sql="from_id = ? OR to_id = ?", params=(memory_id, memory_id))
                self._sqlite_store.remove_node(memory_id)
            except Exception:
                pass

        self._invalidate_cache(current["collection"])
        self._record_memory_mutation("hard_delete", {
            "memory_id": memory_id,
            "collection": current["collection"],
            "reason": reason,
            "document": current["document"][:400],
        })
        return {"success": True, "mode": "hard", "memory_id": memory_id, "collection": current["collection"]}

    def supersede_duplicates(self, keep_id, duplicate_ids, collection=None, reason="duplicate_cluster"):
        """Mark duplicate memories as superseded by a canonical keeper."""
        keeper = self.get_memory(keep_id, collection=collection)
        if not keeper:
            return {"success": False, "message": f"Keeper '{keep_id}' not found"}

        updated = []
        skipped = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for dup_id in duplicate_ids:
            if dup_id == keep_id:
                continue
            dup = self.get_memory(dup_id, collection=collection or keeper["collection"])
            if not dup:
                skipped.append({"id": dup_id, "reason": "not_found"})
                continue
            meta = dict(dup.get("metadata") or {})
            existing_conf = meta.get("confidence")
            try:
                existing_conf = float(existing_conf) if existing_conf is not None else 1.0
            except (TypeError, ValueError):
                existing_conf = 1.0
            meta.update({
                "status": "superseded",
                "superseded_by": keep_id,
                "superseded_at": now_iso,
                "revision_reason": reason,
                "confidence": min(existing_conf, 0.2),
            })
            self.collections[dup["collection"]].update(ids=[dup_id], metadatas=[meta])
            try:
                self.add_relationship(dup_id, keep_id, "superseded_by",
                                      source_collection=dup["collection"],
                                      target_collection=keeper["collection"])
            except Exception:
                pass
            updated.append(dup_id)
            self._record_memory_mutation("supersede", {
                "memory_id": dup_id,
                "collection": dup["collection"],
                "superseded_by": keep_id,
                "reason": reason,
                "document": dup["document"][:400],
            })

        self._invalidate_cache(collection or keeper["collection"])
        return {
            "success": True,
            "keeper": keep_id,
            "updated": updated,
            "skipped": skipped,
            "collection": keeper["collection"],
        }

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

    def get_goals_summary(self, top_n=10, min_progress=0):
        """Return a clean, deduped, sorted summary of active goals.

        Filters out garbage goals (short names, 0-progress junk with no
        recent updates), dedupes by normalized name, and returns a list
        sorted by progress descending, then importance descending.

        Each item: {name, progress, importance, updated, subtasks, source, id}
        """
        raw = self.get_goals(include_archived=False)
        now = datetime.now(timezone.utc)

        # Garbage filters
        GARBAGE_PATTERNS = [
            "bridge", "sbridge", "connection between", "fm goals",
            "outcome", "gwt broadcast", "boost_", "fresh_mirror",
        ]

        seen_names = {}  # normalized_name -> best goal dict
        for g in raw:
            meta = g.get("metadata", {})
            name = meta.get("goal", g.get("id", ""))
            progress = meta.get("progress", 0)
            if isinstance(progress, str):
                try:
                    progress = int(progress)
                except ValueError:
                    progress = 0
            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except ValueError:
                    importance = 0.5

            # Skip garbage
            if not name or len(name.strip()) < 10:
                continue
            name_lower = name.lower().strip()
            if any(p in name_lower for p in GARBAGE_PATTERNS):
                continue

            # Skip stale zero-progress goals (no update in 14 days)
            if progress <= min_progress and progress == 0:
                updated_str = meta.get("updated", "")
                if updated_str:
                    try:
                        updated_dt = datetime.fromisoformat(
                            updated_str.replace("Z", "+00:00")
                        )
                        if (now - updated_dt).days > 14:
                            continue
                    except (ValueError, TypeError):
                        pass

            # Dedupe: keep the one with higher progress, then higher importance
            norm_key = name_lower
            entry = {
                "name": name.strip(),
                "progress": progress,
                "importance": round(importance, 3),
                "updated": meta.get("updated", ""),
                "subtasks": meta.get("subtasks", ""),
                "source": meta.get("source", ""),
                "id": g.get("id", ""),
            }
            if norm_key in seen_names:
                existing = seen_names[norm_key]
                if (progress, importance) > (existing["progress"], existing["importance"]):
                    seen_names[norm_key] = entry
            else:
                seen_names[norm_key] = entry

        # Sort: progress desc, importance desc
        goals = sorted(
            seen_names.values(),
            key=lambda x: (x["progress"], x["importance"]),
            reverse=True,
        )
        return goals[:top_n]

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

        # Get graph counts from SQLite store if available (JSON dict is empty after cutover)
        sqlite = getattr(self, "_sqlite_store", None)
        if sqlite is not None:
            gs = sqlite.stats()
            graph_nodes = gs.get("nodes", 0)
            graph_edges = gs.get("edges", 0)
        else:
            graph_nodes = len(self.graph["nodes"])
            graph_edges = len(self.graph["edges"])

        stats = {
            "collections": {},
            "total_memories": 0,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges
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

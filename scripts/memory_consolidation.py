#!/usr/bin/env python3
"""
Memory Consolidation & Evolution System for Clarvis

Handles:
  - Deduplication of near-duplicate memories
  - Merging of semantically similar memory clusters
  - Importance decay with access-frequency boosting
  - Noise pruning (prediction logs, attention broadcasts, etc.)
  - Archival of stale low-importance memories
  - Attention-guided consolidation (GWT spotlight salience)
  - CLI for manual and automated operation

Attention-Guided Consolidation (GWT Integration):
  The attention spotlight from attention.py provides salience signals for
  what the system is currently focused on. During consolidation, we compute
  a "spotlight salience" for each brain memory — how relevant it is to the
  current spotlight contents. This score modulates all consolidation decisions:

  - High-salience memories RESIST decay (they're currently relevant)
  - Low-salience + low-access + old = prime prune candidates
  - After consolidation, surviving high-value memories are broadcast back
    to the spotlight (GWT global broadcast)

Usage:
    python3 memory_consolidation.py consolidate    # Run full consolidation
    python3 memory_consolidation.py dedup           # Deduplicate only
    python3 memory_consolidation.py prune           # Noise prune only
    python3 memory_consolidation.py archive         # Archive stale memories
    python3 memory_consolidation.py attention-prune # Attention-guided prune
    python3 memory_consolidation.py salience        # Show salience report
    python3 memory_consolidation.py stats           # Show memory stats
    python3 memory_consolidation.py dry-run         # Preview without changes
"""

import json
import math
import os
import re
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain import brain, ALL_COLLECTIONS
from attention import attention

DATA_DIR = "/home/agent/.openclaw/workspace/data"
ARCHIVE_DIR = os.path.join(DATA_DIR, "memory_archive")
ARCHIVE_FILE = os.path.join(ARCHIVE_DIR, "archived_memories.json")

os.makedirs(ARCHIVE_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_text(text):
    """Normalize text for prefix comparison: lowercase, collapse whitespace, strip."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def _get_tags(meta):
    """Extract tags list from metadata safely."""
    tags_raw = meta.get("tags", "[]")
    if isinstance(tags_raw, list):
        return tags_raw
    try:
        return json.loads(tags_raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _has_protected_tag(meta, protected=("critical", "genesis")):
    """Check if memory has any protected tag."""
    tags = _get_tags(meta)
    return any(t in tags for t in protected)


def _load_archive():
    """Load existing archive file or return empty list."""
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_archive(entries):
    """Save archive entries to JSON file."""
    with open(ARCHIVE_FILE, "w") as f:
        json.dump(entries, f, indent=2)


# Session-level cache for _get_all_memories — avoids re-fetching the same
# collection data 5+ times during a single consolidation run.
_memories_cache = {}
_memories_cache_gen = 0  # bump to invalidate


def _get_all_memories(collection_name, _cache_gen=[0]):
    """Get all memories from a single collection with full metadata.

    Results are cached for the duration of a consolidation run. Call
    _invalidate_memories_cache() after mutations to force re-fetch.
    """
    # If generation changed, clear the cache
    if _cache_gen[0] != _memories_cache_gen:
        _memories_cache.clear()
        _cache_gen[0] = _memories_cache_gen

    if collection_name in _memories_cache:
        return _memories_cache[collection_name]

    col = brain.collections.get(collection_name)
    if col is None:
        _memories_cache[collection_name] = []
        return []
    results = col.get()
    memories = []
    for i, mem_id in enumerate(results.get("ids", [])):
        doc = results["documents"][i] if results.get("documents") else ""
        meta = results["metadatas"][i] if results.get("metadatas") else {}
        memories.append({
            "id": mem_id,
            "document": doc,
            "metadata": meta,
            "collection": collection_name,
        })
    _memories_cache[collection_name] = memories
    return memories


def _invalidate_memories_cache():
    """Invalidate the session-level memories cache after mutations."""
    global _memories_cache_gen
    _memories_cache_gen += 1
    _memories_cache.clear()


# ---------------------------------------------------------------------------
# 1. Memory Deduplication
# ---------------------------------------------------------------------------

def deduplicate(dry_run=False):
    """
    Find near-duplicate memories using text prefix matching (first 100 chars
    normalized). Keep the one with highest importance, delete the rest.

    Returns:
        dict with 'duplicates_removed' count and 'groups' detail list.
    """
    stats = {"duplicates_removed": 0, "groups": []}

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        if not memories:
            continue

        # Group by normalized 100-char prefix
        prefix_groups = {}
        for mem in memories:
            prefix = _normalize_text(mem["document"])[:100]
            if not prefix:
                continue
            prefix_groups.setdefault(prefix, []).append(mem)

        col = brain.collections[col_name]

        for prefix, group in prefix_groups.items():
            if len(group) < 2:
                continue

            # Sort by importance descending; keep first
            group.sort(
                key=lambda m: m["metadata"].get("importance", 0.0),
                reverse=True,
            )
            keeper = group[0]
            duplicates = group[1:]

            ids_to_delete = [d["id"] for d in duplicates]

            stats["groups"].append({
                "collection": col_name,
                "prefix": prefix[:60],
                "kept": keeper["id"],
                "removed": ids_to_delete,
            })

            if not dry_run:
                col.delete(ids=ids_to_delete)
                _invalidate_memories_cache()

            stats["duplicates_removed"] += len(ids_to_delete)

    return stats


# ---------------------------------------------------------------------------
# 2. Memory Merging (semantic clusters)
# ---------------------------------------------------------------------------

def merge_clusters(dry_run=False):
    """
    When 3+ memories about the same topic exist (semantic distance < 0.8),
    create a single consolidated memory combining key information and delete
    the originals.

    Uses brain.recall() to find clusters per collection.

    Returns:
        dict with 'clusters_merged' count and 'details'.
    """
    stats = {"clusters_merged": 0, "details": []}
    merged_ids = set()  # track already-merged IDs globally

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        if len(memories) < 3:
            continue

        col = brain.collections[col_name]

        for mem in memories:
            if mem["id"] in merged_ids:
                continue

            # Use brain.recall to find semantically similar memories
            results = brain.recall(
                mem["document"],
                collections=[col_name],
                n=10,
            )

            # Filter to close matches (distance < 0.8) excluding already-merged
            cluster = []
            for r in results:
                if r["id"] in merged_ids:
                    continue
                dist = r.get("distance")
                if dist is not None and dist < 0.8:
                    cluster.append(r)

            if len(cluster) < 3:
                continue

            # Build consolidated text from unique sentences
            seen_sentences = set()
            consolidated_parts = []
            max_importance = 0.0
            all_tags = set()
            total_access = 0

            for item in cluster:
                imp = item["metadata"].get("importance", 0.5)
                max_importance = max(max_importance, imp)
                total_access += item["metadata"].get("access_count", 0)
                for t in _get_tags(item["metadata"]):
                    all_tags.add(t)

                # Extract unique content (sentence-level dedup)
                sentences = re.split(r"[.!?\n]+", item["document"])
                for s in sentences:
                    s_norm = _normalize_text(s)
                    if len(s_norm) > 10 and s_norm not in seen_sentences:
                        seen_sentences.add(s_norm)
                        consolidated_parts.append(s.strip())

            consolidated_text = ". ".join(consolidated_parts)
            # Trim to reasonable length
            if len(consolidated_text) > 2000:
                consolidated_text = consolidated_text[:2000] + "..."

            ids_to_delete = [item["id"] for item in cluster]
            for mid in ids_to_delete:
                merged_ids.add(mid)

            stats["details"].append({
                "collection": col_name,
                "original_count": len(cluster),
                "consolidated_preview": consolidated_text[:100],
                "removed_ids": ids_to_delete,
            })

            if not dry_run:
                # Store consolidated memory
                tags_list = list(all_tags)
                brain.store(
                    consolidated_text,
                    collection=col_name,
                    importance=min(1.0, max_importance + 0.05),
                    tags=tags_list if tags_list else None,
                    source="consolidation-merge",
                )
                # Delete originals
                col.delete(ids=ids_to_delete)
                _invalidate_memories_cache()

            stats["clusters_merged"] += 1

    return stats


# ---------------------------------------------------------------------------
# 3. Importance Decay Enhancement
# ---------------------------------------------------------------------------

def enhanced_decay(dry_run=False):
    """
    Call brain.decay_importance() then boost importance of frequently accessed
    memories. Memories with access_count > 3 get an importance floor of 0.5.

    Returns:
        dict with 'decayed' count and 'boosted' count.
    """
    stats = {"decayed": 0, "boosted": 0}

    # Standard decay
    if not dry_run:
        stats["decayed"] = brain.decay_importance()
    else:
        # In dry-run, just count how many would decay
        stats["decayed"] = 0
        now = datetime.now(timezone.utc)
        for col_name, col in brain.collections.items():
            results = col.get()
            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if results.get("metadatas") else {}
                last_accessed = meta.get("last_accessed")
                if last_accessed:
                    try:
                        last_dt = datetime.fromisoformat(
                            last_accessed.replace("Z", "+00:00")
                        )
                        if (now - last_dt).days > 0:
                            stats["decayed"] += 1
                    except (ValueError, TypeError):
                        pass

    # Boost frequently-accessed memories
    for col_name, col in brain.collections.items():
        results = col.get()
        for i, mem_id in enumerate(results.get("ids", [])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            access_count = meta.get("access_count", 0)
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except (ValueError, TypeError):
                    access_count = 0

            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            if access_count > 3 and importance < 0.5:
                stats["boosted"] += 1
                if not dry_run:
                    meta["importance"] = 0.5
                    doc = results["documents"][i] if results.get("documents") else ""
                    col.upsert(
                        ids=[mem_id],
                        documents=[doc],
                        metadatas=[meta],
                    )

    return stats


# ---------------------------------------------------------------------------
# 4. Noise Pruning
# ---------------------------------------------------------------------------

# Patterns that indicate noise memories
NOISE_PATTERNS = [
    (r"^Prediction:\s", 0.5),          # "Prediction: ..." with importance < 0.5
    (r"^Outcome:\s", 0.5),             # "Outcome: ..." with importance < 0.5
    (r"^World model updated:\s", None), # Always remove (unless protected)
    (r"^Attention broadcast:\s", None), # Always remove (unless protected)
    (r"^Meta-cognition: System initialized", None),  # Always remove (unless protected)
]


def prune_noise(dry_run=False):
    """
    Remove memories matching noise patterns.

    Rules:
      - "Prediction: ..." with importance < 0.5
      - "Outcome: ..." with importance < 0.5
      - "World model updated: ..." (always, unless protected)
      - "Attention broadcast: ..." (always, unless protected)
      - "Meta-cognition: System initialized..." (always, unless protected)

    Protected: memories tagged "critical" or "genesis" are kept.

    Returns:
        dict with 'pruned' count and 'details'.
    """
    stats = {"pruned": 0, "details": []}

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        if not memories:
            continue

        col = brain.collections[col_name]
        ids_to_delete = []

        for mem in memories:
            doc = mem["document"]
            meta = mem["metadata"]

            # Skip protected memories
            if _has_protected_tag(meta):
                continue

            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            for pattern, threshold in NOISE_PATTERNS:
                if re.search(pattern, doc):
                    should_delete = False
                    if threshold is None:
                        # Always delete (unless protected, already checked)
                        should_delete = True
                    elif importance < threshold:
                        should_delete = True

                    if should_delete:
                        ids_to_delete.append(mem["id"])
                        stats["details"].append({
                            "collection": col_name,
                            "id": mem["id"],
                            "preview": doc[:80],
                            "pattern": pattern,
                        })
                        break  # Only match first pattern

        if ids_to_delete:
            if not dry_run:
                col.delete(ids=ids_to_delete)
                _invalidate_memories_cache()
            stats["pruned"] += len(ids_to_delete)

    return stats


# ---------------------------------------------------------------------------
# 5. Stale Memory Archive
# ---------------------------------------------------------------------------

def archive_stale(days=30, importance_threshold=0.3, dry_run=False):
    """
    Move memories not accessed in 30+ days with importance < 0.3 to a JSON
    archive file instead of deleting them.

    Returns:
        dict with 'archived' count.
    """
    stats = {"archived": 0, "details": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    archive_entries = _load_archive()

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        if not memories:
            continue

        col = brain.collections[col_name]
        ids_to_archive = []

        for mem in memories:
            meta = mem["metadata"]

            # Skip protected
            if _has_protected_tag(meta):
                continue

            last_accessed = meta.get("last_accessed", "")
            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            if last_accessed and last_accessed < cutoff and importance < importance_threshold:
                archive_entry = {
                    "id": mem["id"],
                    "document": mem["document"],
                    "metadata": meta,
                    "collection": col_name,
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                }
                archive_entries.append(archive_entry)
                ids_to_archive.append(mem["id"])
                stats["details"].append({
                    "collection": col_name,
                    "id": mem["id"],
                    "preview": mem["document"][:60],
                    "importance": importance,
                    "last_accessed": last_accessed[:10],
                })

        if ids_to_archive:
            if not dry_run:
                col.delete(ids=ids_to_archive)
                _invalidate_memories_cache()
            stats["archived"] += len(ids_to_archive)

    if not dry_run and stats["archived"] > 0:
        _save_archive(archive_entries)

    return stats


# ---------------------------------------------------------------------------
# 6. Attention-Guided Consolidation (GWT Integration)
# ---------------------------------------------------------------------------

# Salience thresholds
SALIENCE_HIGH = 0.6       # Memories above this resist decay entirely
SALIENCE_MEDIUM = 0.3     # Partial decay resistance
PRUNE_SALIENCE_CEILING = 0.2   # Only prune if salience below this
PRUNE_ACCESS_CEILING = 2       # And access count at or below this
PRUNE_AGE_FLOOR_DAYS = 14      # And older than this many days


def _get_spotlight_contents():
    """Get current spotlight items from the attention system.

    Returns:
        List of spotlight item dicts (content, salience, source, etc.)
        Empty list if spotlight is empty or unavailable.
    """
    try:
        ranked = sorted(
            attention.items.values(),
            key=lambda x: x.salience(),
            reverse=True,
        )
        return [item.to_dict() for item in ranked[:attention.capacity]]
    except Exception:
        return []


def _compute_spotlight_salience(memory_text, spotlight_items):
    """Compute how salient a brain memory is relative to the current spotlight.

    Uses word-overlap scoring (fast, no embeddings) weighted by the spotlight
    item's own salience. A memory that overlaps with high-salience spotlight
    items scores higher than one overlapping with low-salience items.

    Args:
        memory_text: The memory document text
        spotlight_items: List of spotlight item dicts (from _get_spotlight_contents)

    Returns:
        Float 0.0-1.0 — composite spotlight salience for this memory
    """
    if not spotlight_items or not memory_text:
        return 0.0

    mem_words = set(memory_text.lower().split())
    if not mem_words:
        return 0.0

    weighted_overlap_sum = 0.0
    total_weight = 0.0

    for item in spotlight_items:
        item_salience = item.get("salience", 0.5)
        item_words = set(item.get("content", "").lower().split())
        if not item_words:
            continue

        overlap = len(mem_words & item_words)
        if overlap == 0:
            continue

        # Overlap normalized by the smaller set
        overlap_score = overlap / min(len(mem_words), len(item_words))
        # Weight by the spotlight item's own salience
        weighted_overlap_sum += overlap_score * item_salience
        total_weight += item_salience

    if total_weight == 0:
        return 0.0

    raw = weighted_overlap_sum / total_weight
    return round(min(1.0, raw), 4)


def attention_guided_prune(dry_run=False):
    """
    Prune memories that are:
      1. Low spotlight salience (not relevant to current attention)
      2. Low access count (not frequently retrieved)
      3. Old (not recently created or accessed)
      4. Low importance (not marked as valuable)

    All four conditions must be met — this is a conservative pruner that only
    removes memories the system has clearly moved past.

    Protected memories (critical/genesis tags) are never pruned.

    Returns:
        dict with 'pruned' count, 'spared_by_salience' count, and details.
    """
    stats = {
        "pruned": 0,
        "spared_by_salience": 0,
        "candidates_evaluated": 0,
        "spotlight_items": 0,
        "details": [],
    }

    spotlight = _get_spotlight_contents()
    stats["spotlight_items"] = len(spotlight)

    if not spotlight:
        return stats

    now = datetime.now(timezone.utc)
    age_cutoff = now - timedelta(days=PRUNE_AGE_FLOOR_DAYS)

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        if not memories:
            continue

        col = brain.collections[col_name]
        ids_to_delete = []

        for mem in memories:
            meta = mem["metadata"]
            doc = mem["document"]

            if _has_protected_tag(meta):
                continue

            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            access_count = meta.get("access_count", 0)
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except (ValueError, TypeError):
                    access_count = 0

            last_accessed = meta.get("last_accessed", "")
            created_at = meta.get("created_at", "")

            most_recent = last_accessed or created_at
            if not most_recent:
                continue

            try:
                most_recent_dt = datetime.fromisoformat(
                    most_recent.replace("Z", "+00:00")
                )
                if most_recent_dt.tzinfo is None:
                    most_recent_dt = most_recent_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if most_recent_dt > age_cutoff:
                continue
            if access_count > PRUNE_ACCESS_CEILING:
                continue
            if importance > 0.4:
                continue

            stats["candidates_evaluated"] += 1

            salience = _compute_spotlight_salience(doc, spotlight)

            if salience >= PRUNE_SALIENCE_CEILING:
                stats["spared_by_salience"] += 1
                continue

            ids_to_delete.append(mem["id"])
            stats["details"].append({
                "collection": col_name,
                "id": mem["id"],
                "preview": doc[:80],
                "importance": round(importance, 3),
                "access_count": access_count,
                "salience": salience,
                "age_days": round((now - most_recent_dt).total_seconds() / 86400, 1),
            })

        if ids_to_delete:
            if not dry_run:
                col.delete(ids=ids_to_delete)
                _invalidate_memories_cache()
            stats["pruned"] += len(ids_to_delete)

    return stats


def attention_guided_decay(dry_run=False):
    """
    Enhanced decay that respects attention salience.

    Modulates the decay rate by spotlight salience:
      - High salience (>0.6): NO decay + small importance boost
      - Medium salience (0.3-0.6): 50% decay rate
      - Low salience (<0.3): Full decay rate

    Returns:
        dict with counts of decayed, resisted, boosted memories.
    """
    stats = {
        "decayed": 0,
        "resisted": 0,
        "salience_boosted": 0,
        "spotlight_items": 0,
    }

    spotlight = _get_spotlight_contents()
    stats["spotlight_items"] = len(spotlight)

    now = datetime.now(timezone.utc)
    DECAY_RATE = 0.01

    for col_name, col in brain.collections.items():
        try:
            results = col.get()
        except Exception:
            continue

        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        for i, mem_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            doc = docs[i] if i < len(docs) else ""

            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            last_accessed = meta.get("last_accessed")
            if not last_accessed:
                continue

            try:
                last_dt = datetime.fromisoformat(
                    last_accessed.replace("Z", "+00:00")
                )
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            days_since = (now - last_dt).total_seconds() / 86400.0
            if days_since <= 0:
                continue

            salience = _compute_spotlight_salience(doc, spotlight) if spotlight else 0.0

            if salience >= SALIENCE_HIGH:
                effective_decay = 0.0
                salience_boost = min(0.05, salience * 0.05)
                if importance < 0.9 and salience_boost > 0.005:
                    new_importance = min(0.95, importance + salience_boost)
                    if not dry_run:
                        meta["importance"] = round(new_importance, 4)
                        meta["salience_boosted_at"] = now.isoformat()
                        meta["spotlight_salience"] = salience
                        col.upsert(ids=[mem_id], documents=[doc], metadatas=[meta])
                    stats["salience_boosted"] += 1
                stats["resisted"] += 1
                continue
            elif salience >= SALIENCE_MEDIUM:
                effective_decay = DECAY_RATE * 0.5
                stats["resisted"] += 1
            else:
                effective_decay = DECAY_RATE

            decay_amount = effective_decay * days_since
            new_importance = max(0.1, importance - decay_amount)

            if new_importance < importance - 0.001:
                stats["decayed"] += 1
                if not dry_run:
                    meta["importance"] = round(new_importance, 4)
                    meta["spotlight_salience"] = salience
                    meta["attention_decay_at"] = now.isoformat()
                    col.upsert(ids=[mem_id], documents=[doc], metadatas=[meta])

    return stats


def gwt_broadcast_survivors(top_n=3):
    """
    After consolidation, broadcast the highest-value surviving memories
    back to the attention spotlight (GWT re-entry mechanism).

    Args:
        top_n: How many memories to promote to spotlight

    Returns:
        List of promoted memory previews
    """
    spotlight_contents = set()
    for item in attention.items.values():
        spotlight_contents.add(item.content.lower().strip()[:100])

    candidates = []
    now = datetime.now(timezone.utc)
    recency_window = timedelta(days=7)

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        for mem in memories:
            meta = mem["metadata"]
            doc = mem["document"]

            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            access_count = meta.get("access_count", 0)
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except (ValueError, TypeError):
                    access_count = 0

            last_accessed = meta.get("last_accessed", "")
            if not last_accessed:
                continue

            try:
                la_dt = datetime.fromisoformat(
                    last_accessed.replace("Z", "+00:00")
                )
                if la_dt.tzinfo is None:
                    la_dt = la_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if now - la_dt > recency_window:
                continue

            if doc.lower().strip()[:100] in spotlight_contents:
                continue

            score = importance * (1.0 + math.log1p(access_count))
            candidates.append((score, doc, importance, access_count, col_name))

    candidates.sort(key=lambda x: x[0], reverse=True)

    promoted = []
    for score, doc, importance, access_count, col_name in candidates[:top_n]:
        preview = doc[:200]
        attention.submit(
            content=f"[consolidated] {preview}",
            source=f"consolidation/{col_name}",
            importance=importance,
            relevance=min(1.0, importance + 0.1),
            boost=0.2,
        )
        promoted.append({
            "collection": col_name,
            "preview": doc[:80],
            "score": round(score, 3),
            "importance": round(importance, 3),
        })

    return promoted


def salience_report():
    """
    Generate a report showing spotlight salience for all brain memories.

    Returns:
        dict with distribution info and top/bottom memories by salience.
    """
    spotlight = _get_spotlight_contents()
    if not spotlight:
        return {"error": "Spotlight is empty — no salience data available"}

    all_scored = []

    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        for mem in memories:
            salience = _compute_spotlight_salience(mem["document"], spotlight)
            importance = mem["metadata"].get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5

            access_count = mem["metadata"].get("access_count", 0)
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except (ValueError, TypeError):
                    access_count = 0

            all_scored.append({
                "collection": col_name,
                "id": mem["id"],
                "preview": mem["document"][:80],
                "salience": salience,
                "importance": round(importance, 3),
                "access_count": access_count,
            })

    if not all_scored:
        return {"error": "No memories to score"}

    all_scored.sort(key=lambda x: x["salience"], reverse=True)
    saliences = [m["salience"] for m in all_scored]

    high = sum(1 for s in saliences if s >= SALIENCE_HIGH)
    medium = sum(1 for s in saliences if SALIENCE_MEDIUM <= s < SALIENCE_HIGH)
    low = sum(1 for s in saliences if 0 < s < SALIENCE_MEDIUM)
    zero = sum(1 for s in saliences if s == 0)

    return {
        "total_memories": len(all_scored),
        "spotlight_items": len(spotlight),
        "distribution": {
            "high_salience": high,
            "medium_salience": medium,
            "low_salience": low,
            "zero_salience": zero,
        },
        "avg_salience": round(sum(saliences) / len(saliences), 4),
        "top_salient": all_scored[:10],
        "bottom_salient": [m for m in all_scored[-10:] if m["salience"] == 0][:5],
    }


# ---------------------------------------------------------------------------
# 7. Stats
# ---------------------------------------------------------------------------

def get_consolidation_stats():
    """
    Gather comprehensive stats about memory state.

    Returns:
        dict with collection counts, archive size, potential duplicates, etc.
    """
    brain_stats = brain.stats()

    # Count archive
    archive = _load_archive()
    archive_count = len(archive)

    # Count potential noise
    noise_count = 0
    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        for mem in memories:
            doc = mem["document"]
            meta = mem["metadata"]
            if _has_protected_tag(meta):
                continue
            importance = meta.get("importance", 0.5)
            if isinstance(importance, str):
                try:
                    importance = float(importance)
                except (ValueError, TypeError):
                    importance = 0.5
            for pattern, threshold in NOISE_PATTERNS:
                if re.search(pattern, doc):
                    if threshold is None or importance < threshold:
                        noise_count += 1
                        break

    # Count potential duplicates
    dup_count = 0
    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        prefix_groups = {}
        for mem in memories:
            prefix = _normalize_text(mem["document"])[:100]
            if prefix:
                prefix_groups.setdefault(prefix, []).append(mem)
        for group in prefix_groups.values():
            if len(group) > 1:
                dup_count += len(group) - 1

    # Count stale
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    stale_count = 0
    for col_name in ALL_COLLECTIONS:
        memories = _get_all_memories(col_name)
        for mem in memories:
            meta = mem["metadata"]
            la = meta.get("last_accessed", "")
            imp = meta.get("importance", 0.5)
            if isinstance(imp, str):
                try:
                    imp = float(imp)
                except (ValueError, TypeError):
                    imp = 0.5
            if la and la < cutoff and imp < 0.3:
                stale_count += 1

    # Attention salience snapshot
    spotlight = _get_spotlight_contents()
    salience_info = {"spotlight_items": len(spotlight)}
    if spotlight:
        salience_scores = []
        for col_name in ALL_COLLECTIONS:
            memories = _get_all_memories(col_name)
            for mem in memories:
                s = _compute_spotlight_salience(mem["document"], spotlight)
                salience_scores.append(s)
        if salience_scores:
            salience_info["avg_salience"] = round(
                sum(salience_scores) / len(salience_scores), 4
            )
            salience_info["high_salience_count"] = sum(
                1 for s in salience_scores if s >= SALIENCE_HIGH
            )

    return {
        "brain": brain_stats,
        "archive_count": archive_count,
        "potential_noise": noise_count,
        "potential_duplicates": dup_count,
        "stale_archivable": stale_count,
        "attention": salience_info,
    }


# ---------------------------------------------------------------------------
# 8. Integration Hook
# ---------------------------------------------------------------------------

def run_consolidation():
    """
    Run full consolidation pipeline with attention-guided phases:
      1. Deduplication
      2. Noise pruning
      3. Importance decay + access boost
      4. Stale memory archival
      5. Attention-guided decay (salience-modulated)
      6. Attention-guided pruning (low-salience + low-access + old)
      7. GWT broadcast survivors (re-entry to spotlight)

    Intended to be called from cron or other automation.

    Returns:
        dict with stats from each phase.
    """
    results = {}

    print("[consolidation] Phase 1: Deduplication...")
    results["dedup"] = deduplicate(dry_run=False)
    print(f"  Removed {results['dedup']['duplicates_removed']} duplicates")

    print("[consolidation] Phase 2: Noise pruning...")
    results["prune"] = prune_noise(dry_run=False)
    print(f"  Pruned {results['prune']['pruned']} noise memories")

    print("[consolidation] Phase 3: Importance decay + access boost...")
    results["decay"] = enhanced_decay(dry_run=False)
    print(f"  Decayed {results['decay']['decayed']}, boosted {results['decay']['boosted']}")

    print("[consolidation] Phase 4: Stale memory archival...")
    results["archive"] = archive_stale(dry_run=False)
    print(f"  Archived {results['archive']['archived']} stale memories")

    print("[consolidation] Phase 5: Attention-guided decay (GWT salience)...")
    results["attention_decay"] = attention_guided_decay(dry_run=False)
    ad = results["attention_decay"]
    print(f"  Decayed {ad['decayed']}, resisted {ad['resisted']}, "
          f"salience-boosted {ad['salience_boosted']} "
          f"(spotlight: {ad['spotlight_items']} items)")

    print("[consolidation] Phase 6: Attention-guided pruning...")
    results["attention_prune"] = attention_guided_prune(dry_run=False)
    ap = results["attention_prune"]
    print(f"  Pruned {ap['pruned']}, spared {ap['spared_by_salience']} by salience "
          f"(evaluated {ap['candidates_evaluated']})")

    print("[consolidation] Phase 7: GWT broadcast survivors...")
    results["gwt_promoted"] = gwt_broadcast_survivors(top_n=3)
    print(f"  Promoted {len(results['gwt_promoted'])} memories to spotlight")
    for p in results["gwt_promoted"]:
        print(f"    [{p['collection']}] {p['preview'][:60]} (score={p['score']})")

    # Summary
    total_actions = (
        results["dedup"]["duplicates_removed"]
        + results["prune"]["pruned"]
        + results["decay"]["decayed"]
        + results["decay"]["boosted"]
        + results["archive"]["archived"]
        + results["attention_decay"]["decayed"]
        + results["attention_decay"]["salience_boosted"]
        + results["attention_prune"]["pruned"]
        + len(results["gwt_promoted"])
    )
    results["total_actions"] = total_actions
    print(f"[consolidation] Complete. Total actions: {total_actions}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "consolidate":
        results = run_consolidation()
        print(json.dumps(results, indent=2, default=str))

    elif cmd == "dedup":
        results = deduplicate(dry_run=False)
        print(f"Deduplication complete: {results['duplicates_removed']} duplicates removed")
        if results["groups"]:
            for g in results["groups"][:10]:
                print(f"  [{g['collection']}] prefix=\"{g['prefix']}\" kept={g['kept']} removed={len(g['removed'])}")

    elif cmd == "merge":
        results = merge_clusters(dry_run=False)
        print(f"Merge complete: {results['clusters_merged']} clusters merged")
        for d in results["details"][:10]:
            print(f"  [{d['collection']}] {d['original_count']} -> 1: {d['consolidated_preview']}")

    elif cmd == "prune":
        results = prune_noise(dry_run=False)
        print(f"Noise pruning complete: {results['pruned']} memories pruned")
        for d in results["details"][:10]:
            print(f"  [{d['collection']}] {d['preview']}")

    elif cmd == "archive":
        results = archive_stale(dry_run=False)
        print(f"Archival complete: {results['archived']} memories archived to {ARCHIVE_FILE}")
        for d in results["details"][:10]:
            print(f"  [{d['collection']}] {d['preview']} (imp={d['importance']}, last={d['last_accessed']})")

    elif cmd == "attention-prune":
        results = attention_guided_prune(dry_run=False)
        print(f"Attention-guided prune: {results['pruned']} pruned, "
              f"{results['spared_by_salience']} spared by salience "
              f"(spotlight: {results['spotlight_items']} items)")
        for d in results["details"][:10]:
            print(f"  [{d['collection']}] {d['preview']} "
                  f"(sal={d['salience']}, imp={d['importance']}, "
                  f"age={d['age_days']}d, acc={d['access_count']})")

    elif cmd == "attention-decay":
        results = attention_guided_decay(dry_run=False)
        print(f"Attention-guided decay: decayed={results['decayed']}, "
              f"resisted={results['resisted']}, "
              f"salience-boosted={results['salience_boosted']} "
              f"(spotlight: {results['spotlight_items']} items)")

    elif cmd == "salience":
        report = salience_report()
        if "error" in report:
            print(report["error"])
        else:
            print(f"=== Salience Report ({report['total_memories']} memories, "
                  f"{report['spotlight_items']} spotlight items) ===")
            d = report["distribution"]
            print(f"  High salience (>={SALIENCE_HIGH}): {d['high_salience']}")
            print(f"  Medium ({SALIENCE_MEDIUM}-{SALIENCE_HIGH}): {d['medium_salience']}")
            print(f"  Low (>0, <{SALIENCE_MEDIUM}): {d['low_salience']}")
            print(f"  Zero salience: {d['zero_salience']}")
            print(f"  Average: {report['avg_salience']}")
            if report["top_salient"]:
                print("\nTop salient memories:")
                for m in report["top_salient"][:5]:
                    print(f"  [{m['collection']}] sal={m['salience']} imp={m['importance']} "
                          f"acc={m['access_count']} {m['preview'][:60]}")

    elif cmd == "gwt-broadcast":
        promoted = gwt_broadcast_survivors(top_n=3)
        if promoted:
            print(f"GWT broadcast: promoted {len(promoted)} memories to spotlight")
            for p in promoted:
                print(f"  [{p['collection']}] score={p['score']} {p['preview'][:60]}")
        else:
            print("GWT broadcast: no memories to promote")

    elif cmd == "stats":
        stats = get_consolidation_stats()
        print("=== Memory Consolidation Stats ===")
        print(f"Total memories: {stats['brain']['total_memories']}")
        print(f"Archived: {stats['archive_count']}")
        print(f"Potential noise: {stats['potential_noise']}")
        print(f"Potential duplicates: {stats['potential_duplicates']}")
        print(f"Stale (archivable): {stats['stale_archivable']}")
        attn = stats.get("attention", {})
        print(f"\nAttention spotlight: {attn.get('spotlight_items', 0)} items")
        if "avg_salience" in attn:
            print(f"  Avg memory salience: {attn['avg_salience']}")
            print(f"  High-salience memories: {attn.get('high_salience_count', 0)}")
        print("\nCollections:")
        for name, count in stats["brain"]["collections"].items():
            print(f"  {name}: {count}")

    elif cmd == "dry-run":
        print("=== DRY RUN (no changes will be made) ===\n")

        print("1. Deduplication preview:")
        dedup_stats = deduplicate(dry_run=True)
        print(f"   Would remove {dedup_stats['duplicates_removed']} duplicates")
        for g in dedup_stats["groups"][:5]:
            print(f"     [{g['collection']}] \"{g['prefix']}\" - {len(g['removed'])} copies")

        print("\n2. Noise pruning preview:")
        prune_stats = prune_noise(dry_run=True)
        print(f"   Would prune {prune_stats['pruned']} noise memories")
        for d in prune_stats["details"][:5]:
            print(f"     [{d['collection']}] {d['preview']}")

        print("\n3. Decay + boost preview:")
        decay_stats = enhanced_decay(dry_run=True)
        print(f"   Would decay {decay_stats['decayed']} memories")
        print(f"   Would boost {decay_stats['boosted']} frequently-accessed memories")

        print("\n4. Archive preview:")
        archive_stats = archive_stale(dry_run=True)
        print(f"   Would archive {archive_stats['archived']} stale memories")
        for d in archive_stats["details"][:5]:
            print(f"     [{d['collection']}] {d['preview']} (imp={d['importance']})")

        print("\n5. Attention-guided decay preview:")
        attn_decay_stats = attention_guided_decay(dry_run=True)
        print(f"   Would decay {attn_decay_stats['decayed']} memories")
        print(f"   Would resist {attn_decay_stats['resisted']} (salience protection)")
        print(f"   Would salience-boost {attn_decay_stats['salience_boosted']}")
        print(f"   Spotlight items: {attn_decay_stats['spotlight_items']}")

        print("\n6. Attention-guided prune preview:")
        attn_prune_stats = attention_guided_prune(dry_run=True)
        print(f"   Would prune {attn_prune_stats['pruned']} low-salience memories")
        print(f"   Would spare {attn_prune_stats['spared_by_salience']} by salience")
        for d in attn_prune_stats["details"][:5]:
            print(f"     [{d['collection']}] sal={d['salience']} imp={d['importance']} "
                  f"age={d['age_days']}d {d['preview'][:50]}")

        total = (
            dedup_stats["duplicates_removed"]
            + prune_stats["pruned"]
            + decay_stats["decayed"]
            + decay_stats["boosted"]
            + archive_stats["archived"]
            + attn_decay_stats["decayed"]
            + attn_decay_stats["salience_boosted"]
            + attn_prune_stats["pruned"]
        )
        print(f"\n=== Total potential actions: {total} ===")

    else:
        print(f"Unknown command: {cmd}")
        print("Valid commands: consolidate, dedup, merge, prune, archive, "
              "attention-prune, attention-decay, salience, gwt-broadcast, "
              "stats, dry-run")
        sys.exit(1)


if __name__ == "__main__":
    main()

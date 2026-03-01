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
# 5.5. Memory Caps — Enforce per-collection size limits
# ---------------------------------------------------------------------------

# Soft caps per collection (total target ~2000)
COLLECTION_CAPS = {
    "clarvis-learnings": 600,
    "clarvis-memories": 400,
    "clarvis-episodes": 300,
    "autonomous-learning": 300,
    "clarvis-goals": 200,
    "clarvis-context": 200,
    "clarvis-preferences": 200,
    "clarvis-procedures": 200,
    # No cap (small, stable):
    # "clarvis-identity", "clarvis-infrastructure"
}

PROTECTED_TAGS = ("genesis", "critical", "identity")


def enforce_memory_caps(dry_run=False):
    """
    Enforce per-collection memory caps by archiving lowest-scored excess.

    Scoring formula: importance * recency * log(access_count + 1)
    where recency = 1 / (1 + days_since_access).

    Protected tags (genesis, critical, identity) are never archived.

    Returns:
        dict with 'archived' count, 'details' list, per-collection breakdown.
    """
    stats = {
        "archived": 0,
        "collections": {},
        "details": [],
    }

    now = datetime.now(timezone.utc)
    archive_entries = _load_archive()

    for col_name, cap in COLLECTION_CAPS.items():
        memories = _get_all_memories(col_name)
        count = len(memories)
        stats["collections"][col_name] = {"count": count, "cap": cap, "excess": 0}

        if count <= cap:
            continue

        excess = count - cap
        stats["collections"][col_name]["excess"] = excess

        # Score each memory (higher = more worth keeping)
        scored = []
        for mem in memories:
            meta = mem["metadata"]

            # Never archive protected
            if _has_protected_tag(meta, protected=PROTECTED_TAGS):
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

            last_accessed = meta.get("last_accessed", meta.get("created_at", ""))
            days_since = 1.0
            if last_accessed:
                try:
                    la_dt = datetime.fromisoformat(
                        last_accessed.replace("Z", "+00:00")
                    )
                    if la_dt.tzinfo is None:
                        la_dt = la_dt.replace(tzinfo=timezone.utc)
                    days_since = max(0.1, (now - la_dt).total_seconds() / 86400.0)
                except (ValueError, TypeError):
                    pass

            recency = 1.0 / (1.0 + days_since)
            score = importance * recency * math.log(access_count + 1 + 1)  # +1 to avoid log(0)

            scored.append((score, mem))

        # Sort ascending — lowest scores get archived first
        scored.sort(key=lambda x: x[0])

        # Archive the lowest-scored excess
        ids_to_archive = []
        for score, mem in scored[:excess]:
            archive_entries.append({
                "id": mem["id"],
                "document": mem["document"],
                "metadata": mem["metadata"],
                "collection": col_name,
                "archived_at": now.isoformat(),
                "archive_reason": "memory_cap",
                "retention_score": round(score, 4),
            })
            ids_to_archive.append(mem["id"])
            stats["details"].append({
                "collection": col_name,
                "id": mem["id"],
                "preview": mem["document"][:60],
                "score": round(score, 4),
            })

        if ids_to_archive:
            if not dry_run:
                col = brain.collections[col_name]
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
# 7. Sleep-Cycle Episodic→Semantic Consolidation
# ---------------------------------------------------------------------------
#
# Inspired by:
# - LightMem (arXiv 2510.18866): offline "sleep-time" consolidation decoupled
#   from online inference, 3-tier sensory→short→long memory, 30x token savings
# - Letta Sleep-time Compute (arXiv 2504.13171): rethink_memory transforms
#   raw context into "learned context" during offline phases, 5x compute reduction
# - MemAgent (ICLR 2026): fixed-size memory panel with overwrite strategy,
#   segmented read→write→aggregate, O(N) complexity
#
# During Clarvis "sleep" (02:45 cron), episodic memories from active tasks
# are periodically consolidated into semantic knowledge in clarvis-learnings.
# This mirrors biological sleep-cycle consolidation: hippocampal replays
# (episodes) get compressed into neocortical schemas (semantic learnings).

SLEEP_CONSOLIDATION_FILE = os.path.join(DATA_DIR, "sleep_consolidation_log.json")

# Minimum episodes before consolidation triggers
SLEEP_MIN_EPISODES = 5
# Max semantic learnings produced per sleep cycle
SLEEP_MAX_LEARNINGS = 10
# Similarity threshold for grouping episodes into themes
SLEEP_THEME_DISTANCE = 0.85


def _load_sleep_log():
    """Load sleep consolidation history."""
    if os.path.exists(SLEEP_CONSOLIDATION_FILE):
        try:
            with open(SLEEP_CONSOLIDATION_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"cycles": [], "total_learnings": 0, "episodes_consolidated": 0}
    return {"cycles": [], "total_learnings": 0, "episodes_consolidated": 0}


def _save_sleep_log(log):
    """Save sleep consolidation history (cap at 100 cycles)."""
    log["cycles"] = log["cycles"][-100:]
    with open(SLEEP_CONSOLIDATION_FILE, "w") as f:
        json.dump(log, f, indent=2)


def _extract_episode_theme(episodes):
    """Extract common theme from a cluster of episodes.

    Uses pattern-matching on task descriptions to identify recurring
    domains, outcomes, and strategies — no LLM needed.
    """
    domain_keywords = {
        "memory": ["brain", "memory", "recall", "store", "retrieval", "episodic", "consolidat"],
        "infrastructure": ["cron", "schedule", "heartbeat", "health", "monitor", "backup", "gateway"],
        "reasoning": ["reasoning", "chain", "thought", "analysis", "synthesis", "metacog"],
        "research": ["research", "paper", "arxiv", "study", "discovery", "survey"],
        "code": ["script", "function", "implement", "build", "fix", "refactor", "test"],
        "metrics": ["phi", "capability", "score", "benchmark", "metric", "performance"],
        "self-model": ["self", "reflection", "awareness", "identity", "model", "confidence"],
    }

    tasks = [ep.get("task", "").lower() for ep in episodes]
    combined = " ".join(tasks)

    # Count domain hits
    domain_scores = {}
    for domain, keywords in domain_keywords.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            domain_scores[domain] = score

    if not domain_scores:
        return "general"

    return max(domain_scores, key=domain_scores.get)


def _synthesize_semantic_learning(theme, episodes):
    """Synthesize a semantic learning from a cluster of related episodes.

    This is the core "rethink_memory" operation (Letta-inspired):
    transform raw episodic context into learned, generalized context.

    Uses rule-based abstraction (no LLM) — extracts success/failure patterns,
    common strategies, and risk signals.
    """
    successes = [ep for ep in episodes if ep.get("outcome") == "success"]
    failures = [ep for ep in episodes if ep.get("outcome") in ("failure", "soft_failure")]
    total = len(episodes)
    success_rate = len(successes) / total if total > 0 else 0

    # Extract unique task verbs/actions
    actions = set()
    for ep in episodes:
        task = ep.get("task", "")
        # Extract first verb-like word
        words = task.split()
        if words:
            actions.add(words[0].lower().rstrip(":"))

    actions_str = ", ".join(sorted(actions)[:5])

    # Compute average duration and confidence
    durations = [ep.get("duration_s", 0) for ep in episodes if ep.get("duration_s")]
    avg_duration = sum(durations) / len(durations) if durations else 0
    confidences = [ep.get("confidence", 0) for ep in episodes if ep.get("confidence")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Build the consolidated semantic learning
    parts = [f"[SLEEP-CONSOLIDATED] Domain: {theme} ({total} episodes)."]

    if success_rate >= 0.8:
        parts.append(f"High reliability ({success_rate:.0%} success). "
                     f"Core operations: {actions_str}.")
    elif success_rate >= 0.5:
        parts.append(f"Mixed reliability ({success_rate:.0%} success). "
                     f"Operations: {actions_str}. Review failure patterns.")
    else:
        parts.append(f"Low reliability ({success_rate:.0%} success). "
                     f"Operations: {actions_str}. Needs attention.")

    if avg_duration > 0:
        parts.append(f"Avg duration: {avg_duration:.0f}s.")

    if avg_confidence > 0:
        parts.append(f"Avg confidence: {avg_confidence:.2f}.")

    # Extract failure lessons
    if failures:
        fail_tasks = [f.get("task", "")[:50] for f in failures[:3]]
        parts.append(f"Failure cases: {'; '.join(fail_tasks)}.")

    # Extract success patterns
    if successes:
        recent_success = successes[-1]
        parts.append(f"Latest success: {recent_success.get('task', '')[:60]}.")

    return " ".join(parts)


def sleep_consolidate(dry_run=False):
    """Run sleep-cycle episodic→semantic consolidation.

    This is the "sleep phase" of the wake/sleep paradigm:
    1. Load recent unconsolidated episodes
    2. Cluster by semantic similarity into themes
    3. For each theme cluster (≥3 episodes), synthesize a semantic learning
    4. Store learning in clarvis-learnings with sleep-consolidation tag
    5. Mark source episodes as consolidated (metadata flag)

    Inspired by LightMem offline consolidation and Letta rethink_memory.

    Returns:
        dict with consolidation stats.
    """
    stats = {
        "episodes_scanned": 0,
        "themes_found": 0,
        "learnings_created": 0,
        "episodes_consolidated": 0,
        "details": [],
    }

    # Load episodes from episodic memory
    try:
        from episodic_memory import episodic
        episodes = episodic.episodes
    except Exception as e:
        print(f"[sleep] Cannot load episodic memory: {e}")
        return stats

    if len(episodes) < SLEEP_MIN_EPISODES:
        print(f"[sleep] Only {len(episodes)} episodes, need {SLEEP_MIN_EPISODES}. Skipping.")
        return stats

    # Filter to unconsolidated episodes (no sleep_consolidated flag in brain)
    # Use the last 100 episodes as working set (MemAgent-inspired fixed window)
    working_set = episodes[-100:]
    stats["episodes_scanned"] = len(working_set)

    # Check which episodes have already been sleep-consolidated
    sleep_log = _load_sleep_log()
    consolidated_ids = set()
    for cycle in sleep_log.get("cycles", []):
        for ep_id in cycle.get("episode_ids", []):
            consolidated_ids.add(ep_id)

    unconsolidated = [ep for ep in working_set if ep.get("id") not in consolidated_ids]

    if len(unconsolidated) < SLEEP_MIN_EPISODES:
        print(f"[sleep] Only {len(unconsolidated)} unconsolidated episodes. Skipping.")
        return stats

    print(f"[sleep] {len(unconsolidated)} unconsolidated episodes in working set")

    # Cluster episodes by theme (domain extraction)
    theme_clusters = {}
    for ep in unconsolidated:
        theme = _extract_episode_theme([ep])
        theme_clusters.setdefault(theme, []).append(ep)

    # Refine: also check semantic similarity within themes using brain.recall
    # (MemAgent overwrite strategy: keep only the most informative per theme)
    learnings_created = 0
    cycle_episode_ids = []

    for theme, cluster in sorted(theme_clusters.items(), key=lambda x: -len(x[1])):
        if len(cluster) < 3:
            continue
        if learnings_created >= SLEEP_MAX_LEARNINGS:
            break

        stats["themes_found"] += 1

        # Synthesize semantic learning (rethink_memory operation)
        learning_text = _synthesize_semantic_learning(theme, cluster)

        # Check if a similar learning already exists (dedup against brain)
        existing = brain.recall(learning_text, n=3, collections=["clarvis-learnings"])
        already_exists = False
        for ex in existing:
            dist = ex.get("distance")
            if dist is not None and dist < 0.5:
                already_exists = True
                break

        if already_exists:
            print(f"  [sleep] Theme '{theme}' ({len(cluster)} eps): similar learning exists, skipping")
            # Still mark episodes as consolidated to avoid re-processing
            for ep in cluster:
                cycle_episode_ids.append(ep["id"])
            stats["episodes_consolidated"] += len(cluster)
            continue

        detail = {
            "theme": theme,
            "episode_count": len(cluster),
            "learning_preview": learning_text[:120],
        }
        stats["details"].append(detail)

        if not dry_run:
            # Store the consolidated learning
            brain.store(
                learning_text,
                collection="clarvis-learnings",
                importance=0.6,  # Moderate — earned importance, not assigned
                tags=["sleep-consolidated", f"theme:{theme}",
                      f"episodes:{len(cluster)}"],
                source="sleep_consolidation",
            )
            for ep in cluster:
                cycle_episode_ids.append(ep["id"])

        learnings_created += 1
        stats["learnings_created"] += 1
        stats["episodes_consolidated"] += len(cluster)

        print(f"  [sleep] Theme '{theme}': {len(cluster)} episodes → 1 semantic learning")

    # Log this sleep cycle
    if not dry_run and (learnings_created > 0 or cycle_episode_ids):
        cycle_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episodes_scanned": stats["episodes_scanned"],
            "themes_found": stats["themes_found"],
            "learnings_created": stats["learnings_created"],
            "episodes_consolidated": stats["episodes_consolidated"],
            "episode_ids": cycle_episode_ids,
        }
        sleep_log["cycles"].append(cycle_entry)
        sleep_log["total_learnings"] += learnings_created
        sleep_log["episodes_consolidated"] += stats["episodes_consolidated"]
        _save_sleep_log(sleep_log)

    return stats


def sleep_stats():
    """Get sleep consolidation statistics."""
    log = _load_sleep_log()
    cycles = log.get("cycles", [])
    return {
        "total_cycles": len(cycles),
        "total_learnings": log.get("total_learnings", 0),
        "total_episodes_consolidated": log.get("episodes_consolidated", 0),
        "last_cycle": cycles[-1].get("timestamp", "")[:19] if cycles else "never",
    }


# ---------------------------------------------------------------------------
# 7.5. Stats
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
# 7.5. Retrieval Error Decomposition (xMemory-inspired)
# ---------------------------------------------------------------------------
# From "Beyond RAG for Agent Memory" (arXiv:2602.02007):
#   Selection Error: retrieved the WRONG memories (redundancy, missing diversity)
#   Integration Error: retrieved correct memories but failed to compose them
# We track these to diagnose retrieval quality over time.

RETRIEVAL_ERROR_FILE = os.path.join(DATA_DIR, "retrieval_errors.jsonl")


def measure_retrieval_quality(query, results, expected_useful=None):
    """Measure selection and integration error for a single retrieval.

    Args:
        query: The recall query
        results: List of recall result dicts
        expected_useful: If known, how many results were actually useful
                         (e.g., from downstream task feedback)

    Returns:
        dict with selection_error, integration_error, evidence_density metrics
    """
    if not results:
        return {"selection_error": 1.0, "integration_error": 1.0, "evidence_density": 0.0}

    # --- Selection Error: redundancy in retrieved set ---
    # High redundancy = wasted retrieval slots = selection failure
    # Measured by pairwise Jaccard similarity of result texts
    texts = [r.get("document", "")[:200].lower().split() for r in results]
    pairwise_sims = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            words_a = set(texts[i])
            words_b = set(texts[j])
            if words_a or words_b:
                jaccard = len(words_a & words_b) / max(1, len(words_a | words_b))
                pairwise_sims.append(jaccard)

    avg_redundancy = sum(pairwise_sims) / max(1, len(pairwise_sims)) if pairwise_sims else 0.0
    selection_error = avg_redundancy  # 0 = perfectly diverse, 1 = all identical

    # --- Integration Error: topic coverage vs query ---
    # Do the results collectively cover the query's key concepts?
    query_words = set(query.lower().split())
    covered_words = set()
    for text_words in texts:
        covered_words.update(set(text_words) & query_words)
    coverage = len(covered_words) / max(1, len(query_words))
    integration_error = 1.0 - coverage  # 0 = full coverage, 1 = no coverage

    # --- Evidence density: useful info per result ---
    # How many results contain query-relevant tokens?
    results_with_hits = 0
    for text_words in texts:
        hits = len(set(text_words) & query_words)
        if hits >= 2:
            results_with_hits += 1
    evidence_density = results_with_hits / max(1, len(results))

    # If we have ground truth feedback (expected_useful), refine
    if expected_useful is not None:
        actual_useful = min(expected_useful, len(results))
        selection_precision = actual_useful / max(1, len(results))
        selection_error = 1.0 - selection_precision

    metrics = {
        "selection_error": round(selection_error, 4),
        "integration_error": round(integration_error, 4),
        "evidence_density": round(evidence_density, 4),
        "redundancy": round(avg_redundancy, 4),
        "coverage": round(coverage, 4),
        "results_count": len(results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_preview": query[:100] if query else "",
    }

    # Append to tracking log
    try:
        with open(RETRIEVAL_ERROR_FILE, "a") as f:
            f.write(json.dumps(metrics) + "\n")
    except OSError:
        pass

    return metrics


def retrieval_error_report(days=7):
    """Aggregate retrieval error metrics over recent period.

    Returns:
        dict with avg selection_error, integration_error, trends
    """
    if not os.path.exists(RETRIEVAL_ERROR_FILE):
        return {"entries": 0, "message": "No retrieval error data yet"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    entries = []
    with open(RETRIEVAL_ERROR_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("timestamp", "") >= cutoff:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue

    if not entries:
        return {"entries": 0, "period_days": days}

    avg_sel = sum(e["selection_error"] for e in entries) / len(entries)
    avg_int = sum(e["integration_error"] for e in entries) / len(entries)
    avg_dens = sum(e["evidence_density"] for e in entries) / len(entries)
    avg_red = sum(e["redundancy"] for e in entries) / len(entries)
    avg_cov = sum(e["coverage"] for e in entries) / len(entries)

    return {
        "entries": len(entries),
        "period_days": days,
        "avg_selection_error": round(avg_sel, 4),
        "avg_integration_error": round(avg_int, 4),
        "avg_evidence_density": round(avg_dens, 4),
        "avg_redundancy": round(avg_red, 4),
        "avg_coverage": round(avg_cov, 4),
        "diagnosis": (
            "HIGH selection error" if avg_sel > 0.5
            else "HIGH integration error" if avg_int > 0.5
            else "HEALTHY" if avg_sel < 0.3 and avg_int < 0.3
            else "MODERATE — check redundancy and coverage"
        ),
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

    print("[consolidation] Phase 4.5: Memory caps enforcement...")
    results["caps"] = enforce_memory_caps(dry_run=False)
    print(f"  Cap-archived {results['caps']['archived']} excess memories")
    for col_name, info in results["caps"]["collections"].items():
        if info["excess"] > 0:
            print(f"    {col_name}: {info['count']}/{info['cap']} (excess: {info['excess']})")

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

    print("[consolidation] Phase 6.5: Sleep-cycle episodic→semantic consolidation...")
    results["sleep"] = sleep_consolidate(dry_run=False)
    sl = results["sleep"]
    print(f"  Scanned {sl['episodes_scanned']} episodes, "
          f"found {sl['themes_found']} themes, "
          f"created {sl['learnings_created']} semantic learnings")

    print("[consolidation] Phase 7: GWT broadcast survivors...")
    results["gwt_promoted"] = gwt_broadcast_survivors(top_n=3)
    print(f"  Promoted {len(results['gwt_promoted'])} memories to spotlight")
    for p in results["gwt_promoted"]:
        print(f"    [{p['collection']}] {p['preview'][:60]} (score={p['score']})")

    # Phase 8: Retrieval error report (diagnostic only, no mutations)
    print("[consolidation] Phase 8: Retrieval error report...")
    results["retrieval_errors"] = retrieval_error_report(days=7)
    re = results["retrieval_errors"]
    if re.get("entries", 0) > 0:
        print(f"  {re['entries']} retrievals analyzed: "
              f"sel_err={re['avg_selection_error']:.3f} "
              f"int_err={re['avg_integration_error']:.3f} "
              f"density={re['avg_evidence_density']:.3f} "
              f"→ {re['diagnosis']}")
    else:
        print("  No retrieval error data yet")

    # Summary
    total_actions = (
        results["dedup"]["duplicates_removed"]
        + results["prune"]["pruned"]
        + results["decay"]["decayed"]
        + results["decay"]["boosted"]
        + results["archive"]["archived"]
        + results["caps"]["archived"]
        + results["attention_decay"]["decayed"]
        + results["attention_decay"]["salience_boosted"]
        + results["attention_prune"]["pruned"]
        + results["sleep"]["learnings_created"]
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

    elif cmd == "caps":
        is_dry = "--dry-run" in sys.argv
        results = enforce_memory_caps(dry_run=is_dry)
        prefix = "Would archive" if is_dry else "Archived"
        print(f"{'DRY RUN: ' if is_dry else ''}Memory caps: {prefix} {results['archived']} excess memories")
        for col_name, info in results["collections"].items():
            status = "OK" if info["excess"] == 0 else f"OVER by {info['excess']}"
            print(f"  {col_name}: {info['count']}/{info['cap']} ({status})")
        if results["details"]:
            print(f"\n{'Would archive' if is_dry else 'Archived'}:")
            for d in results["details"][:15]:
                print(f"  [{d['collection']}] score={d['score']} {d['preview']}")

    elif cmd == "sleep":
        is_dry = "--dry-run" in sys.argv
        results = sleep_consolidate(dry_run=is_dry)
        prefix = "Would create" if is_dry else "Created"
        print(f"{'DRY RUN: ' if is_dry else ''}Sleep consolidation: "
              f"{prefix} {results['learnings_created']} semantic learnings "
              f"from {results['episodes_consolidated']} episodes "
              f"({results['themes_found']} themes)")
        for d in results["details"]:
            print(f"  [{d['theme']}] {d['episode_count']} eps → {d['learning_preview'][:80]}")

    elif cmd == "sleep-stats":
        ss = sleep_stats()
        print("=== Sleep Consolidation Stats ===")
        print(f"Total cycles: {ss['total_cycles']}")
        print(f"Total learnings created: {ss['total_learnings']}")
        print(f"Total episodes consolidated: {ss['total_episodes_consolidated']}")
        print(f"Last cycle: {ss['last_cycle']}")

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

    elif cmd == "retrieval-errors":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        report = retrieval_error_report(days=days)
        print(f"=== Retrieval Error Report (last {days} days) ===")
        if report.get("entries", 0) == 0:
            print("  No retrieval error data yet. Errors are tracked automatically")
            print("  when measure_retrieval_quality() is called after brain.recall().")
        else:
            print(f"  Retrievals analyzed:     {report['entries']}")
            print(f"  Avg selection error:     {report['avg_selection_error']:.4f} (0=diverse, 1=redundant)")
            print(f"  Avg integration error:   {report['avg_integration_error']:.4f} (0=full coverage, 1=none)")
            print(f"  Avg evidence density:    {report['avg_evidence_density']:.4f}")
            print(f"  Avg redundancy:          {report['avg_redundancy']:.4f}")
            print(f"  Avg coverage:            {report['avg_coverage']:.4f}")
            print(f"  Diagnosis:               {report['diagnosis']}")

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
        print("Valid commands: consolidate, dedup, merge, prune, archive, caps, "
              "attention-prune, attention-decay, salience, gwt-broadcast, "
              "sleep, sleep-stats, stats, dry-run")
        sys.exit(1)


if __name__ == "__main__":
    main()

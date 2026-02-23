#!/usr/bin/env python3
"""
Memory Consolidation & Evolution System for Clarvis

Handles:
  - Deduplication of near-duplicate memories
  - Merging of semantically similar memory clusters
  - Importance decay with access-frequency boosting
  - Noise pruning (prediction logs, attention broadcasts, etc.)
  - Archival of stale low-importance memories
  - CLI for manual and automated operation

Usage:
    python3 memory_consolidation.py consolidate   # Run full consolidation
    python3 memory_consolidation.py dedup          # Deduplicate only
    python3 memory_consolidation.py prune          # Noise prune only
    python3 memory_consolidation.py archive        # Archive stale memories
    python3 memory_consolidation.py stats          # Show memory stats
    python3 memory_consolidation.py dry-run        # Preview without changes
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain import brain, ALL_COLLECTIONS

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
    global _memories_cache, _memories_cache_gen

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
# 6. Stats
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

    return {
        "brain": brain_stats,
        "archive_count": archive_count,
        "potential_noise": noise_count,
        "potential_duplicates": dup_count,
        "stale_archivable": stale_count,
    }


# ---------------------------------------------------------------------------
# 7. Integration Hook
# ---------------------------------------------------------------------------

def run_consolidation():
    """
    Run full consolidation pipeline: dedup, noise prune, decay, archive.
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

    # Summary
    total_actions = (
        results["dedup"]["duplicates_removed"]
        + results["prune"]["pruned"]
        + results["decay"]["decayed"]
        + results["decay"]["boosted"]
        + results["archive"]["archived"]
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

    elif cmd == "stats":
        stats = get_consolidation_stats()
        print("=== Memory Consolidation Stats ===")
        print(f"Total memories: {stats['brain']['total_memories']}")
        print(f"Archived: {stats['archive_count']}")
        print(f"Potential noise: {stats['potential_noise']}")
        print(f"Potential duplicates: {stats['potential_duplicates']}")
        print(f"Stale (archivable): {stats['stale_archivable']}")
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

        total = (
            dedup_stats["duplicates_removed"]
            + prune_stats["pruned"]
            + decay_stats["decayed"]
            + decay_stats["boosted"]
            + archive_stats["archived"]
        )
        print(f"\n=== Total potential actions: {total} ===")

    else:
        print(f"Unknown command: {cmd}")
        print("Valid commands: consolidate, dedup, merge, prune, archive, stats, dry-run")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Memory Evolution — A-Mem style recall success tracking and memory refinement.

When a memory is recalled and used in a successful episode:
  - Increment `recall_success` counter in metadata
  - Boost importance slightly (successful recall = useful memory)

When a memory is contradicted or superseded:
  - Spawn a revised version with `evolved_from` linking to the original
  - Mark the original with `superseded_by`

Minimal first iteration: metadata tracking + simple evolution trigger.
"""

import logging
from datetime import datetime, timezone

_log = logging.getLogger("clarvis.brain.memory_evolution")


def record_recall_success(brain, recalled_ids):
    """Increment recall_success counter for memories that contributed to a successful task.

    Args:
        brain: ClarvisBrain instance
        recalled_ids: list of dicts with keys: id, collection
            (as extracted from recall() results)

    Returns:
        dict with updated count and any errors
    """
    updated = 0
    errors = []

    for item in recalled_ids:
        mem_id = item.get("id")
        col_name = item.get("collection")
        if not mem_id or not col_name:
            continue
        if col_name not in brain.collections:
            continue

        col = brain.collections[col_name]
        try:
            existing = col.get(ids=[mem_id])
            if not existing["ids"]:
                continue

            meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            doc = existing["documents"][0] if existing.get("documents") else ""

            # Increment recall_success counter
            recall_success = meta.get("recall_success", 0)
            if isinstance(recall_success, str):
                try:
                    recall_success = int(recall_success)
                except ValueError:
                    recall_success = 0
            recall_success += 1
            meta["recall_success"] = recall_success
            meta["last_recall_success"] = datetime.now(timezone.utc).isoformat()

            # Slight importance boost for proven-useful memories (cap at 1.0)
            current_imp = meta.get("importance", 0.5)
            if isinstance(current_imp, str):
                try:
                    current_imp = float(current_imp)
                except ValueError:
                    current_imp = 0.5
            # Diminishing boost: 0.02 first time, halves each subsequent success
            boost = 0.02 / (1 + (recall_success - 1) * 0.5)
            meta["importance"] = min(1.0, current_imp + boost)

            col.upsert(ids=[mem_id], documents=[doc], metadatas=[meta])
            updated += 1
        except Exception as e:
            errors.append(f"{col_name}/{mem_id}: {e}")

    return {"updated": updated, "errors": errors}


def evolve_memory(brain, old_id, old_collection, new_text, reason="contradiction"):
    """Create an evolved version of a memory, linking back to the original.

    The old memory gets marked with `superseded_by`, and the new memory
    gets an `evolved_from` field pointing to the original.

    Args:
        brain: ClarvisBrain instance
        old_id: ID of the memory being superseded
        old_collection: Collection of the old memory
        new_text: Updated/corrected memory text
        reason: Why the memory was evolved (contradiction, refinement, update)

    Returns:
        dict with new_id, old_id, or error
    """
    if old_collection not in brain.collections:
        return {"evolved": False, "error": f"Collection '{old_collection}' not found"}

    col = brain.collections[old_collection]

    try:
        existing = col.get(ids=[old_id])
    except Exception as e:
        return {"evolved": False, "error": f"Failed to fetch original: {e}"}

    if not existing["ids"]:
        return {"evolved": False, "error": f"Memory '{old_id}' not found"}

    old_meta = existing["metadatas"][0] if existing.get("metadatas") else {}
    old_doc = existing["documents"][0] if existing.get("documents") else ""

    # Generate new ID
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    new_id = f"{old_collection}_evolved_{ts}"

    # Build new metadata, inheriting useful fields from original
    new_meta = {
        "text": new_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_accessed": datetime.now(timezone.utc).isoformat(),
        "access_count": 0,
        "importance": min(1.0, old_meta.get("importance", 0.5) + 0.05),
        "source": f"evolution_{reason}",
        "evolved_from": old_id,
        "evolution_reason": reason,
        "recall_success": 0,
    }

    # Preserve tags from original
    if old_meta.get("tags"):
        new_meta["tags"] = old_meta["tags"]

    # Store evolved memory
    col.upsert(ids=[new_id], documents=[new_text], metadatas=[new_meta])

    # Mark original as superseded
    old_meta["superseded_by"] = new_id
    old_meta["superseded_at"] = datetime.now(timezone.utc).isoformat()
    col.upsert(ids=[old_id], documents=[old_doc], metadatas=[old_meta])

    # Link old → new in graph
    try:
        brain.add_relationship(old_id, new_id, "evolved_into",
                               source_collection=old_collection,
                               target_collection=old_collection)
    except Exception as e:
        _log.debug("Failed to link evolved edge %s -> %s: %s", old_id, new_id, e)

    # Auto-link new memory
    try:
        brain.auto_link(new_id, new_text, old_collection)
    except Exception as e:
        _log.debug("Failed to auto-link evolved memory %s: %s", new_id, e)

    brain._invalidate_cache(old_collection)

    return {
        "evolved": True,
        "new_id": new_id,
        "old_id": old_id,
        "collection": old_collection,
        "reason": reason,
    }


def find_contradictions(brain, text, collection, threshold=0.3, top_n=3):
    """Find existing memories that are highly similar but potentially contradictory.

    Detects contradiction by looking for memories with high embedding similarity
    (distance < threshold) but containing negation/opposing signals.

    This is a simple heuristic — full semantic contradiction detection would
    require an LLM call. We check for negation patterns as a cheap proxy.

    Args:
        brain: ClarvisBrain instance
        text: New memory text to check against existing memories
        collection: Which collection to search
        threshold: Max embedding distance to consider (lower = more similar)
        top_n: Number of similar memories to check

    Returns:
        list of dicts with keys: id, document, distance, contradiction_signal
    """
    import re

    if collection not in brain.collections:
        return []

    try:
        results = brain.recall(text, collections=[collection], n=top_n,
                               caller="contradiction_check")
    except Exception:
        return []

    if not results:
        return []

    # Negation/opposition patterns
    _NEGATION_WORDS = {
        "not", "no", "never", "don't", "doesn't", "didn't", "won't",
        "can't", "cannot", "shouldn't", "isn't", "aren't", "wasn't",
        "weren't", "haven't", "hasn't", "hadn't", "removed", "deprecated",
        "replaced", "obsolete", "wrong", "incorrect", "false", "broken",
    }

    def _extract_negations(t):
        words = set(re.findall(r"[a-z']+", t.lower()))
        return words & _NEGATION_WORDS

    new_negations = _extract_negations(text)

    contradictions = []
    for mem in results:
        dist = mem.get("distance")
        if dist is None or dist > threshold:
            continue

        doc = mem.get("document", "")
        old_negations = _extract_negations(doc)

        # Contradiction signal: one has negation words the other doesn't
        # (symmetric difference in negation patterns)
        neg_diff = new_negations.symmetric_difference(old_negations)
        if neg_diff:
            contradictions.append({
                "id": mem.get("id"),
                "collection": mem.get("collection", collection),
                "document": doc,
                "distance": dist,
                "contradiction_signal": sorted(neg_diff),
            })

    return contradictions

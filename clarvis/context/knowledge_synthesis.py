"""
Cross-collection knowledge synthesis for context briefs.

Queries procedures, episodes, learnings, and goals for the current task,
then bridges findings across collections into a compact synthesis section.
Targets context_relevance improvement via the 'knowledge' budget key.

Usage:
    from clarvis.context.knowledge_synthesis import synthesize_knowledge
    section = synthesize_knowledge("my task text", tier="standard")
"""

import re
import time

# Bridge collections — the 4 that contain actionable cross-domain knowledge
_BRIDGE_COLLECTIONS = [
    "clarvis-procedures",
    "clarvis-episodes",
    "clarvis-learnings",
    "clarvis-goals",
]

# Collection short names for compact output
_SHORT_NAMES = {
    "clarvis-procedures": "proc",
    "clarvis-episodes": "ep",
    "clarvis-learnings": "learn",
    "clarvis-goals": "goal",
}

# Max results per collection
_N_PER_COLLECTION = 3

# Min distance threshold — results further than this are too weak to bridge
_MAX_DISTANCE = 1.4


def _extract_task_tokens(task_text):
    """Extract meaningful tokens from task text for relevance scoring."""
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must", "ought",
        "in", "on", "at", "to", "for", "with", "by", "from", "of", "into",
        "and", "or", "but", "not", "no", "if", "then", "else", "when",
        "that", "this", "it", "its", "as", "so", "up", "out", "about",
        "file", "task", "add", "new", "use", "run", "make", "get", "set",
    }
    words = re.findall(r'[a-z_]{3,}', task_text.lower())
    return set(w for w in words if w not in stop)


def _score_hit(doc_text, task_tokens, distance):
    """Score a brain hit by task-token overlap and distance."""
    doc_words = set(re.findall(r'[a-z_]{3,}', doc_text.lower()))
    if not task_tokens:
        return 1.0 / (1.0 + distance)
    overlap = len(task_tokens & doc_words)
    token_score = overlap / len(task_tokens)
    dist_score = max(0, 1.0 - distance / 2.0)
    return 0.6 * token_score + 0.4 * dist_score


def synthesize_knowledge(current_task, tier="standard", max_chars=400):
    """Build a cross-collection knowledge synthesis section.

    Queries 4 bridge collections (procedures, episodes, learnings, goals)
    for the current task, scores results by task relevance, and formats
    cross-collection bridges as compact lines.

    Args:
        current_task: Task text to synthesize knowledge for.
        tier: "minimal" | "standard" | "full" — controls depth.
        max_chars: Maximum characters for the output section.

    Returns:
        Formatted synthesis string, or "" if no relevant bridges found.
    """
    if tier == "minimal" or not current_task:
        return ""

    try:
        from clarvis.brain import brain
    except ImportError:
        return ""

    task_tokens = _extract_task_tokens(current_task)
    n_per = _N_PER_COLLECTION if tier == "standard" else _N_PER_COLLECTION + 2

    # Query each bridge collection independently
    collection_hits = {}
    for col in _BRIDGE_COLLECTIONS:
        try:
            results = brain.recall(
                current_task,
                collections=[col],
                n=n_per,
                caller="knowledge_synthesis",
            )
            if results:
                collection_hits[col] = results
        except Exception:
            continue

    if not collection_hits:
        return ""

    # Score and rank all hits
    scored = []
    for col, hits in collection_hits.items():
        for hit in hits:
            doc = hit.get("document", hit.get("text", ""))
            dist = hit.get("distance", 1.0)
            if dist > _MAX_DISTANCE:
                continue
            score = _score_hit(doc, task_tokens, dist)
            scored.append({
                "collection": col,
                "text": doc,
                "score": score,
                "distance": dist,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        return ""

    # Identify cross-collection bridges: pairs from different collections
    # that both score above threshold
    min_score = 0.15
    relevant = [s for s in scored if s["score"] >= min_score]

    if not relevant:
        # Fall back to top hits even if low-scoring
        relevant = scored[:3]

    # Group by collection for the output
    by_col = {}
    for hit in relevant:
        col = hit["collection"]
        if col not in by_col:
            by_col[col] = []
        by_col[col].append(hit)

    # Build bridges: find connections between collections
    bridges = []
    cols_present = list(by_col.keys())
    if len(cols_present) >= 2:
        # Cross-collection synthesis: combine insights from multiple sources
        for i, col_a in enumerate(cols_present):
            for col_b in cols_present[i + 1:]:
                hit_a = by_col[col_a][0]
                hit_b = by_col[col_b][0]
                # Check if they share task-relevant tokens (bridgeable)
                words_a = set(re.findall(r'[a-z_]{3,}', hit_a["text"].lower()))
                words_b = set(re.findall(r'[a-z_]{3,}', hit_b["text"].lower()))
                shared = (words_a & words_b) - {"the", "and", "for", "with", "from", "that", "this"}
                if shared or (hit_a["score"] > 0.2 and hit_b["score"] > 0.2):
                    name_a = _SHORT_NAMES.get(col_a, col_a)
                    name_b = _SHORT_NAMES.get(col_b, col_b)
                    text_a = _truncate(hit_a["text"], 80)
                    text_b = _truncate(hit_b["text"], 80)
                    bridges.append(f"[{name_a}+{name_b}] {text_a} ↔ {text_b}")

    # Format output
    lines = []

    # Top relevant hits (compact, one per collection)
    seen_cols = set()
    for hit in relevant[:4]:
        col = hit["collection"]
        if col in seen_cols:
            continue
        seen_cols.add(col)
        name = _SHORT_NAMES.get(col, col)
        text = _truncate(hit["text"], 90)
        lines.append(f"[{name}] {text}")

    # Cross-collection bridges
    if bridges:
        for b in bridges[:2]:
            lines.append(b)

    if not lines:
        return ""

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars].rsplit("\n", 1)[0]

    return result


def _truncate(text, max_len):
    """Truncate text to max_len, breaking at word boundary."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"

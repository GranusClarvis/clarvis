#!/usr/bin/env python3
"""
Prediction Resolver — Embedding-similarity matching for unresolved predictions.

The existing auto_resolve() in confidence.py uses rigid string matching on
sanitized event names. This module adds embedding-based similarity matching
to catch near-misses where the prediction event and episode task describe
the same work but differ in wording.

Usage:
    python3 prediction_resolver.py scan          # Show unresolved + stale with best matches
    python3 prediction_resolver.py resolve        # Auto-resolve matches above threshold
    python3 prediction_resolver.py stats          # Current resolution stats + brier score
    python3 prediction_resolver.py rescue-stale   # Re-evaluate stale predictions against episodes
"""

import json
import os
import re
import sys

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
PREDICTIONS_FILE = f"{WORKSPACE}/data/calibration/predictions.jsonl"
EPISODES_FILE = f"{WORKSPACE}/data/episodes.json"

# Similarity thresholds
EMBED_THRESHOLD = 0.72       # cosine sim above this = auto-resolve
WORD_OVERLAP_THRESHOLD = 0.5 # Jaccard word overlap above this = auto-resolve
STALE_RESCUE_THRESHOLD = 0.78  # higher bar for retroactively changing stale outcomes

# Lazy-loaded embedding function
_ef = None


def _get_ef():
    """Get ONNX MiniLM embedding function (lazy singleton)."""
    global _ef
    if _ef is None:
        from clarvis.brain.constants import get_local_embedding_function
        _ef = get_local_embedding_function()
    return _ef


def _load_predictions():
    if not os.path.exists(PREDICTIONS_FILE):
        return []
    entries = []
    with open(PREDICTIONS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _save_predictions(entries):
    with open(PREDICTIONS_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _load_episodes():
    if not os.path.exists(EPISODES_FILE):
        return []
    with open(EPISODES_FILE) as f:
        return json.load(f)


def _desanitize(event: str) -> str:
    """Convert sanitized event name back to readable text."""
    if not event:
        return ""
    return re.sub(r'_+', ' ', event).strip()


def _word_set(text: str) -> set:
    """Extract meaningful words (>2 chars) from text."""
    return {w.lower() for w in re.findall(r'[a-zA-Z]{3,}', text)}


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cosine_sim(v1, v2):
    """Cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _find_best_episode_match(pred_text: str, episodes: list, ep_embeddings: dict,
                              pred_embedding=None) -> tuple:
    """Find best matching episode for a prediction.

    Returns (best_episode, similarity_score, match_method).
    """
    pred_words = _word_set(pred_text)
    best_ep = None
    best_score = 0.0
    best_method = "none"

    # Phase 1: Word overlap (fast, no embeddings needed)
    for ep in episodes:
        task = ep.get("task") or ""
        ep_words = _word_set(task)
        jacc = _jaccard(pred_words, ep_words)
        if jacc > best_score:
            best_score = jacc
            best_ep = ep
            best_method = "word_overlap"

    # Phase 2: Embedding similarity (only if word overlap didn't find strong match)
    if best_score < EMBED_THRESHOLD and pred_embedding is not None:
        for ep in episodes:
            task = ep.get("task") or ""
            ep_emb = ep_embeddings.get(task)
            if ep_emb is None:
                continue
            sim = _cosine_sim(pred_embedding, ep_emb)
            if sim > best_score:
                best_score = sim
                best_ep = ep
                best_method = "embedding"

    return best_ep, best_score, best_method


def scan(use_embeddings: bool = True) -> list:
    """Scan unresolved predictions and find best episode matches.

    Returns list of {prediction, best_match, score, method} dicts.
    """
    preds = _load_predictions()
    episodes = _load_episodes()
    unresolved = [p for p in preds if p.get("outcome") is None]

    if not unresolved:
        return []

    # Precompute episode embeddings if needed
    ep_embeddings = {}
    pred_embeddings = {}
    if use_embeddings and unresolved:
        ef = _get_ef()
        ep_tasks = list({ep.get("task") or "" for ep in episodes} - {""})
        pred_texts = [_desanitize(p["event"]) for p in unresolved if p.get("event")]
        all_texts = ep_tasks + pred_texts
        if all_texts:
            all_embs = ef(all_texts)
            for i, task in enumerate(ep_tasks):
                ep_embeddings[task] = all_embs[i]
            for i, p in enumerate(unresolved):
                pred_embeddings[p["event"]] = all_embs[len(ep_tasks) + i]

    results = []
    for pred in unresolved:
        pred_text = _desanitize(pred["event"])
        pred_emb = pred_embeddings.get(pred["event"])
        best_ep, score, method = _find_best_episode_match(
            pred_text, episodes, ep_embeddings, pred_emb
        )
        results.append({
            "prediction": pred,
            "best_match": best_ep,
            "score": round(score, 4),
            "method": method,
        })

    return results


def resolve(dry_run: bool = False) -> dict:
    """Auto-resolve unresolved predictions using embedding similarity.

    Returns dict with matched, skipped, remaining counts.
    """
    preds = _load_predictions()
    episodes = _load_episodes()
    unresolved_idx = [i for i, p in enumerate(preds) if p.get("outcome") is None]

    if not unresolved_idx:
        return {"matched": 0, "skipped": 0, "remaining": 0}

    # Precompute embeddings
    ef = _get_ef()
    ep_tasks = list({ep.get("task") or "" for ep in episodes} - {""})
    pred_texts = [_desanitize(preds[i]["event"]) for i in unresolved_idx if preds[i].get("event")]
    all_texts = ep_tasks + pred_texts
    all_embs = ef(all_texts) if all_texts else []

    ep_embeddings = {}
    for i, task in enumerate(ep_tasks):
        ep_embeddings[task] = all_embs[i]

    matched = 0
    skipped = 0

    for j, idx in enumerate(unresolved_idx):
        pred = preds[idx]
        if not pred.get("event"):
            skipped += 1
            continue
        pred_text = _desanitize(pred["event"])
        pred_emb = all_embs[len(ep_tasks) + j] if all_embs else None

        best_ep, score, method = _find_best_episode_match(
            pred_text, episodes, ep_embeddings, pred_emb
        )

        threshold = EMBED_THRESHOLD if method == "embedding" else WORD_OVERLAP_THRESHOLD
        if best_ep and score >= threshold:
            outcome = best_ep.get("outcome", "success")
            # Normalize outcome: soft_failure/timeout → failure for calibration
            if outcome in ("soft_failure", "timeout"):
                outcome = "failure"
            if not dry_run:
                pred["outcome"] = outcome
                pred["correct"] = outcome.lower() == pred["expected"].lower()
                pred["resolved_by"] = "prediction_resolver"
                pred["match_score"] = round(float(score), 4)
                pred["match_method"] = method
                pred["matched_episode"] = best_ep.get("id", "unknown")
            matched += 1
        else:
            skipped += 1

    if not dry_run and matched > 0:
        _save_predictions(preds)

    remaining = sum(1 for p in preds if p.get("outcome") is None)
    return {"matched": matched, "skipped": skipped, "remaining": remaining}


def rescue_stale(dry_run: bool = False) -> dict:
    """Re-evaluate stale predictions against episodes.

    Stale predictions were expired by age without finding a match.
    Many actually DO have matching episodes — the string matcher was too rigid.

    Returns dict with rescued, kept_stale, total_stale counts.
    """
    preds = _load_predictions()
    episodes = _load_episodes()
    stale_idx = [i for i, p in enumerate(preds) if p.get("outcome") == "stale"]

    if not stale_idx:
        return {"rescued": 0, "kept_stale": 0, "total_stale": 0}

    # Precompute embeddings
    ef = _get_ef()
    ep_tasks = list({ep["task"] for ep in episodes if ep.get("task")})
    pred_texts = [_desanitize(preds[i]["event"]) for i in stale_idx if preds[i].get("event")]
    all_texts = ep_tasks + pred_texts
    all_embs = ef(all_texts) if all_texts else []

    ep_embeddings = {}
    for i, task in enumerate(ep_tasks):
        ep_embeddings[task] = all_embs[i]

    rescued = 0
    kept_stale = 0

    for j, idx in enumerate(stale_idx):
        pred = preds[idx]
        if not pred.get("event"):
            kept_stale += 1
            continue
        pred_text = _desanitize(pred["event"])
        pred_emb = all_embs[len(ep_tasks) + j] if all_embs else None

        best_ep, score, method = _find_best_episode_match(
            pred_text, episodes, ep_embeddings, pred_emb
        )

        if best_ep and score >= STALE_RESCUE_THRESHOLD:
            outcome = best_ep.get("outcome", "success")
            if outcome in ("soft_failure", "timeout"):
                outcome = "failure"
            if not dry_run:
                pred["outcome"] = outcome
                pred["correct"] = outcome.lower() == pred["expected"].lower()
                pred["resolved_by"] = "prediction_resolver_rescue"
                pred["match_score"] = round(float(score), 4)
                pred["match_method"] = method
                pred["matched_episode"] = best_ep.get("id", "unknown")
            rescued += 1
        else:
            kept_stale += 1

    if not dry_run and rescued > 0:
        _save_predictions(preds)

    return {"rescued": rescued, "kept_stale": kept_stale, "total_stale": len(stale_idx)}


def resolve_with_episodes(task_text: str, task_outcome: str) -> dict:
    """Enhanced auto-resolve: string match first, then embedding fallback.

    Drop-in replacement for confidence.auto_resolve() with embedding support.
    Called from heartbeat_postflight.

    Args:
        task_text: The completed task description
        task_outcome: 'success' or 'failure'

    Returns:
        dict with matched, stale_expired, embedding_matched, remaining_open counts
    """
    # First: run the existing string-based resolver
    from clarvis.cognition.confidence import auto_resolve as string_resolve
    result = string_resolve(task_text, task_outcome)

    # If there are still unresolved predictions, try embedding matching
    if result["remaining_open"] > 0:
        embed_result = resolve(dry_run=False)
        result["embedding_matched"] = embed_result["matched"]
        result["remaining_open"] = embed_result["remaining"]
    else:
        result["embedding_matched"] = 0

    return result


def stats() -> dict:
    """Compute current prediction statistics including brier score."""
    preds = _load_predictions()
    total = len(preds)
    if total == 0:
        return {"total": 0}

    # Exclude stale from calibration — outcome unknown, not "wrong"
    resolved = [p for p in preds if p.get("correct") is not None and p.get("outcome") != "stale"]
    unresolved = [p for p in preds if p.get("outcome") is None]
    stale = [p for p in preds if p.get("outcome") == "stale"]
    correct = [p for p in preds if p.get("correct") is True and p.get("outcome") != "stale"]
    incorrect = [p for p in preds if p.get("correct") is False and p.get("outcome") != "stale"]

    resolution_rate = len(resolved) / total if total else 0
    accuracy = len(correct) / len(resolved) if resolved else 0

    brier = 0.0
    if resolved:
        brier = sum(
            (p["confidence"] - (1.0 if p["correct"] else 0.0)) ** 2
            for p in resolved
        ) / len(resolved)

    return {
        "total": total,
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "stale": len(stale),
        "correct": len(correct),
        "incorrect": len(incorrect),
        "resolution_rate": round(resolution_rate, 4),
        "accuracy": round(accuracy, 4),
        "brier_score": round(brier, 4),
        "brier_skill": round(1.0 - brier, 4),  # inverted: higher = better
    }


# === CLI ===
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "scan":
        results = scan()
        for r in results:
            p = r["prediction"]
            m = r["best_match"]
            print(f"PRED: {_desanitize(p['event'])[:70]}")
            if m:
                print(f"  MATCH ({r['score']:.3f} {r['method']}): "
                      f"{m['task'][:60]} -> {m['outcome']}")
            else:
                print("  NO MATCH")
            print()

    elif cmd == "resolve":
        dry = "--dry-run" in sys.argv
        result = resolve(dry_run=dry)
        print(f"{'[DRY RUN] ' if dry else ''}Resolved: {result['matched']}, "
              f"Skipped: {result['skipped']}, Remaining: {result['remaining']}")

    elif cmd == "rescue-stale":
        dry = "--dry-run" in sys.argv
        before = stats()
        result = rescue_stale(dry_run=dry)
        after = stats()
        print(f"{'[DRY RUN] ' if dry else ''}Rescued: {result['rescued']}, "
              f"Kept stale: {result['kept_stale']}, Total stale: {result['total_stale']}")
        if not dry:
            print(f"Brier: {before['brier_score']:.4f} -> {after['brier_score']:.4f}")
            print(f"Accuracy: {before['accuracy']:.4f} -> {after['accuracy']:.4f}")

    elif cmd == "stats":
        s = stats()
        print(f"Predictions: {s['total']} total, {s['resolved']} resolved "
              f"({s['resolution_rate']:.1%})")
        print(f"Accuracy: {s['correct']}/{s['resolved']} ({s['accuracy']:.1%})")
        print(f"Unresolved: {s['unresolved']}, Stale: {s['stale']}")
        print(f"Brier score: {s['brier_score']:.4f} (lower=better)")
        print(f"Brier skill: {s['brier_skill']:.4f} (higher=better)")

    elif cmd == "auto-resolve":
        # Called with: prediction_resolver.py auto-resolve "task text" "outcome"
        if len(sys.argv) < 4:
            print("Usage: prediction_resolver.py auto-resolve <task_text> <outcome>")
            sys.exit(1)
        task = sys.argv[2]
        outcome = sys.argv[3]
        result = resolve_with_episodes(task, outcome)
        print(f"String matched: {result['matched']}, Embedding matched: {result['embedding_matched']}, "
              f"Stale expired: {result['stale_expired']}, Remaining: {result['remaining_open']}")

    else:
        print("Usage: prediction_resolver.py [scan|resolve|rescue-stale|stats|auto-resolve]")
        sys.exit(1)

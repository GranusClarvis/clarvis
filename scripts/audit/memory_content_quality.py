#!/usr/bin/env python3
"""Phase 4.5 — Memory Content Quality & Taxonomy Audit.

Samples 20 memories per collection (5 newest, 5 oldest, 10 random),
scores each on crisp/actionable/within_domain/non_redundant rubric,
and performs taxonomy sanity checks.

Output:
  data/audit/memory_content_spot_check.json
"""

import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE))

from clarvis.brain import brain
from clarvis.brain.constants import ALL_COLLECTIONS

DATA_DIR = WORKSPACE / "data" / "audit"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Collection domain definitions (for within_domain scoring) ──────────────

COLLECTION_DOMAINS = {
    "clarvis-identity": {
        "description": "Core identity: who Clarvis is, personality, values, self-concept",
        "keywords": ["identity", "clarvis", "personality", "values", "self", "who i am",
                      "consciousness", "agent", "name", "purpose"],
    },
    "clarvis-preferences": {
        "description": "User/operator preferences, interaction style, formatting choices",
        "keywords": ["prefer", "style", "format", "like", "dislike", "tone", "approach",
                      "operator", "communication"],
    },
    "clarvis-learnings": {
        "description": "Things learned from experience — patterns, insights, techniques, discoveries",
        "keywords": ["learned", "discovered", "insight", "pattern", "technique", "found",
                      "realized", "understood", "observation"],
    },
    "clarvis-infrastructure": {
        "description": "System infrastructure: servers, configs, paths, ports, services, deployment",
        "keywords": ["server", "config", "port", "service", "path", "systemd", "cron",
                      "deploy", "install", "setup", "gateway", "chromadb", "database"],
    },
    "clarvis-goals": {
        "description": "Active goals, objectives, targets, milestones",
        "keywords": ["goal", "objective", "target", "milestone", "achieve", "plan",
                      "roadmap", "aim", "strategy"],
    },
    "clarvis-context": {
        "description": "Contextual information about the current state, situation, environment",
        "keywords": ["context", "current", "state", "situation", "environment", "status",
                      "now", "today", "recent"],
    },
    "clarvis-memories": {
        "description": "General memories, events, experiences, conversations, facts",
        "keywords": ["remember", "event", "experience", "conversation", "happened",
                      "fact", "noted", "memory", "recall"],
    },
    "clarvis-procedures": {
        "description": "How-to procedures, workflows, step-by-step instructions, recipes",
        "keywords": ["procedure", "step", "workflow", "how to", "recipe", "process",
                      "instruction", "method", "protocol"],
    },
    "autonomous-learning": {
        "description": "Insights from autonomous/subconscious sessions, cron discoveries, self-play",
        "keywords": ["autonomous", "cron", "heartbeat", "subconscious", "discovered",
                      "evolution", "reflection", "session", "self-play"],
    },
    "clarvis-episodes": {
        "description": "Episodic task records: what was attempted, outcome, lessons from execution",
        "keywords": ["episode", "task", "executed", "outcome", "result", "attempted",
                      "success", "failure", "completed"],
    },
}


def sample_collection(collection_name, n_newest=5, n_oldest=5, n_random=10):
    """Get stratified sample from a collection: newest, oldest, random."""
    coll = brain.collections.get(collection_name)
    if not coll:
        return []

    count = coll.count()
    if count == 0:
        return []

    # Get all IDs with metadata to sort by timestamp
    # ChromaDB get() with limit
    batch_size = min(count, 2000)
    result = coll.get(
        limit=batch_size,
        include=["documents", "metadatas"],
    )

    if not result or not result.get("ids"):
        return []

    items = []
    for i, mid in enumerate(result["ids"]):
        doc = result["documents"][i] if result.get("documents") else ""
        meta = result["metadatas"][i] if result.get("metadatas") else {}
        ts = meta.get("timestamp", meta.get("stored_at", 0))
        if isinstance(ts, str):
            try:
                ts = float(ts)
            except (ValueError, TypeError):
                ts = 0
        items.append({
            "id": mid,
            "document": doc or "",
            "metadata": meta or {},
            "timestamp": ts,
            "collection": collection_name,
        })

    # Sort by timestamp
    items.sort(key=lambda x: x["timestamp"])

    # Stratified sample
    sampled = []
    sample_ids = set()

    # Oldest
    for item in items[:n_oldest]:
        if item["id"] not in sample_ids:
            item["stratum"] = "oldest"
            sampled.append(item)
            sample_ids.add(item["id"])

    # Newest
    for item in items[-n_newest:]:
        if item["id"] not in sample_ids:
            item["stratum"] = "newest"
            sampled.append(item)
            sample_ids.add(item["id"])

    # Random from middle
    middle = [it for it in items if it["id"] not in sample_ids]
    n_rand = min(n_random, len(middle))
    if n_rand > 0:
        for item in random.sample(middle, n_rand):
            item["stratum"] = "random"
            sampled.append(item)

    return sampled


def score_memory(item, collection_name):
    """Score a single memory on the 4-dimension rubric (0/1 each).

    Heuristic scoring (no LLM) — conservative, transparent, auditable.
    """
    doc = (item.get("document") or "").strip()
    meta = item.get("metadata") or {}

    scores = {}

    # 1. CRISP: Is the memory clear and well-formed? Not vague, not garbled.
    crisp = 1
    if len(doc) < 15:
        crisp = 0  # Too short to be useful
    elif len(doc) > 3000:
        crisp = 0  # Excessively long, likely uncompressed dump
    elif doc.count("\n") > 30 and len(doc) < 500:
        crisp = 0  # Mostly whitespace/formatting
    elif any(marker in doc.lower() for marker in ["error:", "traceback", "exception"]):
        # Error dumps stored as memories are not crisp
        if len(doc) > 500 and doc.count("\n") > 10:
            crisp = 0
    # Check for garbled content
    if doc and (doc.count("???") > 2 or doc.count("\\x") > 3):
        crisp = 0
    scores["crisp"] = crisp

    # 2. ACTIONABLE: Does the memory contain information that could guide future behavior?
    actionable = 0
    actionable_signals = [
        "should", "must", "always", "never", "when", "use", "avoid",
        "prefer", "ensure", "remember to", "important:", "note:",
        "procedure", "step", "how to", "to do", "recipe",
        "learned", "discovered", "insight", "pattern",
        "goal", "target", "objective", "plan",
        "fix", "solution", "workaround", "resolved",
    ]
    doc_lower = doc.lower()
    signal_count = sum(1 for s in actionable_signals if s in doc_lower)
    if signal_count >= 2:
        actionable = 1
    elif signal_count == 1 and len(doc) > 50:
        actionable = 1
    # Episodes with outcomes are actionable
    if meta.get("outcome") or meta.get("lesson") or meta.get("task_id"):
        actionable = 1
    # Goals are inherently actionable
    if collection_name == "clarvis-goals":
        actionable = 1
    # Procedures are inherently actionable
    if collection_name == "clarvis-procedures":
        if len(doc) > 30:
            actionable = 1
    scores["actionable"] = actionable

    # 3. WITHIN_DOMAIN: Does this memory belong in its collection?
    within_domain = 0
    domain_info = COLLECTION_DOMAINS.get(collection_name, {})
    keywords = domain_info.get("keywords", [])
    if keywords:
        match_count = sum(1 for kw in keywords if kw in doc_lower)
        # Generous threshold: 1 keyword match or metadata hints
        if match_count >= 1:
            within_domain = 1
        elif collection_name == "clarvis-memories":
            # General memories collection: anything that doesn't strongly belong elsewhere
            within_domain = 1
        elif collection_name == "clarvis-learnings":
            # Learnings are broad — any non-trivial content likely qualifies
            if len(doc) > 40:
                within_domain = 1
        elif collection_name == "autonomous-learning":
            # Anything from autonomous sessions counts
            src = meta.get("source", "")
            if "autonomous" in src or "cron" in src or "heartbeat" in src or "evolution" in src:
                within_domain = 1
            elif len(doc) > 40:
                within_domain = 1
        elif collection_name == "clarvis-episodes":
            # Episodes just need task-like structure
            if meta.get("task_id") or meta.get("outcome") or "task" in doc_lower or "episode" in doc_lower:
                within_domain = 1
            elif len(doc) > 50:
                within_domain = 1
    else:
        within_domain = 1  # No domain info = can't judge, default pass
    scores["within_domain"] = within_domain

    # 4. NON_REDUNDANT: Is this memory likely unique? (heuristic: check for very short generic content)
    non_redundant = 1
    # Flag very generic, likely-duplicated content
    generic_phrases = [
        "i am clarvis", "clarvis is an ai", "i am an ai assistant",
        "the system uses", "this is a", "updated on",
    ]
    for phrase in generic_phrases:
        if doc_lower.strip().startswith(phrase) and len(doc) < 100:
            non_redundant = 0
            break
    # Flag if document is extremely similar to a common template
    if doc_lower.startswith("episode:") and doc_lower.count(":") > 5 and len(doc) < 80:
        non_redundant = 0  # Likely template stub
    scores["non_redundant"] = non_redundant

    return scores


def check_cross_collection_misplacement(all_samples):
    """Identify memories that seem to belong in a different collection."""
    misplacements = []

    for item in all_samples:
        doc_lower = (item.get("document") or "").lower()
        current_coll = item["collection"]
        meta = item.get("metadata") or {}

        best_match = None
        best_score = 0

        for coll_name, domain_info in COLLECTION_DOMAINS.items():
            if coll_name == current_coll:
                continue
            keywords = domain_info.get("keywords", [])
            score = sum(1 for kw in keywords if kw in doc_lower)
            if score > best_score:
                best_score = score
                best_match = coll_name

        # Current collection match
        current_keywords = COLLECTION_DOMAINS.get(current_coll, {}).get("keywords", [])
        current_score = sum(1 for kw in current_keywords if kw in doc_lower)

        # Flag if another collection matches much better
        if best_match and best_score > current_score + 2:
            misplacements.append({
                "memory_id": item["id"],
                "current_collection": current_coll,
                "suggested_collection": best_match,
                "current_keyword_hits": current_score,
                "suggested_keyword_hits": best_score,
                "doc_preview": (item.get("document") or "")[:120],
            })

    return misplacements


def check_intake_quality():
    """Sample recent store operations by looking at newest memories across collections."""
    recent_stores = []

    for coll_name in ALL_COLLECTIONS:
        coll = brain.collections.get(coll_name)
        if not coll or coll.count() == 0:
            continue

        result = coll.get(
            limit=min(coll.count(), 500),
            include=["documents", "metadatas"],
        )
        if not result or not result.get("ids"):
            continue

        for i, mid in enumerate(result["ids"]):
            meta = result["metadatas"][i] if result.get("metadatas") else {}
            ts = meta.get("timestamp", meta.get("stored_at", 0))
            if isinstance(ts, str):
                try:
                    ts = float(ts)
                except (ValueError, TypeError):
                    ts = 0
            doc = result["documents"][i] if result.get("documents") else ""
            recent_stores.append({
                "id": mid,
                "collection": coll_name,
                "document": doc or "",
                "metadata": meta or {},
                "timestamp": ts,
            })

    # Sort by timestamp descending, take 30 most recent
    recent_stores.sort(key=lambda x: x["timestamp"], reverse=True)
    sample = recent_stores[:30]

    intake_issues = []
    for item in sample:
        doc = (item.get("document") or "").strip()
        meta = item.get("metadata") or {}
        issues = []

        if len(doc) < 20:
            issues.append("too_short")
        if len(doc) > 2000:
            issues.append("excessively_long")
        if not meta.get("source") and not meta.get("tags"):
            issues.append("missing_provenance")
        if not meta.get("importance") and not meta.get("timestamp"):
            issues.append("missing_metadata")

        intake_issues.append({
            "id": item["id"],
            "collection": item["collection"],
            "doc_length": len(doc),
            "has_source": bool(meta.get("source")),
            "has_tags": bool(meta.get("tags")),
            "has_importance": bool(meta.get("importance")),
            "has_timestamp": bool(meta.get("timestamp")),
            "issues": issues,
            "doc_preview": doc[:150],
            "timestamp": item["timestamp"],
        })

    return intake_issues


def run_audit():
    """Run the full Phase 4.5 memory content quality audit."""
    print("=" * 70)
    print("Phase 4.5 — Memory Content Quality & Taxonomy Audit")
    print("=" * 70)

    random.seed(42)  # Reproducible sampling

    all_samples = []
    collection_results = {}

    # ── Per-collection sampling and scoring ──────────────────────────────
    for coll_name in ALL_COLLECTIONS:
        coll = brain.collections.get(coll_name)
        count = coll.count() if coll else 0
        print(f"\n── {coll_name} ({count} memories) ──")

        if count == 0:
            collection_results[coll_name] = {
                "count": 0, "sampled": 0,
                "scores": {}, "verdict": "EMPTY",
            }
            print("  EMPTY — no memories to sample")
            continue

        # Adjust sample sizes for small collections
        n_newest = min(5, count)
        n_oldest = min(5, count)
        n_random = min(10, max(0, count - n_newest - n_oldest))

        samples = sample_collection(coll_name, n_newest, n_oldest, n_random)
        all_samples.extend(samples)

        # Score each memory
        scores_agg = {"crisp": 0, "actionable": 0, "within_domain": 0, "non_redundant": 0}
        scored_samples = []
        for item in samples:
            scores = score_memory(item, coll_name)
            item["scores"] = scores
            scored_samples.append(item)
            for k, v in scores.items():
                scores_agg[k] += v

        n = len(samples)
        rates = {k: round(v / n, 3) if n else 0 for k, v in scores_agg.items()}

        # Determine verdict per Phase 4.5 gates
        within_domain_rate = rates["within_domain"]
        redundant_rate = 1.0 - rates["non_redundant"]
        crisp_and_actionable = sum(
            1 for s in scored_samples
            if s["scores"]["crisp"] == 1 and s["scores"]["actionable"] == 1
        ) / n if n else 0

        if within_domain_rate >= 0.8 and redundant_rate <= 0.2 and crisp_and_actionable >= 0.5:
            verdict = "PASS"
        elif within_domain_rate < 0.6 or redundant_rate > 0.4:
            verdict = "DEMOTE_CANDIDATE"
        else:
            verdict = "REVISE"

        # Check for PROMOTE
        if (within_domain_rate >= 0.9 and redundant_rate <= 0.1 and
                crisp_and_actionable >= 0.7 and rates["crisp"] >= 0.9):
            verdict = "PROMOTE"

        collection_results[coll_name] = {
            "count": count,
            "sampled": n,
            "rates": rates,
            "crisp_and_actionable_rate": round(crisp_and_actionable, 3),
            "within_domain_rate": within_domain_rate,
            "redundant_rate": round(redundant_rate, 3),
            "verdict": verdict,
            "samples": [{
                "id": s["id"],
                "stratum": s["stratum"],
                "doc_preview": (s.get("document") or "")[:200],
                "scores": s["scores"],
                "timestamp": s["timestamp"],
            } for s in scored_samples],
        }

        print(f"  Sampled: {n} | crisp={rates['crisp']:.0%} actionable={rates['actionable']:.0%} "
              f"within_domain={rates['within_domain']:.0%} non_redundant={rates['non_redundant']:.0%}")
        print(f"  crisp+actionable: {crisp_and_actionable:.0%} | redundant: {redundant_rate:.0%}")
        print(f"  ▸ Verdict: {verdict}")

    # ── Taxonomy / cross-collection check ────────────────────────────────
    print("\n" + "=" * 70)
    print("Taxonomy Cross-Collection Check")
    print("=" * 70)
    misplacements = check_cross_collection_misplacement(all_samples)
    print(f"  Potential misplacements found: {len(misplacements)}")
    for mp in misplacements[:10]:
        print(f"  - {mp['memory_id'][:20]}... in {mp['current_collection']} "
              f"→ better fit: {mp['suggested_collection']} "
              f"(hits: {mp['current_keyword_hits']} vs {mp['suggested_keyword_hits']})")
        print(f"    preview: {mp['doc_preview'][:80]}...")

    # ── Intake quality ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Memory Intake Quality (30 most recent stores)")
    print("=" * 70)
    intake = check_intake_quality()
    issue_counts = defaultdict(int)
    for item in intake:
        for issue in item["issues"]:
            issue_counts[issue] += 1
    clean = sum(1 for item in intake if not item["issues"])
    print(f"  Clean (no issues): {clean}/{len(intake)}")
    for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f"  {issue}: {count}/{len(intake)}")

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for coll_name in ALL_COLLECTIONS:
        r = collection_results.get(coll_name, {})
        v = r.get("verdict", "N/A")
        n = r.get("count", 0)
        marker = {"PASS": "✓", "PROMOTE": "★", "REVISE": "~", "DEMOTE_CANDIDATE": "✗", "EMPTY": "○"}.get(v, "?")
        print(f"  {marker} {coll_name:30s} ({n:4d}) → {v}")

    # ── Save artifact ────────────────────────────────────────────────────
    artifact = {
        "audit_phase": "4.5",
        "audit_name": "Memory Content Quality & Taxonomy",
        "date": time.strftime("%Y-%m-%d"),
        "total_memories": sum(r.get("count", 0) for r in collection_results.values()),
        "total_sampled": sum(r.get("sampled", 0) for r in collection_results.values()),
        "collection_results": {k: {kk: vv for kk, vv in v.items() if kk != "samples"}
                               for k, v in collection_results.items()},
        "collection_samples": {k: v.get("samples", []) for k, v in collection_results.items()},
        "taxonomy_misplacements": misplacements,
        "intake_quality": intake,
        "intake_summary": {
            "total_sampled": len(intake),
            "clean_count": clean,
            "issue_counts": dict(issue_counts),
        },
    }

    out_path = DATA_DIR / "memory_content_spot_check.json"
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    print(f"\n  Artifact saved: {out_path}")

    return artifact


if __name__ == "__main__":
    run_audit()

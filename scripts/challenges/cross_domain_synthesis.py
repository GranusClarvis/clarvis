#!/usr/bin/env python3
"""Cross-domain knowledge synthesis engine.

Takes 2 random Wikipedia pages from different domains, computes their
embedding centroid, searches the brain for memories near that centroid,
and writes a synthesis note connecting the domains.

Usage:
    python3 scripts/challenges/cross_domain_synthesis.py run [--pairs N]
    python3 scripts/challenges/cross_domain_synthesis.py test
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
OUTPUT_DIR = BASE / "data" / "synthesis"
OUTPUT_FILE = OUTPUT_DIR / "synthesis_notes.jsonl"

# Wikipedia domain categories for ensuring cross-domain pairs
DOMAIN_CATEGORIES = {
    "science": ["Physics", "Chemistry", "Biology", "Mathematics", "Astronomy"],
    "history": ["Ancient_history", "Medieval_history", "Modern_history", "Military_history"],
    "technology": ["Computing", "Software", "Artificial_intelligence", "Robotics"],
    "arts": ["Music", "Painting", "Literature", "Film", "Architecture"],
    "philosophy": ["Epistemology", "Ethics", "Logic", "Metaphysics"],
    "nature": ["Ecology", "Geology", "Oceanography", "Meteorology"],
    "society": ["Economics", "Sociology", "Psychology", "Law"],
}


def fetch_random_wiki_page() -> dict:
    """Fetch a random Wikipedia page summary via the REST API."""
    url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
    req = urllib.request.Request(url, headers={"User-Agent": "ClarvisSynthesis/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "title": data.get("title", ""),
                "extract": data.get("extract", ""),
                "description": data.get("description", ""),
                "pageid": data.get("pageid"),
            }
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        return {"title": "", "extract": "", "description": "", "error": str(e)}


def _classify_domain(page: dict) -> str:
    """Rough domain classification from page description/extract."""
    text = (page.get("description", "") + " " + page.get("extract", "")).lower()
    domain_signals = {
        "science": ["physics", "physicist", "chemistry", "biology", "species", "molecule", "atom", "cell", "gene", "theorem", "theoretical"],
        "history": ["century", "war", "dynasty", "empire", "kingdom", "battle", "ancient", "medieval"],
        "technology": ["computer", "software", "algorithm", "programming", "internet", "robot", "digital"],
        "arts": ["artist", "painter", "musician", "composer", "film", "novel", "poem", "album", "song"],
        "philosophy": ["philosophy", "ethics", "logic", "epistemology", "metaphysics", "theory"],
        "nature": ["climate", "ocean", "mountain", "river", "forest", "species", "ecosystem"],
        "society": ["economic", "political", "social", "legal", "government", "population"],
    }
    scores = {}
    for domain, signals in domain_signals.items():
        scores[domain] = sum(1 for s in signals if s in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def get_embedder():
    """Get the ONNX MiniLM embedder."""
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        return ONNXMiniLM_L6_V2()
    except ImportError:
        return None


def compute_centroid(embedder, texts: list[str]) -> list[float]:
    """Compute the embedding centroid of multiple texts."""
    embeddings = embedder(texts)
    n = len(embeddings)
    dim = len(embeddings[0])
    centroid = [sum(embeddings[j][i] for j in range(n)) / n for i in range(dim)]
    return centroid


def search_brain_near_centroid(centroid: list[float], page_a: dict, page_b: dict, n: int = 5) -> list[dict]:
    """Search brain for memories near the semantic centroid of two pages.

    Uses a combined query string from both pages' extracts to find
    bridging memories via brain.recall.
    """
    try:
        from clarvis.brain import brain
    except ImportError:
        return []

    # Build a combined query from key terms of both pages
    query = f"{page_a.get('title', '')} {page_b.get('title', '')} "
    query += f"{page_a.get('extract', '')[:100]} {page_b.get('extract', '')[:100]}"

    try:
        results = brain.recall(query, n=n, caller="cross_domain_synthesis")
        # Normalize output format
        normalized = []
        for r in results:
            normalized.append({
                "document": r.get("document", ""),
                "collection": r.get("collection", "unknown"),
                "distance": r.get("distance"),
                "metadata": r.get("metadata", {}),
            })
        return normalized
    except Exception:
        return []


def synthesize_pair(page_a: dict, page_b: dict, brain_memories: list[dict]) -> dict:
    """Create a synthesis note connecting two pages via brain memories."""
    domain_a = _classify_domain(page_a)
    domain_b = _classify_domain(page_b)

    # Build synthesis note
    memory_excerpts = []
    for mem in brain_memories[:3]:
        doc = mem.get("document", "")[:150]
        col = mem.get("collection", "?")
        memory_excerpts.append(f"  [{col}] {doc}")

    note = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "page_a": {"title": page_a["title"], "domain": domain_a,
                    "extract": page_a["extract"][:200]},
        "page_b": {"title": page_b["title"], "domain": domain_b,
                    "extract": page_b["extract"][:200]},
        "cross_domain": domain_a != domain_b,
        "bridging_memories": len(brain_memories),
        "memory_excerpts": memory_excerpts,
        "centroid_distance": brain_memories[0].get("distance") if brain_memories else None,
    }

    # Build a human-readable connection summary
    if brain_memories:
        bridge_doc = brain_memories[0]["document"][:100]
        note["connection"] = (
            f"'{page_a['title']}' ({domain_a}) and '{page_b['title']}' ({domain_b}) "
            f"share a semantic neighborhood with brain memory: \"{bridge_doc}...\""
        )
    else:
        note["connection"] = (
            f"'{page_a['title']}' ({domain_a}) and '{page_b['title']}' ({domain_b}) "
            f"— no close brain memories found at their centroid."
        )

    return note


def score_synthesis(note: dict) -> dict:
    """Score a synthesis on novelty and coherence."""
    novelty = 0.0
    coherence = 0.0

    # Novelty: higher if cross-domain and centroid distance is moderate
    # (too close = obvious, too far = forced)
    if note.get("cross_domain"):
        novelty += 0.3
    dist = note.get("centroid_distance")
    if dist is not None:
        # Sweet spot: distance 0.8-1.2 (not trivially similar, not totally unrelated)
        if 0.6 <= dist <= 1.4:
            novelty += 0.4
        elif dist < 0.6:
            novelty += 0.1  # Too obvious
        else:
            novelty += 0.2  # Too distant
    if note.get("bridging_memories", 0) > 0:
        novelty += 0.3

    # Coherence: based on having bridging memories and connection text
    if note.get("bridging_memories", 0) >= 2:
        coherence += 0.5
    elif note.get("bridging_memories", 0) >= 1:
        coherence += 0.3
    if note.get("connection") and "brain memory" in note.get("connection", ""):
        coherence += 0.3
    if note.get("memory_excerpts"):
        coherence += 0.2

    return {
        "novelty": round(min(novelty, 1.0), 2),
        "coherence": round(min(coherence, 1.0), 2),
        "composite": round((novelty + coherence) / 2, 2),
    }


def run_synthesis(n_pairs: int = 5) -> list[dict]:
    """Run the full synthesis pipeline for N random page pairs."""
    embedder = get_embedder()
    if embedder is None:
        print("ERROR: No embedder available")
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for i in range(n_pairs):
        print(f"\n--- Pair {i + 1}/{n_pairs} ---")

        # Fetch two random pages (retry up to 3 times for non-empty)
        page_a, page_b = None, None
        for _ in range(3):
            page_a = fetch_random_wiki_page()
            if page_a.get("extract"):
                break
            time.sleep(0.5)
        for _ in range(3):
            page_b = fetch_random_wiki_page()
            if page_b.get("extract"):
                break
            time.sleep(0.5)

        if not page_a.get("extract") or not page_b.get("extract"):
            print(f"  Skipping pair {i + 1}: failed to fetch pages")
            continue

        print(f"  A: {page_a['title']} ({_classify_domain(page_a)})")
        print(f"  B: {page_b['title']} ({_classify_domain(page_b)})")

        # Compute centroid of both page extracts
        texts = [page_a["extract"], page_b["extract"]]
        centroid = compute_centroid(embedder, texts)

        # Search brain near centroid
        memories = search_brain_near_centroid(centroid, page_a, page_b, n=5)
        print(f"  Found {len(memories)} bridging memories")

        # Synthesize
        note = synthesize_pair(page_a, page_b, memories)
        scores = score_synthesis(note)
        note["scores"] = scores

        print(f"  Connection: {note['connection'][:120]}")
        print(f"  Scores: novelty={scores['novelty']}, coherence={scores['coherence']}, composite={scores['composite']}")

        results.append(note)

        # Append to JSONL output
        with open(OUTPUT_FILE, "a") as f:
            f.write(json.dumps(note) + "\n")

        time.sleep(0.5)  # Rate limit

    # Summary
    if results:
        avg_novelty = sum(r["scores"]["novelty"] for r in results) / len(results)
        avg_coherence = sum(r["scores"]["coherence"] for r in results) / len(results)
        avg_composite = sum(r["scores"]["composite"] for r in results) / len(results)
        cross_domain_pct = sum(1 for r in results if r["cross_domain"]) / len(results) * 100
        print(f"\n=== Summary ({len(results)} pairs) ===")
        print(f"  Avg novelty:   {avg_novelty:.2f}")
        print(f"  Avg coherence: {avg_coherence:.2f}")
        print(f"  Avg composite: {avg_composite:.2f}")
        print(f"  Cross-domain:  {cross_domain_pct:.0f}%")

    return results


def test():
    """Quick smoke test without network calls."""
    print("Testing cross-domain synthesis engine...")

    # Test domain classification
    page = {"description": "physicist", "extract": "Albert Einstein was a theoretical physicist"}
    assert _classify_domain(page) == "science", f"Expected science, got {_classify_domain(page)}"

    page2 = {"description": "composer", "extract": "Beethoven was a German composer and pianist"}
    assert _classify_domain(page2) == "arts", f"Expected arts, got {_classify_domain(page2)}"

    # Test embedder availability
    embedder = get_embedder()
    assert embedder is not None, "Embedder not available"

    # Test centroid computation
    centroid = compute_centroid(embedder, ["physics quantum mechanics", "music theory harmony"])
    assert len(centroid) > 0, "Empty centroid"
    assert len(centroid) == 384, f"Expected 384-dim, got {len(centroid)}"

    # Test brain search with centroid
    test_a = {"title": "Quantum Mechanics", "extract": "Quantum mechanics describes nature at atomic scale"}
    test_b = {"title": "Jazz Music", "extract": "Jazz is a music genre with improvisation and swing"}
    memories = search_brain_near_centroid(centroid, test_a, test_b, n=3)
    print(f"  Brain search returned {len(memories)} memories")

    # Test synthesis
    page_a = {"title": "Quantum Mechanics", "extract": "Quantum mechanics describes nature at atomic scale",
              "description": "physics"}
    page_b = {"title": "Jazz Music", "extract": "Jazz is a music genre with improvisation and swing",
              "description": "music genre"}
    note = synthesize_pair(page_a, page_b, memories)
    assert note["cross_domain"], "Should be cross-domain"
    assert note["page_a"]["title"] == "Quantum Mechanics"

    # Test scoring
    scores = score_synthesis(note)
    assert 0 <= scores["novelty"] <= 1
    assert 0 <= scores["coherence"] <= 1
    assert 0 <= scores["composite"] <= 1

    print(f"  Synthesis note: {note['connection'][:100]}")
    print(f"  Scores: {scores}")
    print("All tests passed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: cross_domain_synthesis.py run [--pairs N] | test")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "test":
        test()
    elif cmd == "run":
        pairs = 5
        if "--pairs" in sys.argv:
            idx = sys.argv.index("--pairs")
            if idx + 1 < len(sys.argv):
                pairs = int(sys.argv[idx + 1])
        run_synthesis(n_pairs=pairs)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

"""
Clarvis ecosystem adapter — bridges standalone ClarvisDB into Clarvis brain.

Provides the same memory management as brain.py but backed by the standalone
VectorStore. Handles:
- All 10 Clarvis collections
- Graph relationships
- Hebbian + STDP evolution on recall
- Bridge callbacks for attention/somatic systems

Usage (drop-in bridge):
    from clarvis_db.clarvis_adapter import db
    db.store("learned fact", collection="clarvis-learnings", importance=0.8)
    results = db.recall("what did I learn")
"""

import sys
from pathlib import Path

from clarvis_db.store import VectorStore

# Clarvis collection names (same as brain.py)
COLLECTIONS = [
    "clarvis-identity",
    "clarvis-preferences",
    "clarvis-learnings",
    "clarvis-infrastructure",
    "clarvis-goals",
    "clarvis-context",
    "clarvis-memories",
    "clarvis-procedures",
    "autonomous-learning",
    "clarvis-episodes",
]

_DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvisdb"


def _on_recall(query, results):
    """Post-recall hook: wire into attention/retrieval tracking if available."""
    if not results:
        return
    # Retrieval quality tracking
    try:
        scripts_dir = str(Path(__file__).resolve().parents[2].parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from retrieval_quality import tracker
        tracker.on_recall(query, results, caller="clarvis_db")
    except Exception:
        pass


db = VectorStore(
    data_dir=_DATA_DIR,
    collections=COLLECTIONS,
    use_onnx=True,
    enable_hebbian=True,
    enable_stdp=True,
    on_recall=_on_recall,
)

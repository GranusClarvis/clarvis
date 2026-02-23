"""
Clarvis ecosystem adapter — bridges standalone EpisodicStore into Clarvis.

This module provides the same API as the original scripts/episodic_memory.py
but backed by the standalone EpisodicStore. It handles:
- ChromaDB integration via brain.py
- Somatic marker tagging
- GWT attention spreading activation
- Retrieval quality tracking

Usage (drop-in replacement):
    from clarvis_episodic.clarvis_adapter import episodic
    episodic.encode("task", "section", 0.8, "success")
    episodic.recall_similar("query")
"""

import sys
from pathlib import Path

# Import the standalone store
from clarvis_episodic.core import EpisodicStore


def _get_brain_collection():
    """Get ChromaDB collection from Clarvis brain (if available)."""
    try:
        scripts_dir = str(Path(__file__).resolve().parents[2].parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from brain import brain
        return brain.collections.get("clarvis-episodes")
    except Exception:
        return None


def _on_encode(episode):
    """Post-encode hook: store in brain + somatic markers."""
    try:
        scripts_dir = str(Path(__file__).resolve().parents[2].parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from brain import brain
        importance = min(1.0, 0.5 + episode["valence"] * 0.3)
        tags = ["episode", episode["outcome"], episode.get("section", "")]
        summary = f"Episode: {episode['task'][:100]} -> {episode['outcome']}"
        if episode.get("error"):
            summary += f" (error: {episode['error'][:80]})"
        brain.store(summary, collection="clarvis-episodes", importance=importance,
                    tags=tags, source="episodic_memory")
    except Exception:
        pass

    # Somatic markers
    try:
        from somatic_markers import somatic
        somatic.tag_episode(episode)
    except Exception:
        pass


def _on_recall(query, results):
    """Post-recall hook: spreading activation to GWT spotlight."""
    if not results:
        return
    try:
        from attention import attention
        activation_text = " ".join(ep["task"] for ep in results)
        attention.spreading_activation(activation_text, n=3)
        attention.submit(
            f"Episodic recall: {results[0]['task'][:100]} ({results[0]['outcome']})",
            source="episodic_recall",
            importance=0.6,
            relevance=0.7,
            boost=0.1,
        )
    except Exception:
        pass


# Default data directory for Clarvis
_DATA_DIR = "/home/agent/.openclaw/workspace/data"

episodic = EpisodicStore(
    data_dir=_DATA_DIR,
    max_episodes=500,
    chroma_collection=_get_brain_collection(),
    on_encode=_on_encode,
    on_recall=_on_recall,
)

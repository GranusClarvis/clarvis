"""
ClarvisEpisodic — ACT-R inspired episodic memory system.

A standalone episodic memory store with:
- ACT-R base-level activation with power-law decay (Pavlik & Anderson 2005)
- Emotional valence scoring (negativity bias, novelty detection)
- Semantic recall via embedding similarity
- Episode synthesis for pattern detection and goal generation

Usage:
    from clarvis_episodic import EpisodicStore

    store = EpisodicStore("/path/to/data")
    store.encode("Fixed auth bug", section="bugs", salience=0.8, outcome="success")
    episodes = store.recall("authentication issues")
    failures = store.failures()
    stats = store.stats()
"""

from clarvis_episodic.core import EpisodicStore
from clarvis_episodic.actr import compute_activation, compute_valence

__version__ = "1.0.0"
__all__ = ["EpisodicStore", "compute_activation", "compute_valence"]

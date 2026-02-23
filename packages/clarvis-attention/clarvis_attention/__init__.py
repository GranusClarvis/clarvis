"""
ClarvisAttention — GWT attention mechanism as a standalone package.

A capacity-limited attention spotlight based on Baars' Global Workspace Theory.
Items compete for limited broadcast slots via salience scoring (importance,
recency, relevance, access frequency, and external boost).

Usage:
    from clarvis_attention import AttentionSpotlight, AttentionItem

    spotlight = AttentionSpotlight(capacity=7)
    spotlight.submit("important task", source="user", importance=0.9)
    spotlight.tick()
    focus = spotlight.focus()       # Top-K conscious items
    summary = spotlight.broadcast() # Push to registered hooks
"""

from clarvis_attention.spotlight import (
    AttentionItem,
    AttentionSpotlight,
    DEFAULT_CAPACITY,
    DECAY_PER_TICK,
    EVICTION_THRESHOLD,
    W_ACCESS,
    W_BOOST,
    W_IMPORTANCE,
    W_RECENCY,
    W_RELEVANCE,
)

__version__ = "1.0.0"
__all__ = [
    "AttentionSpotlight",
    "AttentionItem",
    "DEFAULT_CAPACITY",
    "DECAY_PER_TICK",
    "EVICTION_THRESHOLD",
    "W_IMPORTANCE",
    "W_RECENCY",
    "W_RELEVANCE",
    "W_ACCESS",
    "W_BOOST",
]

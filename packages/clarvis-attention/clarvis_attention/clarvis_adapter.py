"""
Clarvis adapter — wires ClarvisAttention into the Clarvis brain system.

Provides a drop-in replacement for scripts/attention.py using the
standalone package, with brain-backed persistence and broadcasting.

Usage:
    from clarvis_attention.clarvis_adapter import get_attention, attention

    attention.submit("something important", source="user", importance=0.9)
    attention.broadcast()  # pushes to brain context
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from clarvis_attention.spotlight import AttentionSpotlight

PERSIST_PATH = "/home/agent/.openclaw/workspace/data/attention/spotlight.json"


def _brain_broadcast(summary: str, items: List[Dict[str, Any]]) -> None:
    """Broadcast hook that pushes spotlight to Clarvis brain context."""
    try:
        sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")
        from brain import brain
        brain.set_context(summary)
        brain.store(
            f"Attention broadcast: {summary}",
            collection="clarvis-context",
            importance=0.3,
            tags=["attention", "broadcast"],
            source="attention_mechanism",
        )
    except Exception:
        pass  # Brain not available — standalone mode


def get_attention(
    persist_path: str = PERSIST_PATH,
    capacity: int = 7,
    wire_brain: bool = True,
) -> AttentionSpotlight:
    """Create an AttentionSpotlight wired into Clarvis infrastructure.

    Args:
        persist_path: JSON file for state persistence
        capacity: Spotlight capacity (default 7)
        wire_brain: If True, register brain broadcast hook
    """
    spotlight = AttentionSpotlight(capacity=capacity, persist_path=persist_path)
    if wire_brain:
        spotlight.on_broadcast(_brain_broadcast)
    return spotlight


# Singleton for backward compatibility with scripts/attention.py
_attention = None


def _get_singleton() -> AttentionSpotlight:
    global _attention
    if _attention is None:
        _attention = get_attention()
    return _attention


attention = _get_singleton()

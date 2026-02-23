"""
Global Workspace Theory (GWT) — Attention Spotlight.

Implements a capacity-limited spotlight where items compete for access
to the "global workspace". Only the top-K most salient items are
"conscious" at any time and available to all cognitive subsystems.

Based on Baars' Global Workspace Theory: many modules process in parallel,
but only the most salient items win broadcast access.

This module is backend-agnostic. No filesystem persistence by default;
call to_dict() / from_dict() to serialize wherever you like.

Usage:
    from clarvis_consciousness.gwt import AttentionSpotlight

    spotlight = AttentionSpotlight(capacity=7)
    spotlight.submit("user asked about memory architecture", source="conversation", importance=0.9)
    spotlight.submit("cron job completed", source="system", importance=0.3)

    focus = spotlight.focus()     # Top-K items by salience
    spotlight.tick()              # Run competition cycle
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set


# Salience weights
W_IMPORTANCE = 0.25
W_RECENCY = 0.20
W_RELEVANCE = 0.30
W_ACCESS = 0.10
W_BOOST = 0.15

# Decay per tick for items NOT in spotlight
DECAY_PER_TICK = 0.05
EVICTION_THRESHOLD = 0.1
DEFAULT_CAPACITY = 7  # 7 +/- 2 rule from cognitive science


@dataclass
class AttentionItem:
    """A single item competing for spotlight access."""

    id: str
    content: str
    source: str = "unknown"
    importance: float = 0.5
    relevance: float = 0.5
    boost: float = 0.0
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    ticks_in_spotlight: int = 0
    ticks_total: int = 0

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed:
            self.last_accessed = self.created_at
        self.importance = max(0.0, min(1.0, self.importance))
        self.relevance = max(0.0, min(1.0, self.relevance))
        self.boost = max(0.0, min(1.0, self.boost))

    def salience(self) -> float:
        """Compute composite salience score (0-1)."""
        now = datetime.now(timezone.utc)
        try:
            created = datetime.fromisoformat(self.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            created = now
        age_hours = max(0.01, (now - created).total_seconds() / 3600)

        # Recency: exponential decay (half-life ~6 hours)
        recency = math.exp(-0.115 * age_hours)

        # Access frequency: log-scaled, capped at 1.0
        access_score = min(1.0, math.log1p(self.access_count) / 3.0)

        score = (
            W_IMPORTANCE * self.importance
            + W_RECENCY * recency
            + W_RELEVANCE * self.relevance
            + W_ACCESS * access_score
            + W_BOOST * self.boost
        )
        return round(max(0.0, min(1.0, score)), 4)

    def touch(self):
        """Mark as accessed (reinforces salience)."""
        self.last_accessed = datetime.now(timezone.utc).isoformat()
        self.access_count += 1

    def decay(self, rate: float = DECAY_PER_TICK):
        """Decay relevance and boost (losing attention)."""
        self.relevance = max(0.0, self.relevance - rate)
        self.boost = max(0.0, self.boost - rate * 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "importance": self.importance,
            "relevance": self.relevance,
            "boost": self.boost,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ticks_in_spotlight": self.ticks_in_spotlight,
            "ticks_total": self.ticks_total,
            "salience": self.salience(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AttentionItem":
        item = cls(
            id=d["id"],
            content=d["content"],
            source=d.get("source", "unknown"),
            importance=d.get("importance", 0.5),
            relevance=d.get("relevance", 0.5),
            boost=d.get("boost", 0.0),
            created_at=d.get("created_at", ""),
            last_accessed=d.get("last_accessed", ""),
        )
        item.access_count = d.get("access_count", 0)
        item.ticks_in_spotlight = d.get("ticks_in_spotlight", 0)
        item.ticks_total = d.get("ticks_total", 0)
        return item


class AttentionSpotlight:
    """
    The global workspace spotlight. Items compete for limited slots.
    Only the top-K most salient items are 'in the spotlight' at any time.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self.capacity = capacity
        self.items: Dict[str, AttentionItem] = {}
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"attn_{ts}_{self._id_counter}"

    def submit(
        self,
        content: str,
        source: str = "unknown",
        importance: float = 0.5,
        relevance: float = 0.5,
        boost: float = 0.0,
        item_id: Optional[str] = None,
    ) -> AttentionItem:
        """Submit an item for attention competition.

        If content matches an existing item, reinforces it instead.
        """
        for existing in self.items.values():
            if existing.content == content:
                existing.touch()
                existing.relevance = max(existing.relevance, relevance)
                existing.boost = max(existing.boost, boost)
                existing.importance = max(existing.importance, importance)
                return existing

        item = AttentionItem(
            id=item_id or self._next_id(),
            content=content,
            source=source,
            importance=importance,
            relevance=relevance,
            boost=boost,
        )
        self.items[item.id] = item
        return item

    def focus(self) -> List[Dict[str, Any]]:
        """Get current spotlight contents -- top-K by salience.

        This is the 'conscious' content available to all modules.
        """
        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight = ranked[:self.capacity]
        for item in spotlight:
            item.touch()
        return [item.to_dict() for item in spotlight]

    def focus_summary(self) -> str:
        """Compact text summary of what's in the spotlight."""
        spotlight = self.focus()
        if not spotlight:
            return "Spotlight: empty (no active attention items)"
        lines = [f"Spotlight ({len(spotlight)} items):"]
        for i, item in enumerate(spotlight):
            lines.append(
                f"  {i+1}. [{item['salience']:.2f}] {item['content'][:100]}"
                f" (src={item['source']})"
            )
        return "\n".join(lines)

    def tick(self) -> Dict[str, int]:
        """Run one competition cycle.

        1. Score all items
        2. Spotlight items get ticks_in_spotlight incremented
        3. Non-spotlight items decay
        4. Items below eviction threshold get removed
        """
        if not self.items:
            return {"spotlight": 0, "decayed": 0, "evicted": 0, "total": 0}

        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight_ids = {item.id for item in ranked[:self.capacity]}

        decayed = 0
        evicted = []

        for item in self.items.values():
            item.ticks_total += 1
            if item.id in spotlight_ids:
                item.ticks_in_spotlight += 1
            else:
                item.decay()
                decayed += 1
                if item.salience() < EVICTION_THRESHOLD:
                    evicted.append(item.id)

        for eid in evicted:
            del self.items[eid]

        return {
            "spotlight": len(spotlight_ids),
            "decayed": decayed,
            "evicted": len(evicted),
            "total": len(self.items),
        }

    def spreading_activation(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        """Boost attention items related to a query (spreading activation).

        Used to connect episodic recall with current spotlight.
        """
        query_words = set(query.lower().split())
        boosted = []

        for item in self.items.values():
            item_words = set(item.content.lower().split())
            overlap = len(query_words & item_words)
            if overlap > 0:
                activation_boost = min(0.3, overlap * 0.05)
                item.relevance = min(1.0, item.relevance + activation_boost)
                item.touch()
                boosted.append(item)

        boosted.sort(key=lambda x: x.salience(), reverse=True)
        return [item.to_dict() for item in boosted[:n]]

    def query_relevant(self, query: str, n: int = 3) -> List[Dict[str, Any]]:
        """Find items most relevant to a query via word overlap."""
        query_words = set(query.lower().split())
        scored = []

        for item in self.items.values():
            item_words = set(item.content.lower().split())
            overlap = len(query_words & item_words)
            if overlap > 0:
                word_score = overlap / max(len(query_words), 1)
                combined = 0.6 * item.salience() + 0.4 * word_score
                scored.append((combined, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item.to_dict() for _, item in scored[:n]]

    def stats(self) -> Dict[str, Any]:
        """Attention system statistics."""
        if not self.items:
            return {"total_items": 0, "spotlight_size": 0, "avg_salience": 0, "sources": {}}

        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight = ranked[:self.capacity]
        sources: Dict[str, int] = {}
        for item in self.items.values():
            sources[item.source] = sources.get(item.source, 0) + 1
        saliences = [item.salience() for item in self.items.values()]

        return {
            "total_items": len(self.items),
            "spotlight_size": len(spotlight),
            "capacity": self.capacity,
            "avg_salience": round(sum(saliences) / len(saliences), 4),
            "max_salience": round(max(saliences), 4),
            "min_salience": round(min(saliences), 4),
            "sources": sources,
            "spotlight_items": [s.content[:60] for s in spotlight],
        }

    def clear(self):
        """Reset spotlight."""
        self.items.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entire spotlight state."""
        return {
            "capacity": self.capacity,
            "id_counter": self._id_counter,
            "items": [item.to_dict() for item in self.items.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttentionSpotlight":
        """Restore spotlight from serialized state."""
        spotlight = cls(capacity=data.get("capacity", DEFAULT_CAPACITY))
        spotlight._id_counter = data.get("id_counter", 0)
        for d in data.get("items", []):
            item = AttentionItem.from_dict(d)
            spotlight.items[item.id] = item
        return spotlight

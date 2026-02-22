#!/usr/bin/env python3
"""
Attention Mechanism — GWT-Inspired Spotlight for Clarvis

Global Workspace Theory says consciousness is a spotlight: many modules process
in parallel, but only the most salient items win access to the global workspace
and get broadcast to all cognitive subsystems.

This module implements:
  - Spotlight: a limited-capacity buffer of high-salience items
  - Salience scoring: recency + importance + context-relevance + access frequency
  - Competition: items compete for spotlight slots; losers decay
  - Broadcasting: spotlight contents are available to all modules via focus()
  - Persistence: spotlight state persists across sessions via JSON + brain

Usage:
    from attention import attention

    attention.submit("user asked about memory architecture", source="conversation", relevance=0.9)
    attention.submit("cron job completed backup", source="system", relevance=0.3)

    focus = attention.focus()        # Get current spotlight contents
    attention.tick()                 # Run competition cycle (call periodically)
    attention.broadcast()            # Push spotlight to brain context
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')

ATTENTION_DIR = Path("/home/agent/.openclaw/workspace/data/attention")
ATTENTION_DIR.mkdir(parents=True, exist_ok=True)
SPOTLIGHT_FILE = ATTENTION_DIR / "spotlight.json"

# Spotlight capacity — inspired by cognitive science's 7 +/- 2 rule
SPOTLIGHT_CAPACITY = 7

# Salience weights
W_IMPORTANCE = 0.25
W_RECENCY = 0.20
W_RELEVANCE = 0.30
W_ACCESS = 0.10
W_BOOST = 0.15  # External boost (e.g., user explicitly mentioned it)

# Decay rate per tick for items NOT re-activated
DECAY_PER_TICK = 0.05
# Minimum salience before eviction
EVICTION_THRESHOLD = 0.1


class AttentionItem:
    """A single item competing for spotlight access."""

    def __init__(self, content, source="unknown", importance=0.5, relevance=0.5,
                 boost=0.0, item_id=None):
        self.id = item_id or f"attn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.content = content
        self.source = source
        self.importance = max(0.0, min(1.0, importance))
        self.relevance = max(0.0, min(1.0, relevance))
        self.boost = max(0.0, min(1.0, boost))
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_accessed = self.created_at
        self.access_count = 0
        self.ticks_in_spotlight = 0
        self.ticks_total = 0
        self._salience_cache = None

    def salience(self):
        """Compute composite salience score (0-1)."""
        now = datetime.now(timezone.utc)
        created = datetime.fromisoformat(self.created_at)
        age_hours = max(0.01, (now - created).total_seconds() / 3600)

        # Recency: exponential decay over hours (half-life ~6 hours)
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

        self._salience_cache = round(max(0.0, min(1.0, score)), 4)
        return self._salience_cache

    def touch(self):
        """Mark this item as accessed (reinforces salience)."""
        self.last_accessed = datetime.now(timezone.utc).isoformat()
        self.access_count += 1

    def decay(self, rate=DECAY_PER_TICK):
        """Decay relevance and boost (simulates losing attention)."""
        self.relevance = max(0.0, self.relevance - rate)
        self.boost = max(0.0, self.boost - rate * 2)  # Boost decays faster

    def to_dict(self):
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
    def from_dict(cls, d):
        item = cls(
            content=d["content"],
            source=d.get("source", "unknown"),
            importance=d.get("importance", 0.5),
            relevance=d.get("relevance", 0.5),
            boost=d.get("boost", 0.0),
            item_id=d["id"],
        )
        item.created_at = d.get("created_at", item.created_at)
        item.last_accessed = d.get("last_accessed", item.last_accessed)
        item.access_count = d.get("access_count", 0)
        item.ticks_in_spotlight = d.get("ticks_in_spotlight", 0)
        item.ticks_total = d.get("ticks_total", 0)
        return item


class AttentionSpotlight:
    """
    The global workspace spotlight. Items compete for limited slots.
    Only the top-K most salient items are 'in the spotlight' at any time.
    """

    def __init__(self, capacity=SPOTLIGHT_CAPACITY):
        self.capacity = capacity
        self.items = {}  # id -> AttentionItem (all candidates, not just spotlight)
        self._load()

    def _load(self):
        """Load persisted spotlight state."""
        if SPOTLIGHT_FILE.exists():
            try:
                data = json.loads(SPOTLIGHT_FILE.read_text())
                for d in data.get("items", []):
                    item = AttentionItem.from_dict(d)
                    self.items[item.id] = item
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Persist spotlight state."""
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "capacity": self.capacity,
            "items": [item.to_dict() for item in self.items.values()],
        }
        SPOTLIGHT_FILE.write_text(json.dumps(data, indent=2))

    def submit(self, content, source="unknown", importance=0.5, relevance=0.5,
               boost=0.0, item_id=None):
        """
        Submit an item for attention competition.
        If content matches an existing item, reinforces it instead of duplicating.

        Returns:
            The AttentionItem (new or reinforced)
        """
        # Check for duplicate content — reinforce instead
        for existing in self.items.values():
            if existing.content == content:
                existing.touch()
                existing.relevance = max(existing.relevance, relevance)
                existing.boost = max(existing.boost, boost)
                existing.importance = max(existing.importance, importance)
                self._save()
                return existing

        item = AttentionItem(
            content=content,
            source=source,
            importance=importance,
            relevance=relevance,
            boost=boost,
            item_id=item_id,
        )
        self.items[item.id] = item
        self._save()
        return item

    def focus(self):
        """
        Get current spotlight contents — the top-K items by salience.
        This is the 'conscious' content available to all modules.

        Returns:
            List of dicts representing spotlight items, sorted by salience (highest first)
        """
        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight = ranked[:self.capacity]

        # Touch spotlight items (accessing them reinforces them)
        for item in spotlight:
            item.touch()

        self._save()
        return [item.to_dict() for item in spotlight]

    def focus_summary(self):
        """
        Get a compact text summary of what's in the spotlight.
        Suitable for injecting into prompts or context windows.
        """
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

    def tick(self):
        """
        Run one competition cycle:
        1. Score all items
        2. Items in spotlight get ticks_in_spotlight incremented
        3. Items NOT in spotlight decay
        4. Items below eviction threshold get removed

        Call this periodically (e.g., every heartbeat).

        Returns:
            Dict with tick stats
        """
        if not self.items:
            return {"spotlight": 0, "decayed": 0, "evicted": 0, "total": 0}

        # Rank by salience
        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight_ids = {item.id for item in ranked[:self.capacity]}

        decayed = 0
        evicted = []

        for item in self.items.values():
            item.ticks_total += 1

            if item.id in spotlight_ids:
                item.ticks_in_spotlight += 1
            else:
                # Not in spotlight — decay
                item.decay()
                decayed += 1

                # Check for eviction
                if item.salience() < EVICTION_THRESHOLD:
                    evicted.append(item.id)

        # Evict
        for eid in evicted:
            del self.items[eid]

        self._save()
        return {
            "spotlight": len(spotlight_ids),
            "decayed": decayed,
            "evicted": len(evicted),
            "total": len(self.items),
        }

    def broadcast(self):
        """
        Broadcast spotlight contents to brain context.
        This is the GWT 'global broadcast' — making spotlight contents
        available system-wide.

        Returns:
            The broadcast summary string
        """
        from brain import brain

        summary = self.focus_summary()
        brain.set_context(summary)

        # Also store a snapshot for history
        brain.store(
            f"Attention broadcast: {summary}",
            collection="clarvis-context",
            importance=0.3,
            tags=["attention", "broadcast"],
            source="attention_mechanism",
        )

        return summary

    def query_relevant(self, query, n=3):
        """
        Find attention items most relevant to a query.
        Uses simple word overlap scoring (fast, no embedding needed).

        Args:
            query: text to match against
            n: max items to return

        Returns:
            List of matching items sorted by combined relevance + salience
        """
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

    def add(self, content, importance=0.5, source="system"):
        """
        Working-memory-compatible add method.
        Absorbs working_memory.py's add() — submits to spotlight competition.
        High-importance items (>=0.8) get a boost to auto-focus.
        """
        boost = 0.3 if importance >= 0.8 else 0.0
        return self.submit(
            content=content,
            source=source,
            importance=importance,
            relevance=max(0.5, importance),
            boost=boost,
        )

    def spreading_activation(self, query, n=5):
        """
        Spreading activation: boost attention items related to a query.
        Used by episodic memory to connect recall with current spotlight.

        Returns list of boosted item dicts sorted by combined score.
        """
        query_words = set(query.lower().split())
        boosted = []

        for item in self.items.values():
            item_words = set(item.content.lower().split())
            overlap = len(query_words & item_words)
            if overlap > 0:
                # Boost proportional to overlap
                activation_boost = min(0.3, overlap * 0.05)
                item.relevance = min(1.0, item.relevance + activation_boost)
                item.touch()
                boosted.append(item)

        self._save()
        boosted.sort(key=lambda x: x.salience(), reverse=True)
        return [item.to_dict() for item in boosted[:n]]

    def clear(self):
        """Clear all attention items (reset spotlight)."""
        self.items.clear()
        self._save()

    def stats(self):
        """Get attention system statistics."""
        if not self.items:
            return {
                "total_items": 0,
                "spotlight_size": 0,
                "avg_salience": 0,
                "sources": {},
            }

        ranked = sorted(self.items.values(), key=lambda x: x.salience(), reverse=True)
        spotlight = ranked[:self.capacity]

        sources = {}
        for item in self.items.values():
            sources[item.source] = sources.get(item.source, 0) + 1

        saliences = [item.salience() for item in self.items.values()]

        return {
            "total_items": len(self.items),
            "spotlight_size": len(spotlight),
            "capacity": self.capacity,
            "avg_salience": round(sum(saliences) / len(saliences), 4) if saliences else 0,
            "max_salience": round(max(saliences), 4) if saliences else 0,
            "min_salience": round(min(saliences), 4) if saliences else 0,
            "sources": sources,
            "spotlight_items": [s.content[:60] for s in spotlight],
        }


# --- Singleton ---
_attention = None

def get_attention():
    global _attention
    if _attention is None:
        _attention = AttentionSpotlight()
    return _attention

attention = get_attention()


# --- CLI ---
if __name__ == "__main__":
    import sys

    a = get_attention()

    if len(sys.argv) < 2:
        print("Usage: attention.py <command> [args]")
        print("Commands:")
        print("  add <text> [imp] - Add item (working memory compat)")
        print("  submit <text>    - Submit item for attention")
        print("  focus            - Show current spotlight")
        print("  tick             - Run competition cycle")
        print("  broadcast        - Push spotlight to brain context")
        print("  query <text>     - Find relevant attention items")
        print("  stats            - Show attention stats")
        print("  load             - Reload state from disk")
        print("  save             - Persist state to disk")
        print("  clear            - Reset spotlight")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "add" and len(sys.argv) > 2:
        # Compatible with working_memory.py CLI: add <text> [importance]
        text = sys.argv[2]
        importance = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        item = a.add(text, importance=importance, source="cli")
        print(f"Added: {item.id} (salience={item.salience():.3f})")

    elif cmd == "load":
        # Reload from disk (already happens on init, but explicit for compatibility)
        a._load()
        print(f"Loaded: {len(a.items)} items from disk")

    elif cmd == "save":
        a._save()
        print(f"Saved: {len(a.items)} items to {SPOTLIGHT_FILE}")

    elif cmd == "submit" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        item = a.submit(text, source="cli", importance=0.7, relevance=0.8)
        print(f"Submitted: {item.id} (salience={item.salience():.3f})")

    elif cmd == "focus":
        spotlight = a.focus()
        if not spotlight:
            print("Spotlight is empty.")
        else:
            print(f"=== Attention Spotlight ({len(spotlight)}/{a.capacity}) ===")
            for i, item in enumerate(spotlight):
                print(f"  {i+1}. [{item['salience']:.3f}] {item['content'][:80]}")
                print(f"     src={item['source']}  access={item['access_count']}  "
                      f"ticks={item['ticks_in_spotlight']}/{item['ticks_total']}")

    elif cmd == "tick":
        result = a.tick()
        print(f"Tick: spotlight={result['spotlight']}  decayed={result['decayed']}  "
              f"evicted={result['evicted']}  total={result['total']}")

    elif cmd == "broadcast":
        summary = a.broadcast()
        print(f"Broadcast:\n{summary}")

    elif cmd == "query" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = a.query_relevant(query)
        if not results:
            print("No relevant items found.")
        else:
            for r in results:
                print(f"  [{r['salience']:.3f}] {r['content'][:80]}")

    elif cmd == "stats":
        s = a.stats()
        print(json.dumps(s, indent=2))

    elif cmd == "clear":
        a.clear()
        print("Spotlight cleared.")

    else:
        print(f"Unknown command: {cmd}")

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


# === ATTENTION CODELETS (LIDA-inspired) ===
#
# Each codelet monitors one cognitive domain, scores attention items within
# that domain, and competes with other codelets for broadcast access.
# Coalitions form when multiple codelets activate on the same item.
# Winner-take-all: the strongest coalition determines heartbeat focus.

# Domain keyword definitions — each codelet recognizes its own domain
DOMAIN_KEYWORDS = {
    "memory": {
        "keywords": {"memory", "brain", "recall", "store", "chromadb", "clarvisdb",
                      "episodic", "semantic", "hebbian", "consolidat", "forget",
                      "retriev", "embed", "vector", "collection", "dedup"},
        "weight": 1.0,
    },
    "code": {
        "keywords": {"code", "script", "python", "function", "class", "refactor",
                      "bug", "fix", "implement", "test", "import", "module",
                      "syntax", "error", "package", "pip", "git", "pr"},
        "weight": 0.9,
    },
    "research": {
        "keywords": {"research", "paper", "arxiv", "bundle", "ingest", "learn",
                      "theory", "model", "lida", "gwt", "agi", "consciousness",
                      "phi", "neural", "cognitive", "architecture", "framework"},
        "weight": 0.95,
    },
    "infrastructure": {
        "keywords": {"cron", "gateway", "systemd", "backup", "health", "monitor",
                      "watchdog", "telegram", "budget", "cost", "update", "config",
                      "schedule", "vacuum", "compaction", "disk", "permission"},
        "weight": 0.85,
    },
}

CODELET_STATE_FILE = ATTENTION_DIR / "codelets.json"


class AttentionCodelet:
    """
    A LIDA-style attention codelet that monitors one cognitive domain.

    Each codelet:
      - Scans attention items for domain-relevant content
      - Computes an activation level based on how many relevant items it finds
      - Proposes items for the global workspace broadcast
    """

    def __init__(self, domain, keywords, weight=1.0):
        self.domain = domain
        self.keywords = keywords  # set of keyword stems
        self.weight = weight      # domain priority weight
        self.activation = 0.0     # current activation level [0-1]
        self.proposed_items = []  # items this codelet wants to broadcast
        self.wins = 0             # historical win count
        self.activations_history = []  # last N activation levels

    def scan(self, items):
        """
        Scan attention items and compute activation for this domain.

        Args:
            items: dict of id -> AttentionItem from the spotlight

        Returns:
            activation level (float 0-1)
        """
        self.proposed_items = []
        total_relevance = 0.0
        match_count = 0

        for item in items.values():
            content_lower = item.content.lower()
            # Count keyword matches (partial/stem matching)
            matches = sum(1 for kw in self.keywords if kw in content_lower)
            if matches > 0:
                # Item is relevant to this domain
                domain_relevance = min(1.0, matches / 3.0)  # saturates at 3 keywords
                combined = item.salience() * 0.6 + domain_relevance * 0.4
                total_relevance += combined
                match_count += 1
                self.proposed_items.append({
                    "item_id": item.id,
                    "content": item.content,
                    "salience": item.salience(),
                    "domain_relevance": round(domain_relevance, 3),
                    "combined": round(combined, 3),
                })

        # Activation: weighted combination of match density and total relevance
        if match_count > 0 and len(items) > 0:
            density = match_count / len(items)
            avg_relevance = total_relevance / match_count
            self.activation = round(
                min(1.0, (0.5 * density + 0.5 * avg_relevance) * self.weight),
                4,
            )
        else:
            self.activation = 0.0

        # Sort proposed items by combined score
        self.proposed_items.sort(key=lambda x: x["combined"], reverse=True)

        # Keep activation history (last 20)
        self.activations_history.append(self.activation)
        if len(self.activations_history) > 20:
            self.activations_history = self.activations_history[-20:]

        return self.activation

    def trend(self):
        """Activation trend: positive = gaining attention, negative = fading."""
        h = self.activations_history
        if len(h) < 2:
            return 0.0
        recent = sum(h[-3:]) / min(3, len(h[-3:]))
        older = sum(h[:-3]) / max(1, len(h[:-3])) if len(h) > 3 else recent
        return round(recent - older, 4)

    def to_dict(self):
        return {
            "domain": self.domain,
            "activation": self.activation,
            "weight": self.weight,
            "proposed_count": len(self.proposed_items),
            "wins": self.wins,
            "trend": self.trend(),
            "top_items": self.proposed_items[:3],
        }

    @classmethod
    def from_dict(cls, d):
        c = cls(
            domain=d["domain"],
            keywords=DOMAIN_KEYWORDS.get(d["domain"], {}).get("keywords", set()),
            weight=d.get("weight", 1.0),
        )
        c.activation = d.get("activation", 0.0)
        c.wins = d.get("wins", 0)
        c.activations_history = d.get("activations_history", [])
        return c


class CodeletCompetition:
    """
    Runs competing attention codelets (LIDA cognitive cycle).

    1. Each codelet scans attention items independently
    2. Codelets with overlapping proposed items form coalitions
    3. Winner-take-all: strongest coalition broadcasts to workspace
    4. Result: the winning domain(s) bias heartbeat task selection
    """

    def __init__(self, spotlight):
        self.spotlight = spotlight
        self.codelets = {}
        self._load()

        # Ensure all domains have codelets
        for domain, config in DOMAIN_KEYWORDS.items():
            if domain not in self.codelets:
                self.codelets[domain] = AttentionCodelet(
                    domain=domain,
                    keywords=config["keywords"],
                    weight=config["weight"],
                )

    def _load(self):
        """Load codelet state from disk."""
        if CODELET_STATE_FILE.exists():
            try:
                data = json.loads(CODELET_STATE_FILE.read_text())
                for cd in data.get("codelets", []):
                    codelet = AttentionCodelet.from_dict(cd)
                    self.codelets[codelet.domain] = codelet
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Persist codelet state."""
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "codelets": [c.to_dict() for c in self.codelets.values()],
        }
        CODELET_STATE_FILE.write_text(json.dumps(data, indent=2))

    def compete(self):
        """
        Run one competition cycle.

        Returns:
            dict with competition results:
            - winner: domain name of winning codelet (or coalition)
            - coalition: list of domains in winning coalition
            - activations: {domain: activation_level}
            - broadcast_items: items the winner proposes for broadcast
            - domain_bias: dict mapping domain -> bias score for task selection
        """
        items = self.spotlight.items

        # Phase 1: Each codelet scans independently
        activations = {}
        for domain, codelet in self.codelets.items():
            act = codelet.scan(items)
            activations[domain] = act

        # Phase 2: Coalition detection — codelets that share proposed items
        # build coalitions (reinforcing each other)
        coalitions = self._find_coalitions()

        # Phase 3: Winner-take-all — strongest activation wins
        # Coalition members get their activations summed (capped at 1.0)
        coalition_scores = {}
        for coalition_id, members in coalitions.items():
            score = min(1.0, sum(self.codelets[m].activation for m in members))
            coalition_scores[coalition_id] = {
                "members": members,
                "score": round(score, 4),
            }

        # Find winning coalition
        if coalition_scores:
            winner_id = max(coalition_scores, key=lambda k: coalition_scores[k]["score"])
            winner = coalition_scores[winner_id]
        else:
            # Fallback: single strongest codelet wins
            best_domain = max(activations, key=activations.get) if activations else "memory"
            winner = {"members": [best_domain], "score": activations.get(best_domain, 0.0)}

        # Record win
        for domain in winner["members"]:
            self.codelets[domain].wins += 1

        # Phase 4: Compute domain bias for task selection
        # Winner gets full bias, runner-up gets partial, others get minimal
        sorted_domains = sorted(activations.items(), key=lambda x: x[1], reverse=True)
        domain_bias = {}
        for rank, (domain, act) in enumerate(sorted_domains):
            if domain in winner["members"]:
                domain_bias[domain] = round(min(1.0, act + 0.2), 3)  # winner bonus
            elif rank < 2:
                domain_bias[domain] = round(act * 0.7, 3)  # runner-up
            else:
                domain_bias[domain] = round(act * 0.3, 3)  # suppressed

        # Gather broadcast items from winning coalition
        broadcast_items = []
        for domain in winner["members"]:
            broadcast_items.extend(self.codelets[domain].proposed_items[:2])
        broadcast_items.sort(key=lambda x: x["combined"], reverse=True)

        self._save()

        return {
            "winner": winner["members"][0],
            "coalition": winner["members"],
            "coalition_score": winner["score"],
            "activations": {d: round(a, 4) for d, a in activations.items()},
            "domain_bias": domain_bias,
            "broadcast_items": broadcast_items[:5],
            "trends": {d: c.trend() for d, c in self.codelets.items()},
        }

    def _find_coalitions(self):
        """
        Detect coalitions: codelets that share proposed items form a coalition.
        Returns dict of coalition_id -> list of domain names.
        """
        # Build item -> domains map
        item_domains = {}
        for domain, codelet in self.codelets.items():
            for proposed in codelet.proposed_items:
                iid = proposed["item_id"]
                if iid not in item_domains:
                    item_domains[iid] = set()
                item_domains[iid].add(domain)

        # Find clusters of overlapping domains
        coalitions = {}
        seen = set()
        coalition_id = 0

        for domains in item_domains.values():
            if len(domains) > 1:
                key = frozenset(domains)
                if key not in seen:
                    seen.add(key)
                    coalitions[coalition_id] = sorted(domains)
                    coalition_id += 1

        # Also add singleton codelets (each domain is its own minimal coalition)
        for domain, codelet in self.codelets.items():
            if codelet.activation > 0 and not any(domain in members for members in coalitions.values()):
                coalitions[coalition_id] = [domain]
                coalition_id += 1

        return coalitions

    def bias_for_task(self, task_text):
        """
        Compute how much the current codelet state biases toward a given task.

        Returns:
            float: bias score (-0.2 to +0.3) to add to task salience.
            Positive = task aligns with winning domain.
            Negative = task is off-focus.
        """
        text_lower = task_text.lower()

        # Which domains does this task match?
        task_domains = {}
        for domain, config in DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in config["keywords"] if kw in text_lower)
            if matches > 0:
                task_domains[domain] = min(1.0, matches / 3.0)

        if not task_domains:
            return 0.0  # neutral — task doesn't match any domain

        # Weight by codelet activation: tasks matching active codelets get boosted
        bias = 0.0
        for domain, relevance in task_domains.items():
            if domain in self.codelets:
                codelet = self.codelets[domain]
                # Active codelet + relevant task = positive bias
                bias += codelet.activation * relevance * 0.3
                # Trend bonus: rising domains get extra lift
                if codelet.trend() > 0:
                    bias += codelet.trend() * relevance * 0.1

        # Clamp to range
        return round(max(-0.2, min(0.3, bias)), 4)

    def stats(self):
        """Return codelet stats summary."""
        return {
            domain: {
                "activation": c.activation,
                "wins": c.wins,
                "trend": c.trend(),
                "proposed": len(c.proposed_items),
            }
            for domain, c in self.codelets.items()
        }


# --- Singleton ---
_attention = None
_codelet_competition = None

def get_attention():
    global _attention
    if _attention is None:
        _attention = AttentionSpotlight()
    return _attention

def get_codelet_competition():
    """Get the codelet competition system (lazy init)."""
    global _codelet_competition
    if _codelet_competition is None:
        _codelet_competition = CodeletCompetition(get_attention())
    return _codelet_competition

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
        print("  compete          - Run codelet competition cycle (LIDA)")
        print("  codelets         - Show codelet stats")
        print("  bias <text>      - Show codelet bias for a task")
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

    elif cmd == "compete":
        comp = get_codelet_competition()
        result = comp.compete()
        print("=== Codelet Competition (LIDA) ===")
        print(f"  Winner: {result['winner']} (coalition: {', '.join(result['coalition'])})")
        print(f"  Coalition score: {result['coalition_score']:.3f}")
        print("  Activations:")
        for domain, act in sorted(result['activations'].items(), key=lambda x: x[1], reverse=True):
            trend = result['trends'].get(domain, 0)
            trend_arrow = "↑" if trend > 0.01 else ("↓" if trend < -0.01 else "→")
            print(f"    {domain:15s} {act:.3f} {trend_arrow} (bias={result['domain_bias'].get(domain, 0):.3f})")
        if result['broadcast_items']:
            print(f"  Broadcast items ({len(result['broadcast_items'])}):")
            for bi in result['broadcast_items'][:3]:
                print(f"    [{bi['combined']:.3f}] {bi['content'][:70]}")

    elif cmd == "codelets":
        comp = get_codelet_competition()
        stats = comp.stats()
        print("=== Codelet Stats ===")
        for domain, s in sorted(stats.items(), key=lambda x: x[1]['activation'], reverse=True):
            trend_arrow = "↑" if s['trend'] > 0.01 else ("↓" if s['trend'] < -0.01 else "→")
            print(f"  {domain:15s} act={s['activation']:.3f} {trend_arrow}  "
                  f"wins={s['wins']}  proposed={s['proposed']}")

    elif cmd == "bias" and len(sys.argv) > 2:
        task_text = " ".join(sys.argv[2:])
        comp = get_codelet_competition()
        comp.compete()  # refresh activations
        bias = comp.bias_for_task(task_text)
        print(f"Codelet bias for task: {bias:+.4f}")
        for domain, s in comp.stats().items():
            kws = DOMAIN_KEYWORDS[domain]["keywords"]
            matches = sum(1 for kw in kws if kw in task_text.lower())
            if matches > 0:
                print(f"  {domain}: {matches} keyword hits, activation={s['activation']:.3f}")

    else:
        print(f"Unknown command: {cmd}")

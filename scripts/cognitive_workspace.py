#!/usr/bin/env python3
"""
Cognitive Workspace — Active Memory Management for Functional Infinite Context

Based on: Agarwal et al. (2025) "Cognitive Workspace: Active Memory Management
for LLMs — An Empirical Study of Functional Infinite Context" (arXiv:2508.13171)

Maps Baddeley's working memory model to Clarvis's cognitive architecture:

  Central Executive  →  CognitiveWorkspace (this module) — metacognitive controller
  Phonological Loop  →  ActiveBuffer       — immediate task context (cap: 5 items)
  Visuospatial Sketch→  WorkingBuffer      — session-level working set (cap: 12 items)
  Episodic Buffer    →  DormantBuffer      — compressed background (cap: 30 items)

Key innovations over the flat AttentionSpotlight:
  1. Hierarchical buffers with promotion/demotion between tiers
  2. Task-driven relevance scoring (not just salience decay)
  3. Dormant buffer enables memory REUSE (target: 58.6% per paper)
  4. Metacognitive controller decides keep/compress/evict based on task utility

Integration points:
  - attention.py: Spotlight items feed into ActiveBuffer
  - context_compressor.py: generate_tiered_brief() uses workspace.get_context()
  - heartbeat_preflight.py: workspace.set_task() at task start
  - heartbeat_postflight.py: workspace.close_task() archives active→dormant

Usage:
    from cognitive_workspace import workspace

    workspace.set_task("implement feature X")     # Focus active buffer on task
    workspace.ingest("relevant finding", tier="active", source="research")
    context = workspace.get_context(budget=600)    # Task-optimized context string
    workspace.close_task(outcome="success")        # Demote active→dormant, track reuse
"""

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

WORKSPACE_DIR = Path("/home/agent/.openclaw/workspace/data/cognitive_workspace")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = WORKSPACE_DIR / "workspace_state.json"
REUSE_LOG = WORKSPACE_DIR / "reuse_log.jsonl"

# Buffer capacities — inspired by cognitive science constraints
ACTIVE_CAPACITY = 5     # Immediate task focus (~phonological loop, 3-5 chunks)
WORKING_CAPACITY = 12   # Session working set (~7±2 expanded for cross-task)
DORMANT_CAPACITY = 30   # Compressed background (episodic buffer, larger)

# Reuse threshold — item must have relevance > this to be reactivated from dormant
REUSE_RELEVANCE_THRESHOLD = 0.3

# Compression: items in dormant buffer get summarized to this max length
DORMANT_SUMMARY_MAX = 120


class WorkspaceItem:
    """A single item in the cognitive workspace hierarchy."""

    def __init__(self, content, source="unknown", importance=0.5, tier="working",
                 item_id=None, task_context="", summary=None):
        self.id = item_id or f"cw_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.content = content
        self.summary = summary  # compressed form for dormant tier
        self.source = source
        self.importance = max(0.0, min(1.0, importance))
        self.tier = tier  # "active", "working", "dormant"
        self.task_context = task_context  # which task this item was ingested for
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_accessed = self.created_at
        self.access_count = 0
        self.reuse_count = 0  # how many different tasks have used this item
        self.tasks_used_in = set()  # task IDs that accessed this item

    def relevance_to(self, query):
        """Compute task-driven relevance score (0-1) for a query/task.

        Uses word + bigram overlap, importance, recency, and reuse-history
        weighting. Items proven useful across multiple tasks get a boost.
        """
        if not query:
            return self.importance * 0.5

        text = (self.content + " " + (self.summary or "")).lower()
        query_words = re.findall(r'[a-z]{3,}', query.lower())
        text_words = re.findall(r'[a-z]{3,}', text)

        query_set = set(query_words)
        text_set = set(text_words)

        if not query_set or not text_set:
            return self.importance * 0.3

        # Unigram Jaccard overlap
        jaccard = len(query_set & text_set) / max(1, len(query_set | text_set))

        # Bigram overlap — catches partial phrase matches (e.g. "reuse rate")
        def bigrams(words):
            return set(zip(words, words[1:])) if len(words) > 1 else set()
        q_bi = bigrams(query_words)
        t_bi = bigrams(text_words)
        bigram_score = len(q_bi & t_bi) / max(1, len(q_bi | t_bi)) if q_bi else 0.0

        # Recency — slower decay than attention (half-life ~14h)
        now = datetime.now(timezone.utc)
        try:
            created = datetime.fromisoformat(self.created_at)
            age_hours = max(0.01, (now - created).total_seconds() / 3600)
        except (ValueError, TypeError):
            age_hours = 24
        recency = math.exp(-0.05 * age_hours)

        # Reuse history boost — items used across 2+ tasks are proven valuable
        reuse_bonus = min(0.15, 0.05 * len(self.tasks_used_in))

        # Composite: word match 40%, bigram 15%, importance 20%, recency 15%, reuse 10%
        score = (jaccard * 0.40 + bigram_score * 0.15 + self.importance * 0.20
                 + recency * 0.15 + reuse_bonus)
        return min(1.0, score)

    def touch(self, task_id=None):
        """Mark as accessed. Tracks cross-task reuse."""
        self.last_accessed = datetime.now(timezone.utc).isoformat()
        self.access_count += 1
        if task_id:
            was_new = task_id not in self.tasks_used_in
            self.tasks_used_in.add(task_id)
            if was_new and len(self.tasks_used_in) > 1:
                self.reuse_count += 1
            return was_new
        return False

    def compress(self):
        """Create a compressed summary for dormant storage."""
        if self.summary:
            return self.summary
        # Truncate to key content, strip redundant whitespace
        text = re.sub(r'\s+', ' ', self.content).strip()
        if len(text) > DORMANT_SUMMARY_MAX:
            # Keep first and last parts (primacy + recency)
            half = DORMANT_SUMMARY_MAX // 2 - 3
            text = text[:half] + "..." + text[-half:]
        self.summary = text
        return self.summary

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "summary": self.summary,
            "source": self.source,
            "importance": self.importance,
            "tier": self.tier,
            "task_context": self.task_context,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "reuse_count": self.reuse_count,
            "tasks_used_in": list(self.tasks_used_in),
        }

    @classmethod
    def from_dict(cls, d):
        item = cls(
            content=d["content"],
            source=d.get("source", "unknown"),
            importance=d.get("importance", 0.5),
            tier=d.get("tier", "working"),
            item_id=d["id"],
            task_context=d.get("task_context", ""),
            summary=d.get("summary"),
        )
        item.created_at = d.get("created_at", item.created_at)
        item.last_accessed = d.get("last_accessed", item.last_accessed)
        item.access_count = d.get("access_count", 0)
        item.reuse_count = d.get("reuse_count", 0)
        item.tasks_used_in = set(d.get("tasks_used_in", []))
        return item


class CognitiveWorkspace:
    """
    Metacognitive controller implementing hierarchical buffer management.

    Manages three tiers inspired by Baddeley's working memory model:
      - Active:  Items directly relevant to the current task (central executive focus)
      - Working: Session-level items not yet demoted (phonological loop analog)
      - Dormant: Compressed background items available for reuse (episodic buffer)

    The controller actively manages memory by:
      1. Promoting dormant items when they're relevant to a new task (reuse)
      2. Demoting active items when a task completes (compression)
      3. Evicting dormant items with lowest utility (capacity management)
    """

    def __init__(self):
        self.items = {}  # id -> WorkspaceItem
        self.current_task = ""
        self.current_task_id = ""
        self.task_history = []  # recent task IDs for reuse tracking
        self._reuse_hits = 0  # items reused from dormant in current session
        self._reuse_total = 0  # total items accessed in current session
        self._load()

    def _load(self):
        """Load persisted workspace state."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                for d in data.get("items", []):
                    item = WorkspaceItem.from_dict(d)
                    self.items[item.id] = item
                self.current_task = data.get("current_task", "")
                self.current_task_id = data.get("current_task_id", "")
                self.task_history = data.get("task_history", [])
                self._reuse_hits = data.get("reuse_hits", 0)
                self._reuse_total = data.get("reuse_total", 0)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Persist workspace state."""
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "current_task": self.current_task,
            "current_task_id": self.current_task_id,
            "task_history": self.task_history[-20:],  # keep last 20
            "reuse_hits": self._reuse_hits,
            "reuse_total": self._reuse_total,
            "items": [item.to_dict() for item in self.items.values()],
            "buffer_sizes": self._buffer_sizes(),
            "reuse_rate": self.reuse_rate(),
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def _buffer_sizes(self):
        """Count items per tier."""
        sizes = {"active": 0, "working": 0, "dormant": 0}
        for item in self.items.values():
            sizes[item.tier] = sizes.get(item.tier, 0) + 1
        return sizes

    # ========= METACOGNITIVE CONTROLLER =========

    def set_task(self, task_description, task_id=None):
        """Set the current task — triggers active buffer reorganization.

        1. Demotes previous active items to working
        2. Scans dormant buffer for reusable items (promotes relevant ones)
        3. Sets task context for new items

        This is the core "task-driven context optimization" from the paper.
        """
        # Generate task ID
        if not task_id:
            task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Demote current active items to working
        for item in self.items.values():
            if item.tier == "active":
                item.tier = "working"

        self.current_task = task_description
        self.current_task_id = task_id
        if task_id not in self.task_history:
            self.task_history.append(task_id)

        # Scan dormant for reusable items (the 58.6% mechanism)
        reactivated = self._reactivate_dormant(task_description, task_id)

        # Enforce capacity: demote excess working → dormant
        self._enforce_capacity()
        self._save()

        return {
            "task_id": task_id,
            "reactivated": reactivated,
            "buffers": self._buffer_sizes(),
        }

    def close_task(self, outcome="success", lesson=""):
        """Close the current task — archives active buffer to dormant.

        1. Compresses active items and moves to dormant
        2. Records reuse metrics
        3. Optionally stores a lesson from the task outcome
        """
        closed = 0
        for item in list(self.items.values()):
            if item.tier == "active":
                item.tier = "dormant"
                item.compress()
                closed += 1

        # Store task outcome as a dormant item for future reuse
        if lesson:
            self.ingest(
                f"[{outcome}] {self.current_task[:60]}: {lesson}",
                tier="dormant",
                source="task_outcome",
                importance=0.6 if outcome == "success" else 0.7,
            )

        # Log reuse stats
        rate = self.reuse_rate()
        self._log_reuse(self.current_task_id, rate)

        prev_task = self.current_task
        self.current_task = ""
        self.current_task_id = ""

        self._enforce_capacity()
        self._save()

        return {
            "closed_items": closed,
            "reuse_rate": rate,
            "task": prev_task[:60],
            "buffers": self._buffer_sizes(),
        }

    def ingest(self, content, tier="working", source="unknown", importance=0.5):
        """Ingest a new item into the workspace.

        If content matches existing item, reinforces rather than duplicates.
        """
        # Dedup check
        for existing in self.items.values():
            if existing.content == content:
                existing.touch(self.current_task_id)
                existing.importance = max(existing.importance, importance)
                self._reuse_total += 1
                if existing.tier == "dormant":
                    self._reuse_hits += 1
                self._save()
                return existing

        item = WorkspaceItem(
            content=content,
            source=source,
            importance=importance,
            tier=tier,
            task_context=self.current_task,
        )
        if self.current_task_id:
            item.tasks_used_in.add(self.current_task_id)

        self.items[item.id] = item
        self._reuse_total += 1

        self._enforce_capacity()
        self._save()
        return item

    def get_context(self, budget=600, task_query=None):
        """Generate task-optimized context string from workspace buffers.

        Draws from all tiers with task-driven relevance scoring:
          - Active items: included verbatim (highest priority)
          - Working items: included if relevant to task_query
          - Dormant items: included (compressed form) if highly relevant

        Args:
            budget: approximate token budget (1 token ≈ 4 chars)
            task_query: task text for relevance scoring (defaults to current_task)

        Returns:
            Structured context string with buffer markers.
        """
        query = task_query or self.current_task
        char_budget = budget * 4  # ~4 chars per token

        parts = []
        used_chars = 0

        # === Active buffer (always included, verbatim) ===
        active_items = [i for i in self.items.values() if i.tier == "active"]
        active_items.sort(key=lambda x: x.importance, reverse=True)
        if active_items:
            parts.append("ACTIVE CONTEXT:")
            for item in active_items[:ACTIVE_CAPACITY]:
                text = f"  [{item.importance:.1f}] {item.content[:200]}"
                used_chars += len(text)
                parts.append(text)
                item.touch(self.current_task_id)

        # === Working buffer (filtered by relevance) ===
        working_items = [i for i in self.items.values() if i.tier == "working"]
        # Score by task relevance
        scored_working = [(i.relevance_to(query), i) for i in working_items]
        scored_working.sort(key=lambda x: x[0], reverse=True)

        remaining = char_budget - used_chars
        if scored_working and remaining > 100:
            parts.append("WORKING CONTEXT:")
            for rel, item in scored_working:
                if rel < 0.15:
                    break
                text = f"  ({rel:.2f}) {item.content[:150]}"
                if used_chars + len(text) > char_budget * 0.75:
                    break
                parts.append(text)
                used_chars += len(text)
                item.touch(self.current_task_id)

        # === Dormant buffer (compressed, only high-relevance) ===
        used_chars = self._collect_dormant_context(parts, query, char_budget, used_chars)

        # Footer with stats
        sizes = self._buffer_sizes()
        rate = self.reuse_rate()
        parts.append(f"--- workspace: active={sizes['active']}, working={sizes['working']}, dormant={sizes['dormant']}, reuse={rate:.0%}")

        return "\n".join(parts)

    def _collect_dormant_context(self, parts, query, char_budget, used_chars):
        """Collect high-relevance dormant items into context parts.

        Returns updated used_chars count.
        """
        dormant_items = [i for i in self.items.values() if i.tier == "dormant"]
        scored_dormant = [(i.relevance_to(query), i) for i in dormant_items]
        scored_dormant.sort(key=lambda x: x[0], reverse=True)

        remaining = char_budget - used_chars
        if not scored_dormant or remaining <= 80:
            return used_chars

        dormant_shown = []
        for rel, item in scored_dormant:
            if rel < REUSE_RELEVANCE_THRESHOLD:
                break
            display = item.summary or item.compress()
            text = f"  ({rel:.2f}) {display}"
            if used_chars + len(text) > char_budget:
                break
            dormant_shown.append(text)
            used_chars += len(text)
            item.touch(self.current_task_id)
            if len(item.tasks_used_in) > 1:
                self._reuse_hits += 1

        if dormant_shown:
            parts.append("REUSED CONTEXT (dormant):")
            parts.extend(dormant_shown)

        return used_chars

    def reuse_rate(self):
        """Compute memory reuse rate (paper target: 58.6%).

        Reuse = items accessed from dormant / total items accessed.
        """
        if self._reuse_total == 0:
            return 0.0
        return self._reuse_hits / self._reuse_total

    # ========= INTERNAL MECHANISMS =========

    def _reactivate_dormant(self, task_description, task_id):
        """Scan dormant buffer and promote relevant items to active.

        This is the key mechanism for achieving the paper's 58.6% reuse rate.
        Items are promoted (not copied) — they move from dormant to active.
        """
        reactivated = []
        dormant = [i for i in self.items.values() if i.tier == "dormant"]

        for item in dormant:
            rel = item.relevance_to(task_description)
            # Adaptive threshold: proven items (reused 2+ times) get a lower bar
            threshold = REUSE_RELEVANCE_THRESHOLD
            if len(item.tasks_used_in) >= 2:
                threshold = max(0.15, threshold - 0.10)
            if rel >= threshold:
                # Promote to active
                item.tier = "active"
                item.touch(task_id)
                self._reuse_hits += 1
                self._reuse_total += 1
                reactivated.append({
                    "id": item.id,
                    "relevance": round(rel, 3),
                    "reuse_count": item.reuse_count,
                    "summary": (item.summary or item.content)[:80],
                })

        # Cap active reactivations to avoid flooding
        if len(reactivated) > ACTIVE_CAPACITY - 1:
            # Keep only the most relevant
            reactivated.sort(key=lambda x: x["relevance"], reverse=True)
            keep_ids = {r["id"] for r in reactivated[:ACTIVE_CAPACITY - 1]}
            for r in reactivated[ACTIVE_CAPACITY - 1:]:
                if r["id"] in self.items:
                    self.items[r["id"]].tier = "working"  # demote overflow to working
            reactivated = reactivated[:ACTIVE_CAPACITY - 1]

        return reactivated

    def _enforce_capacity(self):
        """Enforce buffer capacities with demotion cascade.

        Active overflow → working. Working overflow → dormant. Dormant overflow → evict.
        """
        # Active → working overflow
        active = [i for i in self.items.values() if i.tier == "active"]
        if len(active) > ACTIVE_CAPACITY:
            active.sort(key=lambda x: x.relevance_to(self.current_task))
            for item in active[:len(active) - ACTIVE_CAPACITY]:
                item.tier = "working"

        # Working → dormant overflow
        working = [i for i in self.items.values() if i.tier == "working"]
        if len(working) > WORKING_CAPACITY:
            working.sort(key=lambda x: x.relevance_to(self.current_task))
            for item in working[:len(working) - WORKING_CAPACITY]:
                item.tier = "dormant"
                item.compress()

        # Dormant → evict overflow (lowest utility first)
        dormant = [i for i in self.items.values() if i.tier == "dormant"]
        if len(dormant) > DORMANT_CAPACITY:
            # Utility = importance * (1 + reuse_count) * recency
            def utility(item):
                now = datetime.now(timezone.utc)
                try:
                    last = datetime.fromisoformat(item.last_accessed)
                    age_hours = max(0.01, (now - last).total_seconds() / 3600)
                except (ValueError, TypeError):
                    age_hours = 168  # 1 week
                recency = math.exp(-0.02 * age_hours)  # very slow decay
                return item.importance * (1 + item.reuse_count) * recency

            dormant.sort(key=utility)
            to_evict = dormant[:len(dormant) - DORMANT_CAPACITY]
            for item in to_evict:
                del self.items[item.id]

    def _log_reuse(self, task_id, rate):
        """Append reuse event to JSONL log for trend tracking."""
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task_id,
                "reuse_rate": round(rate, 4),
                "reuse_hits": self._reuse_hits,
                "reuse_total": self._reuse_total,
                "buffers": self._buffer_sizes(),
            }
            with open(REUSE_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def sync_from_spotlight(self):
        """Import current attention spotlight items into working buffer.

        Bridge between the existing AttentionSpotlight (attention.py) and this
        cognitive workspace. Called at session start or after spotlight updates.
        """
        try:
            from attention import attention
            focus = attention.focus()
            imported = 0
            for item_data in focus:
                content = item_data.get("content", "")
                if not content:
                    continue
                # Check for duplication
                exists = any(
                    i.content == content
                    for i in self.items.values()
                )
                if exists:
                    continue
                self.ingest(
                    content,
                    tier="working",
                    source="spotlight",
                    importance=item_data.get("importance", 0.5),
                )
                imported += 1
            return imported
        except Exception as e:
            return 0

    def stats(self):
        """Full workspace statistics."""
        sizes = self._buffer_sizes()
        return {
            "buffers": sizes,
            "total_items": len(self.items),
            "current_task": self.current_task[:60] if self.current_task else None,
            "reuse_rate": round(self.reuse_rate(), 4),
            "reuse_hits": self._reuse_hits,
            "reuse_total": self._reuse_total,
            "task_history_len": len(self.task_history),
            "sources": _count_sources(self.items),
        }

    def health(self):
        """Quick health check for integration into health_monitor."""
        sizes = self._buffer_sizes()
        total = sum(sizes.values())
        rate = self.reuse_rate()
        issues = []

        if sizes["active"] > ACTIVE_CAPACITY:
            issues.append(f"active buffer overflow ({sizes['active']} > {ACTIVE_CAPACITY})")
        if sizes["dormant"] > DORMANT_CAPACITY:
            issues.append(f"dormant buffer overflow ({sizes['dormant']} > {DORMANT_CAPACITY})")
        if total > 0 and rate < 0.1 and self._reuse_total > 10:
            issues.append(f"low reuse rate ({rate:.1%}), check dormant quality")

        return {
            "status": "HEALTHY" if not issues else "DEGRADED",
            "issues": issues,
            "buffers": sizes,
            "reuse_rate": round(rate, 4),
        }


def _count_sources(items):
    """Count items by source."""
    sources = {}
    for item in items.values():
        sources[item.source] = sources.get(item.source, 0) + 1
    return sources


# === Lazy singleton ===
class _LazyWorkspace:
    _instance = None

    def __getattr__(self, name):
        if _LazyWorkspace._instance is None:
            _LazyWorkspace._instance = CognitiveWorkspace()
        return getattr(_LazyWorkspace._instance, name)

workspace = _LazyWorkspace()


# === CLI ===
if __name__ == "__main__":
    ws = CognitiveWorkspace()

    if len(sys.argv) < 2:
        print("Cognitive Workspace — Hierarchical Active Memory Management")
        print(json.dumps(ws.stats(), indent=2))
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        print(json.dumps(ws.stats(), indent=2))

    elif cmd == "health":
        print(json.dumps(ws.health(), indent=2))

    elif cmd == "set-task":
        task = sys.argv[2] if len(sys.argv) > 2 else "unnamed task"
        result = ws.set_task(task)
        print(json.dumps(result, indent=2))

    elif cmd == "close-task":
        outcome = sys.argv[2] if len(sys.argv) > 2 else "success"
        lesson = sys.argv[3] if len(sys.argv) > 3 else ""
        result = ws.close_task(outcome=outcome, lesson=lesson)
        print(json.dumps(result, indent=2))

    elif cmd == "ingest":
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        tier = sys.argv[3] if len(sys.argv) > 3 else "working"
        importance = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        if content:
            item = ws.ingest(content, tier=tier, importance=importance)
            print(f"Ingested: {item.id} → {item.tier}")
        else:
            print("Usage: cognitive_workspace.py ingest <content> [tier] [importance]")

    elif cmd == "context":
        budget = int(sys.argv[2]) if len(sys.argv) > 2 else 600
        task = sys.argv[3] if len(sys.argv) > 3 else ""
        print(ws.get_context(budget=budget, task_query=task or None))

    elif cmd == "sync":
        imported = ws.sync_from_spotlight()
        print(f"Synced {imported} items from attention spotlight")

    elif cmd == "reuse-rate":
        rate = ws.reuse_rate()
        print(f"Memory reuse rate: {rate:.1%} (target: 58.6%)")
        print(f"  Hits: {ws._reuse_hits}, Total: {ws._reuse_total}")

    elif cmd == "buffers":
        sizes = ws._buffer_sizes()
        print(f"Active:  {sizes['active']}/{ACTIVE_CAPACITY}")
        print(f"Working: {sizes['working']}/{WORKING_CAPACITY}")
        print(f"Dormant: {sizes['dormant']}/{DORMANT_CAPACITY}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: stats, health, set-task, close-task, ingest, context, sync, reuse-rate, buffers")

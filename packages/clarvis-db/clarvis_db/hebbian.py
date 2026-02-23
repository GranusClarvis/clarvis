"""
Hebbian learning for vector memories.

"Cells that fire together wire together" — co-retrieved memories form
stronger associations. Retrieval = rehearsal (log-scaled reinforcement).
Neglect = power-law decay (ACT-R inspired, not linear TTL).

Standalone: no ChromaDB dependency. Works on any dict-based memory store.
"""

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple


# === DEFAULTS ===

REINFORCEMENT_BASE = 0.02
REINFORCEMENT_DECAY = 0.7
MAX_IMPORTANCE = 0.95
MIN_IMPORTANCE = 0.05
COACTIVATION_WINDOW_S = 300
ASSOCIATION_BOOST = 0.15
ASSOCIATION_DECAY = 0.01
DECAY_EXPONENT = 0.5
DECAY_GRACE_DAYS = 1
DECAY_FLOOR_MULTIPLIER = 0.3
STRENGTHEN_THRESHOLD = 3
WEAKEN_THRESHOLD_DAYS = 14


class HebbianEngine:
    """Hebbian learning engine for memory importance evolution.

    Tracks access patterns and co-activation to strengthen/weaken memories.
    Works with any store that exposes get/upsert operations on metadata dicts.

    Args:
        data_dir: Directory for access logs and co-activation data.
        on_strengthen: Callback(memory_id, old_importance, new_importance).
        on_weaken: Callback(memory_id, old_importance, new_importance).
    """

    def __init__(
        self,
        data_dir: str = "./data/hebbian",
        on_strengthen: Optional[Callable] = None,
        on_weaken: Optional[Callable] = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.access_log_file = self.data_dir / "access_log.jsonl"
        self.coactivation_file = self.data_dir / "coactivation.json"
        self.evolution_file = self.data_dir / "evolution_history.jsonl"
        self.stats_file = self.data_dir / "stats.json"
        self.on_strengthen = on_strengthen
        self.on_weaken = on_weaken
        self._coactivation = self._load_coactivation()

    # === ACCESS TRACKING ===

    def on_recall(self, query: str, memory_ids: List[str], caller: Optional[str] = None):
        """Called after retrieval — log access and update co-activation.

        Args:
            query: The recall query.
            memory_ids: IDs of retrieved memories.
            caller: Who triggered the recall.
        """
        if not memory_ids:
            return

        now = datetime.now(timezone.utc)
        for mem_id in memory_ids:
            self._log_access(mem_id, query, caller, now)

        if len(memory_ids) >= 2:
            self._update_coactivation(memory_ids, now)

    def reinforce(self, memory_id: str, current_importance: float, access_count: int) -> float:
        """Compute reinforced importance for a memory.

        Log-scaled reinforcement with diminishing returns.

        Args:
            memory_id: The memory being reinforced.
            current_importance: Current importance value.
            access_count: How many times it's been accessed.

        Returns:
            New importance value.
        """
        boost = REINFORCEMENT_BASE * (max(1, access_count) ** (-REINFORCEMENT_DECAY))
        new_importance = min(MAX_IMPORTANCE, current_importance + boost)

        if self.on_strengthen and new_importance > current_importance + 0.001:
            self.on_strengthen(memory_id, current_importance, new_importance)

        return round(new_importance, 4)

    # === CO-ACTIVATION ===

    def get_associations(self, memory_id: str, min_strength: float = 0.1) -> List[Tuple[str, float]]:
        """Get memories associated with the given memory via co-activation.

        Args:
            memory_id: Source memory ID.
            min_strength: Minimum association strength.

        Returns:
            List of (other_memory_id, strength) tuples.
        """
        result = []
        for pair_key, entry in self._coactivation.items():
            if entry.get("strength", 0) < min_strength:
                continue
            ids = entry.get("ids", [])
            if len(ids) == 2 and memory_id in ids:
                other = ids[1] if ids[0] == memory_id else ids[0]
                result.append((other, entry["strength"]))
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    # === DECAY ===

    def compute_decay(
        self,
        current_importance: float,
        days_since_access: float,
        access_count: int = 0,
        original_importance: Optional[float] = None,
    ) -> float:
        """Compute decayed importance using power-law.

        Args:
            current_importance: Current importance.
            days_since_access: Days since last access.
            access_count: Total access count (high = slower decay).
            original_importance: Original importance (for floor calculation).

        Returns:
            New importance (may be unchanged if within grace period).
        """
        if original_importance is None:
            original_importance = current_importance

        if days_since_access <= DECAY_GRACE_DAYS:
            return current_importance

        # Frequently accessed memories decay more slowly
        if access_count >= STRENGTHEN_THRESHOLD:
            effective_days = days_since_access / (1 + math.log1p(access_count))
        else:
            effective_days = days_since_access

        if effective_days <= DECAY_GRACE_DAYS:
            return current_importance

        decay_factor = effective_days ** (-DECAY_EXPONENT)
        decay_factor = max(0.5, min(1.0, decay_factor))

        new_importance = current_importance * decay_factor
        floor = max(MIN_IMPORTANCE, original_importance * DECAY_FLOOR_MULTIPLIER)
        new_importance = max(floor, new_importance)

        return round(new_importance, 4)

    # === EVOLUTION CYCLE ===

    def evolve(self, memories: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """Run a full Hebbian evolution cycle over a list of memories.

        Each memory dict must have: id, importance, access_count, last_accessed (ISO).
        Optionally: original_importance.

        Args:
            memories: List of memory metadata dicts.
            dry_run: If True, compute but don't mutate.

        Returns:
            Stats dict with counts of strengthened/weakened memories.
        """
        now = datetime.now(timezone.utc)
        stats = {
            "timestamp": now.isoformat(),
            "total_scanned": len(memories),
            "strengthened": 0,
            "weakened": 0,
            "associations_decayed": 0,
            "dry_run": dry_run,
        }

        for mem in memories:
            importance = _safe_float(mem.get("importance", 0.5))
            access_count = _safe_int(mem.get("access_count", 0))
            original = _safe_float(mem.get("original_importance", importance))
            last_accessed = mem.get("last_accessed")

            if not last_accessed:
                continue

            try:
                last_dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            days_since = (now - last_dt).total_seconds() / 86400.0
            new_importance = self.compute_decay(importance, days_since, access_count, original)

            if new_importance < importance - 0.001:
                stats["weakened"] += 1
                if not dry_run:
                    mem["importance"] = new_importance
                    mem["original_importance"] = mem.get("original_importance", importance)
                    if self.on_weaken:
                        self.on_weaken(mem.get("id", ""), importance, new_importance)
            elif access_count >= STRENGTHEN_THRESHOLD and importance < 0.7:
                boost = REINFORCEMENT_BASE * math.log1p(access_count)
                new_importance = min(MAX_IMPORTANCE, importance + boost)
                new_importance = round(new_importance, 4)
                if new_importance > importance + 0.001:
                    stats["strengthened"] += 1
                    if not dry_run:
                        mem["importance"] = new_importance
                        if self.on_strengthen:
                            self.on_strengthen(mem.get("id", ""), importance, new_importance)

        # Decay stale co-activation associations
        pairs_to_remove = []
        for pair_key, entry in self._coactivation.items():
            try:
                last_seen = datetime.fromisoformat(entry["last_seen"].replace("Z", "+00:00"))
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError, KeyError):
                pairs_to_remove.append(pair_key)
                continue

            days_since_coactive = (now - last_seen).total_seconds() / 86400.0
            if days_since_coactive > 7:
                entry["strength"] = max(0.0, entry["strength"] - ASSOCIATION_DECAY * days_since_coactive)
                if entry["strength"] < 0.01:
                    pairs_to_remove.append(pair_key)
                else:
                    stats["associations_decayed"] += 1

        for key in pairs_to_remove:
            self._coactivation.pop(key, None)
        if not dry_run:
            self._save_coactivation()

        # Log
        if not dry_run:
            with open(self.evolution_file, "a") as f:
                f.write(json.dumps(stats) + "\n")
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=2)

        return stats

    # === DIAGNOSTICS ===

    def get_access_patterns(self, days: int = 7) -> Dict[str, Any]:
        """Analyze access patterns from the log."""
        if not self.access_log_file.exists():
            return {"total_events": 0, "memories": {}}

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        memory_counts: Dict[str, int] = defaultdict(int)
        caller_counts: Dict[str, int] = defaultdict(int)
        total = 0

        with open(self.access_log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("timestamp", "") >= cutoff:
                        memory_counts[event["memory_id"]] += 1
                        caller_counts[event.get("caller", "unknown")] += 1
                        total += 1
                except (json.JSONDecodeError, KeyError):
                    continue

        top = sorted(memory_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        return {
            "total_events": total,
            "unique_memories": len(memory_counts),
            "top_accessed": top,
            "caller_breakdown": dict(caller_counts),
            "period_days": days,
        }

    def coactivation_stats(self) -> Dict[str, Any]:
        """Stats about co-activation network."""
        total = len(self._coactivation)
        strong = sum(1 for e in self._coactivation.values() if e.get("strength", 0) > 0.3)
        return {"total_pairs": total, "strong_pairs": strong}

    # === INTERNAL ===

    def _log_access(self, mem_id, query, caller, now):
        event = {
            "memory_id": mem_id,
            "query": query[:200] if query else "",
            "caller": caller or "unknown",
            "timestamp": now.isoformat(),
        }
        with open(self.access_log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def _load_coactivation(self):
        if self.coactivation_file.exists():
            try:
                with open(self.coactivation_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_coactivation(self):
        with open(self.coactivation_file, "w") as f:
            json.dump(self._coactivation, f)

    def _update_coactivation(self, memory_ids, now):
        for i, id_a in enumerate(memory_ids):
            for id_b in memory_ids[i + 1:]:
                pair_key = "|".join(sorted([id_a, id_b]))
                if pair_key not in self._coactivation:
                    self._coactivation[pair_key] = {
                        "ids": sorted([id_a, id_b]),
                        "count": 0,
                        "first_seen": now.isoformat(),
                        "last_seen": now.isoformat(),
                        "strength": 0.0,
                    }
                entry = self._coactivation[pair_key]
                entry["count"] += 1
                entry["last_seen"] = now.isoformat()
                entry["strength"] = min(
                    1.0,
                    entry["strength"] + ASSOCIATION_BOOST * (entry["count"] ** -0.5),
                )
        self._save_coactivation()


def _safe_float(v, default=0.5):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _safe_int(v, default=0):
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except (ValueError, TypeError):
        return default

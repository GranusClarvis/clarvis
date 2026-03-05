#!/usr/bin/env python3
"""
Hebbian Memory Evolution — A-Mem style memory strengthening/weakening.

Memories strengthen when accessed (retrieved) and weaken when neglected.
Co-accessed memories form stronger associations. This replaces the simple
TTL-based decay with biologically-inspired Hebbian learning.

Core Principles:
  1. "Cells that fire together wire together" — co-retrieved memories
     strengthen their graph edges (association weight)
  2. Retrieval = rehearsal — accessing a memory boosts its importance
     following a log-scaled reinforcement curve (diminishing returns)
  3. Neglect = decay — unaccessed memories lose importance via power-law
     (not linear TTL), matching ACT-R base-level activation
  4. Memories evolve — when new info arrives that's semantically close
     to an existing memory, the existing memory's importance gets a
     context-boost (spreading activation from storage)

Usage:
    from hebbian_memory import hebbian

    # After a recall event — strengthen retrieved memories
    hebbian.on_recall(query, results)

    # Run periodic evolution (nightly via cron)
    hebbian.evolve()

    # CLI
    python3 hebbian_memory.py evolve      # Run full evolution cycle
    python3 hebbian_memory.py stats       # Show evolution statistics
    python3 hebbian_memory.py diagnose    # Diagnose memory health
"""

import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

_SCRIPTS_DIR = "/home/agent/.openclaw/workspace/scripts"

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/hebbian")
DATA_DIR.mkdir(parents=True, exist_ok=True)

ACCESS_LOG_FILE = DATA_DIR / "access_log.jsonl"
COACTIVATION_FILE = DATA_DIR / "coactivation.json"
EVOLUTION_HISTORY_FILE = DATA_DIR / "evolution_history.jsonl"
FISHER_FILE = DATA_DIR / "fisher_importance.json"
STATS_FILE = DATA_DIR / "stats.json"

# === CONSTANTS ===

# Reinforcement parameters
REINFORCEMENT_BASE = 0.02       # Base importance boost per access
REINFORCEMENT_DECAY = 0.7       # Diminishing returns exponent (< 1.0)
MAX_IMPORTANCE = 0.95           # Importance ceiling
MIN_IMPORTANCE = 0.05           # Importance floor (never fully forget)

# Hebbian association parameters
COACTIVATION_WINDOW_S = 300     # 5 minutes — memories recalled within this
                                # window of each other are "co-activated"
ASSOCIATION_BOOST = 0.15        # Graph edge weight boost for co-activation
ASSOCIATION_DECAY = 0.01        # Daily decay of association strength

# Power-law decay parameters
DECAY_EXPONENT = 0.5            # Power-law: importance *= (days)^(-exponent)
DECAY_GRACE_DAYS = 1            # No decay in the first day after access
DECAY_FLOOR_MULTIPLIER = 0.3   # Never decay below 30% of original importance

# Evolution thresholds
STRENGTHEN_THRESHOLD = 3        # Min accesses to be considered "strong"
WEAKEN_THRESHOLD_DAYS = 14      # Days without access before weakening starts

# EWC-inspired Fisher importance parameters (arXiv:2504.01241, Kirkpatrick 2017)
# Maps neural EWC to vector memory: Fisher_i ∝ freq × uniqueness × downstream_impact
FISHER_LAMBDA = 5.0             # Consolidation strength — how much Fisher shields decay
FISHER_FREQ_WEIGHT = 0.4       # Weight for retrieval frequency in Fisher score
FISHER_UNIQ_WEIGHT = 0.3       # Weight for semantic uniqueness (irreplaceability)
FISHER_IMPACT_WEIGHT = 0.3     # Weight for downstream task impact (confidence delta)
FISHER_RECOMPUTE_HOURS = 24    # Recompute Fisher scores at most once per day


class HebbianMemory:
    """Hebbian-style memory evolution engine with EWC-inspired forgetting prevention."""

    def __init__(self):
        self._coactivation = self._load_coactivation()
        self._fisher_scores = self._load_fisher()

    # === ACCESS TRACKING ===

    def on_recall(self, query, results, caller=None):
        """Called after brain.recall() — strengthens retrieved memories.

        Args:
            query: The recall query text
            results: List of recall result dicts (from brain.recall)
            caller: Who triggered the recall (for logging)
        """
        if not results:
            return

        now = datetime.now(timezone.utc)
        memory_ids = []

        for r in results:
            mem_id = r.get("id")
            if not mem_id:
                continue
            memory_ids.append(mem_id)

            # 1. Log the access event
            self._log_access(mem_id, query, r.get("collection", ""), caller, now)

            # 2. Strengthen this memory (retrieval = rehearsal)
            self._strengthen_memory(
                mem_id,
                r.get("collection", ""),
                r.get("metadata", {}),
                r.get("document", ""),
                now,
            )

        # 3. Hebbian association: co-accessed memories strengthen connections
        if len(memory_ids) >= 2:
            self._update_coactivation(memory_ids, now)

    def _log_access(self, mem_id, query, collection, caller, now):
        """Append access event to log (append-only for analysis)."""
        event = {
            "memory_id": mem_id,
            "query": query[:200] if query else "",
            "collection": collection,
            "caller": caller or "unknown",
            "timestamp": now.isoformat(),
        }
        with open(ACCESS_LOG_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")

    def _strengthen_memory(self, mem_id, collection, metadata, document, now):
        """Boost a memory's importance based on access count (diminishing returns).

        Uses log-scaled reinforcement: boost = base * (1 + count)^(-decay)
        This gives strong initial reinforcement that diminishes with repeated access,
        preventing any single memory from monopolizing importance.
        """
        try:
            from clarvis.brain import brain

            if collection not in brain.collections:
                return

            col = brain.collections[collection]

            # Get current metadata from ChromaDB
            try:
                existing = col.get(ids=[mem_id])
                if not existing or not existing["metadatas"] or not existing["metadatas"][0]:
                    return
                meta = existing["metadatas"][0]
                doc = existing["documents"][0] if existing.get("documents") else document
            except Exception:
                return

            # Update access tracking fields
            access_count = meta.get("access_count", 0)
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except ValueError:
                    access_count = 0

            access_count += 1

            # Compute reinforcement boost (diminishing returns)
            boost = REINFORCEMENT_BASE * (access_count ** (-REINFORCEMENT_DECAY))
            current_importance = meta.get("importance", 0.5)
            if isinstance(current_importance, str):
                try:
                    current_importance = float(current_importance)
                except ValueError:
                    current_importance = 0.5

            new_importance = min(MAX_IMPORTANCE, current_importance + boost)

            # Track access times for ACT-R activation scoring
            access_times = meta.get("access_times", [])
            if isinstance(access_times, str):
                try:
                    access_times = json.loads(access_times)
                except (json.JSONDecodeError, ValueError):
                    access_times = []
            access_times.append(now.timestamp())
            # Keep last 30 access times (sufficient for ACT-R activation)
            access_times = access_times[-30:]

            # Update metadata
            meta["access_count"] = access_count
            meta["last_accessed"] = now.isoformat()
            meta["importance"] = round(new_importance, 4)
            meta["hebbian_boost"] = round(boost, 6)
            meta["access_times"] = json.dumps(access_times)

            col.upsert(
                ids=[mem_id],
                documents=[doc],
                metadatas=[meta],
            )

        except Exception:
            pass  # Never let strengthening break the recall flow

    # === HEBBIAN CO-ACTIVATION ===

    def _load_coactivation(self):
        """Load co-activation matrix (sparse dict of dicts)."""
        if COACTIVATION_FILE.exists():
            try:
                with open(COACTIVATION_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_coactivation(self):
        """Save co-activation matrix."""
        with open(COACTIVATION_FILE, "w") as f:
            json.dump(self._coactivation, f)

    def _update_coactivation(self, memory_ids, now):
        """Update co-activation counts for memories retrieved together.

        "Cells that fire together wire together" — memories that are
        co-retrieved in the same recall() call form stronger associations.
        """
        for i, id_a in enumerate(memory_ids):
            for id_b in memory_ids[i + 1:]:
                # Order pair lexicographically for consistent keys
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

                # Hebbian strength: grows with co-activation, bounded
                entry["strength"] = min(
                    1.0,
                    entry["strength"] + ASSOCIATION_BOOST * (entry["count"] ** -0.5),
                )

        self._save_coactivation()

    # === EWC-INSPIRED FISHER IMPORTANCE ===
    # Adapted from Kirkpatrick et al. 2017 (arXiv:1612.00796)
    # Maps neural EWC to vector memory: Fisher_i = freq × uniqueness × impact
    # High Fisher score → memory resists decay (like high F_i protects weights)

    def _load_fisher(self):
        """Load cached Fisher importance scores."""
        if FISHER_FILE.exists():
            try:
                with open(FISHER_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"scores": {}, "computed_at": None}

    def _save_fisher(self):
        """Save Fisher importance scores."""
        with open(FISHER_FILE, "w") as f:
            json.dump(self._fisher_scores, f)

    def compute_fisher(self):
        """Compute Fisher-analog importance for all memories.

        EWC uses F_i = E[(∂L/∂θ_i)²] to identify critical parameters.
        Our analog for vector memory entries:
          F_m = w_freq * freq_score + w_uniq * uniqueness + w_impact * impact

        Where:
          - freq_score: retrieval frequency (how often this memory is accessed)
          - uniqueness: 1 - max_similarity_to_neighbors (irreplaceability)
          - impact: downstream confidence delta when this memory was retrieved

        Returns:
            Dict mapping memory_id → fisher_score (0.0 to 1.0)
        """
        from clarvis.brain import brain

        # Check if recomputation is needed
        last_computed = self._fisher_scores.get("computed_at")
        if last_computed:
            try:
                last_dt = datetime.fromisoformat(last_computed.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                if hours_since < FISHER_RECOMPUTE_HOURS:
                    return self._fisher_scores["scores"]
            except (ValueError, TypeError):
                pass

        # Compute access frequency from log
        access_counts = defaultdict(int)
        total_accesses = 0
        if ACCESS_LOG_FILE.exists():
            with open(ACCESS_LOG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        access_counts[event["memory_id"]] += 1
                        total_accesses += 1
                    except (json.JSONDecodeError, KeyError):
                        continue

        scores = {}
        for col_name, col in brain.collections.items():
            try:
                results = col.get()
            except Exception:
                continue

            ids = results.get("ids", [])
            metas = results.get("metadatas", [])

            for i, mem_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}

                # Component 1: Retrieval frequency (normalized)
                freq = access_counts.get(mem_id, 0)
                freq_score = min(1.0, freq / max(1, total_accesses) * len(ids))

                # Component 2: Uniqueness — approximated from coactivation patterns
                # Memories with many coactivation partners are less unique
                coact_count = 0
                for pair_key, entry in self._coactivation.items():
                    if mem_id in entry.get("ids", []):
                        coact_count += 1
                # Invert: many coactivation partners = less unique
                uniqueness = 1.0 / (1.0 + coact_count * 0.2)

                # Component 3: Downstream impact — proxy from importance trajectory
                # If importance has been boosted by accesses, it has downstream impact
                current_imp = meta.get("importance", 0.5)
                original_imp = meta.get("original_importance", current_imp)
                if isinstance(current_imp, str):
                    try:
                        current_imp = float(current_imp)
                    except ValueError:
                        current_imp = 0.5
                if isinstance(original_imp, str):
                    try:
                        original_imp = float(original_imp)
                    except ValueError:
                        original_imp = current_imp
                # Impact = how much importance grew from original (capped at 1.0)
                impact = min(1.0, max(0.0, (current_imp - original_imp * 0.5) / 0.5))

                # Combine: Fisher-analog score
                fisher = (
                    FISHER_FREQ_WEIGHT * freq_score
                    + FISHER_UNIQ_WEIGHT * uniqueness
                    + FISHER_IMPACT_WEIGHT * impact
                )
                scores[mem_id] = round(min(1.0, fisher), 4)

        self._fisher_scores = {
            "scores": scores,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_memories": len(scores),
            "total_accesses": total_accesses,
        }
        self._save_fisher()
        return scores

    def get_fisher_score(self, mem_id):
        """Get Fisher importance for a single memory (cached)."""
        return self._fisher_scores.get("scores", {}).get(mem_id, 0.0)

    # === EVOLUTION CYCLE ===

    def evolve(self, dry_run=False):
        """Run a full Hebbian evolution cycle.

        1. Strengthen frequently accessed memories (already done per-recall)
        2. Weaken neglected memories (power-law decay)
        3. Strengthen graph edges for co-activated pairs
        4. Decay stale co-activation associations
        5. Report statistics

        Args:
            dry_run: If True, compute changes but don't apply

        Returns:
            Dict with evolution statistics
        """
        from clarvis.brain import brain

        now = datetime.now(timezone.utc)
        stats = {
            "timestamp": now.isoformat(),
            "strengthened": 0,
            "weakened": 0,
            "fisher_protected": 0,
            "associations_strengthened": 0,
            "associations_decayed": 0,
            "total_memories_scanned": 0,
            "dry_run": dry_run,
        }

        # --- 0. Compute EWC Fisher importance (shields critical memories) ---
        fisher_scores = self.compute_fisher()

        # --- 1. Power-law decay with EWC protection of neglected memories ---
        for col_name, col in brain.collections.items():
            try:
                results = col.get()
            except Exception:
                continue

            ids = results.get("ids", [])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])

            for i, mem_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                doc = docs[i] if i < len(docs) else ""
                stats["total_memories_scanned"] += 1

                last_accessed = meta.get("last_accessed")
                if not last_accessed:
                    # Never accessed — set to created_at or now
                    last_accessed = meta.get("created_at", now.isoformat())

                try:
                    last_dt = datetime.fromisoformat(
                        last_accessed.replace("Z", "+00:00")
                    )
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                days_since = (now - last_dt).total_seconds() / 86400.0
                access_count = meta.get("access_count", 0)
                if isinstance(access_count, str):
                    try:
                        access_count = int(access_count)
                    except ValueError:
                        access_count = 0

                current_importance = meta.get("importance", 0.5)
                if isinstance(current_importance, str):
                    try:
                        current_importance = float(current_importance)
                    except ValueError:
                        current_importance = 0.5

                original_importance = meta.get("original_importance", current_importance)
                if isinstance(original_importance, str):
                    try:
                        original_importance = float(original_importance)
                    except ValueError:
                        original_importance = current_importance

                # Skip recently accessed memories
                if days_since <= DECAY_GRACE_DAYS:
                    continue

                # Skip memories with high access counts (they've earned persistence)
                if access_count >= STRENGTHEN_THRESHOLD:
                    # Still decay, but much more slowly
                    effective_days = days_since / (1 + math.log1p(access_count))
                else:
                    effective_days = days_since

                if effective_days <= DECAY_GRACE_DAYS:
                    continue

                # Ebbinghaus-ACT-R hybrid decay:
                # R = e^(-t/S) where S = memory_strength from access count
                # Blended with power-law: importance *= blend(R, t^(-d))
                memory_strength = 1.0 + math.log1p(access_count) * 2.0  # S grows with access
                ebbinghaus_R = math.exp(-effective_days / max(1.0, memory_strength))
                power_law_factor = effective_days ** (-DECAY_EXPONENT)
                # Blend: 60% Ebbinghaus (smooth curve) + 40% power-law (ACT-R style)
                decay_factor = 0.6 * ebbinghaus_R + 0.4 * power_law_factor
                decay_factor = max(0.5, min(1.0, decay_factor))  # Bounded decay per cycle

                # EWC protection: high Fisher importance shields from decay
                # Analogous to EWC penalty: L += (λ/2) * F_i * (θ_i - θ*_i)²
                # Here: effective_decay_rate /= (1 + λ * F_i)
                fisher_i = fisher_scores.get(mem_id, 0.0)
                if fisher_i > 0.1:  # Only apply protection to non-trivial Fisher
                    # Decay factor moves closer to 1.0 (less decay) with high Fisher
                    ewc_shield = 1.0 / (1.0 + FISHER_LAMBDA * fisher_i)
                    # Interpolate: decay_factor → 1.0 as Fisher increases
                    decay_factor = decay_factor + (1.0 - decay_factor) * (1.0 - ewc_shield)
                    if decay_factor > 0.99:
                        stats["fisher_protected"] += 1
                        continue  # Fully protected — skip decay

                new_importance = current_importance * decay_factor
                floor = max(MIN_IMPORTANCE, original_importance * DECAY_FLOOR_MULTIPLIER)
                new_importance = max(floor, new_importance)
                new_importance = round(new_importance, 4)

                if new_importance < current_importance - 0.001:
                    stats["weakened"] += 1
                    if not dry_run:
                        if "original_importance" not in meta:
                            meta["original_importance"] = current_importance
                        meta["importance"] = new_importance
                        meta["hebbian_decay_applied"] = now.isoformat()
                        col.upsert(ids=[mem_id], documents=[doc], metadatas=[meta])
                elif access_count >= STRENGTHEN_THRESHOLD and current_importance < 0.7:
                    # Frequently accessed but low importance — boost it
                    boost = REINFORCEMENT_BASE * math.log1p(access_count)
                    new_importance = min(MAX_IMPORTANCE, current_importance + boost)
                    new_importance = round(new_importance, 4)
                    if new_importance > current_importance + 0.001:
                        stats["strengthened"] += 1
                        if not dry_run:
                            meta["importance"] = new_importance
                            meta["hebbian_boost_applied"] = now.isoformat()
                            col.upsert(ids=[mem_id], documents=[doc], metadatas=[meta])

        # --- 2. Strengthen graph edges for co-activated pairs ---
        pairs_to_remove = []
        for pair_key, entry in self._coactivation.items():
            try:
                last_seen = datetime.fromisoformat(
                    entry["last_seen"].replace("Z", "+00:00")
                )
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError, KeyError):
                pairs_to_remove.append(pair_key)
                continue

            days_since_coactive = (now - last_seen).total_seconds() / 86400.0

            if entry["count"] >= 2 and entry["strength"] > 0.1:
                # Strengthen the graph edge between these memories
                ids = entry["ids"]
                if len(ids) == 2 and not dry_run:
                    try:
                        brain.add_relationship(
                            ids[0], ids[1], "hebbian_association",
                        )
                        stats["associations_strengthened"] += 1
                    except Exception:
                        pass

            # Decay association strength over time
            if days_since_coactive > 7:
                old_strength = entry["strength"]
                entry["strength"] = max(
                    0.0,
                    old_strength - ASSOCIATION_DECAY * days_since_coactive,
                )
                if entry["strength"] < 0.01:
                    pairs_to_remove.append(pair_key)
                else:
                    stats["associations_decayed"] += 1

        # Clean up dead associations
        for key in pairs_to_remove:
            self._coactivation.pop(key, None)
        if not dry_run:
            self._save_coactivation()

        # --- 3. Log evolution event ---
        if not dry_run:
            with open(EVOLUTION_HISTORY_FILE, "a") as f:
                f.write(json.dumps(stats) + "\n")

        # Save stats snapshot
        self._save_stats(stats)

        return stats

    # === DIAGNOSTICS ===

    def get_access_patterns(self, days=7):
        """Analyze access patterns from the log.

        Returns:
            Dict with access frequency analysis per memory.
        """
        if not ACCESS_LOG_FILE.exists():
            return {"total_events": 0, "memories": {}}

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        memory_counts = defaultdict(int)
        caller_counts = defaultdict(int)
        total = 0

        with open(ACCESS_LOG_FILE) as f:
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

        # Top accessed memories
        top_memories = sorted(
            memory_counts.items(), key=lambda x: x[1], reverse=True
        )[:20]

        return {
            "total_events": total,
            "unique_memories": len(memory_counts),
            "top_accessed": top_memories,
            "caller_breakdown": dict(caller_counts),
            "period_days": days,
        }

    def diagnose(self):
        """Diagnose memory health — find over/under-strengthened memories.

        Returns:
            Dict with diagnostic info.
        """
        from clarvis.brain import brain

        high_importance = []   # Memories that may be over-strengthened
        low_importance = []    # Memories at risk of being forgotten
        never_accessed = []    # Memories with access_count = 0
        heavily_accessed = []  # Memories with high access counts

        for col_name, col in brain.collections.items():
            try:
                results = col.get()
            except Exception:
                continue

            for i, mem_id in enumerate(results.get("ids", [])):
                meta = results["metadatas"][i] if i < len(results.get("metadatas", [])) else {}
                doc = results["documents"][i][:60] if i < len(results.get("documents", [])) else ""

                importance = meta.get("importance", 0.5)
                if isinstance(importance, str):
                    try:
                        importance = float(importance)
                    except ValueError:
                        importance = 0.5

                access_count = meta.get("access_count", 0)
                if isinstance(access_count, str):
                    try:
                        access_count = int(access_count)
                    except ValueError:
                        access_count = 0

                entry = {
                    "id": mem_id,
                    "collection": col_name,
                    "importance": round(importance, 3),
                    "access_count": access_count,
                    "preview": doc,
                }

                if importance > 0.85:
                    high_importance.append(entry)
                elif importance < 0.15:
                    low_importance.append(entry)

                if access_count == 0:
                    never_accessed.append(entry)
                elif access_count >= 10:
                    heavily_accessed.append(entry)

        # Co-activation stats
        total_pairs = len(self._coactivation)
        strong_pairs = sum(
            1 for e in self._coactivation.values() if e.get("strength", 0) > 0.3
        )

        return {
            "high_importance_count": len(high_importance),
            "low_importance_count": len(low_importance),
            "never_accessed_count": len(never_accessed),
            "heavily_accessed_count": len(heavily_accessed),
            "top_high_importance": sorted(
                high_importance, key=lambda x: x["importance"], reverse=True
            )[:5],
            "top_heavily_accessed": sorted(
                heavily_accessed, key=lambda x: x["access_count"], reverse=True
            )[:5],
            "coactivation_pairs": total_pairs,
            "strong_associations": strong_pairs,
        }

    def get_stats(self):
        """Get latest evolution stats."""
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_stats(self, stats):
        """Save stats snapshot."""
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)

    def get_evolution_history(self, n=10):
        """Get recent evolution history."""
        if not EVOLUTION_HISTORY_FILE.exists():
            return []
        entries = []
        with open(EVOLUTION_HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-n:]


# Singleton
hebbian = HebbianMemory()


# === CLI ===

def main():
    if len(sys.argv) < 2:
        print("Usage: hebbian_memory.py <evolve|stats|diagnose|access|history|fisher>")
        print()
        print("Commands:")
        print("  evolve     Run full Hebbian evolution cycle (strengthen + decay + EWC)")
        print("  evolve-dry Dry run — compute changes without applying")
        print("  stats      Show latest evolution stats")
        print("  diagnose   Diagnose memory health (over/under-strengthened)")
        print("  access     Show access pattern analysis (last 7 days)")
        print("  history    Show evolution history")
        print("  fisher     Compute and show EWC Fisher importance scores")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "evolve":
        print("Running Hebbian evolution cycle...")
        result = hebbian.evolve(dry_run=False)
        print("\n=== Hebbian Evolution Complete ===")
        print(f"  Memories scanned:          {result['total_memories_scanned']}")
        print(f"  Strengthened:              {result['strengthened']}")
        print(f"  Weakened (power-law decay): {result['weakened']}")
        print(f"  Fisher-protected (EWC):    {result['fisher_protected']}")
        print(f"  Associations strengthened: {result['associations_strengthened']}")
        print(f"  Associations decayed:      {result['associations_decayed']}")

    elif cmd == "evolve-dry":
        print("Dry-run Hebbian evolution cycle...")
        result = hebbian.evolve(dry_run=True)
        print("\n=== Hebbian Evolution (DRY RUN) ===")
        print(f"  Memories scanned:          {result['total_memories_scanned']}")
        print(f"  Would strengthen:          {result['strengthened']}")
        print(f"  Would weaken:              {result['weakened']}")
        print(f"  Fisher-protected (EWC):    {result['fisher_protected']}")
        print(f"  Would strengthen assoc:    {result['associations_strengthened']}")
        print(f"  Would decay assoc:         {result['associations_decayed']}")

    elif cmd == "stats":
        stats = hebbian.get_stats()
        if stats:
            print("=== Latest Hebbian Evolution Stats ===")
            print(json.dumps(stats, indent=2))
        else:
            print("No evolution stats yet. Run 'evolve' first.")

    elif cmd == "diagnose":
        print("Diagnosing memory health...")
        diag = hebbian.diagnose()
        print("\n=== Memory Health Diagnosis ===")
        print(f"  High importance (>0.85): {diag['high_importance_count']}")
        print(f"  Low importance (<0.15):  {diag['low_importance_count']}")
        print(f"  Never accessed:          {diag['never_accessed_count']}")
        print(f"  Heavily accessed (10+):  {diag['heavily_accessed_count']}")
        print(f"  Co-activation pairs:     {diag['coactivation_pairs']}")
        print(f"  Strong associations:     {diag['strong_associations']}")

        if diag["top_heavily_accessed"]:
            print("\n  Top accessed memories:")
            for m in diag["top_heavily_accessed"]:
                print(f"    [{m['collection']}] x{m['access_count']} imp={m['importance']} {m['preview']}")

        if diag["top_high_importance"]:
            print("\n  Highest importance memories:")
            for m in diag["top_high_importance"]:
                print(f"    [{m['collection']}] imp={m['importance']} x{m['access_count']} {m['preview']}")

    elif cmd == "access":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        patterns = hebbian.get_access_patterns(days=days)
        print(f"=== Access Patterns (last {days} days) ===")
        print(f"  Total access events: {patterns['total_events']}")
        print(f"  Unique memories:     {patterns['unique_memories']}")

        if patterns.get("caller_breakdown"):
            print("\n  By caller:")
            for caller, count in sorted(patterns["caller_breakdown"].items(),
                                         key=lambda x: x[1], reverse=True):
                print(f"    {caller}: {count}")

        if patterns.get("top_accessed"):
            print("\n  Top accessed memories:")
            for mem_id, count in patterns["top_accessed"][:10]:
                print(f"    x{count}  {mem_id}")

    elif cmd == "history":
        history = hebbian.get_evolution_history()
        if history:
            print("=== Hebbian Evolution History ===")
            for entry in history:
                ts = entry.get("timestamp", "?")[:19]
                print(f"  {ts}: +{entry.get('strengthened', 0)} strengthened, "
                      f"-{entry.get('weakened', 0)} weakened, "
                      f"~{entry.get('associations_strengthened', 0)} assoc")
        else:
            print("No evolution history yet. Run 'evolve' first.")

    elif cmd == "fisher":
        print("Computing EWC Fisher importance scores...")
        # Force recompute by clearing cache timestamp
        hebbian._fisher_scores["computed_at"] = None
        scores = hebbian.compute_fisher()
        print(f"\n=== EWC Fisher Importance (λ={FISHER_LAMBDA}) ===")
        print(f"  Total memories scored: {len(scores)}")
        if scores:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            high = sum(1 for _, s in sorted_scores if s > 0.5)
            med = sum(1 for _, s in sorted_scores if 0.1 < s <= 0.5)
            low = sum(1 for _, s in sorted_scores if s <= 0.1)
            print(f"  High Fisher (>0.5):    {high} (strongly protected)")
            print(f"  Medium (0.1-0.5):      {med} (partially protected)")
            print(f"  Low (<0.1):            {low} (unprotected, free to decay)")
            print("\n  Top 10 most protected memories:")
            for mem_id, score in sorted_scores[:10]:
                print(f"    F={score:.4f}  {mem_id[:60]}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

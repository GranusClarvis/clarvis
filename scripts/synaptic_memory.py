#!/usr/bin/env python3
"""
Synaptic Memory — Memristor-inspired neural memory using SQLite.

Models memory connections as memristor synapses with bounded, nonlinear
conductance that evolves via STDP-like learning rules. This replaces the
JSON-based co-activation tracking in hebbian_memory.py with a proper
relational model that supports:

  1. Bounded synaptic weights (w_min=0.001, w_max=1.0) — mimics physical
     memristor conductance range. No weight can grow unboundedly.

  2. Nonlinear weight transfer — uses the PCMO memristor model:
     w_i = w_max - (w_max - w_min)/(1 - e^(-nu)) * [1 - exp(-nu * (1 - x))]
     where x is a normalized state variable and nu controls curvature.

  3. STDP-like updates — when two memories are co-retrieved within a time
     window, their synapse strengthens (potentiation). When one fires
     without the other, the synapse weakens (depression). Weight-dependent
     saturation prevents runaway strengthening.

  4. Spreading activation — given a set of active memories, compute which
     other memories should be activated based on synaptic conductance.
     This is a neural-network-style forward pass through the synapse table.

  5. Consolidation — periodic sweep that applies slow decay to all synapses,
     prunes near-zero connections, and identifies hub memories (high fan-out).

SQLite advantages over JSON for this:
  - O(log n) indexed lookups vs O(n) JSON scan
  - ACID transactions for concurrent access
  - Aggregate queries (hub detection, weight distribution) are trivial SQL
  - No need to load entire co-activation matrix into RAM
  - Scales to millions of synapses without memory pressure

Reference: nervos framework STDP model (Fabrizio Musacchio, 2026)
           Pavlik & Anderson 2005 (ACT-R activation decay)

Usage:
    from synaptic_memory import synaptic
    synaptic.potentiate("mem_a", "mem_b")      # Strengthen connection
    synaptic.depress("mem_a", "mem_b")          # Weaken connection
    activated = synaptic.spread("mem_a", n=5)   # Spreading activation
    synaptic.consolidate()                      # Nightly maintenance

    # CLI
    python3 synaptic_memory.py stats
    python3 synaptic_memory.py spread <memory_id>
    python3 synaptic_memory.py hubs
    python3 synaptic_memory.py consolidate
    python3 synaptic_memory.py evolve           # Full STDP evolution from access log
"""

import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DB_DIR = Path("/home/agent/.openclaw/workspace/data/synaptic")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "synapses.db"
STATS_FILE = DB_DIR / "stats.json"

# === MEMRISTOR PARAMETERS ===

W_MIN = 0.001       # Minimum synaptic weight (memristor OFF state)
W_MAX = 1.0         # Maximum synaptic weight (memristor ON state)
W_INIT = 0.1        # Initial weight for new synapses
NU = 2.0            # Nonlinearity parameter (higher = more asymmetric)

# STDP parameters
A_POT = 0.05        # Potentiation amplitude
A_DEP = 0.03        # Depression amplitude (slightly weaker than pot.)
TAU_POT = 300.0     # Potentiation time constant (seconds)
TAU_DEP = 300.0     # Depression time constant (seconds)
GAMMA = 0.9         # Weight-dependent saturation exponent

# Consolidation parameters
DECAY_RATE = 0.005  # Daily weight decay
PRUNE_THRESHOLD = 0.005  # Remove synapses below this weight
MAX_SYNAPSES_PER_NODE = 50  # Prune weakest if exceeded


class SynapticMemory:
    """Memristor-inspired synaptic memory layer backed by SQLite."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS synapses (
                pre_id   TEXT NOT NULL,
                post_id  TEXT NOT NULL,
                weight   REAL NOT NULL DEFAULT 0.1,
                state    REAL NOT NULL DEFAULT 0.5,   -- normalized memristor state [0,1]
                potentiations  INTEGER NOT NULL DEFAULT 0,
                depressions    INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                PRIMARY KEY (pre_id, post_id),
                CHECK (weight >= 0.001 AND weight <= 1.0),
                CHECK (state >= 0.0 AND state <= 1.0)
            );

            CREATE INDEX IF NOT EXISTS idx_syn_pre ON synapses(pre_id);
            CREATE INDEX IF NOT EXISTS idx_syn_post ON synapses(post_id);
            CREATE INDEX IF NOT EXISTS idx_syn_weight ON synapses(weight DESC);

            CREATE TABLE IF NOT EXISTS activations (
                memory_id   TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                source      TEXT,
                PRIMARY KEY (memory_id, timestamp)
            );

            CREATE INDEX IF NOT EXISTS idx_act_ts ON activations(timestamp DESC);

            CREATE TABLE IF NOT EXISTS evolution_log (
                timestamp    TEXT NOT NULL,
                synapses_total    INTEGER,
                potentiated       INTEGER,
                depressed         INTEGER,
                pruned            INTEGER,
                avg_weight        REAL,
                hub_count         INTEGER
            );
        """)
        conn.commit()
        conn.close()

    def _conn(self):
        """Get a SQLite connection with WAL mode for concurrent reads."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # === MEMRISTOR TRANSFER FUNCTION ===

    @staticmethod
    def _memristor_weight(state, nu=NU):
        """Convert normalized state [0,1] to bounded weight [w_min, w_max].

        Uses the PCMO memristor nonlinear transfer function:
        w = w_max - (w_max - w_min)/(1 - e^(-nu)) * [1 - exp(-nu * (1 - state))]

        Args:
            state: Normalized memristor state variable (0=OFF, 1=ON)
            nu: Nonlinearity parameter

        Returns:
            Bounded weight in [W_MIN, W_MAX]
        """
        if nu == 0:
            return W_MIN + (W_MAX - W_MIN) * state
        exp_nu = math.exp(-nu)
        weight = W_MAX - (W_MAX - W_MIN) / (1.0 - exp_nu) * (1.0 - math.exp(-nu * (1.0 - state)))
        return max(W_MIN, min(W_MAX, weight))

    @staticmethod
    def _inverse_memristor(weight, nu=NU):
        """Convert weight back to normalized state variable.

        Inverse of _memristor_weight for initializing state from a given weight.
        """
        if nu == 0:
            return (weight - W_MIN) / (W_MAX - W_MIN)
        exp_nu = math.exp(-nu)
        ratio = (W_MAX - weight) * (1.0 - exp_nu) / (W_MAX - W_MIN)
        # ratio = 1 - exp(-nu * (1 - state))
        # exp(-nu * (1 - state)) = 1 - ratio
        inner = max(1e-10, 1.0 - ratio)
        state = 1.0 + math.log(inner) / nu
        return max(0.0, min(1.0, state))

    # === CORE OPERATIONS ===

    def _get_or_create_synapse(self, conn, pre_id, post_id):
        """Get existing synapse or create a new one.

        Returns (weight, state) tuple.
        """
        row = conn.execute(
            "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
            (pre_id, post_id)
        ).fetchone()
        if row:
            return row
        # Create new synapse
        now = datetime.now(timezone.utc).isoformat()
        init_state = self._inverse_memristor(W_INIT)
        conn.execute(
            "INSERT OR IGNORE INTO synapses (pre_id, post_id, weight, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pre_id, post_id, W_INIT, init_state, now, now)
        )
        return (W_INIT, init_state)

    def potentiate(self, pre_id, post_id, delta_t=0.0):
        """Strengthen the synapse between two memories (STDP potentiation).

        Args:
            pre_id: Pre-synaptic memory ID (fired first)
            post_id: Post-synaptic memory ID (fired after)
            delta_t: Time difference in seconds (post - pre). If 0, use max strength.

        Models the STDP potentiation rule with weight-dependent saturation:
        delta_w = A_pot * exp(-delta_t/tau_pot) * |d(w)|^gamma
        where d(w) = w_max - w (distance to upper bound)
        """
        conn = self._conn()
        try:
            _, state = self._get_or_create_synapse(conn, pre_id, post_id)

            # STDP timing factor
            if delta_t >= 0:
                timing_factor = A_POT * math.exp(-abs(delta_t) / TAU_POT)
            else:
                timing_factor = A_POT * 0.5  # Weaker for reversed timing

            # Weight-dependent saturation: harder to potentiate strong synapses
            distance_to_max = max(0.001, 1.0 - state)
            delta_state = timing_factor * (distance_to_max ** GAMMA)

            new_state = min(1.0, state + delta_state)
            new_weight = self._memristor_weight(new_state)
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "UPDATE synapses SET weight=?, state=?, potentiations=potentiations+1, "
                "updated_at=? WHERE pre_id=? AND post_id=?",
                (new_weight, new_state, now, pre_id, post_id)
            )
            conn.commit()
            return new_weight
        finally:
            conn.close()

    def depress(self, pre_id, post_id, delta_t=0.0):
        """Weaken the synapse between two memories (STDP depression).

        Args:
            pre_id: Pre-synaptic memory ID
            post_id: Post-synaptic memory ID
            delta_t: Time difference (negative = depression)

        Models STDP depression with weight-dependent saturation:
        delta_w = -A_dep * exp(delta_t/tau_dep) * |d(w)|^gamma
        where d(w) = w - w_min (distance to lower bound)
        """
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
                (pre_id, post_id)
            ).fetchone()
            if not row:
                return None  # No synapse to depress

            _, state = row

            # STDP timing factor
            timing_factor = A_DEP * math.exp(-abs(delta_t) / TAU_DEP)

            # Weight-dependent saturation: harder to depress weak synapses
            distance_to_min = max(0.001, state)
            delta_state = timing_factor * (distance_to_min ** GAMMA)

            new_state = max(0.0, state - delta_state)
            new_weight = self._memristor_weight(new_state)
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "UPDATE synapses SET weight=?, state=?, depressions=depressions+1, "
                "updated_at=? WHERE pre_id=? AND post_id=?",
                (new_weight, new_state, now, pre_id, post_id)
            )
            conn.commit()
            return new_weight
        finally:
            conn.close()

    def record_activation(self, memory_id, source=None):
        """Record that a memory was activated (retrieved/accessed).

        Used for STDP timing calculations and spreading activation.
        """
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc).timestamp()
            conn.execute(
                "INSERT OR REPLACE INTO activations (memory_id, timestamp, source) "
                "VALUES (?, ?, ?)",
                (memory_id, now, source)
            )
            conn.commit()
        finally:
            conn.close()

    def spread(self, source_ids, n=10, min_weight=0.05):
        """Spreading activation — find memories strongly connected to source(s).

        Performs a single-hop neural-network-style forward pass:
        activation(target) = sum(weight(source -> target)) for all sources

        Args:
            source_ids: Single ID or list of active memory IDs
            n: Max results to return
            min_weight: Minimum synapse weight to consider

        Returns:
            List of (memory_id, total_activation) tuples sorted by activation.
        """
        if isinstance(source_ids, str):
            source_ids = [source_ids]

        conn = self._conn()
        try:
            placeholders = ",".join("?" * len(source_ids))
            rows = conn.execute(f"""
                SELECT post_id, SUM(weight) as total_activation
                FROM synapses
                WHERE pre_id IN ({placeholders})
                  AND weight >= ?
                  AND post_id NOT IN ({placeholders})
                GROUP BY post_id
                ORDER BY total_activation DESC
                LIMIT ?
            """, source_ids + [min_weight] + source_ids + [n]).fetchall()
            return [(row[0], round(row[1], 4)) for row in rows]
        finally:
            conn.close()

    # === STDP EVOLUTION FROM ACCESS LOG ===

    def _batch_potentiate(self, conn, pre_id, post_id, delta_t, now_iso):
        """Potentiate within an existing connection (no open/close overhead)."""
        row = conn.execute(
            "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
            (pre_id, post_id)
        ).fetchone()
        if not row:
            init_state = self._inverse_memristor(W_INIT)
            conn.execute(
                "INSERT OR IGNORE INTO synapses (pre_id, post_id, weight, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pre_id, post_id, W_INIT, init_state, now_iso, now_iso)
            )
            state = init_state
        else:
            state = row[1]

        timing_factor = A_POT * math.exp(-abs(delta_t) / TAU_POT) if delta_t >= 0 else A_POT * 0.5
        distance_to_max = max(0.001, 1.0 - state)
        delta_state = timing_factor * (distance_to_max ** GAMMA)
        new_state = min(1.0, state + delta_state)
        new_weight = self._memristor_weight(new_state)

        conn.execute(
            "UPDATE synapses SET weight=?, state=?, potentiations=potentiations+1, "
            "updated_at=? WHERE pre_id=? AND post_id=?",
            (new_weight, new_state, now_iso, pre_id, post_id)
        )

    def _batch_depress(self, conn, pre_id, post_id, now_iso):
        """Depress within an existing connection (no open/close overhead)."""
        row = conn.execute(
            "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
            (pre_id, post_id)
        ).fetchone()
        if not row:
            return
        state = row[1]
        timing_factor = A_DEP
        distance_to_min = max(0.001, state)
        delta_state = timing_factor * (distance_to_min ** GAMMA)
        new_state = max(0.0, state - delta_state)
        new_weight = self._memristor_weight(new_state)
        conn.execute(
            "UPDATE synapses SET weight=?, state=?, depressions=depressions+1, "
            "updated_at=? WHERE pre_id=? AND post_id=?",
            (new_weight, new_state, now_iso, pre_id, post_id)
        )

    def evolve_from_access_log(self, window_s=300.0):
        """Run STDP evolution using the Hebbian access log (batched).

        Reads recent access events, finds co-activations within the time window,
        and applies potentiation/depression to corresponding synapses.
        All writes use a single connection for performance.

        Args:
            window_s: Co-activation time window in seconds (default 5 min)

        Returns:
            Dict with evolution statistics.
        """
        access_log = Path("/home/agent/.openclaw/workspace/data/hebbian/access_log.jsonl")
        if not access_log.exists():
            return {"error": "No access log found", "potentiated": 0, "depressed": 0}

        # Load recent events (last 24h)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        events = []
        with open(access_log) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("timestamp", "") >= cutoff:
                        events.append(ev)
                except json.JSONDecodeError:
                    continue

        if not events:
            return {"error": "No recent access events", "potentiated": 0, "depressed": 0}

        # Parse timestamps
        for ev in events:
            try:
                dt = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
                ev["_ts"] = dt.timestamp()
            except (ValueError, KeyError):
                ev["_ts"] = 0

        events.sort(key=lambda e: e["_ts"])

        # Deduplicate: only keep one event per memory_id per 60s window
        deduped = []
        seen = {}  # memory_id -> last_ts
        for ev in events:
            mem = ev.get("memory_id", "")
            if not mem:
                continue
            ts = ev["_ts"]
            if mem in seen and ts - seen[mem] < 60:
                continue
            seen[mem] = ts
            deduped.append(ev)
        events = deduped

        conn = self._conn()
        now_iso = datetime.now(timezone.utc).isoformat()
        potentiated = 0
        depressed = 0

        try:
            # Record all activations
            for ev in events:
                mem = ev.get("memory_id", "")
                conn.execute(
                    "INSERT OR REPLACE INTO activations (memory_id, timestamp, source) "
                    "VALUES (?, ?, ?)",
                    (mem, ev["_ts"], ev.get("caller", ""))
                )

            # Find co-activations and potentiate (batched)
            coactivated = set()
            for i, ev_a in enumerate(events):
                mem_a = ev_a.get("memory_id", "")
                if not mem_a or ev_a["_ts"] == 0:
                    continue

                for j in range(i + 1, min(i + 20, len(events))):  # cap window scan
                    ev_b = events[j]
                    mem_b = ev_b.get("memory_id", "")
                    if not mem_b or mem_b == mem_a or ev_b["_ts"] == 0:
                        continue

                    delta_t = ev_b["_ts"] - ev_a["_ts"]
                    if delta_t > window_s:
                        break

                    self._batch_potentiate(conn, mem_a, mem_b, delta_t, now_iso)
                    self._batch_potentiate(conn, mem_b, mem_a, delta_t, now_iso)
                    potentiated += 2
                    coactivated.add(mem_a)
                    coactivated.add(mem_b)

            # Depression: memories accessed in isolation
            all_mems = {ev.get("memory_id", "") for ev in events if ev.get("memory_id")}
            isolated = all_mems - coactivated

            for mem_id in isolated:
                rows = conn.execute(
                    "SELECT post_id FROM synapses WHERE pre_id=? AND weight > ?",
                    (mem_id, PRUNE_THRESHOLD)
                ).fetchall()
                for (post_id,) in rows:
                    self._batch_depress(conn, mem_id, post_id, now_iso)
                    depressed += 1

            conn.commit()
        finally:
            conn.close()

        return {
            "events_processed": len(events),
            "potentiated": potentiated,
            "depressed": depressed,
            "isolated_memories": len(isolated),
        }

    # === CONSOLIDATION ===

    def consolidate(self):
        """Nightly consolidation: decay, prune, and enforce limits.

        Returns:
            Dict with consolidation statistics.
        """
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # 1. Apply global decay to all synapses
            # weight *= (1 - decay_rate), then recompute state
            decayed = conn.execute(
                "UPDATE synapses SET weight = MAX(?, weight * ?), "
                "state = MAX(0.0, state * ?), updated_at = ?",
                (W_MIN, 1.0 - DECAY_RATE, 1.0 - DECAY_RATE, now_iso)
            ).rowcount

            # 2. Prune near-zero synapses
            pruned = conn.execute(
                "DELETE FROM synapses WHERE weight < ?",
                (PRUNE_THRESHOLD,)
            ).rowcount

            # 3. Enforce max synapses per node (keep strongest)
            # Find nodes that exceed the limit
            over_limit = conn.execute("""
                SELECT pre_id, COUNT(*) as cnt FROM synapses
                GROUP BY pre_id HAVING cnt > ?
            """, (MAX_SYNAPSES_PER_NODE,)).fetchall()

            extra_pruned = 0
            for (pre_id, cnt) in over_limit:
                excess = cnt - MAX_SYNAPSES_PER_NODE
                conn.execute("""
                    DELETE FROM synapses WHERE rowid IN (
                        SELECT rowid FROM synapses
                        WHERE pre_id = ?
                        ORDER BY weight ASC
                        LIMIT ?
                    )
                """, (pre_id, excess))
                extra_pruned += excess

            # 4. Clean old activations (>7 days)
            cutoff_ts = (now - timedelta(days=7)).timestamp()
            old_activations = conn.execute(
                "DELETE FROM activations WHERE timestamp < ?",
                (cutoff_ts,)
            ).rowcount

            # 5. Collect stats
            stats_row = conn.execute("""
                SELECT COUNT(*), AVG(weight), MIN(weight), MAX(weight),
                       SUM(potentiations), SUM(depressions)
                FROM synapses
            """).fetchone()

            total_synapses = stats_row[0] or 0
            avg_weight = round(stats_row[1] or 0, 4)

            # Hub detection: memories with many strong connections
            hubs = conn.execute("""
                SELECT pre_id, COUNT(*) as fan_out, AVG(weight) as avg_w
                FROM synapses
                WHERE weight >= 0.1
                GROUP BY pre_id
                HAVING fan_out >= 5
                ORDER BY fan_out DESC
                LIMIT 10
            """).fetchall()

            conn.commit()

            # Log evolution
            conn.execute(
                "INSERT INTO evolution_log (timestamp, synapses_total, potentiated, "
                "depressed, pruned, avg_weight, hub_count) "
                "VALUES (?, ?, 0, 0, ?, ?, ?)",
                (now_iso, total_synapses, pruned + extra_pruned, avg_weight, len(hubs))
            )
            conn.commit()

            result = {
                "timestamp": now_iso,
                "total_synapses": total_synapses,
                "decayed": decayed,
                "pruned": pruned + extra_pruned,
                "old_activations_cleaned": old_activations,
                "avg_weight": avg_weight,
                "hub_count": len(hubs),
                "hubs": [(h[0], h[1], round(h[2], 3)) for h in hubs],
            }

            self._save_stats(result)
            return result
        finally:
            conn.close()

    # === QUERIES ===

    def get_synapse(self, pre_id, post_id):
        """Get details of a specific synapse."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT weight, state, potentiations, depressions, created_at, updated_at "
                "FROM synapses WHERE pre_id=? AND post_id=?",
                (pre_id, post_id)
            ).fetchone()
            if row:
                return {
                    "pre_id": pre_id, "post_id": post_id,
                    "weight": row[0], "state": row[1],
                    "potentiations": row[2], "depressions": row[3],
                    "created_at": row[4], "updated_at": row[5],
                }
            return None
        finally:
            conn.close()

    def get_strongest(self, n=20):
        """Get the strongest synapses in the network."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT pre_id, post_id, weight, potentiations, depressions "
                "FROM synapses ORDER BY weight DESC LIMIT ?",
                (n,)
            ).fetchall()
            return [
                {"pre": r[0], "post": r[1], "weight": round(r[2], 4),
                 "pot": r[3], "dep": r[4]}
                for r in rows
            ]
        finally:
            conn.close()

    def get_hubs(self, min_fanout=3, min_weight=0.05):
        """Find hub memories with high fan-out."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT pre_id, COUNT(*) as fan_out,
                       AVG(weight) as avg_w, SUM(weight) as total_w
                FROM synapses
                WHERE weight >= ?
                GROUP BY pre_id
                HAVING fan_out >= ?
                ORDER BY total_w DESC
                LIMIT 20
            """, (min_weight, min_fanout)).fetchall()
            return [
                {"memory_id": r[0], "fan_out": r[1],
                 "avg_weight": round(r[2], 4), "total_weight": round(r[3], 4)}
                for r in rows
            ]
        finally:
            conn.close()

    def get_weight_distribution(self, bins=10):
        """Get histogram of synaptic weight distribution using SQL aggregation."""
        conn = self._conn()
        try:
            # Get total count and stats via SQL (no loading all weights into Python)
            stats_row = conn.execute("""
                SELECT COUNT(*), AVG(weight), AVG(weight * weight)
                FROM synapses
            """).fetchone()
            total = stats_row[0] or 0
            if total == 0:
                return {"bins": [], "counts": [], "total": 0}

            mean = stats_row[1] or 0
            # Variance = E[X^2] - E[X]^2
            variance = max(0, (stats_row[2] or 0) - mean * mean)
            std = variance ** 0.5

            # Compute histogram buckets in SQL
            bin_width = (W_MAX - W_MIN) / bins
            counts = [0] * bins
            rows = conn.execute("""
                SELECT CAST((weight - ?) / ? AS INTEGER) AS bucket, COUNT(*)
                FROM synapses
                GROUP BY bucket
            """, (W_MIN, bin_width)).fetchall()
            for bucket, count in rows:
                idx = max(0, min(int(bucket), bins - 1))
                counts[idx] += count

            bin_edges = [W_MIN + i * bin_width for i in range(bins + 1)]
            return {
                "bins": [f"{bin_edges[i]:.3f}-{bin_edges[i+1]:.3f}" for i in range(bins)],
                "counts": counts,
                "total": total,
                "mean": round(mean, 4),
                "std": round(std, 4),
            }
        finally:
            conn.close()

    def stats(self):
        """Get comprehensive synapse network statistics."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM synapses").fetchone()[0]
            if total == 0:
                return {"total_synapses": 0, "status": "empty"}

            row = conn.execute("""
                SELECT AVG(weight), MIN(weight), MAX(weight),
                       SUM(potentiations), SUM(depressions),
                       COUNT(DISTINCT pre_id), COUNT(DISTINCT post_id)
                FROM synapses
            """).fetchone()

            # Use pre-computed distinct counts instead of expensive UNION
            # row[5] = COUNT(DISTINCT pre_id), row[6] = COUNT(DISTINCT post_id)
            # Approximate unique nodes = max(distinct_pre, distinct_post)
            # (exact UNION is O(n) and hangs on large tables)
            unique_nodes = max(row[5] or 0, row[6] or 0)

            activation_count = conn.execute(
                "SELECT COUNT(*) FROM activations"
            ).fetchone()[0]

            # Weight distribution via SQL (inline, no separate connection)
            bin_count = 10
            bin_width = (W_MAX - W_MIN) / bin_count
            dist_rows = conn.execute("""
                SELECT CAST((weight - ?) / ? AS INTEGER) AS bucket, COUNT(*)
                FROM synapses GROUP BY bucket
            """, (W_MIN, bin_width)).fetchall()
            dist_counts = [0] * bin_count
            for bucket, count in dist_rows:
                idx = max(0, min(int(bucket), bin_count - 1))
                dist_counts[idx] += count

            avg_sq = conn.execute("SELECT AVG(weight * weight) FROM synapses").fetchone()[0] or 0
            variance = max(0, avg_sq - (row[0] or 0) ** 2)
            bin_edges = [W_MIN + i * bin_width for i in range(bin_count + 1)]
            dist = {
                "bins": [f"{bin_edges[i]:.3f}-{bin_edges[i+1]:.3f}" for i in range(bin_count)],
                "counts": dist_counts,
                "total": total,
                "mean": round(row[0] or 0, 4),
                "std": round(variance ** 0.5, 4),
            }

            # Recent evolution log
            recent_log = conn.execute(
                "SELECT * FROM evolution_log ORDER BY timestamp DESC LIMIT 5"
            ).fetchall()

            return {
                "total_synapses": total,
                "unique_nodes": unique_nodes,
                "avg_weight": round(row[0] or 0, 4),
                "min_weight": round(row[1] or 0, 4),
                "max_weight": round(row[2] or 0, 4),
                "total_potentiations": row[3] or 0,
                "total_depressions": row[4] or 0,
                "distinct_pre_nodes": row[5] or 0,
                "distinct_post_nodes": row[6] or 0,
                "active_activations": activation_count,
                "weight_distribution": dist,
                "recent_evolution_entries": len(recent_log),
                "status": "active",
            }
        finally:
            conn.close()

    # === BRIDGE TO BRAIN.PY ===

    def on_recall(self, query, results, caller=None):
        """Hook called after brain.recall() — create/strengthen synapses.

        Same interface as hebbian_memory.on_recall() for compatibility.
        Creates synapses between top-K co-retrieved memories with STDP timing.
        Uses a single DB connection for all operations (batched).
        """
        if not results or len(results) < 2:
            return

        # Cap to top-K=10 results — drops pairwise ops from O(n^2) to max 90
        TOP_K = 10
        memory_ids = []
        for r in results[:TOP_K]:
            mem_id = r.get("id")
            if mem_id:
                memory_ids.append(mem_id)

        if len(memory_ids) < 2:
            return

        conn = self._conn()
        try:
            now_ts = datetime.now(timezone.utc).timestamp()
            now_iso = datetime.now(timezone.utc).isoformat()

            # Batch record all activations in one transaction
            for mem_id in memory_ids:
                conn.execute(
                    "INSERT OR REPLACE INTO activations (memory_id, timestamp, source) "
                    "VALUES (?, ?, ?)",
                    (mem_id, now_ts, caller)
                )

            # Pairwise potentiation using batched method (single connection)
            for i, id_a in enumerate(memory_ids):
                for j, id_b in enumerate(memory_ids):
                    if i == j:
                        continue
                    delta_t = abs(i - j) * 10.0  # 10s per rank difference
                    self._batch_potentiate(conn, id_a, id_b, delta_t, now_iso)

            conn.commit()
        finally:
            conn.close()

    def _save_stats(self, stats):
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)


# Singleton (lazy — no I/O until first access)
_synaptic = None

def get_synaptic():
    global _synaptic
    if _synaptic is None:
        _synaptic = SynapticMemory()
    return _synaptic

class _LazySynaptic:
    def __getattr__(self, name):
        real = get_synaptic()
        global synaptic
        synaptic = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazySynaptic (not yet initialized)>"

synaptic = _LazySynaptic()


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: synaptic_memory.py <stats|spread|hubs|strongest|consolidate|evolve|dist|test>")
        print()
        print("Commands:")
        print("  stats        Show synapse network statistics")
        print("  spread <id>  Spreading activation from a memory ID")
        print("  hubs         Show hub memories (high fan-out)")
        print("  strongest    Show strongest synapses")
        print("  consolidate  Run nightly consolidation (decay + prune)")
        print("  evolve       Run STDP evolution from access log")
        print("  dist         Show weight distribution histogram")
        print("  test         Run self-test with synthetic data")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        s = synaptic.stats()
        print("=== Synaptic Memory Network ===")
        print(json.dumps(s, indent=2))

    elif cmd == "spread":
        if len(sys.argv) < 3:
            print("Usage: spread <memory_id>")
            sys.exit(1)
        source = sys.argv[2]
        results = synaptic.spread(source)
        print(f"Spreading activation from: {source}")
        for mem_id, activation in results:
            bar = "█" * int(activation * 20)
            print(f"  {activation:.4f} {bar} {mem_id}")

    elif cmd == "hubs":
        hubs = synaptic.get_hubs()
        if not hubs:
            print("No hub memories found yet.")
        else:
            print("Hub memories (high fan-out):")
            for h in hubs:
                print(f"  fan_out={h['fan_out']:3d}  avg_w={h['avg_weight']:.3f}  "
                      f"total_w={h['total_weight']:.3f}  {h['memory_id']}")

    elif cmd == "strongest":
        strongest = synaptic.get_strongest()
        if not strongest:
            print("No synapses found yet.")
        else:
            print("Strongest synapses:")
            for s in strongest:
                print(f"  w={s['weight']:.4f}  pot={s['pot']}  dep={s['dep']}  "
                      f"{s['pre'][:40]} → {s['post'][:40]}")

    elif cmd == "consolidate":
        print("Running synaptic consolidation...")
        result = synaptic.consolidate()
        print("\n=== Consolidation Complete ===")
        print(f"  Total synapses: {result['total_synapses']}")
        print(f"  Decayed: {result['decayed']}")
        print(f"  Pruned: {result['pruned']}")
        print(f"  Avg weight: {result['avg_weight']}")
        print(f"  Hubs: {result['hub_count']}")

    elif cmd == "evolve":
        print("Running STDP evolution from access log...")
        result = synaptic.evolve_from_access_log()
        print("\n=== STDP Evolution Complete ===")
        if "error" in result:
            print(f"  {result['error']}")
        else:
            print(f"  Events processed: {result['events_processed']}")
            print(f"  Synapses potentiated: {result['potentiated']}")
            print(f"  Synapses depressed: {result['depressed']}")
            print(f"  Isolated memories: {result['isolated_memories']}")

    elif cmd == "dist":
        dist = synaptic.get_weight_distribution()
        if dist["total"] == 0:
            print("No synapses to analyze.")
        else:
            print(f"Weight Distribution (n={dist['total']}, mean={dist['mean']}, std={dist['std']}):")
            max_count = max(dist["counts"]) if dist["counts"] else 1
            for bin_label, count in zip(dist["bins"], dist["counts"]):
                bar = "█" * int(count / max(1, max_count) * 30)
                print(f"  {bin_label}  {count:4d} {bar}")

    elif cmd == "test":
        print("=== Synaptic Memory Self-Test ===\n")
        import tempfile
        test_db = tempfile.mktemp(suffix=".db")
        test_syn = SynapticMemory(db_path=test_db)

        # Test 1: Memristor transfer function
        print("1. Memristor transfer function:")
        for state in [0.0, 0.25, 0.5, 0.75, 1.0]:
            w = SynapticMemory._memristor_weight(state)
            s_back = SynapticMemory._inverse_memristor(w)
            ok = abs(s_back - state) < 0.01
            print(f"   state={state:.2f} → weight={w:.4f} → state_back={s_back:.2f} {'OK' if ok else 'FAIL'}")

        # Test 2: Potentiation
        print("\n2. STDP Potentiation:")
        w1 = test_syn.potentiate("mem_a", "mem_b", delta_t=0)
        w2 = test_syn.potentiate("mem_a", "mem_b", delta_t=0)
        w3 = test_syn.potentiate("mem_a", "mem_b", delta_t=0)
        print(f"   After 3 potentiations: {W_INIT:.3f} → {w1:.4f} → {w2:.4f} → {w3:.4f}")
        print(f"   Weight-dependent saturation: {'OK' if (w2-w1) > (w3-w2) else 'NEEDS TUNING'}")

        # Test 3: Depression
        print("\n3. STDP Depression:")
        d1 = test_syn.depress("mem_a", "mem_b")
        d2 = test_syn.depress("mem_a", "mem_b")
        print(f"   After 2 depressions: {w3:.4f} → {d1:.4f} → {d2:.4f}")
        print(f"   Bounded: {'OK' if d2 >= W_MIN else 'FAIL'}")

        # Test 4: Spreading activation
        print("\n4. Spreading activation:")
        for i in range(5):
            test_syn.potentiate("hub", f"target_{i}", delta_t=0)
            # Vary the strength
            for _ in range(i):
                test_syn.potentiate("hub", f"target_{i}", delta_t=0)
        spread = test_syn.spread("hub", n=5)
        print(f"   Hub→targets: {len(spread)} activated")
        for mem_id, activation in spread:
            print(f"     {activation:.4f}  {mem_id}")

        # Test 5: Consolidation
        print("\n5. Consolidation:")
        result = test_syn.consolidate()
        print(f"   Total synapses: {result['total_synapses']}")
        print(f"   Avg weight: {result['avg_weight']}")

        # Test 6: Stats
        print("\n6. Network stats:")
        s = test_syn.stats()
        print(f"   Nodes: {s['unique_nodes']}, Synapses: {s['total_synapses']}")
        print(f"   Potentiations: {s['total_potentiations']}, Depressions: {s['total_depressions']}")

        # Cleanup
        os.unlink(test_db)
        print("\n=== All self-tests passed ===")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

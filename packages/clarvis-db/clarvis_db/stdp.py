"""
STDP (Spike-Timing-Dependent Plasticity) synaptic memory layer.

Memristor-inspired neural memory backed by SQLite. Models memory connections
as bounded, nonlinear conductances that evolve via STDP learning rules:

  - Bounded weights (w_min=0.001, w_max=1.0)
  - PCMO memristor nonlinear transfer function
  - Co-retrieval potentiation, isolation depression
  - Spreading activation for associative recall
  - Consolidation: decay, prune, hub detection

Standalone: only depends on Python stdlib (sqlite3).
"""

import json
import math
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# === MEMRISTOR PARAMETERS ===

W_MIN = 0.001
W_MAX = 1.0
W_INIT = 0.1
NU = 2.0

# STDP parameters
A_POT = 0.05
A_DEP = 0.03
TAU_POT = 300.0
TAU_DEP = 300.0
GAMMA = 0.9

# Consolidation
DECAY_RATE = 0.005
PRUNE_THRESHOLD = 0.005
MAX_SYNAPSES_PER_NODE = 50


class SynapticEngine:
    """Memristor-inspired synaptic memory backed by SQLite.

    Args:
        db_path: Path to SQLite database (created if missing).
    """

    def __init__(self, db_path: str = "./data/synaptic/synapses.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS synapses (
                pre_id   TEXT NOT NULL,
                post_id  TEXT NOT NULL,
                weight   REAL NOT NULL DEFAULT 0.1,
                state    REAL NOT NULL DEFAULT 0.5,
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
                timestamp       TEXT NOT NULL,
                synapses_total  INTEGER,
                potentiated     INTEGER,
                depressed       INTEGER,
                pruned          INTEGER,
                avg_weight      REAL,
                hub_count       INTEGER
            );
        """)
        conn.commit()
        conn.close()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # === MEMRISTOR TRANSFER FUNCTION ===

    @staticmethod
    def memristor_weight(state: float, nu: float = NU) -> float:
        """Convert normalized state [0,1] to bounded weight [W_MIN, W_MAX].

        Uses the PCMO memristor nonlinear transfer function.
        """
        if nu == 0:
            return W_MIN + (W_MAX - W_MIN) * state
        exp_nu = math.exp(-nu)
        w = W_MAX - (W_MAX - W_MIN) / (1.0 - exp_nu) * (1.0 - math.exp(-nu * (1.0 - state)))
        return max(W_MIN, min(W_MAX, w))

    @staticmethod
    def inverse_memristor(weight: float, nu: float = NU) -> float:
        """Convert weight back to normalized state variable."""
        if nu == 0:
            return (weight - W_MIN) / (W_MAX - W_MIN)
        exp_nu = math.exp(-nu)
        ratio = (W_MAX - weight) * (1.0 - exp_nu) / (W_MAX - W_MIN)
        inner = max(1e-10, 1.0 - ratio)
        state = 1.0 + math.log(inner) / nu
        return max(0.0, min(1.0, state))

    # === CORE OPERATIONS ===

    def potentiate(self, pre_id: str, post_id: str, delta_t: float = 0.0) -> float:
        """Strengthen the synapse (STDP potentiation).

        Args:
            pre_id: Pre-synaptic memory ID.
            post_id: Post-synaptic memory ID.
            delta_t: Time difference in seconds.

        Returns:
            New synaptic weight.
        """
        conn = self._conn()
        try:
            _, state = self._get_or_create(conn, pre_id, post_id)
            timing = A_POT * math.exp(-abs(delta_t) / TAU_POT) if delta_t >= 0 else A_POT * 0.5
            dist = max(0.001, 1.0 - state)
            new_state = min(1.0, state + timing * (dist ** GAMMA))
            new_weight = self.memristor_weight(new_state)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE synapses SET weight=?, state=?, potentiations=potentiations+1, "
                "updated_at=? WHERE pre_id=? AND post_id=?",
                (new_weight, new_state, now, pre_id, post_id),
            )
            conn.commit()
            return new_weight
        finally:
            conn.close()

    def depress(self, pre_id: str, post_id: str, delta_t: float = 0.0) -> Optional[float]:
        """Weaken the synapse (STDP depression).

        Returns:
            New weight, or None if no synapse exists.
        """
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
                (pre_id, post_id),
            ).fetchone()
            if not row:
                return None
            state = row[1]
            timing = A_DEP * math.exp(-abs(delta_t) / TAU_DEP)
            dist = max(0.001, state)
            new_state = max(0.0, state - timing * (dist ** GAMMA))
            new_weight = self.memristor_weight(new_state)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE synapses SET weight=?, state=?, depressions=depressions+1, "
                "updated_at=? WHERE pre_id=? AND post_id=?",
                (new_weight, new_state, now, pre_id, post_id),
            )
            conn.commit()
            return new_weight
        finally:
            conn.close()

    def record_activation(self, memory_id: str, source: Optional[str] = None):
        """Record that a memory was activated."""
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc).timestamp()
            conn.execute(
                "INSERT OR REPLACE INTO activations (memory_id, timestamp, source) VALUES (?, ?, ?)",
                (memory_id, now, source),
            )
            conn.commit()
        finally:
            conn.close()

    def spread(self, source_ids, n: int = 10, min_weight: float = 0.05) -> List[Tuple[str, float]]:
        """Spreading activation — find memories strongly connected to source(s).

        Args:
            source_ids: Single ID or list of active memory IDs.
            n: Max results.
            min_weight: Minimum synapse weight.

        Returns:
            List of (memory_id, total_activation) sorted by activation.
        """
        if isinstance(source_ids, str):
            source_ids = [source_ids]
        conn = self._conn()
        try:
            ph = ",".join("?" * len(source_ids))
            rows = conn.execute(f"""
                SELECT post_id, SUM(weight) as total_activation
                FROM synapses
                WHERE pre_id IN ({ph})
                  AND weight >= ?
                  AND post_id NOT IN ({ph})
                GROUP BY post_id
                ORDER BY total_activation DESC
                LIMIT ?
            """, source_ids + [min_weight] + source_ids + [n]).fetchall()
            return [(r[0], round(r[1], 4)) for r in rows]
        finally:
            conn.close()

    def on_recall(self, memory_ids: List[str], caller: Optional[str] = None):
        """Hook for co-retrieval: potentiate all pairs.

        Args:
            memory_ids: IDs of co-retrieved memories.
            caller: Who triggered the recall.
        """
        if len(memory_ids) < 2:
            return
        for mem_id in memory_ids:
            self.record_activation(mem_id, source=caller)
        for i, id_a in enumerate(memory_ids):
            for j, id_b in enumerate(memory_ids):
                if i == j:
                    continue
                delta_t = abs(i - j) * 10.0
                self.potentiate(id_a, id_b, delta_t=delta_t)

    # === CONSOLIDATION ===

    def consolidate(self) -> Dict[str, Any]:
        """Nightly consolidation: decay, prune, enforce limits.

        Returns:
            Stats dict.
        """
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            decayed = conn.execute(
                "UPDATE synapses SET weight = MAX(?, weight * ?), "
                "state = MAX(0.0, state * ?), updated_at = ?",
                (W_MIN, 1.0 - DECAY_RATE, 1.0 - DECAY_RATE, now_iso),
            ).rowcount

            pruned = conn.execute(
                "DELETE FROM synapses WHERE weight < ?", (PRUNE_THRESHOLD,)
            ).rowcount

            over_limit = conn.execute("""
                SELECT pre_id, COUNT(*) as cnt FROM synapses
                GROUP BY pre_id HAVING cnt > ?
            """, (MAX_SYNAPSES_PER_NODE,)).fetchall()

            extra_pruned = 0
            for pre_id, cnt in over_limit:
                excess = cnt - MAX_SYNAPSES_PER_NODE
                conn.execute("""
                    DELETE FROM synapses WHERE rowid IN (
                        SELECT rowid FROM synapses WHERE pre_id = ?
                        ORDER BY weight ASC LIMIT ?
                    )
                """, (pre_id, excess))
                extra_pruned += excess

            cutoff_ts = (now - timedelta(days=7)).timestamp()
            conn.execute("DELETE FROM activations WHERE timestamp < ?", (cutoff_ts,))

            stats_row = conn.execute("""
                SELECT COUNT(*), AVG(weight), MIN(weight), MAX(weight)
                FROM synapses
            """).fetchone()

            total_synapses = stats_row[0] or 0
            avg_weight = round(stats_row[1] or 0, 4)

            hubs = conn.execute("""
                SELECT pre_id, COUNT(*) as fan_out FROM synapses
                WHERE weight >= 0.1
                GROUP BY pre_id HAVING fan_out >= 5
            """).fetchall()

            conn.commit()

            conn.execute(
                "INSERT INTO evolution_log VALUES (?, ?, 0, 0, ?, ?, ?)",
                (now_iso, total_synapses, pruned + extra_pruned, avg_weight, len(hubs)),
            )
            conn.commit()

            return {
                "total_synapses": total_synapses,
                "decayed": decayed,
                "pruned": pruned + extra_pruned,
                "avg_weight": avg_weight,
                "hub_count": len(hubs),
            }
        finally:
            conn.close()

    # === QUERIES ===

    def get_synapse(self, pre_id: str, post_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific synapse."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT weight, state, potentiations, depressions, created_at, updated_at "
                "FROM synapses WHERE pre_id=? AND post_id=?",
                (pre_id, post_id),
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

    def get_strongest(self, n: int = 20) -> List[Dict[str, Any]]:
        """Get the strongest synapses."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT pre_id, post_id, weight, potentiations, depressions "
                "FROM synapses ORDER BY weight DESC LIMIT ?", (n,)
            ).fetchall()
            return [
                {"pre": r[0], "post": r[1], "weight": round(r[2], 4), "pot": r[3], "dep": r[4]}
                for r in rows
            ]
        finally:
            conn.close()

    def get_hubs(self, min_fanout: int = 3, min_weight: float = 0.05) -> List[Dict[str, Any]]:
        """Find hub memories with high fan-out."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT pre_id, COUNT(*) as fan_out,
                       AVG(weight) as avg_w, SUM(weight) as total_w
                FROM synapses WHERE weight >= ?
                GROUP BY pre_id HAVING fan_out >= ?
                ORDER BY total_w DESC LIMIT 20
            """, (min_weight, min_fanout)).fetchall()
            return [
                {"memory_id": r[0], "fan_out": r[1],
                 "avg_weight": round(r[2], 4), "total_weight": round(r[3], 4)}
                for r in rows
            ]
        finally:
            conn.close()

    def stats(self) -> Dict[str, Any]:
        """Comprehensive network statistics."""
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

            unique_nodes = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT pre_id as id FROM synapses UNION
                    SELECT post_id as id FROM synapses
                )
            """).fetchone()[0]

            return {
                "total_synapses": total,
                "unique_nodes": unique_nodes,
                "avg_weight": round(row[0] or 0, 4),
                "min_weight": round(row[1] or 0, 4),
                "max_weight": round(row[2] or 0, 4),
                "total_potentiations": row[3] or 0,
                "total_depressions": row[4] or 0,
                "status": "active",
            }
        finally:
            conn.close()

    # === INTERNAL ===

    def _get_or_create(self, conn, pre_id, post_id):
        row = conn.execute(
            "SELECT weight, state FROM synapses WHERE pre_id=? AND post_id=?",
            (pre_id, post_id),
        ).fetchone()
        if row:
            return row
        now = datetime.now(timezone.utc).isoformat()
        init_state = self.inverse_memristor(W_INIT)
        conn.execute(
            "INSERT OR IGNORE INTO synapses (pre_id, post_id, weight, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pre_id, post_id, W_INIT, init_state, now, now),
        )
        return (W_INIT, init_state)

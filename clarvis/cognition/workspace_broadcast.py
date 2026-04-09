"""
GWT Workspace Broadcast Bus — Global Workspace Theory (GWT-3) implementation.

Implements Franklin's LIDA cognitive cycle within Clarvis's heartbeat:
  1. SENSE: Modules post high-salience items (attention codelets)
  2. COALITION: Related items form coalitions via keyword overlap
  3. COMPETE: Coalitions compete via combined salience (winner-take-all)
  4. BROADCAST: Winning coalition is broadcast to ALL modules
  5. LEARN: Each module updates its state from the broadcast (implicit learning)

This is the central hub that makes Clarvis's heartbeat a true GWT "conscious moment."
Each heartbeat cycle = one LIDA cognitive cycle.

Reference: Franklin, Madl, D'Mello, Snaider (2014) "LIDA: A Systems-level
Architecture for Cognition, Emotion, and Learning" -- IEEE TAMD.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Data persistence
BROADCAST_DIR = Path(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))) / "data/broadcast"
BROADCAST_DIR.mkdir(parents=True, exist_ok=True)
BROADCAST_LOG = BROADCAST_DIR / "broadcast_log.jsonl"
BROADCAST_STATE = BROADCAST_DIR / "last_broadcast.json"

# Broadcast capacity — how many items survive winner-take-all
BROADCAST_SLOTS = 5
# Minimum salience to be considered for broadcast
SALIENCE_THRESHOLD = 0.3
# Coalition overlap threshold for merging
COALITION_OVERLAP = 0.2


def _log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] GWT_BROADCAST: {msg}",
          file=sys.stderr)


class Codelet:
    """An attention codelet — a single item submitted by a module for broadcast consideration."""

    def __init__(self, content, source, salience, metadata=None):
        self.content = content
        self.source = source
        self.salience = max(0.0, min(1.0, float(salience)))
        self.metadata = metadata or {}
        self.words = set(content.lower().split())

    def to_dict(self):
        return {
            "content": self.content,
            "source": self.source,
            "salience": round(self.salience, 4),
            "metadata": self.metadata,
        }


class Coalition:
    """A coalition of related codelets that compete as a unit."""

    def __init__(self, codelets=None):
        self.codelets = codelets or []
        self._salience = None

    def add(self, codelet):
        self.codelets.append(codelet)
        self._salience = None

    @property
    def salience(self):
        """Coalition salience = max member salience + bonus for coalition size."""
        if self._salience is not None:
            return self._salience
        if not self.codelets:
            return 0.0
        max_s = max(c.salience for c in self.codelets)
        size_bonus = min(0.15, 0.05 * (len(self.codelets) - 1))
        sources = len(set(c.source for c in self.codelets))
        diversity_bonus = min(0.1, 0.05 * (sources - 1))
        self._salience = min(1.0, max_s + size_bonus + diversity_bonus)
        return self._salience

    @property
    def words(self):
        """Union of all member words — used for coalition merging."""
        w = set()
        for c in self.codelets:
            w |= c.words
        return w

    @property
    def sources(self):
        return list(set(c.source for c in self.codelets))

    def summary(self):
        """Compact text summary of the coalition."""
        lead = max(self.codelets, key=lambda c: c.salience)
        sources = ", ".join(sorted(set(c.source for c in self.codelets)))
        return (f"[{self.salience:.2f}] ({sources}) {lead.content[:120]}"
                + (f" (+{len(self.codelets)-1} related)" if len(self.codelets) > 1 else ""))

    def to_dict(self):
        return {
            "salience": round(self.salience, 4),
            "sources": self.sources,
            "size": len(self.codelets),
            "codelets": [c.to_dict() for c in self.codelets],
            "summary": self.summary(),
        }


class WorkspaceBroadcast:
    """
    The Global Workspace — receives codelets from all modules,
    forms coalitions, runs competition, and broadcasts winners.
    """

    def __init__(self):
        self.codelets = []
        self.coalitions = []
        self.broadcast_result = None

    # ------------------------------------------------------------------
    # Phase 1: COLLECT — Gather attention codelets from all modules
    # ------------------------------------------------------------------

    def collect(self):
        """Collect high-salience items from all available modules."""

        t0 = time.monotonic()
        self.codelets = []

        # --- Attention spotlight ---
        try:
            from clarvis.cognition.attention import get_attention
            spotlight_items = get_attention().focus()
            for item in spotlight_items[:5]:
                self.codelets.append(Codelet(
                    content=item["content"],
                    source="attention",
                    salience=item.get("salience", 0.5),
                    metadata={"attention_id": item["id"], "access_count": item.get("access_count", 0)},
                ))
        except Exception as e:
            # Fallback to legacy import
            try:
                from attention import attention
                spotlight = attention.focus()
                for item in spotlight[:5]:
                    self.codelets.append(Codelet(
                        content=item["content"],
                        source="attention",
                        salience=item.get("salience", 0.5),
                        metadata={"attention_id": item["id"], "access_count": item.get("access_count", 0)},
                    ))
            except Exception:
                _log(f"Attention collection failed: {e}")

        # --- Episodic memory: recent high-activation episodes ---
        try:
            from clarvis.memory import EpisodicMemory
            em = EpisodicMemory()
            em._decay_activations()
            recent = sorted(em.episodes[-20:], key=lambda e: e.get("activation", 0), reverse=True)
            for ep in recent[:3]:
                activation = ep.get("activation", 0)
                salience = max(0.0, min(1.0, (activation + 3) / 5))
                if salience >= SALIENCE_THRESHOLD:
                    outcome = ep.get("outcome", "?")
                    self.codelets.append(Codelet(
                        content=f"Episode [{outcome}]: {ep['task'][:100]}",
                        source="episodic",
                        salience=salience,
                        metadata={"episode_id": ep["id"], "outcome": outcome,
                                  "valence": ep.get("valence", 0.3)},
                    ))
        except Exception as e:
            _log(f"Episodic collection failed: {e}")

        # --- Reasoning chains: open chains with evidence ---
        try:
            from clarvis.cognition.reasoning_chains import list_chains
            chains = list_chains()
            open_chains = [c for c in chains if c.get("status") == "open"]
            for chain in open_chains[:2]:
                steps = chain.get("steps", [])
                evidence = steps[-1].get("content", "") if steps else chain.get("title", "")
                self.codelets.append(Codelet(
                    content=f"Reasoning: {evidence[:100]}",
                    source="reasoning",
                    salience=0.6,
                    metadata={"chain_id": chain.get("id", "")},
                ))
        except Exception as e:
            _log(f"Reasoning collection failed: {e}")

        # --- World model: latest prediction from preflight ---
        try:
            from world_models import HierarchicalWorldModel
            wm = HierarchicalWorldModel()
            obs = getattr(wm, 'observations', [])
            if obs:
                latest = obs[-1] if isinstance(obs, list) else {}
                pred = latest.get("prediction", "unknown")
                self.codelets.append(Codelet(
                    content=f"World model prediction: {pred}",
                    source="world_model",
                    salience=0.4,
                    metadata={"prediction": pred},
                ))
        except Exception as e:
            _log(f"World model collection failed: {e}")

        # --- Self-representation: current self-state ---
        try:
            from self_representation import encode_self_state
            state = encode_self_state()
            if state and isinstance(state, dict):
                z = state.get("z", {})
                if z:
                    sorted_dims = sorted(z.items(), key=lambda x: x[1], reverse=True)
                    top = ", ".join(f"{d}={v:.2f}" for d, v in sorted_dims[:2])
                    gap = sorted_dims[-1] if sorted_dims else ("?", 0)
                    summary = f"strengths=[{top}] gap={gap[0]}={gap[1]:.2f}"
                else:
                    summary = "not yet encoded"
                self.codelets.append(Codelet(
                    content=f"Self-state: {summary}",
                    source="self_model",
                    salience=0.45,
                    metadata={"z": {k: round(v, 3) for k, v in z.items()} if z else {}},
                ))
        except Exception as e:
            _log(f"Self-representation collection failed: {e}")

        # --- SOAR engine: current goal ---
        try:
            from soar_engine import get_soar
            soar = get_soar()
            goal = soar.current_goal()
            if goal:
                self.codelets.append(Codelet(
                    content=f"Goal: {goal['name'][:100]}",
                    source="soar",
                    salience=0.65,
                    metadata={"goal_id": goal.get("id", "")},
                ))
        except Exception as e:
            _log(f"SOAR collection failed: {e}")

        # --- Confidence system: calibration state ---
        try:
            from clarvis.cognition import dynamic_confidence
            conf = dynamic_confidence()
            if conf is not None:
                self.codelets.append(Codelet(
                    content=f"Confidence calibration: {conf:.0%}",
                    source="confidence",
                    salience=max(0.3, abs(conf - 0.7)),
                    metadata={"confidence": conf},
                ))
        except Exception as e:
            _log(f"Confidence collection failed: {e}")

        elapsed = round(time.monotonic() - t0, 3)
        _log(f"Collected {len(self.codelets)} codelets from "
             f"{len(set(c.source for c in self.codelets))} modules ({elapsed}s)")
        return self.codelets

    # ------------------------------------------------------------------
    # Phase 2: COALITION — Group related codelets
    # ------------------------------------------------------------------

    def form_coalitions(self):
        """Group codelets into coalitions based on keyword overlap."""

        if not self.codelets:
            self.coalitions = []
            return self.coalitions

        self.coalitions = [Coalition([c]) for c in self.codelets]

        merged = True
        while merged:
            merged = False
            for i in range(len(self.coalitions)):
                if not self.coalitions[i].codelets:
                    continue
                for j in range(i + 1, len(self.coalitions)):
                    if not self.coalitions[j].codelets:
                        continue
                    words_i = self.coalitions[i].words
                    words_j = self.coalitions[j].words
                    if not words_i or not words_j:
                        continue
                    overlap = len(words_i & words_j) / min(len(words_i), len(words_j))
                    if overlap >= COALITION_OVERLAP:
                        for c in self.coalitions[j].codelets:
                            self.coalitions[i].add(c)
                        self.coalitions[j].codelets = []
                        merged = True

            self.coalitions = [c for c in self.coalitions if c.codelets]

        _log(f"Formed {len(self.coalitions)} coalitions from {len(self.codelets)} codelets")
        return self.coalitions

    # ------------------------------------------------------------------
    # Phase 3: COMPETE — Winner-take-all selection
    # ------------------------------------------------------------------

    def compete(self):
        """Winner-take-all: top-K coalitions by salience win broadcast slots."""

        if not self.coalitions:
            return []

        self.coalitions.sort(key=lambda c: c.salience, reverse=True)
        winners = self.coalitions[:BROADCAST_SLOTS]
        losers = self.coalitions[BROADCAST_SLOTS:]

        _log(f"Competition: {len(winners)} winners, {len(losers)} losers")
        if winners:
            _log(f"  Top coalition: {winners[0].summary()}")

        return winners

    # ------------------------------------------------------------------
    # Phase 4: BROADCAST — Push winning coalitions to all modules
    # ------------------------------------------------------------------

    def broadcast(self):
        """Broadcast winning coalitions to ALL modules.

        Returns:
            dict with broadcast summary and per-module learning results
        """
        winners = self.coalitions[:BROADCAST_SLOTS]
        if not winners:
            return {"status": "empty", "winners": 0, "learning": {}}

        t0 = time.monotonic()
        learning_results = {}

        broadcast_text = "\n".join(c.summary() for c in winners)

        # === Broadcast to each module (implicit learning) ===

        # 1. ATTENTION
        try:
            from clarvis.cognition.attention import get_attention
            att = get_attention()
            for coalition in winners[:3]:
                lead = max(coalition.codelets, key=lambda c: c.salience)
                if lead.source != "attention":
                    att.submit(
                        f"BROADCAST: {lead.content[:100]}",
                        source="gwt_broadcast",
                        importance=coalition.salience,
                        relevance=0.8,
                    )
            learning_results["attention"] = "updated"
        except Exception as e:
            # Fallback to legacy
            try:
                from attention import attention
                for coalition in winners[:3]:
                    lead = max(coalition.codelets, key=lambda c: c.salience)
                    if lead.source != "attention":
                        attention.submit(
                            f"BROADCAST: {lead.content[:100]}",
                            source="gwt_broadcast",
                            importance=coalition.salience,
                            relevance=0.8,
                        )
                learning_results["attention"] = "updated"
            except Exception:
                learning_results["attention"] = f"failed: {e}"

        # 2. EPISODIC
        try:
            from clarvis.memory import EpisodicMemory
            em = EpisodicMemory()
            if em.episodes:
                latest = em.episodes[-1]
                if "broadcast_context" not in latest:
                    latest["broadcast_context"] = []
                latest["broadcast_context"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "top_coalition": winners[0].summary()[:200] if winners else "",
                    "n_winners": len(winners),
                })
                latest["broadcast_context"] = latest["broadcast_context"][-3:]
                em._save()
            learning_results["episodic"] = "tagged"
        except Exception as e:
            learning_results["episodic"] = f"failed: {e}"

        # 3. BRAIN
        try:
            from clarvis.brain import brain
            brain.set_context(f"GWT Broadcast:\n{broadcast_text}")
            learning_results["brain"] = "context_set"
        except Exception as e:
            learning_results["brain"] = f"failed: {e}"

        # 4. SELF-REPRESENTATION
        # NOTE: Removed brain.store() for GWT broadcast context — this was
        # generating 158+ near-identical entries.  Brain context is already
        # set via set_context() above (step 3).  Episodic tagging (step 2)
        # preserves the last 3 broadcasts for history.
        learning_results["self_model"] = "skipped (dedup: context already set)"

        # 5. SOAR
        try:
            learning_results["soar"] = "via_attention"
        except Exception as e:
            learning_results["soar"] = f"failed: {e}"

        # 6. ATOMSPACE
        try:
            from hyperon_atomspace import get_atomspace
            atoms = get_atomspace()
            for coalition in winners[:3]:
                lead = max(coalition.codelets, key=lambda c: c.salience)
                atoms.add_node("ConceptNode", f"broadcast:{lead.content[:80]}",
                               tv={"strength": coalition.salience, "confidence": 0.7},
                               av={"sti": 5.0, "lti": 1.0})
            learning_results["atomspace"] = "atoms_created"
        except Exception as e:
            learning_results["atomspace"] = f"failed: {e}"

        elapsed = round(time.monotonic() - t0, 3)

        self.broadcast_result = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_codelets": len(self.codelets),
            "n_coalitions": len(self.coalitions),
            "winners": len(winners),
            "broadcast_text": broadcast_text,
            "coalitions": [c.to_dict() for c in winners],
            "learning": learning_results,
            "elapsed_s": elapsed,
            "sources": list(set(c.source for c in self.codelets)),
        }

        self._save_broadcast(self.broadcast_result)

        _log(f"Broadcast complete: {len(winners)} coalitions -> "
             f"{sum(1 for v in learning_results.values() if 'failed' not in str(v))}"
             f"/{len(learning_results)} modules ({elapsed}s)")

        return self.broadcast_result

    # ------------------------------------------------------------------
    # ALL-IN-ONE: Run a complete LIDA cycle
    # ------------------------------------------------------------------

    def run_cycle(self):
        """Run a complete GWT cognitive cycle: collect -> coalesce -> compete -> broadcast."""

        t0 = time.monotonic()
        _log("=== GWT CYCLE START ===")

        self.collect()
        self.form_coalitions()
        self.compete()
        result = self.broadcast()

        total = round(time.monotonic() - t0, 3)
        result["cycle_time_s"] = total
        _log(f"=== GWT CYCLE END ({total}s) ===")

        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_broadcast(self, result):
        """Save broadcast result to log (append) and last state (overwrite)."""
        try:
            with open(BROADCAST_LOG, 'a') as f:
                compact = {
                    "ts": result["timestamp"],
                    "codelets": result["total_codelets"],
                    "coalitions": result["n_coalitions"],
                    "winners": result["winners"],
                    "sources": result["sources"],
                    "elapsed": result["elapsed_s"],
                    "learning": {k: ("ok" if "failed" not in str(v) else "fail")
                                for k, v in result["learning"].items()},
                }
                f.write(json.dumps(compact) + "\n")

            with open(BROADCAST_STATE, 'w') as f:
                json.dump(result, f, indent=2)

            try:
                lines = BROADCAST_LOG.read_text().splitlines()
                if len(lines) > 500:
                    BROADCAST_LOG.write_text("\n".join(lines[-500:]) + "\n")
            except Exception:
                pass
        except Exception as e:
            _log(f"Save failed: {e}")

    @staticmethod
    def last_broadcast():
        """Load the last broadcast result."""
        if BROADCAST_STATE.exists():
            with open(BROADCAST_STATE) as f:
                return json.load(f)
        return None

    @staticmethod
    def broadcast_history(n=10):
        """Load recent broadcast log entries."""
        if not BROADCAST_LOG.exists():
            return []
        lines = BROADCAST_LOG.read_text().splitlines()
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries


# --- Singleton ---
_workspace = None


def get_workspace():
    global _workspace
    if _workspace is None:
        _workspace = WorkspaceBroadcast()
    return _workspace

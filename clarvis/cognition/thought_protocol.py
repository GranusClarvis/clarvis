#!/usr/bin/env python3
"""
Thought Protocol — Clarvis Internal Meta-Language for Thought

A DSL optimized for speed of internal reasoning, not human readability.
Represents memory relationships, salience signals, and decision patterns
as compact symbolic expressions that can be parsed, evaluated, and composed.

The protocol has three layers:
  1. SIGNALS: Compact representations of cognitive state
     - Salience vectors, emotional biases, activation levels
  2. RELATIONS: Memory relationship patterns
     - Semantic links, causal chains, temporal sequences
  3. DECISIONS: Composable decision rules
     - Pattern-matching on signals → action selection

Notation (ThoughtScript):
  Signal:    @signal_name(value)         e.g., @sal(0.8) @emo(approach,0.6)
  Memory:    #mem_id                      e.g., #ep_20260222_143200
  Relation:  #a -> #b [type]             e.g., #m1 -> #m2 [causal]
  Query:     ?query_text                  e.g., ?retrieval_performance
  Decision:  IF cond THEN action          e.g., IF @sal>0.7 AND @emo.approach THEN execute
  Sequence:  expr ; expr ; expr          e.g., ?task ; @score ; !decide
  Action:    !action(args)               e.g., !select(#task1) !recall("attention")
  Compound:  { expr1 ; expr2 }           e.g., { ?ctx ; @sal(0.8) ; !focus }

This is NOT meant for humans. It's Clarvis's inner voice — compressed, fast, precise.

Usage:
    from clarvis.cognition.thought_protocol import thought, ThoughtFrame

    # Create a thought frame for task selection
    frame = thought.frame("task_selection")
    frame.signal("sal", 0.85)
    frame.signal("emo", {"approach": 0.6, "avoid": 0.1})
    frame.relate("#ep_001", "#task_007", "similar_context")
    frame.decide("sal>0.7 AND emo.approach>0.3", "execute")
    result = frame.resolve()

    # Or use ThoughtScript notation directly
    result = thought.eval("?current_task ; @sal ; IF @sal>0.7 THEN !execute")

    # Encode cognitive state as compact signal vector
    vec = thought.encode_state()
    # -> "S[sal=0.85|emo=+0.6/-0.1|act=0.72|ctx=task_selection|ep=48/0.88]"
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_WS = os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
_SCRIPTS_DIR = os.path.join(_WS, "scripts")


# NOTE: Disk logging to thought_log.jsonl was removed in Phase 6 (2026-04-09).
# The file had zero downstream consumers. Thought frames are kept in-memory only
# (frame_history, last 50) and surfaced via get_recent_thoughts() / thought_stats().


# =============================================================================
# Layer 1: SIGNALS — compact cognitive state representations
# =============================================================================

@dataclass
class Signal:
    """A single cognitive signal — a named value with optional dimensions."""
    name: str
    value: Any  # float, dict, or str
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    def strength(self) -> float:
        """Scalar strength of this signal."""
        if isinstance(self.value, (int, float)):
            return float(self.value)
        if isinstance(self.value, dict):
            # For multi-dimensional signals, return max absolute value
            return max(abs(v) for v in self.value.values()) if self.value else 0.0
        return 0.5  # Unknown type → neutral

    def encode(self) -> str:
        """Encode as ThoughtScript notation."""
        if isinstance(self.value, (int, float)):
            return f"@{self.name}({self.value:.2f})"
        if isinstance(self.value, dict):
            parts = "/".join(f"{k}={v:.2f}" for k, v in self.value.items())
            return f"@{self.name}({parts})"
        return f"@{self.name}({self.value})"


@dataclass
class SignalVector:
    """A collection of signals representing full cognitive state at one moment."""
    signals: dict = field(default_factory=dict)  # name -> Signal

    def set(self, name: str, value: Any, source: str = ""):
        self.signals[name] = Signal(name, value, source=source)

    def get(self, name: str, default=0.0) -> Any:
        sig = self.signals.get(name)
        return sig.value if sig else default

    def strength(self, name: str) -> float:
        sig = self.signals.get(name)
        return sig.strength() if sig else 0.0

    def encode(self) -> str:
        """Encode full state as compact string: S[sal=0.8|emo=+0.6/-0.1|...]"""
        parts = []
        for name in sorted(self.signals.keys()):
            sig = self.signals[name]
            if isinstance(sig.value, (int, float)):
                parts.append(f"{name}={sig.value:.2f}")
            elif isinstance(sig.value, dict):
                vals = "/".join(f"{v:.2f}" for v in sig.value.values())
                parts.append(f"{name}={vals}")
            else:
                parts.append(f"{name}={sig.value}")
        return "S[" + "|".join(parts) + "]"

    def to_dict(self) -> dict:
        return {name: sig.value for name, sig in self.signals.items()}


# =============================================================================
# Layer 2: RELATIONS — memory relationship patterns
# =============================================================================

@dataclass
class Relation:
    """A relationship between two memory/cognitive nodes."""
    source_id: str
    target_id: str
    rel_type: str  # similar_context, causal, temporal, inhibits, supports
    weight: float = 1.0
    evidence: str = ""

    def encode(self) -> str:
        return f"#{self.source_id} -> #{self.target_id} [{self.rel_type}:{self.weight:.1f}]"


class RelationGraph:
    """Lightweight in-frame relation graph for reasoning."""

    def __init__(self):
        self.relations: list[Relation] = []
        self._index: dict[str, list[Relation]] = {}

    def add(self, source_id: str, target_id: str, rel_type: str,
            weight: float = 1.0, evidence: str = "") -> Relation:
        rel = Relation(source_id, target_id, rel_type, weight, evidence)
        self.relations.append(rel)
        self._index.setdefault(source_id, []).append(rel)
        self._index.setdefault(target_id, []).append(rel)
        return rel

    def neighbors(self, node_id: str, rel_type: str = None) -> list[Relation]:
        rels = self._index.get(node_id, [])
        if rel_type:
            return [r for r in rels if r.rel_type == rel_type]
        return rels

    def strongest_path(self, source: str, target: str, max_depth: int = 3) -> list[Relation]:
        """BFS for strongest path between two nodes."""
        if source == target:
            return []
        visited = {source}
        queue = [(source, [])]
        for _ in range(max_depth * len(self.relations)):
            if not queue:
                break
            current, path = queue.pop(0)
            for rel in self._index.get(current, []):
                next_id = rel.target_id if rel.source_id == current else rel.source_id
                if next_id == target:
                    return path + [rel]
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [rel]))
        return []

    def encode(self) -> str:
        return " ; ".join(r.encode() for r in self.relations)


# =============================================================================
# Layer 3: DECISIONS — pattern-matching decision rules
# =============================================================================

@dataclass
class DecisionRule:
    """IF condition THEN action pattern."""
    condition: str   # e.g., "sal>0.7 AND emo.approach>0.3"
    action: str      # e.g., "execute" or "recall" or "defer"
    confidence: float = 0.5
    source: str = ""

    def evaluate(self, signals: SignalVector) -> bool:
        """Evaluate condition against current signal state."""
        # Parse simple conditions: signal_name OP value
        # Supports: AND, OR, >, <, >=, <=, ==
        try:
            return self._eval_expr(self.condition, signals)
        except Exception:
            return False

    def _eval_expr(self, expr: str, signals: SignalVector) -> bool:
        """Evaluate a condition expression."""
        expr = expr.strip()

        # Handle OR (lower precedence)
        if " OR " in expr:
            parts = expr.split(" OR ", 1)
            return self._eval_expr(parts[0], signals) or self._eval_expr(parts[1], signals)

        # Handle AND
        if " AND " in expr:
            parts = expr.split(" AND ", 1)
            return self._eval_expr(parts[0], signals) and self._eval_expr(parts[1], signals)

        # Handle NOT
        if expr.startswith("NOT "):
            return not self._eval_expr(expr[4:], signals)

        # Atomic comparison: signal_name op value
        # Supports dotted access: emo.approach > 0.3
        for op, fn in [(">=", lambda a, b: a >= b), ("<=", lambda a, b: a <= b),
                        (">", lambda a, b: a > b), ("<", lambda a, b: a < b),
                        ("==", lambda a, b: abs(a - b) < 0.001)]:
            if op in expr:
                left, right = expr.split(op, 1)
                left = left.strip()
                right = float(right.strip())

                # Dotted access: emo.approach
                if "." in left:
                    sig_name, sub_key = left.split(".", 1)
                    val = signals.get(sig_name, {})
                    if isinstance(val, dict):
                        lval = val.get(sub_key, 0.0)
                    else:
                        lval = 0.0
                else:
                    lval = signals.strength(left)

                return fn(lval, right)

        return False

    def encode(self) -> str:
        return f"IF {self.condition} THEN !{self.action} [{self.confidence:.2f}]"


# =============================================================================
# ThoughtFrame — a single reasoning episode
# =============================================================================

class ThoughtFrame:
    """
    A ThoughtFrame is one unit of internal reasoning.

    It collects signals, relations, and decision rules for a specific
    cognitive task (e.g., "should I execute this task?" or "what do I recall
    about this topic?"). Frames are fast, disposable, and composable.
    """

    def __init__(self, purpose: str, frame_id: str = None):
        self.id = frame_id or f"tf_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.purpose = purpose
        self.created_at = time.time()
        self.signals = SignalVector()
        self.relations = RelationGraph()
        self.rules: list[DecisionRule] = []
        self.trace: list[str] = []  # Execution trace for debugging
        self._resolved = False
        self._result = None

    def signal(self, name: str, value: Any, source: str = ""):
        """Set a signal in this frame."""
        self.signals.set(name, value, source)
        self.trace.append(f"@{name}({value})")

    def relate(self, source_id: str, target_id: str, rel_type: str,
               weight: float = 1.0, evidence: str = ""):
        """Add a relation to this frame."""
        self.relations.add(source_id, target_id, rel_type, weight, evidence)
        self.trace.append(f"#{source_id}->{target_id}[{rel_type}]")

    def decide(self, condition: str, action: str, confidence: float = 0.5, source: str = ""):
        """Add a decision rule."""
        rule = DecisionRule(condition, action, confidence, source)
        self.rules.append(rule)
        self.trace.append(f"RULE({condition}→{action})")

    def resolve(self) -> dict:
        """
        Execute all decision rules against current signals.
        Returns the winning action and its confidence.
        """
        if self._resolved:
            return self._result

        matching_rules = []
        for rule in self.rules:
            if rule.evaluate(self.signals):
                matching_rules.append(rule)
                self.trace.append(f"MATCH({rule.condition}→{rule.action})")

        if matching_rules:
            # Pick highest confidence matching rule
            best = max(matching_rules, key=lambda r: r.confidence)
            self._result = {
                "action": best.action,
                "confidence": best.confidence,
                "matched_rules": len(matching_rules),
                "total_rules": len(self.rules),
                "signals": self.signals.to_dict(),
                "frame_id": self.id,
                "purpose": self.purpose,
            }
        else:
            self._result = {
                "action": "defer",
                "confidence": 0.0,
                "matched_rules": 0,
                "total_rules": len(self.rules),
                "signals": self.signals.to_dict(),
                "frame_id": self.id,
                "purpose": self.purpose,
            }

        self._resolved = True
        self.trace.append(f"RESOLVED→{self._result['action']}[{self._result['confidence']:.2f}]")
        return self._result

    def encode(self) -> str:
        """Encode entire frame as ThoughtScript."""
        parts = [
            f"FRAME({self.purpose})",
            self.signals.encode(),
        ]
        if self.relations.relations:
            parts.append(self.relations.encode())
        for rule in self.rules:
            parts.append(rule.encode())
        if self._resolved:
            parts.append(f"RESULT(!{self._result['action']}[{self._result['confidence']:.2f}])")
        return " ; ".join(parts)

    def duration_ms(self) -> float:
        return (time.time() - self.created_at) * 1000


# =============================================================================
# ThoughtProtocol — the main interface
# =============================================================================

class ThoughtProtocol:
    """
    Clarvis's internal thought protocol.

    Provides:
      - frame(): create a new reasoning frame
      - encode_state(): snapshot current cognitive state as compact signal string
      - eval(): evaluate ThoughtScript expressions
      - log(): persist thought traces for introspection
      - patterns: reusable decision pattern library
    """

    def __init__(self):
        self.active_frame: Optional[ThoughtFrame] = None
        self.frame_history: list[dict] = []
        self._patterns: dict[str, list[DecisionRule]] = {}
        self._load_patterns()
        self._register_defaults()

    def _register_defaults(self):
        """Register default decision patterns if not already loaded from disk."""
        defaults = {
            "urgent_task": [
                {"condition": "sal > 0.8", "action": "execute_now", "confidence": 0.9},
                {"condition": "sal > 0.5 AND emo_bias > 0", "action": "execute", "confidence": 0.7},
                {"condition": "sal <= 0.5", "action": "queue", "confidence": 0.5},
            ],
            "risky_action": [
                {"condition": "emo_bias < -0.3", "action": "avoid", "confidence": 0.8},
                {"condition": "emo_bias < -0.1 AND ep_act < 0.3", "action": "investigate", "confidence": 0.6},
                {"condition": "emo_bias >= 0 AND sal > 0.5", "action": "proceed_cautious", "confidence": 0.7},
            ],
            "memory_retrieval": [
                {"condition": "sal > 0.7", "action": "deep_recall", "confidence": 0.8},
                {"condition": "sal > 0.4", "action": "standard_recall", "confidence": 0.6},
                {"condition": "sal <= 0.4", "action": "quick_scan", "confidence": 0.5},
            ],
        }
        for name, rules in defaults.items():
            if name not in self._patterns:
                self._patterns[name] = [
                    DecisionRule(r["condition"], r["action"], r.get("confidence", 0.5))
                    for r in rules
                ]

    def frame(self, purpose: str) -> ThoughtFrame:
        """Create a new ThoughtFrame for a reasoning episode."""
        f = ThoughtFrame(purpose)
        self.active_frame = f
        return f

    def encode_state(self) -> str:
        """
        Snapshot current cognitive state from all subsystems.
        Returns a compact signal vector string.

        Queries: attention spotlight, somatic markers, episodic stats,
        brain context, recent performance.
        """
        sv = SignalVector()

        # 1. Attention/salience from spotlight
        try:
            from clarvis.cognition.attention import attention
            stats = attention.stats()
            sv.set("sal", stats.get("avg_salience", 0.0), "attention")
            sv.set("attn_n", stats.get("total_items", 0), "attention")
            sv.set("spot_n", stats.get("spotlight_size", 0), "attention")
        except Exception:
            sv.set("sal", 0.5, "default")

        # 2. Emotional state from somatic markers
        try:
            from clarvis.cognition.somatic_markers import somatic
            sm_stats = somatic.get_stats()
            signal_dist = sm_stats.get("signal_distribution", {})
            approach = signal_dist.get("approach", 0)
            avoid = signal_dist.get("avoid", 0)
            total_markers = sm_stats.get("total_markers", 1)
            sv.set("emo", {
                "approach": round(approach / max(total_markers, 1), 2),
                "avoid": round(avoid / max(total_markers, 1), 2),
                "strength": sm_stats.get("avg_strength", 0.0),
            }, "somatic")
        except Exception:
            sv.set("emo", {"approach": 0.5, "avoid": 0.0, "strength": 0.0}, "default")

        # 3. Episodic activation level
        try:
            from clarvis.memory.episodic_memory import episodic
            ep_stats = episodic.get_stats()
            sv.set("ep_n", ep_stats.get("total", 0), "episodic")
            sv.set("ep_act", ep_stats.get("avg_activation", 0.0), "episodic")
            sv.set("ep_rate", ep_stats.get("success_rate", 0.0), "episodic")
        except Exception:
            sv.set("ep_n", 0, "default")

        # 4. Brain context
        try:
            from clarvis.brain import brain
            ctx = brain.get_context()
            ctx_len = len(ctx) if ctx and ctx != "idle" else 0
            sv.set("ctx_active", 1.0 if ctx_len > 10 else 0.0, "brain")
        except Exception:
            sv.set("ctx_active", 0.0, "default")

        # 5. Timestamp
        sv.set("t", round(time.time() % 86400, 0), "clock")  # seconds since midnight

        return sv.encode()

    def eval(self, script: str) -> dict:
        """
        Evaluate a ThoughtScript expression.

        Supports:
          ?query       — recall from brain
          @sig(val)    — set signal
          !action(args) — execute action
          IF ... THEN   — decision rule
          expr ; expr   — sequence

        Returns dict with results of each expression.
        """
        results = []
        statements = [s.strip() for s in script.split(";")]

        frame = self.frame("eval")

        for stmt in statements:
            if not stmt:
                continue

            # ?query — recall
            if stmt.startswith("?"):
                query = stmt[1:].strip()
                result = self._action_recall(query)
                results.append({"type": "query", "query": query, "result": result})

            # @signal(value) — set signal
            elif stmt.startswith("@"):
                match = re.match(r"@(\w+)\((.+)\)", stmt)
                if match:
                    name = match.group(1)
                    raw_val = match.group(2)
                    try:
                        val = float(raw_val)
                    except ValueError:
                        val = raw_val
                    frame.signal(name, val)
                    results.append({"type": "signal", "name": name, "value": val})

            # !action(args) — execute
            elif stmt.startswith("!"):
                match = re.match(r"!(\w+)(?:\((.+)\))?", stmt)
                if match:
                    action = match.group(1)
                    args = match.group(2) or ""
                    result = self._execute_action(action, args, frame)
                    results.append({"type": "action", "action": action, "result": result})

            # IF ... THEN ... — decision rule
            elif stmt.upper().startswith("IF "):
                match = re.match(r"IF\s+(.+?)\s+THEN\s+!?(.+)", stmt, re.IGNORECASE)
                if match:
                    condition = match.group(1).strip()
                    action = match.group(2).strip()
                    frame.decide(condition, action, confidence=0.7)
                    results.append({"type": "rule", "condition": condition, "action": action})

        # Resolve all rules
        resolution = frame.resolve()
        results.append({"type": "resolution", **resolution})

        # Log this thought
        self._log_frame(frame, results)

        return {
            "script": script,
            "results": results,
            "resolution": resolution,
            "state": frame.signals.encode(),
            "trace": frame.trace,
            "duration_ms": round(frame.duration_ms(), 2),
        }

    def task_decision(self, task_text: str, salience: float,
                      somatic_bias: float = 0.0, spotlight_align: float = 0.0,
                      episode_activation: float = 0.0) -> dict:
        """
        Specialized thought frame for task execution decisions.

        This replaces the scattered scoring logic with a unified
        protocol-based decision. Can be called from task_selector.py.

        Returns:
            dict with "action" (execute/defer/investigate), "confidence",
            and full signal state.
        """
        frame = self.frame("task_decision")

        # Load signals
        frame.signal("sal", salience, "task_selector")
        frame.signal("emo_bias", somatic_bias, "somatic")
        frame.signal("spot_align", spotlight_align, "attention")
        frame.signal("ep_act", episode_activation, "episodic")

        # Combined readiness score
        readiness = (
            0.50 * salience +
            0.15 * max(0, somatic_bias + 0.5) +  # map [-1,1] to [0,1]
            0.15 * spotlight_align +
            0.20 * min(1.0, episode_activation + 0.5)
        )
        frame.signal("readiness", readiness, "computed")

        # Decision rules — the core decision patterns
        frame.decide("readiness >= 0.6", "execute", confidence=0.8, source="threshold_high")
        frame.decide("readiness >= 0.4 AND sal > 0.5", "execute", confidence=0.6, source="threshold_med")
        frame.decide("readiness >= 0.3 AND emo_bias > 0.3", "execute", confidence=0.5, source="emo_push")
        frame.decide("emo_bias < -0.3 AND readiness < 0.5", "defer", confidence=0.7, source="emo_block")
        frame.decide("readiness < 0.3", "defer", confidence=0.6, source="threshold_low")
        frame.decide("sal > 0.8 AND spot_align > 0.5", "execute", confidence=0.9, source="spotlight_match")

        result = frame.resolve()
        self._log_frame(frame, [result])
        return result

    def memory_query(self, query: str, context_signals: dict = None) -> dict:
        """
        Protocol-based memory query with signal-guided retrieval.

        Instead of raw brain.recall(), this wraps the query in a thought frame
        that considers current cognitive state to guide retrieval strategy.
        """
        frame = self.frame("memory_query")
        frame.signal("query", query, "user")

        if context_signals:
            for k, v in context_signals.items():
                frame.signal(k, v, "context")

        # Decide retrieval strategy based on signals
        frame.decide("sal > 0.7", "deep_recall", confidence=0.8)     # High salience → search more
        frame.decide("sal <= 0.7", "quick_recall", confidence=0.6)    # Low salience → fast search
        frame.decide("ep_act > 0.5", "episodic_first", confidence=0.7)  # Active episodes → check those

        result = frame.resolve()
        strategy = result["action"]

        # Execute retrieval based on strategy
        try:
            from clarvis.brain import brain
            if strategy == "deep_recall":
                memories = brain.recall(query, n=10, include_related=True, attention_boost=True)
            elif strategy == "episodic_first":
                from clarvis.memory.episodic_memory import episodic
                episodes = episodic.recall_similar(query, n=3)
                memories = brain.recall(query, n=5, attention_boost=True)
                result["episodes"] = [{"task": e["task"][:80], "outcome": e["outcome"]} for e in episodes]
            else:
                memories = brain.recall(query, n=5)

            result["memories"] = [{"doc": m["document"][:100], "dist": m.get("distance")} for m in memories[:5]]
            result["hit_count"] = len(memories)
        except Exception as e:
            result["error"] = str(e)
            result["memories"] = []

        self._log_frame(frame, [result])
        return result

    # === Pattern Library ===

    def register_pattern(self, name: str, rules: list[dict]):
        """Register a reusable decision pattern.

        Args:
            name: pattern name (e.g., "urgent_task", "risky_action")
            rules: list of {"condition": str, "action": str, "confidence": float}
        """
        self._patterns[name] = [
            DecisionRule(r["condition"], r["action"], r.get("confidence", 0.5))
            for r in rules
        ]
        self._save_patterns()

    def apply_pattern(self, name: str, frame: ThoughtFrame) -> bool:
        """Apply a named pattern's rules to a frame."""
        if name not in self._patterns:
            return False
        for rule in self._patterns[name]:
            frame.rules.append(rule)
        frame.trace.append(f"PATTERN({name},{len(self._patterns[name])}rules)")
        return True

    def _load_patterns(self):
        """Load decision patterns from disk."""
        pattern_file = Path(_WS) / "data" / "thought_patterns.json"
        if pattern_file.exists():
            try:
                data = json.loads(pattern_file.read_text())
                for name, rules in data.items():
                    self._patterns[name] = [
                        DecisionRule(r["condition"], r["action"], r.get("confidence", 0.5))
                        for r in rules
                    ]
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_patterns(self):
        """Persist decision patterns."""
        pattern_file = Path(_WS) / "data" / "thought_patterns.json"
        data = {}
        for name, rules in self._patterns.items():
            data[name] = [
                {"condition": r.condition, "action": r.action, "confidence": r.confidence}
                for r in rules
            ]
        pattern_file.write_text(json.dumps(data, indent=2))

    # === Internal Actions ===

    def _action_recall(self, query: str) -> list:
        """Execute a memory recall action."""
        try:
            from clarvis.brain import brain
            results = brain.recall(query, n=3)
            return [{"doc": r["document"][:80], "dist": r.get("distance")} for r in results]
        except Exception as e:
            return [{"error": str(e)}]

    def _execute_action(self, action: str, args: str, frame: ThoughtFrame) -> Any:
        """Execute a named action."""
        if action == "recall":
            return self._action_recall(args.strip('"\''))
        elif action == "state":
            return self.encode_state()
        elif action == "focus":
            try:
                from clarvis.cognition.attention import attention
                return attention.focus_summary()
            except Exception:
                return "attention unavailable"
        elif action == "decide":
            return frame.resolve()
        elif action == "select":
            return {"selected": args, "frame": frame.id}
        else:
            return {"unknown_action": action, "args": args}

    # === Logging ===

    def _log_frame(self, frame: ThoughtFrame, results: list):
        """Record thought frame in memory history (last 50 frames)."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "frame_id": frame.id,
            "purpose": frame.purpose,
            "encoded": frame.encode(),
            "signals": frame.signals.to_dict(),
            "trace": frame.trace,
            "duration_ms": round(frame.duration_ms(), 2),
        }
        self.frame_history.append(entry)
        if len(self.frame_history) > 50:
            self.frame_history = self.frame_history[-50:]

    def get_recent_thoughts(self, n: int = 10) -> list:
        """Get recent thought frames for introspection."""
        return self.frame_history[-n:]

    def thought_stats(self) -> dict:
        """Statistics about thought protocol usage."""
        if not self.frame_history:
            return {"total_frames": 0}

        purposes = {}
        durations = []
        for entry in self.frame_history:
            p = entry.get("purpose", "unknown")
            purposes[p] = purposes.get(p, 0) + 1
            durations.append(entry.get("duration_ms", 0))

        return {
            "total_frames": len(self.frame_history),
            "purposes": purposes,
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "max_duration_ms": round(max(durations), 2) if durations else 0,
        }


# =============================================================================
# Singleton (lazy — no I/O until first access)
# =============================================================================

_thought = None

def get_thought():
    global _thought
    if _thought is None:
        _thought = ThoughtProtocol()
    return _thought

class _LazyThought:
    def __getattr__(self, name):
        real = get_thought()
        global thought
        thought = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazyThought (not yet initialized)>"

thought = _LazyThought()


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: thought_protocol.py <command> [args]")
        print("Commands:")
        print("  state              — encode current cognitive state")
        print("  eval <script>      — evaluate ThoughtScript expression")
        print("  decide <task> <sal> — run task decision frame")
        print("  query <text>       — protocol-based memory query")
        print("  recent [n]         — show recent thought frames")
        print("  stats              — thought protocol statistics")
        print("  patterns           — list registered decision patterns")
        print("  test               — run self-test")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "state":
        print(thought.encode_state())

    elif cmd == "eval":
        if len(sys.argv) < 3:
            print("Usage: eval <ThoughtScript expression>")
            sys.exit(1)
        script = " ".join(sys.argv[2:])
        result = thought.eval(script)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "decide":
        if len(sys.argv) < 4:
            print("Usage: decide <task_text> <salience>")
            sys.exit(1)
        task = sys.argv[2]
        sal = float(sys.argv[3])
        somatic_b = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        result = thought.task_decision(task, sal, somatic_b)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: query <text>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        result = thought.memory_query(query)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        thoughts = thought.get_recent_thoughts(n)
        for t in thoughts:
            print(f"  [{t.get('duration_ms', 0):.1f}ms] {t['purpose']}: {t['encoded'][:100]}")

    elif cmd == "stats":
        stats = thought.thought_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "patterns":
        for name, rules in thought._patterns.items():
            print(f"\n  Pattern: {name}")
            for r in rules:
                print(f"    {r.encode()}")

    elif cmd == "test":
        print("=== ThoughtProtocol Self-Test ===\n")

        # Test 1: Signal encoding
        sv = SignalVector()
        sv.set("sal", 0.85)
        sv.set("emo", {"approach": 0.6, "avoid": 0.1})
        encoded = sv.encode()
        print(f"1. Signal encoding: {encoded}")
        assert "sal=0.85" in encoded, "Signal encoding failed"
        print("   PASS\n")

        # Test 2: Decision rules
        frame = thought.frame("test_decision")
        frame.signal("sal", 0.8)
        frame.signal("emo", {"approach": 0.6, "avoid": 0.1})
        frame.decide("sal > 0.7", "execute", confidence=0.9)
        frame.decide("sal <= 0.3", "defer", confidence=0.8)
        result = frame.resolve()
        print(f"2. Decision: sal=0.8 → {result['action']} (conf={result['confidence']})")
        assert result["action"] == "execute", f"Expected execute, got {result['action']}"
        print("   PASS\n")

        # Test 3: Relation graph
        rg = RelationGraph()
        rg.add("task_a", "task_b", "similar_context", 0.9)
        rg.add("task_b", "task_c", "causal", 0.7)
        path = rg.strongest_path("task_a", "task_c")
        print(f"3. Relations: path A→C has {len(path)} hops: {rg.encode()}")
        assert len(path) == 2, f"Expected 2-hop path, got {len(path)}"
        print("   PASS\n")

        # Test 4: ThoughtScript eval
        result = thought.eval("@sal(0.9) ; @emo_bias(0.5) ; IF sal > 0.7 THEN execute")
        print(f"4. ThoughtScript: {result['resolution']['action']} "
              f"({result['duration_ms']:.1f}ms)")
        assert result["resolution"]["action"] == "execute"
        print("   PASS\n")

        # Test 5: Task decision
        decision = thought.task_decision(
            "Build internal protocol",
            salience=0.85,
            somatic_bias=0.3,
            spotlight_align=0.6
        )
        print(f"5. Task decision: {decision['action']} "
              f"(conf={decision['confidence']}, readiness={decision['signals'].get('readiness', 0):.2f})")
        print("   PASS\n")

        # Test 6: Cognitive state encoding
        state = thought.encode_state()
        print(f"6. State encoding: {state}")
        assert state.startswith("S["), "State encoding format wrong"
        print("   PASS\n")

        # Test 7: Pattern application
        frame2 = thought.frame("pattern_test")
        frame2.signal("sal", 0.9)
        frame2.signal("emo_bias", 0.2)
        thought.apply_pattern("urgent_task", frame2)
        result2 = frame2.resolve()
        print(f"7. Pattern 'urgent_task': {result2['action']} (conf={result2['confidence']})")
        assert result2["action"] == "execute_now"
        print("   PASS\n")

        # Test 8: AND/OR conditions
        frame3 = thought.frame("logic_test")
        frame3.signal("sal", 0.6)
        frame3.signal("emo_bias", 0.4)
        frame3.decide("sal > 0.5 AND emo_bias > 0.3", "go", confidence=0.8)
        frame3.decide("sal > 0.9 OR emo_bias > 0.9", "rush", confidence=0.9)
        result3 = frame3.resolve()
        print(f"8. Logic (AND/OR): sal=0.6, emo=0.4 → {result3['action']}")
        assert result3["action"] == "go", f"Expected 'go', got {result3['action']}"
        print("   PASS\n")

        # Stats
        stats = thought.thought_stats()
        print(f"Stats: {stats['total_frames']} frames logged, "
              f"avg {stats['avg_duration_ms']:.1f}ms")

        print("\n=== ALL TESTS PASSED ===")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

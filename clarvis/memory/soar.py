#!/usr/bin/env python3
"""
SOAR-Inspired Goal-Driven Cognition Engine

Implements core SOAR concepts adapted for Clarvis:

1. Goal Stack — hierarchical goals with push/pop, priority, and state tracking
2. Operator Proposal — multiple operators can be proposed for a goal
3. Operator Selection — conflict resolution via preferences (numeric + symbolic)
4. Operator Application — execute the selected operator
5. Impasse Detection — when no operator can be selected, create a sub-goal
6. Chunking — learn from impasse resolution to avoid future impasses

SOAR Cycle (adapted):
  Input → Propose → Decide → Apply → Output
  If impasse at Decide → push sub-goal → recurse

References:
  - Laird (2012) "The Soar Cognitive Architecture"
  - Laird, Newell, Rosenbloom (1987) "SOAR: An architecture for general intelligence"

Integration points:
  - episodic_memory.py: episodes inform operator preferences
  - procedural_memory.py: successful operator sequences become procedures
  - attention.py: goal changes broadcast to GWT spotlight
  - heartbeat_postflight.py: postflight calls soar.apply_outcome()

Usage:
    from soar_engine import soar
    soar.push_goal("Improve retrieval accuracy", source="episodic_synthesis")
    proposal = soar.propose_operators()
    selected = soar.select_operator()
    soar.apply_outcome(selected["id"], "success")
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os as _os
_WS = _os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DATA_DIR = Path(_WS) / "data" / "soar"
DATA_DIR.mkdir(parents=True, exist_ok=True)
GOAL_STACK_FILE = DATA_DIR / "goal_stack.json"
CHUNKS_FILE = DATA_DIR / "chunks.json"
HISTORY_FILE = DATA_DIR / "decision_history.jsonl"

# Impasse types (SOAR terminology)
IMPASSE_TIE = "tie"           # Multiple operators equally preferred
IMPASSE_CONFLICT = "conflict"  # Contradictory preferences
IMPASSE_NO_CHANGE = "no-change"  # No operators proposed
IMPASSE_REJECTION = "rejection"  # All operators rejected


class Goal:
    """A goal on the SOAR goal stack."""

    def __init__(self, name, source="manual", priority=0.5, parent_id=None,
                 context=None, goal_id=None):
        self.id = goal_id or f"goal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.name = name
        self.source = source
        self.priority = max(0.0, min(1.0, priority))
        self.parent_id = parent_id  # For sub-goals created by impasses
        self.context = context or {}
        self.status = "active"  # active, achieved, failed, suspended
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.operators_proposed = []
        self.operators_tried = []
        self.impasse = None
        self.resolution = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "priority": self.priority,
            "parent_id": self.parent_id,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at,
            "operators_proposed": self.operators_proposed,
            "operators_tried": self.operators_tried,
            "impasse": self.impasse,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, d):
        g = cls(
            name=d["name"],
            source=d.get("source", "loaded"),
            priority=d.get("priority", 0.5),
            parent_id=d.get("parent_id"),
            context=d.get("context", {}),
            goal_id=d["id"],
        )
        g.status = d.get("status", "active")
        g.created_at = d.get("created_at", g.created_at)
        g.operators_proposed = d.get("operators_proposed", [])
        g.operators_tried = d.get("operators_tried", [])
        g.impasse = d.get("impasse")
        g.resolution = d.get("resolution")
        return g


class Operator:
    """An operator proposed for achieving a goal."""

    def __init__(self, name, goal_id, preference=0.5, conditions=None,
                 actions=None, op_id=None):
        self.id = op_id or f"op_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.name = name
        self.goal_id = goal_id
        self.preference = max(0.0, min(1.0, preference))
        self.conditions = conditions or []   # Pre-conditions (descriptive)
        self.actions = actions or []          # Action steps
        self.status = "proposed"  # proposed, selected, applied, succeeded, failed

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "goal_id": self.goal_id,
            "preference": self.preference,
            "conditions": self.conditions,
            "actions": self.actions,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d):
        op = cls(
            name=d["name"],
            goal_id=d["goal_id"],
            preference=d.get("preference", 0.5),
            conditions=d.get("conditions", []),
            actions=d.get("actions", []),
            op_id=d["id"],
        )
        op.status = d.get("status", "proposed")
        return op


class SOAREngine:
    """
    SOAR-inspired goal-driven cognition engine.

    Maintains a goal stack, proposes/selects/applies operators,
    detects impasses, and learns chunks from resolutions.
    """

    def __init__(self):
        self.goal_stack = []  # List[Goal], last = top of stack
        self.chunks = []      # Learned impasse→resolution mappings
        self._load()

    def _load(self):
        """Load persisted state."""
        if GOAL_STACK_FILE.exists():
            try:
                data = json.loads(GOAL_STACK_FILE.read_text())
                self.goal_stack = [Goal.from_dict(g) for g in data.get("goals", [])]
            except (json.JSONDecodeError, KeyError):
                self.goal_stack = []
        if CHUNKS_FILE.exists():
            try:
                self.chunks = json.loads(CHUNKS_FILE.read_text())
            except (json.JSONDecodeError, KeyError):
                self.chunks = []

    def _save(self):
        """Persist goal stack."""
        data = {"goals": [g.to_dict() for g in self.goal_stack],
                "updated_at": datetime.now(timezone.utc).isoformat()}
        GOAL_STACK_FILE.write_text(json.dumps(data, indent=2))

    def _save_chunks(self):
        """Persist learned chunks."""
        CHUNKS_FILE.write_text(json.dumps(self.chunks[-500:], indent=2))

    def _log_decision(self, decision):
        """Append a decision to history (JSONL)."""
        decision["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(decision) + "\n")

    # ------------------------------------------------------------------
    # Goal Stack Operations
    # ------------------------------------------------------------------

    def push_goal(self, name, source="manual", priority=0.5, context=None,
                  parent_id=None):
        """Push a new goal onto the stack.

        Args:
            name: Goal description
            source: Where the goal came from (episodic_synthesis, user, impasse, etc.)
            priority: 0.0-1.0
            context: Additional context dict
            parent_id: Parent goal ID (for sub-goals)

        Returns:
            The created Goal
        """
        # Check for duplicate active goals
        for g in self.goal_stack:
            if g.name == name and g.status == "active":
                g.priority = max(g.priority, priority)
                self._save()
                return g

        goal = Goal(name, source=source, priority=priority,
                    parent_id=parent_id, context=context)
        self.goal_stack.append(goal)
        self._save()

        # Broadcast to attention
        try:
            from attention import attention
            attention.submit(
                f"SOAR goal pushed: {name}",
                source="soar_engine",
                importance=priority,
                relevance=0.7,
            )
        except Exception:
            pass

        return goal

    def pop_goal(self, status="achieved", resolution=None):
        """Pop the top goal from the stack.

        Args:
            status: How the goal ended (achieved, failed, suspended)
            resolution: Description of how it was resolved

        Returns:
            The popped Goal, or None
        """
        active = [g for g in self.goal_stack if g.status == "active"]
        if not active:
            return None

        goal = active[-1]
        goal.status = status
        goal.resolution = resolution
        self._save()

        self._log_decision({
            "type": "goal_resolved",
            "goal_id": goal.id,
            "goal_name": goal.name,
            "status": status,
            "resolution": resolution,
        })

        return goal

    def current_goal(self):
        """Get the current (top) active goal.

        Returns:
            Goal dict, or None if stack is empty
        """
        active = [g for g in self.goal_stack if g.status == "active"]
        if active:
            return active[-1].to_dict()
        return None

    def goal_stack_summary(self):
        """Get a summary of the goal stack."""
        active = [g for g in self.goal_stack if g.status == "active"]
        return {
            "depth": len(active),
            "goals": [{"id": g.id, "name": g.name, "priority": g.priority,
                        "source": g.source, "parent": g.parent_id}
                       for g in reversed(active)],
        }

    # ------------------------------------------------------------------
    # Operator Proposal & Selection (SOAR Decide Phase)
    # ------------------------------------------------------------------

    def propose_operators(self, goal_id=None):
        """Propose operators for the current goal using multiple knowledge sources.

        Gathers candidates from:
        1. Procedural memory (matching procedures)
        2. Episodic memory (past successes on similar goals)
        3. Learned chunks (impasse resolutions)

        Returns:
            List of Operator dicts, sorted by preference
        """
        goal = self._get_goal(goal_id)
        if not goal:
            return []

        operators = []

        # 1. Check procedural memory for matching procedures
        try:
            from procedural_memory import find_procedure
            proc = find_procedure(goal.name, threshold=1.0)
            if proc:
                op = Operator(
                    name=f"procedure:{proc['name']}",
                    goal_id=goal.id,
                    preference=min(0.9, 0.5 + proc["success_rate"] * 0.4),
                    conditions=[f"Matched procedure '{proc['name']}' (rate={proc['success_rate']:.0%})"],
                    actions=proc.get("steps", []),
                )
                operators.append(op)
        except Exception:
            pass

        # 2. Check episodic memory for similar past successes
        try:
            from episodic_memory import episodic
            similar = episodic.recall_similar(goal.name, n=3, use_spreading_activation=False)
            for ep in similar:
                if ep["outcome"] == "success":
                    pref = min(0.85, 0.4 + ep.get("activation", 0) * 0.1)
                    op = Operator(
                        name=f"episodic:{ep['task'][:60]}",
                        goal_id=goal.id,
                        preference=pref,
                        conditions=[f"Similar past success (activation={ep.get('activation', 0):.2f})"],
                        actions=ep.get("steps") or [ep["task"]],
                    )
                    operators.append(op)
        except Exception:
            pass

        # 3. Check learned chunks
        for chunk in self.chunks:
            if _text_overlap(goal.name, chunk.get("impasse_context", "")) > 0.3:
                op = Operator(
                    name=f"chunk:{chunk.get('resolution', 'unknown')[:60]}",
                    goal_id=goal.id,
                    preference=min(0.8, chunk.get("confidence", 0.5)),
                    conditions=["Learned chunk from impasse resolution"],
                    actions=chunk.get("actions", []),
                )
                operators.append(op)

        # 4. Default operator: attempt the goal directly
        if not operators:
            op = Operator(
                name=f"direct:{goal.name[:60]}",
                goal_id=goal.id,
                preference=0.3,
                conditions=["No specialized knowledge; attempt directly"],
                actions=[goal.name],
            )
            operators.append(op)

        # Sort by preference (highest first)
        operators.sort(key=lambda o: o.preference, reverse=True)

        # Store proposals on the goal
        goal.operators_proposed = [op.to_dict() for op in operators]
        self._save()

        return [op.to_dict() for op in operators]

    def select_operator(self, goal_id=None):
        """Select the best operator using SOAR-style conflict resolution.

        Selection rules (in priority order):
        1. If one operator dominates (preference >> others), select it
        2. If tie (top operators within 0.05), detect TIE impasse
        3. If no operators, detect NO-CHANGE impasse

        Returns:
            Selected operator dict, or impasse dict
        """
        goal = self._get_goal(goal_id)
        if not goal:
            return {"impasse": IMPASSE_NO_CHANGE, "reason": "No active goal"}

        proposals = goal.operators_proposed
        if not proposals:
            proposals = self.propose_operators(goal.id)

        if not proposals:
            # NO-CHANGE impasse
            impasse = self._handle_impasse(goal, IMPASSE_NO_CHANGE)
            return impasse

        # Sort by preference
        sorted_ops = sorted(proposals, key=lambda o: o.get("preference", 0), reverse=True)
        best = sorted_ops[0]

        # Check for tie (top 2 within 0.05 of each other)
        if len(sorted_ops) >= 2:
            second = sorted_ops[1]
            gap = best.get("preference", 0) - second.get("preference", 0)
            if gap < 0.05:
                # TIE impasse — but we still pick the first one after logging
                self._log_decision({
                    "type": "tie_resolved",
                    "goal_id": goal.id,
                    "tied_operators": [best["name"], second["name"]],
                    "gap": round(gap, 3),
                })

        # Select the best
        best["status"] = "selected"
        goal.operators_tried.append(best["id"])
        self._save()

        self._log_decision({
            "type": "operator_selected",
            "goal_id": goal.id,
            "operator_id": best["id"],
            "operator_name": best["name"],
            "preference": best.get("preference", 0),
            "alternatives": len(sorted_ops) - 1,
        })

        return best

    def apply_outcome(self, operator_id, outcome, goal_id=None, details=None):
        """Record the outcome of applying an operator.

        Args:
            operator_id: The operator that was applied
            outcome: "success" or "failure"
            goal_id: Optional goal ID (uses current if not specified)
            details: Optional details string

        Returns:
            Result dict with goal status update
        """
        goal = self._get_goal(goal_id)
        if not goal:
            return {"error": "No active goal"}

        # Find the operator in proposals
        op_data = None
        for op in goal.operators_proposed:
            if op["id"] == operator_id:
                op_data = op
                break

        if op_data:
            op_data["status"] = "succeeded" if outcome == "success" else "failed"

        self._log_decision({
            "type": "operator_outcome",
            "goal_id": goal.id,
            "operator_id": operator_id,
            "outcome": outcome,
            "details": details,
        })

        if outcome == "success":
            # Goal achieved — pop it
            self.pop_goal("achieved", resolution=f"Operator {operator_id} succeeded")
            self._save()
            return {"status": "goal_achieved", "goal": goal.to_dict()}
        else:
            # Operator failed — check if we have alternatives
            tried = set(goal.operators_tried)
            untried = [op for op in goal.operators_proposed
                       if op["id"] not in tried]
            if untried:
                return {"status": "retry_available",
                        "remaining_operators": len(untried)}
            else:
                # All operators exhausted — impasse
                impasse = self._handle_impasse(goal, IMPASSE_REJECTION)
                return impasse

    # ------------------------------------------------------------------
    # Impasse Detection & Resolution
    # ------------------------------------------------------------------

    def _handle_impasse(self, goal, impasse_type):
        """Handle a SOAR impasse by creating a sub-goal.

        In SOAR, impasses trigger automatic sub-goaling: the system
        creates a sub-goal to resolve the impasse, which may itself
        lead to further impasses (recursive).

        Here we create a sub-goal and log the impasse for chunking.
        """
        goal.impasse = {
            "type": impasse_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

        # Create a sub-goal to resolve the impasse
        sub_name = f"Resolve {impasse_type} impasse for: {goal.name[:80]}"
        sub_goal = self.push_goal(
            name=sub_name,
            source="impasse",
            priority=min(1.0, goal.priority + 0.1),
            parent_id=goal.id,
            context={"impasse_type": impasse_type, "original_goal": goal.name},
        )

        self._log_decision({
            "type": "impasse_detected",
            "goal_id": goal.id,
            "impasse_type": impasse_type,
            "sub_goal_id": sub_goal.id,
        })

        return {
            "impasse": impasse_type,
            "goal_id": goal.id,
            "sub_goal_id": sub_goal.id,
            "reason": f"Impasse ({impasse_type}) on goal: {goal.name[:60]}",
        }

    def learn_chunk(self, impasse_goal_id, resolution_description, actions=None,
                    confidence=0.5):
        """Learn a chunk from impasse resolution (SOAR chunking).

        When an impasse sub-goal is resolved, the system learns the
        resolution as a 'chunk' — a compiled rule that can shortcut
        the impasse in the future.

        Args:
            impasse_goal_id: The sub-goal that resolved the impasse
            resolution_description: What resolved it
            actions: List of action steps that resolved it
            confidence: How confident we are in this chunk
        """
        goal = None
        for g in self.goal_stack:
            if g.id == impasse_goal_id:
                goal = g
                break

        parent_name = ""
        if goal and goal.parent_id:
            for g in self.goal_stack:
                if g.id == goal.parent_id:
                    parent_name = g.name
                    break

        chunk = {
            "id": f"chunk_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "impasse_context": parent_name or (goal.name if goal else "unknown"),
            "impasse_type": goal.context.get("impasse_type", "unknown") if goal else "unknown",
            "resolution": resolution_description,
            "actions": actions or [],
            "confidence": round(confidence, 2),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "use_count": 0,
        }
        self.chunks.append(chunk)
        self._save_chunks()

        self._log_decision({
            "type": "chunk_learned",
            "chunk_id": chunk["id"],
            "impasse_context": chunk["impasse_context"][:80],
            "resolution": resolution_description[:80],
        })

        # Also store in brain for semantic retrieval
        try:
            from brain import brain
            brain.store(
                f"SOAR chunk: When impasse on '{chunk['impasse_context'][:100]}', "
                f"resolve by: {resolution_description[:200]}",
                collection="clarvis-learnings",
                importance=0.7,
                tags=["soar", "chunk", "impasse-resolution"],
                source="soar_engine",
            )
        except Exception:
            pass

        return chunk

    # ------------------------------------------------------------------
    # Goal-Task Integration
    # ------------------------------------------------------------------

    def align_task(self, task_text):
        """Check if a task aligns with current goals and boost if so.

        Called during preflight to connect autonomous tasks to the goal stack.

        Returns:
            Dict with alignment info (goal_id, relevance, boost)
        """
        current = self.current_goal()
        if not current:
            return {"aligned": False}

        overlap = _text_overlap(task_text, current["name"])
        if overlap > 0.2:
            return {
                "aligned": True,
                "goal_id": current["id"],
                "goal_name": current["name"],
                "relevance": round(overlap, 2),
                "boost": round(min(0.3, overlap * 0.5), 2),
            }

        # Check deeper in stack
        for g in reversed([g for g in self.goal_stack if g.status == "active"]):
            overlap = _text_overlap(task_text, g.name)
            if overlap > 0.2:
                return {
                    "aligned": True,
                    "goal_id": g.id,
                    "goal_name": g.name,
                    "relevance": round(overlap, 2),
                    "boost": round(min(0.2, overlap * 0.3), 2),
                }

        return {"aligned": False}

    def ingest_goals_from_synthesis(self, synthesis_result):
        """Import goals generated by episodic_memory.synthesize().

        Converts synthesis goals into SOAR goals on the stack.
        """
        goals_created = []
        for goal_name in synthesis_result.get("goals_generated", []):
            g = self.push_goal(
                name=goal_name,
                source="episodic_synthesis",
                priority=0.6,
                context={"from_synthesis": True},
            )
            goals_created.append(g.to_dict())
        return goals_created

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_goal(self, goal_id=None):
        """Get a goal by ID, or the current top goal."""
        if goal_id:
            for g in self.goal_stack:
                if g.id == goal_id and g.status == "active":
                    return g
            return None
        active = [g for g in self.goal_stack if g.status == "active"]
        return active[-1] if active else None

    def cleanup(self, max_resolved=100):
        """Remove old resolved goals to prevent unbounded growth."""
        active = [g for g in self.goal_stack if g.status == "active"]
        resolved = [g for g in self.goal_stack if g.status != "active"]
        # Keep only most recent resolved goals
        resolved = resolved[-max_resolved:]
        self.goal_stack = resolved + active
        self._save()
        return len(self.goal_stack)

    def stats(self):
        """Get SOAR engine statistics."""
        active = [g for g in self.goal_stack if g.status == "active"]
        achieved = [g for g in self.goal_stack if g.status == "achieved"]
        failed = [g for g in self.goal_stack if g.status == "failed"]

        return {
            "active_goals": len(active),
            "achieved_goals": len(achieved),
            "failed_goals": len(failed),
            "total_goals": len(self.goal_stack),
            "chunks_learned": len(self.chunks),
            "stack_depth": len(active),
            "current_goal": active[-1].name if active else None,
            "sources": _count_field(self.goal_stack, "source"),
        }

    def save(self):
        """Public save method."""
        self._save()


def _text_overlap(a, b):
    """Compute Jaccard word overlap between two strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _count_field(items, field):
    """Count occurrences of each value in a field."""
    counts = {}
    for item in items:
        val = getattr(item, field, None) or item.get(field, "unknown") if isinstance(item, dict) else getattr(item, field, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


# Singleton
_soar = None

def get_soar():
    global _soar
    if _soar is None:
        _soar = SOAREngine()
    return _soar

class _LazySoar:
    """Lazy proxy — defers SOAREngine init until first access."""
    def __getattr__(self, name):
        real = get_soar()
        global soar
        soar = real
        return getattr(real, name)
    def __repr__(self):
        return "<LazySoar (not yet initialized)>"

soar = _LazySoar()


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: soar_engine.py <command> [args]")
        print("Commands:")
        print("  push <goal> [priority] [source]  - Push a goal")
        print("  pop [status]                     - Pop top goal")
        print("  current                          - Show current goal")
        print("  stack                            - Show goal stack")
        print("  propose                          - Propose operators for current goal")
        print("  select                           - Select best operator")
        print("  outcome <op_id> <success|failure> - Record operator outcome")
        print("  align <task>                     - Check task-goal alignment")
        print("  chunks                           - List learned chunks")
        print("  stats                            - Show engine stats")
        print("  cleanup                          - Remove old resolved goals")
        sys.exit(0)

    cmd = sys.argv[1]
    s = get_soar()

    if cmd == "push":
        name = sys.argv[2] if len(sys.argv) > 2 else "unnamed goal"
        priority = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        source = sys.argv[4] if len(sys.argv) > 4 else "cli"
        g = s.push_goal(name, source=source, priority=priority)
        print(f"Pushed: {g.id} — {g.name} (priority={g.priority})")

    elif cmd == "pop":
        status = sys.argv[2] if len(sys.argv) > 2 else "achieved"
        g = s.pop_goal(status=status)
        if g:
            print(f"Popped: {g.id} — {g.name} ({g.status})")
        else:
            print("No active goal to pop")

    elif cmd == "current":
        c = s.current_goal()
        if c:
            print(json.dumps(c, indent=2))
        else:
            print("No active goal")

    elif cmd == "stack":
        summary = s.goal_stack_summary()
        print(f"Goal Stack (depth={summary['depth']}):")
        for i, g in enumerate(summary["goals"]):
            indent = "  " * i
            parent = f" (sub-goal of {g['parent'][:20]})" if g["parent"] else ""
            print(f"  {indent}[{g['priority']:.1f}] {g['name'][:70]}{parent}")

    elif cmd == "propose":
        ops = s.propose_operators()
        if not ops:
            print("No operators proposed (no active goal?)")
        else:
            print(f"Proposed {len(ops)} operators:")
            for op in ops:
                print(f"  [{op['preference']:.2f}] {op['name'][:70]}")
                if op.get("conditions"):
                    for c in op["conditions"]:
                        print(f"         {c[:80]}")

    elif cmd == "select":
        result = s.select_operator()
        if "impasse" in result:
            print(f"IMPASSE: {result['impasse']} — {result.get('reason', '')}")
        else:
            print(f"Selected: [{result.get('preference', 0):.2f}] {result['name'][:70]}")

    elif cmd == "outcome":
        op_id = sys.argv[2] if len(sys.argv) > 2 else ""
        outcome = sys.argv[3] if len(sys.argv) > 3 else "success"
        result = s.apply_outcome(op_id, outcome)
        print(json.dumps(result, indent=2))

    elif cmd == "align":
        task = sys.argv[2] if len(sys.argv) > 2 else ""
        result = s.align_task(task)
        print(json.dumps(result, indent=2))

    elif cmd == "chunks":
        if not s.chunks:
            print("No chunks learned yet")
        else:
            for c in s.chunks:
                print(f"  [{c['id']}] conf={c['confidence']:.2f} uses={c['use_count']}")
                print(f"    Context: {c['impasse_context'][:60]}")
                print(f"    Resolution: {c['resolution'][:60]}")

    elif cmd == "stats":
        print(json.dumps(s.stats(), indent=2))

    elif cmd == "cleanup":
        remaining = s.cleanup()
        print(f"Cleanup done. {remaining} goals remaining.")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

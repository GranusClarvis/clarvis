"""
Self-Model — Meta-cognitive capability tracking.

Implements a self-model based on Higher-Order Theories of consciousness:
- Awareness levels (operational -> reflective -> meta)
- Cognitive state tracking
- Working memory (GWT-inspired spotlight)
- Meta-thoughts (thinking about thinking)
- Scored capability assessment framework

Backend-agnostic: state is returned as dicts for you to persist however you like.

Usage:
    from clarvis_consciousness.self_model import SelfModel, CapabilityAssessor

    model = SelfModel()
    model.add_capability("Code execution")
    model.think_about_thinking("Am I improving at reasoning?")
    model.set_awareness_level("reflective")

    # Scored capability assessment
    assessor = CapabilityAssessor()
    assessor.register("memory", my_memory_scorer)
    results = assessor.assess_all()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


VALID_AWARENESS_LEVELS = ("operational", "reflective", "meta")
VALID_COGNITIVE_STATES = ("active", "reflective", "idle", "processing")

AssessorFn = Callable[[], Tuple[float, List[str]]]  # () -> (score, evidence_list)


@dataclass
class MetaCognitiveState:
    """Tracks meta-cognitive state: awareness, working memory, meta-thoughts."""

    awareness_level: str = "operational"
    cognitive_state: str = "active"
    working_memory: List[Dict[str, Any]] = field(default_factory=list)
    meta_thoughts: List[Dict[str, Any]] = field(default_factory=list)
    user_model: Dict[str, Any] = field(default_factory=dict)
    attention_shifts: int = 0
    working_memory_capacity: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "awareness_level": self.awareness_level,
            "cognitive_state": self.cognitive_state,
            "working_memory": self.working_memory,
            "meta_thoughts": self.meta_thoughts,
            "user_model": self.user_model,
            "attention_shifts": self.attention_shifts,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MetaCognitiveState":
        return cls(
            awareness_level=d.get("awareness_level", "operational"),
            cognitive_state=d.get("cognitive_state", "active"),
            working_memory=d.get("working_memory", []),
            meta_thoughts=d.get("meta_thoughts", []),
            user_model=d.get("user_model", {}),
            attention_shifts=d.get("attention_shifts", 0),
        )


class SelfModel:
    """Internal world model tracking capabilities, strengths, weaknesses.

    Expanded with meta-cognition (Higher-Order Theories of consciousness).
    """

    def __init__(self):
        self.capabilities: List[str] = []
        self.strengths: List[str] = []
        self.weaknesses: List[str] = []
        self.trajectory: List[Dict[str, Any]] = []
        self.meta = MetaCognitiveState()
        self.last_updated: Optional[str] = None

    # === Core Model ===

    def add_capability(self, capability: str):
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def add_strength(self, strength: str):
        if strength not in self.strengths:
            self.strengths.append(strength)

    def add_weakness(self, weakness: str):
        if weakness not in self.weaknesses:
            self.weaknesses.append(weakness)

    def log_trajectory(self, event: str, status: str = "logged"):
        self.trajectory.append({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "event": event,
            "status": status,
        })
        self.last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # === Meta-Cognition ===

    def set_awareness_level(self, level: str) -> str:
        """Set awareness level. Returns previous level."""
        if level not in VALID_AWARENESS_LEVELS:
            raise ValueError(f"Invalid level: {level}. Use: {VALID_AWARENESS_LEVELS}")
        old = self.meta.awareness_level
        self.meta.awareness_level = level
        return old

    def set_cognitive_state(self, state: str) -> str:
        """Set cognitive state. Returns previous state."""
        if state not in VALID_COGNITIVE_STATES:
            raise ValueError(f"Invalid state: {state}. Use: {VALID_COGNITIVE_STATES}")
        old = self.meta.cognitive_state
        self.meta.cognitive_state = state
        return old

    def add_to_working_memory(self, item: str):
        """Add item to GWT-inspired working memory spotlight."""
        self.meta.working_memory.append({
            "item": item,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.meta.working_memory = self.meta.working_memory[-self.meta.working_memory_capacity:]
        self.meta.attention_shifts += 1

    def clear_working_memory(self):
        self.meta.working_memory = []

    def think_about_thinking(self, thought: str):
        """Record a meta-cognitive thought."""
        self.meta.meta_thoughts.append({
            "thought": thought,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "awareness_level": self.meta.awareness_level,
        })
        self.meta.meta_thoughts = self.meta.meta_thoughts[-20:]

    def update_user_model(self, **kwargs):
        """Update theory of mind about user."""
        self.meta.user_model.update(kwargs)
        self.meta.user_model["last_update"] = datetime.now(timezone.utc).isoformat()

    # === Serialization ===

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "trajectory": self.trajectory,
            "meta": self.meta.to_dict(),
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SelfModel":
        model = cls()
        model.capabilities = d.get("capabilities", [])
        model.strengths = d.get("strengths", [])
        model.weaknesses = d.get("weaknesses", [])
        model.trajectory = d.get("trajectory", [])
        model.last_updated = d.get("last_updated")
        if "meta" in d:
            model.meta = MetaCognitiveState.from_dict(d["meta"])
        return model

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Self-Model (updated: {self.last_updated or 'never'})",
            f"  Capabilities: {len(self.capabilities)}",
            f"  Strengths: {len(self.strengths)}",
            f"  Weaknesses: {len(self.weaknesses)}",
            f"  Trajectory events: {len(self.trajectory)}",
            f"  Awareness: {self.meta.awareness_level}",
            f"  Cognitive state: {self.meta.cognitive_state}",
            f"  Working memory: {len(self.meta.working_memory)} items",
            f"  Meta-thoughts: {len(self.meta.meta_thoughts)}",
            f"  Attention shifts: {self.meta.attention_shifts}",
        ]
        return "\n".join(lines)


class CapabilityAssessor:
    """Pluggable scored capability assessment framework.

    Register domain assessors, then run assess_all() to get scored results.
    Each assessor returns (score: 0-1, evidence: list[str]).
    """

    def __init__(self, remediation_threshold: float = 0.4):
        self.domains: Dict[str, Dict[str, Any]] = {}
        self.assessors: Dict[str, AssessorFn] = {}
        self.history: List[Dict[str, Any]] = []
        self.remediation_threshold = remediation_threshold
        self.max_history = 90

    def register(
        self,
        domain: str,
        assessor: AssessorFn,
        label: str = "",
        description: str = "",
        remediation_template: str = "",
    ):
        """Register a capability domain assessor."""
        self.domains[domain] = {
            "label": label or domain,
            "description": description,
            "remediation_template": remediation_template,
        }
        self.assessors[domain] = assessor

    def assess(self, domain: str) -> Dict[str, Any]:
        """Run assessment for a single domain."""
        if domain not in self.assessors:
            raise KeyError(f"Unknown domain: {domain}")
        score, evidence = self.assessors[domain]()
        return {
            "score": round(max(0.0, min(1.0, score)), 2),
            "evidence": evidence,
            "label": self.domains[domain]["label"],
        }

    def assess_all(self) -> Dict[str, Dict[str, Any]]:
        """Run all assessments."""
        return {domain: self.assess(domain) for domain in self.assessors}

    def snapshot(self) -> Dict[str, Any]:
        """Run assessment and save snapshot to history."""
        results = self.assess_all()
        snap = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scores": {d: results[d]["score"] for d in results},
            "evidence": {d: results[d]["evidence"] for d in results},
        }
        self.history.append(snap)
        self.history = self.history[-self.max_history:]
        return snap

    def check_regressions(
        self,
        current: Optional[Dict[str, Dict[str, Any]]] = None,
        threshold: float = 0.10,
    ) -> List[str]:
        """Detect regressions compared to last snapshot.

        Returns list of alert strings for domains that dropped > threshold.
        """
        if len(self.history) < 2:
            return []

        if current is None:
            current = self.assess_all()

        prev = self.history[-2] if len(self.history) >= 2 else self.history[-1]
        alerts = []

        for domain, data in current.items():
            prev_score = prev.get("scores", {}).get(domain, 0)
            if prev_score == 0:
                continue
            pct_drop = (prev_score - data["score"]) / prev_score
            if pct_drop > threshold:
                alerts.append(
                    f"REGRESSION: {data['label']} dropped {pct_drop:.0%} "
                    f"({prev_score:.2f} -> {data['score']:.2f})"
                )

        return alerts

    def remediation_tasks(
        self,
        current: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[str]:
        """Generate tasks for domains below remediation threshold."""
        if current is None:
            current = self.assess_all()

        tasks = []
        for domain, data in current.items():
            if data["score"] >= self.remediation_threshold:
                continue
            template = self.domains[domain].get("remediation_template", "")
            if template:
                tasks.append(template.format(score=data["score"]))
            else:
                tasks.append(
                    f"Improve {data['label']} -- score {data['score']:.2f} "
                    f"below threshold {self.remediation_threshold}"
                )
        return tasks

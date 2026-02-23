"""
14-Dimension Prompt Scorer for model routing.

Analyzes a prompt across 14 orthogonal dimensions to produce a feature vector
that drives model selection. Each dimension yields a score in [-1, 1].

Dimensions:
  1. code_generation   — implementation, coding, scripting
  2. file_editing      — modify existing files, integrate
  3. multi_step        — sequential workflows, pipelines
  4. reasoning_depth   — analysis, evaluation, design
  5. system_ops        — deploy, configure, infrastructure
  6. creative          — brainstorm, invent, novel
  7. task_length       — word count as complexity proxy
  8. agentic           — run, execute, spawn, fetch
  9. simplicity        — inverse: simple queries penalize complexity
 10. domain_depth      — specialized domains (quantum, genomics, etc.)
 11. context_size      — estimated input token load
 12. output_length     — expected output length (long-form vs one-liner)
 13. safety_risk       — content that needs careful guardrails
 14. latency_need      — urgency/interactive vs batch
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DimensionConfig:
    """Configuration for a single scoring dimension."""
    weight: float
    positive: List[str] = field(default_factory=list)
    negative: List[str] = field(default_factory=list)
    # If True, score is computed dynamically (not keyword-based)
    dynamic: bool = False


# === DEFAULT 14 DIMENSIONS ===

DEFAULT_DIMENSIONS: Dict[str, DimensionConfig] = {
    "code_generation": DimensionConfig(
        weight=0.15,
        positive=[
            "implement", "create script", "write function", "build module",
            "code", "class ", "def ", "import ", "refactor", "debug",
            "fix bug", "unit test", "integration test", "compile", "transpile",
        ],
        negative=["check", "read", "list", "count", "verify", "status"],
    ),
    "file_editing": DimensionConfig(
        weight=0.12,
        positive=[
            "edit", "modify", "update file", "change", "wire into",
            "integrate", "add to script", ".py", ".sh", ".json", ".md",
            "patch", "merge", "rebase",
        ],
        negative=["summarize", "report", "measure"],
    ),
    "multi_step": DimensionConfig(
        weight=0.10,
        positive=[
            "first", "then", "step 1", "step 2", "and then",
            "pipeline", "workflow", "sequence", "chain",
            "followed by", "after that", "finally",
        ],
        negative=[],
    ),
    "reasoning_depth": DimensionConfig(
        weight=0.12,
        positive=[
            "analyze", "evaluate", "compare", "design", "architect",
            "trade-off", "strategy", "optimize", "prove", "derive",
            "why does", "explain how", "reason about", "think through",
        ],
        negative=["simple", "quick", "just", "only"],
    ),
    "system_ops": DimensionConfig(
        weight=0.06,
        positive=[
            "deploy", "install", "configure", "cron", "systemd",
            "permission", "upgrade", "migrate", "docker", "kubernetes",
        ],
        negative=[],
    ),
    "creative": DimensionConfig(
        weight=0.05,
        positive=["brainstorm", "novel", "creative", "invent", "design new",
                   "imagine", "generate ideas", "story", "write a"],
        negative=[],
    ),
    "task_length": DimensionConfig(
        weight=0.05,
        positive=[],
        negative=[],
        dynamic=True,
    ),
    "agentic": DimensionConfig(
        weight=0.07,
        positive=[
            "run", "execute", "spawn", "invoke", "call",
            "fetch", "download", "upload", "push", "pull",
            "search the web", "browse",
        ],
        negative=[],
    ),
    "simplicity": DimensionConfig(
        weight=0.05,
        positive=[],
        negative=[
            "what is", "how many", "show me", "tell me", "define",
            "hello", "status", "check if", "yes or no", "true or false",
        ],
    ),
    "domain_depth": DimensionConfig(
        weight=0.04,
        positive=[
            "quantum", "fpga", "genomics", "neural network", "transformer",
            "attention mechanism", "bayesian", "differential equation",
            "category theory", "compiler", "kernel", "assembly",
        ],
        negative=[],
    ),
    "context_size": DimensionConfig(
        weight=0.06,
        positive=[],
        negative=[],
        dynamic=True,
    ),
    "output_length": DimensionConfig(
        weight=0.05,
        positive=[
            "write a full", "generate a complete", "produce a detailed",
            "comprehensive", "thorough", "in-depth", "essay", "report",
            "entire file", "whole module",
        ],
        negative=[
            "one word", "yes or no", "brief", "short", "tl;dr", "summarize",
            "one-liner", "quick answer",
        ],
    ),
    "safety_risk": DimensionConfig(
        weight=0.04,
        positive=[
            "user-facing", "production", "security", "authentication",
            "payment", "medical", "legal", "compliance", "pii",
            "sensitive", "confidential",
        ],
        negative=[],
    ),
    "latency_need": DimensionConfig(
        weight=0.04,
        positive=[],
        negative=[
            "real-time", "interactive", "chat", "autocomplete",
            "streaming", "instant", "fast", "quick response",
        ],
        dynamic=False,  # Negative = needs low latency = prefer fast model
    ),
}


@dataclass
class ScorerResult:
    """Output of the 14-dimension scorer."""
    dimensions: Dict[str, float]   # dimension_name -> score [-1, 1]
    composite: float               # Weighted composite [0, 1]
    vector: List[float]            # 14-element feature vector (ordered)

    def to_dict(self) -> dict:
        return {
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "composite": round(self.composite, 4),
            "vector": [round(v, 4) for v in self.vector],
        }


class PromptScorer:
    """Scores prompts across 14 dimensions for model routing.

    Each dimension produces a signal in [-1, 1]. The composite score
    normalizes the weighted sum to [0, 1] where higher = more complex/capable
    model needed.

    Args:
        dimensions: Custom dimension configs. Defaults to 14-dim standard.

    Example:
        scorer = PromptScorer()
        result = scorer.score("Implement a Redis caching layer with TTL")
        print(result.composite)     # ~0.65 (complex)
        print(result.dimensions)    # Per-dimension breakdown
        print(result.vector)        # 14-float feature vector
    """

    def __init__(self, dimensions: Optional[Dict[str, DimensionConfig]] = None):
        self.dimensions = dimensions or DEFAULT_DIMENSIONS
        self._dim_order = list(self.dimensions.keys())

    @property
    def dimension_names(self) -> List[str]:
        return list(self._dim_order)

    def score(self, prompt: str, context: str = "") -> ScorerResult:
        """Score a prompt across all 14 dimensions.

        Args:
            prompt: The user prompt / task description.
            context: Optional additional context (system prompt, history).

        Returns:
            ScorerResult with per-dimension scores, composite, and feature vector.
        """
        text = f"{prompt} {context}".strip()
        text_lower = text.lower()
        word_count = len(text.split())

        dim_scores: Dict[str, float] = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for name, config in self.dimensions.items():
            if name == "task_length":
                raw = self._score_task_length(word_count)
            elif name == "context_size":
                raw = self._score_context_size(len(text))
            else:
                raw = self._score_keywords(text_lower, config)

            dim_scores[name] = raw
            weighted_sum += raw * config.weight
            total_weight += config.weight

        # Normalize to [0, 1]
        composite = (weighted_sum / max(total_weight, 0.01) + 1.0) / 2.0
        composite = max(0.0, min(1.0, composite))

        vector = [dim_scores[name] for name in self._dim_order]

        return ScorerResult(
            dimensions=dim_scores,
            composite=composite,
            vector=vector,
        )

    @staticmethod
    def _score_keywords(text_lower: str, config: DimensionConfig) -> float:
        """Score based on positive/negative keyword presence. Returns [-1, 1]."""
        pos = sum(1 for kw in config.positive if kw.lower() in text_lower)
        neg = sum(1 for kw in config.negative if kw.lower() in text_lower)
        if pos + neg == 0:
            return 0.0
        raw = (pos - neg) / max(pos + neg, 1)
        return max(-1.0, min(1.0, raw))

    @staticmethod
    def _score_task_length(word_count: int) -> float:
        """Longer prompts generally need more capable models."""
        if word_count < 8:
            return -0.5
        elif word_count < 20:
            return 0.0
        elif word_count < 50:
            return 0.3
        elif word_count < 150:
            return 0.5
        else:
            return 0.7

    @staticmethod
    def _score_context_size(char_count: int) -> float:
        """More context = potentially needs larger context window or stronger model."""
        if char_count < 200:
            return -0.3
        elif char_count < 1000:
            return 0.0
        elif char_count < 5000:
            return 0.3
        elif char_count < 20000:
            return 0.5
        else:
            return 0.8

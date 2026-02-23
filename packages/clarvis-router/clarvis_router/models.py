"""
Model registry and capability profiles for ClarvisRouter.

Each model has a capability profile — a 14-dimension vector describing what
it's good at, plus metadata (cost, latency, context window, provider).

The router matches prompt feature vectors against model capability profiles
to pick the best model for each request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelProfile:
    """Capability profile for a single model.

    Attributes:
        model_id: OpenRouter-compatible model ID (e.g. "anthropic/claude-sonnet-4-6")
        display_name: Human-readable name
        capabilities: 14-element vector — how well this model handles each dimension
                      Values in [0, 1]: 0 = poor, 1 = excellent
        cost_per_1m_input: USD per 1M input tokens
        cost_per_1m_output: USD per 1M output tokens
        context_window: Max context in tokens
        avg_latency_ms: Typical first-token latency
        provider: "anthropic", "google", "openrouter", "local", etc.
        tags: Freeform tags for filtering ("fast", "cheap", "reasoning", etc.)
    """
    model_id: str
    display_name: str
    capabilities: List[float]  # 14 elements, matching dimension order
    cost_per_1m_input: float
    cost_per_1m_output: float
    context_window: int = 200_000
    avg_latency_ms: int = 1000
    provider: str = "openrouter"
    tags: List[str] = field(default_factory=list)

    def cost_score(self) -> float:
        """Normalized cost score [0, 1] where 0 = free, 1 = most expensive."""
        # Log-scale: $0 = 0, $15/1M = ~1.0
        blended = self.cost_per_1m_input * 0.6 + self.cost_per_1m_output * 0.4
        if blended <= 0:
            return 0.0
        import math
        return min(1.0, math.log1p(blended) / math.log1p(75.0))

    def latency_score(self) -> float:
        """Normalized latency score [0, 1] where 0 = instant, 1 = slow."""
        if self.avg_latency_ms <= 100:
            return 0.0
        if self.avg_latency_ms >= 10000:
            return 1.0
        return min(1.0, self.avg_latency_ms / 10000.0)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "cost_per_1m_input": self.cost_per_1m_input,
            "cost_per_1m_output": self.cost_per_1m_output,
            "context_window": self.context_window,
            "avg_latency_ms": self.avg_latency_ms,
            "provider": self.provider,
            "tags": self.tags,
        }


# Dimension order (must match scorer.py):
# 0=code_generation 1=file_editing 2=multi_step 3=reasoning_depth
# 4=system_ops 5=creative 6=task_length 7=agentic
# 8=simplicity 9=domain_depth 10=context_size 11=output_length
# 12=safety_risk 13=latency_need

DEFAULT_MODELS: Dict[str, ModelProfile] = {
    # === CLAUDE FAMILY ===
    "anthropic/claude-opus-4-6": ModelProfile(
        model_id="anthropic/claude-opus-4-6",
        display_name="Claude Opus 4.6",
        capabilities=[
            0.98,  # code_generation — top-tier coding
            0.95,  # file_editing
            0.95,  # multi_step
            0.99,  # reasoning_depth — best reasoning
            0.90,  # system_ops
            0.95,  # creative
            0.90,  # task_length — handles complex prompts
            0.95,  # agentic
            0.70,  # simplicity — overkill for simple
            0.98,  # domain_depth — deepest knowledge
            0.90,  # context_size — 200k
            0.95,  # output_length — can write extensive
            0.95,  # safety_risk — most careful
            0.30,  # latency_need — slower
        ],
        cost_per_1m_input=15.0,
        cost_per_1m_output=75.0,
        context_window=200_000,
        avg_latency_ms=3000,
        provider="anthropic",
        tags=["reasoning", "coding", "premium"],
    ),
    "anthropic/claude-sonnet-4-6": ModelProfile(
        model_id="anthropic/claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        capabilities=[
            0.92,  # code_generation
            0.90,  # file_editing
            0.88,  # multi_step
            0.90,  # reasoning_depth
            0.85,  # system_ops
            0.88,  # creative
            0.85,  # task_length
            0.90,  # agentic
            0.80,  # simplicity
            0.88,  # domain_depth
            0.90,  # context_size — 200k
            0.90,  # output_length
            0.90,  # safety_risk
            0.55,  # latency_need — medium speed
        ],
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        context_window=200_000,
        avg_latency_ms=1500,
        provider="anthropic",
        tags=["balanced", "coding", "fast"],
    ),
    "anthropic/claude-haiku-4-5": ModelProfile(
        model_id="anthropic/claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        capabilities=[
            0.75,  # code_generation
            0.70,  # file_editing
            0.65,  # multi_step
            0.70,  # reasoning_depth
            0.65,  # system_ops
            0.72,  # creative
            0.60,  # task_length
            0.70,  # agentic
            0.95,  # simplicity — great for simple tasks
            0.60,  # domain_depth
            0.85,  # context_size — 200k
            0.70,  # output_length
            0.80,  # safety_risk
            0.85,  # latency_need — fast
        ],
        cost_per_1m_input=0.80,
        cost_per_1m_output=4.0,
        context_window=200_000,
        avg_latency_ms=500,
        provider="anthropic",
        tags=["fast", "cheap", "simple"],
    ),

    # === GEMINI ===
    "google/gemini-2.0-flash": ModelProfile(
        model_id="google/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        capabilities=[
            0.65,  # code_generation
            0.55,  # file_editing
            0.55,  # multi_step
            0.60,  # reasoning_depth
            0.50,  # system_ops
            0.65,  # creative
            0.50,  # task_length
            0.55,  # agentic
            0.95,  # simplicity — excellent for simple
            0.50,  # domain_depth
            0.80,  # context_size — 1M
            0.60,  # output_length
            0.60,  # safety_risk
            0.95,  # latency_need — very fast
        ],
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        context_window=1_000_000,
        avg_latency_ms=200,
        provider="google",
        tags=["free", "fast", "simple"],
    ),
    "google/gemini-2.5-pro": ModelProfile(
        model_id="google/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        capabilities=[
            0.85,  # code_generation
            0.78,  # file_editing
            0.80,  # multi_step
            0.88,  # reasoning_depth
            0.72,  # system_ops
            0.82,  # creative
            0.80,  # task_length
            0.75,  # agentic
            0.85,  # simplicity
            0.82,  # domain_depth
            0.95,  # context_size — 1M+
            0.85,  # output_length
            0.75,  # safety_risk
            0.70,  # latency_need — medium
        ],
        cost_per_1m_input=1.25,
        cost_per_1m_output=10.0,
        context_window=1_000_000,
        avg_latency_ms=800,
        provider="google",
        tags=["balanced", "reasoning", "large-context"],
    ),

    # === OPEN-SOURCE / OPENROUTER ===
    "deepseek/deepseek-r1": ModelProfile(
        model_id="deepseek/deepseek-r1",
        display_name="DeepSeek R1",
        capabilities=[
            0.88,  # code_generation — strong coder
            0.75,  # file_editing
            0.80,  # multi_step
            0.92,  # reasoning_depth — chain-of-thought
            0.65,  # system_ops
            0.70,  # creative
            0.80,  # task_length
            0.65,  # agentic
            0.70,  # simplicity
            0.85,  # domain_depth — math/science
            0.80,  # context_size
            0.85,  # output_length
            0.70,  # safety_risk
            0.50,  # latency_need — slower (reasoning)
        ],
        cost_per_1m_input=0.55,
        cost_per_1m_output=2.19,
        context_window=64_000,
        avg_latency_ms=2000,
        provider="openrouter",
        tags=["reasoning", "math", "coding", "cheap"],
    ),
    "meta-llama/llama-4-maverick": ModelProfile(
        model_id="meta-llama/llama-4-maverick",
        display_name="Llama 4 Maverick",
        capabilities=[
            0.82,  # code_generation
            0.72,  # file_editing
            0.75,  # multi_step
            0.78,  # reasoning_depth
            0.65,  # system_ops
            0.80,  # creative
            0.75,  # task_length
            0.70,  # agentic
            0.88,  # simplicity
            0.72,  # domain_depth
            0.85,  # context_size
            0.80,  # output_length
            0.65,  # safety_risk
            0.75,  # latency_need
        ],
        cost_per_1m_input=0.20,
        cost_per_1m_output=0.60,
        context_window=1_000_000,
        avg_latency_ms=600,
        provider="openrouter",
        tags=["balanced", "cheap", "fast"],
    ),
}


class ModelRegistry:
    """Registry of available models with capability profiles.

    Models can be added from the built-in defaults, custom profiles,
    or loaded from JSON config files.

    Example:
        registry = ModelRegistry()
        registry.load_defaults()
        registry.add(ModelProfile(...))

        models = registry.filter(tags=["fast"], max_cost_input=1.0)
    """

    def __init__(self):
        self._models: Dict[str, ModelProfile] = {}

    def load_defaults(self) -> "ModelRegistry":
        """Load the built-in model profiles."""
        self._models.update(DEFAULT_MODELS)
        return self

    def add(self, profile: ModelProfile) -> None:
        """Add or update a model profile."""
        self._models[profile.model_id] = profile

    def remove(self, model_id: str) -> None:
        """Remove a model from the registry."""
        self._models.pop(model_id, None)

    def get(self, model_id: str) -> Optional[ModelProfile]:
        """Get a model profile by ID."""
        return self._models.get(model_id)

    def all(self) -> List[ModelProfile]:
        """Get all registered models."""
        return list(self._models.values())

    def filter(
        self,
        tags: Optional[List[str]] = None,
        provider: Optional[str] = None,
        max_cost_input: Optional[float] = None,
        min_context: Optional[int] = None,
        max_latency_ms: Optional[int] = None,
    ) -> List[ModelProfile]:
        """Filter models by constraints.

        All criteria are AND-ed. Returns models matching all specified constraints.
        """
        result = []
        for m in self._models.values():
            if tags and not any(t in m.tags for t in tags):
                continue
            if provider and m.provider != provider:
                continue
            if max_cost_input is not None and m.cost_per_1m_input > max_cost_input:
                continue
            if min_context is not None and m.context_window < min_context:
                continue
            if max_latency_ms is not None and m.avg_latency_ms > max_latency_ms:
                continue
            result.append(m)
        return result

    def load_from_dict(self, data: Dict) -> None:
        """Load models from a JSON-compatible dict.

        Expected format:
        {
            "model_id": {
                "display_name": "...",
                "capabilities": [14 floats],
                "cost_per_1m_input": float,
                "cost_per_1m_output": float,
                ...
            }
        }
        """
        for model_id, info in data.items():
            profile = ModelProfile(
                model_id=model_id,
                display_name=info.get("display_name", model_id),
                capabilities=info["capabilities"],
                cost_per_1m_input=info.get("cost_per_1m_input", 0.0),
                cost_per_1m_output=info.get("cost_per_1m_output", 0.0),
                context_window=info.get("context_window", 200_000),
                avg_latency_ms=info.get("avg_latency_ms", 1000),
                provider=info.get("provider", "openrouter"),
                tags=info.get("tags", []),
            )
            self.add(profile)

    def __len__(self) -> int:
        return len(self._models)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._models

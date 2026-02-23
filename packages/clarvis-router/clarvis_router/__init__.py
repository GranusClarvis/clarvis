"""
ClarvisRouter — Smart model routing with 14-dimension prompt scoring.

Analyzes prompts across 14 orthogonal dimensions to select the optimal LLM
for each task. Matches prompt feature vectors against model capability profiles.

Dimensions: code_generation, file_editing, multi_step, reasoning_depth,
system_ops, creative, task_length, agentic, simplicity, domain_depth,
context_size, output_length, safety_risk, latency_need.

Usage:
    from clarvis_router import PromptScorer, ModelRegistry, ModelProfile

    scorer = PromptScorer()
    result = scorer.score("Build a REST API with auth")

    registry = ModelRegistry()
    registry.load_defaults()
    models = registry.filter(tags=["fast"], max_cost_input=1.0)
"""

from clarvis_router.scorer import PromptScorer, DimensionConfig
from clarvis_router.models import ModelProfile, ModelRegistry

__version__ = "1.0.0"
__all__ = [
    "PromptScorer",
    "DimensionConfig",
    "ModelProfile",
    "ModelRegistry",
]

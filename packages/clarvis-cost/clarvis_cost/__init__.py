"""
ClarvisCost — Token optimization and cost tracking for LLM systems.

Track API costs, estimate tokens, monitor budgets, and optimize spending.
Backend-agnostic: works with any model provider (OpenRouter, Anthropic, Google).

Usage:
    from clarvis_cost import CostTracker, estimate_cost, estimate_tokens

    tracker = CostTracker("/path/to/costs.jsonl")
    tracker.log("claude-opus-4-6", input_tokens=5000, output_tokens=1200, source="heartbeat")

    rollup = tracker.rollup("day")
    print(f"Today: ${rollup['total_cost']:.4f}")

    budget = tracker.budget_check(daily_budget=5.0)
    print(f"Budget: {budget['pct_used']:.0f}% used, alert={budget['alert']}")

    tokens = estimate_tokens("Some prompt text", model="claude")
    cost = estimate_cost("claude-opus-4-6", input_tokens=5000, output_tokens=1200)
"""

from clarvis_cost.core import (
    CostEntry,
    CostTracker,
    estimate_cost,
    estimate_tokens,
    get_pricing,
    analyze_savings,
    import_router_decisions,
    MODEL_PRICING,
)
from clarvis_cost.optimizer import (
    PromptCache,
    ContextBudgetPlanner,
    detect_prompt_waste,
    compression_ratio_report,
)

__version__ = "1.0.0"
__all__ = [
    "CostEntry",
    "CostTracker",
    "estimate_cost",
    "estimate_tokens",
    "get_pricing",
    "analyze_savings",
    "import_router_decisions",
    "MODEL_PRICING",
    "PromptCache",
    "ContextBudgetPlanner",
    "detect_prompt_waste",
    "compression_ratio_report",
]

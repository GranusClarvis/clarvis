# clarvis-cost

Token optimization and cost tracking for LLM-powered cognitive systems.

Track API costs, estimate tokens, monitor budgets, and optimize spending. Works with any model provider (OpenRouter, Anthropic, Google).

## Installation

```bash
pip install clarvis-cost
```

## Usage

### Cost Tracking

```python
from clarvis_cost import CostTracker, estimate_cost, estimate_tokens

tracker = CostTracker("/path/to/costs.jsonl")
tracker.log("claude-opus-4-6", input_tokens=5000, output_tokens=1200, source="heartbeat")

rollup = tracker.rollup("day")
print(f"Today: ${rollup['total_cost']:.4f}")

budget = tracker.budget_check(daily_budget=5.0)
print(f"Budget: {budget['pct_used']:.0f}% used, alert={budget['alert']}")
```

### Quick Estimates

```python
from clarvis_cost import estimate_cost, estimate_tokens

tokens = estimate_tokens("Some prompt text")
cost = estimate_cost("claude-opus-4-6", input_tokens=5000, output_tokens=1200)
```

### Prompt Optimization

```python
from clarvis_cost import PromptCache, ContextBudgetPlanner, detect_prompt_waste

cache = PromptCache()
planner = ContextBudgetPlanner(max_tokens=8000)
waste = detect_prompt_waste(prompt_text)
```

## CLI

```bash
clarvis-cost estimate claude-opus-4-6 5000 1200   # Estimate cost
clarvis-cost tokens "Some prompt text"              # Estimate tokens
clarvis-cost log claude-opus-4-6 5000 1200 heartbeat  # Log entry
clarvis-cost rollup day costs.jsonl                 # Daily rollup
clarvis-cost budget 5.0 costs.jsonl                 # Budget check
clarvis-cost pricing                                # Show all model pricing
clarvis-cost pricing claude-opus-4-6                # Specific model pricing
clarvis-cost demo                                   # Run demo
```

## License

MIT

# clarvis-router

Smart model routing: 14-dimension prompt scorer selects the optimal LLM for each task. OpenRouter compatible.

Analyzes prompts across 14 orthogonal dimensions (code generation, reasoning depth, creativity, domain depth, etc.) and matches against model capability profiles to pick the cheapest model that can handle the task well.

## Installation

```bash
pip install clarvis-router

# With OpenRouter API support:
pip install clarvis-router[openrouter]
```

## Usage

```python
from clarvis_router import PromptScorer, ModelRegistry

# Score a prompt across 14 dimensions
scorer = PromptScorer()
features = scorer.score("Build a REST API with JWT auth")

# Match against model capabilities
registry = ModelRegistry()
best = registry.match(features)
print(f"Use {best.display_name} (${best.cost_per_1m_input}/1M)")

# Or get a ranked list
ranked = registry.rank(features)
for model, score in ranked:
    print(f"  [{score:.3f}] {model.display_name}")
```

### Scoring Dimensions

| # | Dimension | What it detects |
|---|-----------|-----------------|
| 1 | code_generation | Implementation, coding, scripting |
| 2 | file_editing | Modify existing files, integrate |
| 3 | multi_step | Sequential workflows, pipelines |
| 4 | reasoning_depth | Analysis, evaluation, design |
| 5 | system_ops | Deploy, configure, infrastructure |
| 6 | creative | Brainstorm, invent, novel |
| 7 | task_length | Word count as complexity proxy |
| 8 | agentic | Run, execute, spawn, fetch |
| 9 | simplicity | Simple queries (inverse complexity) |
| 10 | domain_depth | Specialized domains (quantum, genomics) |
| 11 | context_size | Estimated input token load |
| 12 | output_length | Expected output length |
| 13 | safety_risk | Content needing careful guardrails |
| 14 | latency_need | Urgency/interactive vs batch |

## CLI

```bash
clarvis-router route "Build a REST API with auth"    # Recommend best model
clarvis-router score "Explain quantum entanglement"  # Show feature vector
clarvis-router models                                 # List available models
clarvis-router compare "Write a haiku about code"    # Rank all models
```

## License

MIT

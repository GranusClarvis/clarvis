# AgencyBench: 1M-Token Autonomous Agent Evaluation

**Paper**: arXiv:2601.11044 (Jan 2026, GAIR-NLP)
**Ingested**: 2026-03-15
**Relevance**: PI benchmark expansion, Context Relevance measurement, automated evaluation

## Summary

AgencyBench benchmarks autonomous agents on 138 tasks across 32 real-world scenarios requiring ~90 tool calls, ~1M tokens, and hours of execution. Evaluates 6 capabilities: game dev (50 tasks), frontend (15), backend (15), code generation (29), research (19), MCP tool use (10). Uses Docker sandbox + three-tier rubric assessment (rule-based, vision-based, LLM-as-judge) with automated user simulation agent replacing human-in-the-loop.

## Key Ideas for Clarvis

### 1. Three-Tier Rubric Assessment
Instead of single-dimension scoring, AgencyBench uses:
- **Rule-based judges**: automated assertion logic (functional correctness, 0-10 scale)
- **Vision-based judges**: screenshot analysis for UI/visual tasks
- **LLM-as-judge**: subjective quality at temperature 0.0

**Clarvis application**: PI currently uses heuristic metrics. Could add rule-based checks (brain health assertions), and LLM-as-judge for evaluating whether heartbeat task outputs actually addressed the task prompt. This directly targets **Context Relevance** (0.387 → 0.75) by measuring whether retrieved context was actually useful.

### 2. Self-Correction Rate as First-Class Metric
Pass@1 vs Pass@2 reveals self-correction capability. GPT-5.2: +88.9%, Kimi-K2: +300%, DeepSeek-V3.2: 0% (persists on wrong paths).

**Clarvis application**: Track heartbeat retry success rate. When a task fails or produces low-quality output, does the next attempt improve? Currently unmeasured. Could add `self_correction_rate` to PI dimensions.

### 3. Efficiency-Normalized Scoring
- Attempt Efficiency = S_avg / Attempts
- Token Efficiency = S_avg / Tokens consumed
- Grok-4.1-Fast: highest token efficiency (37.2%) with 1.2M tokens vs GPT-5.2 at 3.4M using frugality normalization.

**Clarvis application**: PI should weight quality by cost/token efficiency. A heartbeat that achieves good results in 800 tokens of context is better than one using 4000 tokens with same quality. Directly relevant to Context Relevance — measuring signal-to-noise ratio.

### 4. User Simulation Agent for Automated Evaluation
Claude-4-Sonnet (temp=0.0) provides iterative feedback. 4.69/5.0 consistency with human experts (validated on 50 rollouts). Eliminates human-in-the-loop bottleneck.

**Clarvis application**: Use a cheap model (Haiku or local Qwen) to auto-evaluate heartbeat outputs against task rubrics. Generate a `task_quality_score` per episode. This would give us ground-truth Context Relevance measurement: "did the retrieved context actually help the task?"

### 5. Tool-Use Distribution Analysis
Shell execution dominates for Claude/GPT (43-45%). Gemini uniquely uses memory tools (6.9%). Some models over-index on web search.

**Clarvis application**: Analyze tool-use distribution across heartbeats. Are we over-using brain search and under-using episodic recall? Is the context assembly pipeline pulling from the right sources? Tool-use profiling could reveal why Context Relevance is low.

## Model Performance (S_avg)

| Model | Score | Tokens | Attempts |
|-------|-------|--------|----------|
| GPT-5.2 | 56.5% | 3.4M | 1.46 |
| Claude-4.5-Opus | 47.7% | - | 1.54 |
| Gemini-3-Pro | ~45% | - | - |
| GLM-4.6 (open) | 38.6% | - | 1.54 |
| Qwen-3 (open) | 27.0% | - | 1.79 |

Closed-source: 48.4% avg. Open-source: 32.1% avg.

## Scaffold Dependency Finding
Claude-4.5-Opus improves 20.5% within Claude-Agent-SDK native ecosystem. Open-source models show heterogeneous scaffold sensitivity. This validates that evaluation framework choice significantly impacts measured performance — relevant when benchmarking Clarvis across different execution modes.

## Implementation Priority
1. **LLM-as-judge for heartbeat outputs** → most direct Context Relevance improvement path
2. **Efficiency-normalized PI scoring** → cost-aware quality measurement
3. **Self-correction rate tracking** → new PI dimension
4. **Tool-use profiling** → diagnostic for context assembly pipeline

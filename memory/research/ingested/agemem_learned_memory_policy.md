# AgeMem — Learned Agentic Memory Policy

**Paper**: Yu et al. 2025, "Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for LLM Agents" (arXiv:2601.01885)
**Ingested**: 2026-03-15

## Core Idea
Memory operations (store, retrieve, update, summarize, discard) exposed as **tool-based actions** that the agent learns to invoke autonomously via reinforcement learning, replacing static heuristics.

## Key Contributions
1. **Unified LTM/STM**: Single policy manages both memory types (vs separate subsystems)
2. **Memory-as-tools**: Store/retrieve/update/forget are callable tools — agent decides what/when
3. **Three-stage progressive RL**: Gradual training from simple to complex memory tasks
4. **Step-wise GRPO**: Specialized training for sparse, discontinuous rewards from memory ops

## Relevance to Clarvis
- **Maps to**: `brain.remember()`, `brain.recall()`, `brain.reconsolidate()`, `brain.revise()`
- **Current approach**: Clarvis uses heuristic importance scoring + decay + propose/commit pipeline
- **Gap**: Clarvis lacks learned policy for when to store vs discard — uses fixed thresholds (importance >= 0.6 in `capture()`, dedup distance < 0.3)
- **Actionable**: The propose/commit pipeline already separates decision from execution — the "evaluation" step could be enhanced with a learned scoring model instead of rule-based checks

## Benchmark Results
- Outperforms baselines across 5 long-horizon benchmarks
- Improved task performance, higher-quality LTM, more efficient context usage
- Works across multiple LLM backbones

## Applicable Ideas (prioritized)
1. **Memory operation logging** — Already done via conflict_log.jsonl, episode encoding. Could add explicit store/skip decision logging to train a classifier later.
2. **Unified store/update decision** — Currently `remember()` vs `reconsolidate()` are separate code paths. Could unify under a single `memory_action()` dispatcher.
3. **Progressive difficulty** — Training on easy memory tasks first. Maps to our golden QA benchmarks — could create difficulty-tiered retrieval tests.

## Not Applicable
- Full RL training loop (requires model fine-tuning, not feasible with API-only models)
- Step-wise GRPO (training-time technique)

# CLR / ΦID Benchmark Plan

_Date: 2026-03-19_

## Purpose

Clarvis needs benchmark scores that answer three practical questions:

1. **Is Clarvis improving over time?**
2. **Did a new addition actually help, hurt, or just add complexity?**
3. **Which subsystem is responsible for the change?**

The existing CLR idea in the queue is the right umbrella. This document defines how to extend CLR so it measures not just task success, but also **integration quality**: uniqueness, redundancy, synergy, and perturbation sensitivity across Clarvis subsystems.

This is inspired by IIT / Φ proxies / ΦID, but it is framed as an engineering benchmark rather than a consciousness claim.

## Benchmarking Principles

- **Code-verified over vibes**: prefer deterministic or replayable checks over LLM-judged scores when possible.
- **Before/after deltas matter more than absolutes**: every intervention should produce a benchmark delta.
- **Multi-metric beats one mystical scalar**: CLR should be a dashboard with a composite score, not a single sacred number.
- **Perturbation over narration**: measure what breaks when a module is muted.
- **Cheap enough to run often**: lightweight daily subset, heavier weekly full run.

## CLR vNext Structure

### 1. Memory Quality
Measures whether recall is useful and efficient.

- recall_accuracy
- retrieval_latency_p95
- context_relevance_7d
- retrieval_precision_at_k
- stale_context_rate

### 2. Brain Integration
Measures whether the memory graph and subsystems are actually connected.

- graph_density
- semantic_cross_collection
- cross_collection_bridge_count
- goal_context_linkage
- episode_to_learning_promotion_rate

### 3. Task Execution
Measures whether Clarvis can do work reliably.

- task_success_rate
- first_pass_success_rate
- test_pass_rate
- execution_reliability
- autonomous_completion_rate

### 4. Prompt / Brief Quality
Measures whether internal context assembly produces usable working state.

- brief_coherence
- brief_noise_ratio
- section_usefulness
- budget_allocation_quality
- prompt_overhead_ratio

### 5. Self-Improvement Quality
Measures whether evolution actually improves the system.

- benchmark_delta_after_change
- regression_rate
- queue_throughput
- archived_task_value
- reflection_to_implementation_rate

### 6. Integration Dynamics (new)
This is the ΦID-inspired layer.

#### 6.1 Unique Contribution Score
For each module, estimate how much task performance depends on information that only that module provides.

Candidate modules:
- episodic memory
- semantic memory / brain recall
- graph expansion
- queue / goal context
- reasoning scaffold
- recent completions

Method:
- run benchmark item with all modules enabled
- ablate one module at a time
- measure delta in task success, relevance, or solution quality
- unique contribution = marginal gain not recovered by other modules

#### 6.2 Redundancy Ratio
Measures how much repeated information appears across brief sections.

Examples:
- same fact appears in related_tasks, decision_context, and episodes
- multiple sections carry overlapping tokens with little new value

Method:
- semantic overlap between sections
- repeated fact clusters / duplicate token spans
- ratio of repeated vs novel useful content

Goal:
- lower redundancy without harming task success

#### 6.3 Synergy Gain
Measures whether combinations of modules outperform the best single module.

Formula idea:
- synergy_gain = score(all enabled) - max(score(single module i))

Useful read:
- if memory + goals + episodes together beat any one of them alone, Clarvis is integrating rather than just stacking context

#### 6.4 Perturbation Integration Score
Measures how gracefully Clarvis degrades when subsystems are muted.

Ablations:
- no episodic memory
- no graph expansion
- no related_tasks
- no decision_context
- no reasoning scaffold

Outputs:
- performance drop
- context relevance drop
- latency change
- failure mode classification

Interpretation:
- a healthy integrated system should show meaningful but interpretable degradation, not random chaos or no change at all

## Proposed Composite Layout

CLR should remain the headline benchmark, but broken into weighted bands:

- Memory Quality: 20%
- Brain Integration: 15%
- Task Execution: 25%
- Prompt / Brief Quality: 15%
- Self-Improvement Quality: 10%
- Integration Dynamics (ΦID-inspired): 15%

Keep raw submetrics visible; never show only the weighted final score.

## Daily vs Weekly Runs

### Daily CLR-Lite
Cheap and trend-focused.

Includes:
- context_relevance_7d
- recall latency
- task success
- brief noise ratio
- a small perturbation sample
- regression detection vs previous day

### Weekly CLR-Full
More expensive and diagnostic.

Includes:
- full ablation matrix
- synergy / redundancy / unique contribution estimates
- cross-collection bridge audit
- benchmark delta report for all code changes that week
- scorecard by subsystem

## What This Lets Us Answer

With this structure, we can finally ask useful questions such as:

- Did a new retrieval module improve context relevance, or just add tokens?
- Did graph expansion increase true synergy, or only redundancy?
- Did prompt changes help task success but hurt calibration?
- Did a self-improvement task produce a measurable delta, or merely move code around?

## Immediate Next Steps

1. ~~**Wire CLR baseline into the canonical benchmark path**~~ ✓ Done 2026-03-19
   - `clarvis/metrics/clr.py` has `__main__` block, commit_sha in output/records
   - CLI: `python3 -m clarvis metrics clr --record`
2. **Add perturbation benchmark harness**
   - deterministic module ablation runner for brief assembly and recall pipeline
3. ~~**Add three ΦID-inspired metrics first**~~ ✓ Done 2026-03-19
   - redundancy_ratio (CV of per-section relevance scores)
   - unique_contribution_score (fraction of referenced sections)
   - synergy_gain (success rate: rich-context vs sparse-context episodes)
   - Implemented as 7th CLR dimension: `integration_dynamics` (w=0.14)
   - Data source: `data/retrieval_quality/context_relevance.jsonl`
4. ~~**Store per-run history**~~ ✓ Done 2026-03-19
   - `data/clr_history.jsonl` with timestamp, commit_sha, dimension subscores
5. **Show deltas next to goals**
   - tie benchmark movement to evolution queue tasks and current roadmap goals

## Guard Rails

- Do not claim these metrics measure consciousness directly.
- Treat them as **integration-quality and evaluation metrics**.
- Exact Φ remains a toy benchmark for tiny synthetic graphs only.
- Prefer honest, reproducible proxies over grand metaphysical theatre.

## Relationship to Existing CLR Queue Item

Source queue note: `memory/evolution/QUEUE.md` already defines CLR as a comprehensive Clarvis benchmark spanning memory quality, brain integration, task success, prompt quality, and self-improvement.

This document extends that existing CLR concept with a sixth dimension:
- **Integration Dynamics (ΦID-inspired)**

That makes CLR the umbrella benchmark, while ΦID-style analysis becomes one diagnostic slice inside it rather than a separate vanity metric.

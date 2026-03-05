# OBLITERATUS Review — 2026-03-05

**Repo**: https://github.com/elder-plinius/OBLITERATUS
**License**: AGPL-3.0
**Verdict**: DISCARD for direct integration (weight-level safety removal tool; Clarvis is API-based + safety-aligned).

**Keep (transferable patterns):** the *research/engineering loop* ideas (telemetry-driven benchmarking, analysis→action auto-configuration, iterative self-repair detection) are worth adapting to Clarvis’s self-evolution + benchmarks.

## 10-Bullet Summary

1. **Purpose**: Open-source toolkit for surgically removing refusal/safety-alignment mechanisms from LLMs. "Abliteration" — extracts learned refusal directions from transformer weight matrices via SVD and projects them out to produce uncensored models.

2. **Architecture**: 6-stage pipeline (SUMMON→PROBE→DISTILL→EXCISE→VERIFY→REBIRTH) with optional 7th ANALYZE stage. Built on PyTorch + HuggingFace. ~27 analysis modules, 6 ablation strategies, 9 evaluation modules.

3. **Core Mechanism — Direction Extraction**: Collects activations from paired harmful/harmless prompts, computes difference-in-means vectors, SVD decomposition to find principal "refusal direction." Four extraction methods: basic diff-of-means (Arditi et al.), multi-direction Gabliteration, whitened SVD, and Wasserstein-optimal.

4. **Excision**: Projects refusal directions out of weight matrices (attention projections, FFN, MoE routers). Layer selection via knee detection, COSMIC fusion, or middle-60%. Advanced: spectral cascade (DCT frequency-selective attenuation), layer-adaptive weighting, jailbreak-contrastive blending.

5. **Informed Pipeline**: 5 analysis modules (alignment imprint detection, concept cone geometry, cross-layer clustering, sparse surgery planning, defense robustness evaluation) run BEFORE excision to auto-configure parameters.

6. **Ouroboros Loop**: Detects and re-removes refusal directions that self-repair post-ablation (up to 3 iterative passes). Bayesian optimization (Optuna TPE) searches 7-parameter space for Pareto-optimal refusal-rate vs. KL-divergence tradeoffs.

7. **Concept Geometry**: Characterizes refusal as a "polyhedral concept cone" — computes per-category direction specificity indices, effective SVD rank, solid angles. Classifies refusal geometry as LINEAR, POLYHEDRAL, or intermediate.

8. **LoRA Reversibility**: Decomposes ablation operation into LoRA adapter pairs for non-destructive apply/remove. Compatible with HuggingFace PEFT.

9. **Threat Model**: Fundamentally a safety-alignment removal tool. Defense robustness evaluator explicitly maps how to defeat model self-repair. Bayesian optimization automates finding minimum intervention to disable safety. Community leaderboard crowd-sources most effective jailbreaking configs per architecture.

10. **Code Quality**: Well-structured Python package, dataclass configs, YAML serialization, Rich CLI, type hints. Mathematically sound SVD/Wasserstein/Riemannian implementations. ~70+ modules total.

## Integration Assessment

**DISCARD** — Three reasons:

1. **Domain mismatch**: Clarvis consumes models via API (OpenRouter, Claude Code). No access to model weights, intermediate activations, or forward-pass internals. OBLITERATUS's entire value requires weight-level access.

2. **Purpose misalignment**: Removing safety alignment is antithetical to Clarvis's design philosophy. Clarvis values safety constraints.

3. **Scale mismatch**: Concept cone geometry for memory clustering could theoretically apply to ChromaDB embeddings, but a 2200-memory brain doesn't benefit from polyhedral SVD analysis — existing dedup/compaction suffices.

**Transferable patterns (useful for Clarvis):**

1) **Telemetry + crowd-sourced benchmark dataset**: OBLITERATUS treats each run as a data point feeding a shared benchmark corpus. Clarvis analogue: every autonomous task run should emit a structured record `{task_id, route, outcome, error_type, time, cost, delta_metrics}` and we should trend it (this is partially in place: postflight completeness + cost_per_task).

2) **Analysis-informed pipeline (closed loop)**: run diagnostics first, then pick the intervention parameters automatically. Clarvis analogue: before executing a queue item, run a fast “preflight analyzer” that selects *scope* (subtasks), budget, and which modules to activate; then execute; then re-measure (golden QA / PI / Phi) and decide if rollback needed.

3) **Ouroboros self-repair detection**: they re-probe after each surgery pass to detect rotated residual directions. Clarvis analogue: after each major refactor or migration, automatically re-run invariants + parity checks (golden QA, graph parity, hook registration, CLI parity) and if drift occurs, auto-open a queue item to remediate.

4) **Decision matrix discipline**: explicit axes (performance, correctness, ops risk) and a written decision doc. Clarvis is now doing this for graph storage; replicate the pattern for other storage decisions (Chroma singleton consolidation, episodic store, cost DB).

**Non-transferable**: all weight/activation surgery mechanics (SVD refusal direction extraction, projection, Optuna tuning) — not applicable without local weights and contradicts safety stance.

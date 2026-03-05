# OBLITERATUS Review — 2026-03-05

**Repo**: https://github.com/elder-plinius/OBLITERATUS
**License**: AGPL-3.0
**Verdict**: DISCARD — domain mismatch (safety-alignment removal tool, not applicable to API-based agent)

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

**Inspirational note**: The iterative self-repair detection (Ouroboros) is an interesting pattern for any system that makes modifications that could revert — worth remembering as a concept even if the code is inapplicable.

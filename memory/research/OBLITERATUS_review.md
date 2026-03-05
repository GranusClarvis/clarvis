# OBLITERATUS Research Review — 2026-03-05

**Repo**: https://github.com/elder-plinius/OBLITERATUS
**Stars**: 1,281 | **License**: AGPL-3.0 | **Created**: 2026-03-03 (very recent)

## 10-Point Summary

1. **Purpose**: Open-source toolkit for removing refusal behaviors from LLMs via "abliteration" — surgically eliminating activation directions responsible for content refusal without retraining. Tagline: "Break the chains. Free the mind. Keep the brain."

2. **Architecture**: Six-stage pipeline: SUMMON → PROBE → ANALYZE → DISTILL → EXCISE → VERIFY. `InformedAbliterationPipeline` adds closed-loop feedback where analysis auto-configures downstream hyperparameters.

3. **Key Components**: `abliterate.py` (291KB main pipeline), 24 analysis modules (cross-layer alignment, concept cone geometry, Riemannian manifold analysis, Wasserstein optimal transport, sparse surgery, causal tracing), 7 intervention presets, Bayesian optimizer (TPE-based, 7-parameter kernel space).

4. **Threat Model**: **Offensive tool against alignment** — removes safety guardrails from LLMs. No defensive threat model. SECURITY.md only covers code vulnerabilities, not the tool's primary function.

5. **Memory Patterns**: Minimal persistent memory. Telemetry uses append-only JSONL with background Hub sync. No episodic memory, no learning across sessions — purely stateless tool.

6. **Autonomy Patterns**: `InformedAbliterationPipeline` runs 5 analysis modules to detect alignment method (DPO/RLHF/CAI/SFT), then auto-derives parameters. Ouroboros compensation loop re-probes up to 3 times if residual refusal detected. No cron/scheduling/persistent evolution.

7. **Safety Mechanisms**: Quality safeguards only (norm-preservation, entanglement gating, regularization scaling, KL-divergence monitoring) — prevents capability collapse, not misuse.

8. **Orchestration**: Strategy pattern with pluggable ablation strategies + registry-based analysis module dispatch. YAML-configurable presets. Gradio UI + Colab + HuggingFace Spaces interfaces.

9. **Notable Techniques**: (a) GRRO — unifies 20+ techniques under `W' = W - sum(alpha_i * P_i(W))`; (b) Concept Cone Analysis — refusal as polyhedral cones; (c) Anti-Ouroboros ASRG — spectral analysis for minimum simultaneous ablations; (d) Alignment Imprint Detection — classifies training method from 6 geometric fingerprints; (e) Expert-Granular Abliteration for MoE models.

10. **Code Quality**: Version 0.1.2, 2 days old. Large codebase (~1.3MB) with 20+ test files. Well-structured but `abliterate.py` is 291KB monolith. High intellectual quality, early-stage maturity.

## 3 Integration Ideas for Clarvis

### 1. Closed-Loop Analysis-Driven Configuration (from InformedAbliterationPipeline)
Add `heartbeat_analysis.py` that between preflight task selection and Claude Code execution, runs lightweight diagnostics (brain query speed, memory saturation, recent failure patterns) and auto-tunes execution parameters — timeout duration, context budget, which collections to prioritize, whether to include episodic recall. Mirrors the AlignmentImprintDetector pattern: diagnose → derive configuration → execute (not fixed defaults).

### 2. Anti-Ouroboros Redundancy Detection for Brain Optimization
After pruning memories in `brain optimize-full`, re-run retrieval benchmarks on golden queries and detect if other memories "compensated" (increased in relevance rank). Those compensating memories are redundant carriers — candidates for consolidation. Uses perturbation-based redundancy detection instead of purely similarity-based dedup. Could identify "hub memories" that carry disproportionate load.

### 3. Geometric Fingerprinting for Cognitive State Classification
Compute periodic metrics over ChromaDB embedding space: Gini coefficient of importance scores, effective rank of embedding matrix per collection, spectral decay. Fingerprint cognitive states: "learning mode" (high influx), "maintenance mode" (stable), "drift mode" (embeddings spreading), "saturation mode" (redundancy climbing). Drive autonomous decisions: saturation → aggressive consolidation, drift → increase decay rate. Add `embedding_geometry.py`, run from evening cron.

## Verdict
**Worth watching, selectively adopt patterns.** The analysis-driven configuration and perturbation-based redundancy detection are directly applicable. The tool itself (alignment removal) is not relevant to Clarvis's goals. Core value: sophisticated geometric analysis of neural representations — transferable methodology.

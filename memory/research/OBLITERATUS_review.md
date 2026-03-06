# Research Review: OBLITERATUS
**Date**: 2026-03-06
**Repo**: https://github.com/elder-plinius/OBLITERATUS
**License**: AGPL-3.0

## What It Is
Open-source toolkit for identifying and removing refusal mechanisms from LLMs via "abliteration" — surgically extracting internal representations responsible for content refusal without retraining.

## 10 Key Bullets

1. **Six-stage pipeline**: SUMMON (load) → PROBE (collect activations from restricted vs unrestricted prompts) → DISTILL (extract refusal directions via SVD) → EXCISE (project out guardrail directions, norm-preserving) → VERIFY (perplexity/coherence check) → REBIRTH (save modified model).

2. **Two intervention paradigms**: Weight projection (permanent model modification) and steering vectors (inference-time, reversible). Steering vectors are more interesting architecturally — they modify behavior without touching weights.

3. **Seven intensity presets**: basic → advanced → aggressive → surgical → optimized → inverted → nuclear. Each adds more SVD directions, passes, and techniques. Shows good progressive-escalation pattern.

4. **15 analysis modules**: Cross-layer alignment, logit lens, whitened SVD, activation probing, concept cone geometry, alignment imprint detection (DPO vs RLHF fingerprinting), causal tracing, residual stream decomposition, linear probing classifiers, cross-model transfer analysis.

5. **Ouroboros self-repair detection**: Detects when guardrails attempt to "self-repair" after ablation, then runs additional passes. Notable pattern: monitoring for system self-correction and responding adaptively.

6. **Analysis-informed configuration**: The pipeline runs geometric analysis *during* obliteration to auto-configure parameters rather than using fixed hyperparameters. Analysis feeds back into execution.

7. **COSMIC layer selection**: Uses cosine similarity metrics to identify which layers most strongly encode refusal, targeting only those layers instead of blanket modification.

8. **MoE-aware**: Expert-granular ablation for mixture-of-experts architectures — knows which experts to target rather than modifying the entire model.

9. **Capability preservation emphasis**: Norm-preserving projections, chain-of-thought awareness, KL-divergence constraints to maintain reasoning quality while modifying behavior.

10. **Threat model**: Tool explicitly enables bypassing safety measures. Framed as "democratizing model behavior decisions" for research/red-teaming. AGPL-3.0 copyleft. Includes optional community telemetry for aggregating benchmark data.

## Integration Assessment: DISCARD (with caveats)

**Core purpose is not relevant to Clarvis.** OBLITERATUS is a model-modification toolkit for removing safety guardrails from LLMs. Clarvis does not run local LLMs that need modification — it uses API-based models (MiniMax M2.5, Claude Opus, OpenRouter models). The abliteration techniques require model weight access, which API users don't have.

**However, 3 architectural patterns are worth noting (but not worth implementing now):**

1. **Analysis-informed pipeline pattern** (low priority): OBLITERATUS runs diagnostic analysis *during* its pipeline to auto-configure parameters. Clarvis's heartbeat pipeline could benefit from a similar pattern — running quick diagnostics mid-pipeline to adjust task selection parameters. However, the heartbeat pipeline already has attention scoring and the preflight does similar work. **Verdict: Not actionable now.**

2. **Self-repair detection (Ouroboros pattern)** (interesting but speculative): Detecting when a system "undoes" an intended modification is conceptually relevant to Clarvis's self-modification safety. If Clarvis modifies a script and a subsequent cron job overwrites the change, detecting that would be useful. **Verdict: Too speculative, no concrete implementation path.**

3. **Progressive intensity presets** (minor): The 7-level intensity model (basic → nuclear) is a clean UX pattern. Clarvis's task router already has complexity levels (SIMPLE/MEDIUM/COMPLEX). No gap here. **Verdict: Already covered.**

**Final verdict: DISCARD.** The repo is well-engineered but solves a fundamentally different problem (model weight modification for jailbreaking). No components warrant integration into Clarvis's cognitive architecture. The interesting patterns (analysis-informed pipelines, self-repair detection) are either already present in Clarvis or too speculative to justify implementation effort.

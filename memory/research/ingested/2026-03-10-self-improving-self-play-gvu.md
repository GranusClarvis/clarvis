# Self-Improving AI Agents through Self-Play — Mathematical Framework

**Paper**: arXiv:2512.02731 (Dec 2025)
**Author**: Przemyslaw Chojecki
**Ingested**: 2026-03-10

## Core Framework

The GVU (Generator-Verifier-Updater) operator formalizes self-improvement as a dynamical system on a parameter manifold:

**T_GVU: θ ↦ U(θ, V(G(θ)))**

- **Generator G**: samples evaluation triples from battery distribution, produces input-output pairs via policy π_θ
- **Verifier V**: scores outputs via internal potential V(x,y), produces weighted empirical measure with softmax weights w_i = exp(βV(x_i,y_i)) / Z
- **Updater U**: minimizes -log π_θ'(y|x) + λR(θ',θ) under weighted measure (encompasses SFT, PPO, in-context learning)

## Second Law of AGI Dynamics

**"Entropy (hallucination) increases unless generation+verification signal exceeds threshold relative to noise and curvature."**

Formal Variance Inequality (Theorem 4.1):

```
ρ||g*||² > (ηL/2)(ρ²||g*||² + σ²_G + σ²_V)
```

Where: ρ = alignment coefficient [-1,1], σ²_G/σ²_V = generation/verification noise, L = smoothness constant, η = step size.

Equivalent form: **ρ > (ηL/2)(ρ² + 1/SNR(G) + 1/SNR(V))**

## Self-Improvement Coefficient κ

κ(r) := Lie derivative of capability functional F along the agent flow ν_r.

**κ ∝ ||g*|| · ||v|| · cos(θ_F)** where θ_F is the Fisher angle between GVU drift and true gradient.

"Ignition" = sustained κ > 0 across capability fibers.

## Key Results

### Hallucination Barrier (Corollary 4.2)
When verifier ≈ generator (self-critique, "diagonal GVU"):
- SNR_diag must satisfy: 2/SNR_diag ≪ 2ρ/(ηL) - ρ²
- **Rarely satisfied** with modest SNR → naive self-correction fails
- Generation and verification inherit identical noise; quadratic curvature penalty dominates

### Verifier SNR Dominance (Corollary 4.3)
For fixed generator noise, there exists finite SNR*_V such that SNR(V) > SNR*_V ⟹ E[ΔF] > 0.
**"Strengthen the verifier, not the generator"** to break through plateaus.

### Ensemble Scaling (Theorem 4.7)
M independent judges: σ²_V,ensemble = σ²_V,single / M → SNR scales linearly with M.

### Oracle Verifier (Corollary 4.10)
When σ²_V = 0 (code execution, formal proofs, AlphaZero game rules):
Even with noisy generator, oracle verifier guarantees stable self-improvement window.

### Step-Size Window (Corollary 4.6)
η_max = 2ρ||g*||² / [L(ρ²||g*||² + σ²_G + σ²_V)]
Better alignment ρ or lower verification noise widens the window.

### Goodhart Drift
Alignment decays: ρ̇ ≈ -γ||θ̇_r||. Critical threshold:
ρ_crit ≈ ηL(σ²_G + σ²_V) / (2||g*||²)
Below ρ_crit → improvement stops. Must periodically refresh verifier potential V.

### AI Slop (formal definition)
Slop region = outputs scored high by internal verifier but low by true battery.
Slop mass ≥ δ → agent is in slop regime (reward hacking).

## System Mappings

| System | Generator | Verifier | Updater |
|--------|-----------|----------|---------|
| STaR | LLM sample | Execution correctness | SFT on filtered |
| SPIN | Student LLM | Discriminator vs human | DPO/IPO |
| Reflexion | LLM + memory | Self-critique + env | In-context update |
| AlphaZero | MCTS self-play | Game rules (oracle) | Policy gradient |
| GANs | Generator network | Discriminator | Adversarial update |
| GRPO | Group samples | Group-normalized advantage | Policy gradient |

## Universality Result (Theorem 3.6)
Any smooth first-order update on a regular statistical manifold can be written as score-weighted expectation under some verifier potential V. **A non-trivial verifier is mathematically necessary for κ > 0** (Corollary 3.8).

## Clarvis Applications

1. **AZR Self-Play** (cron_absolute_zero.sh): Our self-play uses execution correctness as oracle verifier (σ²_V ≈ 0) → guarantees stable improvement window per Corollary 4.10. Key: ensure generation diversity (temperature) while keeping verifier strict.

2. **Strategy Evolution** (meta-learning): Strategy weights function as soft verifier alignment ρ. Weight decay toward uniform = Goodhart drift prevention (periodic refresh). The `explore=10%` rate controls σ²_G (generation noise).

3. **Confidence Calibration**: Brier score degradation (0.13) maps to ρ decay — predictions drift from true outcomes. The framework suggests strengthening verification (outcome recording) rather than adjusting prediction generation.

4. **Retrieval Quality**: Brain recall acts as a verifier for context relevance. Ensemble approach (multiple collections, graph expansion) maps to Theorem 4.7 — more retrieval sources reduce effective verification noise.

5. **Design Principle**: When autonomous task success plateaus, invest in stronger verification (tests, evaluation, success criteria) rather than more generation (more attempts, more models). This is the core insight of verifier SNR dominance.

# Bundle Q: Meta-Learning & RL

**Date:** 2026-02-25
**Sources:**
- Xu, van Hasselt & Silver, "Meta-Gradient Reinforcement Learning" (NeurIPS 2018, arXiv:1805.09801)
- Sutton, Precup & Singh, "Between MDPs and Semi-MDPs: A Framework for Temporal Abstraction in RL" (AIJ 1999)
- Dossa/Maytié/Devillers/VanRullen, "Zero-shot cross-modal transfer of RL policies through a Global Workspace" (RLC 2024, arXiv:2403.04588)
- Devillers/Maytié/VanRullen, "Semi-Supervised Multimodal Representation Learning Through a Global Workspace" (IEEE TNNLS 2024)

---

## 1. Meta-Gradient RL (Xu et al. 2018)

**Core idea:** Instead of fixing hyperparameters (γ discount, λ bootstrapping), treat them as meta-parameters η and learn them online via gradient descent on validation performance.

**Algorithm — Online Cross-Validation:**
1. With parameters θ, collect experience batch τ and update θ → θ'
2. Collect consecutive batch τ' with θ'
3. Evaluate performance J(τ', θ', η̄) on the validation batch
4. Compute meta-gradient ∂J/∂η via chain rule: Δη = -β · (∂J/∂θ') · (∂f/∂η)
5. Key simplification: drop secondary gradient (prefer immediate effect of η on θ)

**Results:** 30–80% improvement over baseline IMPALA on 57 Atari games.

**Key insight for Clarvis:** The meta-parameters that define "what counts as a good return" (γ, λ) should be learned, not hand-tuned. Applied to Clarvis: task-selection weights, exploration rate, and temporal discounting should auto-adapt based on consecutive heartbeat performance.

## 2. Hierarchical RL — Options Framework (Sutton, Precup, Singh 1999)

**Core idea:** Extend primitive actions with "options" — temporally extended courses of action. Each option = (I, π, β) where I = initiation set, π = internal policy, β = termination condition.

**Key concepts:**
- **Temporal abstraction:** Options compress sequences of primitive actions into macro-actions, enabling planning at multiple time scales
- **Semi-MDP framework:** Between-option transitions form a Semi-MDP (variable-duration steps)
- **Intra-option learning:** Update option value estimates from PARTIAL option executions, not just completions (sample-efficient)
- **Option-critic architecture** (Bacon et al. 2017): End-to-end learning of option policies and termination conditions

**2024 updates:**
- Hierarchical world models (Nature 2024): world models at multiple temporal abstractions improve sample efficiency
- Option discovery remains open: which options to create is still mostly hand-designed

**Key insight for Clarvis:** Multi-step task bundles (research→ingest→store, diagnose→fix→test) are options. Track their value estimates, learn which bundles succeed, use intra-option learning to update from partial completions.

## 3. Global Workspace Agent for Cross-Modal RL Transfer (Dossa et al. 2024)

**Core contribution:** RL policies trained via a Global Workspace (GW) transfer zero-shot between input modalities — a policy trained on attribute vectors works on images, and vice versa.

**Architecture:**
- Modality-specific encoders (e_v, e_attr) + decoders (d_v, d_attr)
- Shared GW latent space trained with 4 losses:
  - L_tr (translation): supervised cross-modal reconstruction
  - L_cont (contrastive): CLIP-like alignment
  - L_dcy (demi-cycle): self-supervised within-modality reconstruction
  - L_cy (full-cycle): unsupervised A→GW→B→GW→A reconstruction
- Frozen GW → PPO policy training

**Key findings:**
- CLIP fails at cross-modal transfer; GW succeeds
- Contrastive alignment discards modality-specific information
- Cycle consistency (L_cy) is the critical ingredient — ensures GW captures semantics, not surface
- Works in low-data regimes (1/4 to 1/100 paired data)
- Tested in: Simple Shapes grid world (32×32), Factory robotic reaching (Webots)

**Key insight for Clarvis:** Strategies that succeed in one cognitive domain (e.g., memory_system) can transfer to another (e.g., code_generation) IF the underlying representation captures domain-agnostic patterns. Build a transfer matrix tracking cross-domain strategy success correlations.

---

## Synthesis: Three Ideas, One System

The three papers converge on a unified theme: **self-adaptive agents that learn how to learn.**

| Paper | What it adapts | How |
|---|---|---|
| Xu et al. | Return function (γ, λ) | Meta-gradient on consecutive batches |
| Sutton et al. | Action granularity | Options framework (temporal abstraction) |
| Dossa et al. | Input modality | GW cycle consistency (cross-modal transfer) |

**Implementation:** `scripts/meta_gradient_rl.py`
- Meta-gradient adaptation of γ, λ, exploration rate, strategy weights
- Hierarchical options with intra-option value learning
- Cross-domain transfer matrix (Pearson correlation of strategy success rates)
- Wired into heartbeat postflight for continuous online adaptation

**Connection to existing Clarvis systems:**
- `meta_learning.py`: Strategy effectiveness analysis (complementary — meta_learning does mining, meta_gradient_rl does gradient-based tuning)
- `world_models.py`: Hierarchical options provide temporal structure for world model predictions
- `attention.py`: Salience threshold in meta-params maps to GWT ignition threshold
- `absolute_zero.py`: Meta-gradient exploration rate informs AZR task difficulty targeting

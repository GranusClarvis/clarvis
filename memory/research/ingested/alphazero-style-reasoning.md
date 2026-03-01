# AlphaZero-style Reasoning (AZR) for Cognitive Agents

**Key Authors:** Silver, Hubert, Schrittwieser (DeepMind); Feng et al. (TS-LLM); Zhou et al. (LATS); Qi et al. (rStar); Chojecki (GVU framework)
**Key Works:** AlphaZero (Science, 2018), MuZero (Nature, 2020), AlphaProof (Nature, 2025), TS-LLM (2023), LATS (ICML 2024), rStar (ICLR 2025)
**Year Range:** 2017-2025

---

## Key Ideas

### 1. AlphaZero Core Architecture: Neural Network + MCTS Self-Play

Two-component system: (1) Neural network with policy head p(a|s) ("intuition") and value head v(s) ("positional judgment"), (2) MCTS that uses UCB formula `a* = argmax[Q(s,a) + c*P(s,a)*sqrt(N(s))/(1+N(s,a))]` to balance exploitation (high Q) with exploration (high P, low N). Self-play training loop: play games -> record (state, MCTS-improved policy pi, outcome z) -> train network to minimize `L = (z-v(s))^2 - pi^T*log(p(s)) + c||theta||^2` -> repeat. Starting from random initialization, surpassed world-champion programs in chess, shogi, and Go within 24 hours.

### 2. MuZero: Learned World Model Removes Need for Perfect Rules

Three neural functions: representation h(o)->s (encode observation to latent state), dynamics g(s,a)->(r,s') (predict next state + reward in latent space), prediction f(s)->(p,v) (policy + value from latent state). MCTS operates entirely in learned latent space -- no environment simulator needed. Only needs to predict planning-relevant quantities, not reconstruct full observations. Matched AlphaZero on Go/chess/shogi without knowing rules, set SOTA on 57 Atari games.

### 3. MCTS Applied to LLM Reasoning: Reasoning as Tree Search

Central analogy: board state = partial reasoning chain, legal move = next reasoning step, policy head = LLM's generation distribution, value head = estimated P(correct|partial chain), game outcome = answer correctness. Key systems:
- **TS-LLM** (2023): Separate learned value function (not LLM self-eval) for intermediate states, handles tree depth up to 64
- **MCTS Preference Learning** (2024): Decomposes instance-level rewards into step-level preference signals via MCTS look-ahead, Mistral-7B GSM8K +5.9%
- **LATS** (ICML 2024): Unifies reasoning + acting + planning, 92.7% HumanEval with GPT-4
- **rStar** (ICLR 2025): Mutual generation-discrimination self-play, LLaMA2-7B GSM8K 12.51%→63.91%

### 4. AlphaProof: Self-Play for Mathematical Theorem Proving

Autoformalization (Gemini translates problems to Lean 4) + AlphaZero-style RL (search over proof steps, verified by Lean type checker). Key innovation: Test-Time RL -- continues training on self-generated variants of the target problem at inference time. IMO 2024: solved 4/6 problems including hardest one (only 5 humans solved it).

### 5. The Variance Inequality: When Self-Play Works (GVU Framework)

Generator-Verifier-Updater decomposition. Self-improvement requires: `rho > (eta*L/2) * (rho^2 + 1/SNR(G) + 1/SNR(V))`. Key implications:
- **Verification quality dominates** -- strengthen the verifier, not the generator
- **Hallucination Barrier** -- when V~G (same model generates and judges), SNR collapses and self-improvement fails
- **Oracle verifiers** (game rules, type checkers, test suites) have sigma^2_V~0, always work
- **Ensemble verifiers** improve linearly: SNR(V_ensemble) = M * SNR(V_single)
- Explains why AlphaZero, AlphaProof work (oracle V) and naive self-critique fails

### 6. Test-Time Compute Scaling (System 2 Thinking)

o1/o3 embody AZR: more MCTS simulations = stronger play, applied as more thinking = better reasoning. System 1 = raw LLM forward pass (policy head alone). System 2 = LLM + search (full MCTS). The self-play loop makes System 2 learnable -- search generates training data that improves System 1 intuition, which makes search more efficient.

### 7. Self-Play SWE-RL: Software Engineering Application

One agent injects bugs, another fixes them. Test patches serve as oracle verifier. +10.4 points on SWE-bench Verified, consistently outperforming human-data baselines. Demonstrates AZR works for real-world code tasks.

---

## Application to Clarvis Architecture

| Clarvis Component | AZR Analogue | Gap |
|---|---|---|
| `clarvis_reasoning.py` (linear chains) | MCTS reasoning tree | No branching/backtracking |
| `clarvis_confidence.py` (scalar confidence) | Value head | No learned calibration function |
| `attention.py` (salience scoring) | Policy head | Fixed weights, not learned from outcomes |
| `heartbeat_preflight.py` (task selection) | MCTS root selection | Greedy single-pass, no look-ahead |
| `reasoning_chain_hook.py` + reflection | Self-play training loop | Reflection doesn't update reasoning priors |

### Implementation Idea 1: MCTS Task Planner

Replace greedy task selection in heartbeat_preflight.py with lightweight MCTS over task sequences (50 simulations). Each node = system state after completing N tasks. Value function trained on historical (task, outcome, PI_change) data from `performance_history.jsonl`. Even 20-50 simulations provide meaningful look-ahead for task ordering.

### Implementation Idea 2: Self-Play Reasoning Improvement

Tree-structured reasoning with branching (2-3 candidate steps per node). Self-play loop: record (chain, predicted_confidence, actual_outcome) -> replay failures generating alternative paths -> recalibrate confidence. STaR-style rationalization: when task fails, generate post-hoc chain that would have led to correct approach, use to update reasoning priors.

### Implementation Idea 3: Mutual Verification (rStar-inspired)

Exploit dual-layer architecture: Claude Code generates reasoning chains, MiniMax M2.5 evaluates independently. Only mutually-agreed chains get high confidence. Addresses Hallucination Barrier by doubling SNR(V). Use existing `data/calibration/predictions.jsonl` as ground truth for training verification quality.

---

**Key References:**
- Silver et al. (2018) AlphaZero: [arXiv:1712.01815](https://arxiv.org/abs/1712.01815)
- Schrittwieser et al. (2020) MuZero: [arXiv:1911.08265](https://arxiv.org/abs/1911.08265)
- Zelikman et al. (2022) STaR: [arXiv:2203.14465](https://arxiv.org/abs/2203.14465)
- Feng et al. (2023) TS-LLM: [arXiv:2309.17179](https://arxiv.org/abs/2309.17179)
- Zhou et al. (2024) LATS: [arXiv:2310.04406](https://arxiv.org/abs/2310.04406)
- Qi et al. (2024) rStar: [arXiv:2408.06195](https://arxiv.org/abs/2408.06195)
- DeepMind (2025) AlphaProof: [Nature](https://www.nature.com/articles/s41586-025-09833-y)
- Chojecki (2024) GVU Framework: [arXiv:2512.02731](https://arxiv.org/abs/2512.02731)

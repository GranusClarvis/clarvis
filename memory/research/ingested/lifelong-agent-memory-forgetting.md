# Lifelong Agent Memory — Forgetting Prevention & Replay

**Ingested**: 2026-03-01
**Status**: Implemented
**Sources**: arXiv:2504.01241, arXiv:2511.22367, arXiv:2602.02007

## Key Concepts

### 1. EWC — Elastic Weight Consolidation (Kirkpatrick 2017)
- **Core idea**: Protect critical parameters from catastrophic forgetting using Fisher information
- **Formula**: L(θ) = L_new(θ) + (λ/2) Σ_i F_i (θ_i - θ*_i)²
- **Fisher diagonal**: F_i = E[(∂L/∂θ_i)²] — squared gradient averaged across data
- **Bayesian view**: Posterior from old task becomes Gaussian prior for new task
- **Neuroscience**: Models synaptic consolidation — important synapses resist plasticity

### 2. SuRe — Surprise-Driven Prioritised Replay (arXiv:2511.22367)
- **Core idea**: Replay memories that the system "predicted poorly" (high NLL)
- **Surprise**: s(z) = -(1/T) Σ log p(z_t | z_<t) — mean negative log-likelihood
- **Buffer**: Fixed 2% capacity, equal per-task quotas, evict lowest-surprise
- **Dual-LoRA**: Fast learner (gradient descent) + Slow learner (EMA β=0.995)
- **Result**: +5 accuracy points over prior SOTA on LNT benchmark

### 3. Selection vs Integration Error (xMemory, arXiv:2602.02007)
- **Selection error**: Retrieved wrong/redundant memories (diversity failure)
- **Integration error**: Correct memories but failed to compose them (coverage gap)
- **Fano bound**: Max candidate set size ≤ 2^((B+1)/α) before selection degrades
- **Fix**: Hierarchical organization (themes/semantics/episodes) + uncertainty-gated expansion

## Implementation in Clarvis

### hebbian_memory.py — EWC Fisher Importance
- `compute_fisher()`: Scores all 1800+ memories by freq × uniqueness × impact
- Fisher score shields decay: `effective_decay /= (1 + λ·F_i)`, λ=5.0
- Recomputes max once per 24h, caches to `data/hebbian/fisher_importance.json`
- CLI: `python3 hebbian_memory.py fisher`

### dream_engine.py — SuRe Surprise Replay
- `compute_surprise()`: 4-component score (semantic novelty 35%, outcome 30%, confidence 20%, duration 15%)
- `select_episodes()`: 70% surprise-driven picks + 30% exploration
- Surprise scores logged in dream entries for analysis

### memory_consolidation.py — Error Decomposition
- `measure_retrieval_quality()`: Decomposes retrieval into selection/integration error
- Selection error = pairwise Jaccard redundancy in results
- Integration error = 1 - query concept coverage
- Tracks to `data/retrieval_errors.jsonl`, report via `retrieval_error_report()`
- CLI: `python3 memory_consolidation.py retrieval-errors`

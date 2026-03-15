# TARG: Training-Free Adaptive Retrieval Gating for Efficient RAG

**Paper:** arXiv:2511.09803 (Wang et al., Nov 2025)
**Reviewed:** 2026-03-14
**Relevance:** High — directly addresses Clarvis's weakest metric (Context Relevance = 0.481)

---

## Core Idea

TARG is a single-shot, training-free policy that decides **whether** to retrieve by measuring model uncertainty from a short prefix draft. No fine-tuning, no auxiliary heads, no multi-stage loops.

**Process:** Generate k=20 tokens via greedy decoding on the raw prompt (no retrieval context) → extract logits → compute uncertainty score → retrieve only if score exceeds threshold τ.

## Three Uncertainty Signals

| Signal | Formula | Best For |
|--------|---------|----------|
| **Entropy** | U_ent = (1/k) Σ H_t where H_t = -Σ π_t,j log π_t,j | Older/weaker models |
| **Margin** | U_margin = (1/k) Σ φ(g_t) where g_t = ℓ_t,(1) - ℓ_t,(2), φ(z) = exp(-z/β) | **Robust default** for instruction-tuned LLMs |
| **Small-N Variance** | N=3 stochastic prefixes at T=0.7, d_t = 1 - max_j p̂_t(j) | Conservative, budget-first |

**Key finding:** Entropy compresses as models get sharper (instruction-tuned), making margin the robust default. Variance is most conservative (retrieval as low as 0.1%).

## Results

On NQ-Open, TriviaQA, PopQA with Qwen2.5-7B and Llama-3.1-8B:

- **70-90% retrieval reduction** while matching or exceeding Always-RAG accuracy
- Margin on Llama TriviaQA: 83.8 EM at 0.1% retrieval (vs Always-RAG 67.6)
- Margin on Llama NQ-Open: 57.6 EM at 0.8% retrieval (vs Always-RAG 48.6)
- Always-RAG often *hurts* accuracy — noise injection degrades strong models

## Ablations

- **Prefix length k=20** is optimal (k=10 under-informs, k=30 over-triggers)
- **Retriever-agnostic:** gating ordering stable across E5 and BGE-m3
- **Threshold calibration:** τ = F_U^{-1}(1-ρ) from dev set empirical CDF — fast, stable

## Comparison with Related Work

| Method | Training? | Multi-stage? | Pre/Post retrieval? |
|--------|-----------|--------------|---------------------|
| **TARG** | No | No (single-shot) | Pre (gate) |
| Self-RAG | Yes (reflection tokens) | Yes | Both |
| FLARE | No | Yes (multi-query) | Pre (iterative) |
| CRAG | No | Yes (corrective) | Post (evaluator) |

TARG and CRAG are **complementary**: TARG gates pre-retrieval, CRAG evaluates post-retrieval.

## Limitations

- Evaluated only on English open-domain QA over Wikipedia
- Thresholds may shift with models/prompts/domains
- No evaluation on fact verification or long-form generation
- Requires access to model logits (not available via all APIs)

---

## Clarvis Application Ideas

### 1. Uncertainty-Augmented Retrieval Gate (Priority: High)
Current `retrieval_gate.py` uses pure keyword/tag heuristics. TARG's principle suggests augmenting with an uncertainty signal:
- **Practical adaptation:** Since Clarvis can't access Claude logits, use local Ollama/Qwen (4B) as a lightweight uncertainty probe — generate 3 short drafts (small-N variance), measure token agreement
- **Hybrid approach:** Keep heuristic gate as fast-path (NO_RETRIEVAL for obvious maintenance), add uncertainty check for borderline LIGHT vs DEEP decisions
- **Expected impact:** Reduce false-negative retrievals (tasks wrongly classified as NO_RETRIEVAL) and false-positive deep retrievals → higher Context Relevance

### 2. Threshold Auto-Calibration via PI
TARG's CDF-based threshold selection maps to Clarvis's existing RL-lite feedback loop (ADAPTIVE_RAG_PLAN Component 4). Use episode outcomes to calibrate the uncertainty threshold empirically, just as TARG uses dev-set CDF.

### 3. Context Relevance Boost (Weakest Metric: 0.481 → 0.75)
TARG's core insight: **retrieving when the model doesn't need it actively hurts accuracy**. This directly explains low Context Relevance — injecting brain memories into tasks that are self-contained dilutes the context. Better gating = only retrieve when genuinely needed = higher relevance of injected context.

### 4. Budget-Aware Gating
TARG's ρ parameter (target retrieval budget) could be adapted for Clarvis cost control — set a daily retrieval budget and let the gate auto-adjust threshold to meet it.

### 5. Integration Path
```
Current:  heuristic gate → brain.recall() → CRAG eval → context assembly
Proposed: heuristic gate → uncertainty probe → brain.recall() → CRAG eval → context assembly
                           (Ollama 3-draft)
```
Add ~3-5s for uncertainty probe (3x Qwen 4B drafts at ~7 tok/s each, k=20 tokens). Only triggers for tasks not already caught by keyword heuristics. Net time: +3-5s for borderline tasks, but saves 7.5s on correctly-gated NO_RETRIEVAL tasks that were previously misclassified.

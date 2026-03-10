# Influence-Guided Context Selection via Contextual Influence Value

**Paper**: arXiv:2509.21359 (Deng, Shen, Pei, Chen, Huang — SJTU, NeurIPS 2025)
**Date**: 2026-03-09
**Relevance**: Context Relevance metric (0.838), context_compressor MMR, brain recall filtering

## Core Idea

Reconceptualizes context quality assessment as **inference-time data valuation**. Instead of scoring contexts independently (cosine similarity, BM25), CI value measures each context's *marginal contribution* to generation quality:

```
φ_i(v) = v(C) - v(C \ c_i)
```

A positive CI means removing the context degrades output — keep it. Negative CI means it actively hurts — drop it. Near-zero means noise — safe to drop.

## Four Properties (vs existing approaches)

| Property | CI Value | Cosine Sim | MMR | RankGPT |
|---|---|---|---|---|
| Query-awareness | Yes (implicit) | Yes | Yes | Yes |
| List-awareness | Yes (marginal) | No | Partial (lambda) | No |
| Generator-awareness | Yes (feedback) | No | No | Partial |
| No hyperparameters | Yes (φ>0 rule) | No (top-k) | No (lambda+k) | No (k) |

**List-awareness** is the key differentiator: a context's value depends on what *else* is selected. Redundant contexts get zero marginal contribution even if individually relevant. This is strictly stronger than MMR's static diversity penalty.

## CSM Architecture (Context Selection Model)

Surrogate model that predicts CI values without requiring repeated LLM inference:

1. **Local layer**: BERT-uncased encodes each (query, context) pair → local embeddings
2. **Global layer**: Multi-head self-attention across all context embeddings → captures inter-context interactions
3. **Output**: MLP maps global embeddings → predicted CI scores

Two training modes:
- **CSM-st** (supervised): Oracle CI values as regression targets. Handles 78% near-zero class imbalance via downsampling + cross-instance data intervention + contrastive loss for hard samples.
- **CSM-e2e** (end-to-end): Uses Gumbel-Softmax for differentiable context selection. Dual loss: sufficiency (correct answers with selected contexts) + necessity (KL-divergence penalty for false positives).

## Results

Tested on 8 NLP tasks (NQ, TriviaQA, WebQA, HotpotQA, 2WikiMultiHop, FEVER, TruthfulQA, ASQA) with Llama3-8B and Qwen2.5-7B:

- **~15% average improvement** over standard RAG (top-10 all contexts)
- NQ: 42.53% vs 37.01% EM (+5.5 pts)
- HotpotQA: 47.53% vs 40.95% F1 (+6.6 pts)
- **Inference latency**: 253ms (CSM, n=10) vs 874ms (RankGPT) — **3.4x faster**
- Scales to n=50 contexts at 481ms vs RankGPT's 1437ms

## Key Statistical Insight

~78% of retrieved contexts have near-zero CI value (noise/padding). Only 3.4% have CI > 0.3 (strongly beneficial). **Most retrieval results contribute nothing to generation quality** — aggressive filtering works because the signal-to-noise ratio in retrieval is very low.

## Clarvis Application Ideas

### 1. Replace static MMR with marginal-contribution scoring (CONTEXT_ADAPTIVE_MMR_TUNING)
Current `context_compressor.py` uses MMR with static lambda. CI value's list-awareness subsumes MMR — it captures *actual* marginal contribution rather than a geometric diversity proxy. A lightweight version: after brain recall returns N results, score each by leave-one-out impact on a brief quality metric, keep only positive-contribution items.

### 2. Train a context scorer from postflight outcome data (CONTEXT_RELEVANCE_FEEDBACK)
Clarvis already records task outcomes in postflight. The CI framework shows how to use this as training signal: episodes where context was used → positive label; context present but not referenced → near-zero; context present and task failed → negative. This directly attacks Context Relevance (0.838 → target higher).

### 3. Brain recall noise filtering
The 78%-noise finding is likely true for ClarvisDB too — most of 10 search results per collection are padding. A simple heuristic: after vector search, do a fast second pass removing results whose removal doesn't change the top-1 answer (crude CI approximation). Could improve recall precision without changing ChromaDB.

### 4. Eliminate top-k tuning in context assembly
Currently brain search uses fixed n=10 per collection. CI's φ>0 rule suggests: retrieve more candidates (n=20), then keep only those with positive marginal contribution. Self-tuning context window size per query.

### 5. Generator-aware feedback loop for context quality
The CSM-e2e sufficiency/necessity dual loss maps to: "did Claude Code actually use this context?" (sufficiency) + "did including this context cause confusion or errors?" (necessity). Postflight already has enough signal to compute both.

## Relation to Weakest Metric

Context Relevance (0.838) is the weakest metric. This paper directly targets it: CI value provides a principled framework for measuring and improving which contexts help generation. The practical path is:
1. **Short-term**: Use leave-one-out heuristic in context_compressor to filter low-value contexts
2. **Medium-term**: Collect postflight outcome data per CONTEXT_RELEVANCE_FEEDBACK task
3. **Long-term**: Train a lightweight CSM-like scorer on accumulated outcome data

## Code

GitHub: [SJTU-DMTai/RAG-CSM](https://github.com/SJTU-DMTai/RAG-CSM)

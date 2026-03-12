# MacRAG: Multi-Scale Adaptive Context RAG

**Paper**: Lim et al., "MacRAG: Compress, Slice, and Scale-up for Multi-Scale Adaptive Context RAG" (arXiv:2505.06569, May 2025)
**Code**: github.com/Leezekun/MacRAG
**Researched**: 2026-03-11

## Core Problem

Existing RAG suffers from three failure modes: (1) imprecise retrieval from coarse chunks, (2) incomplete context coverage under constrained windows, (3) fragmented information from suboptimal context construction. These map directly to Clarvis's Context Relevance metric stalling at 0.838.

## Architecture: Compress → Slice → Scale-up

### Offline Pipeline (Index Time)
1. **Chunk**: Documents split into overlapping chunks (~400 tokens, 10-200 token overlap)
2. **Compress**: Each chunk summarized via LLM → compressed summary retaining core facts
3. **Slice**: Summaries further partitioned into fine-grained slices (~100 tokens, overlapping)
4. **Index**: Slices embedded and indexed with metadata (document_id, chunk_id, offsets)

Hierarchy: `Document → Chunk (400tok) → Summary → Slice (100tok)`

### Online Pipeline (Query Time)
1. **Slice retrieval**: Top-k₁ slices by dense similarity (finest grain = highest precision)
2. **Parent mapping**: Deduplicate slices → unique parent chunks (prevent redundancy)
3. **Re-ranking**: Cross-encoder (marco-miniLM) re-ranks chunks to fix fragmentation
4. **Scale-up**: Select top-(k₂×α) chunks, aggregate scores per document
5. **Neighbor merging**: For each ranked chunk, merge h-hop neighbors (h=0 or 1)
6. **Budget control**: Bounded by k₂, α, chunk dimensions

Key insight: Start fine (precision) → progressively widen (coverage).

### Reference Implementation Parameters
- Raw chunks: 1500 chars / 500 overlap
- Summary chunks: 450 chars / 300 overlap
- Top-k₁=100 (coarse), top-k₂=7 (fine)
- Upscaling factor α=4, neighbor hops h=1
- Embedding: E5 model, Index: FAISS

## Results

| Dataset | Baseline (LongRAG) | MacRAG | Gain |
|---------|-------------------|--------|------|
| HotpotQA (F1) | 66.20 | 68.52 | +3.5% |
| 2WikiMultihopQA (F1) | 65.89 | 73.19 | +11.1% |
| Musique (F1) | 43.83 | 50.09 | +14.3% |

- Biggest gains on multi-hop reasoning (exactly Clarvis's use case — multi-collection queries)
- 38% faster retrieval than RAPTOR (0.23s vs 0.37s)
- 8.19% less context consumed than LongRAG (efficiency + quality)

### Ablation Highlights
- Neighbor merging: +1.3-4.4% F1 (critical for multi-hop)
- Scale-up factor α: robust across {2,3,4}
- Compression: +7.2% precision gain over raw slices
- Cross-encoder re-ranking: essential for defragmentation

## Clarvis Application: 5 Ideas

### 1. Phased Multi-Scale Retrieval in context_compressor.py
**Current**: Single-scale — `brain.recall(query, n=N)` returns flat results, then MMR reranks.
**Proposed**: Three retrieval scales:
- **Fine**: Query memory slices (sub-memory segments) for precision
- **Medium**: Expand to full parent memories
- **Coarse**: Expand via 1-hop graph neighbors (synergy with RECALL_GRAPH_CONTEXT queue item)

Implementation: Add `multi_scale_recall()` to brain.py that chains slice→parent→neighbor expansion.

### 2. Offline Memory Compression Index
For memories >200 tokens, generate TF-IDF compressed summaries (no LLM needed — use existing `tfidf_extract()` from context_compressor.py), then slice into ~100-token overlapping segments. Store as auxiliary ChromaDB entries with `parent_memory_id` metadata. Query these for initial retrieval, expand to full memories for context.

Benefits: Better precision on initial retrieval (compressed = less noise), automatic deduplication via parent mapping.

### 3. Re-Ranking Stage via retrieval_eval.py
Already have `score_result()` with composite scoring (0.50 semantic + 0.25 keyword + 0.15 importance + 0.10 recency). Currently only used for evaluation/classification, not in the hot path. Wire it as a re-ranking stage between initial retrieval and MMR — similar to MacRAG's cross-encoder step.

Fastest path to improvement: Already built, just needs wiring.

### 4. Adaptive Budget Control via Retrieval Gate
Use `retrieval_gate.py` tiers to parameterize expansion:
- **LIGHT**: α=2, h=0 (no neighbor expansion)
- **DEEP**: α=4, h=1 (full neighbor expansion)

Connects retrieval_gate tier → multi_scale_recall parameters → context budget.

### 5. Neighbor Merging = Graph Context Expansion
MacRAG's h-hop neighbor merging is conceptually identical to the existing RECALL_GRAPH_CONTEXT queue item. The graph already has 102k+ edges. Merging these two tasks: implement MacRAG-style neighbor expansion as the mechanism for graph context expansion.

## Implementation Priority (Fastest Path to Context Relevance 0.90+)

1. **Wire retrieval_eval.py re-ranking into recall path** — zero new code, biggest bang (RETRIEVAL_EVAL_WIRING queue item)
2. **Add 1-hop graph neighbor expansion** — already have edges (RECALL_GRAPH_CONTEXT queue item)
3. **Build memory slice index** — new auxiliary collection, TF-IDF compression (CONTEXT_MULTI_SCALE_RETRIEVAL queue item)
4. **Adaptive expansion parameters** — connect retrieval_gate tiers to expansion config

Steps 1+2 are low-risk, high-impact. Steps 3+4 are the full MacRAG adaptation.

## Connection to Weakest Metric

Context Relevance = 0.838 (target: 0.90+). MacRAG directly targets this via:
- Fine-grained initial retrieval → higher precision (less irrelevant context)
- Adaptive expansion → coverage without dilution
- Re-ranking → fragmentation repair
- Budget control → only relevant context in window

The +14.3% F1 improvement on Musique (multi-hop) suggests significant headroom for Clarvis, which regularly performs multi-hop cross-collection queries.

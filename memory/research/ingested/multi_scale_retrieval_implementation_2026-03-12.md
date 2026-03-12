# Multi-Scale Retrieval for Context Relevance 0.90+: Implementation Blueprint

**Papers**: MacRAG (arXiv:2505.06569), FunnelRAG (NAACL 2025, arXiv:2410.10293), A-RAG (arXiv:2602.03442)
**Prior note**: `ingested/macrag_multi_scale_retrieval_2026-03-11.md` (architecture + 5 ideas)
**Researched**: 2026-03-12
**Purpose**: Concrete implementation blueprint synthesizing 3 papers into Clarvis adaptation

## Key Numbers from Papers

| Paper | Architecture | Best Gain | Time Cost | Key Insight |
|-------|-------------|-----------|-----------|-------------|
| MacRAG | slice→chunk→doc, bottom-up expansion | +14.3% F1 (Musique multi-hop) | 38% faster than RAPTOR | Compression before indexing +7.2% precision |
| FunnelRAG | cluster→doc→passage, top-down narrowing | +3.93% EM (Llama3) | 40% faster (2.97s vs 5.25s) | Cheap BM25 first, expensive reranker only on survivors |
| A-RAG | keyword+semantic+chunk_read, agent-selected | 94.5% HotpotQA | Comparable or lower tokens | Agent decides granularity per query |

## Current Clarvis Retrieval Path (Single-Scale)

```
query → route_query() → collections → brain.recall(query, n=N)
  → parallel ChromaDB queries (cosine similarity) per collection
  → ACT-R scoring + attention boost (hooks)
  → sort by _actr_score or distance+importance fallback
  → return top-N results (flat list)
```

**Weaknesses** (why Context Relevance stalls at 0.838):
1. **No granularity hierarchy** — all memories treated as equal-sized units
2. **No re-ranking** — retrieval_eval.py exists but not wired into hot path
3. **No neighbor expansion** — 103k graph edges unused at query time
4. **Fixed retrieval budget** — same N regardless of query complexity
5. **No compression index** — long memories dilute retrieval precision

## Proposed 3-Tier Multi-Scale Architecture

### Tier 1: Fine-Grained Precision (Slices)
**What**: For memories >200 tokens, generate TF-IDF compressed summaries (~100 tokens) stored as `compressed_summary` metadata field in ChromaDB. Initial retrieval queries embeddings of compressed text.
**Why**: MacRAG ablation shows +7.2% precision from compression. Compressed = less noise = better cosine match.
**How**:
- Batch job: iterate memories, compute `tfidf_extract(doc, ratio=0.3)`, store as metadata update
- At query time: first pass uses compressed summaries for initial top-k₁ retrieval
- No new collection needed — just add metadata field to existing memories
**Effort**: Medium. Batch script + recall() modification.

### Tier 2: Full Memory Expansion (Parent Mapping)
**What**: After Tier 1 retrieval, expand compressed results to full parent memories. Deduplicate (same memory matched via multiple slices).
**Why**: MacRAG's parent mapping prevents redundancy while recovering full context.
**How**:
- Map compressed-match IDs back to full memory documents
- Dedup by memory ID (ChromaDB already stores this)
- Re-rank expanded results using retrieval_eval.py's `score_result()` composite scorer
**Effort**: Low. Wire existing retrieval_eval.py scorer.

### Tier 3: Graph Neighbor Expansion (Breadth)
**What**: For top-k₂ results after re-ranking, fetch 1-hop graph neighbors. Include as lower-weight "context expansion" entries.
**Why**: MacRAG's neighbor merging gives +5-10% F1 on multi-hop. Clarvis has 103k edges ready.
**How**:
- `brain.get_related(memory_id, depth=1)` already exists
- Append neighbors with a 0.5x weight penalty (they're context, not direct matches)
- Budget cap: max 3 neighbors per result, total expansion ≤ 2x original results
**Effort**: Low. brain.recall() already has `include_related=True` parameter.

### Adaptive Scale-Up (Retrieval Gate Integration)
**What**: Use retrieval_gate.py tiers to parameterize expansion:
- **SKIP**: No retrieval (gate says "don't bother")
- **LIGHT**: Tier 1 only (precision, no expansion) — simple factual queries
- **DEEP**: Tiers 1+2+3 (full expansion + re-ranking + neighbors) — multi-hop, complex queries
**Why**: A-RAG shows agent-selected granularity outperforms fixed strategies. FunnelRAG shows 40% time savings from progressive narrowing.
**How**: retrieval_gate.py already classifies queries. Map tier → expansion parameters:
```python
EXPANSION_PARAMS = {
    "SKIP": {"n_initial": 0, "rerank": False, "neighbors": 0},
    "LIGHT": {"n_initial": 10, "rerank": False, "neighbors": 0},
    "DEEP": {"n_initial": 20, "rerank": True, "neighbors": 3, "alpha": 3},
}
```
**Effort**: Low. Config mapping + if/else in recall path.

## Implementation Order (4 Increments)

### Increment 1: Wire Re-Ranking (0 new code, biggest bang)
- Wire `retrieval_eval.py`'s `score_result()` into `brain.recall()` as a `_recall_scorer` hook
- Already registered via hook pattern — just implement the registration
- **Directly addresses**: retrieval fragmentation (MacRAG's cross-encoder equivalent)
- **Queue item**: RETRIEVAL_EVAL_WIRING

### Increment 2: Graph Neighbor Expansion (low risk)
- In `brain.recall()`, when `include_related=True`, fetch 1-hop neighbors for top-5 results
- Weight neighbors at 0.5x and append to results
- Cap total expansion at 2x original `n`
- **Directly addresses**: multi-hop coverage (MacRAG's h-hop merging)
- **Queue item**: RECALL_GRAPH_CONTEXT

### Increment 3: Compressed Summary Index (medium effort)
- Batch script: compute `tfidf_extract()` for memories >200 tokens, store as metadata
- Modify initial retrieval to prefer compressed matches, expand to full after
- **Directly addresses**: retrieval precision (MacRAG's slice indexing)
- **Queue item**: CONTEXT_MULTI_SCALE_RETRIEVAL (this item)

### Increment 4: Retrieval Gate Parameterization
- Map gate tiers to expansion parameters
- LIGHT queries skip re-ranking and neighbors (faster)
- DEEP queries get full expansion (better)
- **Directly addresses**: adaptive budget control (A-RAG + FunnelRAG progressive narrowing)

## Expected Impact on Context Relevance

| Component | Estimated CR Impact | Confidence |
|-----------|-------------------|------------|
| Re-ranking (Increment 1) | +0.02-0.04 | High (already built, just wiring) |
| Graph neighbors (Increment 2) | +0.02-0.03 | High (103k edges, +5-10% F1 in papers) |
| Compressed index (Increment 3) | +0.01-0.02 | Medium (needs batch + recall change) |
| Adaptive gate (Increment 4) | +0.01-0.02 | Medium (prevents dilution on simple queries) |
| **Combined** | **+0.06-0.11** | Moderate (0.838 + 0.06 = 0.90+ target) |

## Key Design Decisions

1. **No new ChromaDB collection** — store compressed summaries as metadata, not separate collection. Avoids brain bloat and sync issues.
2. **No LLM compression** — use existing `tfidf_extract()` (zero cost, already proven in context_compressor.py). MacRAG uses LLM compression but our budget doesn't allow it per-memory.
3. **Hook-based integration** — all 4 increments wire into existing hook registries (`_recall_scorers`, `_recall_boosters`). No brain.py core refactor needed.
4. **Backward compatible** — `include_related=False` (default) preserves current behavior. Multi-scale is opt-in via parameter or gate tier.

## Connection to Weakest Metric

Context Relevance = 0.838 (target: 0.90+). This is the weakest metric. The 4-increment plan directly targets it:
- Precision: compressed index reduces noise in initial retrieval
- Coverage: graph neighbors fill multi-hop gaps
- Quality: re-ranking defragments results
- Efficiency: gate-based adaptive expansion prevents context dilution

The +14.3% F1 improvement MacRAG achieves on multi-hop (Musique) is directly analogous to Clarvis's cross-collection queries, suggesting significant headroom.

## References

- MacRAG: [arXiv:2505.06569](https://arxiv.org/abs/2505.06569) — Compress, Slice, Scale-up
- FunnelRAG: [arXiv:2410.10293](https://arxiv.org/abs/2410.10293) — Coarse-to-Fine Progressive Retrieval (NAACL 2025)
- A-RAG: [arXiv:2602.03442](https://arxiv.org/abs/2602.03442) — Hierarchical Retrieval Interfaces (Feb 2026)

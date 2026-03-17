# Reconstructing Context: Advanced Chunking Strategies for RAG

**Paper**: Merola & Singh, "Reconstructing Context: Evaluating Advanced Chunking Strategies for Retrieval-Augmented Generation" (arXiv:2504.19754, ECIR 2025 Workshop)
**Related**: Günther et al., "Late Chunking: Contextual Chunk Embeddings" (arXiv:2409.04701)
**Date researched**: 2026-03-16

## Core Problem

Traditional fixed-size chunking fragments document context — each chunk is embedded in isolation, losing semantic relationships with surrounding text. This directly degrades retrieval relevance because chunk embeddings fail to capture document-level meaning.

## Two Solutions Compared

### Late Chunking (embed-then-chunk)
- **Method**: Pass entire document through a long-context embedding model first. Then segment the token-level embeddings into chunks and apply mean pooling per chunk.
- **Key insight**: Every chunk embedding "knows about" the full document because the transformer's attention already mixed global context into each token.
- **Pros**: No LLM calls needed. ~30 min for NFCorpus. No extra VRAM beyond the embedding model. Works with any long-context embedding model (Jina-V3, Stella-V5).
- **Cons**: Slight relevance drop vs contextual retrieval (~2-3% NDCG). Requires long-context embedding model.
- **Best results**: Stella-V5 (131K context) on MSMarco: NDCG@5=0.630.

### Contextual Retrieval (Anthropic, 2024)
- **Method**: After chunking, prepend an LLM-generated summary of the full document to each chunk before embedding. Then combine with BM25 rank fusion (4:1 dense:sparse) and cross-encoder reranking (Jina Reranker V2).
- **Key insight**: Explicitly reconstructs lost context by having an LLM describe each chunk's role within the document.
- **Pros**: Best semantic coherence. NDCG@5=0.317 vs late chunking's 0.309 on NFCorpus.
- **Cons**: ~20GB VRAM for contextualization. 4x embedding time for dynamic segmentation. Expensive at scale.

## Quantitative Results (NFCorpus, Jina-V3)

| Method | NDCG@5 | MAP@5 | NDCG@10 |
|--------|--------|-------|---------|
| Contextual Rank Fusion | 0.317 | 0.146 | 0.308 |
| Late Chunking | 0.309 | 0.143 | 0.294 |
| Traditional (early chunk) | 0.312 | 0.144 | 0.295 |

Key: contextual > traditional > late on some metrics, but late chunking shines with larger models (Stella-V5: late 0.445 vs early 0.443 NDCG@5).

## Additional Findings

- **Context cliff at ~2500 tokens**: Response quality drops sharply when chunks exceed this size (Jan 2026 analysis).
- **Sentence chunking ≈ semantic chunking** up to ~5000 tokens at fraction of cost.
- **Cross-granularity retrieval** (2026 frontier): retrieve at multiple chunk sizes, fuse results — combines fine-grained precision with coarse-grained context.
- **Segmentation matters**: Topic-based dynamic segmentation (Topic-Qwen) costs 4x but doesn't always improve over fixed-size.

## Clarvis Application — Context Relevance (0.387→0.75)

### Current State
- `clarvis/context/assembly.py` uses sentence-level splitting (`_split_sentences`) and DyCP section pruning.
- Brain search returns memories as isolated text blobs — no document-level context enrichment.
- Context relevance is measured per-section but chunk quality is not addressed upstream.

### Actionable Ideas

1. **Lightweight contextual enrichment for brain results**: When brain search returns a memory, prepend its collection name + related memories (graph neighbors) as context header before inclusion in the brief. This is a poor-man's contextual retrieval that costs zero LLM calls — we already have graph edges.

2. **Cross-granularity retrieval for brain search**: Search at both the individual memory level AND episode level (coarser grain), then fuse results. Episode summaries provide document-level context that individual memories lack.

3. **Chunk size discipline**: Keep context brief sections under 2500 tokens (the context cliff). Current TIER_BUDGETS already enforce this (max 150 tokens per section) — validate this holds after assembly.

4. **Late-chunking principle for episodic memory**: When encoding episodes, embed the full episode narrative first (via the embedding model), then extract per-section embeddings. This preserves episode-level context in each stored chunk.

5. **Rank fusion for spotlight sections**: Combine dense brain search with keyword overlap scoring (like BM25) at 4:1 weighting before including in brief. The paper shows this consistently improves over dense-only retrieval.

### Priority Assessment
Ideas 1 (graph-neighbor enrichment) and 2 (cross-granularity search) are highest ROI — they improve chunk quality at the formation layer with zero LLM cost, directly targeting the 0.387→0.75 context relevance gap. Ideas 3-5 are complementary refinements.

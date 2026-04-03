# Retrieval Optimization

Date: 2026-04-03
Topic: Retrieval optimization for dense retrieval / RAG systems

Recent retrieval research is converging on a simple idea: first-stage embedding search is no longer enough; quality improves when the system injects richer ranking signals before and after retrieval. Three useful patterns emerged. First, Reciprocal Nearest Neighbors (RNN) improves dense retrieval by using document-to-document structure, not just query-to-document distance. The EMNLP 2023 paper shows RNN helps both during training (evidence-based label smoothing to reduce false-negative damage) and during post-retrieval reranking. Second, PairDistill (EMNLP 2024) argues that pointwise distillation from rerankers is too coarse: pairwise comparisons teach the retriever finer distinctions between similarly relevant passages. Distilling pairwise relevance from a strong reranker produced state-of-the-art gains across benchmarks. Third, hybrid retrieval pipelines remain pragmatically strong: combine sparse lexical retrieval, dense semantic retrieval, reciprocal-rank fusion, and a late cross-encoder reranker. The practical implication for ClarvisDB is that retrieval optimization should be layered, not monolithic. Rather than only swapping embedding models, Clarvis should add: (1) hybrid BM25+dense candidate generation, (2) lightweight fusion, (3) reranking, and (4) evaluation on benchmarked query-doc pairs. The deeper lesson is that retrieval quality depends as much on supervision, candidate diversity, and post-processing as on embedding geometry itself.

Sources:
- https://aclanthology.org/2023.emnlp-main.665/
- https://arxiv.org/abs/2410.01383
- https://lite.duckduckgo.com/lite/?q=hybrid+search+reranking+retrieval+optimization+RAG+paper

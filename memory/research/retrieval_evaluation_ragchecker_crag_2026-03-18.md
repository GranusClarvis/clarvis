# Research — Retrieval Evaluation via RAGChecker + CRAG

Date: 2026-03-18

Topic: Retrieval optimization through diagnosis and corrective control

Key sources reviewed:
- https://arxiv.org/abs/2408.08067 — "RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation"
- https://github.com/amazon-science/RAGChecker — framework README and metric taxonomy
- https://arxiv.org/abs/2401.15884 — "Corrective Retrieval Augmented Generation"

Summary:

The useful shift is from “retrieve better” to “measure failure modes, then adapt retrieval policy.” RAGChecker turns RAG evaluation into a component diagnosis problem: retriever metrics such as claim recall and context precision tell whether the right evidence was fetched, while generator metrics such as context utilization, hallucination, faithfulness, self-knowledge, and noise sensitivity show whether the model used that evidence well. This matters for Clarvis because a low-quality answer can come from several distinct faults: poor recall, noisy context, or correct retrieval that the generator ignores. CRAG complements this by adding a lightweight retrieval evaluator at inference time. Instead of trusting every retrieval pass, it scores confidence, escalates to broader search when quality is low, and selectively filters or decomposes documents before generation. The joint lesson is architectural: retrieval should be a gated control loop, not a one-shot lookup. For Clarvis, the immediate implementation path is to log RAGChecker-style metrics around brain.recall(), classify failures by stage, and trigger corrective retry or graph expansion only when confidence is weak. That should improve context relevance without blindly increasing retrieval depth.
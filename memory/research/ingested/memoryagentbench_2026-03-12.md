# MemoryAgentBench — Evaluating Memory in LLM Agents (ICLR 2026)

**Paper**: arXiv:2507.05257 | Hu, Wang, McAuley (UCSD)
**Code**: github.com/HUST-AI-HYZ/MemoryAgentBench
**Data**: huggingface.co/datasets/ai-hyz/MemoryAgentBench
**Ingested**: 2026-03-12

## Core Framework: 4 Memory Competencies

1. **Accurate Retrieval (AR)**: Retrieve dispersed facts from long dialogue history. ClarvisDB: STRONG (composite scoring, 3-tier verdict, strip refinement, adaptive retry).
2. **Test-Time Learning (TTL)**: Learn new tasks from conversation examples. ClarvisDB: PARTIAL (EMA feedback, threshold suggestions, but no online parameter tuning).
3. **Long-Range Understanding (LRU)**: Holistic synthesis, not just fact lookup. ClarvisDB: MODERATE (causal DAG, Hebbian co-activation, but no spreading activation or multi-hop retrieval).
4. **Conflict Resolution (CR)**: Detect/resolve contradictions, prioritize newer facts. ClarvisDB: MINIMAL (zero contradiction detection, only time-based decay).

## Key Findings

- **No agent masters all 4 competencies** — each excels at 1-2 and fails elsewhere.
- **RAG dominates AR** (NV-Embed-v2: 83% RULER-QA) **but fails at LRU** (20.7%) — retrieves fragments, not holistic understanding. ClarvisDB has same structural limitation.
- **Multi-hop conflict resolution: ALL methods ≤6% accuracy.** This is the hardest unsolved problem.
- **Commercial memory agents (Mem0, Cognee) perform poorly** — factual extraction discards context. ClarvisDB's full-text storage is better.
- **Long-context models dominate TTL** (87-97%) **and LRU** (28-52% summary F1) — raw context beats retrieval for integration tasks.
- **Graph-augmented RAG (HippoRAG-v2, GraphRAG)** doesn't solve CR or LRU — better at AR only.

## Datasets

| Dataset | Tokens | Competency | Metric |
|---------|--------|------------|--------|
| RULER-QA | 197-421K | AR | SubEM |
| NIAH-MQ | 448K | AR | Recall |
| ∞-Bench-QA | 183K | AR | ROUGE |
| LongMemEval | 355K | AR | Model-based |
| EventQA (new) | 534K | AR+LRU | 6-way MC |
| FactConsolidation (new) | 262K | CR | SubEM |
| BANKING77/CLINC150/NLU/TREC | ~103K | TTL | Accuracy |
| Movie Rec (Redial) | 1.44M | TTL | Recall@5 |
| ∞-Bench-Sum | 172K | LRU | ROUGE |

## ClarvisDB Gap Analysis & Action Items

### Critical Gap: Conflict Resolution (Priority: HIGH)
- Zero contradiction detection in current system
- No certainty/source-credibility scores on memories
- No explicit update/correction mechanism (only delete+re-add)
- **Action**: Build contradiction detector in `memory_consolidation.py` — compare new memory embeddings against existing, flag semantic conflicts (high similarity + opposite sentiment/negation). Maps to [AMEM_MEMORY_EVOLUTION] queue item.

### Medium Gap: Long-Range Understanding
- Graph exists but isn't used in recall pipeline for multi-hop
- `graph_expand` (just landed) helps but only does 1-hop
- No spreading activation through relationship graph
- **Action**: Extend `graph_expand` to k-hop with decay. Add summarization pass for large context sets.

### Low Gap: Test-Time Learning
- Feedback loop exists but suggestions require manual review
- No auto-application of threshold changes
- **Action**: After 100+ episodes with stable EMA, auto-apply threshold suggestions (with rollback mechanism).

## Benchmark Applicability to ClarvisDB

MemoryAgentBench could benchmark ClarvisDB directly:
- Adapt EventQA for episode causal chain evaluation
- Use FactConsolidation to test contradiction handling (currently would score ~0%)
- NIAH-MQ maps to multi-collection search (ClarvisDB's strength)
- Could create ClarvisDB-specific eval harness using their framework

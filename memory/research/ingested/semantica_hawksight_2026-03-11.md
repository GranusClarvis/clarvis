# Research: Hawksight-AI/Semantica — Semantic Layers, Context Graphs & Decision Intelligence

**Date**: 2026-03-11
**Source**: [github.com/Hawksight-AI/semantica](https://github.com/Hawksight-AI/semantica), [docs](https://hawksight-ai.github.io/semantica/)
**Version reviewed**: v0.3.0 (first stable release, 886+ tests)
**License**: MIT

## What It Is

Semantica is a 24-module Python framework (`pip install semantica`) for building semantic layers, context graphs, and decision intelligence systems with W3C PROV-O provenance. It's an **accountability layer** that sits atop existing agent frameworks (LangChain, LlamaIndex, AutoGen, CrewAI) — not a replacement.

Three-layer architecture:
1. **Input**: Governed ingestion (PDF, DOCX, HTML, CSV, web crawl, databases, Snowflake)
2. **Semantic Engine**: Entity/relation extraction, NER, reasoning engines, conflict detection, provenance tracking, deduplication, ontology management
3. **Output**: Knowledge graphs, embeddings, RDF/OWL/Parquet/AQL exports, vector stores (FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector)

## Key Ideas (5)

### 1. Decisions as First-Class Objects
Every decision is recorded with `category`, `scenario`, `reasoning`, `outcome`, `confidence`, and entity links. Full lifecycle: `record_decision()` → `add_causal_relationship()` → `find_precedents()` → `trace_decision_chain()` → `analyze_decision_impact()`. This is the single biggest gap in Clarvis — we track episodes (what happened) and reasoning chains (how we thought), but NOT discrete decisions with causal linkage.

### 2. Multi-Type Conflict Detection
Five conflict types: value (contradictory facts), type (incompatible categories), relationship (inconsistent edges), temporal (expired validity), and logical (rule violations). Uses Jaro-Winkler similarity + semantic matching. Clarvis has zero conflict detection in `brain.recall()` — contradictory memories coexist silently and surface based on embedding proximity alone.

### 3. Temporal Validity on Graph Nodes
Nodes/edges carry `valid_from`/`valid_until` windows. Weighted BFS with `min_weight` parameter filters stale paths. Clarvis edges have `created_at` but no expiry. Adding temporal validity would let graph traversal automatically exclude outdated relationships — important for evolving technical knowledge.

### 4. Declarative Reasoning Engines
Five reasoning engines (forward chaining, Rete network, deductive, abductive, SPARQL), all returning **explanation paths** not just answers. Most applicable to Clarvis: forward chaining rules for memory governance. Instead of procedural `cleanup_policy.py` logic, express rules declaratively: `IF contradicts_existing AND newer → flag_review`, `IF importance < 0.1 AND access_count == 0 AND age > 30d → auto_archive`.

### 5. W3C PROV-O Provenance Chain
Every fact links to its source document → extracted entity → applied ontology rule → reasoning step → final assertion. Full lineage is queryable. Clarvis tracks memory `source` (conversation, cron, research, manual) but nothing deeper — no record of which hook modified a score, why a memory was excluded from recall, or which edge was created by which operation.

## Architecture Comparison: Semantica vs Clarvis

| Dimension | Semantica | Clarvis |
|-----------|-----------|---------|
| **Memory model** | Knowledge graph + context graph + vector store | ChromaDB + graph (JSON/SQLite) |
| **Decision tracking** | First-class objects with causal chains | None (episodes record outcomes, not decisions) |
| **Conflict detection** | 5 types, automated | None |
| **Temporal validity** | valid_from/valid_until on nodes/edges | created_at only, no expiry |
| **Provenance** | W3C PROV-O, full lineage | Source field only |
| **Reasoning** | 5 explicit engines with explanation paths | Reasoning chains (tracking, not inference) |
| **Graph algorithms** | PageRank, betweenness, Louvain, Node2Vec, link prediction | BFS traversal, bulk cross-link, decay |
| **Entity extraction** | NER, relation extraction, triplet generation | None (memories are pre-formed text) |
| **Deduplication** | Blocking, semantic, hybrid strategies | Similarity-based consolidation |

## Clarvis Application — Actionable Items

### High-Value, Low-Effort (Steal Ideas, Don't Add Dependency)
1. **Decision event bus** (~2 sessions): Add lightweight `log_decision(type, reasoning, outcome)` calls at key points in `brain.py` store/recall paths. Store in `data/decisions.jsonl`. No Semantica dependency needed.
2. **Temporal edge validity** (~1 session): Add `valid_until` field to graph edge metadata in `clarvis/brain/graph.py`. Honor during `get_related()` traversal. Default: 90 days for `similar_to`, unlimited for `hebbian_association`.
3. **Basic conflict detection** (~1 session): In `brain.store()`, before storing, query for high-similarity existing memories (cosine > 0.90). If found and assertion direction differs, add `conflict_with` metadata linking them. Surface in recall results.

### Medium-Effort (Future Queue Items)
4. **Forward-chaining rules for cleanup_policy.py** (~2 sessions): Replace procedural cleanup logic with declarative IF/THEN rules evaluated against memory metadata. More maintainable and auditable.
5. **Graph algorithm enrichment** (~2 sessions): Add PageRank-based importance scoring to graph nodes (complement embedding-based importance). Would improve recall ranking for highly-connected memories.

### Not Worth Adopting
- Full Semantica as a dependency: too heavy (24 modules), overlapping vector store, different storage assumptions. Better to steal specific patterns.
- SPARQL/RDF export: no use case in Clarvis's local-only architecture.
- Enterprise compliance features: overkill for single-agent system.

## Context Relevance Connection

Context Relevance (0.838) is the weakest metric. Semantica's decision tracking pattern is relevant: if Clarvis recorded **why** specific memories were selected for context briefs (decision provenance), we could measure which selection criteria correlate with successful task outcomes. This is complementary to the RETRIEVAL_EVAL_WIRING and CONTEXT_RELEVANCE_FEEDBACK queue items — the decision journal would provide ground truth for tuning retrieval parameters.

## Brain Memories Stored

5 memories stored in `clarvis-learnings` (importance 0.80-0.85):
1. Semantica overview + decisions as first-class objects
2. Conflict detection types + gap in Clarvis
3. Temporal validity windows + edge metadata improvement
4. Reasoning engines + forward chaining for memory governance
5. Architecture comparison + decision journal proposal

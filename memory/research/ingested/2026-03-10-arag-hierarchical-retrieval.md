# A-RAG: Scaling Agentic RAG via Hierarchical Retrieval Interfaces

**Paper**: arXiv:2602.03442 (Feb 2026)
**Authors**: Ayanami et al.
**Code**: github.com/Ayanami0730/arag
**Date reviewed**: 2026-03-10

## Core Idea

A-RAG shifts RAG from algorithm-driven (single-shot retrieval) or workflow-driven (predefined multi-step) to **agent-driven** retrieval. The model itself decides what to retrieve, at what granularity, and when to stop — via a ReAct reasoning loop over three hierarchical retrieval tools.

## Three-Tool Hierarchy

| Tool | Granularity | Scoring | Clarvis Analog |
|------|-------------|---------|----------------|
| **keyword_search** | Exact lexical match | `Σ count(k, chunk) × \|k\|` (character-weighted frequency) | `brain.search()` with metadata keyword matching |
| **semantic_search** | Dense vector cosine similarity at sentence level | `v_i^T · v_q / (\|\|v_i\|\| · \|\|v_q\|\|)` | `brain.recall()` ChromaDB vector search |
| **chunk_read** | Full chunk content + adjacent ±1 chunks | Context tracker prevents re-reads | `RECALL_GRAPH_CONTEXT` — graph-neighbor expansion |

**Hierarchical index**: corpus → chunks → sentences → keywords. Each tool accesses a different level.

## Three Principles of Agentic Autonomy

1. **Autonomous Strategy**: Model dynamically chooses retrieval approach without fixed workflows or external rules
2. **Iterative Execution**: Multi-round retrieval adapting iteration count based on intermediate results (not preset steps)
3. **Interleaved Tool Use**: ReAct-pattern action→observation→reasoning; each tool call conditions on prior observations

## Key Results

| Benchmark | A-RAG (GPT-5-mini) | LinearRAG | Naive RAG | Token Reduction |
|-----------|---------------------|-----------|-----------|-----------------|
| HotpotQA | **94.5%** | 84.8% | ~77% | 2,737 vs 5,358 (49% fewer) |
| MuSiQue | **74.1%** | 62.4% | — | — |
| 2WikiMultiHopQA | **89.7%** | 87.2% | — | — |

- Scaling: 5→20 max steps yields ~8% improvement on MuSiQue-300
- Reasoning effort scaling (minimal→high): ~25% gains
- Stronger models scale better with A-RAG (GPT-5 > GPT-5-mini > GPT-4o-mini)

## Failure Analysis (Critical Insight)

- **82% of A-RAG errors** stem from reasoning chain mistakes (entity confusion: 40%), NOT retrieval failures
- Naive RAG: 50% of errors are retrieval-limited
- **Implication**: A-RAG shifts the bottleneck from retrieval to reasoning quality

## Clarvis Application — 5 Concrete Ideas

### 1. Map A-RAG tools to existing RETRIEVAL_GATE tiers
- `NO_RETRIEVAL` → skip (maintenance tasks)
- `LIGHT_RETRIEVAL` → keyword_search analog (brain.search with keyword matching, 2-3 collections)
- `DEEP_RETRIEVAL` → semantic_search + chunk_read analog (brain.recall all collections + graph-neighbor expansion)
- The A-RAG insight: don't hardcode the tier — let the agent reason about which tier to use

### 2. Context tracker pattern for deduplication
- A-RAG's chunk_read returns zero tokens for already-read chunks
- Map to `context_compressor.py` MMR deduplication — currently static lambda
- A-RAG suggests: track what's been retrieved this session, never re-retrieve

### 3. Iterative retrieval with query rewriting (RETRIEVAL_ADAPTIVE_RETRY)
- A-RAG's iterative execution maps directly to the planned corrective retry loop
- On INCORRECT verdict: rewrite query (TF-IDF keywords), broaden scope, retry
- A-RAG validates this approach: iterative > single-shot, especially for multi-hop queries

### 4. RECALL_GRAPH_CONTEXT as chunk_read analog
- A-RAG's chunk_read fetches adjacent chunks (±1) for context
- Clarvis equivalent: fetch 1-hop graph neighbors for retrieved memories
- Both serve same purpose: expand beyond the exact match to provide contextual understanding

### 5. Post-retrieval quality investment
- A-RAG's failure analysis shows reasoning quality > retrieval quality once retrieval is adequate
- After RETRIEVAL_GATE + RETRY land, focus should shift to `clarvis_reasoning.py` quality
- Entity disambiguation and reasoning chain coherence are the next bottleneck

## Related Work Connections

- **Corrective RAG (CRAG)**: External evaluator scores retrieval → 3 corrective actions (correct/incorrect/ambiguous). Clarvis `retrieval_eval.py` already implements this pattern.
- **Adaptive RAG**: Classifier routes queries to single-step vs iterative vs no-retrieval. Maps to RETRIEVAL_GATE 3-tier routing.
- **Self-RAG**: Model self-decides when retrieval is needed. A-RAG extends this with tool-level granularity.
- **Higress-RAG** (arXiv:2602.23374): Enterprise CRAG with adaptive routing + semantic caching. Caching idea applicable to Clarvis brain queries.

## Implementation Priority for Context Relevance 0.838→0.90+

Based on A-RAG findings, recommended implementation order:

1. **[RETRIEVAL_GATE]** — Biggest impact: skip unnecessary retrievals (saves time) + route complex queries to deep retrieval (improves relevance)
2. **[RECALL_GRAPH_CONTEXT]** — chunk_read analog: graph expansion provides contextual understanding beyond exact matches
3. **[RETRIEVAL_ADAPTIVE_RETRY]** — Iterative retry with query rewriting for failed retrievals
4. **[CONTEXT_ADAPTIVE_MMR_TUNING]** — A-RAG validates task-type-aware retrieval parameters
5. **[RETRIEVAL_RL_FEEDBACK]** — Long-term: learn optimal tier routing from outcomes

# Corrective RAG + Agentic RAG Patterns

**Date:** 2026-03-03
**Papers:**
- Yan et al. 2024 — "Corrective Retrieval Augmented Generation" (CRAG), arXiv:2401.15884
- Singh et al. 2025 — "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG", arXiv:2501.09136
- Related: Asai et al. 2024 — "Self-RAG" (ICLR 2024 oral), arXiv:2310.11511
- Related: Jeong et al. 2024 — "Adaptive-RAG" (NAACL 2024), arXiv:2403.14403

## Key Ideas

### 1. CRAG: Self-Corrective Retrieval (Yan et al. 2024)

Core insight: RAG fails silently when retrieved documents are irrelevant. CRAG adds a lightweight evaluator that grades retrieval quality and triggers corrective actions.

**Architecture:**
1. **Retrieval Evaluator** — Fine-tuned T5-large (0.77B params) scores each document's relevance to query
2. **Three-tier confidence classification:**
   - **Correct** (≥1 doc above upper threshold) → Refine with decompose-recompose
   - **Incorrect** (all docs below lower threshold) → Discard, trigger web search fallback
   - **Ambiguous** (mixed scores) → Combine internal refinement + external search
3. **Decompose-Then-Recompose** — Split documents into fine-grained "knowledge strips" via heuristic rules, score each strip against query, filter irrelevant strips, reassemble relevant ones
4. **Web Search Fallback** — Rewrite query into keywords (via LLM), search web, transcribe results, apply same strip refinement

**Results:** +7% accuracy over Self-RAG on PopQA, +5 FactScore on Biography generation. Key ablation: the evaluator + decompose-recompose contribute most; web search is fallback insurance.

### 2. Agentic RAG Taxonomy (Singh et al. 2025)

Six architectural patterns:
1. **Single-Agent Router** — One agent routes queries across multiple data sources
2. **Multi-Agent** — Specialized agents (SQL, semantic search, web, recommendations) work in parallel
3. **Hierarchical** — Strategic oversight agent directs subordinate task agents
4. **Corrective RAG** — Evaluate → refine → fallback cycle with 5 specialized agents
5. **Adaptive RAG** — Classify query complexity → route to appropriate retrieval depth
6. **Graph-Based** — Combine structured knowledge graphs with unstructured vector retrieval

Four agentic design patterns: reflection (self-critique), planning (task decomposition), tool use (API/external resource access), multi-agent collaboration (parallel specialization).

Evolution: Naive RAG (keyword/BM25, static) → Advanced RAG (dense embeddings, multi-hop) → Agentic RAG (dynamic strategy selection, autonomous multi-step reasoning, adaptive workflows).

### 3. Adaptive RAG (Jeong et al. 2024)

Query complexity classifier routes to three strategies:
- **No retrieval** — Simple factual queries the model can answer alone
- **Single-step** — Moderate questions needing one external lookup
- **Multi-hop** — Complex queries requiring multiple reasoning + retrieval rounds

Production results: 35% latency reduction, 28% API cost reduction, 8% accuracy improvement.

### 4. Self-RAG Reflection Tokens (Asai et al. 2024)

Model generates special reflection tokens during generation:
- **RET** — Should I retrieve? (on-demand retrieval decision)
- **REL** — Is this retrieved document relevant?
- **SUP** — Is my output supported by the evidence?
- **USE** — Is this output useful?

Key insight: On-demand retrieval (don't always retrieve) + per-document relevance judgment = better than always-retrieve-and-hope.

## Application to Clarvis Architecture

### Current State (Gap Analysis)

Clarvis's `brain.recall()` pipeline:
- Semantic distance → relevance: `1/(1+distance)` (purely geometric, no content evaluation)
- ACT-R scoring: 70% semantic + 30% activation + 5% importance
- MMR reranking in context_compressor: lambda=0.5 (relevance vs diversity)
- Hard threshold: distance > 0.8 rejected for procedures
- Min importance: 0.3 for most searches
- **No explicit "is this document actually relevant?" evaluation**
- **No corrective fallback when retrieval quality is poor**
- **No query complexity routing — all queries search all 10 collections equally**

### Integration Opportunities

**1. Retrieval Relevance Evaluator (Zero-LLM-Cost Implementation)**

Add a `RetrievalEvaluator` class to `clarvis/brain/search.py` or a new `retrieval_evaluator.py`:
```python
def evaluate_retrieval(query: str, results: list[dict]) -> str:
    """Classify retrieval quality as CORRECT/AMBIGUOUS/INCORRECT."""
    scores = []
    query_tokens = set(tokenize(query.lower()))
    for r in results:
        dist = r.get("distance", 1.0)
        semantic = 1.0 / (1.0 + dist)
        doc_tokens = set(tokenize(r["document"].lower()))
        overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
        combined = 0.6 * semantic + 0.3 * overlap + 0.1 * r.get("importance", 0.5)
        scores.append(combined)

    max_score = max(scores) if scores else 0
    if max_score >= 0.55:
        return "CORRECT"
    elif max_score <= 0.25:
        return "INCORRECT"
    return "AMBIGUOUS"
```

Triggered actions:
- CORRECT → Use results, apply knowledge strip refinement
- INCORRECT → Retry with keyword-extracted query, broaden collection set, log quality miss
- AMBIGUOUS → Use best results + retry with alternative query, merge

**2. Knowledge Strip Decomposition in context_compressor.py**

After MMR reranking, before context assembly:
```python
def decompose_recompose(query: str, memories: list[str]) -> list[str]:
    """Split memories into sentence strips, re-score, filter irrelevant."""
    strips = []
    for mem in memories:
        sentences = split_sentences(mem)
        for sent in sentences:
            score = keyword_overlap(query, sent) + semantic_sim(query, sent)
            if score > STRIP_THRESHOLD:
                strips.append(sent)
    return strips
```

This directly addresses the CONTEXT_RELEVANCE_FIX P0 task — irrelevant content within otherwise-relevant memories gets filtered out at sentence level.

**3. Query Complexity Router in brain.recall()**

Classify query before retrieval to select strategy:
- **Simple** (entity lookup, single fact) → Search 2-3 most relevant collections, top-3 results, skip spreading activation
- **Moderate** (how-to, procedure) → Search 5 collections with min_importance=0.3, top-5
- **Complex** (multi-hop, synthesis) → All 10 collections, enable spreading activation, top-10, allow multi-round retrieval

Classification can be heuristic: query length, presence of compound questions ("and", "how does X relate to Y"), domain keywords.

**4. Retrieval Quality Tracking Enhancement**

Extend existing `retrieval_quality.py` to track per-query confidence classification:
- Log CORRECT/AMBIGUOUS/INCORRECT ratio over time
- Feed into `parameter_evolution.py` for threshold auto-tuning
- Dashboard metric: "retrieval confidence rate" (% CORRECT)
- Alert if INCORRECT rate exceeds 30% (indicates embedding degradation or query drift)

## Concrete Implementation Plan

### Phase 1: Retrieval Evaluator (1 session, ~30 min)
- Add `retrieval_evaluator.py` to `scripts/` or `clarvis/brain/`
- Heuristic scorer: semantic_distance × keyword_overlap × importance
- Three-tier classification with tunable thresholds
- Hook into `brain.recall()` as post-retrieval step
- Log evaluations to `retrieval_quality.py`

### Phase 2: Knowledge Strip Refinement (1 session, ~20 min)
- Add `decompose_recompose()` to `context_compressor.py`
- Sentence-level splitting + per-strip relevance scoring
- Filter strips below threshold before context assembly
- Test with real preflight contexts

### Phase 3: Query Complexity Router (1 session, ~30 min)
- Add `classify_query_complexity()` to `brain.recall()` or separate module
- Route to collection subsets + result limits
- Track routing decisions in retrieval quality log

### Phase 4: Corrective Fallback Loop (1 session, ~20 min)
- On INCORRECT classification: auto-retry with keyword-extracted query
- On persistent INCORRECT: log as retrieval miss, skip context injection
- Avoid injecting bad context (better to have no context than misleading context)

## Priority Ranking

1. **Retrieval Evaluator** — Highest ROI, directly fixes CONTEXT_RELEVANCE_FIX P0
2. **Knowledge Strip Decomposition** — Complements evaluator, improves context density
3. **Query Complexity Router** — Performance optimization, reduces latency for simple queries
4. **Corrective Fallback** — Safety net, prevents hallucination from bad retrievals

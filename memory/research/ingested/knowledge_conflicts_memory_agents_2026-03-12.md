# Knowledge Conflicts in LLM Agent Memory — Detection & Resolution

**Date**: 2026-03-12
**Sources**: arXiv:2403.08319 (Xu et al. survey), arXiv:2509.25250 (Xu, contextual consistency)

## Taxonomy (from 2403.08319)

### 1. Context-Memory Conflict (CM)
Discrepancies between external context (retrieved docs, user input) and parametric knowledge.
- **Temporal Misalignment**: model trained on stale data
- **Misinformation Pollution**: external docs contain false info contradicting correct knowledge
- Behavioral: models show confirmation bias (favor memorized), but well-structured false context can override

### 2. Inter-Context Conflict (IC)
Inconsistencies among multiple retrieved documents.
- **Misinformation**: different docs make contradictory claims
- **Outdated Information**: retrieval returns both old and new versions of same fact
- Strong bias toward evidence aligning with parametric memory
- Position sensitivity: order of conflicting docs matters

### 3. Intra-Memory Conflict (IM)
Inconsistencies within the model's own knowledge (different answers to paraphrased queries).
- Training corpus bias, decoding strategy variance, knowledge editing side-effects
- 40% gap between probe accuracy and generation accuracy

## Detection Methods

### For ClarvisDB (vector memory, not LLM params):
The relevant conflict types map to:
- **Inter-context** → multiple stored memories contradict each other
- **Context-memory** → new input contradicts stored memories
- **Temporal** → old memories superseded by newer facts

### Practical Detection Heuristics
1. **Pairwise NLI scoring** (PCNN, XLM-RoBERTa): score contradiction between top-K retrieved results
2. **Rephrase-cluster-divergence**: query same concept multiple ways, flag if results diverge
3. **Entity-level fact tracking**: extract (entity, attribute, value) triples, detect value conflicts
4. **Temporal precedence**: newer memory with same entity+attribute supersedes older
5. **Embedding distance anomaly**: flag when semantically similar memories have very different content (high embedding sim + high text divergence = likely conflict)

## Resolution Strategies for ClarvisDB

### At remember() time (pre-hoc):
1. **Conflict gate**: before storing, query existing memories for same entities/topics
2. If semantic similarity > 0.85 but content diverges → flag for review
3. Apply temporal precedence: if new memory is more recent, mark old as superseded
4. Store conflict metadata: `{conflict_with: [ids], resolution: "temporal_precedence"}`

### At search/retrieval time (post-hoc):
1. **Contradiction-aware reranking**: penalize results that contradict each other
2. **Temporal recency boost**: S(M) = α·relevance + β·recency + γ·importance
3. **Source disentanglement**: when conflicts detected, present both with timestamps
4. **Majority voting**: if 3+ memories agree and 1 contradicts, demote the outlier

## Composite Utility Score (from 2509.25250)
```
S(M_i) = α·R_i + β·E_i + γ·U_i
where:
  R_i = e^(-λ·(t_now - t_i))    # exponential recency decay (λ=0.0005)
  E_i = cosine_sim(v_i, v_query) # semantic relevance
  U_i = importance score          # user/system utility signal
```

## Key Benchmarks
- Hybrid system (3-tier memory + decay): 1.2% contradiction rate vs 5.5% basic RAG vs 18.1% sliding window
- Task completion: 92.5% hybrid vs 81.4% basic RAG (500-turn test)
- MemoryAgentBench: contradiction resolution ≤6% across ALL methods — this is the hardest unsolved problem

## Actionable for ClarvisDB

### Priority 1: Conflict Detection in brain.remember()
- On store: query top-5 similar existing memories
- If cosine_sim > 0.85 AND text overlap < 0.3 → potential conflict
- Extract key entities/facts, compare for contradictions
- Log conflicts to `data/conflict_log.jsonl` for analysis

### Priority 2: Temporal Precedence in brain.search()
- Already have timestamps on all memories
- Add recency decay factor to retrieval scoring
- When two memories conflict, prefer the more recent one

### Priority 3: Contradiction-Aware Reranking
- After retrieval, pairwise check top-K results for contradictions
- Use lightweight NLI or simple heuristic (same entity, different value)
- Demote or annotate conflicting results

## Research Gaps
- No universal solution exists (survey conclusion)
- Cross-type conflict interactions unexplored
- Synthetic vs real-world conflict evaluation gap
- Current detection relies heavily on NLI models (compute cost)

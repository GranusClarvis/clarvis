# Agent Memory Frontiers Survey 2026

**Paper:** "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers"
**Author:** Pengfei Du
**Source:** arXiv:2603.07670 (2026)
**Ingested:** 2026-03-16

## Core Framework

Agent memory formalized as a **write–manage–read loop** coupled with perception and action:
- Action: πθ(xt, R(Mt, xt), gt) — reads from memory
- Update: Mt+1 = U(Mt, xt, at, ot, rt) — writes/manages memory
- U is NOT simple append — it summarizes, deduplicates, scores priority, resolves contradictions, deletes.

## Three-Axis Taxonomy

| Axis | Categories |
|------|-----------|
| **Temporal scope** | Working, Episodic, Semantic, Procedural |
| **Representational substrate** | Context-resident text, Vector-indexed, Structured (SQL/KG), Executable repos |
| **Control policy** | Heuristic, Prompted self-control, Learned (RL-optimized) |

## Five Mechanism Families

### 1. Context-Resident Compression
Sliding windows, rolling summaries, hierarchical summaries, task-conditioned compression. Pathology: summarization drift (details vanish by 3rd pass), attentional dilution.

### 2. Retrieval-Augmented Stores
Multi-granularity indexing (fine=individual calls, coarse=sessions), LLM-reformulated queries, Self-RAG gating, hybrid BM25+dense. Bottleneck: retrieval quality, not storage.

### 3. Reflective & Self-Improving Memory
Reflexion (verbal critiques → 91% HumanEval), Generative Agents (stream → reflection clusters → recency+relevance+importance scoring), ExpeL (contrastive trajectory rules), Think-in-Memory. **Risk:** false beliefs self-reinforce. Mitigation: citation-grounded reflection.

### 4. Hierarchical Virtual Context (MemGPT)
Main context (RAM) → Recall storage (disk) → Archival storage (cold). Memory management via function calls. Achilles heel: silent orchestration failures with no exception.

### 5. Policy-Learned Management (AgeMem)
5 memory ops as tools → 3-stage RL training (supervised → task-level RL → step-level GRPO). Discovers non-obvious tactics: proactive summarization, selective discard. Concerns: training cost, learned forgetting of safety info, poor transfer.

## Evaluation Benchmarks

| Benchmark | Year | Focus | Key Finding |
|-----------|------|-------|-------------|
| LoCoMo | 2024 | Long-term conversation | RAG lags humans on temporal/causal dynamics |
| MemBench | 2025 | Factual vs reflective | Separates effectiveness, efficiency, capacity |
| MemoryAgentBench | 2025 | 4 cognitive competencies | No system masters all four; forgetting worst |
| MemoryArena | 2026 | Multi-session agentic | Near-perfect LoCoMo → 40-60% here |

Four-layer metric stack: task effectiveness → memory quality → efficiency → governance.

## Key Empirical Findings

1. **Memory >> model selection**: Removing Generative Agents reflection → degeneration in 48h; Voyager skill loss → 15.3× slowdown
2. **Long context ≠ memory**: 200k token windows consistently underperform purpose-built memory
3. **RAG necessary but insufficient**: Bottleneck shifts to retrieval quality
4. **Forgetting least evaluated**: Only MemoryAgentBench tests it explicitly
5. **Cross-session coherence underexplored**: Most benchmarks are within-session

## Architecture Patterns

| Pattern | Design | Best For |
|---------|--------|----------|
| A: Monolithic | All memory in prompt | Short-lived, prototyping |
| B: Context + Retrieval | Working memory + external store | Production (recommended start) |
| C: Tiered + Learned | Multi-tier + RL orchestration | Complex long-horizon (graduate when data shows benefit) |

## ClarvisDB Gap Analysis

### What ClarvisDB Covers Well (relative to survey taxonomy)

| Survey Mechanism | ClarvisDB Implementation | Coverage |
|-----------------|-------------------------|----------|
| Vector-indexed store | ChromaDB + ONNX MiniLM, 10 collections, 3400+ memories | ✅ Strong |
| Temporal scope: Episodic | `clarvis-episodes` collection, episodic_memory.py | ✅ Strong |
| Temporal scope: Semantic | `clarvis-learnings`, `clarvis-preferences`, `clarvis-identity` | ✅ Strong |
| Temporal scope: Procedural | `clarvis-procedures`, tool_maker.py LATM extraction | ✅ Strong |
| Structured store (KG) | Graph with 134k+ edges (JSON + SQLite backends) | ✅ Strong |
| Reflective memory | clarvis_reflection.py (8-step pipeline), knowledge_synthesis.py | ✅ Moderate |
| Hierarchical context | Cognitive workspace (active/working/dormant buffers) | ✅ Moderate |
| Write-path filtering | Importance scoring, dedup in brain.optimize() | ✅ Moderate |
| Consolidation | memory_consolidation.py, brain optimize-full (decay + dedup + noise prune + archive) | ✅ Moderate |
| Hebbian learning | hebbian_memory.py (association strengthening) | ✅ Moderate |
| Architecture Pattern B | Context assembly + ChromaDB retrieval | ✅ Core design |

### Gaps & Missing Mechanisms

| Survey Mechanism | ClarvisDB Status | Priority | Effort |
|-----------------|-----------------|----------|--------|
| **Causally grounded retrieval** | Only semantic similarity; graph has edges but no causal traversal in retrieval path | HIGH — directly impacts Context Relevance (0.387) | MEDIUM |
| **Self-RAG gating** | context_relevance.py has relevance scoring but no retrieval-or-not gate | HIGH — would reduce noise in assembly | LOW |
| **Multi-granularity indexing** | Single granularity per collection (document-level) | MEDIUM — late chunking research (2026-03-16) addresses this | MEDIUM |
| **Contradiction detection** | No explicit contradiction resolution between memories | MEDIUM | MEDIUM |
| **Learned forgetting** | Only heuristic decay (time-based importance reduction) | MEDIUM — AgeMem approach is template | HIGH |
| **Spreading activation** | No priming of related memories on access | LOW — Hebbian is partial analog | MEDIUM |
| **Task-conditioned compression** | Context compressor exists but not task-aware query reformulation | MEDIUM — directly impacts Context Relevance | LOW |
| **Memory operation observability** | No comprehensive read/write/update logging for debugging | LOW | LOW |
| **Policy-learned control** | All memory ops are heuristic/prompted, no RL optimization | LOW (Pattern C: graduate when data shows benefit) | HIGH |
| **Foundation memory model** | N/A — requires massive cross-domain training data | FUTURE | N/A |

### Actionable Next Steps (ordered by impact on Context Relevance)

1. **Self-RAG gating in assembly** — Add retrieval-or-not decision before brain search. If query is self-contained (e.g., code generation from spec), skip retrieval. Uses existing `context_relevance.py` scoring. LOW effort, HIGH impact on reducing noise.

2. **Task-conditioned query reformulation** — Current brain search uses raw task text. Reformulate into typed sub-queries (factual, procedural, contextual) before searching. Maps to OpenViking's hierarchical retrieval pattern already in brain learnings. MEDIUM effort.

3. **Causal edge traversal in retrieval** — Graph has 134k+ edges. Add `get_causal_chain(memory_id, depth=2)` to retrieval path so assembly can include causally linked memories, not just semantically similar ones. MEDIUM effort, addresses the survey's #2 open challenge.

4. **Contradiction detection layer** — Before assembly, check if retrieved memories contradict each other. Flag for resolution or prefer newest. LOW effort for basic temporal versioning.

5. **Memory operation logging** — Add structured JSONL logging of every brain read/write with query, results, latency, caller. Enables the observability the survey identifies as the #1 reason demo-stage systems fail in production. LOW effort.

## Design Tensions (ClarvisDB specific)

The survey identifies 5 design tensions. ClarvisDB's current position:

| Tension | Current Position | Risk |
|---------|-----------------|------|
| Utility vs. Storage | Aggressive storage (3400+ memories) with periodic pruning | Bloat risk — brain_hygiene.py mitigates |
| Efficiency vs. Faithfulness | Fine-grained (per-memory) ONNX embeddings, sequential 10-collection search | Slow (7.5s avg) — parallel query optimization planned |
| Adaptivity vs. Stability | Reflection + learning with no external validation | Self-reinforcing errors possible |
| Governance vs. Performance | No deletion compliance, no access control | Acceptable for single-agent |
| Scalability vs. Interpretability | Hybrid vector + structured graph | Good balance |

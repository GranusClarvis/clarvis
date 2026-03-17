# OpenViking — Context Database for AI Agents

**Source**: https://github.com/volcengine/OpenViking (volcengine/ByteDance, 11.8k stars)
**Reviewed**: 2026-03-15
**Relevance to Clarvis**: High — directly comparable architecture (context DB for agents), many adoptable patterns

## Core Concept

OpenViking is an open-source context database that unifies Memory, Resources, and Skills into a single filesystem-paradigm store with semantic retrieval and progressive content loading. Instead of separate vector DBs, knowledge bases, and tool registries, everything lives in a hierarchical directory tree with built-in embeddings.

Key insight: **treat context like a filesystem, not a flat vector store**. This enables path-based navigation, hierarchical summarization, and natural organization that maps to how agents actually use context.

## Architecture

```
Client Layer (Python SDK / Rust CLI / HTTP API)
    ↓
Service Layer
  ├── FSService (filesystem ops)
  ├── SearchService (retrieval)
  ├── SessionService (conversation mgmt)
  ├── ResourceService (external knowledge)
  ├── RelationService (cross-links)
  └── DebugService (observability)
    ↓
Storage Layer
  ├── VikingFS (virtual filesystem over AGFS)
  │   └── AGFS backends: local FS, S3, in-memory
  └── Vector Index (embeddings + metadata only, NO content)
      └── Backends: local, Volcengine VikingDB, HTTP
```

**Dual-layer separation**: AGFS stores full content; vector index stores only URIs + embeddings + metadata. This allows independent scaling and means the vector DB stays small.

## Viking URI Scheme

```
viking://{scope}/{path}
```

Six scopes:
- `resources/` — external knowledge (docs, code, manuals)
- `user/{id}/memories/` — per-user learned context
- `agent/{space}/` — agent-level learning, config
- `session/{id}/` — ephemeral conversation state
- `queue/` — internal processing queue
- `temp/` — transient parsing artifacts

Special metadata files in each directory:
- `.abstract.md` — L0 (~100 tokens) for vector search/filtering
- `.overview.md` — L1 (~1-2k tokens) for reranking and context loading
- `.relations.json` — cross-references to other URIs
- `.meta.json` — structural metadata

## Three-Tier Content Loading (L0/L1/L2)

This is OpenViking's most impactful pattern:

| Layer | Tokens | Purpose | When to load |
|-------|--------|---------|-------------|
| **L0 (Abstract)** | ~100 | Vector search, quick filtering | Always (cheap) |
| **L1 (Overview)** | 1-2k | Reranking, context assembly, navigation | When relevant |
| **L2 (Detail)** | Unlimited | Full original content | Only when needed |

**Generation**: Bottom-up traversal. Files get summarized first, then child summaries aggregate into parent directory overviews/abstracts. Uses VLM for multimodal (images/video get text descriptions at L0/L1).

**Key benefit**: Agents can assess relevance from L0/L1 without loading full documents. Dramatically reduces token consumption vs. flat RAG.

## Hierarchical Retrieval Algorithm

Two-stage: Intent Analysis → Directory-Recursive Search

1. **Intent analysis** (LLM): examines session summary + recent messages + query → generates 0-5 TypedQuery objects (SKILL/RESOURCE/MEMORY)
2. **Global vector search**: finds starting directories via L0 embeddings
3. **Recursive directory traversal** via priority queue:
   - Score propagation: `0.5 * embedding_score + 0.5 * parent_score`
   - Convergence detection: stops after 3 unchanged top-k rounds
4. **Reranking**: optional semantic reranking of L1 content

This "directory-recursive retrieval" is much more structured than flat top-k vector search.

## Session Management & Memory Extraction

Session lifecycle: Create → add_message() → used() → commit()

On `commit()`:
1. **Archive**: messages copied to timestamped subdirectory
2. **Compress**: LLM generates structured summary (overview, key steps, intent, concepts, unfinished tasks)
3. **Memory extraction**: LLM analyzes session → generates candidates in 6 categories:
   - User: profile, preferences, entities, events
   - Agent: cases (learned examples), patterns (discovered tendencies)
4. **Deduplication**: vector similarity check → merge with existing or create new
5. **Persist**: TreeBuilder → AGFS → SemanticQueue → Vector Index

## Self-Evolving Pattern

The SemanticQueue + SemanticProcessor pipeline:
1. New content enters queue (file add, session commit, memory extraction)
2. SemanticProcessor does bottom-up traversal with concurrent LLM calls (semaphore-bounded)
3. Generates L0/L1 summaries for files, then aggregates into directory summaries
4. Vectorizes at both file and directory level
5. Parent directory summaries auto-update when children change

This means the knowledge base continually refines its own summaries and navigation structure.

## Evaluation Framework

- RAGAS integration for retrieval quality
- Metrics: retrieval success rate, avg contexts/question, latency, context relevance scores
- IO recording for storage layer performance
- LoCoMo benchmark support (long-context memory evaluation)
- SkillsBench for skill retrieval evaluation

## Comparison with ClarvisDB

| Aspect | ClarvisDB | OpenViking | Assessment |
|--------|-----------|------------|------------|
| **Storage** | ChromaDB (10 collections, flat) | VikingFS (hierarchical dirs) + Vector Index | OV's hierarchy is superior for organization |
| **Embeddings** | ONNX MiniLM (local, 140ms) | Multiple providers (Volcengine, OpenAI, Jina) | Clarvis: local-first is better for autonomy |
| **Content tiers** | None (full content always) | L0/L1/L2 progressive loading | **Adopt**: huge token savings potential |
| **Retrieval** | Flat semantic search per collection | Directory-recursive + intent analysis | **Adapt**: recursive structure useful |
| **Memory extraction** | Manual `remember()`/`capture()` | Auto-extract 6 categories from sessions | **Adopt**: structured extraction categories |
| **Relations** | Graph (JSON/SQLite, 134k edges) | `.relations.json` per directory | Clarvis graph is more powerful |
| **URI scheme** | Collection-based keys | `viking://scope/path` | **Adapt**: URI scheme for brain organization |
| **Session mgmt** | Working memory + episodes | Full session lifecycle with compression | OV more complete; Clarvis has pieces |
| **Eval** | PI benchmark (8 dimensions) | RAGAS + LoCoMo + SkillsBench | **Borrow**: RAGAS integration patterns |
| **Multimodal** | Qwen3-VL (local, limited) | VLM for L0/L1 generation | OV more integrated |

## Concrete Ideas for Clarvis

### 1. ADOPT: L0/L1/L2 Content Tiers for Brain Memories
**What**: Store a ~100-token abstract (L0) and ~1k-token overview (L1) alongside full content for each brain memory.
**Why**: Currently Clarvis loads full content for every search result. With L0/L1, context assembly can use abstracts for filtering and overviews for context — loading full content only when the task demands it. This directly addresses Context Relevance (0.387) by reducing noise.
**How**: Add `abstract` and `overview` fields to ChromaDB metadata. Generate on `remember()`/`capture()`. Use L0 for initial search, L1 for context assembly, L2 (full) only when explicitly needed.
**Effort**: Medium. Backwards-compatible addition to brain schema.

### 2. ADOPT: Structured Memory Extraction Categories
**What**: Auto-extract memories in 6 categories from session/episode data: user profile, preferences, entities, events, agent cases, agent patterns.
**Why**: Currently `capture()` stores unstructured text. Categorized extraction enables better retrieval (search within category) and deduplication (compare within same category).
**How**: Extend episodic_memory.py or conversation_learner.py to classify extracted memories. Map to brain collections or add category metadata.
**Effort**: Medium. Build on existing conversation_learner.py.

### 3. ADAPT: Directory-Recursive Retrieval for Brain Search
**What**: Instead of flat top-k per collection, implement a two-stage search: (1) identify relevant "topic clusters" via fast L0 search, (2) recursively expand within promising clusters.
**Why**: Current brain search queries all 10 collections independently. A recursive approach focuses on the most promising areas and follows relationships.
**How**: Use existing graph edges to define "neighborhoods". First search finds entry points, then expand via graph traversal with score propagation.
**Effort**: High. Requires graph-aware retrieval refactor.

### 4. ADAPT: Semantic Queue for Async Processing
**What**: Decouple memory ingestion from embedding/summarization. New memories enter a queue; a background processor generates embeddings, L0/L1 summaries, and cross-references asynchronously.
**Why**: Current `remember()` is synchronous (blocks on ONNX embedding). Async processing allows faster writes and richer post-processing (auto-summarize, auto-link).
**How**: Add a simple JSONL queue. Background cron or thread processes entries.
**Effort**: Low-Medium. Natural extension of existing cron infrastructure.

### 5. BORROW: RAGAS-Style Evaluation for Brain Quality
**What**: Implement ground-truth retrieval evaluation: store golden Q&A pairs, measure retrieval success rate, context relevance, and answer faithfulness.
**Why**: PI benchmark measures operational health but not retrieval quality directly. Need a way to measure "did we find the right memories for this task?"
**How**: Create a golden QA dataset from successful past tasks. Run periodic eval comparing brain search results to expected contexts.
**Effort**: Low. Build on existing performance_benchmark.py framework.

### 6. DISCARD: VikingFS Filesystem Abstraction
**Why not**: ClarvisDB is already well-integrated as ChromaDB + graph. Switching to a filesystem paradigm would require rewriting the entire brain. The URI scheme idea is useful but doesn't need VikingFS.

### 7. DISCARD: External Embedding Providers
**Why not**: Clarvis's local ONNX embeddings are a core strength (free, fast, no API dependency). No need to add Volcengine/OpenAI embedding providers.

### 8. DISCARD: Multi-tenant Architecture
**Why not**: Clarvis is single-agent. Multi-tenant isolation adds complexity without benefit.

## Summary of Actionable Items

| Priority | Item | Impact on CR | Effort |
|----------|------|-------------|--------|
| P1 | L0/L1 content tiers | High (reduce context noise) | Medium |
| P1 | RAGAS-style brain eval | Medium (measure quality) | Low |
| P2 | Structured memory categories | Medium (better retrieval) | Medium |
| P2 | Semantic async queue | Low-Med (richer processing) | Low-Med |
| P3 | Directory-recursive retrieval | High (focused search) | High |

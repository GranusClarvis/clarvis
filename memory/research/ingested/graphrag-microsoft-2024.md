# GraphRAG: From Local to Global (Microsoft, Edge et al. 2024)

Source: arXiv 2404.16130, github.com/microsoft/graphrag

## Core Innovation
GraphRAG addresses the fundamental limitation of vector-only RAG: inability to answer holistic/sensemaking queries that require reasoning across the entire corpus. Standard RAG retrieves individual relevant chunks but cannot synthesize themes, compare entities, or answer "What are the main X?" questions.

## Architecture: 6-Phase Indexing Pipeline
1. **TextUnit Composition** — Chunk documents (1200 tokens default)
2. **Document Processing** — Link documents to TextUnits for provenance
3. **Graph Extraction** — LLM extracts entities + relationships per chunk, with "gleanings" self-reflection loop to catch missed entities
4. **Graph Augmentation** — Hierarchical Leiden algorithm for community detection (C0=broadest to C3=most granular)
5. **Community Summarization** — Bottom-up LLM summaries: leaf communities from entity descriptions, higher levels from sub-community summaries
6. **Text Embedding** — Embed entity descriptions, TextUnits, community reports

## Leiden Community Detection
Uses the Hierarchical Leiden Algorithm (improved Louvain):
- Recursively partitions graph by optimizing modularity
- Each level is mutually exclusive, collectively exhaustive partition
- Resolution parameter controls granularity (higher = more, smaller communities)
- C0 (root, broadest) through C3 (leaf, most specific)
- Communities form a tree: each child community is fully contained in one parent

## Dual Query Modes
**Local Search** (entity-specific): Query → embed → find similar entities → fan out to graph neighbors → collect entity descriptions, relationships, source texts, and community reports → allocate context window (50% text, 10% community, 40% entity/relationship) → LLM synthesizes answer.

**Global Search** (holistic): Select community level → MAP: each community summary scored for relevance (0-100) → REDUCE: top-scoring summaries concatenated → LLM synthesizes coherent answer. Key insight: C0 requires 97% fewer tokens than full text summarization while maintaining 72% comprehensiveness win over vector RAG.

## DRIFT Search (hybrid, newer)
Starts like local search (entity-focused), adds community context, generates follow-up questions for iterative refinement. More diverse fact retrieval than pure local search.

## Dynamic Community Selection (2025 improvement)
Top-down hierarchy traversal: rate each community's relevance, prune irrelevant branches (skip sub-communities entirely). Result: 77% fewer tokens at C1 vs. static approach.

## Key Design Decisions
- Entity resolution by name matching (descriptions merged)
- Edge weight = normalized count of detection instances across chunks
- Community summaries prioritize high-degree nodes (prominent entities first)
- Configurable YAML prompts for domain-specific extraction
- Optional claim/covariate extraction (factual assertions with evaluated status)

## ClarvisDB Applicability
Clarvis's 122k+ edges, 2134 nodes, 10 ChromaDB collections map naturally:
- **Existing advantage**: Hebbian edge evolution (83k dynamic edges) — superior to GraphRAG's static edges
- **Primary gap filled**: Community detection (Leiden) + summaries enable global search
- **Architecture fit**: Collections act as "soft modules" alongside graph communities
- Node-to-community mapping enables enhanced local search with community context
- Extractive summaries (keyword + representative text) work without per-summary LLM calls
- Re-detection can run weekly (communities are relatively stable)

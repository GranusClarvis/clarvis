# OpenStinger Review — Portable Memory Harness for Agents

**Date**: 2026-03-05
**Repo**: https://github.com/srikanthbellary/openstinger
**Author**: srikanthbellary
**License**: MIT | **Stars**: 87 | **Language**: Python | **Created**: 2026-02-24

## What It Is

OpenStinger is a portable memory, reasoning, and alignment infrastructure for autonomous agents. It runs *beside* the agent (never inside it), exposing 27 MCP tools over SSE that any MCP-compatible agent framework can call natively. Tagline: "OpenClaw gave agents hands. OpenStinger gives them a pulse."

## Architecture

**Stack**: FalkorDB (bi-temporal graph + vector embeddings) + PostgreSQL (operational audit trail). Ships as two Docker containers.

**Three-Tier Progressive Enhancement**:

| Tier | Name | Tools | Function |
|------|------|-------|----------|
| 1 | Memory Harness | 9 | Bi-temporal episodic memory, hybrid BM25 + vector search |
| 2 | StingerVault | +10 (19) | Autonomous session distillation → identity, expertise, boundaries, preferences, methodology |
| 3 | Gradient | +8 (27) | Synchronous alignment evaluation, drift detection, correction engine |

**Module structure**: `agents/`, `gradient/` (alignment_profile, drift_detector, correction_engine, interceptor, evaluators), `ingestion/`, `knowledge/` (chunker, ingest, sources), `mcp/`, `operational/`, `scaffold/`, `search/` (ranker — hybrid BM25+vector), `storage/`, `temporal/` (nodes, edges, engine, entity_registry, deduplicator, conflict_resolver, falkordb_driver).

## 10 Key Observations

1. **Bi-temporal graph model** — every node carries transaction_time + valid_time, enabling "what was true when" queries. FalkorDB delivers sub-10ms multi-hop queries via sparse matrix representation.

2. **Hybrid search with automatic fallback** — BM25 → CONTAINS (substring) → fuzzy vector → numeric/IP detection. No agent intervention needed on fallback.

3. **StingerVault session distillation** — periodically runs LLM classification on ingested episodes, extracting structured self-knowledge into 5 categories (IDENTITY, EXPERTISE, BOUNDARY, PREFERENCE, METHODOLOGY). SHA-256 hashed, stored locally.

4. **Gradient alignment** — evaluates every response against vault-derived agent profile. Starts in observe-only mode (no correction). Drift is logged to PostgreSQL for trend analysis.

5. **SQL-queryable audit trail** — every ingestion, entity merge, vault classification, and alignment event goes to PostgreSQL. Connect Metabase/Grafana with zero instrumentation.

6. **MCP as vendor lock-in prevention** — all 27 tools served via standard MCP protocol. Same endpoint works for OpenClaw, Claude Code, Cursor, Nanobot, etc.

7. **Zero-write ingestion** — reads JSONL session files asynchronously, never modifies them. Clean separation of concerns.

8. **Entity deduplication + conflict resolution** — dedicated modules handle merging duplicate entities and resolving contradictory facts in the temporal graph.

9. **Observe-only-first safety** — Gradient alignment starts disabled, then observe-only, collecting metrics before any correction. Production-grade safety pattern.

10. **Lightweight stack** — only 2 containers (FalkorDB + PostgreSQL), Python 3.10+, one LLM API key. Minimal operational overhead compared to multi-service alternatives.

## Comparison to Clarvis

| Capability | Clarvis | OpenStinger | Gap |
|-----------|---------|-------------|-----|
| Graph DB | NetworkX (in-process, 72k edges) | FalkorDB (Redis-protocol, sub-10ms) | Clarvis lacks temporal dimensions |
| Vector search | ChromaDB (pure vector) | FalkorDB vectors + BM25 hybrid | Clarvis missing BM25 keyword layer |
| Episodic memory | episodic_memory.py (ChromaDB) | Bi-temporal graph episodes | Clarvis lacks valid_time/invalid_time |
| Self-knowledge | SOUL.md + self_model.py (manual) | StingerVault (auto-distilled from sessions) | Clarvis lacks automated distillation |
| Alignment | clarvis_confidence.py + reasoning_chain | Gradient (continuous drift detection) | Clarvis evaluates post-hoc, not pre-response |
| Audit trail | JSONL logs (cost, performance, episodes) | PostgreSQL (structured, queryable) | Clarvis logs are file-based, not queryable |
| Tool exposure | CLI + Python API | 27 MCP tools over SSE | Clarvis has no MCP server |
| Session ingestion | heartbeat_postflight.py | Async JSONL reader (zero-write) | Comparable |

## 3 Concrete Integration Ideas

### 1. Bi-Temporal Edge Metadata for Clarvis Graph (High Value)
**What**: Add `valid_from` and `valid_until` timestamps to graph edges in `brain.py`. When a fact is superseded, set `valid_until` on the old edge and create a new edge with current `valid_from`.
**Why**: Enables temporal queries ("what did I know about X last month?"), supports knowledge decay with historical context, and improves graph_compaction by allowing time-bounded pruning.
**Effort**: Medium — extend `_add_edge()` and `_get_edges()` in graph code to include temporal fields. Add `temporal_query(entity, at_date)` method.
**Relevance to Action Accuracy**: Temporal context prevents acting on stale knowledge, directly improving action correctness.

### 2. Hybrid BM25 + Vector Search in brain.py (High Value)
**What**: Add BM25 keyword scoring as a complementary signal to ChromaDB vector search. When a query contains exact terms (function names, error codes, IDs), BM25 catches what embeddings miss.
**Why**: Pure vector search underperforms on exact matches — "heartbeat_preflight.py" embeds similarly to many scripts but BM25 would rank it #1. OpenStinger's automatic fallback chain (keyword → substring → vector → numeric) is elegant.
**Effort**: Low-Medium — `rank_bm25` from pip, build index over memory texts, weighted merge with ChromaDB scores: `final = α*vector + (1-α)*bm25`.
**Relevance to Action Accuracy**: Better retrieval → better context → fewer incorrect actions. Directly addresses retrieval quality.

### 3. Automated Session-to-Identity Distillation (Medium Value)
**What**: Adapt OpenStinger's StingerVault pattern — periodically scan recent episodes and extract structured self-knowledge into categories (identity, expertise, boundaries, preferences, methodology). Store as high-importance memories or update SOUL.md sections.
**Why**: Clarvis currently relies on manual SOUL.md curation and MEMORY.md updates. Automated distillation would surface emergent identity traits and preferences that manual curation misses.
**Effort**: Medium — LLM classification pass over episode batches, structured output, dedup against existing identity memories. Could run in `cron_reflection.sh`.
**Where**: New script `session_distiller.py` or extend `knowledge_synthesis.py`.

### Verdict: **Keep, selectively adapt patterns** — OpenStinger's bi-temporal graph and hybrid search are directly applicable to Clarvis's pending [INTRA_DENSITY_BOOST] and retrieval quality goals. The Gradient alignment pattern is conceptually interesting but Clarvis's post-hoc evaluation via confidence + reasoning chains serves a similar purpose. MCP exposure is irrelevant since Clarvis's tools are internal.

## Not Worth Adopting

- **FalkorDB migration** — Clarvis's ChromaDB + NetworkX stack works well enough and a full graph DB migration would be massive effort for marginal gain at current scale (2k memories, 72k edges).
- **PostgreSQL audit trail** — Clarvis's JSONL approach is simpler and sufficient for a single-agent system. PostgreSQL would be over-engineering.
- **MCP tool server** — Clarvis is self-contained, not a service for other agents. No benefit from MCP exposure.
- **Docker deployment** — Clarvis runs directly on NUC hardware with systemd. Docker adds complexity with no benefit.

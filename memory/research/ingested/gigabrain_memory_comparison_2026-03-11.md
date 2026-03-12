# Gigabrain vs Clarvis — Memory Architecture Comparison

_Research date: 2026-03-11 | Source: github.com/legendaryvibecoder/gigabrain v0.5.0_

## What is Gigabrain?

Production-grade OpenClaw memory plugin (Node.js/TypeScript). "Memory OS" — operational layer between agent and persistent store. SQLite + FTS5 for lexical search, optional Ollama-backed LLM review, read-only Obsidian vault surface. **No vector database** by design — embeddings are optional.

## Architecture (Gigabrain)

```
lib/core/
├── event-store.js          Append-only event log (full audit trail)
├── projection-store.js     Materialized current-state view (SQLite, FTS5)
├── capture-service.js      Parse <memory_note> tags, quality gate, dedup
├── recall-service.js       Multi-signal scoring, class budgets, temporal decay
├── orchestrator.js         Query intent classification → strategy selection
├── world-model.js          Entity graph (persons, projects, beliefs, contradictions)
├── person-service.js       Entity mention graph, person-aware retrieval boost
├── policy.js               27 junk filters, plausibility heuristics, value scoring
├── audit-service.js        Quality sweep, shadow/apply/restore modes
├── maintenance-service.js  19-step nightly pipeline with snapshot/rollback
├── native-sync.js          MEMORY.md + daily notes → SQLite indexer
├── native-promotion.js     Markdown bullets → structured registry entries
├── vault-mirror.js         Obsidian vault builder + pull workflow
└── review-queue.js         Capture + audit review queue (JSONL)
```

## Patterns Gigabrain Has That Clarvis Doesn't

### 1. Event Sourcing (HIGH PRIORITY)
Every memory write/reject/merge/audit appends to `memory_events`. Full audit trail, replay capability, delta reports. **Clarvis gap**: zero write-level audit trail. Once decayed/pruned, action is unrecoverable.

### 2. Recall Intent Classification (HIGH PRIORITY)
Orchestrator classifies queries: `quick_context`, `entity_brief`, `relationship_brief`, `timeline_brief`, `verification_lookup`, `contradiction_check`. Each routes to different retrieval profile and SQL joins. **Clarvis gap**: uniform semantic search regardless of query intent. "Who is Patrick?" and "when did X happen?" use identical path.

### 3. Quality Gate at Capture (HIGH PRIORITY)
27 junk patterns block system tags, API keys, benchmark artifacts. Value scoring (0.0-1.0) with keep/archive/reject thresholds. Plausibility heuristics detect token anomalies, broken phrases. LLM second opinion for borderline cases. **Clarvis gap**: any script can `brain.store()` anything at any importance level.

### 4. Stale Relative-Time Detection (HIGH PRIORITY)
Memories with "today", "currently", "right now" — if timestamp ≠ today, prepends `Recorded on YYYY-MM-DD`. Prevents "today" memories from being treated as currently-true. **Clarvis gap**: no detection or rewriting of stale temporal references.

### 5. World Model / Entity Projection (MEDIUM)
Entities (person, project, org) with aliases, beliefs, episodes, open loops, contradictions, syntheses. Entity resolution with proper-name extraction. **Clarvis gap**: graph edges exist but no entity-centric view, no contradiction detection.

### 6. Structured Capture Protocol (MEDIUM)
`<memory_note type="USER_FACT" confidence="0.9">` XML tags. Gated capture with intent detection ("remember that", "merk dir"). Durable vs ephemeral classification. **Clarvis gap**: no structured protocol, no durable/ephemeral split.

### 7. Coreference Resolution (MEDIUM)
Detects pronoun follow-ups and enriches query with entity from prior messages. **Clarvis gap**: each recall query treated independently.

### 8. Scope-Based Access Control (LOW for single-agent)
Memories have `scope` field (shared, profile:main). Multi-user safe. **Clarvis gap**: everything accessible uniformly (acceptable for single-agent).

### 9. Obsidian Vault Surface (LOW)
Human-browsable curated vault with entity pages, contradiction reports, briefings. **Clarvis gap**: CLI-only access.

### 10. Native Promotion (Two-Way Markdown Sync) (MEDIUM)
Markdown bullets in MEMORY.md auto-promoted to structured registry entries. **Clarvis gap**: MEMORY.md not fed back into ChromaDB.

## What Clarvis Has That Gigabrain Doesn't

1. **True Vector Semantic Search** — ONNX MiniLM embeddings, cosine similarity (Gigabrain is FTS5 lexical only)
2. **Cognitive Architecture** — ACT-R, GWT salience, Hebbian reinforcement, Phi metric, cognitive workspace
3. **Confidence Calibration** — Brier score, prediction tracking, dynamic recalibration
4. **Procedural Memory** — ACT-R 7-stage skill lifecycle
5. **Autonomous Evolution** — 12x/day self-improvement via Claude Code spawning
6. **Multi-Collection Taxonomy** — 10 semantic collections with route_query()
7. **Retrieval Gate** — Zero-LLM pre-check whether to wake at all
8. **Graph Layer** — 85k+ typed edges, dual-backend (JSON + SQLite+WAL), GraphRAG

## Recommended Adoptions (Priority Order)

### P1 — Immediate Value
1. **Write-level event log** — Append to `data/memory_events.jsonl` on every `brain.store()`, decay, prune. Unlocks "what changed?" queries.
2. **Recall intent classification** — Route entity queries, temporal queries, verification queries to different retrieval profiles. Biggest single quality improvement.
3. **Quality gate at capture** — Junk pattern filter + value scoring before `brain.store()`. Prevents noise accumulation.
4. **Stale relative-time rewriting** — Cheap accuracy fix: detect temporal words in recalled memories, prepend date context.

### P2 — Strategic
5. **Entity world model (lightweight)** — Track persons/projects as first-class entities. Entity mention index enables person-aware retrieval boost.
6. **Durable vs ephemeral split** — Classify memory types; ephemeral (episodes, context) expire after N days.
7. **Review queue** — Write borderline memories to `data/memory_review_queue.jsonl` instead of silently rejecting.
8. **Contradiction detection** — Flag conflicting assertions about same entity.

### P3 — Nice to Have
9. **Snapshot before maintenance** — Point-in-time ChromaDB snapshot before optimize-full.
10. **Obsidian vault surface** — Curated visual memory product.

## Integration Paths

- **Option A (HTTP bridge)**: Gigabrain exposes `/gb/recall`, `/gb/suggestions`. Clarvis calls via requests.
- **Option B (Shared SQLite)**: Both read/write shared SQLite for structured entity queries.
- **Option C (Native markdown bridge)**: Gigabrain's `native_sync` auto-ingests MEMORY.md. Zero code changes on Clarvis side. **Most practical immediate option.**
- **Option D (SQLite+vector hybrid)**: FTS5 for structured + ONNX for semantic. Non-trivial but architecturally strongest.

## Key Takeaway

Gigabrain is stronger on **memory hygiene** (event sourcing, quality gates, structured pipeline, audit). Clarvis is stronger on **cognitive depth** (semantic search, cognitive architecture, self-improvement). The systems are complementary. Highest-value single adoption: **recall intent classification** — routing different query types to different retrieval strategies.

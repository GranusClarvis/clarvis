# MemOS — Memory Operating System for AI Systems

**Paper**: arXiv:2507.03724 (v4, Dec 2025), 36pp, MemTensor
**Short version**: arXiv:2505.22101 (May 2025) — earliest Memory OS proposal
**Code**: github.com/MemTensor/MemOS (Apache 2.0)
**Researched**: 2026-03-11

## Core Thesis

LLMs lack well-defined memory management. MemOS treats memory as a first-class system resource — like how an OS manages RAM/disk — unifying plaintext, activation, and parametric memories under a single scheduling and governance framework.

## Architecture: Three Layers

### 1. Interface Layer
- **MemReader**: Parses natural language into structured MemoryCalls (task intent, temporal scope, entity focus)
- **Memory API Suite**: Standardized ops — Provenance API, Update API, LogQuery API
- **Memory Pipeline**: Compositional workflow chaining with transactional consistency

### 2. Operation Layer
- **MemOperator**: Structures memory via tagging, knowledge graphs, semantic layering; hybrid retrieval (symbolic + semantic)
- **MemScheduler**: Dynamically selects memory type per query using contextual similarity, access frequency, temporal decay, priority tags. Pluggable strategies: LRU, semantic similarity, label-based matching
- **MemLifecycle**: 5 states: Generated → Activated → Merged → Archived → Expired. Policy-driven transitions

### 3. Infrastructure Layer
- **MemGovernance**: ACL, retention policies, audit logging, compliance
- **MemVault**: Multi-repository management with standardized access
- **MemLoader/MemDumper**: Import/export, cross-platform sync
- **MemStore**: Pub-sub memory sharing among agents

## MemCube — Universal Memory Unit

The core abstraction. Each MemCube = Payload + Metadata Header:

| Category | Fields |
|----------|--------|
| **Descriptive** | timestamp, origin_signature (inference/user/retrieval/fine-tune), semantic_type (task prompt, fact, preference) |
| **Governance** | ACL (read/write/share scope), TTL/decay policy, priority level, sensitivity tags, watermarks, audit logs |
| **Behavioral** | access_frequency, recency, contextual_fingerprint (lightweight semantic signature), version_chain (modification lineage) |

MemCubes are composable, migratable, and fusible across types.

## Memory Type Transitions

Three cross-type conversion pathways:
1. **Plaintext → Activation**: Frequently accessed text → attention templates for faster decoding
2. **Plaintext/Activation → Parametric**: Stable knowledge → distilled into model parameter plugins
3. **Parametric → Plaintext**: Outdated parameters → externalized to editable plaintext

## Benchmarks

MemOS-0630 ranks #1 on LOCOMO benchmark across all categories (single-hop, multi-hop, open-domain, temporal reasoning), outperforming mem0, LangMem, Zep, and OpenAI Memory. Especially strong margins in multi-hop and temporal reasoning.

## Comparison with Alternatives

| System | Approach | Limitation (from MemOS perspective) |
|--------|----------|-------------------------------------|
| **mem0** | Memory layer (extract/store/retrieve) | No lifecycle, no type transitions, no governance |
| **MemGPT/Letta** | Virtual context (OS-inspired paging) | Single memory type (text), no parametric/activation, no multi-agent sharing |
| **Zep** | Temporal knowledge graph | No scheduling, no memory type diversity |
| **MemOS** | Full OS: scheduling + lifecycle + governance + type transitions + agent sharing | Heavier framework, Redis dependency for production |

## Clarvis Application — 5 Actionable Ideas

### 1. MemCube Metadata Enrichment (Quick Win)
**Current**: brain.py stores ~10 metadata fields (created_at, source, importance, access_count, tags, hebbian_boost, etc.)
**Gap**: No provenance chain, no contextual fingerprint, no version lineage
**Action**: Add `origin_episode_id` (which heartbeat created this), `evolved_from` (parent memory ID for refinements), `semantic_fingerprint` (top-3 TF-IDF terms as lightweight signature for fast pre-filtering). The `evolved_from` field is already planned in [AMEM_MEMORY_EVOLUTION].

### 2. Explicit Lifecycle State Machine (Medium Effort)
**Current**: Implicit states scattered across hebbian_memory.py, memory_consolidation.py, cleanup_policy.py
**Gap**: No formal state machine, no Expired/dispose state (archived memories linger forever)
**Action**: Define `lifecycle_state` metadata field: ACTIVE → LABILE → DORMANT → ARCHIVED → EXPIRED. Add state transition rules to a single `MemLifecycle` class in `clarvis/brain/`. Wire transitions: Hebbian sets LABILE, consolidation sets DORMANT, cleanup sets ARCHIVED, new sweep sets EXPIRED (then purge from archive JSON after 90 days).

### 3. MemScheduler → Enhanced Retrieval Gate (Synergy with RETRIEVAL_GATE)
**Current**: retrieval_gate.py (planned) routes NO/LIGHT/DEEP retrieval
**Insight**: MemScheduler adds a FORMAT dimension — not just "should I retrieve?" but "what memory format is optimal?" For Clarvis (all plaintext), this maps to: which collections? how many results? with graph expansion or not? The RETRIEVAL_GATE task already captures the routing logic; MemScheduler's contribution is making the routing policy-aware (access patterns, task type history).

### 4. MemStore → Agent Memory Sharing (Synergy with Orchestrator Pillar 2)
**Current**: Project agents have isolated LiteBrain instances, `promote` command manually copies results
**Insight**: MemStore's pub-sub pattern enables principled inter-agent memory flow. Agent discovers procedure → publishes to shared channel → orchestrator evaluates utility → promotes to relevant brains. More automated than current manual promote.
**Action**: When building Phase 4 (Enhanced Brain) of orchestrator, design a shared memory bus inspired by MemStore.

### 5. Memory Governance for Cleanup (Synergy with MEMORY_PROPOSAL_STAGE)
**Current**: cleanup_policy.py uses importance + recency scoring, protected tags
**Gap**: No formal retention policies, no audit trail of mutations
**Insight**: MemOS governance adds TTL policies per memory type, provenance-based retention (keep if cited in successful episodes), and LogQuery audit trail. The planned [MEMORY_PROPOSAL_STAGE] (two-stage commit) is a subset of MemOS MemLifecycle's Generated→Activated transition.

## Context Relevance Connection

MemOS's MemScheduler concept — using behavioral indicators to select optimal memory injection strategy — directly supports Context Relevance improvement. Current metric: 0.838. The MemScheduler pattern suggests: track per-memory "usefulness" (was it referenced in task output?) and use that signal to rank memories in future recalls. This aligns with [CONTEXT_RELEVANCE_FEEDBACK] and [RETRIEVAL_RL_FEEDBACK] tasks already in queue.

## Sources

- [arXiv:2507.03724 — MemOS Full Paper](https://arxiv.org/abs/2507.03724)
- [arXiv:2505.22101 — MemOS Short Version](https://arxiv.org/abs/2505.22101)
- [GitHub: MemTensor/MemOS](https://github.com/MemTensor/MemOS)
- [HuggingFace Paper Page](https://huggingface.co/papers/2507.03724)

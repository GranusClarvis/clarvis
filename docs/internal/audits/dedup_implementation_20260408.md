# Brain Dedup & Consolidation — Implementation Report (2026-04-08)

Follow-up to `docs/brain_audit_20260408.md`. Implements write-time prevention for the root causes identified in the audit.

## Changes Made

### 1. Write-Time Dedup Guard (`clarvis/brain/store.py`)

**What**: Before inserting a new memory, `store()` now queries the target collection for a near-duplicate (L2 distance < 0.30). If found, the existing entry's importance is boosted (+0.02, capped at max of old/new importance) and its ID is returned — no new entry is created.

**Scope**: Only applies when `memory_id` is auto-generated (caller passes `memory_id=None`). Callers that pass an explicit `memory_id` get upsert semantics as before — this is intentional for the fixed-ID patterns below.

**New methods**: `_find_near_duplicate(text, collection)`, `_boost_existing(existing, importance, collection)`.

**Reversibility**: Set `DEDUP_DISTANCE_THRESHOLD = 0.0` to disable. The guard is best-effort (exceptions are caught and silently ignored).

### 2. Self-Model / Self-Representation Upsert (`clarvis/metrics/self_model.py`, `scripts/metrics/self_representation.py`)

| Writer | Old behavior | New behavior |
|---|---|---|
| `update_model()` world model | Appended new entry per call | Fixed ID `self-model-world-{YYYY-MM-DD}` — one entry per day |
| `set_awareness_level()` | Appended new entry per change | Fixed ID `self-model-awareness-current` — always upserts |
| `think_about_thinking()` | Stored in brain + meta JSON | **Removed brain storage** — meta JSON already persists last 20 |
| Capability assessment | Appended new entry per call | Fixed ID `self-model-capability-{YYYY-MM-DD}` — one per day |
| `self_representation.py` update | Appended per heartbeat | Fixed ID `self-rep-current` — always upserts |

### 3. Broadcast Spam Elimination (`clarvis/cognition/workspace_broadcast.py`, `clarvis/cognition/attention.py`)

**GWT broadcast context** (`workspace_broadcast.py`): Removed `brain.store()` call in step 4 (self-representation). Brain context is already set via `set_context()` (step 3), and episodic tagging (step 2) preserves the last 3 broadcasts.

**Attention broadcast** (`attention.py`): Removed `brain.store()` snapshot call. `set_context()` is the authoritative current-context record.

**Impact**: Eliminates the 158+ GWT broadcast entries and unbounded attention broadcast entries that were the #1 and #3 spam sources.

### 4. Dream Engine Dedup (`scripts/cognition/dream_engine.py`)

Dream insights now use deterministic IDs: `dream_{episode_id}_{template_id}`. Dream session summaries use `dream_session_{session_id}`. Reruns of the same episode+template upsert instead of appending, eliminating the 100+ dream chain duplicates found in the audit.

### 5. Research Queue Leak Prevention (`scripts/evolution/research_to_queue.py`)

**New function**: `_proposal_fingerprint(paper_file, proposal)` — disposition-agnostic hash of paper+proposal.

**New function**: `_load_processed_fingerprints(path)` — loads all fingerprints from the disposition log.

**Change in `scan_papers()`**: Before classifying proposals, checks if they were already processed in a previous run (any disposition). Previously-processed proposals are silently skipped, preventing completed/discarded research from re-entering the actionable pipeline.

## Tests Added

`tests/test_write_time_dedup.py` — 13 tests covering:
- Exact duplicate blocked by write-time guard
- Importance boost on duplicate detection
- Explicit `memory_id` bypasses dedup (upsert semantics)
- Cross-collection independence
- Self-model fixed-ID upsert behavior (3 tests)
- Dream deterministic ID
- Research fingerprint determinism, normalization, paper differentiation
- End-to-end: processed proposals skipped on rescan

All 144 existing tests continue to pass (0 regressions).

## Risks

1. **False-positive dedup**: The 0.30 L2 threshold is conservative but could block legitimately different short texts with coincidentally similar embeddings. Mitigated by: only applying to auto-generated IDs, and the threshold being tunable via `DEDUP_DISTANCE_THRESHOLD`.

2. **Performance**: The dedup guard adds one ChromaDB query per `store()` call (~5-10ms). For the typical store pattern (1-10 stores per task), this is negligible. Bulk operations that pass explicit `memory_id` skip this entirely.

3. **Research fingerprint staleness**: If a paper's proposals change significantly after initial scan, the old fingerprint won't match and the new version will be processed. This is the desired behavior — only identical proposals are blocked.

## Follow-Up Tasks (Not Done)

- **P1: Semantic dedup in optimize-full**: The batch dedup threshold (0.8 L2, 3+ members) is still too permissive. Should tighten to 0.4 for pairs.
- **P1: Cross-collection dedup**: Same knowledge appearing in learnings + preferences + identity simultaneously. Requires collection priority rules.
- **P2: Consciousness content consolidation**: 104 remaining consciousness entries in learnings should be merged to ~15 canonical entries. Requires LLM-guided merge pass.
- **P2: Evolved-entry cleanup**: After evolution creates `_evolved_` entries, originals should be auto-superseded if semantically identical.

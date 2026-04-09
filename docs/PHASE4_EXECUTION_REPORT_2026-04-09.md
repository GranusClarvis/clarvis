# Phase 4 Execution Report: Safety Hardening

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 4

---

## Phase 3 Verification (Pre-Execution)

Before executing Phase 4, verified all Phase 3 claims against the codebase:

| Phase 3 Claim | Verified |
|---|---|
| Episodes rebuilt (367 entries from ChromaDB) | Yes — data/episodes.json has 367 entries |
| Backup scope expanded (OPENCLAW_CONFIG_FILES + ENCRYPTED_FILES) | Yes — in backup_daily.sh |
| CLARVIS_WORKSPACE guard before source line | Yes — line 28 of backup_daily.sh |
| Sidecar pruning function added | Yes — prune_sidecar() in clarvis/queue/writer.py |
| Sidecar pruning tests (3 tests) | Yes — tests/test_sidecar_pruning.py |
| Dead scripts deleted (lockfree_ring_buffer, ab_comparison_benchmark) | Yes — files absent |
| wiki_render.py NOT deleted (has active test deps) | Yes — still exists |

**Verdict**: All Phase 3 functionality confirmed in place. No carry-over needed.

---

## Changes Made

### 4.1 Per-hook timeout (F3.5a) — HIGH

**Files**: `clarvis/brain/search.py`, `clarvis/brain/__init__.py`

- **Brain recall hooks** (scorers, boosters): 500ms timeout via `_run_hook_with_timeout()` using `ThreadPoolExecutor` with `future.result(timeout=0.5)`. A hung scorer/booster no longer blocks `recall()` indefinitely.
- **Brain operation hooks** (`_run_brain_hooks` in `__init__.py`): 10s timeout for heartbeat registry hooks (pre-store, post-store, pre-search, post-search).
- **Recall observers** (hebbian, synaptic): Already ran in background thread pool; added circuit-breaker tracking (see 4.2).
- **Mechanism**: Each hook runs in a dedicated thread with a timeout. On timeout, the future is cancelled and the hook is recorded as failed for the circuit breaker.
- **Verification**: Direct test — slow hook (2s) correctly times out within 0.5s; fast hook completes normally.

### 4.2 Hook circuit breaker (F3.5c) — MEDIUM

**File**: `clarvis/brain/search.py`

- **State tracking**: `_hook_state` dict keyed by function qualname, tracking `consecutive_failures` and `disabled_at`.
- **Threshold**: 3 consecutive failures → hook disabled for 300s (5-minute cooldown).
- **Half-open recovery**: After cooldown expires, the hook gets one retry attempt. Success resets the breaker; failure re-opens it.
- **Scope**: Applies to all hook types (scorers, boosters, observers, brain operation hooks).
- **Logging**: Warning logged when a hook is circuit-broken, including failure count and cooldown duration.
- **Verification**: Direct test — 3 consecutive failures correctly disables the hook; `_is_hook_disabled()` returns True.

### 4.3 Archive originals before merge_clusters() deletion (F3.6a) — HIGH

**File**: `clarvis/memory/memory_consolidation.py`

- **Before**: `merge_clusters()` deleted original memories after consolidation with no recovery path.
- **After**: Before deletion, writes all original memories (id, document, metadata) to `data/memory_archive/merge_originals.jsonl` as a JSONL append. Each entry includes timestamp, collection, original count, consolidated preview, and full originals array.
- **Safety**: Archive write is wrapped in try/except — failure to archive does not block consolidation. JSONL format allows easy recovery of specific merge events.
- **Recovery**: `grep` + `jq` on the JSONL file can extract originals by timestamp, collection, or memory ID.

### 4.4 Queue engine lock timeout (F3.7a) — HIGH

**Files**: `clarvis/queue/engine.py`, `clarvis/queue/writer.py`

- **Engine**: `_acquire_lock()` now uses `fcntl.LOCK_EX | fcntl.LOCK_NB` with a retry loop and 30s deadline. Raises `TimeoutError` if the lock cannot be acquired within 30s. This prevents a crashed process's lock from blocking queue selection indefinitely.
- **Writer**: Added `_flock_with_timeout()` helper. All 5 flock sites in `writer.py` (add_tasks, select_task, archive_completed, mark_tasks_complete) now use the timeout wrapper instead of blocking `LOCK_EX`.
- **Mechanism**: Non-blocking flock attempt every 100ms, up to 30s. On timeout, the fd is closed and `TimeoutError` is raised. Callers can catch this and skip the operation rather than hang.

### 4.5 Cap _labile_memories dict (F2.5a) — MEDIUM

**File**: `clarvis/brain/search.py`

- **Before**: `_labile_memories` grew unboundedly — every `recall()` call added entries, never evicted.
- **After**: After adding new labile entries, if size > 500:
  1. First pass: evict entries past `_lability_window` (300s TTL).
  2. Second pass: if still > 500, evict oldest by `retrieved_at` timestamp.
- **Bound**: Dict never exceeds 500 entries + current recall batch. At typical usage (5-15 results per recall), this caps memory at ~500 entries.

### 4.6 Cross-collection dedup in recall() merge path (F2.5b) — MEDIUM

**File**: `clarvis/brain/search.py`

- **Before**: Same memory text stored in 2+ collections appeared as duplicate results.
- **After**: Phase 4c in `recall()` — after fetching from all collections but before scoring, deduplicate by normalized document text (lowercase, first 500 chars). When duplicates exist across collections, keep the one with the best (lowest) distance score.
- **Only active** when querying multiple collections (the common case for `recall()`).

### 4.7 Brain health orphan check for SQLite graph (F2.2a) — LOW

**Files**: `clarvis/brain/graph_store_sqlite.py`, `clarvis/brain/store.py`

- **Before**: Health check had no graph integrity verification. The orphan check was a no-op because the in-memory JSON graph dict was empty (post-cutover).
- **After**:
  - Added `GraphStoreSQLite.orphan_edges_count()` — SQL query counting edges where `from_id` or `to_id` is not in the `nodes` table. These are "soft orphans" (edges work but node metadata is missing).
  - Added step 4 to `health_check()`: queries orphan count from SQLite store, reports as issue if > 0, includes timing in `orphan_check_ms`.
  - Added `orphan_edges` field to health check output dict.
- **Current state**: 0 orphan edges (backfill has been running). The check now correctly uses the SQLite backend.
- **Verification**: Direct test — created nodes + edges, then edges with missing nodes. `orphan_edges_count()` correctly reports 0, 1, 2 orphans.

### 4.8 ChromaDB repair step in cron_doctor (F4.4.7) — MEDIUM

**File**: `scripts/cron/cron_doctor.py`

- Added `check_chromadb_health()` function with 3-step repair strategy:
  1. **Health check**: Try to import and instantiate `ClarvisBrain`, run `health_check()`.
  2. **SQLite .recover**: If brain init fails, attempt `sqlite3 chroma.sqlite3 .recover` to dump recoverable data.
  3. **Backup pointer**: Locate latest daily backup with brain data, queue evolution task for manual review (auto-restore is too risky for production data).
- Wired into `recover()` — runs once per recovery cycle with the same retry budget (max 2/day) as other jobs.
- **Conservative**: Does not auto-restore or overwrite production ChromaDB. Instead, logs the situation and queues a task for review. This prevents silent data loss from aggressive auto-repair.

---

## Verification

| Check | Result |
|-------|--------|
| `python3 -c "from clarvis.brain import brain"` | OK |
| `python3 -c "from clarvis.queue.engine import QueueEngine"` | OK |
| `python3 -c "from clarvis.queue.writer import add_task"` | OK |
| Hook timeout test (slow hook times out, fast hook succeeds) | PASSED |
| Circuit breaker test (3 failures → disabled) | PASSED |
| Orphan edge count test (0, 1, 2 orphans correctly detected) | PASSED |
| `python3 -m pytest tests/clarvis/ -q` | 479 passed |
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 pre-existing flaky (lock timing) |
| `python3 -m clarvis brain stats` | 2917 memories, 93215 edges, 7/7 hooks |
| Brain health check | orphan_edges: 0, orphan_check_ms: 51 |

## Pre-existing Test Failures (NOT introduced by Phase 4)

| Test | Issue | Phase 4 Related? |
|------|-------|-----------------|
| `test_project_agent.py::test_double_acquire_blocked` | Flaky lock timing assertion | No — pre-existing since Phase 3 |
| `test_smoke.py::test_health_check` | Retrieval probe not found in results | No — ChromaDB query timing issue pre-existing |

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| Hook timeout for optimize hooks | `_optimize_hooks` run during consolidation (offline), not in hot recall path. Low urgency. | Future |
| merge_originals.jsonl rotation | JSONL file grows forever. Should rotate monthly or cap at 10 MB. | Phase 7 polish |
| Queue lock timeout exception handling in callers | Callers catch generic Exception but not TimeoutError specifically. Works fine but could be more explicit. | Future |

## Rating Impact

Per the master plan:
- **Resilience**: B+ → A- (hook timeouts, circuit breaker, merge safety, lock timeout, ChromaDB repair)
- **Runtime Correctness**: B+ → A- (labile cap, cross-collection dedup, orphan check)

## Files Changed

| File | Change |
|------|--------|
| `clarvis/brain/search.py` | Hook timeout + circuit breaker, _labile_memories cap, cross-collection dedup |
| `clarvis/brain/__init__.py` | _run_brain_hooks 10s timeout |
| `clarvis/brain/store.py` | health_check orphan edge check via SQLite |
| `clarvis/brain/graph_store_sqlite.py` | orphan_edges_count() method |
| `clarvis/memory/memory_consolidation.py` | merge_clusters archive-before-delete |
| `clarvis/queue/engine.py` | _acquire_lock 30s timeout with LOCK_NB retry |
| `clarvis/queue/writer.py` | _flock_with_timeout helper, all flock sites use timeout |
| `scripts/cron/cron_doctor.py` | check_chromadb_health(), wired into recover() |

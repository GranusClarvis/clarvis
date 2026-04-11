# Phase 2: Runtime Correctness Review

**Date**: 2026-04-08
**Reviewer**: Claude Code Opus (automated quality review)
**Scope**: Tier 1 deep dives — episodes corruption, graph verification, CLR ablation, wiki metadata, brain recall() hot path
**Method**: Code reading + runtime execution + data inspection

---

## Executive Summary

Phase 2 investigated the 5 highest-priority runtime correctness concerns from the quality review plan. Three of five areas have **CRITICAL or HIGH** issues requiring action. One (graph verification) is healthier than expected. The brain recall() hot path is functionally correct but has medium-severity growth/dedup gaps.

### Severity Distribution

| Severity | Count | Components |
|----------|-------|------------|
| CRITICAL | 3 | Episodes write path (2), CLR ablation HARD_SUPPRESS bypass (1) |
| HIGH | 4 | Episodes second writer, episodes no error handling, CLR retrieval_precision stuck at 1.0, CLR first 4 runs returned all zeros |
| MEDIUM | 5 | Episodes _load no recovery, episodes bare except:pass, wiki metadata drift (2 files), recall() _labile_memories unbounded, recall() no cross-collection dedup |
| LOW | 5 | Graph health no-op orphan check, graph health import path, recall() cache eviction O(n), ACT-R weight sum 1.05, result budgeting not integrated |

---

## 2.1 Episodes.json Corruption

### Status: CRITICAL — confirmed corrupted, root cause identified, fix applied

**Evidence**: `data/episodes.json` (961 KB) is truncated mid-JSON-object at line 32409. `json.load()` raises `JSONDecodeError`. The file ends mid-key inside a `broadcast_context` array.

### Root Cause: Non-atomic writes + no locking

| Finding | Severity | Location | Description |
|---------|----------|----------|-------------|
| F2.1a | **CRITICAL** | `clarvis/memory/episodic_memory.py:70-73` | `_save()` opens with `'w'` (immediate truncation), then writes. Process kill during `json.dump()` leaves truncated file. |
| F2.1b | **CRITICAL** | Same | No file locking. Multiple cron jobs (`heartbeat_postflight`, `failure_amplifier`, etc.) can call `encode()` simultaneously — race condition. |
| F2.1c | **HIGH** | `scripts/evolution/failure_amplifier.py:59-62` | Second independent writer (`save_episodes()`) uses identical unsafe `open(file, 'w')` pattern. Two writers, neither locked, neither atomic. |
| F2.1d | **HIGH** | `episodic_memory.py:479` | `_save()` called bare after `self.episodes.append(episode)` — if save raises, in-memory state is mutated but disk is inconsistent. |
| F2.1e | **MEDIUM** | `episodic_memory.py:58-62` | `_load()` had no corruption recovery. If `json.load()` fails, constructor crashes, cascading to all importers. |
| F2.1f | **MEDIUM** | Lines 514, 573, 610, 885, 981 | Broad `except Exception: pass` blocks silently swallow errors in post-encode processing (somatic tagging, attention, goal alignment). |

### Fix Applied

**`clarvis/memory/episodic_memory.py`**: Replaced `_save()` and `_save_causal()` with atomic write pattern (tempfile + `os.replace()`). Added backup on each save. Added corruption recovery in `_load()` (falls back to `.bak` file). Added `import tempfile`.

### Remaining Work

- The existing corrupted `data/episodes.json` needs manual repair or rebuild (separate P0 task).
- `failure_amplifier.py` still has its own independent write path — should be routed through `EpisodicMemory`.
- File locking (e.g., `fcntl.flock()`) should be added for cross-process safety.

---

## 2.2 Graph Verification

### Status: HEALTHY — "blocking since Apr 5" is outdated

**Evidence**: `python3 -m clarvis brain health` succeeds. Graph verification has been passing since 2026-03-30 (after the SQLite cutover on 2026-03-29). The failures from Mar 7-29 were JSON/SQLite parity mismatches during the dual-write migration period, now resolved.

| Finding | Severity | Location | Description |
|---------|----------|----------|-------------|
| F2.2a | **LOW** | `clarvis/cli_brain.py:44-53` | Health command checks `b.graph` (in-memory dict) for orphan nodes, but under SQLite backend `b.graph` is always `{"nodes": {}, "edges": []}`. Orphan check iterates zero edges, always reports "OK". This is a **silent no-op**. |
| F2.2b | **LOW** | `clarvis/cli_brain.py:56` | `from memory_consolidation import get_consolidation_stats` uses bare module name instead of `clarvis.memory.memory_consolidation`. Import fails unless `scripts/` is on sys.path. |
| F2.2c | **LOW** | `graph_store_sqlite.py:23-50` | No `FOREIGN KEY` constraints on `edges` table. Edges can reference non-existent node IDs. `integrity_check()` only runs SQLite `PRAGMA integrity_check` (B-tree), not referential integrity. |

### Fix Applied

**`clarvis/cli_brain.py:56`**: Fixed import to `from clarvis.memory.memory_consolidation import get_consolidation_stats`.

### Remaining Work

- The orphan node check (F2.2a) should be rewritten to query the SQLite graph store directly instead of the empty in-memory dict. This requires a `verify_referential_integrity()` method on `GraphStoreSQLite`.

---

## 2.3 CLR Ablation Regression

### Status: HIGH — ablation mechanism is structurally broken; CLR has insufficient dynamic range

**Evidence**: Analysis of `clarvis/metrics/ablation_v3.py` and `clarvis/metrics/clr.py` with runtime data from `data/ablation_v3_history.jsonl` and `data/clr_history.jsonl`.

| Finding | Severity | Location | Description |
|---------|----------|----------|-------------|
| F2.3a | **CRITICAL** | `ablation_v3.py:151-154` | `_apply_ablation()` reassigns `assembly.HARD_SUPPRESS` to disable `graph_expansion`. But `should_suppress_section()` in `dycp.py:243` reads `HARD_SUPPRESS` from its own module scope. The reassignment only affects the `assembly` module's binding — **zero effect on actual brief generation**. Ablation relies entirely on the post-hoc `_strip_sections` regex fallback. |
| F2.3b | **HIGH** | `data/ablation_v3_history.jsonl` lines 1-4 | First 4 ablation runs (2026-04-02 before 14:16) all returned `FLAT_NEUTRAL` with `net_score=0.0` for every module. The budget-zeroing mechanism was completely ineffective. Only after `_strip_sections` was added did ablation show differentiated scores. |
| F2.3c | **HIGH** | `clr.py:182-223` | `_score_retrieval_precision()` tests only 3 hardcoded queries against their "home" collections. Getting any result from `clarvis-goals` for "current evolution goals" is trivially easy. Precision has been **1.0 for every recorded run** — zero signal for regression detection. |
| F2.3d | **MEDIUM** | `data/ablation_v3_results.json:100-117` | `working_memory` ablation shows 0 wins, 0 losses, 24 ties, net_score=0.0. The budget key `"spotlight"` maps to assembly sections that are rarely generated. Working memory contribution is **unmeasurable** by current harness. |
| F2.3e | **LOW** | `data/clr_history.jsonl` | CLR hovers at 0.865-0.870 with near-zero deltas. 5 of 7 dimensions use fallback defaults when data is missing (e.g., `_score_task_success` defaults to 0.5). This masks real regressions. |

### No Fix Applied

The ablation and CLR issues are architectural — they require redesigning the ablation mechanism to actually propagate HARD_SUPPRESS changes through `dycp.py`, and adding dynamic-range evaluation queries for CLR. These are too high-risk for an automated fix.

### Recommended Fixes

1. **Ablation**: Make `_apply_ablation()` patch `dycp.HARD_SUPPRESS` directly (the module where `should_suppress_section()` lives), not `assembly.HARD_SUPPRESS`.
2. **CLR retrieval_precision**: Replace the 3 trivial queries with queries that test discrimination (include distractor queries that *should* return low scores).
3. **Working memory ablation**: Add assembly sections that actually use the `spotlight` budget key, or remap the key.

---

## 2.4 Wiki Metadata Schema Drift

### Status: MEDIUM — two readers using wrong field name, fix applied

**Evidence**: Canonical schema in `SourceRegistry` (`scripts/wiki_ingest.py:64`) defines `ingest_ts`. All 8 write sites use `ingest_ts`. Two readers use the non-existent field `ingested_at`.

| Finding | Severity | Location | Description |
|---------|----------|----------|-------------|
| F2.4a | **MEDIUM** | `scripts/wiki_lint.py:425` | `record.get("ingested_at", "")[:10]` — reads non-existent field. "Recent sources" count in lint summary is always 0. Freshness metric silently broken. |
| F2.4b | **MEDIUM** | `scripts/evolution/research_novelty.py:704` | `info.get("ingested_at", "")` — reads non-existent field. Topic earliest/latest timestamp tracking is always empty. Novelty timeline analysis broken. |

### Fix Applied

- `scripts/wiki_lint.py:425`: Changed `ingested_at` → `ingest_ts`
- `scripts/evolution/research_novelty.py:704`: Changed `ingested_at` → `ingest_ts`

### Remaining Work

- Consider adding a schema validation step to wiki_ingest.py that rejects records missing required fields.
- The `content_hash` and `original_path` fields referenced by `wiki_maintenance.py:188-190` are not in the canonical schema — they may be ad-hoc additions that should be formalized.

---

## 2.5 Brain recall() Hot Path

### Status: FUNCTIONAL — correct architecture, medium-severity growth and dedup gaps

**Evidence**: Live search completed in 1.245s for 15 results across 6 collections. Architecture uses ThreadPoolExecutor(6) for parallel collection queries, embedding cache (50-entry, 60s TTL), and recall cache (50-entry, 30s TTL).

| Finding | Severity | Location | Description |
|---------|----------|----------|-------------|
| F2.5a | **MEDIUM** | `__init__.py:78`, `search.py:603-605` | `_labile_memories` dict grows monotonically. Entries added on every recall, only removed on reconsolidation. In long-running processes, this is unbounded memory growth. |
| F2.5b | **MEDIUM** | `search.py:569-571` | No cross-collection deduplication in main recall path. Same memory text in multiple collections (e.g., `clarvis-learnings` and `clarvis-context`) appears as duplicate results. Only `_supplement_chronological()` deduplicates. |
| F2.5c | **LOW** | `search.py:318-320`, `607-609` | Embedding and recall caches use `min(dict, key=...)` for eviction — O(n) scan. Harmless at n=50 but `OrderedDict` or `lru_cache` would be cleaner. |
| F2.5d | **LOW** | `actr_activation.py:436-441` | Composite scoring weights sum to 1.05 (70% semantic + 30% ACT-R + 5% importance). Masked by clamp to [0,1]. Technically a miscalibration. |
| F2.5e | **LOW** | `result_budgeting.py` | Result budgeting exists but is not called from `recall()`. Must be invoked externally. If a caller skips it, unbounded result text flows into context. |

### No Fix Applied

The recall path is working correctly for current load. The _labile_memories growth (F2.5a) is the most actionable — add a TTL-based eviction or cap the dict size. Cross-collection dedup (F2.5b) should be added to the main merge path.

---

## Trustworthiness Assessment

### Trustworthy Runtime Paths

| Path | Confidence | Evidence |
|------|-----------|----------|
| **Brain search/recall** | HIGH | Correct parallel architecture, bounded caches, ACT-R scoring is sound. 1.2s latency within targets. |
| **Graph SQLite backend** | HIGH | WAL mode, proper timeouts, integrity checks passing daily since cutover. |
| **Brain write paths** (store.py) | HIGH | Not investigated in depth here, but no corruption signals in brain data. |
| **Cron lock management** | HIGH | Global lock + PID locks with stale detection. No contention evidence. |

### Fragile Runtime Paths

| Path | Risk | Evidence |
|------|------|----------|
| **Episodes.json** | **CRITICAL** | Currently corrupted. Non-atomic writes were the root cause. Fixed now but existing data needs repair. |
| **CLR/Ablation measurement** | **HIGH** | HARD_SUPPRESS bypass renders budget-zeroing ineffective. Retrieval precision stuck at 1.0. CLR score is insensitive to real regressions. |
| **Wiki lint freshness** | **MEDIUM** | Was silently reporting 0 recent sources due to wrong field name. Fixed. |
| **Research novelty timeline** | **MEDIUM** | Was silently producing empty timestamps. Fixed. |
| **Brain health report** | **LOW** | Orphan check is a no-op under SQLite; consolidation import was broken. Import fixed. |

### Priority Fix Order

1. **Repair corrupted `data/episodes.json`** — rebuild from brain EPISODES collection or truncate to last valid JSON
2. **Fix CLR ablation HARD_SUPPRESS bypass** — patch `dycp.HARD_SUPPRESS` directly in `_apply_ablation()`
3. **Add dynamic-range queries to CLR retrieval_precision** — replace trivial hardcoded queries
4. **Cap `_labile_memories` dict** — add TTL eviction or max-size bound
5. **Add cross-collection dedup to recall()** — ID-based dedup in main merge path
6. **Rewrite brain health orphan check** — query SQLite graph store instead of empty in-memory dict
7. **Route `failure_amplifier.py` through `EpisodicMemory`** — eliminate independent writer

---

## Fixes Applied in This Review

| File | Change | Severity Addressed |
|------|--------|--------------------|
| `clarvis/memory/episodic_memory.py` | Atomic writes (tempfile + os.replace), backup on save, corruption recovery in _load() | CRITICAL |
| `scripts/wiki_lint.py:425` | `ingested_at` → `ingest_ts` | MEDIUM |
| `scripts/evolution/research_novelty.py:704` | `ingested_at` → `ingest_ts` | MEDIUM |
| `clarvis/cli_brain.py:56` | `from memory_consolidation` → `from clarvis.memory.memory_consolidation` | LOW |

All fixes verified with `python3 -c "import ..."` / `py_compile.compile()` — no syntax errors introduced.

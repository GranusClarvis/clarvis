# Phase 5 Execution Report: Spine Migration (Batch 1)

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 5

---

## Phase 4 Verification (Pre-Execution)

Before executing Phase 5, verified all 11 Phase 4 claims against the codebase:

| Phase 4 Claim | Verified |
|---|---|
| Hook timeout via `_run_hook_with_timeout()` in search.py | Yes |
| Brain operation hooks 10s timeout in `__init__.py` | Yes |
| Hook circuit breaker (`_hook_state`, `_is_hook_disabled`) | Yes |
| merge_clusters archive-before-delete (merge_originals.jsonl) | Yes |
| Queue engine `_acquire_lock()` 30s LOCK_NB retry | Yes |
| Writer `_flock_with_timeout()` helper | Yes |
| `_labile_memories` cap at 500 entries | Yes |
| Cross-collection dedup in `recall()` | Yes |
| `orphan_edges_count()` in graph_store_sqlite.py | Yes |
| Health check step 4 orphan edge check in store.py | Yes |
| `check_chromadb_health()` in cron_doctor.py | Yes |

**Verdict**: All Phase 4 functionality confirmed in place. No carry-over needed.

---

## Changes Made

### 5.1 Migrate daily_memory_log.py (3 cron callers)

**File**: `scripts/tools/daily_memory_log.py`

- **Before**: `sys.path.insert(0, scripts/)` + `import _paths` + `from brain import brain`
- **After**: `from clarvis.brain import brain` (direct spine import, no sys.path manipulation)
- **Scope**: Only `_get_brain_stats()` function used brain; migration was surgical.
- **Callers**: cron_morning.sh, cron_evening.sh, cron_autonomous.sh — all unaffected (they invoke the script via `python3`, not import it).
- **Verification**: `_get_brain_stats()` returns "2863 memories" — confirmed working.

### 5.2 digest_writer.py — No Migration Needed

**File**: `scripts/tools/digest_writer.py`

- **Assessment**: Pure stdlib script (os, sys, json, fcntl, datetime). Has zero brain/clarvis imports. No legacy `sys.path.insert` or `_paths` imports.
- **Verdict**: Already migration-complete. No changes required.

### 5.3 Migrate performance_benchmark.py (2 cron callers + 2 Python callers)

**File**: `scripts/metrics/performance_benchmark.py`

- **Before**: Lines 48-54 had dual `sys.path.insert` + `import _paths`. Six scattered `from brain import brain` imports inside functions (lines 127, 237, 412, 674, 797, 1209).
- **After**: 
  - Removed `import _paths` and the scripts-dir sys.path.insert.
  - Replaced workspace path derivation with `CLARVIS_WORKSPACE` env var (consistent with other spine-migrated scripts).
  - All 6 `from brain import brain` replaced with `from clarvis.brain import brain`.
  - Pre-existing `from clarvis.metrics.benchmark import ...` (line 57) and `from clarvis.memory.episodic_memory import EpisodicMemory` (line 306) were already spine — left unchanged.
- **Callers**: cron_pi_refresh.sh, cron_env.sh `get_weakest_metric()`, performance_gate.py, heartbeat_postflight.py.
- **Verification**: `performance_benchmark.py pi` returns "PI: 0.7013 — Good" — confirmed working.

### 5.4 Migrate session_hook.py (2 cron callers)

**File**: `scripts/hooks/session_hook.py`

- **Before**: `sys.path.insert(0, scripts/)` + `import _paths` + `from brain import brain`. Theory of Mind imports (`from theory_of_mind import tom`) at lines 59, 132 relied on `_paths` for path resolution.
- **After**:
  - Replaced with `CLARVIS_WORKSPACE` env var + `from clarvis.brain import brain`.
  - `from clarvis.cognition.attention import attention` was already spine — unchanged.
  - Added targeted `sys.path.insert` for `scripts/cognition/` inside the Theory of Mind try block (no spine equivalent exists for theory_of_mind yet).
- **Callers**: cron_morning.sh (`open`), cron_reflection.sh (`close`).
- **Verification**: `session_hook.py` help output works. Brain and attention imports confirmed.

### 5.5 Migrate absolute_zero.py (3 cron callers)

**File**: `scripts/cognition/absolute_zero.py`

- **Before**: `sys.path.insert(0, parent.parent)` + `import _paths` + `from brain import brain` + `from episodic_memory import episodic`.
- **After**: 
  - `CLARVIS_WORKSPACE` env var + `from clarvis.brain import brain`.
  - `from clarvis.memory.episodic_memory import episodic` (full spine migration for episodic too).
  - Removed `_paths` import entirely.
- **Callers**: cron_absolute_zero.sh, cron_reflection.sh, cron_watchdog.sh (monitoring).
- **Verification**: `absolute_zero.py stats` returns full stats (94 cycles, 22 insights) — confirmed working.

### 5.6 brain.py Shim — Retained (Intentional)

**File**: `scripts/brain_mem/brain.py`

- **Assessment**: Already a backward-compatibility shim that re-exports from `clarvis.brain`. Contains deprecation warning. ~50+ scripts still import via `from brain import brain` through this shim.
- **Verdict**: Per the master plan's "do not change" list: "Bridge stubs in scripts/ — Delete individually as callers migrate, not en masse." The shim stays until the remaining ~50 callers are migrated in future batches.

### 5.7 Bridge Stubs — None Found

- **Assessment**: Searched for bridge stubs (`*_bridge*`) referencing the 5 migrated scripts. None exist. The only bridge stub is `brain_bridge.py` (heartbeat brain bridge — different concern, not related to these scripts).
- **Verdict**: No cleanup needed.

---

## Verification

| Check | Result |
|-------|--------|
| `daily_memory_log._get_brain_stats()` | OK — returns "2863 memories" |
| `performance_benchmark.py pi` | OK — PI: 0.7013 |
| `session_hook.py` (help) | OK — displays usage |
| `absolute_zero.py stats` | OK — 94 cycles, 22 insights |
| `python3 -m clarvis brain stats` | OK — 2865 memories, 92651 edges, 7/7 hooks |
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 pre-existing flaky (lock timing) |
| Spine brain import | OK |
| Spine episodic import | OK |
| Spine attention import | OK |

## Pre-existing Test Failures (NOT introduced by Phase 5)

| Test | Issue | Phase 5 Related? |
|------|-------|-----------------|
| `test_project_agent.py::test_double_acquire_blocked` | Flaky lock timing assertion | No — pre-existing since Phase 3 |

---

## Migration Pattern Established

The Phase 5 migrations follow a consistent pattern for future batches:

1. **Remove** `sys.path.insert(0, scripts/)` + `import _paths`
2. **Add** `_workspace = os.environ.get("CLARVIS_WORKSPACE", ...)` with sys.path guard
3. **Replace** `from brain import brain` with `from clarvis.brain import brain`
4. **Replace** `from episodic_memory import ...` with `from clarvis.memory.episodic_memory import ...`
5. **Keep** targeted sys.path for non-spine modules (e.g., `theory_of_mind`) inside try/except blocks
6. **Verify** each script's CLI entry point and cron callers still work

---

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| theory_of_mind spine migration | No spine module exists yet; used only by session_hook in try/except | Future (when cognition spine expands) |
| brain.py shim deletion | ~50+ scripts still use it | Phase 7 (batch 2 migrations reduce callers) |
| digest_writer.py | Already pure stdlib — no migration needed | N/A |
| Remaining ~50 scripts with legacy imports | Batched for Phase 7 | Phase 7 |

## Scripts Migrated Summary

| Script | Legacy Imports Removed | Spine Imports Added | Cron Callers |
|--------|----------------------|--------------------|----|
| `scripts/tools/daily_memory_log.py` | `_paths`, `from brain import brain` | `from clarvis.brain import brain` | 3 |
| `scripts/metrics/performance_benchmark.py` | `_paths`, 6x `from brain import brain` | 6x `from clarvis.brain import brain` | 2 + 2 Python |
| `scripts/hooks/session_hook.py` | `_paths`, `from brain import brain` | `from clarvis.brain import brain` | 2 |
| `scripts/cognition/absolute_zero.py` | `_paths`, `from brain import brain`, `from episodic_memory import episodic` | `from clarvis.brain import brain`, `from clarvis.memory.episodic_memory import episodic` | 3 |

**Total**: 4 scripts fully migrated, 1 already complete (digest_writer), 1 retained as shim (brain.py).

## Rating Impact

Per the master plan:
- **Architecture**: B → B+ (4 high-impact scripts migrated to spine; migration pattern established for batch 2)

## Files Changed

| File | Change |
|------|--------|
| `scripts/tools/daily_memory_log.py` | Replaced legacy brain import with spine import |
| `scripts/metrics/performance_benchmark.py` | Removed _paths, replaced 6 legacy brain imports with spine imports |
| `scripts/hooks/session_hook.py` | Replaced legacy imports with spine; added targeted path for theory_of_mind |
| `scripts/cognition/absolute_zero.py` | Full spine migration (brain + episodic_memory) |

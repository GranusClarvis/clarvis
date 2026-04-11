# Phase 1: Structural Integrity Review

**Date**: 2026-04-08
**Reviewer**: Claude Code Opus (autonomous)
**Scope**: Repository structure, package boundaries, imports, path hygiene, duplicates, stale modules, docs-vs-reality, test structure, data integrity
**Method**: 4-stream parallel audit (spine, scripts, docs, tests+data) with manual verification of critical findings

---

## Executive Summary

Clarvis has **strong structural foundations** — the spine package (`clarvis/`) is well-organized with clean exports, the CLI works, and the editable install is functional. However, **four critical structural defects** were found, two of which were fixed during this review. The most significant remaining risk is the **23 shadow modules** between `scripts/` and `clarvis/` with independent logic that can silently diverge.

**Test suite**: 182 passed, 1 failed (pre-existing: `test_periodic_synthesis_import` fails due to corrupted `episodes.json`). The dual-write test failures (4 tests) were fixed during this review.

---

## Findings Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| F1 | `episodes.json` corrupted (truncated mid-object) | CRITICAL | **Known P0 — unfixed** |
| F2 | Episodic singleton instantiated at import time | CRITICAL | **FIXED** |
| F3 | 23 shadow modules with independent logic in scripts/ vs clarvis/ | CRITICAL | Documented |
| F4 | Dual-write test suite asserted dead dual-write contract | HIGH | **FIXED** |
| F5 | `clarvis.memory` import blocked by F1+F2 cascade | CRITICAL | **FIXED** (F2 fix breaks cascade) |
| F6 | Missing referenced doc: `docs/GRAPH_SQLITE_CUTOVER_2026-03-29.md` | HIGH | Documented |
| F7 | 3/7 brain hooks fail to register (hebbian, synaptic, consolidation) | HIGH | Documented |
| F8 | 41 scripts bypass clarvis with direct script-to-script imports | MEDIUM | Documented |
| F9 | 90 scripts use `sys.path.insert` hacks | MEDIUM | Documented |
| F10 | No `__init__.py` in any scripts/ subdirectory | MEDIUM | Documented |
| F11 | CLAUDE.md claims "3400+ memories" but actual count is 3,136 | MEDIUM | Documented |
| F12 | 22 potentially dead scripts (no callers found) | LOW | Documented |
| F13 | Backward-compat shims in `clarvis/orch/` for queue migration | LOW | Intentional, documented |

---

## Detailed Findings

### F1: `episodes.json` corrupted [CRITICAL]

**File**: `data/episodes.json` (939 KB)
**Evidence**: `json.decoder.JSONDecodeError: Expecting value: line 32409 column 26 (char 961330)`
**Impact**: File ends mid-JSON object (`"top_coalition":` with no value). Any code loading this file crashes. This is a **known P0** in the evolution queue (`[FIX_EPISODES_CORRUPTION]`).
**Recommendation**: Recover from backup or truncate to last valid episode.

### F2: Episodic singleton at import time [CRITICAL — FIXED]

**File**: `clarvis/memory/episodic_memory.py:1026`
**Was**: `episodic = EpisodicMemory()` — forces JSON load at import time
**Now**: Lazy proxy pattern matching `clarvis/brain/__init__.py`'s `_LazyBrain`
**Effect**: `import clarvis.memory` now succeeds even with corrupted data. Actual initialization deferred to first use.

### F3: 23 shadow modules with independent logic [CRITICAL]

The spine migration left 23 modules where `scripts/` retains **independent logic** (not just re-exports) that duplicates or diverges from `clarvis/`:

| scripts/ location | clarvis/ counterpart | scripts/ LOC |
|-------------------|---------------------|--------------|
| `brain_mem/brain.py` | `brain/__init__.py` | 282 (CLI dispatch) |
| `cognition/attention.py` | `cognition/attention.py` | re-export stub |
| `cognition/reasoning_chains.py` | `cognition/reasoning_chains.py` | 46 (CLI) |
| `metrics/self_model.py` | `metrics/self_model.py` | 123 (display) |
| `metrics/performance_benchmark.py` | `metrics/benchmark.py` | 1230 |
| `pipeline/heartbeat_postflight.py` | `heartbeat/` | 1569 |
| `pipeline/heartbeat_preflight.py` | `heartbeat/` | 1213 |
| `agents/project_agent.py` | (no spine counterpart) | 2554 |
| `tools/context_compressor.py` | `context/compressor.py` | 1101 |
| ... (14 more pairs) | | |

**Only 2 of 24 are pure bridges**: `evolution/meta_learning.py`, `brain_mem/somatic_markers.py`
**17 scripts are pure re-export stubs** (the "17 micro-stubs" referenced in the review plan)
**Risk**: Changes to clarvis/ won't propagate to scripts/ logic. Bugs can silently diverge.
**Recommendation**: Phase the remaining independent logic into spine or establish a clear contract that scripts/ is the CLI/orchestration layer only.

### F4: Dual-write test suite stale [HIGH — FIXED]

**File**: `tests/clarvis/test_graph_dual_write.py`
**Problem**: 7 tests asserted dual-write behavior (JSON + SQLite) that was removed in the 2026-03-29 cutover. The actual code (`graph.py:176-191`) writes SQLite-only when `_sqlite_store` is active.
**Fix**: Rewrote tests to assert post-cutover behavior:
- `TestDualWriteAddRelationship` → `TestSQLiteWriteAddRelationship` (asserts JSON untouched)
- `TestDualWriteBackfill` → `TestBackfill` (tests both SQLite-noop and JSON-fallback paths)
- `TestVerifyParity` → Asserts SQLite integrity check (no JSON fields)
- `TestDualWriteDecay` → `TestSQLiteDecay`
**Result**: 15/15 tests pass.

### F5: `clarvis.memory` import cascade failure [CRITICAL — FIXED]

**Cause**: F1 (corrupted JSON) + F2 (eager singleton) cascaded: importing `clarvis.memory` triggered `EpisodicMemory()` which loaded corrupted `episodes.json` which raised `JSONDecodeError`.
**Fix**: F2's lazy proxy breaks the cascade. `import clarvis.memory` now succeeds; error deferred to first actual use.
**Remaining risk**: Code that calls `episodic.encode(...)` will still fail until F1 is fixed.

### F6: Missing referenced document [HIGH]

**CLAUDE.md line ~132**: References `docs/GRAPH_SQLITE_CUTOVER_2026-03-29.md` which does not exist.
**Nearby doc**: `docs/DECOMPOSITION_REMEDIATION_AND_STRUCTURAL_POLICY_PLAN_2026-03-29.md`
**Recommendation**: Either create the missing doc or update the CLAUDE.md reference.

### F7: 3/7 brain hooks fail to register [HIGH]

Every `python3 -m clarvis` invocation shows: `[hooks] Registered 4/7 hooks (failed: hebrian, synaptic, consolidation)`
**Root cause**: These hooks import from `clarvis.memory` which until F2's fix cascaded from F1. Post-fix, the hook registration may now succeed — needs re-verification after episodes.json is repaired.
**Impact**: Hebbian learning, synaptic plasticity, and memory consolidation hooks are silently disabled.

### F8: 41 scripts bypass clarvis architecture [MEDIUM]

Scripts directly import from sibling scripts via `from brain import brain`, `from episodic_memory import episodic`, etc. — bypassing the clarvis spine entirely. This creates:
- Import-order sensitivity (depends on sys.path setup)
- Risk of loading wrong module (scripts/ version vs clarvis/ version)
- Makes spine refactoring dangerous (scripts still depend on old paths)

**Top offenders**: `absolute_zero.py`, `agent_orchestrator.py`, `brain_introspect.py` + 35 more.

### F9: 90 scripts use `sys.path.insert` hacks [MEDIUM]

23 distinct path patterns found. Most scripts insert `/home/agent/.openclaw/workspace/scripts` at position 0 on sys.path. This is fragile and machine-specific.
**Root cause**: scripts/ subdirectories have no `__init__.py` (F10), so Python can't resolve them as packages.

### F10: No `__init__.py` in scripts/ subdirectories [MEDIUM]

All 12 subdirectories (`brain_mem/`, `cognition/`, `evolution/`, `hooks/`, `infra/`, `metrics/`, `pipeline/`, `tools/`, `agents/`, `cron/`, `challenges/`, `data/`) lack `__init__.py`. This forces every script to use sys.path hacks (F9).
**Note**: Adding `__init__.py` won't fully fix this since scripts/ isn't a proper package. The long-term fix is completing the spine migration (F3).

### F11: CLAUDE.md stale numeric claims [MEDIUM]

| Claim | Actual | Delta |
|-------|--------|-------|
| "3400+ memories" | 3,136 | -264 |
| "106k+ graph edges" | 135,723 | +29k |
| "19 OpenClaw skills" | 20 | +1 |
| "130+ scripts" | 165 | +35 |
| "20+ cron entries" | 48 | +28 |
| Version "2026.3.7" (SELF.md) | 2026.3.11 | stale |

### F12: 22 potentially dead scripts [LOW]

Scripts with no callers found in crontab, shell scripts, or other Python imports:
- `hooks/canonical_state_refresh.py` — suspicious name, zero references
- `evolution/task_selector.py` — should be in evolution pipeline?
- `infra/data_lifecycle.py` — claimed in CLAUDE.md cron table but not in actual crontab
- `infra/graph_cutover.py`, `infra/graph_migrate_to_sqlite.py` — one-time migration tools
- `challenges/lockfree_ring_buffer.py` — isolated experiment

### F13: Backward-compat shims [LOW — INTENTIONAL]

`clarvis/orch/queue_engine.py` (28 lines) and `clarvis/orch/queue_writer.py` (19 lines) are marked shims from 2026-04-04 queue module migration. These are documented and intentional.

---

## Structural Scorecard

| Area | Grade | Notes |
|------|-------|-------|
| **Spine package structure** | A | All __init__.py present, exports clean, CLI works |
| **Spine import health** | B | Works after F2 fix; circular deps exist but lazy-loaded |
| **Scripts layer organization** | D | Shadow modules, path hacks, no package structure |
| **Docs accuracy** | C | Mostly correct; stale numbers, one broken reference |
| **Test structure** | B | 2357 tests collect; good conftest isolation; some gaps |
| **Data integrity** | D | episodes.json corrupted; broken.gz artifact present |
| **Entrypoints** | A | CLI, __main__, pyproject.toml all correct |
| **Cross-package coupling** | C | 35+ cross-package imports; intentional but makes isolation hard |

---

## Changes Made During This Review

### 1. Lazy episodic singleton (`clarvis/memory/episodic_memory.py`)

Replaced:
```python
episodic = EpisodicMemory()
```

With lazy proxy pattern:
```python
_episodic = None

def get_episodic() -> EpisodicMemory:
    global _episodic
    if _episodic is None:
        _episodic = EpisodicMemory()
    return _episodic

class _LazyEpisodic:
    def __getattr__(self, name):
        return getattr(get_episodic(), name)

episodic = _LazyEpisodic()
```

**Effect**: `import clarvis.memory` succeeds; I/O deferred to first actual use.

### 2. Post-cutover test alignment (`tests/clarvis/test_graph_dual_write.py`)

Rewrote 7 stale tests that asserted dual-write (JSON+SQLite) behavior:
- Assertions now match actual post-cutover behavior (SQLite-only writes)
- Added JSON-fallback backfill test for completeness
- Updated docstrings and class names to reflect post-cutover era
- **Result**: 15/15 tests pass (was 8/15)

---

## Priority Remediation Order

For follow-up work, address in this order:

1. **[P0] Fix episodes.json** (F1) — Blocks episodic memory, hook registration, and learning loop. Recover from backup or rebuild.
2. **[P1] Verify hook registration** (F7) — After F1 fix, check if hooks now register. If not, debug registration failures.
3. **[P1] Create/fix cutover doc reference** (F6) — Update CLAUDE.md to point to existing doc or create the missing one.
4. **[P2] Shadow module consolidation plan** (F3) — Audit which scripts/ logic should move into spine vs. remain as CLI/orchestration wrappers. Establish a clear boundary contract.
5. **[P2] Update stale CLAUDE.md numbers** (F11) — Quick doc refresh.
6. **[P3] Script import hygiene** (F8, F9, F10) — Long-term; tied to completing spine migration.
7. **[P3] Dead script audit** (F12) — Low risk but reduces maintenance surface.

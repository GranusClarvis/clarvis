# Structure Audit Report — 2026-03-04

## Executive Summary

The `clarvis/` spine package is **structurally sound**. All 23 submodules import cleanly, 610 tests pass, import health checks pass, and zero circular dependencies exist between spine and scripts. The refactored modules (brain, 5 memory modules, 3 cognition modules, heartbeat hooks+adapters) are correctly wired with thin shims in `scripts/` for backward compatibility.

**Primary gap**: 3 of 8 spine subpackages are empty shells (`context/`, `metrics/`, `orch/`). 12 large scripts remain in `scripts/` that belong in these packages.

---

## 1. Spine Status

### Populated (5/8)

| Package | Modules | Lines | Status |
|---------|---------|-------|--------|
| `clarvis/brain/` | constants, graph, search, store, hooks, __init__ | 1,206 | Complete — ClarvisBrain class, hook registry, singletons |
| `clarvis/memory/` | episodic, procedural, hebbian, working, consolidation | 4,019 | Complete — all 5 memory systems extracted |
| `clarvis/cognition/` | attention, confidence, thought_protocol | 2,812 | Complete — 3 core cognition modules |
| `clarvis/heartbeat/` | hooks, adapters | 341 | Complete — HookRegistry + 6 adapter hooks |
| `clarvis/__init__.py` | docstring only | 1 | Correct (namespace package) |

### Empty Shells (3/8)

| Package | __init__.py | Next Candidates |
|---------|------------|-----------------|
| `clarvis/context/` | docstring only | context_compressor.py (1487L), cognitive_workspace.py (678L) |
| `clarvis/metrics/` | docstring only | self_model.py (1631L), performance_benchmark.py (1484L) |
| `clarvis/orch/` | docstring only | task_selector.py (435L), task_router.py (564L) |

---

## 2. Legacy Coupling

### Shim Pattern (correct)
8 scripts are now thin shims that re-export from clarvis/:
- `scripts/brain.py` → `clarvis.brain`
- `scripts/attention.py` → `clarvis.cognition.attention`
- `scripts/clarvis_confidence.py` → `clarvis.cognition.confidence`
- `scripts/thought_protocol.py` → `clarvis.cognition.thought_protocol`
- `scripts/episodic_memory.py` → `clarvis.memory.episodic_memory`
- `scripts/procedural_memory.py` → `clarvis.memory.procedural_memory`
- `scripts/hebbian_memory.py` → `clarvis.memory.hebbian_memory`
- `scripts/working_memory.py` → `clarvis.memory.working_memory`
- `scripts/memory_consolidation.py` → `clarvis.memory.memory_consolidation`

### Direct `from brain import` (55 scripts)
These still use `from brain import brain` (via the shim). This is **acceptable** — the shim delegates to `clarvis.brain`, so there's no hidden coupling. Migrating them to `from clarvis.brain import brain` is cosmetic and can be done incrementally.

### Mixed Imports in `heartbeat_postflight.py`
Lines 31-32 use spine: `from clarvis.heartbeat.hooks import ...`
Lines 285, 690, 709 still use: `from brain import brain`
This works via the shim but should ideally be migrated to `from clarvis.brain import brain` for consistency.

---

## 3. Test Coverage

| Test File | Imports From | Tests | Status |
|-----------|-------------|-------|--------|
| test_clarvis_brain.py | `clarvis.brain.constants` | Brain constants/routing | Modern |
| test_clarvis_cognition.py | `clarvis.cognition.confidence` | Confidence/calibration | Modern |
| test_clarvis_heartbeat.py | `clarvis.heartbeat.hooks` | Hook registry | Modern |
| test_clarvis_memory.py | `clarvis.memory.hebbian_memory` | Hebbian constants | Modern |
| test_hook_order.py | `clarvis.heartbeat.hooks` | Hook ordering | Modern |
| test_critical_paths.py | `scripts/` (legacy path) | Integration tests | **Legacy** |

**Result**: 610 tests pass. test_critical_paths.py should migrate to spine imports.

---

## 4. Import Health

```
SCC count: 0 (no circular dependencies)
Max depth: 6 (heartbeat_postflight)
Max fan-in: 52 (brain — via shim)
Max fan-out: 28 (heartbeat_postflight)
Side effects: 0
brain.py import time: 401ms (threshold 600ms)
All checks PASS
```

---

## 5. Dead/Orphan Scripts

29 scripts are never imported by any other module. Most are CLI entry points or cron targets (correct). Candidates for review:

| Script | Lines | Verdict |
|--------|-------|---------|
| `clarvis_eyes.py` | 152 | Unused vision helper — **archive candidate** |
| `orchestration_benchmark.py` | 431 | One-off benchmark — keep but move to `tests/` or `benchmarks/` |
| `semantic_bridge_builder.py` | 322 | One-off graph tool — keep in scripts/ |
| `code_quality_gate.py` | 300 | CI gate not used in any cron — verify if needed |

All others are legitimate CLI/cron entry points.

---

## 6. Punchlist (Priority Order)

### P1 — Complete Before Next Refactor Phase

1. **Extract context_compressor.py → clarvis/context/compressor.py** (1487L)
   - Largest unextracted cognitive module
   - context/ is empty — this is its primary occupant

2. **Extract self_model.py → clarvis/metrics/self_model.py** (1631L)
   - metrics/ is empty — this is its primary occupant

3. **Extract task_selector.py → clarvis/orch/task_selector.py** (435L)
   - orch/ is empty — this is its primary occupant

### P2 — Next Batch

4. **Extract performance_benchmark.py → clarvis/metrics/benchmark.py** (1484L)
5. **Extract cognitive_workspace.py → clarvis/context/workspace.py** (678L)
6. **Extract task_router.py → clarvis/orch/router.py** (564L)
7. **Extract clarvis_reasoning.py → clarvis/cognition/reasoning.py** (915L)
8. **Extract soar_engine.py → clarvis/cognition/soar.py** (827L)

### P3 — Cleanup

9. **Migrate test_critical_paths.py** to use spine imports instead of scripts/ path
10. **Archive clarvis_eyes.py** — unused, no importers
11. **Migrate heartbeat_postflight.py `from brain import`** → `from clarvis.brain import`
12. **Add clarvis/context/__init__.py exports** once compressor is extracted
13. **Add clarvis/metrics/__init__.py exports** once self_model is extracted
14. **Add clarvis/orch/__init__.py exports** once task_selector is extracted

### P4 — Documentation

15. Update CLAUDE.md "Script Categories" section to reference clarvis/ spine locations
16. Add `docs/ARCHITECTURE.md` with spine package diagram

---

## 7. Structure Recommendations

### Current Layout (Good)
```
clarvis/
├── brain/          ← ClarvisBrain + hooks (COMPLETE)
├── memory/         ← 5 memory systems (COMPLETE)
├── cognition/      ← attention, confidence, thought (COMPLETE, 4 more pending)
├── heartbeat/      ← hooks + adapters (COMPLETE)
├── context/        ← EMPTY → compressor, workspace
├── metrics/        ← EMPTY → self_model, benchmark
└── orch/           ← EMPTY → selector, router
```

### Suggested Final Layout
```
clarvis/
├── brain/          ← ClarvisBrain + hooks
├── memory/         ← episodic, procedural, hebbian, working, consolidation, synthesis
├── cognition/      ← attention, confidence, thought, reasoning, reflection, soar, meta
├── heartbeat/      ← hooks, adapters
├── context/        ← compressor, workspace
├── metrics/        ← self_model, benchmark, phi
└── orch/           ← selector, router, project_agent
```

### Naming Conventions (Verified)
- Spine modules use lowercase_snake_case ✓
- No `clarvis_` prefix inside spine (stripped during extraction) ✓
- Shim files retain original names for backward compat ✓
- Tests follow `test_clarvis_{subpackage}.py` pattern ✓

---

## 8. Scalability Assessment

**Current state supports growth**. The hook-based dependency inversion in brain and heartbeat means new subsystems can register without modifying core code. The shim pattern means existing 55+ scripts continue working during migration.

**Risk**: If all 12 remaining extractions are done without updating the 55 legacy importers, the shim layer becomes technical debt. Recommend: migrate importers in batches of 5-10 per refactor phase.

**No blocking issues found.** The spine is correctly wired and all core features work through it.

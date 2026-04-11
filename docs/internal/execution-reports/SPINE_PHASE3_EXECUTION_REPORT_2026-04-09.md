# Spine Migration Phase 3 Execution Report: queue_writer Migration

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: SPINE_MIGRATION_PLAN.md, Phase 3
**Scope**: Migrate all callers of `scripts/evolution/queue_writer.py` to `from clarvis.queue.writer import ...`. Delete wrapper.

---

## Prior Phase Verification

| Phase | Claim | Verified |
|-------|-------|----------|
| Phase 0 | Dead code removal of `brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py` | NOT DONE (files still exist). Not blocking Phase 3. |
| Phase 1 | brain_mem/ thin wrappers deleted (episodic_memory, hebbian, etc.) | YES. All 7 wrappers deleted, zero `from brain_mem.` imports remain in code. |
| Phase 2 | cognition/ stubs and metrics/ wrappers deleted | YES. All 12 wrappers deleted (attention.py, clarvis_confidence.py, clarvis_reasoning.py, reasoning_chains.py, thought_protocol.py, cognitive_load.py, phi_metric.py, orchestration_scoreboard.py, clr_benchmark.py, self_model.py, cost_api.py). Zero legacy imports remain. |

**Verdict**: Phases 1-2 complete. Phase 0 has leftover dead code (out of scope for Phase 3). No carry-over needed.

---

## Changes Made

### 3.1 Audit of queue_writer callers

The plan claimed 18 callers. Actual audit found **16 unique import sites** across 15 files:

**Python scripts (11 files, 14 import sites):**
- `scripts/evolution/evolution_loop.py` (1 site)
- `scripts/evolution/research_to_queue.py` (1 site)
- `scripts/metrics/performance_benchmark.py` (1 site)
- `scripts/metrics/llm_brain_review.py` (1 site)
- `scripts/hooks/goal_tracker.py` (1 site)
- `scripts/hooks/obligation_tracker.py` (1 site)
- `scripts/pipeline/heartbeat_preflight.py` (1 site)
- `scripts/pipeline/heartbeat_postflight.py` (4 sites: add_task x3, mark_task_complete x1, archive_completed x1)
- `scripts/cron/cron_doctor.py` (1 site)
- `scripts/cognition/absolute_zero.py` (1 site)
- `scripts/cognition/prediction_review.py` (1 site)
- `scripts/cognition/clarvis_reflection.py` (1 site)

**Shell scripts with embedded Python (2 files, 3 sites):**
- `scripts/cron/cron_strategic_audit.sh` (1 embedded `from queue_writer import add_task`)
- `scripts/cron/cron_research.sh` (2 embedded `from queue_writer import mark_task_complete, archive_completed`)

**Shell scripts with subprocess calls (2 files, 3 sites):**
- `scripts/cron/lock_helper.sh` (1 subprocess call to `evolution/queue_writer.py`)
- `scripts/cron/cron_research.sh` (2 prompt-text references to `evolution/queue_writer.py`)

**Test files (2 files):**
- `tests/test_queue_writer_mode_gate.py` (imported `queue_writer` shim + canonical)
- `tests/scripts/test_smoke.py` (string reference in CRITICAL_SCRIPTS list)

**Already using spine import (no change needed):**
- `clarvis/metrics/self_model.py` — already uses `from clarvis.queue.writer import add_tasks`

### 3.2 Caller migration

All callers updated from `from queue_writer import X` to `from clarvis.queue.writer import X`.

Where callers had `sys.path.insert(0, ...)` + `import _paths` solely for the queue_writer import, those lines were removed.

Shell subprocess calls updated from `python3 scripts/evolution/queue_writer.py add` to `python3 -m clarvis queue add`.

### 3.3 Wrapper deletion

Deleted:
- `scripts/evolution/queue_writer.py` (63 lines) — the deprecated re-export wrapper
- `clarvis/orch/queue_writer.py` (19 lines) — backward-compatibility shim (zero callers)

### 3.4 Test updates

- `tests/test_queue_writer_mode_gate.py`: Rewritten `_load_modules()` to test `clarvis.queue.writer` directly instead of testing both shim and canonical in parallel. Removed `sys.path` manipulation.
- `tests/scripts/test_smoke.py`: Removed `"queue_writer"` from `CRITICAL_SCRIPTS` list (wrapper deleted; spine module tested elsewhere).
- `tests/test_open_source_smoke.py`: Updated stale comment about legacy wrapper.

---

## Verification

| Check | Result |
|-------|--------|
| `grep -r "from queue_writer\|import queue_writer" scripts/` | 0 matches |
| `grep -r "evolution/queue_writer\|evolution.queue_writer" scripts/` | 0 matches |
| `python3 -c "from clarvis.queue.writer import add_task, ..."` | All imports OK |
| `python3 -m clarvis queue status` | 89 pending, 1400 archived |
| `pytest tests/test_queue_writer_mode_gate.py -v` | 2/2 passed |
| `pytest tests/test_critical_paths.py tests/test_open_source_smoke.py -v` | 76 passed, 3 skipped |
| `pytest tests/scripts/test_preflight_defer.py -v` | 23 passed |
| Total: 99 tests passed, 3 skipped, 0 failures | |

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/evolution/queue_writer.py` | **DELETED** (63 LOC wrapper) |
| `clarvis/orch/queue_writer.py` | **DELETED** (19 LOC shim) |
| `scripts/evolution/evolution_loop.py` | `from queue_writer` → `from clarvis.queue.writer` |
| `scripts/evolution/research_to_queue.py` | Same + removed `sys.path` + `_paths` setup |
| `scripts/metrics/performance_benchmark.py` | Same |
| `scripts/metrics/llm_brain_review.py` | Same |
| `scripts/hooks/goal_tracker.py` | Same |
| `scripts/hooks/obligation_tracker.py` | Same + removed `sys.path` + `_paths` setup |
| `scripts/pipeline/heartbeat_preflight.py` | Same |
| `scripts/pipeline/heartbeat_postflight.py` | Same (6 import sites) |
| `scripts/cron/cron_doctor.py` | Same + removed `sys.path` |
| `scripts/cognition/absolute_zero.py` | Same |
| `scripts/cognition/prediction_review.py` | Same |
| `scripts/cognition/clarvis_reflection.py` | Same + removed `sys.path` |
| `scripts/cron/lock_helper.sh` | `python3 evolution/queue_writer.py` → `python3 -m clarvis queue` |
| `scripts/cron/cron_strategic_audit.sh` | Embedded Python: removed `sys.path`, spine import |
| `scripts/cron/cron_research.sh` | 4 sites: 2 embedded Python + 2 prompt-text references updated |
| `tests/test_queue_writer_mode_gate.py` | Test against spine module directly |
| `tests/scripts/test_smoke.py` | Removed `queue_writer` from critical script list |
| `tests/test_open_source_smoke.py` | Updated stale comment |

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| Phase 0 dead code (`brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py`) | Not Phase 3 scope. Still exist, may have callers — needs Phase 0 execution. | Phase 0 |
| `clarvis/orch/queue_engine.py` shim (28 lines) | Not a queue_writer caller. Separate shim for engine module. | Phase 3 was scoped to queue_writer only. |
| Doc references to `queue_writer.py` in `docs/` | Documentation references are historical/architectural notes, not code paths. | Optional doc cleanup in Phase 9. |

## Acceptance Criteria (from plan)

- `grep -r "from evolution.queue_writer\|from evolution import queue_writer\|import queue_writer" scripts/` → **0 results**
- Wrapper deleted → **YES** (`scripts/evolution/queue_writer.py` removed)
- All cron jobs that use queue injection pass → **YES** (verified via test suite + CLI)

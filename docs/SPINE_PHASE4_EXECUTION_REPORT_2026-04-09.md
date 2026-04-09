# Spine Migration Phase 4 Execution Report: hooks/ Library Extraction

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: SPINE_MIGRATION_PLAN.md, Phase 4
**Scope**: Extract shared library logic from hooks/ into spine. Migrate callers. Delete shims/bridges.

---

## Prior Phase Verification

| Phase | Claim | Verified |
|-------|-------|----------|
| Phase 0 | Dead code removal of `brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py` | NOT DONE (files still exist). Not blocking Phase 4. |
| Phase 1 | brain_mem/ thin wrappers deleted (episodic_memory, hebbian, etc.) | YES. All 7 wrappers deleted, zero `from brain_mem.` imports remain. |
| Phase 2 | cognition/ stubs and metrics/ wrappers deleted | YES. All 12 wrappers deleted (attention.py, clarvis_confidence.py, etc.). Zero legacy imports remain. |
| Phase 3 | queue_writer wrapper deleted, all callers migrated to `clarvis.queue.writer` | YES. Wrapper gone, zero `from queue_writer` imports remain. |

**Leftover from Phases 1-2**: `tests/scripts/test_smoke.py` still listed 14 deleted wrappers in CRITICAL_SCRIPTS and COGNITIVE_SCRIPTS, causing 14 test failures. Fixed in this phase (see 4.4 below).

---

## Changes Made

### 4.1 obligation_tracker.py — Library Extraction

The plan called for migrating `obligation_tracker.py` (4 callers) to `clarvis/cognition/obligations.py`.

**What actually happened:**
- `scripts/hooks/obligation_tracker.py` is 880 lines of standalone library logic AND a CLI tool called from shell scripts (`cron_autonomous.sh`, `cron_implementation_sprint.sh`).
- Created `clarvis/cognition/obligations.py` (spine module) containing all library logic: `ObligationTracker`, `seed_defaults`, `run_verification`, plus private helpers `_now()`, `_parse_iso()`.
- Converted `scripts/hooks/obligation_tracker.py` to a thin CLI wrapper (85 lines) that imports from spine and provides the CLI interface. This is necessary because shell scripts call it directly as `python3 "$SCRIPTS/hooks/obligation_tracker.py" auto-fix`.
- Added exports to `clarvis/cognition/__init__.py`: `ObligationTracker`, `seed_defaults`, `run_verification`.

**Callers updated (3 Python import sites):**

| File | Old Import | New Import |
|------|-----------|------------|
| `scripts/pipeline/heartbeat_preflight.py:149` | `from obligation_tracker import ObligationTracker` | `from clarvis.cognition.obligations import ObligationTracker` |
| `scripts/pipeline/heartbeat_postflight.py:226` | `from obligation_tracker import ObligationTracker as OT_Postflight` | `from clarvis.cognition.obligations import ObligationTracker as OT_Postflight` |
| `scripts/hooks/directive_engine.py:413` | `sys.path.insert` + `import _paths` + `from obligation_tracker import ObligationTracker` | `from clarvis.cognition.obligations import ObligationTracker` (removed sys.path hack) |

**Shell callers (unchanged — they call the CLI wrapper):**
- `scripts/cron/cron_autonomous.sh:644` — `python3 "$SCRIPTS/hooks/obligation_tracker.py" auto-fix`
- `scripts/cron/cron_implementation_sprint.sh:183` — same

### 4.2 workspace_broadcast.py — Shim Deletion

The source at `scripts/hooks/workspace_broadcast.py` was already a backward-compatibility shim (93 lines) re-exporting from `clarvis.cognition.workspace_broadcast`.

**Actions:**
- Updated 4 import sites to use spine directly
- Deleted the shim

**Callers updated:**

| File | Old Import | New Import |
|------|-----------|------------|
| `scripts/pipeline/heartbeat_preflight.py:98` | `from workspace_broadcast import WorkspaceBroadcast` | `from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast` |
| `scripts/pipeline/heartbeat_postflight.py:145` | `from workspace_broadcast import WorkspaceBroadcast` | `from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast` |
| `tests/scripts/test_smoke.py:123` | `from workspace_broadcast import WorkspaceBroadcast, Codelet, Coalition` | `from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast, Codelet, Coalition` |
| `tests/scripts/test_smoke.py:147` | `from workspace_broadcast import WorkspaceBroadcast` | `from clarvis.cognition.workspace_broadcast import WorkspaceBroadcast` |

### 4.3 soar_engine.py — Bridge Deletion

The source at `scripts/hooks/soar_engine.py` was already a bridge (16 lines) re-exporting from `clarvis.memory.soar`.

**Note**: The plan specified target `clarvis/cognition/soar.py`, but the actual spine module lives at `clarvis/memory/soar.py`. Used the actual location.

**Actions:**
- Updated 2 import sites to use spine directly
- Updated docstring in `clarvis/memory/soar.py` to reference spine import path
- Deleted the bridge

**Callers updated:**

| File | Old Import | New Import |
|------|-----------|------------|
| `scripts/pipeline/heartbeat_postflight.py:135` | `from soar_engine import get_soar as get_soar_engine` | `from clarvis.memory.soar import get_soar as get_soar_engine` |
| `clarvis/cognition/workspace_broadcast.py:243` | `from soar_engine import get_soar` | `from clarvis.memory.soar import get_soar` |

This is significant: a spine module (`clarvis/cognition/workspace_broadcast.py`) was importing from a scripts/ bridge. This Phase 4 change eliminates a spine→scripts dependency.

### 4.4 Test Cleanup (Phase 1-2 leftover)

`tests/scripts/test_smoke.py` still listed 14 wrappers deleted in Phases 1-2 in its CRITICAL_SCRIPTS and COGNITIVE_SCRIPTS lists, causing 14 test failures. Also listed `soar_engine` and `workspace_broadcast` (deleted in this phase).

**Removed from CRITICAL_SCRIPTS** (deleted in Phase 1-2):
`attention`, `episodic_memory`, `procedural_memory`, `working_memory`, `hebbian_memory`, `phi_metric`, `brain_bridge`, `self_model`, `clarvis_reasoning`, `clarvis_confidence`, `reasoning_chains`

**Removed from COGNITIVE_SCRIPTS** (deleted in Phase 2):
`cognitive_load`, `memory_consolidation`, `thought_protocol`

**Removed from CRITICAL_SCRIPTS** (deleted in this phase):
`soar_engine`, `workspace_broadcast`

---

## Verification

| Check | Result |
|-------|--------|
| `grep -r "from obligation_tracker import" scripts/ clarvis/ tests/` | 0 matches |
| `grep -r "from workspace_broadcast import" scripts/ clarvis/ tests/` | 0 matches |
| `grep -r "from soar_engine import" scripts/ clarvis/ tests/` | 0 matches |
| `python3 -c "from clarvis.cognition.obligations import ObligationTracker"` | OK |
| `python3 scripts/hooks/obligation_tracker.py status` | 3 obligations, working |
| `python3 -m pytest tests/ -v --tb=short` | **143 passed, 3 skipped, 0 failures** |

---

## Files Changed

| File | Change |
|------|--------|
| `clarvis/cognition/obligations.py` | **CREATED** (spine module, 520 LOC) |
| `clarvis/cognition/__init__.py` | Added obligations exports |
| `scripts/hooks/obligation_tracker.py` | **REWRITTEN** to thin CLI wrapper (85 LOC, down from 880) |
| `scripts/hooks/workspace_broadcast.py` | **DELETED** (93 LOC shim) |
| `scripts/hooks/soar_engine.py` | **DELETED** (16 LOC bridge) |
| `scripts/pipeline/heartbeat_preflight.py` | 2 imports updated (obligation_tracker, workspace_broadcast) |
| `scripts/pipeline/heartbeat_postflight.py` | 3 imports updated (obligation_tracker, workspace_broadcast, soar_engine) |
| `scripts/hooks/directive_engine.py` | Import updated + sys.path hack removed |
| `clarvis/cognition/workspace_broadcast.py` | `from soar_engine import` → `from clarvis.memory.soar import` |
| `clarvis/memory/soar.py` | Docstring import example updated |
| `tests/scripts/test_smoke.py` | Removed 16 deleted modules from test lists; updated 2 broadcast test imports |

## What Remains After Phase 4

| Item | Why Not Done | Phase |
|------|-------------|-------|
| Phase 0 dead code (`brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py`) | Not Phase 4 scope | Phase 0 |
| `scripts/hooks/obligation_tracker.py` CLI wrapper (85 LOC) | Cannot delete — called by cron shell scripts as `python3 .../obligation_tracker.py auto-fix` | Stays as operational entry point |
| Remaining hooks/ scripts (session_hook, temporal_self, etc.) | Cron entry points — stay per plan | Not migrating |
| Doc references in `docs/` | Historical/architectural notes | Optional, Phase 9 |

## Acceptance Criteria (from plan)

- "Migrated scripts have zero sys.path hacks" — **YES**. obligation_tracker spine module has none. directive_engine's lazy-load sys.path hack removed.
- "Original scripts deleted" — **PARTIAL**. workspace_broadcast.py and soar_engine.py deleted. obligation_tracker.py converted to thin CLI wrapper (cannot delete — shell callers need it).
- "Callers updated" — **YES**. All 9 import sites updated to spine paths. Zero legacy imports remain.
- "Cron jobs pass" — **YES**. CLI wrapper verified working. Test suite: 143 passed, 0 failed.

## Payoff

- `hooks/` now contains only operational entry points (session_hook, temporal_self, goal_tracker, etc.) plus the obligation_tracker CLI wrapper.
- Shared cognitive logic (obligations, workspace broadcast, SOAR) fully lives in `clarvis.cognition` and `clarvis.memory`.
- Eliminated a spine→scripts dependency (`workspace_broadcast.py` importing `soar_engine` from scripts/).
- Fixed 14 pre-existing test failures from stale references to Phase 1-2 deleted wrappers.

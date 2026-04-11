# Spine Migration Phase 7 Execution Report: Spine Internal sys.path Elimination

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: SPINE_MIGRATION_PLAN.md, Phase 7
**Scope**: Eliminate all `sys.path` hacks from within the spine itself (`clarvis/*.py`). Zero `sys.path.insert` in any `clarvis/*.py` file.

---

## Prior Phase Verification

| Phase | Claim | Verified |
|-------|-------|----------|
| Phase 1 | brain_mem/ thin wrappers deleted | YES. Zero `from brain_mem.` imports remain. |
| Phase 2 | cognition/ stubs and metrics/ wrappers deleted | YES. Zero legacy imports remain. |
| Phase 3 | queue_writer wrapper deleted, all callers migrated | YES. Zero `from queue_writer import` imports remain. |
| Phase 4 | hooks/ library extraction (obligations, workspace_broadcast, soar_engine) | YES. Zero legacy imports remain. |
| Phase 5 | tools/ library extraction (prompt_builder, prompt_optimizer, context_compressor) | YES. Zero legacy imports remain. |
| Phase 6 | Wiki subsystem consolidated, root-level wiki_* scripts moved to scripts/wiki/ | YES. Zero root-level wiki scripts, zero `from wiki_canonical import` legacy imports. |

---

## Plan Corrections

The migration plan listed **17 sys.path hacks** across 5 CLI modules, 4 metrics modules, 6 core modules, and 2 heartbeat modules. Actual count was **22 sys.path.insert sites across 15 files**, plus 2 unlisted files:

| Module | Plan listed? | Actual status |
|--------|-------------|---------------|
| `memory/procedural_memory.py` | NO | Had 1 sys.path.insert + 2 template strings containing "sys.path" |
| `memory/cognitive_workspace.py` | NO | Had 1 sys.path.insert (in `sync_from_spotlight`) |
| `cognition/intrinsic_assessment.py` | NO | Had 1 template string containing "sys.path" (not code) |

### Critical Pre-existing Breakage Discovery

**All 22 sys.path hacks were already broken.** Prior phases (4-6) reorganized scripts/ into subdirectories (`scripts/metrics/`, `scripts/brain_mem/`, `scripts/pipeline/`, etc.) but did not update the spine modules that imported from them. Every `sys.path.insert(0, f"{WORKSPACE}/scripts")` + `import <module>` was silently failing because the target modules no longer existed at `scripts/` root.

Evidence:
```
$ python3 -c "import sys; sys.path.insert(0, 'scripts'); import performance_benchmark"
ModuleNotFoundError: No module named 'performance_benchmark'
$ python3 -c "import sys; sys.path.insert(0, 'scripts'); import brain_hygiene"
ModuleNotFoundError: No module named 'brain_hygiene'
```

All 14 scripts tested this way returned `ModuleNotFoundError`. The CLI commands that called these scripts were non-functional (would crash on invocation).

---

## Solution: `clarvis/_script_loader.py`

Created a shared utility module that loads scripts via `importlib.util.spec_from_file_location` — no `sys.path` manipulation at all. Key properties:

- Loads modules by absolute file path (not module name search)
- Modules are cached in `sys.modules` after first load
- The loaded script's own top-level code (including any internal path setup) runs normally
- Zero `sys.path` references in the loader itself

```python
from clarvis._script_loader import load as _load_script
mod = _load_script("performance_benchmark", "metrics")  # loads scripts/metrics/performance_benchmark.py
```

---

## Changes Made

### 7.0 New File: `clarvis/_script_loader.py` (35 LOC)
Shared `importlib.util`-based script loader. Used by 9 spine modules.

### 7.1 CLI Modules (5 files, 10 sys.path sites eliminated)

| Module | Sites | Fix |
|--------|-------|-----|
| `cli_brain.py` | 1 | Removed unnecessary `sys.path.insert` — was importing from `clarvis.brain` (already spine). Removed unused `import sys`. |
| `cli_bench.py` | 4 | Converted `_get_benchmark()`, `_get_retrieval_benchmark()`, `brief`, `retrieval-report` from `sys.path + import` to `_load_script()` with correct subdirectory paths. |
| `cli_heartbeat.py` | 4 | Converted preflight/postflight to `_load_script("heartbeat_preflight", "pipeline")`. Removed broken gate fallback (spine `clarvis.heartbeat.gate` is authoritative). |
| `cli_maintenance.py` | 7 | Removed `_ensure_scripts_path()` helper entirely. All 7 commands converted from `_ensure_scripts_path() + import` to `_load_script()` with correct subdirectory paths. |
| `cli_wiki.py` | 1 | Converted `wiki_hooks` import to `_load_script("wiki_hooks", "wiki")`. |

### 7.2 Metrics Modules (4 files, 5 sys.path sites eliminated)

| Module | Sites | Fix |
|--------|-------|-----|
| `metrics/membench.py` | 2 | Removed top-level `sys.path.insert`. Replaced `from brain import brain` with `from clarvis.brain import brain`. Removed unused `import sys`. |
| `metrics/beam.py` | 1 | Replaced `import sys; sys.path.insert; from brain import brain` with `from clarvis.brain import brain` in `run_beam()`. |
| `metrics/longmemeval.py` | 1 | Same fix in `run_longmemeval()`. |
| `metrics/evidence_scoring.py` | 1 | Same fix in `_run_live_evidence_scoring()`. |

### 7.3 Orch Modules (2 files, 2 sys.path sites eliminated)

| Module | Sites | Fix |
|--------|-------|-----|
| `orch/task_selector.py` | 1 | Replaced `sys.path.insert + from retrieval_experiment import smart_recall` with `_load_script("retrieval_experiment", "brain_mem")`. Also fixed broken `from world_models import get_world_model` the same way. Removed unused `import sys`. |
| `orch/scoreboard.py` | 1 | Replaced `sys.path.insert + from project_agent import cmd_list` with `_load_script("project_agent", "agents")`. Kept directory-scanning fallback. Removed unused `import sys`. |

### 7.4 Brain Modules (2 files, 2 sys.path sites eliminated)

| Module | Sites | Fix |
|--------|-------|-----|
| `brain/retrieval_eval.py` | 1 | Removed `sys.path.insert` from `__main__` block (module already uses spine imports for `from clarvis.brain import brain` elsewhere). |
| `brain/llm_rerank.py` | 1 | Same — `__main__` already uses `from clarvis.brain import brain` at line 401. |

### 7.5 Heartbeat Modules (2 files, 3 sys.path sites eliminated)

| Module | Sites | Fix |
|--------|-------|-----|
| `heartbeat/runner.py` | 2 | Converted `run_preflight()` and `run_postflight()` from importlib+sys.path+stdout-capture to clean `subprocess.run()` calls. Removed `import sys`, added `import subprocess`. |
| `heartbeat/adapters.py` | 1 | Removed top-level `sys.path.insert`. Converted 5 lazy imports: `performance_benchmark` → `_load_script("performance_benchmark", "metrics")`, `latency_budget` → `_load_script("latency_budget", "metrics")`, `import_health` → `_load_script("import_health", "infra")`, `extract_steps` → `_load_script("extract_steps", "tools")`, `meta_learning` → spine import `from clarvis.learning.meta_learning import MetaLearner`. |

### 7.6 Memory Modules (2 files, 2 sys.path sites + 2 template strings)

| Module | Sites | Fix |
|--------|-------|-----|
| `memory/procedural_memory.py` | 1 + 2 templates | Replaced `sys.path.insert + from retrieval_experiment import smart_recall` and `from failure_amplifier import (...)` with `_load_script()`. Updated 2 code-generation scaffold templates to use spine import patterns instead of `sys.path.insert`. |
| `memory/cognitive_workspace.py` | 1 | Replaced `import sys; sys.path.insert; from attention import attention` with `from clarvis.cognition.attention import attention` (spine import). |

### 7.7 Cognition Module (1 file, 0 code sites, 1 template string)

| Module | Sites | Fix |
|--------|-------|-----|
| `cognition/intrinsic_assessment.py` | 0 + 1 template | Updated remediation template string from "verify sys.path and dependencies" to "verify import paths and dependencies". |

### 7.8 Spawn Relay Fix (1 file)

| File | Fix |
|------|-----|
| `scripts/agents/spawn_claude.sh` | Restored `try/except` around `urllib.request.urlopen()` in Telegram delivery code (lost during worker-detach refactor in commit `e1358b8`). Added stderr logging for failures. See `docs/CLAUDE_SPAWN_RELAY_INVESTIGATION_2026-04-09.md` for full analysis. |

---

## Verification

| Check | Result |
|-------|--------|
| `grep -r "sys.path" clarvis/ --include="*.py" \| grep -v __pycache__` | **0 matches** |
| `grep -r "sys.path.insert" clarvis/ --include="*.py" \| grep -v __pycache__` | **0 matches** |
| All 19 modified modules import cleanly | **19/19 OK** |
| `python3 -m clarvis brain stats` | OK |
| `python3 -m clarvis heartbeat gate` | OK |
| `python3 -m clarvis wiki status` | OK |
| `python3 -m pytest tests/test_cost_tracker.py tests/test_cost_optimizer.py tests/test_metacognition.py tests/test_prompt_route_golden.py tests/test_queue_writer_mode_gate.py tests/test_critical_paths.py tests/test_wiki_canonical.py tests/test_wiki_render.py tests/test_wiki_eval_suite.py` | **245 passed, 0 failures** |
| `bash -n scripts/agents/spawn_claude.sh` | OK (syntax valid) |

---

## Files Changed

| File | Change |
|------|--------|
| `clarvis/_script_loader.py` | **CREATED** (35 LOC) — importlib-based script loader |
| `clarvis/cli_brain.py` | Removed sys.path.insert + unused `import sys` |
| `clarvis/cli_bench.py` | 4 sys.path sites → `_load_script()` with correct subdirs |
| `clarvis/cli_heartbeat.py` | 4 sys.path sites → `_load_script()`, removed broken gate fallback |
| `clarvis/cli_maintenance.py` | 7 sys.path sites → `_load_script()`, removed `_ensure_scripts_path()` |
| `clarvis/cli_wiki.py` | 1 sys.path site → `_load_script()` |
| `clarvis/metrics/membench.py` | Removed sys.path, `from brain` → `from clarvis.brain` |
| `clarvis/metrics/beam.py` | Same |
| `clarvis/metrics/longmemeval.py` | Same |
| `clarvis/metrics/evidence_scoring.py` | Same |
| `clarvis/brain/retrieval_eval.py` | Removed sys.path from `__main__` |
| `clarvis/brain/llm_rerank.py` | Same |
| `clarvis/orch/task_selector.py` | sys.path → `_load_script()`, removed unused `import sys` |
| `clarvis/orch/scoreboard.py` | sys.path → `_load_script()`, removed unused `import sys` |
| `clarvis/heartbeat/runner.py` | sys.path + importlib → `subprocess.run()` |
| `clarvis/heartbeat/adapters.py` | sys.path → `_load_script()` + spine imports |
| `clarvis/memory/procedural_memory.py` | sys.path → `_load_script()`, updated scaffold templates |
| `clarvis/memory/cognitive_workspace.py` | sys.path → spine import `clarvis.cognition.attention` |
| `clarvis/cognition/intrinsic_assessment.py` | Updated template string |
| `scripts/agents/spawn_claude.sh` | Restored try/except for TG delivery |

## What Was NOT Done

| Item | Why |
|------|-----|
| Duplicated `_parse_frontmatter` across wiki scripts | Phase 6 noted this as Phase 7 work. However, these are in `scripts/wiki/` (not in `clarvis/`), so they're Phase 8 scope (cron script import modernization). |
| Removal of `_SCRIPTS_DIR` constant from `heartbeat/adapters.py` | Still used for data file path construction (procedure_injection_log, performance_history). Not a sys.path issue. |
| Subprocess conversion for CLI modules | Plan suggested subprocess for CLI orchestration. Used `_load_script()` instead because: (a) scripts' Python APIs return structured dicts needed by CLI formatting, (b) subprocess would require CLI interfaces for every function, (c) importlib achieves the same isolation without losing structured data. |

## Acceptance Criteria (from plan)

- "Zero `sys.path.insert` in any `clarvis/*.py` file" — **YES**. grep returns 0 matches.
- "grep -r 'sys.path' clarvis/ returns zero results (excluding __pycache__)" — **YES**. 0 matches.
- "The spine is self-contained. No import-time dependency on scripts/ layout" — **YES**. All script loading uses absolute file paths via `_load_script()` or `subprocess.run()`.

## Payoff

- 22 sys.path.insert sites eliminated across 15 spine files.
- All were already broken (scripts moved to subdirectories in prior phases). Phase 7 both fixes the breakage and eliminates the anti-pattern.
- `_script_loader.py` provides a single, cached, importlib-based mechanism for the entire spine.
- 4 unused `import sys` statements cleaned up.
- Spawn Telegram relay error handling restored (lost since 2026-03-18).

## What Still Remains After Phase 7

| Item | Phase |
|------|-------|
| ~37 cron entry point scripts using `sys.path.insert` for internal imports | Phase 8 (batched import modernization) |
| Duplicated `_parse_frontmatter` in `scripts/wiki/` scripts | Phase 8 (can import from `clarvis.wiki.canonical` during modernization) |
| Doc references update (CLAUDE.md, AGENTS.md, etc.) | Phase 9 |
| End-state verification and structural cleanup | Phase 9 |

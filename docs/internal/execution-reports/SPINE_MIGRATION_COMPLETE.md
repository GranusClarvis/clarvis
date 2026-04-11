# Spine Migration Complete

**Date**: 2026-04-10
**Duration**: 2026-04-03 to 2026-04-10 (8 days, 9 phases)
**Executor**: Claude Code Opus (executive function)

---

## Final State Snapshot

### Structural Invariants (all verified)

1. **No `sys.path` hacks in `clarvis/`**: `grep -r "sys.path.insert" clarvis/` returns **0 matches**.
2. **No script-to-script bare imports**: All cross-script imports use `clarvis._script_loader.load()`.
3. **All scripts import from `clarvis.*`**: No bare `from brain import brain` anywhere.
4. **`_paths.py` is vestigial for production code**: Only used by test infrastructure (~20 test files). Zero production scripts import it.
5. **Remaining `sys.path.insert` in scripts/**: **8 total** — 3 in `_paths.py` itself, 5 in string literals (code generation templates). **0 in actual runtime code**.

### Spine Layout (`clarvis/`)

```
clarvis/                          125 .py files, 14 subpackages
├── brain/          (19 files)    ChromaDB + graph, hooks, search, store
├── metrics/        (18 files)    PI benchmark, CLR, ablation, self-model
├── cognition/      (13 files)    Attention, confidence, reasoning, obligations, SOAR
├── orch/           (11 files)    Cost tracking, queue engine v2, task routing
├── heartbeat/      (10 files)    Gate, hooks, runner, adapters
├── context/        (10 files)    Compression, assembly, prompt building/optimization
├── memory/         (9 files)     Episodic, procedural, working, Hebbian, consolidation
├── queue/          (3 files)     Queue state machine
├── adapters/       (3 files)     External integrations
├── wiki/           (2 files)     Canonical page model, retrieval
├── runtime/        (2 files)     Execution monitor
├── learning/       (2 files)     Meta-learning from episodes
├── compat/         (2 files)     Backwards compatibility shims
├── _script_loader.py             importlib-based script loader
└── 21 root files                 CLI modules, __init__, __main__
```

### Scripts Layout (`scripts/`)

```
scripts/                          ~104 .py files, 10 subdirectories
├── agents/       (4)     project_agent, agent_orchestrator, pr_factory, agent_lifecycle
├── brain_mem/    (10)    brain.py (CLI), brain_hygiene, graph_compaction, retrieval tools
├── cognition/    (11)    absolute_zero, dream_engine, causal_model, reflection, etc.
├── cron/         (1)     cron_doctor.py + 25 .sh launchers
├── evolution/    (13)    evolution_loop, research_to_queue, task_selector, etc.
├── hooks/        (12)    session_hook, temporal_self, goal_*, canonical_state, etc.
├── infra/        (9)     backup, health, install, cost_checkpoint, graph_cutover
├── metrics/      (14)    dashboard, benchmarks, brain_eval, self_report, etc.
├── pipeline/     (5)     heartbeat_preflight, postflight, evolution_preflight
├── tools/        (11)    context_compressor, tool_maker, ast_surgery, browser_agent
├── wiki/         (13)    wiki_ingest, query, compile, lint, sync, eval, hooks
└── _paths.py              Legacy utility (test infrastructure only)
```

### Import Convention

```python
# Library code — always spine imports
from clarvis.brain import brain, search, remember
from clarvis.cognition.attention import attention

# Script-to-script — _script_loader (no sys.path mutation)
from clarvis._script_loader import load as _load_script
wiki_hooks = _load_script("wiki_hooks", "wiki")
```

---

## Phase Summary

| Phase | Description | Key Outcome |
|-------|-------------|-------------|
| 1 | brain_mem/ thin wrapper deletion | Removed delegating wrappers, callers import spine directly |
| 2 | cognition/ + metrics/ stub removal | Deleted stubs, all callers use `clarvis.cognition.*` / `clarvis.metrics.*` |
| 3 | queue_writer wrapper deletion | Removed wrapper, all callers use `clarvis.orch.queue_writer` |
| 4 | hooks/ library extraction | Moved obligations, workspace_broadcast, soar_engine into spine |
| 5 | tools/ library extraction | Moved prompt_builder, prompt_optimizer, context_compressor into spine |
| 6 | Wiki subsystem consolidation | Created `clarvis.wiki`, moved root-level wiki_* to scripts/wiki/ |
| 7 | CLI normalization + _script_loader | Zero sys.path in spine, created importlib-based loader |
| 8 | Cron import modernization | 72 sys.path sites eliminated across 61 scripts |
| 9 | Final cleanup + verification | Fixed 6 remaining code sites, updated all docs, end-state verified |

---

## Verification Results (Phase 9)

| Check | Result |
|-------|--------|
| `sys.path.insert` in `clarvis/` | **0 matches** |
| `sys.path.insert` in `scripts/` (actual code) | **0** (3 in `_paths.py` utility + 5 in string literals = 8 total) |
| `import _paths` in `scripts/` (production) | **0** (only `_paths.py` self-import) |
| Test suite (245 tests) | **All passed** |
| `clarvis brain stats` | OK |
| `clarvis heartbeat gate` | OK |
| `clarvis wiki status` | OK |
| All modified files pass `ast.parse()` | OK |

---

## What Was Removed

- `packages/` directory (clarvis-db, clarvis-cost, clarvis-reasoning) — consolidated into spine
- ~72 `sys.path.insert` sites across scripts
- ~35 `import _paths` registration calls
- Numerous thin wrapper scripts that just delegated to spine

## What Was Kept

- `scripts/_paths.py` — still needed by ~20 test files for path registration
- String-embedded `sys.path.insert` in code generation templates (5 sites) — not runtime code
- All cron .sh orchestrators — unchanged (they spawn Python, don't need migration)

---

## Documents Updated

- `CLAUDE.md` — Import convention section rewritten
- `SELF.md` — Module counts updated, sys.path example removed
- `docs/ARCHITECTURE.md` — Package layout diagram updated, stale sections removed
- `docs/SPINE_USAGE_AUDIT.md` — Marked SUPERSEDED

---

_The spine migration is complete. All shared library logic lives in `clarvis/`. All scripts import from the spine. No sys.path manipulation in production code._

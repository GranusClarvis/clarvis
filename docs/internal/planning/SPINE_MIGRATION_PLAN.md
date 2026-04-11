# Spine Migration Plan — Scripts → clarvis/

**Date**: 2026-04-09
**Author**: Claude Code Opus (executive function)
**Status**: Active — supersedes SPINE_USAGE_AUDIT.md migration recommendations
**Prereqs**: Read MASTER_IMPROVEMENT_PLAN.md (operational fixes), ARCHITECTURE.md (structural context)

---

## 0. Executive Summary

The `clarvis/` spine has 120 files / 57k LOC across 14 subsystems. The `scripts/` tree has 124 Python + 39 Shell files. Spine migration is ~34% complete by import count. This plan defines exactly what moves, what stays, what dies, and what "done" looks like — in 10 phases.

**Key principle**: Not everything should move. Scripts that are operational entry points (cron launchers, CLI tools, one-shot maintenance) stay as scripts. Only *library logic consumed by multiple callers* belongs in the spine. Migration is about eliminating `sys.path` hacks and establishing clear ownership — not about emptying `scripts/`.

### What the spine already owns (stable, no migration needed)

| Spine Module | LOC | Status | Scripts Replaced |
|---|---|---|---|
| `clarvis.brain` | 7,637 | PRODUCTION | brain.py core logic |
| `clarvis.memory` | 9,229 | PRODUCTION | episodic, procedural, hebbian, consolidation, workspace |
| `clarvis.cognition` | 8,249 | PRODUCTION | attention, confidence, reasoning, workspace broadcast |
| `clarvis.context` | 3,652 | PRODUCTION | context_compressor, assembly |
| `clarvis.metrics` | 11,887 | PRODUCTION | phi, self_model, CLR, benchmarks |
| `clarvis.queue` | 2,054 | PRODUCTION | queue_engine, queue_writer |
| `clarvis.orch` | 5,819 | MATURE | router, PR intake, cost tracking, scoreboard |
| `clarvis.heartbeat` | 1,787 | PRODUCTION | gate, hooks, brain bridge |
| `clarvis.runtime` | 320 | PRODUCTION | mode control |

### What this plan covers

1. **Dead code removal** — 5–8 confirmed dead scripts
2. **Thin wrapper cleanup** — ~12 bridge stubs that re-export spine modules
3. **Library extraction** — ~8 scripts with shared logic that belongs in the spine
4. **Import modernization** — ~60 scripts still using `sys.path.insert` to resolve legacy paths
5. **CLI path normalization** — 5 `cli_*.py` files with sys.path hacks
6. **Wiki subsystem consolidation** — 12 root-level wiki_* scripts → organized subsystem
7. **Structural end-state** — Clear ownership map for every surviving script

### What this plan does NOT cover

- Operational/cron shell scripts (they stay as-is — they're entry points, not libraries)
- The MASTER_IMPROVEMENT_PLAN phases 1–4 (operational fixes, safety hardening — do those first)
- Rewriting scripts that work correctly but use old import patterns (just update imports, don't rewrite)

---

## 1. Decision Framework: Migrate, Stay, or Delete

### When to migrate a script into `clarvis/`

A script belongs in the spine **only if ALL of these are true**:

1. **It is imported by 2+ other files** (it's a library, not a standalone tool)
2. **Its logic is general-purpose** (not specific to one cron job or one-time operation)
3. **There is a natural home in an existing spine subsystem** (brain, memory, cognition, context, metrics, orch, heartbeat)
4. **The migration eliminates sys.path hacks** in callers (measurable improvement)

### When a script should stay in `scripts/`

A script stays **if ANY of these are true**:

1. **It's a cron entry point** — called directly from crontab or a cron_*.sh launcher
2. **It's a CLI tool** — run by operators, not imported by code
3. **It's a one-time/maintenance tool** — graph cutover, backup, install, migration
4. **It has heavy external dependencies** — browser automation, Telegram, file I/O that doesn't belong in a library
5. **It's the only consumer of its own logic** — no other script imports it

### When to delete a script

Delete **only if ALL of these are true**:

1. **Not in crontab** (verified with `crontab -l`, not just grepping .sh files)
2. **Not imported by any file** (verified with `grep -r` across entire workspace)
3. **Not called via subprocess** (check for `subprocess.run`, `os.system`, shell backticks referencing it)
4. **Not referenced in any .sh file** (cron launchers often call scripts indirectly)
5. **Confirmed by reading the file** — if it has a `if __name__` block with useful CLI, it may be an operator tool even with zero automated callers

### Errata warning

The SPINE_USAGE_AUDIT.md (2026-03-23) incorrectly flagged 31 scripts as dead. Actual confirmed dead count is **5–8**. The audit missed:
- Direct crontab entries (dream_engine, brain_hygiene, goal_hygiene, data_lifecycle, generate_status_json)
- Indirect calls from shell launchers
- Dynamic imports and subprocess invocations
- Operator-facing CLI tools used interactively

**Rule**: Never delete based on automated analysis alone. Always verify each script against crontab + grep + shell references + manual read.

---

## 2. Current State Inventory

### 2.1 Scripts by Role (verified against crontab + import graph)

**Cron Entry Points (37 Python scripts called from crontab directly or via shell launchers)**
These STAY in scripts/. They are operational infrastructure, not library code.

```
pipeline/heartbeat_preflight.py    pipeline/heartbeat_postflight.py
pipeline/evolution_preflight.py    pipeline/execution_monitor.py
cognition/absolute_zero.py         cognition/dream_engine.py
cognition/causal_model.py          cognition/knowledge_synthesis.py
cognition/clarvis_reflection.py    cognition/theory_of_mind.py
hooks/session_hook.py              hooks/temporal_self.py
hooks/intra_linker.py              hooks/actr_activation.py
hooks/goal_tracker.py              hooks/goal_hygiene.py
hooks/canonical_state_refresh.py
brain_mem/brain_hygiene.py         brain_mem/graph_compaction.py
brain_mem/retrieval_quality.py     brain_mem/retrieval_benchmark.py
metrics/dashboard.py               metrics/performance_benchmark.py
metrics/brief_benchmark.py         metrics/daily_brain_eval.py
metrics/llm_brain_review.py        metrics/self_report.py
metrics/orchestration_benchmark.py metrics/brain_effectiveness.py
metrics/dashboard_events.py
evolution/failure_amplifier.py     evolution/research_to_queue.py
evolution/meta_learning.py         evolution/external_challenge_feed.py
infra/cost_checkpoint.py           infra/generate_status_json.py
infra/data_lifecycle.py
tools/daily_memory_log.py
```

**Library Scripts (imported by 2+ files — migration candidates)**
These are the primary migration targets.

```
evolution/queue_writer.py          (18 callers) — already delegates to clarvis.queue
evolution/research_novelty.py      (3 callers)
brain_mem/brain.py                 (10+ callers) — partial wrapper + CLI
brain_mem/retrieval_experiment.py  (4 callers)
brain_mem/brain_introspect.py      (1 caller, but used by prompt_builder)
brain_mem/somatic_markers.py       (1 caller)
hooks/obligation_tracker.py        (4 callers)
hooks/workspace_broadcast.py       (2 callers)
hooks/refresh_priorities.py        (1 caller)
hooks/soar_engine.py               (1 caller)
hooks/directive_engine.py          (1 caller)
hooks/session_transcript_logger.py (1 caller)
tools/prompt_builder.py            (1 caller, but core to heartbeat)
tools/context_compressor.py        (1 caller, but core to context)
tools/prompt_optimizer.py          (2 callers)
tools/tool_maker.py                (1 caller)
tools/ast_surgery.py               (1 caller)
metrics/performance_gate.py        (1 caller)
metrics/self_representation.py     (1 caller)
cognition/world_models.py          (2 callers)
cognition/prediction_review.py     (1 caller)
cognition/reasoning_chain_hook.py  (2 callers)
wiki_canonical.py                  (4 callers)
wiki_retrieval.py                  (1 caller)
agents/project_agent.py            (1 caller)
agents/agent_lifecycle.py          (1 caller)
_paths.py                          (infrastructure, many callers)
```

**Thin Wrappers (re-export spine modules, minimal or zero own logic)**
These exist solely for backward compatibility during migration.

```
brain_mem/episodic_memory.py       (19 LOC, pure re-export)
brain_mem/hebbian_memory.py        (re-export wrapper)
brain_mem/memory_consolidation.py  (re-export wrapper)
brain_mem/procedural_memory.py     (re-export wrapper)
brain_mem/synaptic_memory.py       (re-export wrapper)
brain_mem/working_memory.py        (re-export wrapper)
brain_mem/brain_bridge.py          (re-export wrapper)
metrics/phi_metric.py              (116 LOC, re-export + CLI)
metrics/orchestration_scoreboard.py (49 LOC, re-export)
metrics/clr_benchmark.py           (69 LOC, re-export)
metrics/self_model.py              (160 LOC, re-export + display)
infra/cost_api.py                  (53 LOC, re-export)
infra/cost_tracker.py              (200 LOC, re-export)
evolution/queue_writer.py          (delegates to clarvis.queue)
cognition/attention.py             (20 LOC, stub)
cognition/clarvis_confidence.py    (18 LOC, stub)
cognition/clarvis_reasoning.py     (15 LOC, stub)
cognition/reasoning_chains.py      (65 LOC, stub)
cognition/thought_protocol.py      (17 LOC, stub)
cognition/cognitive_load.py        (59 LOC, stub)
```

**Confirmed Dead Code (0 crontab + 0 imports + 0 shell refs + verified by reading)**

```
scripts/challenges/lockfree_ring_buffer.py    (DELETED in git status)
scripts/metrics/ab_comparison_benchmark.py    (DELETED in git status)
scripts/brain_mem/graphrag_communities.py     (DELETED in git status)
scripts/brain_mem/lite_brain.py               (no callers, no cron)
scripts/brain_mem/cognitive_workspace.py      (no callers — spine has clarvis.memory.cognitive_workspace)
```

**Likely Dead (needs final verification before deletion)**

```
scripts/metrics/dashboard_server.py    (no cron, no imports — but may be run manually)
scripts/metrics/latency_budget.py      (no cron, no imports)
scripts/metrics/benchmark_brief.py     (no cron, no imports)
scripts/evolution/automation_insights.py (no cron, no imports)
scripts/evolution/meta_gradient_rl.py  (no cron, no imports)
scripts/evolution/research_lesson_store.py (no cron, no imports)
scripts/tools/clone_test_verify.py     (no cron, no imports)
scripts/hooks/hyperon_atomspace.py     (no cron, no imports)
```

### 2.2 Spine sys.path Hacks (in clarvis/ itself)

**17 files** within the spine import from scripts/ — they must be fixed as part of migration:

**CLI modules (5)**:
| File | Hack Target | What It Imports |
|---|---|---|
| `cli_context.py` | `scripts/tools/` | `context_compressor.gc()` |
| `cli_bench.py` | `scripts/` | `performance_benchmark`, `retrieval_benchmark` |
| `cli_heartbeat.py` | `scripts/` | Heartbeat pipeline operations |
| `cli_maintenance.py` | `scripts/` | Brain hygiene, backups |
| `cli_brain.py` | `scripts/` | Brain CLI bridge |

**Metrics modules (4)**:
| File | What It Imports |
|---|---|
| `metrics/beam.py` | Legacy analyzers |
| `metrics/membench.py` | Memory benchmarks |
| `metrics/longmemeval.py` | Long memory evaluation |
| `metrics/evidence_scoring.py` | Evidence scoring |

**Core modules (6)**:
| File | What It Imports |
|---|---|
| `orch/task_selector.py` | Task selection logic from scripts |
| `orch/scoreboard.py` | Scoreboard imports |
| `memory/procedural_memory.py` | Procedural helpers |
| `memory/cognitive_workspace.py` | Workspace imports |
| `brain/retrieval_eval.py` | Retrieval evaluation |
| `brain/llm_rerank.py` | LLM reranking |

**Heartbeat modules (2)**:
| File | What It Imports |
|---|---|
| `heartbeat/adapters.py` | project_agent, postflight hooks |
| `heartbeat/runner.py` | Task execution bridge |

### 2.3 Import Pattern Summary

| Pattern | File Count | % |
|---|---|---|
| `sys.path.insert` (legacy) | 81 | 63% |
| `from clarvis.` (spine) | 47 | 37% |
| Both | 12 | 9% |

---

## 3. Ten-Phase Migration Plan

### Phase 0: Dead Code Removal
**Goal**: Remove confirmed dead scripts. Clean baseline before migration.
**Effort**: 30 minutes. **Risk**: Minimal (all verified).
**Dependencies**: None.

| Task | File | Acceptance Criteria |
|---|---|---|
| 0.1 Delete confirmed dead scripts | `brain_mem/lite_brain.py`, `brain_mem/cognitive_workspace.py` | File removed, no import errors anywhere |
| 0.2 Verify likely-dead scripts | 8 files listed in §2.1 | Each file confirmed dead via crontab + grep + shell refs |
| 0.3 Delete verified dead scripts | Subset of 8 from 0.2 | No runtime errors after 24h |

**Decision**: If a "likely dead" script has a useful `__main__` CLI, keep it but move to `scripts/archive/` instead of deleting.

**Payoff**: Reduces noise. Every future audit is smaller.

---

### Phase 1: Thin Wrapper Inventory and Caller Migration (brain_mem/)
**Goal**: Migrate callers of brain_mem/ thin wrappers to use `from clarvis.memory import ...` directly.
**Effort**: 1–2 sessions. **Risk**: Low (wrappers already delegate; just changing import paths).
**Dependencies**: None.

| Task | Wrapper | Callers | Target Import |
|---|---|---|---|
| 1.1 | `brain_mem/episodic_memory.py` | ~12 | `from clarvis.memory import EpisodicMemory` |
| 1.2 | `brain_mem/hebbian_memory.py` | ~3 | `from clarvis.memory import HebbianMemory` |
| 1.3 | `brain_mem/memory_consolidation.py` | ~5 | `from clarvis.memory import run_consolidation, deduplicate, ...` |
| 1.4 | `brain_mem/procedural_memory.py` | ~4 | `from clarvis.memory import find_procedure, store_procedure, ...` |
| 1.5 | `brain_mem/synaptic_memory.py` | ~2 | `from clarvis.memory import SynapticMemory` |
| 1.6 | `brain_mem/working_memory.py` | ~3 | `from clarvis.memory import WorkingMemory` |
| 1.7 | `brain_mem/brain_bridge.py` | ~2 | `from clarvis.heartbeat import brain_preflight_context, ...` |

**Per-wrapper protocol**:
1. Grep all callers: `grep -r "from brain_mem.episodic_memory import" scripts/ clarvis/`
2. Also check `import episodic_memory` (bare import via sys.path)
3. Update each caller to use spine import
4. Run the caller's cron job or test to verify
5. Once all callers migrated, delete the wrapper
6. Run full test suite: `python3 -m pytest tests/ -x -q`

**Acceptance criteria**: Zero files import from `brain_mem/episodic_memory`, `brain_mem/hebbian_memory`, etc. Wrappers deleted. All cron jobs pass.

**Payoff**: Eliminates 7 bridge files. Establishes the migration pattern for subsequent phases.

---

### Phase 2: Thin Wrapper Cleanup (cognition/ and metrics/)
**Goal**: Remove cognition/ stubs and metrics/ re-export wrappers.
**Effort**: 1 session. **Risk**: Low.
**Dependencies**: None (parallel with Phase 1).

| Task | Wrapper | Action |
|---|---|---|
| 2.1 | `cognition/attention.py` (20 LOC stub) | Migrate callers → `from clarvis.cognition import AttentionSpotlight` |
| 2.2 | `cognition/clarvis_confidence.py` (18 LOC) | Migrate callers → `from clarvis.cognition import predict, outcome` |
| 2.3 | `cognition/clarvis_reasoning.py` (15 LOC) | Migrate callers → `from clarvis.cognition import ...` |
| 2.4 | `cognition/reasoning_chains.py` (65 LOC) | Migrate callers → `from clarvis.cognition import ReasoningChains` |
| 2.5 | `cognition/thought_protocol.py` (17 LOC) | Migrate callers → `from clarvis.cognition import ThoughtProtocol` |
| 2.6 | `cognition/cognitive_load.py` (59 LOC) | Migrate callers → `from clarvis.cognition import compute_load` |
| 2.7 | `metrics/phi_metric.py` (116 LOC) | Migrate callers → `from clarvis.metrics import compute_phi` |
| 2.8 | `metrics/orchestration_scoreboard.py` (49 LOC) | Migrate callers → `from clarvis.orch import record, show` |
| 2.9 | `metrics/clr_benchmark.py` (69 LOC) | Migrate callers → `from clarvis.metrics import compute_clr` |
| 2.10 | `metrics/self_model.py` (160 LOC) | Migrate callers → `from clarvis.metrics import assess` |
| 2.11 | `infra/cost_api.py` (53 LOC) | Migrate callers → `from clarvis.orch import CostAPI` |
| 2.12 | `infra/cost_tracker.py` (200 LOC) | Migrate callers → `from clarvis.orch import CostTracker` |

**Acceptance criteria**: All 12 wrappers deleted. Zero remaining callers use legacy import paths for these modules.

**Payoff**: Eliminates 12 more bridge files. Scripts-side cognition/ and metrics/ become pure operational scripts, no more hybrid wrapper/library ambiguity.

---

### Phase 3: evolution/queue_writer.py Migration
**Goal**: Migrate the most-imported script (18 callers) to spine imports.
**Effort**: 1 session. **Risk**: Moderate (high caller count, but wrapper already delegates).
**Dependencies**: None.

| Task | Detail |
|---|---|
| 3.1 | Audit all 18 callers of `queue_writer.py` |
| 3.2 | Update each caller: `from evolution.queue_writer import add_task` → `from clarvis.queue import add_task` |
| 3.3 | Test each cron job that uses queue_writer |
| 3.4 | Once all callers migrated, delete `evolution/queue_writer.py` |

**Risk mitigation**: The wrapper already delegates to `clarvis.queue`. If any caller breaks, temporarily restore the wrapper. No logic changes needed — just import paths.

**Acceptance criteria**: `grep -r "from evolution.queue_writer\|from evolution import queue_writer\|import queue_writer" scripts/` returns zero results. Wrapper deleted.

**Payoff**: Eliminates the single highest-traffic legacy import path.

---

### Phase 4: Library Extraction — hooks/ Subsystem
**Goal**: Extract shared library logic from hooks/ into spine where it has multiple consumers.
**Effort**: 2 sessions. **Risk**: Moderate (hooks interact with brain and heartbeat).
**Dependencies**: Phases 1–2 (brain_mem wrappers gone, so import paths are clean).

**What moves to spine**:

| Script | Callers | Target Location | Rationale |
|---|---|---|---|
| `obligation_tracker.py` | 4 | `clarvis/cognition/obligations.py` | Tracks promises/commitments — cognitive function, not a hook |
| `workspace_broadcast.py` | 2 | Already in `clarvis/cognition/workspace_broadcast.py` | Just migrate callers |
| `soar_engine.py` | 1 | `clarvis/cognition/soar.py` | Cognitive architecture component |

**What stays in scripts/hooks/**:

| Script | Why |
|---|---|
| `session_hook.py` | Cron entry point |
| `temporal_self.py` | Cron entry point |
| `intra_linker.py` | Cron entry point |
| `actr_activation.py` | Cron entry point |
| `goal_tracker.py` | Cron entry point |
| `goal_hygiene.py` | Cron entry point |
| `canonical_state_refresh.py` | Cron entry point |
| `refresh_priorities.py` | 1 caller, but tightly coupled to session_hook |
| `session_transcript_logger.py` | 1 caller, operational logging |
| `directive_engine.py` | 1 caller, thin — not worth spine overhead |

**Acceptance criteria**: Migrated scripts have zero `sys.path` hacks. Original scripts deleted. Callers updated. Cron jobs pass.

**Payoff**: hooks/ becomes purely operational entry points. Shared cognitive logic lives in `clarvis.cognition`.

---

### Phase 5: Library Extraction — tools/ Subsystem
**Goal**: Move shared tool libraries into spine; keep operational tools as scripts.
**Effort**: 1–2 sessions. **Risk**: Low-moderate.
**Dependencies**: Phase 1 (brain_mem wrappers gone).

**What moves**:

| Script | Target | Rationale |
|---|---|---|
| `tools/prompt_builder.py` | `clarvis/context/prompt_builder.py` | Core to heartbeat context assembly; imported by preflight |
| `tools/context_compressor.py` | Already delegated to `clarvis/context/` | Just migrate remaining callers |
| `tools/prompt_optimizer.py` | `clarvis/context/prompt_optimizer.py` | 2 callers, optimization logic |

**What stays**:

| Script | Why |
|---|---|
| `tools/daily_memory_log.py` | Cron entry point |
| `tools/tool_maker.py` | 1 caller, specialized LATM tool — operational, not library |
| `tools/ast_surgery.py` | 1 caller, specialized AST tool |

**Acceptance criteria**: Migrated scripts accessible via `from clarvis.context import ...`. No sys.path hacks in callers.

**Payoff**: Context assembly is fully owned by `clarvis.context/`. No more cross-directory sys.path imports for prompt building.

---

### Phase 6: Wiki Subsystem Consolidation
**Goal**: Organize 12 root-level wiki_* scripts into a proper subsystem.
**Effort**: 2 sessions. **Risk**: Moderate (wiki is actively being developed).
**Dependencies**: WIKI_SPINE_REFACTOR_PLAN (P0 queue item) should define the target layout first.

**Proposed structure** (pending WIKI_SPINE_REFACTOR_PLAN decision):

```
clarvis/wiki/                     # Spine: shared library logic
├── __init__.py
├── canonical.py                  # From wiki_canonical.py (4 callers)
├── retrieval.py                  # From wiki_retrieval.py (1 caller)
└── store.py                      # Shared storage abstractions

scripts/wiki/                     # Operational: CLI tools and cron entry points
├── wiki_ingest.py               # CLI tool
├── wiki_query.py                # CLI tool
├── wiki_compile.py              # CLI tool
├── wiki_lint.py                 # CLI tool
├── wiki_brain_sync.py           # Standalone sync
└── wiki_backfill.py             # Manual maintenance (if kept)
```

**What gets deleted** (verified dead):
- `wiki_eval.py` — no callers, no cron
- `wiki_render.py` — no callers, no cron
- `wiki_maintenance.py` — says "for cron" but never wired
- `wiki_index.py` — no callers, no cron

**Acceptance criteria**: `wiki_canonical` importable as `from clarvis.wiki import canonical`. Root-level wiki_* scripts moved to `scripts/wiki/`. Dead scripts removed.

**Payoff**: Wiki subsystem has clear ownership. No more root-level script sprawl.

---

### Phase 7: Spine Internal sys.path Elimination
**Goal**: Eliminate all 17 sys.path hacks from within the spine itself.
**Effort**: 2–3 sessions. **Risk**: Moderate (touches CLI, metrics, core, and heartbeat).
**Dependencies**: Phases 1, 4, 5 (the scripts these modules import must be migrated first).

**CLI modules (5):**
| Module | Fix |
|---|---|
| `cli_context.py` | Import from `clarvis.context` (Phase 5) |
| `cli_bench.py` | Import from `clarvis.metrics` or subprocess |
| `cli_heartbeat.py` | Import from `clarvis.heartbeat` + subprocess for ops |
| `cli_maintenance.py` | Spine imports + subprocess for ops tasks |
| `cli_brain.py` | Direct spine imports (already partially done) |

**Metrics modules (4):**
| Module | Fix |
|---|---|
| `metrics/beam.py` | Inline needed logic or add to `clarvis.metrics` |
| `metrics/membench.py` | Same |
| `metrics/longmemeval.py` | Same |
| `metrics/evidence_scoring.py` | Same |

**Core modules (6):**
| Module | Fix |
|---|---|
| `orch/task_selector.py` | Pull needed scripts logic into spine or use subprocess |
| `orch/scoreboard.py` | Same |
| `memory/procedural_memory.py` | Replace scripts helper imports with spine equivalents |
| `memory/cognitive_workspace.py` | Same |
| `brain/retrieval_eval.py` | Inline or migrate needed evaluation logic |
| `brain/llm_rerank.py` | Same |

**Heartbeat modules (2):**
| Module | Fix |
|---|---|
| `heartbeat/adapters.py` | Import project_agent via subprocess, not import |
| `heartbeat/runner.py` | Use subprocess for script execution (appropriate here) |

**Design decision**: CLI and heartbeat modules that *orchestrate* scripts (run a cron job, trigger maintenance) should call scripts as subprocesses, not import them. Only *library logic* should be imported. Core/metrics modules should have their needed logic inlined or extracted into spine.

**Acceptance criteria**: Zero `sys.path.insert` in any `clarvis/*.py` file. `grep -r "sys.path" clarvis/` returns zero results (excluding `__pycache__`).

**Payoff**: The spine is self-contained. No import-time dependency on scripts/ layout.

---

### Phase 8: Cron Script Import Modernization
**Goal**: Update the ~37 cron entry point scripts to use spine imports instead of sys.path hacks.
**Effort**: 3–5 sessions (spread over time). **Risk**: Low per-script, moderate in aggregate.
**Dependencies**: Phases 1–5 (shared libraries must be in spine first).

**Approach**: Update imports in batches of 5–8 scripts per session. Each batch:
1. Pick scripts in the same subdirectory (e.g., all `cognition/*.py`)
2. Replace `sys.path.insert(0, ...)` + `from brain import brain` with `from clarvis.brain import brain`
3. Replace `from episodic_memory import ...` with `from clarvis.memory import ...`
4. Run the script's cron job or `--dry-run` to verify
5. Commit the batch

**Batch plan**:

| Batch | Scripts | Count |
|---|---|---|
| 8a | `cognition/absolute_zero.py`, `dream_engine.py`, `causal_model.py`, `knowledge_synthesis.py`, `clarvis_reflection.py`, `theory_of_mind.py` | 6 |
| 8b | `hooks/session_hook.py`, `temporal_self.py`, `intra_linker.py`, `actr_activation.py`, `goal_tracker.py`, `goal_hygiene.py`, `canonical_state_refresh.py` | 7 |
| 8c | `pipeline/heartbeat_preflight.py`, `heartbeat_postflight.py`, `evolution_preflight.py`, `execution_monitor.py` | 4 |
| 8d | `metrics/dashboard.py`, `performance_benchmark.py`, `daily_brain_eval.py`, `llm_brain_review.py`, `brain_effectiveness.py`, `orchestration_benchmark.py` | 6 |
| 8e | `evolution/failure_amplifier.py`, `research_to_queue.py`, `meta_learning.py`, `external_challenge_feed.py` | 4 |
| 8f | `brain_mem/brain_hygiene.py`, `graph_compaction.py`, `retrieval_quality.py`, `retrieval_benchmark.py` | 4 |
| 8g | `tools/daily_memory_log.py`, `infra/cost_checkpoint.py`, `data_lifecycle.py`, `generate_status_json.py` | 4 |
| 8h | `agents/project_agent.py`, `agent_lifecycle.py`, `agent_orchestrator.py` | 3 |

**Acceptance criteria per batch**: All modified scripts run without error. `sys.path.insert` count in scripts/ drops by batch size.

**Payoff**: Import modernization without structural changes. Scripts stay where they are but use clean imports.

---

### Phase 9: Structural Cleanup and End-State Verification
**Goal**: Final cleanup, documentation, and verification that the end-state is reached.
**Effort**: 1 session. **Risk**: Minimal.
**Dependencies**: All prior phases.

| Task | Detail |
|---|---|
| 9.1 | Delete `scripts/_paths.py` if no remaining callers (or keep if still needed by shell-launched scripts) |
| 9.2 | Verify: `grep -r "sys.path.insert" clarvis/` returns 0 |
| 9.3 | Verify: `grep -r "sys.path.insert" scripts/` — remaining count is ≤10 (shell-launched cron scripts that need PYTHONPATH) |
| 9.4 | Run full test suite |
| 9.5 | Run all cron jobs in `--dry-run` mode |
| 9.6 | Update `CLAUDE.md` import conventions section |
| 9.7 | Update `docs/ARCHITECTURE.md` package layout diagram |
| 9.8 | Update `SELF.md` with accurate module counts |
| 9.9 | Archive `docs/SPINE_USAGE_AUDIT.md` (add "SUPERSEDED" header) |
| 9.10 | Write `docs/SPINE_MIGRATION_COMPLETE.md` — final state snapshot |

**Acceptance criteria**: All items verified. Documentation matches reality.

---

## 4. End-State Definition

### What "fully done" looks like

```
clarvis/                          # THE SPINE — all shared library logic
├── brain/          (19 files)    # Core data layer
├── memory/         (9 files)     # Memory systems
├── cognition/      (14 files)    # +obligations, +soar from hooks/
├── context/        (10 files)    # +prompt_builder, +prompt_optimizer from tools/
├── metrics/        (18 files)    # Unchanged
├── queue/          (3 files)     # Unchanged
├── orch/           (12 files)    # Unchanged
├── heartbeat/      (10 files)    # Unchanged
├── wiki/           (4 files)     # NEW: canonical, retrieval, store
├── runtime/        (2 files)     # Unchanged
├── learning/       (2 files)     # Unchanged (wire into heartbeat separately)
├── adapters/       (3 files)     # Unchanged
├── cli_*.py        (15 files)    # ZERO sys.path hacks
└── __init__.py, __main__.py

scripts/                          # OPERATIONAL ENTRY POINTS — cron jobs, CLI tools, one-shots
├── agents/         (4 files)     # Agent spawning/orchestration
├── brain_mem/      (6 files)     # brain.py (CLI), brain_hygiene, graph_compaction, retrieval_*
├── cognition/      (8 files)     # absolute_zero, dream_engine, causal_model, etc.
├── cron/           (25 .sh)      # Shell launchers — UNCHANGED
├── evolution/      (5 files)     # failure_amplifier, research_to_queue, etc.
├── hooks/          (9 files)     # session_hook, temporal_self, goal_*, etc.
├── infra/          (8 .sh + 5 .py) # Backup, health, install, cost_checkpoint
├── metrics/        (10 files)    # dashboard, benchmarks, brain_eval, etc.
├── pipeline/       (4 files)     # heartbeat_preflight, postflight, etc.
├── tools/          (4 files)     # daily_memory_log, tool_maker, ast_surgery
└── wiki/           (5 files)     # NEW: ingest, query, compile, lint, sync
```

### Structural Invariants (must hold after migration)

1. **No sys.path hacks in clarvis/**. The spine imports only from itself, stdlib, and pip-installed packages.
2. **scripts/ never imports from scripts/**. Each script imports from `clarvis.*` or stdlib. The `_paths.py` helper is deleted or vestigial.
3. **Every file in scripts/ is either a cron entry point, a CLI tool, or an operator utility**. No file in scripts/ is imported by 2+ other files (those belong in the spine).
4. **brain_mem/ has no thin wrappers**. The only files are brain.py (CLI + backward compat), brain_hygiene.py, graph_compaction.py, and retrieval tools.
5. **The spine __init__.py files export stable public APIs**. External code (scripts, tests) imports from package level, not from internal modules.

### Ownership Map

| Domain | Spine (library) | Scripts (operational) |
|---|---|---|
| **Brain** | `clarvis.brain` | `brain_mem/brain.py` (CLI), `brain_hygiene.py`, `graph_compaction.py` |
| **Memory** | `clarvis.memory` | (none — all library logic in spine) |
| **Cognition** | `clarvis.cognition` | `absolute_zero.py`, `dream_engine.py`, `causal_model.py`, etc. |
| **Context** | `clarvis.context` | (none) |
| **Metrics** | `clarvis.metrics` | `dashboard.py`, `performance_benchmark.py`, `daily_brain_eval.py`, etc. |
| **Queue** | `clarvis.queue` | (none — evolution/queue_writer.py deleted) |
| **Heartbeat** | `clarvis.heartbeat` | `pipeline/heartbeat_preflight.py`, `heartbeat_postflight.py` |
| **Wiki** | `clarvis.wiki` | `scripts/wiki/ingest.py`, `query.py`, `compile.py`, `lint.py` |
| **Agents** | (none yet) | `agents/project_agent.py`, `agent_lifecycle.py`, `agent_orchestrator.py` |
| **Hooks** | (minimal — obligations, soar) | `session_hook.py`, `temporal_self.py`, `goal_*.py`, etc. |
| **Infra** | (none) | All shell + Python ops scripts |
| **Evolution** | (none — queue_writer migrated) | `failure_amplifier.py`, `research_to_queue.py`, etc. |

---

## 5. Traps to Avoid

### 5.1 False Dead-Code Assumptions
The SPINE_USAGE_AUDIT incorrectly flagged 23+ scripts as dead. Before deleting anything:
- Check `crontab -l` (not just shell scripts)
- Check `grep -r` for subprocess calls, dynamic imports, `__import__`
- Check shell scripts for `python3 scripts/path/to/file.py` patterns
- Read the script — does it have a useful `__main__` CLI?
- If unsure, move to `scripts/archive/` instead of deleting

### 5.2 Over-Migration
Not every library needs to be in the spine. Signs of over-migration:
- Moving a script that has exactly 1 caller (just update that caller's import, don't move the file)
- Creating spine modules with a single 50-line file (overhead > value)
- Moving operational logic (file I/O, Telegram calls, subprocess management) into library modules
- Breaking the "spine is pure library, scripts are operational" boundary

### 5.3 Wrapper Drift
When a wrapper exists alongside its spine equivalent:
- The wrapper may accumulate local patches that diverge from the spine
- Callers may import from either location inconsistently
- The wrapper may be tested while the spine equivalent is not (or vice versa)
- **Fix**: Migrate callers and delete wrappers promptly. Don't let both exist for weeks.

### 5.4 Breakage of Cron/CLI Paths
Cron jobs run in a specific environment (`cron_env.sh` sets PATH, PYTHONPATH, etc.). After migration:
- Verify scripts still work from cron context (not just interactive shell)
- The `PYTHONPATH` must include the workspace root for `from clarvis.` to resolve
- Test with: `source scripts/cron/cron_env.sh && python3 scripts/path/to/script.py`

### 5.5 Import-Time Side Effects
Some scripts execute code at import time (ChromaDB connections, file reads). When moving these into spine modules:
- Wrap expensive initialization in lazy singletons (the brain module already does this well)
- Don't let `import clarvis.wiki` trigger a ChromaDB connection
- Use the `_LazyBrain` pattern as a reference

### 5.6 Circular Import Traps
The spine uses hook-based dependency injection to break cycles (brain ↔ memory ↔ cognition). When adding new modules:
- Register hooks lazily, not at import time
- Use the `clarvis.brain.hooks` pattern (factory functions, deferred registration)
- Test with: `python3 -c "from clarvis.X import Y"` — if it hangs or errors, there's a cycle

---

## 6. Execution Schedule and Dependencies

```
Phase 0 (Dead Code)         ─── standalone, do first
Phase 1 (brain_mem wrappers) ─── standalone
Phase 2 (cognition/metrics)  ─── standalone, parallel with Phase 1
Phase 3 (queue_writer)       ─── standalone, parallel with 1-2
Phase 4 (hooks extraction)   ─── after Phase 1 (clean brain_mem imports)
Phase 5 (tools extraction)   ─── after Phase 1 (clean brain_mem imports)
Phase 6 (wiki consolidation) ─── after WIKI_SPINE_REFACTOR_PLAN (P0 queue item)
Phase 7 (CLI normalization)  ─── after Phases 4 + 5 (migrated libraries available)
Phase 8 (cron modernization) ─── after Phases 1-5 (all libraries in spine)
Phase 9 (final cleanup)      ─── after all phases
```

**Parallelism**: Phases 1, 2, 3 can run in parallel. Phase 6 is independent of 1–5 but blocked on wiki planning. Phase 8 is the longest (3–5 sessions) and can be spread over multiple days.

**Total effort**: ~15–20 sessions across all phases.

---

## 7. Metrics and Progress Tracking

### Migration Progress Score

Track two metrics after each phase:

1. **sys.path hack count**: `grep -rc "sys.path.insert\|sys.path.append" scripts/ clarvis/ | grep -v ":0$" | wc -l`
   - Current: ~91 files
   - Target: ≤10 files (only shell-launched cron scripts)

2. **Wrapper count**: Number of files in scripts/ that are pure re-exports of spine modules.
   - Current: ~20 files
   - Target: 0 files (brain.py can keep its CLI but must not be a re-export)

### Phase Completion Checklist

After each phase, verify:
- [ ] `python3 -m pytest tests/ -x -q` — no new failures
- [ ] `python3 -m clarvis brain health` — healthy
- [ ] `python3 -c "from clarvis import __version__"` — imports clean
- [ ] Modified cron jobs run without error (test in cron context)
- [ ] `grep -r "sys.path" clarvis/` — count decreased or unchanged

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cron job breaks after import change | Medium | High (missed autonomous cycle) | Test each script in cron context before committing. Keep wrapper as fallback for 24h. |
| Circular import introduced | Low | Medium (import error) | Test `python3 -c "from clarvis.X import Y"` for every new spine module. Use lazy imports. |
| brain_mem/brain.py callers break | Medium | High (brain.py is the most-imported script) | Migrate callers incrementally. Keep brain.py CLI working throughout. |
| Wiki migration conflicts with active wiki development | Medium | Low (wiki is P0 queue) | Phase 6 is blocked on WIKI_SPINE_REFACTOR_PLAN. Don't start until wiki layout is decided. |
| Over-migration creates maintenance burden | Low | Medium | Follow decision framework (§1). Don't migrate 1-caller scripts. |

---

## Appendix A: Queue-Ready Task Blocks

```
## P0 — Current Sprint

- [ ] [DEAD_CODE_REMOVAL] Delete confirmed dead scripts: brain_mem/lite_brain.py, brain_mem/cognitive_workspace.py. Verify 8 likely-dead scripts (dashboard_server, latency_budget, benchmark_brief, automation_insights, meta_gradient_rl, research_lesson_store, clone_test_verify, hyperon_atomspace). Delete verified ones. [spine, cleanup, hygiene]

## P1 — Next Sprint

- [ ] [WRAPPER_CLEANUP_BRAIN_MEM] Migrate all callers of brain_mem/ thin wrappers (episodic_memory, hebbian_memory, memory_consolidation, procedural_memory, synaptic_memory, working_memory, brain_bridge) to clarvis.memory imports. Delete wrappers after migration. Verify cron jobs. [spine, migration, brain_mem]
- [ ] [WRAPPER_CLEANUP_COGNITION] Migrate callers of cognition/ stubs (attention, clarvis_confidence, clarvis_reasoning, reasoning_chains, thought_protocol, cognitive_load) to clarvis.cognition imports. Delete stubs. [spine, migration, cognition]
- [ ] [WRAPPER_CLEANUP_METRICS] Migrate callers of metrics/ re-exports (phi_metric, orchestration_scoreboard, clr_benchmark, self_model) and infra/ re-exports (cost_api, cost_tracker) to spine imports. Delete wrappers. [spine, migration, metrics]
- [ ] [QUEUE_WRITER_MIGRATION] Migrate all 18 callers of evolution/queue_writer.py to clarvis.queue imports. Delete wrapper. Test all cron jobs that use queue injection. [spine, migration, queue]

## P2 — Planned

- [ ] [HOOKS_LIBRARY_EXTRACTION] Extract obligation_tracker.py → clarvis/cognition/obligations.py, soar_engine.py → clarvis/cognition/soar.py. Migrate callers. Keep cron entry points in scripts/hooks/. [spine, migration, hooks]
- [ ] [TOOLS_LIBRARY_EXTRACTION] Extract prompt_builder.py → clarvis/context/prompt_builder.py, prompt_optimizer.py → clarvis/context/prompt_optimizer.py. Migrate callers. Keep operational tools in scripts/tools/. [spine, migration, tools]
- [ ] [SPINE_SYSPATH_ELIMINATION] Remove all 17 sys.path hacks from within clarvis/ (5 CLI, 4 metrics, 6 core, 2 heartbeat modules). Use spine imports, inline logic, or subprocess calls. Target: zero sys.path in clarvis/. [spine, cli, normalization]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_A] Update cognition/ cron scripts (absolute_zero, dream_engine, causal_model, knowledge_synthesis, clarvis_reflection, theory_of_mind) to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_B] Update hooks/ cron scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_C] Update pipeline/ scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_D] Update metrics/ cron scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_E] Update evolution/ cron scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_F] Update brain_mem/ cron scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_G] Update tools/ and infra/ cron scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [CRON_IMPORT_MODERNIZE_BATCH_H] Update agents/ scripts to use clarvis.* imports. [spine, migration, cron]
- [ ] [SPINE_MIGRATION_FINAL_CLEANUP] Delete _paths.py if unused. Update CLAUDE.md, ARCHITECTURE.md, SELF.md. Archive SPINE_USAGE_AUDIT.md. Write SPINE_MIGRATION_COMPLETE.md. [spine, docs, final]
```

---

## Appendix B: What Intentionally Stays Outside the Spine

These files will **never** move to `clarvis/` and that is correct:

| Category | Files | Reason |
|---|---|---|
| **Cron shell launchers** | 25 .sh files in `scripts/cron/` | Entry points, not library code |
| **Infrastructure** | `backup_daily.sh`, `health_monitor.sh`, `safe_update.sh`, etc. | Operational, external-facing |
| **One-time tools** | `graph_cutover.py`, `graph_migrate_to_sqlite.py` | Historical migration tools |
| **Agent spawners** | `spawn_claude.sh`, `agent_orchestrator.py` | Subprocess management |
| **Cron entry points** | All 37 Python scripts listed in §2.1 | Called by crontab, not imported |
| **brain.py CLI** | `brain_mem/brain.py` | Backward-compatible CLI; delegates to spine but provides `python3 scripts/brain_mem/brain.py` entry point |

This is not a failure of migration. The spine/scripts split is the intended architecture: **spine = importable library, scripts = runnable operations**.

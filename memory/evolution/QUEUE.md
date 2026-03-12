# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat


---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)


## Pillar 2: Agent Orchestrator (Multi-Project Command Center)

_Design: `docs/ORCHESTRATOR_PLAN_2026-03-06.md` — 5-phase rollout._

### Phase 1: Scoreboard + Trust (P0)

### Phase 2: Multi-Session Loop (P0)

### Phase 3: Cron Integration (P1)

### Phase 4: Enhanced Brain (P1)

### Phase 5: Visual Ops Dashboard (P1)
_Design informed by claw-empire visual deep dive (`docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`). Stack: Starlette SSE + vanilla JS + PixiJS 8._
  - Shows: current QUEUE tasks, active task being executed, recent evolution runs, subagents list + their current tasks/status, and PR/CI outcomes.
  - Style: 2D game-ish rooms/avatars (procedural PixiJS Graphics for rooms/furniture, emoji-based agents with status particles — same approach as claw-empire but simpler: 1 room, no CEO movement, no sub-clone fireworks).
  - Data sources: `memory/evolution/QUEUE.md`, `memory/cron/digest.md`, `memory/cron/autonomous.log`, `memory/cron/marathon.log`, `scripts/orchestration_scoreboard.py` outputs, `data/invariants_runs.jsonl`, GitHub PR list via `gh` (read-only).
  - 6 SSE event types: `task_started`, `task_completed`, `agent_status`, `queue_update`, `cron_activity`, `pr_update`.



### Steal List (from claw-empire review, P1)

### Deferred

## Pillar 3: Autonomous Execution (Success > 85%)


## Adaptive RAG Pipeline (Context Relevance > 0.90)

_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout based on CRAG/Self-RAG/Adaptive-RAG research._
_Dependency chain: GATE → EVAL → RETRY → FEEDBACK. Each phase is independently useful._

- [~] [CONTEXT_RELEVANCE_FEEDBACK_LOOP] Close the context relevance feedback loop: wire `context_relevance.aggregate_relevance()` per-section scores back into `clarvis/context/assembly.py` TIER_BUDGETS so consistently-unreferenced sections auto-shrink their token budget. Currently `TIER_BUDGETS` are hardcoded dicts; add a `load_relevance_weights()` that reads `data/retrieval_quality/brief_v2_report.json` and scales budgets proportionally. Fallback to static budgets when no report exists. _(Targets weakest metric: Context Relevance=0.820)_
  - [ ] [AUTO_SPLIT 2026-03-12] [CONTEXT_RELEVANCE_FEEDBACK_LOOP_1] Analyze: read relevant source files, identify change boundary
  - [ ] [AUTO_SPLIT 2026-03-12] [CONTEXT_RELEVANCE_FEEDBACK_LOOP_2] Implement: core logic change in one focused increment
  - [ ] [AUTO_SPLIT 2026-03-12] [CONTEXT_RELEVANCE_FEEDBACK_LOOP_3] Test: add/update test(s) covering the new behavior
  - [ ] [AUTO_SPLIT 2026-03-12] [CONTEXT_RELEVANCE_FEEDBACK_LOOP_4] Verify: run existing tests, confirm no regressions
- [~] [SEMANTIC_TASK_MATCHING] Replace word-overlap Jaccard scoring in `clarvis/context/assembly.py:find_related_tasks` (lines 380-409) with brain semantic search via `from clarvis.brain import search`. Current approach misses tasks with similar meaning but different vocabulary. Also filter results by QUEUE section priority (P0/P1/P2) so low-priority tasks don't crowd the brief. _(Targets Context Relevance — richer related-task context)_
  - [ ] [AUTO_SPLIT 2026-03-12] [SEMANTIC_TASK_MATCHING_1] Analyze: read relevant source files, identify change boundary
  - [ ] [AUTO_SPLIT 2026-03-12] [SEMANTIC_TASK_MATCHING_2] Implement: core logic change in one focused increment
  - [ ] [AUTO_SPLIT 2026-03-12] [SEMANTIC_TASK_MATCHING_3] Test: add/update test(s) covering the new behavior
  - [ ] [AUTO_SPLIT 2026-03-12] [SEMANTIC_TASK_MATCHING_4] Verify: run existing tests, confirm no regressions

## Research Sessions


## Pillar 3: Performance & Reliability (PI > 0.70)


### AGI-Readiness (from 2026-03-04 audit, see docs/AGI_READINESS_ARCHITECTURE_AUDIT.md)

  - **Done**: `clarvis/brain/factory.py` — `get_chroma_client(path)` (singleton per abs-path), `get_embedding_function(use_onnx)` (singleton ONNX model), `reset_singletons()` (test helper). Thread-safe with double-checked locking.
  - **Done**: ClarvisBrain wired (`__init__.py` lines 56, 126 → factory). LiteBrain wired (`lite_brain.py` lines 62-68, 82-86 → factory). Both embedding + client consolidated.
  - **Done**: 8 factory tests in `tests/test_clarvis_brain.py` — singleton identity, path isolation, collection consistency, embedding singleton, reset. All 87 tests pass.
  - **Done (Step 3)**: Test fixtures (`conftest.py` tmp_brain, `test_clarvis_brain.py` brain_instance) now use `get_chroma_client()` + `reset_singletons()` cleanup. No direct `chromadb.PersistentClient` in test fixtures. All 87 tests pass.
  - VectorStore (`packages/clarvis-db`) intentionally unchanged (standalone package, own lifecycle).

### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)


### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop


## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

_Consolidated into Pillar 2 above. See `docs/ORCHESTRATOR_PLAN_2026-03-06.md` for full design._


## Backlog


## Non-Code Improvements

- [~] [HEARTBEAT_DOC_REFRESH] Update HEARTBEAT.md stale cron frequency counts: line 155 says "6x/day" → actual is 12x/day; line 167 says "8x" → 12x. Add missing jobs to daily rhythm section (cron_cleanup.sh Sun 05:30, cron_absolute_zero.sh Sun 03:00, brain_hygiene.py). Fix legacy API reference on line 100 (`brain.optimize(full=True)` → `python3 -m clarvis brain optimize-full`). Also update `skills/clarvis-brain/SKILL.md` memory counts from "1175+ memories, 48k+ edges" to actual (3401 memories, 129k edges). _(Non-Python documentation task)_
  - [ ] [AUTO_SPLIT 2026-03-12] [HEARTBEAT_DOC_REFRESH_1] Analyze: read relevant source files, identify change boundary
  - [ ] [AUTO_SPLIT 2026-03-12] [HEARTBEAT_DOC_REFRESH_2] Implement: core logic change in one focused increment
  - [ ] [AUTO_SPLIT 2026-03-12] [HEARTBEAT_DOC_REFRESH_3] Test: add/update test(s) covering the new behavior
  - [ ] [AUTO_SPLIT 2026-03-12] [HEARTBEAT_DOC_REFRESH_4] Verify: run existing tests, confirm no regressions


## P1

- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling. _(Phase 1 done 2026-03-10: `pr_factory_rules.py` → `clarvis/orch/pr_rules.py`, `pr_factory_intake.py` → `clarvis/orch/pr_intake.py`, `pr_factory_indexes.py` → `clarvis/orch/pr_indexes.py`. Scripts converted to thin deprecated wrappers. 70/70 tests pass. Remaining: `pr_factory.py` (Phase 3 execution brief), `project_agent.py` (large, multi-session), `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine. _(2026-03-10: Audited 8 scripts. pr_factory_{rules,intake,indexes} already thin wrappers — updated 5 callers to import from canonical `clarvis.orch.*` directly. phi_metric.py already done. context_compressor.py blocked on `compress_health` migration. heartbeat_{pre,post}flight.py are canonical sources — inverted delegation, multi-session migration needed.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions. _(2026-03-12: Second migration — `cron_reflection.sh` inline `brain.optimize()` → `python3 -m clarvis brain optimize`. Removed 6-line legacy `sys.path + from brain import brain` inline Python block. 2026-03-10: First migration — `cron_reflection.sh` brain.py crosslink → `python3 -m clarvis brain crosslink`. Added `monthly_reflection` to cli_cron.py known jobs. Remaining: `cron_report_{morning,evening}.sh` use `from brain import brain; brain.stats()` inside larger inline Python heredocs — needs restructuring, not simple substitution. Next candidate: context_compressor gc.)_

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.


## P1 — This Week

- [ ] [RETRIEVAL_GATE_TESTS] Add unit tests for `clarvis/brain/retrieval_gate.py`. This module runs 12x/day to classify retrieval depth (NO_RETRIEVAL/LIGHT/DEEP) but has zero test coverage. Test: keyword matching, tier classification thresholds, edge cases (empty task text, very long queries). A regression here silently degrades all heartbeat retrieval.
- [ ] [MMR_POSTFLIGHT_RATE_LIMIT] Gate `mmr_update_lambdas()` call in `heartbeat_postflight.py` to skip when (a) task was classified NO_RETRIEVAL (no useful signal) or (b) fewer than 10 new episodes since last update (check `episodes` field in `data/adaptive_mmr_state.json`). Currently scans full 7-day `context_relevance.jsonl` window on every postflight (12x/day) — wasteful I/O with no signal on retrieval-free tasks.

## P2 — When Idle

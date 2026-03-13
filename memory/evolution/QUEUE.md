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



## P1

- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling. _(Phase 1 done 2026-03-10: `pr_factory_rules.py` → `clarvis/orch/pr_rules.py`, `pr_factory_intake.py` → `clarvis/orch/pr_intake.py`, `pr_factory_indexes.py` → `clarvis/orch/pr_indexes.py`. Scripts converted to thin deprecated wrappers. 70/70 tests pass. Remaining: `pr_factory.py` (Phase 3 execution brief), `project_agent.py` (large, multi-session), `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine. _(2026-03-10: Audited 8 scripts. pr_factory_{rules,intake,indexes} already thin wrappers — updated 5 callers to import from canonical `clarvis.orch.*` directly. phi_metric.py already done. context_compressor.py blocked on `compress_health` migration. heartbeat_{pre,post}flight.py are canonical sources — inverted delegation, multi-session migration needed.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions. _(2026-03-12: Second migration — `cron_reflection.sh` inline `brain.optimize()` → `python3 -m clarvis brain optimize`. Removed 6-line legacy `sys.path + from brain import brain` inline Python block. 2026-03-10: First migration — `cron_reflection.sh` brain.py crosslink → `python3 -m clarvis brain crosslink`. Added `monthly_reflection` to cli_cron.py known jobs. Remaining: `cron_report_{morning,evening}.sh` use `from brain import brain; brain.stats()` inside larger inline Python heredocs — needs restructuring, not simple substitution. Next candidate: context_compressor gc.)_

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.


## NEW ITEMS

- [ ] [EXECUTION_MONITOR_ALL_SPAWNERS] Extend `execution_monitor.py` integration from only `cron_autonomous.sh` to all Claude-spawning cron scripts: `cron_morning.sh`, `cron_evolution.sh`, `cron_implementation_sprint.sh`, `cron_reflection.sh`, `cron_research.sh`. Currently only autonomous runs get mid-execution monitoring — other spawners run blind. Improves autonomous execution reliability.
- [ ] [CODE_QUALITY_METRIC_COMPLETENESS] Wire `first_pass_success_rate` and `test_pass_rate` into the composite code_quality_score in `clarvis/metrics/quality.py`. Currently both return None and don't contribute — the 0.655 score is computed from only 3 of 5 sub-metrics. (1) Add a postflight step to capture pytest results into `data/test_results.json` so test_pass_rate has fresh data. (2) Tag code-specific episodes in episodic memory so first_pass_success_rate can find ≥5 qualifying episodes. Directly targets Code Generation Quality 0.655→0.75.
- [ ] [CRON_SHELLCHECK_LINT] Non-code quality: install ShellCheck and run it against all `.sh` scripts in `scripts/`. Fix all findings rated "error" or "warning" severity. Cron orchestrators (`cron_autonomous.sh`, `cron_morning.sh`, etc.) are bash with zero lint coverage — this is the non-Python equivalent of the code quality metric gap.
- [x] [RESEARCH_IMPLEMENTATION_BRIDGE] Create `scripts/research_to_queue.py` that scans `memory/research/ingested/` for papers with actionable findings, cross-references QUEUE.md for existing tasks, and prints candidate queue items for unimplemented research. Start with the 4 ingested papers (code_generation_agent_survey, sage_rl, self_debugging_architectures, veriguard_ticoder). Run monthly via cron_reflection.sh. _(Done 2026-03-13: Script created. Scans 19 papers, found 218 uncovered proposals. Top: multi-path planning for Code Gen Quality. 5 brain memories stored.)_

## P1 — This Week


## P2 — When Idle

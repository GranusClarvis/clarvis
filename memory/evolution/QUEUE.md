# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat


---

## Pillar 1: Integration & Coherence (legacy label; deprioritized)

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

- [~] [RESEARCH_DISCOVERY 2026-03-16] Research: SParC-RAG — Adaptive Sequential-Parallel Scaling with Context Management (arXiv:2602.00083). Multi-agent RAG with Query Rewriter (diversity), Answer Evaluator (stop criterion), and Context Manager (cross-round evidence consolidation + noise filtering). +6.2 F1 on multi-hop QA. Targets Context Relevance (0.387→0.75) via principled multi-round retrieval with selective integration. Compare to A-RAG hierarchical retrieval and MacRAG multi-scale. Source: arxiv.org/abs/2602.00083
- [x] [RESEARCH_DISCOVERY 2026-03-16] Research: SWE-Pruner — Self-Adaptive Context Pruning for Coding Agents (arXiv:2601.16746). (2026-03-17: Research complete. 5 brain memories stored. Note: memory/research/swe_pruner_sparc_rag_context_pruning.md)
  - [x] [AUTO_SPLIT 2026-03-16] [RESEARCH_DISCOVERY 2026-03-16_2] Implement: core logic change in one focused increment (2026-03-17: Deep research on SWE-Pruner + SParC-RAG. 5 brain memories stored. Research note: memory/research/swe_pruner_sparc_rag_context_pruning.md. Key finding: line-level goal-conditioned pruning within sections + enriched related_tasks are highest-ROI improvements for Context Relevance.)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling. _(Phase 1 done 2026-03-10: `pr_factory_rules.py` → `clarvis/orch/pr_rules.py`, `pr_factory_intake.py` → `clarvis/orch/pr_intake.py`, `pr_factory_indexes.py` → `clarvis/orch/pr_indexes.py`. Scripts converted to thin deprecated wrappers. 70/70 tests pass. Remaining: `pr_factory.py` (Phase 3 execution brief), `project_agent.py` (large, multi-session), `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine. _(2026-03-10: Audited 8 scripts. pr_factory_{rules,intake,indexes} already thin wrappers — updated 5 callers to import from canonical `clarvis.orch.*` directly. phi_metric.py already done. context_compressor.py blocked on `compress_health` migration. heartbeat_{pre,post}flight.py are canonical sources — inverted delegation, multi-session migration needed.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions. _(2026-03-14: Third migration — `cron_report_{morning,evening}.sh` `from brain import brain; brain.stats()` → `subprocess.run(['python3', '-m', 'clarvis', 'brain', 'stats'])`. 2026-03-12: Second — `cron_reflection.sh` `brain.optimize()` → `python3 -m clarvis brain optimize`. 2026-03-10: First — `cron_reflection.sh` `brain.py crosslink` → `python3 -m clarvis brain crosslink`. Next candidate: context_compressor gc.)_

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.


## NEW ITEMS


- [~] [HEARTBEAT_POSTFLIGHT_DECOMPOSITION] `run_postflight()` in `scripts/heartbeat_postflight.py` is 1457 lines — the largest function in the codebase. Decompose into 10-15 named sub-functions (one per §section) called from a clean dispatcher. Preserve all behavior; each section (§1 episode encoding through §14 cleanup) becomes its own testable function. Directly improves `reasonable_function_length` metric (currently 0.739, 79 functions >100 lines). **Targets Code Generation Quality.** P1.
  - [ ] [AUTO_SPLIT 2026-03-13] [HEARTBEAT_POSTFLIGHT_DECOMPOSITION_3] Test: add/update test(s) covering the new behavior

- [~] [CONTEXT_RELATED_TASKS_QUALITY 2026-03-16] `related_tasks` has the highest importance weight (0.304) but often scores 0.0 containment in recent episodes. Root-cause: the section likely contains task titles/queue items that share zero tokens with Claude Code output. Fix: in `assembly.py`, enrich `related_tasks` with actionable context (file paths, function names, concrete overlap with current task) instead of raw queue lines. Validate by checking containment on 5+ recent episodes. **Targets Context Relevance (weakest metric).** P1.
  - [ ] [AUTO_SPLIT 2026-03-16] [CONTEXT_RELATED_TASKS_QUALITY 2026-03-16_1] Analyze: read relevant source files, identify change boundary
  - [ ] [AUTO_SPLIT 2026-03-16] [CONTEXT_RELATED_TASKS_QUALITY 2026-03-16_2] Implement: core logic change in one focused increment
  - [ ] [AUTO_SPLIT 2026-03-16] [CONTEXT_RELATED_TASKS_QUALITY 2026-03-16_3] Test: add/update test(s) covering the new behavior





## P1 — This Week


## P2 — When Idle

## P0 — Do Next Heartbeat (2026-03-14)


## P0 — Stabilization / Improvement Window (next several days)


## P0 — Brain v2 / Clarvis Quality Window



## P0 — Fork Integration Execution Phases

### Phase 1 — Architecture Contracts & Benchmark Core

### Phase 2 — Mode System

### Phase 3 — Host Compatibility & Open-Source Readiness

### Phase 4 — Wiring Into Real Runtime

### Phase 5 — Public Surface (only after readiness gates)

### Guard Rails / Explicit Non-Goals

## P1 — Agent Benchmarking

### Research Additions


### CLR Benchmark — Clarvis Agent Score

_Superseded by fork merge tasks above. Implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions). See `FORK_MERGE_CLR` task._

### A/B Comparison Benchmark (Fixed)

Fix ab_comparison_benchmark.py:
- Write prompts to temp file, read via stdin or file flag
- Or use direct API calls instead of spawn_claude.sh
- Run 10+ comparison pairs with hard tasks (not trivial "count files")
- Measure: success rate, quality score, duration, context usage

Wiring: Results should feed into evolution queue as metrics.

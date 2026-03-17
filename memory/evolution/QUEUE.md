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

- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling. _(Phase 1 done 2026-03-10: `pr_factory_rules.py` → `clarvis/orch/pr_rules.py`, `pr_factory_intake.py` → `clarvis/orch/pr_intake.py`, `pr_factory_indexes.py` → `clarvis/orch/pr_indexes.py`. Scripts converted to thin deprecated wrappers. 70/70 tests pass. Remaining: `pr_factory.py` (Phase 3 execution brief), `project_agent.py` (large, multi-session), `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine. _(2026-03-10: Audited 8 scripts. pr_factory_{rules,intake,indexes} already thin wrappers — updated 5 callers to import from canonical `clarvis.orch.*` directly. phi_metric.py already done. context_compressor.py blocked on `compress_health` migration. heartbeat_{pre,post}flight.py are canonical sources — inverted delegation, multi-session migration needed.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions. _(2026-03-14: Third migration — `cron_report_{morning,evening}.sh` `from brain import brain; brain.stats()` → `subprocess.run(['python3', '-m', 'clarvis', 'brain', 'stats'])`. 2026-03-12: Second — `cron_reflection.sh` `brain.optimize()` → `python3 -m clarvis brain optimize`. 2026-03-10: First — `cron_reflection.sh` `brain.py crosslink` → `python3 -m clarvis brain crosslink`. Next candidate: context_compressor gc.)_

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.


## NEW ITEMS


- [~] [HEARTBEAT_POSTFLIGHT_DECOMPOSITION] `run_postflight()` in `scripts/heartbeat_postflight.py` is 1457 lines — the largest function in the codebase. Decompose into 10-15 named sub-functions (one per §section) called from a clean dispatcher. Preserve all behavior; each section (§1 episode encoding through §14 cleanup) becomes its own testable function. Directly improves `reasonable_function_length` metric (currently 0.739, 79 functions >100 lines). **Targets Code Generation Quality.** P1.

- [~] [CONTEXT_RELATED_TASKS_QUALITY 2026-03-16] `related_tasks` has the highest importance weight (0.304) but often scores 0.0 containment in recent episodes. Root-cause: the section likely contains task titles/queue items that share zero tokens with Claude Code output. Fix: in `assembly.py`, enrich `related_tasks` with actionable context (file paths, function names, concrete overlap with current task) instead of raw queue lines. Validate by checking containment on 5+ recent episodes. **Targets Context Relevance (weakest metric).** P1.





## P1 — This Week


## P2 — When Idle

## P0 — Do Next Heartbeat (2026-03-14)


## P0 — Stabilization / Improvement Window (next several days)


## P0 — Brain v2 / Clarvis Quality Window



## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)

### Delivery Goal
Presentable Clarvis by 2026-03-31:
- open-source-ready main repo
- working/public-ready website v0
- clean repo boundaries and consolidation plan
- stronger Clarvis brain / recall / context quality
- reliable orchestration and benchmarks
- clearly wired, tested, maintainable structure

### Milestone A — Foundation Freeze (by 2026-03-19)
- [ ] [DLV_DEADLINE_LOCK_2026-03-17] Lock the next 14 days around delivery work only: cleanup, consolidation, wiring, testing, context quality, website, open-source readiness. No broad feature expansion unless required for delivery.
- [ ] [DLV_CRITICAL_PATH_BOARD_2026-03-17] Create a single critical-path delivery board/status artifact for the 14-day window with milestone tracking and blockers.
- [ ] [DLV_QUEUE_PRUNE_2026-03-17] Prune or demote non-essential queue items that do not contribute directly to: presentability, open-source readiness, website, brain quality, or orchestration reliability.
- [ ] [DLV_OPEN_SOURCE_GAP_AUDIT_2026-03-17] Produce a hard gap list: what still blocks public repo release today.

### Milestone B — Brain / Context Quality (by 2026-03-23)
- [ ] [DLV_CONTEXT_RELEVANCE_RECOVERY_2026-03-17] Raise Context Relevance from current weak state via related_tasks quality, section quality, pruning, and better scoring.
- [ ] [DLV_BRAIN_QUERY_POLICY_2026-03-17] Implement or refine explicit policy for when Clarvis should query memory vs stay lean.
- [ ] [DLV_RECALL_PRECISION_REPORT_2026-03-17] Add a visible retrieval quality report: precision, contamination, usefulness, and current weak spots.
- [ ] [DLV_GOAL_HYGIENE_FINAL_2026-03-17] Finish removal/demotion of stale steering so active goals match current direction.

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)
- [ ] [DLV_REPO_CONSOLIDATION_EXEC_2026-03-17] Execute repo consolidation decisions around clarvis / clarvis-db / clarvis-p and remove or defer vanity fragmentation.
- [ ] [DLV_OPEN_SOURCE_SMOKE_GREEN_2026-03-17] Make open-source smoke/readiness checks green and trustworthy.
- [ ] [DLV_STRUCTURE_CLEANUP_2026-03-17] Reduce bloat, dead surfaces, and half-wired internal-only clutter from main repo.
- [ ] [DLV_MODE_SYSTEM_WIRING_2026-03-17] Ensure GE / Architecture / Passive modes are not just present but actually govern runtime behavior reliably.

### Milestone D — Public Surface (by 2026-03-29)
- [ ] [DLV_WEBSITE_V0_BUILD_2026-03-17] Build website/landing page v0 on raw IP: who Clarvis is, current work, roadmap, repos, mode, benchmarks.
- [ ] [DLV_PUBLIC_FEED_SAFE_2026-03-17] Create/sanitize the public-safe feed for website status data.
- [ ] [DLV_REPO_PRESENTATION_2026-03-17] Make repo/docs/readme presentation coherent and externally understandable.

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [DLV_FINAL_BENCH_PASS_2026-03-17] Run final benchmark/readiness pass: CLR, retrieval quality, smoke checks, orchestration sanity, website health.
- [ ] [DLV_PRESENTABILITY_REVIEW_2026-03-17] Final review against user ask: presentable, open-sourceable, usable, structured, beautiful enough, real quality.
- [ ] [DLV_LAUNCH_PACKET_2026-03-17] Prepare concise launch packet: what Clarvis is, repo map, website, usage, current capabilities, known limitations.

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

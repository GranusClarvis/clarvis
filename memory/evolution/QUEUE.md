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

- [ ] [RESEARCH_DISCOVERY 2026-03-15] Research: Context Engineering Survey — Systematic Context Optimization (arXiv:2507.13334, Li et al. 2025). Comprehensive 1400-paper survey formalizing context engineering as a discipline: retrieval, processing, management as unified pipeline. Covers context assembly patterns, prompt construction taxonomy, dynamic context budgeting. Directly targets Context Relevance (0.387→0.75) — provides the missing theoretical framework for WHY our CR keeps dropping despite good retrieval. Extract: assembly-order effects, context budget allocation strategies, noise-vs-signal tradeoffs in multi-source context. Source: arxiv.org/abs/2507.13334
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
- [ ] [CR_NOISE_PRUNE 2026-03-15] Context Relevance: aggressively prune noise sections from briefs. 14-day data shows 9 sections below 0.15 mean relevance (meta_gradient=0.056, brain_goals=0.089, failure_avoidance=0.092, metrics=0.100, synaptic=0.112, world_model=0.122, gwt_broadcast=0.128, introspection=0.129, working_memory=0.147). Current DyCP thresholds are too permissive — raise `DYCP_HISTORICAL_FLOOR` from 0.13 to 0.16, `DYCP_ZERO_OVERLAP_CEILING` from 0.16 to 0.20, and add these 9 sections to a default-suppress list in `assembly.py` unless they have high task-containment (>0.10). This alone should lift CR from 0.387 to ~0.55+ by eliminating 40-60% of noise sections. **Targets Context Relevance (0.387→0.75).** P1.
- [ ] [CR_SECTION_QUALITY 2026-03-15] Context Relevance: improve quality of top-3 sections (decision_context=0.284, related_tasks=0.316, episodes=0.273). These are the highest-value sections but still low. For `decision_context`: include the actual task description and success criteria more prominently. For `related_tasks`: filter to only tasks with >0.5 semantic similarity to current task (currently includes distant matches). For `episodes`: rank by recency AND task similarity, not just recency. Implement in `clarvis/context/assembly.py`. **Targets Context Relevance.** P1.
- [ ] [CRON_SCHEDULE_AUDIT 2026-03-15] Non-code: audit crontab for schedule conflicts and resource contention. The 12x/day autonomous runs (1,6,7,9,11,12,15,17,19,20,22,23h) overlap with research (10,16h), evolution (13h), and implementation sprint (14h) — all share the same global lock. Measure actual lock contention (grep for "lock held" in `/tmp/clarvis_*.lock` logs), identify slots where autonomous runs are consistently blocked, and consolidate or redistribute. Update CLAUDE.md cron table if schedule changes. **Non-Python task.** P1.
- [ ] [CONTAINMENT_TO_WEIGHTED_RELEVANCE 2026-03-15] Context Relevance: replace binary containment threshold with weighted section scoring in `context_relevance.py`. Currently a section is either "referenced" (containment >= 0.15) or not — this loses signal. Replace with: `weighted_relevance = sum(containment_i * importance_i) / sum(importance_i)` where importance is empirical mean relevance from history. Sections like `decision_context` (0.284) and `episodes` (0.273) should count more than `metrics` (0.100). This gives a more accurate CR signal and better feedback for DyCP tuning. **Targets Context Relevance measurement accuracy.** P2.


## P1 — This Week


## P2 — When Idle

## P0 — Do Next Heartbeat (2026-03-14)


## P0 — Stabilization / Improvement Window (next several days)


## P0 — Brain v2 / Clarvis Quality Window


## P1 — Agent Benchmarking

### Research Additions

- [ ] [RESEARCH_REPO_OPENVIKING] Deep review https://github.com/volcengine/OpenViking — open-source context database for AI agents. Study the core concept, repo architecture, file-system-paradigm context model, database/storage design, hierarchical context delivery, self-evolving patterns, and how memory/resources/skills are unified. Extract: concrete ideas Clarvis can adopt for brain structure, context delivery, benchmarking, and long-term agent architecture; identify overlap/conflict with ClarvisDB and whether to borrow, adapt, or discard specific patterns.

### CLR Benchmark — Clarvis Agent Score

Create a comprehensive agent benchmark called "CLR" (Clarvis Rating) that measures:
- **Memory quality**: recall accuracy, retrieval latency, context relevance
- **Brain integration**: graph edges, cross-collection links, importance decay
- **Task success**: code generation, execution, reasoning chain depth
- **Prompt quality**: context assembly score, brief coherence
- **Self-improvement**: evolution loop effectiveness, meta-learning gains
- **Autonomy**: success rate without human intervention, cost efficiency

Each dimension 0-1, weighted composite score. Compare baseline (no brain) vs Clarvis (full) to measure value add.

Implementation: `scripts/clr_benchmark.py` that runs tiered tests and outputs JSON.

### A/B Comparison Benchmark (Fixed)

Fix ab_comparison_benchmark.py:
- Write prompts to temp file, read via stdin or file flag
- Or use direct API calls instead of spawn_claude.sh
- Run 10+ comparison pairs with hard tasks (not trivial "count files")
- Measure: success rate, quality score, duration, context usage

Wiring: Results should feed into evolution queue as metrics.

# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

### Open-Source Release Blockers (2026-04-03 audit, populated 2026-04-03)

---

## P1 — This Week

### Execution Reliability (2026-04-03 audit)
_(Cron lock system, auto-recovery, and monitoring all confirmed healthy. No open items.)_

### SWO / Clarvis Brand Integration (2026-04-03)

### Queue Architecture v2 (2026-04-03 design + pressure test)
- [x] [QUEUE_ENGINE_V2] _(Done 2026-04-04)_ Queue Engine V2 implemented at `clarvis/orch/queue_engine.py`: sidecar state model (`data/queue_state.json`), 5-state machine (pending/running/succeeded/failed/deferred), simplified 3-factor scorer, `stats()` observability, atomic writes, run records. Wired into heartbeat preflight (`start_run`) and postflight (`end_run` + `mark_succeeded`/`mark_failed`). 30 tests pass. CLI: `clarvis queue engine-stats`, `clarvis queue runs`, `clarvis queue run-stats`.
- [x] [QUEUE_RUN_RECORDS] _(Done 2026-04-04)_ First-class run records added to Queue Engine V2: `start_run(tag)` → run_id, `end_run(run_id, outcome, ...)`, `get_runs(tag)`, `recent_runs()`, `run_stats()`. Stored in `data/queue_runs.jsonl` (append-only JSONL). Wired into heartbeat pipeline — preflight starts run, postflight ends it with outcome/duration/error. CLI: `clarvis queue runs [TAG]`, `clarvis queue run-stats`.
- [x] [QUEUE_V2_SOAK] _(Done 2026-04-04)_ Soak readiness check added: `clarvis queue soak` / `queue_engine.py soak`. Validates 5 dimensions: sidecar integrity, QUEUE.md↔sidecar sync, state machine validity, run record integrity, stats sanity. Fixed sidecar consistency (completed items were still marked pending). 3 soak tests added (33 total pass). Current verdict: PASS.

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Phase 3: queue_writer.py migrated 2026-04-04 (19+ importers, highest-value). Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L). All actively called from cron — large, not trivially wrappable. Parking — each is a multi-hour refactor with risk.)_
- [~] [SPINE_REMAINING_LIBRARY_MODULES] ~18 scripts with reusable library logic still in scripts/. _(2026-04-04: queue_writer migrated to `clarvis/orch/queue_writer`; reasoning_chains migrated to `clarvis/cognition/reasoning_chains`. 2 spine→scripts dependency violations annotated: world_models (task_selector.py) and causal_model (reasoning.py) — both wrapped in try/except, safe but should migrate eventually. Remaining LIBRARY-grade (2+ importers): cognitive_load, brain_bridge, workspace_broadcast, world_models, causal_model, project_agent. LIGHT_LIBRARY (1 importer): theory_of_mind, parameter_evolution, tool_maker, pr_factory. LEAF (0 importers, cron-only): temporal_self, failure_amplifier, agent_orchestrator. Low priority — spine is functional.)_

### Package Consolidation — COMPLETED (2026-04-03)
- [x] [PKG_COST_OPTIMIZER_MIGRATE] _(Done 2026-04-03)_ Migrated optimizer.py → `clarvis/orch/cost_optimizer.py`. Imports updated from `clarvis_cost.core` → `clarvis.orch.cost_tracker`.
- [x] [PKG_COST_TESTS_MIGRATE] _(Done 2026-04-03)_ 90 tests migrated to spine: `tests/test_cost_tracker.py` (38), `tests/test_cost_optimizer.py` (12), `tests/test_metacognition.py` (40). All pass.
- [x] [PKG_CLARVIS_DB_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-db/`. Zero runtime imports confirmed.
- [x] [PKG_CLARVIS_REASONING_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-reasoning/`. Metacognition functions migrated to `clarvis/cognition/metacognition.py`.
- [x] [PKG_COST_PACKAGE_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-cost/`. All migrated to spine.
- [x] [PKG_DOCS_BULK_UPDATE] _(Done 2026-04-04)_ README, CONTRIBUTING, CLAUDE.md, verify_install.sh updated. Deprecation notices added to 11 key architecture/planning docs (ARCHITECTURE.md, CONSOLIDATION_PLAN.md, INSTALL.md, etc.). Remaining historical references are informational only.

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for delivery._

### Roadmap Gaps (2026-04-03 audit — items from ROADMAP.md with no queue entry)

---

## Partial Items (tracked, not actively worked)
- [x] [WORKTREE_AUTO_ENABLE] _(Done 2026-04-04)_ In `cron_autonomous.sh`, auto-detect code-modifying tasks and pass `--worktree` to Claude Code CLI for git worktree isolation. Detection regex expanded (consolidat, PKG_). `run_claude_code()` now conditionally passes `--worktree` flag. bash -n validated.

---

## NEW ITEMS

### Research Sessions

### External Challenges


### Bloat Reduction (2026-04-03 evolution analysis)
- [x] [BLOAT_AGGRESSIVE_DEDUP_PRUNE] _(Done 2026-04-04)_ Ran `optimize-full`: decayed 2306, pruned 53 low-importance, removed 539 duplicates, cleaned 73 noise, archived 2. Total 3605→2938 (below 3000 target). 5-query retrieval validation: top-3 distances identical, no regression.

### Cron Hardening (2026-04-03 evolution analysis)

### Self-Awareness (2026-04-03 evolution analysis)

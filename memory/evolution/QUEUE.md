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
- [ ] [QUEUE_ENGINE_V2] Implement Queue Engine V2 as a **spine subsystem** (preferred location: `clarvis/queue/`, not `clarvis/orch/`). Follow the sidecar model from `docs/QUEUE_V2_PRESSURE_TEST_2026-04-03.md`: keep `QUEUE.md` human-editable, add runtime sidecar state for attempts/failures/timestamps/state, simplify scoring first, then add explicit state transitions, `stats()` observability, and phased pipeline integration. See also `docs/QUEUE_ARCHITECTURE_REVIEW_2026-04-03.md`.
- [ ] [QUEUE_RUN_RECORDS] Add first-class task run records linked by task id / run id so queue items map cleanly to executions, outputs, durations, tests, and artifacts. This is the missing execution-history layer needed to avoid reconstructing outcomes from logs/digests/text similarity. Build this as part of Queue Engine V2, but keep it separately visible because it is the key observability layer.

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~20 scripts with reusable library logic still in scripts/: cognitive_load, brain_bridge, workspace_broadcast, theory_of_mind, temporal_self, world_models, causal_model, reasoning_chains, failure_amplifier, parameter_evolution, tool_maker, etc. Each is a separate migration task. Low priority — spine is functional without these.

### Package Consolidation — COMPLETED (2026-04-03)
- [x] [PKG_COST_OPTIMIZER_MIGRATE] _(Done 2026-04-03)_ Migrated optimizer.py → `clarvis/orch/cost_optimizer.py`. Imports updated from `clarvis_cost.core` → `clarvis.orch.cost_tracker`.
- [x] [PKG_COST_TESTS_MIGRATE] _(Done 2026-04-03)_ 90 tests migrated to spine: `tests/test_cost_tracker.py` (38), `tests/test_cost_optimizer.py` (12), `tests/test_metacognition.py` (40). All pass.
- [x] [PKG_CLARVIS_DB_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-db/`. Zero runtime imports confirmed.
- [x] [PKG_CLARVIS_REASONING_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-reasoning/`. Metacognition functions migrated to `clarvis/cognition/metacognition.py`.
- [x] [PKG_COST_PACKAGE_DELETE] _(Done 2026-04-03)_ Deleted `packages/clarvis-cost/`. All migrated to spine.
- [~] [PKG_DOCS_BULK_UPDATE] _(Partially done 2026-04-03)_ README, CONTRIBUTING, CLAUDE.md, verify_install.sh updated. ~20 architecture/planning docs still reference packages historically — low priority, informational only.

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
- [~] [WORKTREE_AUTO_ENABLE] In `cron_autonomous.sh`, auto-detect code-modifying tasks and enable `--isolated` worktree mode. _(Partial 2026-04-03: detection logic added. Full worktree isolation requires restructuring — follow-up needed.)_

---

## NEW ITEMS

### Research Sessions

### External Challenges


### Bloat Reduction (2026-04-03 evolution analysis)
- [ ] [BLOAT_AGGRESSIVE_DEDUP_PRUNE] Run targeted dedup+prune on `clarvis-learnings` (1459 items, 41% of brain) and `clarvis-memories` (612 items). Goal: reduce total_memories below 3000. Use `brain_hygiene.py run` + similarity scan on the two largest collections. Validate retrieval quality doesn't regress via `performance_benchmark.py`.

### Cron Hardening (2026-04-03 evolution analysis)

### Self-Awareness (2026-04-03 evolution analysis)

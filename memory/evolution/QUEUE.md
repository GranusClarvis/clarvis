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

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Phase 3: queue_writer.py migrated 2026-04-04 (19+ importers, highest-value). Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L). All actively called from cron — large, not trivially wrappable. Parking — each is a multi-hour refactor with risk.)_
- [~] [SPINE_REMAINING_LIBRARY_MODULES] ~18 scripts with reusable library logic still in scripts/. _(2026-04-04: queue_writer migrated to `clarvis/orch/queue_writer`; reasoning_chains migrated to `clarvis/cognition/reasoning_chains`. 2 spine→scripts dependency violations annotated: world_models (task_selector.py) and causal_model (reasoning.py) — both wrapped in try/except, safe but should migrate eventually. Remaining LIBRARY-grade (2+ importers): cognitive_load, brain_bridge, workspace_broadcast, world_models, causal_model, project_agent. LIGHT_LIBRARY (1 importer): theory_of_mind, parameter_evolution, tool_maker, pr_factory. LEAF (0 importers, cron-only): temporal_self, failure_amplifier, agent_orchestrator. Low priority — spine is functional.)_

### Package Consolidation — COMPLETED (2026-04-03)

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

---

## NEW ITEMS

### Research Sessions

### External Challenges



### Bloat Reduction (2026-04-03 evolution analysis)

### Cron Hardening (2026-04-03 evolution analysis)

### Self-Awareness (2026-04-03 evolution analysis)

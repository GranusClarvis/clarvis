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
- [ ] [QUEUE_RUN_RECORDS] Add first-class task run records linked by task id / run id so queue items map cleanly to executions, outputs, durations, tests, and artifacts. This is the missing execution-history layer needed to avoid reconstructing outcomes from logs/digests/text similarity.

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~20 scripts with reusable library logic still in scripts/: cognitive_load, brain_bridge, workspace_broadcast, theory_of_mind, temporal_self, world_models, causal_model, reasoning_chains, failure_amplifier, parameter_evolution, tool_maker, etc. Each is a separate migration task. Low priority — spine is functional without these.

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

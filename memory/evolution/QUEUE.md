# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

- [x] [QUEUE_V2_SELECTOR_CUTOVER] Wire `queue_engine.select_next()` into heartbeat preflight `_gather_candidates` as primary selection path (V2 scoring, backoff, retry limits). Legacy `task_selector` becomes fallback. _(Blocked: this task — being done now.)_ (2026-04-04 wired into preflight)
- [x] [QUEUE_V2_SOAK_WITH_TASKS] Run soak check with real tasks in queue to validate reconciliation, scoring, and state transitions end-to-end. Must show md_tasks>0, no orphans, no stuck runs. (2026-04-04 PASS md_tasks=22 no_orphans)

## P1 — This Week

### Queue Architecture v2 (2026-04-04 audit)
- [ ] [MANUAL 2026-04-04] [MANUAL 2026-03-15] User task: update architecture notes
- [x] [QUEUE_V2_STUCK_RUN_RECOVERY] Add auto-recovery for stuck "running" entries in sidecar (>4h with no end_run). Heartbeat or watchdog should reset to failed. (2026-04-04 implemented: reconcile auto-recovers >3h stuck, recover_stuck() + dangling run closure)
- [x] [QUEUE_V2_SPINE_MOVE] Move queue_engine.py + queue_writer.py from clarvis/orch/ to clarvis/queue/ as canonical spine package. Backward-compat shims in clarvis/orch/. (2026-04-04 done: 37 tests pass, soak PASS)
- [x] [QUEUE_V2_DAILY_CAP_WIRE] Wire queue_writer daily cap + dedup into heartbeat autonomous loop so self-generated tasks respect limits. (2026-04-04 verified: all 15+ injection callers route through writer.add_task() which enforces cap=5/day + word-overlap dedup)
- [x] [QUEUE_V2_PRIMARY_SELECTOR_CUTOVER] Final cutover: remove legacy task_selector fallback from heartbeat_preflight, make queue_engine.select_next() the sole selection path. (2026-04-04 done: ranked_eligible() is sole primary path, legacy demoted to import-fail-only fallback, 44 tests pass, soak PASS)
- [x] [QUEUE_V2_MANUAL_SPAWN_VISIBILITY] Wire spawn_claude.sh to register V2 run records via engine.start_external_run() / end_run(), so operator-spawned tasks create run records + sidecar state transitions. (2026-04-04 done: spawn_claude.sh wired, CLI start-external/end-external commands added, 48 tests pass, soak PASS)
- [ ] [QUEUE_V2_CRON_ORCHESTRATOR_RUNS] Wire cron_research.sh and cron_strategic_audit.sh to create V2 run records around their Claude Code spawns (currently they mark_task_complete but don't log run duration/outcome in queue_runs.jsonl). Low priority — heartbeat pipeline covers 90%+ of runs.

### Context/Prompt Pipeline
- [ ] [CONTEXT_TIERED_BRIEF_COVERAGE] Validate tiered brief covers all 10 task types in taskset.json with no missing critical sections. Fix gaps found by prompt_quality_eval.py.

### SWO / Clarvis Brand Integration
- [ ] [SWO_AGENT_WORKSPACE_SETUP] Ensure star-world-order agent workspace is functional: clone, brain seed, golden QA passing.
- [ ] [SWO_NEXT_PR] Pick next SWO issue from upstream, spawn agent, deliver PR via fork workflow.

### Spine Migration (continued)
- [ ] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1-3 done. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L). Large, not trivially wrappable. Each is a multi-hour refactor.)_

### Execution Reliability
- [ ] [CRON_STUCK_LOCK_RECOVERY] Add stale-lock auto-recovery to cron_watchdog.sh — detect locks held >2h with dead PID, clean up.

### Open-Source Release
- [ ] [OSS_HARDCODED_PATHS] Audit and parameterize remaining hardcoded `/home/agent/.openclaw/` paths in Python and shell scripts. _(146+ Python files, 7 shell files identified.)_
- [ ] [OSS_README_PUBLIC] Write public-facing README.md for the clarvis repo — architecture overview, quickstart, API examples.

---

## P2 — When Idle

### Spine Migration (low priority)
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~18 scripts with reusable library logic still in scripts/. _(queue_writer + reasoning_chains migrated. Remaining LIBRARY-grade: cognitive_load, brain_bridge, workspace_broadcast, world_models, causal_model, project_agent. Low priority — spine is functional.)_

### Benchmarking
- [ ] [BENCH_CLR_AB_COMPARISON] Fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.
- [ ] [BENCH_MONTHLY_REFLECTION_AUDIT] Validate monthly structural reflection output quality — check last 3 months for actionable insights vs noise.

### Agent Orchestrator
- [ ] [AGENT_MULTI_PARALLEL] Implement multi-agent parallel execution — spawn 2+ project agents concurrently with isolated workspaces.
- [ ] [AGENT_VISUAL_OPS_DASHBOARD] Pillar 2 Phase 5 — PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.

### Deep Cognition (Phase 4-5 gaps)
- [ ] [COGNITION_TIERED_CONFIDENCE] Implement tiered action levels (HIGH/MEDIUM/LOW/UNKNOWN) for confidence-gated execution.
- [ ] [COGNITION_GATE_PROMOTION] Gate promotion of self-improvements — require benchmark delta before accepting code changes.
- [ ] [COGNITION_CONCEPTUAL_FRAMEWORK] Knowledge synthesis beyond keyword matching — conceptual framework building.

### Adaptive RAG Pipeline
- [ ] [RAG_PHASE1_GATE] Implement GATE phase of adaptive RAG — query classification before retrieval. Design: `docs/ADAPTIVE_RAG_PLAN.md`.

---

## Partial Items (tracked, not actively worked)

### Research Sessions
- [ ] [RESEARCH_PROACTIVE_TOOLS] Proactive research on emerging agent tools and frameworks (Phase 3.3 gap).

### External Challenges
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

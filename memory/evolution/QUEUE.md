# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)


### Delivery Goal
Presentable Clarvis by 2026-03-31:
- open-source-ready main repo
- working/public-ready website v0
- clean repo boundaries and consolidation plan
- stronger Clarvis brain / recall / context quality
- reliable orchestration and benchmarks
- clearly wired, tested, maintainable structure

### March 24 audit note
_Queue audited on 2026-03-24 evening. Removed 3 completed items (A5_A7, TEMPORAL_RETRIEVAL_FIX, BACKFILL_SENTINEL_FIX). Demoted 2 items (postflight import cleanup, semantic bridges) to P1 — functional via bridges, not release-blocking. 7 items remain on the critical path._

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26) ✅ COMPLETE

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)


---

## P1 — This Week




### Demoted from P0 (2026-03-24 audit)

### Episode Success Rate Hardening

### Code Quality

### Phi / Benchmarking

---

## P2 — When Idle (Demoted 2026-03-17)

### Spine Migration
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Remaining: `pr_factory.py`, `project_agent.py`, `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-03-10: 3 scripts wrapped. Remaining: context_compressor, heartbeat_{pre,post}flight.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(3 done. Next: context_compressor gc.)_

### Code Quality

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

---

## NEW ITEMS

- [ ] [ORCH_BENCHMARK_SCRIPTS] Create `scripts/orchestration_benchmark.py` and `scripts/orchestration_scoreboard.py` — both are referenced by `cron_orchestrator.sh` (lines 60, 72) but missing, causing 5 daily benchmark failures since 2026-03-17. Implement per-agent composite scoring (isolation, latency, PR success, retrieval, cost) and JSONL scoreboard writer.
- [ ] [EPISODE_ACTION_SUBCLASS] Decompose the catch-all "action" failure category in `heartbeat_postflight.py` error classifier (~line 241) into sub-types (param_missing, api_error, race_condition, validation_fail). 45 of 68 failures are bucketed as generic "action" — finer classification will surface root causes and directly improve Episode Success Rate (current 0.922).
- [ ] [EPISODE_CAUSAL_DENSITY] Add automatic causal-link inference in `heartbeat_postflight.py` episode encoding: when a new episode's task overlaps a recent episode by topic/collection, auto-create a causal edge. Current ratio is 64 links / 341 episodes (0.19) — target 0.5+. This strengthens episodic retrieval and indirectly improves episode success rate.
- [x] [CRON_ORCHESTRATOR_LOCKFILE_DOCS] Added header docs (pipeline, lock behavior, benchmark fallback, error interpretation, troubleshooting FAQ) and inline stage comments. (2026-03-26)
- [x] [EPISODE_STATUS_FIELD_FIX] Fixed: `failure_type` now always defaults to `"action"` for non-success episodes in `encode()`. Backfilled 45 historical episodes. 249 tests pass. (2026-03-26)

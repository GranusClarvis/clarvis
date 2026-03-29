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


- [~] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/autonomy] Add external challenge source to evolution loop — e.g., user-submitted tasks, research paper implementations, or benchmark suites that test novel problem-solving.
  - [ ] [AUTO_SPLIT 2026-03-29] [STRATEGIC_AUDIT 2026-03-28_1] Analyze: read relevant source files, identify change boundary
  - [ ] [AUTO_SPLIT 2026-03-29] [STRATEGIC_AUDIT 2026-03-28_2] Implement: core logic change in one focused increment
  - [ ] [AUTO_SPLIT 2026-03-29] [STRATEGIC_AUDIT 2026-03-28_3] Test: add/update test(s) covering the new behavior
  - [ ] [AUTO_SPLIT 2026-03-29] [STRATEGIC_AUDIT 2026-03-28_4] Verify: run existing tests, confirm no regressions












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

### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

- [ ] [BRIEF_COMPRESSION_BOOST] Raise brief compression ratio from 0.503→0.55+ by (a) lowering DyCP `DYCP_MIN_CONTAINMENT` from 0.08→0.10, (b) adding redundant-sentence dedup across retained sections in `generate_tiered_brief`, and (c) tightening `compress_text` extractive ratio from 0.3→0.25 for low-relevance sections. Measure before/after with `performance_benchmark.py record`.



- [ ] [SEMANTIC_CROSS_COLLECTION_BRIDGE] Cross-collection connectivity score is 0.66 (second-weakest). Run `brain.py bulk_cross_link` with lowered similarity threshold (0.55→0.50) on the 3 least-connected collections, then verify connectivity improvement via `performance_benchmark.py record`.
- [ ] [GOAL_SET_COMPACTION] Curate active goals so `brain.get_goals()` returns a concise operator view instead of bridge/generated clutter. Archive or demote stale bridge goals, keep 5-8 canonical active goals, and document the policy.
- [ ] [INFRA_RETRIEVAL_HARDENING] Fix the remaining infrastructure/procedural retrieval blind spots called out in recent LLM brain reviews. Target graph backend/configuration factual recall and verify with 5-10 focused QA prompts.
- [ ] [EXTERNAL_CHALLENGE_FEED] Add one external challenge source to the evolution loop (benchmark set, public issue feed, or research implementation tasks) so autonomous work is tested on novel problems, not only self-generated ones.









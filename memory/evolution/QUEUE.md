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
- [x] [RESEARCH_PHI_COMPUTATION] (2026-03-30) Reviewed IIT 4.0, approximation literature, and core critiques; summary in `memory/research/phi-computation.md`.

---

## NEW ITEMS

### External Challenges



### P0 — Found in 2026-03-27 evening scan

- [ ] [CONTEXT_CACHE_SUPPRESSION_TEST_FIX] Fix and validate the pre-existing failing test `test_hard_suppress_ignores_content_cache` after today's `context_compressor.py` pruning/compression changes. Ensure static suppression and dynamic suppression expectations are aligned so benchmark-driven refactors do not ship with a red test suite.

### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

- [x] [BRIEF_COMPRESSION_STABILITY] (2026-03-30) Fixed: brain-size-adaptive pruning in `_prune_knowledge_hints` (tighter max_hints + char budget for larger brains), tighter distance cutoff in brain_bridge (0.20 margin, 1.10 cap), stabilized denominator floor in `_measure_compression_live`. Result: 0.807 (target ≥0.58).
- [ ] [ACTION_FAILURE_TRIAGE] 45 action-type episode failures dominate the failure distribution (vs 14 timeout, 7 system). Sample 10 recent action failures from episodes, classify root causes (bad tool call, wrong model, missing context, etc.), and file a short report in `memory/research/action-failure-triage.md` with top-3 actionable fixes.













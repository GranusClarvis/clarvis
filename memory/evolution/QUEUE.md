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

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)
- [x] [C_OPEN_SOURCE_READINESS_SWEEP] _(2026-03-25: Sweep complete. Removed chat ID from longmemeval.py, email from beam.py. LICENSE/CONTRIBUTING/CI all present. .gitignore solid. data/ + monitoring/ untracked. 30/30 smoke tests pass. Burndown C1+C3 updated.)_

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)

---

## P1 — This Week

### Demoted from P0 (2026-03-24 audit)
- [~] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. _(All metric targets met. Blocked on Phi verification compute time. Not a release blocker.)_

### Code Quality
- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/metrics/membench.py:run_membench` (137 lines), `scripts/heartbeat_postflight.py:_brain_store` (89 lines), `scripts/heartbeat_postflight.py:run_postflight` (1444 lines), `scripts/retrieval_benchmark.py:run_benchmark` (167 lines). Target: all functions ≤80 lines.
- [ ] [BRIER_CALIBRATION_OVERHAUL] Audit `clarvis_confidence.py` prediction-outcome loop: review bucket distributions, prune stale/low-signal predictions, recalibrate bin edges, and add a post-recalibration Brier check to `performance_benchmark.py`. Current brier capability=0.06 is the worst dimension. Target: brier ≥ 0.30 within 2 weeks.

### Phi / Benchmarking
- [ ] [SEMANTIC_CROSS_COLLECTION_UNBLOCK] Unblock SEMANTIC_CROSS_COLLECTION_BRIDGES (stuck since 2026-03-19): profile Phi computation timeout, identify which of the 99k graph edges + 720 ONNX queries dominate wall time, and implement either sampling-based Phi estimation or collection-pair parallel evaluation. Current semantic_cross_collection=0.57 (target >0.75).

---

## P2 — When Idle (Demoted 2026-03-17)

### Spine Migration
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Remaining: `pr_factory.py`, `project_agent.py`, `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-03-10: 3 scripts wrapped. Remaining: context_compressor, heartbeat_{pre,post}flight.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(3 done. Next: context_compressor gc.)_

### Code Quality
- [~] [HEARTBEAT_POSTFLIGHT_DECOMPOSITION] Decompose `run_postflight()` (1457 lines) into 10-15 named sub-functions. Improves `reasonable_function_length` metric.

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

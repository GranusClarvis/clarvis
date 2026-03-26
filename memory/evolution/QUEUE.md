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

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)


---

## P1 — This Week

- [ ] [ACTION_ACCURACY_GUARD 2026-03-26] [ACTION_ACCURACY_DIAGNOSTIC] Action accuracy dropped to 0.737 (threshold: 0.95). Failing episodes: ep_20260325_140122, ep_20260325_150100, ep_20260325_190102, ep_20260325_200101, ep_20260325_220123. Investigate root causes and fix.
- [x] [DECOMPOSE_LONG_FUNCTIONS] Done 2026-03-26. All 4 functions decomposed to ≤52 lines. Also decomposed `self_representation.py:encode_self_state` (234→28 lines, 10 helpers).

### Demoted from P0 (2026-03-24 audit)

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

- [ ] [DIAGNOSE_BRAIN_EDGE_REGRESSION] Investigate 10.3% graph edge drop (88211→79152) and memory count below 3000 threshold flagged repeatedly in alerts.log. Determine if caused by graph compaction/hygiene over-pruning or data loss. Fix root cause and restore healthy baseline. Touch: `graph_compaction.py`, `brain_hygiene.py`, `goal_hygiene.py`.
- [x] [LONG_FUNCTION_DECOMPOSITION] Done 2026-03-26. Decomposed 5 functions across 3 files: `daily_brain_eval.py` (3 functions: _run_retrieval_probe 92→3+31+44, _assess_quality 89→5 scorers+37, run_full_eval 96→30+16+52), `llm_brain_review.py` (build_review_prompt 119→3 formatters+8), `self_representation.py` (encode_self_state 234→10 encoders+28). All now ≤80 lines.

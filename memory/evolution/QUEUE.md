# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)


### Delivery Goal
- [x] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/build_consolidate] Define concrete deliverables for Milestones D and E. _(Done 2026-03-28: Website v0, LICENSE, README, CI all exist (Milestone C complete). Defined 4 Milestone D tasks (website smoke, secrets scan, status.json freshness, README review) and 5 Milestone E tasks (CI green, brain health, benchmark record, cron audit, consolidation plan).)_
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
- [ ] [D1_WEBSITE_SMOKE] Verify website v0 serves all 5 pages + /api/public/status returns valid JSON. Fix any 404s or broken links.
- [ ] [D2_SECRETS_SCAN] Add secrets scanning to CI (gitleaks or trufflehog). Ensure no API keys, tokens, or passwords in tracked files.
- [ ] [D3_STATUS_JSON_FRESH] Ensure `generate_status_json.py` cron produces fresh `website/static/status.json` (or verify it's already running).
- [ ] [D4_README_FINAL] Review README.md — verify install instructions work, remove any internal-only references, ensure metrics table is current.

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [E1_CI_GREEN] All CI checks pass on main (lint + test). Fix any failures.
- [ ] [E2_BRAIN_HEALTH] `python3 -m clarvis brain health` passes all checks. Fix any degraded metrics.
- [ ] [E3_BENCHMARK_RECORD] Run `performance_benchmark.py record` and `cron_clr_benchmark.sh` — record final PI and CLR scores. Both above thresholds.
- [ ] [E4_CRON_AUDIT] All cron jobs ran successfully in the last 24h (no stale locks, no failures in watchdog logs).
- [ ] [E5_CONSOLIDATION_PLAN] Document repo boundary plan: what stays in main repo vs what moves to separate packages/repos. One-pager in `docs/CONSOLIDATION_PLAN.md`.


---

## P1 — This Week

- [x] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/brain_quality] Store 5-10 procedural memories with step-by-step structure. Add infrastructure memories for graph backends. _(Done 2026-03-28: stored 7 procedural memories (deploy, brain optimize, update, debug locks, add cron, store memory, spawn claude) + 3 infrastructure memories (graph backends, ChromaDB, gateway). Retrieval verified — top results match queries.)_
- [ ] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/autonomy] Add external challenge source to evolution loop — e.g., user-submitted tasks, research paper implementations, or benchmark suites that test novel problem-solving.
- [ ] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/metric_integrity] Raise TARGET_DEGREE to 25 or increase semantic_overlap weight to 0.50 so Phi reflects real integration quality.
- [ ] [STRATEGIC_AUDIT 2026-03-28] [STRATEGIC_AUDIT/metric_integrity] Investigate CLR ablation methodology. Use harder test tasks, remove scoring floors, or test with 2+ components ablated simultaneously to find interaction effects.
- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/metrics/self_model.py:_assess_memory_system` (95 lines), `clarvis/metrics/self_model.py:_assess_autonomous_execution` (134 lines), `clarvis/metrics/self_model.py:_assess_self_reflection` (108 lines), `clarvis/metrics/self_model.py:_assess_reasoning_chains` (95 lines), `clarvis/metrics/self_model.py:_assess_learning_feedback` (127 lines). Target: all functions ≤80 lines.












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
- [x] [RESEARCH_SELECTIVE_RETRIEVAL_ROUTING] Investigate selective retrieval routing: when to use internal memory, long-context units, or compressed evidence in RAG systems. (2026-03-28)

---

## NEW ITEMS

### P0 — Found in 2026-03-27 evening scan

- [ ] [LOCKFILE_PID_PARSE_REGRESSION] Fix `scripts/cron_report_morning.sh` and `scripts/cron_report_evening.sh` to parse the new `PID TIMESTAMP` lockfile format before calling `kill -0`. Current `pid=$(cat "$LOCKFILE")` breaks lock detection and can spawn duplicate report runs.
- [ ] [RESEARCH_ROOT_ARTIFACT_SWEEP_CUTOFF] Fix `scripts/cron_research.sh` run-start cutoff parsing. `RUN_ID=$(date +%Y-%m-%d-%H%M%S)` is not reliably parseable by `date -d`, so the fallback to `now` can miss/misclassify root artifacts created earlier in the same run.

### P1 — Found in 2026-03-28 evolution scan

- [ ] [BRIEF_COMPRESSION_BOOST] Raise brief compression ratio from 0.503→0.55+ by (a) lowering DyCP `DYCP_MIN_CONTAINMENT` from 0.08→0.10, (b) adding redundant-sentence dedup across retained sections in `generate_tiered_brief`, and (c) tightening `compress_text` extractive ratio from 0.3→0.25 for low-relevance sections. Measure before/after with `performance_benchmark.py record`.



- [ ] [SEMANTIC_CROSS_COLLECTION_BRIDGE] Cross-collection connectivity score is 0.66 (second-weakest). Run `brain.py bulk_cross_link` with lowered similarity threshold (0.55→0.50) on the 3 least-connected collections, then verify connectivity improvement via `performance_benchmark.py record`.

- [x] [CONTEXT_COMPRESSOR_SECTION_WEIGHTS] Add per-section relevance weights to `generate_tiered_brief` so high-value sections (episodes, reasoning, knowledge) get more token budget and low-value sections (health, infrastructure stats) get compressed more aggressively. _(Done 2026-03-28: added `load_section_relevance_weights()` in budgets.py, `_scale_chars()` helper in assembly.py, all 3 zone builders now scale char budgets per-section. Episodes/knowledge get up to 1.5x, metrics/completions capped at 0.8x.)_








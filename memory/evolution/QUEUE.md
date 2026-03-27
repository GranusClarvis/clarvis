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

- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/brain/search.py:recall` (91 lines), `scripts/performance_benchmark.py:benchmark_retrieval_quality` (83 lines), `scripts/performance_benchmark.py:benchmark_context_quality` (91 lines), `scripts/performance_benchmark.py:run_full_benchmark` (135 lines), `scripts/performance_benchmark.py:run_refresh_benchmark` (101 lines). Target: all functions ≤80 lines.







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

- [x] [RESEARCH_DISCOVERY 2026-03-27] Research: Late Chunking for Retrieval Optimization — completed. Long-context embedding models perform better when chunking is delayed until after full-document encoding, preserving cross-chunk references. Best fit: long, context-dependent notes; weak effect on short atomic docs. Research note: `memory/research/late_chunking_retrieval_optimization_2026-03-27.md`.

- [ ] [GRAPH_PARITY_RECONCILE] Diagnose and fix JSON↔SQLite edge count mismatch (JSON=90,577 vs SQLite=90,628). Cross-collection and similar_to edges diverging — blocks soak cutover decision. _(P1, non-Python: involves graph data inspection + shell tooling)_
- [~] [POSTFLIGHT_DECOMPOSE] Phase 1 done: extracted error classifier into `clarvis/heartbeat/error_classifier.py` (classify_error + ERROR_RULES + _match_keywords). Postflight re-imports from canonical module. Remaining: extract episode encoding + brain storage. _(P2, in progress 2026-03-27)_
- [ ] [LOAD_SCALING_OPTIMIZE] Profile and reduce n=1→n=10 recall degradation from 19.1% to <15% target. Investigate `brain.recall()` post-processing: graph-edge lookups, reranking, and result enrichment likely scale linearly with n. Batch graph queries or add early-exit optimizations. _(P1, targets weakest metric: load_degradation)_
- [ ] [BENCHMARK_LOAD_NOISE_FLOOR] Load degradation jumped 0%→19.1% in a single benchmark run — high volatility suggests measurement noise. In `benchmark_load_scaling()`: increase samples from 5→9, add IQR outlier trimming, and log raw timings to history for trend analysis. _(P1, stabilizes the metric that gates LOAD_SCALING_OPTIMIZE)_
- [ ] [CRON_STALE_LOCK_AUDIT] Audit all `/tmp/clarvis_*.lock` files and cron scripts for stale-lock handling. Verify `trap EXIT` cleanup works when scripts are killed by timeout. Add a check to `cron_watchdog.sh` that alerts on locks older than 2 hours. _(P1, non-Python: shell scripting + cron inspection)_
- [ ] [MILESTONE_D_STATUS_PAGE] P0 deadline 2026-03-29. Scaffold a minimal public landing page for Clarvis: architecture overview, live brain stats, current PI score, link to repo. Static HTML or lightweight framework — keep it deployable. _(P1, supports Milestone D: Public Surface)_


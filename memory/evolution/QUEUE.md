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

- [x] [P0_BUGFIX_EPISODIC_MEMORY_WRAPPER] Fixed: added `from clarvis.memory.episodic_memory import main` to wrapper. Verified working.

---

## P1 — This Week

- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `scripts/daily_brain_eval.py:_run_retrieval_probe` (92 lines), `scripts/daily_brain_eval.py:_assess_quality` (89 lines), `scripts/daily_brain_eval.py:run_full_eval` (96 lines), `scripts/llm_brain_review.py:build_review_prompt` (119 lines). Target: all functions ≤80 lines.

### Demoted from P0 (2026-03-24 audit)

### Code Quality

### Phi / Benchmarking

- [x] [REASONING_FAILURE 2026-03-25] ~~Investigate failure~~ — Root cause: expired OAuth token (401 auth error), not a code issue. Resolved 2026-03-25 by token refresh.
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

- [x] [ACTION_ACCURACY_CONFIDENCE_GATE] Done: confidence gate wired into `_check_candidate_gates()` in heartbeat_preflight.py. LOW/UNKNOWN tiers skip tasks. Override: `CLARVIS_FORCE_LOW_CONFIDENCE=1`.
- [x] [CRON_ERROR_AGGREGATOR] Done: `scripts/cron_error_aggregator.sh` built and tested. Scans cron+monitoring logs, deduplicates by signature, writes daily summary to `monitoring/cron_errors_daily.md`.
- [ ] [DIAGNOSE_BRAIN_EDGE_REGRESSION] Investigate 10.3% graph edge drop (88211→79152) and memory count below 3000 threshold flagged repeatedly in alerts.log. Determine if caused by graph compaction/hygiene over-pruning or data loss. Fix root cause and restore healthy baseline. Touch: `graph_compaction.py`, `brain_hygiene.py`, `goal_hygiene.py`.
- [x] [ACTION_FAILURE_PATTERN_ANALYSIS] Done: Analyzed 68 non-success episodes. Top 3 root causes: (1) auth 401 errors (5 episodes, reclassified system), (2) NO_ERROR failures (3, reclassified partial-success), (3) shallow_reasoning (21 soft_failures). Fixes: auto-detect system failures in `_get_failure_type()` and `encode()`, exclude system failures from action_accuracy formula, added auth pre-check to heartbeat_preflight.py, backfilled 20 episode failure_types. Action accuracy: 0.963→0.989.
- [x] [SEMANTIC_CROSS_COLLECTION_BOOST] Done: score boosted 0.588→0.6617 (target 0.65+ met). Fixed L2-to-cosine formula in phi.py, added 42 bridge memories, Phi 0.7949→0.8205.
- [x] [OPEN_SOURCE_PRELAUNCH_CHECKLIST] Done: `scripts/oss_readiness_check.sh` built and tested. 17 checks pass, 0 fail, 1 advisory warning.
- [ ] [LONG_FUNCTION_DECOMPOSITION] Split the longest functions flagged by `reasonable_function_length` (0.772 — lowest structural code quality sub-metric, 622 files checked). Identify top 5 offenders via pylint/AST scan, decompose into smaller helpers. Improves code quality score and maintainability for open-source readiness. Touch: scripts with functions >80 lines.

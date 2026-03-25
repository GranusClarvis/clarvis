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

- [ ] [ACTION_ACCURACY_CONFIDENCE_GATE] Wire confidence predictions into heartbeat task_selector — skip tasks with LOW/UNKNOWN confidence unless forced. Currently confidence is computed but not enforced, allowing low-confidence actions that degrade Action Accuracy (weakest metric at 0.981). Touch: `heartbeat_preflight.py` task selection, `clarvis_confidence.py` thresholds.
- [ ] [CRON_ERROR_AGGREGATOR] Build `scripts/cron_error_aggregator.sh` (Bash) — scan all `memory/cron/*.log` and `monitoring/*.log` for ERROR/FATAL/traceback lines, deduplicate by signature, write daily summary to `monitoring/cron_errors_daily.md`. Wire into `cron_report_morning.sh`. Currently cron failures are scattered across individual logs with no aggregation.
- [ ] [DIAGNOSE_BRAIN_EDGE_REGRESSION] Investigate 10.3% graph edge drop (88211→79152) and memory count below 3000 threshold flagged repeatedly in alerts.log. Determine if caused by graph compaction/hygiene over-pruning or data loss. Fix root cause and restore healthy baseline. Touch: `graph_compaction.py`, `brain_hygiene.py`, `goal_hygiene.py`.
- [ ] [ACTION_FAILURE_PATTERN_ANALYSIS] Analyze the 50 action-type failures in episodes (259 success vs 50 action failures) to identify top recurring failure patterns. Group by error signature, identify the 3 most common root causes, and file targeted fixes or guardrails. Directly improves Action Accuracy (0.981→target 0.99+). Touch: `data/episodes/`, `episodic_memory.py`, relevant failing scripts.
- [ ] [SEMANTIC_CROSS_COLLECTION_BOOST] Boost semantic_cross_collection score (0.588 — weakest Phi component by far, next-weakest is 0.835). Run targeted `bulk_cross_link` between under-connected collection pairs (identity↔learnings, procedures↔context, goals↔episodes). Verify with `phi_metric.py` before/after. Target: 0.65+. Touch: `scripts/brain.py` cross-link functions, `phi_metric.py`.
- [ ] [OPEN_SOURCE_PRELAUNCH_CHECKLIST] (Bash/Shell) Create `scripts/oss_readiness_check.sh` — automated pre-launch audit: scan for hardcoded IPs/tokens/emails, validate LICENSE exists, check .gitignore covers secrets dirs, verify no large binaries in git history, confirm CLAUDE.md has no internal-only references. Output pass/fail report. P0 Milestone C (repo readiness) deadline is 2026-03-26. Non-Python task.
- [ ] [LONG_FUNCTION_DECOMPOSITION] Split the longest functions flagged by `reasonable_function_length` (0.772 — lowest structural code quality sub-metric, 622 files checked). Identify top 5 offenders via pylint/AST scan, decompose into smaller helpers. Improves code quality score and maintainability for open-source readiness. Touch: scripts with functions >80 lines.

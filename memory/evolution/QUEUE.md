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

### Milestone A — Foundation Freeze (by 2026-03-19)

### Milestone B — Brain / Context Quality (by 2026-03-23)
- [~] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. Current semantic_cross_collection=0.62 (target >0.75). _(2026-03-19: Added 13 bridge memories across 3 weakest pairs. Phi full computation times out at 120s due to 99k graph edges + 720 ONNX queries. Pair scores: proc↔learn=0.600, ctx↔goals=0.644, ep↔infra=0.555. Need graph compaction or parallel queries to verify full Phi. Blocked on compute time. Checklist B8.)_

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)

---

## P1 — This Week

- [ ] [LLM_BRAIN_REVIEW 2026-03-24] [LLM_BRAIN_REVIEW] Investigate why temporal/recency queries return only 3 results with poor relevance. Episodes should have timestamps that enable recency-boosted retrieval for 'recent' or 'last N hours' queries. — Temporal awareness is a known gap flagged in prior planning. An agent that can't answer 'what happened recently' has a significant operational blind spot.
- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/metrics/membench.py:run_membench` (137 lines), `scripts/heartbeat_postflight.py:_brain_store` (89 lines), `scripts/heartbeat_postflight.py:run_postflight` (1444 lines), `scripts/retrieval_benchmark.py:run_benchmark` (167 lines). Target: all functions ≤80 lines.

- [ ] [LLM_BRAIN_REVIEW 2026-03-23] [LLM_BRAIN_REVIEW] Audit clarvis-identity collection — it appears to contain mostly creator/origin info. Enrich it with operational identity: what Clarvis IS (architecture), what it DOES (capabilities), and how it WORKS (key subsystems). — clarvis-identity surfaced 'who created Clarvis' for an architecture query, suggesting the collection is too narrow. Identity should encompass architectural self-knowledge, not just origin story.

### Repo / Spine Audit
- [ ] [LEGACY_IMPORT_MIGRATION_PHASE1] Execute Phase 2 starting with the highest-risk/high-value migration: replace legacy wrapper imports inside `heartbeat_preflight.py` and `heartbeat_postflight.py` with direct `clarvis.*` imports where equivalent spine modules are confirmed. Do this incrementally with rollback-ready commits.

### Website / Public Presence
- [x] [CLARVIS_STYLEGUIDE_V1] _(2026-03-24: Delivered `docs/STYLEGUIDE.md` — 10 sections covering color system, typography scale, spacing tokens, card/panel language, buttons/links, motion principles, icon/diagram treatment, badges, layout, and copy tone. Codifies existing `style.css` design system into reusable reference.)_

### Benchmarking / CLR v2

### NEW ITEMS (added 2026-03-23 evolution analysis)
- [ ] [BRIER_CALIBRATION_OVERHAUL] Audit `clarvis_confidence.py` prediction-outcome loop: review bucket distributions, prune stale/low-signal predictions, recalibrate bin edges, and add a post-recalibration Brier check to `performance_benchmark.py`. Current brier capability=0.06 is the worst dimension. Target: brier ≥ 0.30 within 2 weeks.
- [x] [GIT_AUTOCOMMIT_CRON_HOOK] _(2026-03-24: `cron_autonomous.sh` already had git hygiene auto-fix since obligation_tracker.py was added. Added same hook to `cron_implementation_sprint.sh`. Both now call `obligation_tracker.py auto-fix` post-task — commits+pushes if dirty >60min, excludes secrets/large binaries.)_

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

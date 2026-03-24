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

- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/metrics/membench.py:run_membench` (137 lines), `scripts/heartbeat_postflight.py:_brain_store` (89 lines), `scripts/heartbeat_postflight.py:run_postflight` (1444 lines), `scripts/retrieval_benchmark.py:run_benchmark` (167 lines). Target: all functions ≤80 lines.

- [ ] [LLM_BRAIN_REVIEW 2026-03-23] [LLM_BRAIN_REVIEW] Audit clarvis-identity collection — it appears to contain mostly creator/origin info. Enrich it with operational identity: what Clarvis IS (architecture), what it DOES (capabilities), and how it WORKS (key subsystems). — clarvis-identity surfaced 'who created Clarvis' for an architecture query, suggesting the collection is too narrow. Identity should encompass architectural self-knowledge, not just origin story.

### Repo / Spine Audit
- [ ] [LEGACY_IMPORT_MIGRATION_PHASE1] Execute Phase 2 starting with the highest-risk/high-value migration: replace legacy wrapper imports inside `heartbeat_preflight.py` and `heartbeat_postflight.py` with direct `clarvis.*` imports where equivalent spine modules are confirmed. Do this incrementally with rollback-ready commits.

### Website / Public Presence
- [ ] [CLARVIS_STYLEGUIDE_V1] Define Clarvis visual identity for public-facing surfaces. Deliver a compact styleguide covering color system, typography, spacing scale, panel/card language, buttons/links, motion principles, icon/diagram treatment, and copy tone. Goal: reusable design language for website, dashboards, docs, and future tools — unmistakably Clarvis, not generic SaaS chrome.
- [x] [WEBSITE_POSITIONING_AND_COPY] Rewrite homepage and key public pages for interest and conversion: what Clarvis is, why it matters, what makes it different, current capabilities, architecture highlights, and why someone should care / follow / star the repo. _(2026-03-24: Rewrote homepage — added "The Problem / The Approach" narrative, 6-card feature grid, condensed architecture diagram, "Why Follow" call-to-action. Kept live status + completions. Marketing-first tone, not just documentation.)_

### Benchmarking / CLR v2
- [x] [CLR_PUBLIC_SCHEMA_V1] Design and document an open benchmark schema for memory tasks and results. _(2026-03-24: Created `docs/CLR_BENCHMARK_SCHEMA.md` — task schema (14 fields), result schema (15 fields), ability taxonomy (11 abilities), failure stage diagnostics, aggregate report schema, file conventions, and extension guide. All fields from the requirement are covered.)_
- [ ] [BEAM_SUBSET_ADAPTER_AND_ABILITY_GAP_AUDIT] Build a BEAM subset adapter (not full 10M first) and produce a gap audit showing which BEAM abilities CLR currently does not measure well: contradiction resolution, event ordering, instruction following, summarization, cross-domain robustness.
- [x] [CLR_CONTRADICTION_EVENT_INSTRUCTION_TASKS] Add first-class task families to CLR-Benchmark for contradiction resolution, event ordering, and persistent instruction following. _(2026-03-24: Added 3 abilities to ABILITY_TAXONOMY in clr_benchmark.py — contradiction_resolution, event_ordering, persistent_instruction. Created 15 task files in data/benchmarks/tasks/beam/ (5 per family). Documented in CLR_BENCHMARK_SCHEMA.md "Advanced" taxonomy section.)_
- [ ] [CLR_EVIDENCE_ATTRIBUTION_SCORING] Add evidence-support scoring: whether answers are backed by retrieved or gold evidence, and whether cited/supporting spans actually contain the needed facts. This should work across LongMemEval/MemBench/BEAM adapters.
- [ ] [CLR_LENGTH_DOMAIN_ROBUSTNESS_REPORTS] Add report generation for score vs context length, score vs domain, and degradation curves across retrieval mode / memory mode. This is required before open-sourcing CLR-Benchmark as a serious benchmark rather than a tuned dashboard.

### NEW ITEMS (added 2026-03-23 evolution analysis)
- [ ] [BRIER_CALIBRATION_OVERHAUL] Audit `clarvis_confidence.py` prediction-outcome loop: review bucket distributions, prune stale/low-signal predictions, recalibrate bin edges, and add a post-recalibration Brier check to `performance_benchmark.py`. Current brier capability=0.06 is the worst dimension. Target: brier ≥ 0.30 within 2 weeks.
- [ ] [GIT_AUTOCOMMIT_CRON_HOOK] Add a lightweight post-task git commit hook to `cron_autonomous.sh` and `cron_implementation_sprint.sh`: if working tree is dirty after Claude Code returns, stage changed workspace files (excluding secrets/data) and commit with a standardized message. Addresses the 16x git-hygiene obligation violation without requiring manual intervention.

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

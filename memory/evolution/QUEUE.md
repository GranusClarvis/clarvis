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
- [ ] [D4_ARCHITECTURE_PAGE] Publish sanitized architecture page derived from SELF.md/ROADMAP.md without private/internal details. _(Checklist D4.)_

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [E2_SECRET_SCAN_PASS] Run secret scan and verify the repo is clean after C1-C2. _(Checklist E2.)_
- [ ] [E3_FRESH_CLONE_SETUP] Validate fresh clone + setup from scratch and write down the exact bootstrap path. _(Checklist E3 — critical path.)_
- [x] [E5_README_MATCHES_REALITY] Final pass: ensure README accurately describes current architecture, commands, and repo structure. _(Done 2026-03-23: fixed website status, brain stats, CLI commands, project structure, testing paths, contributing link.)_
- [ ] [E6_PUBLIC_ROADMAP_SANITIZE] Update `ROADMAP.md` for public visibility; remove internal-only details, IDs, and operational specifics. _(Checklist E6.)_

---

## P1 — This Week

- [ ] [LLM_BRAIN_REVIEW 2026-03-23] [LLM_BRAIN_REVIEW] Audit clarvis-identity collection — it appears to contain mostly creator/origin info. Enrich it with operational identity: what Clarvis IS (architecture), what it DOES (capabilities), and how it WORKS (key subsystems). — clarvis-identity surfaced 'who created Clarvis' for an architecture query, suggesting the collection is too narrow. Identity should encompass architectural self-knowledge, not just origin story.
- [ ] [OBLIGATION_TRACKER 2026-03-23] [OBLIGATION_ESCALATION_ob_20260321_112950_0] Obligation violated 16x: Git hygiene: commit and push useful work. repeated violations
- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions still above target length: `clarvis/heartbeat/gate.py:check_gate`, `clarvis/orch/task_selector.py:score_tasks`, `scripts/heartbeat_gate.py:check_gate`. Target: all functions ≤80 lines.
- [ ] [DIRECTIVE_LLM_CLASSIFIER_UPGRADE] Add optional LLM-based classification fallback for ambiguous directives where rule-based classifier confidence < 0.5. Use task_router to pick cheapest model. Gate behind env var `DIRECTIVE_LLM_CLASSIFY=true`.

### Repo / Spine Audit
- [ ] [SPINE_USAGE_AUDIT] Perform a careful subsystem audit of Clarvis `scripts/` and spine modules before any major cleanup/open-source restructuring. For each significant feature/module, classify as: (1) core live, (2) partially wired, (3) good idea but not properly integrated yet, (4) experimental/research, or (5) retire/archive. Require evidence for each classification: current call sites, cron/hooks/runtime entrypoints, docs references, recent usage signals, and measurable value over plain OpenClaw. Output must include explicit recommendations per module: keep as-is, promote into spine, wire properly, wrap as adapter, move to `experimental/`, archive, or remove — with deletion-risk notes so useful systems are not broken by cleanup.

### Website / Public Presence
- [ ] [CLARVIS_STYLEGUIDE_V1] Define Clarvis visual identity for public-facing surfaces. Deliver a compact styleguide covering color system, typography, spacing scale, panel/card language, buttons/links, motion principles, icon/diagram treatment, and copy tone. Goal: reusable design language for website, dashboards, docs, and future tools — unmistakably Clarvis, not generic SaaS chrome.
- [ ] [WEBSITE_REFINEMENT_PASS] Refine website v0 into a stronger front-facing presentation of Clarvis. Improve visual hierarchy, polish spacing/layout, add cleaner animations, and align all pages to `CLARVIS_STYLEGUIDE_V1`. Goal: feel deliberate, distinctive, and worth starring — not merely functional.
- [ ] [WEBSITE_POSITIONING_AND_COPY] Rewrite homepage and key public pages for interest and conversion: what Clarvis is, why it matters, what makes it different, current capabilities, architecture highlights, and why someone should care / follow / star the repo. Goal: market Clarvis as a compelling evolving agent, not just document it.
- [ ] [WEBSITE_PROOF_AND_DEMOS] Add stronger proof signals to the public site: benchmark snippets, live status blocks, architecture diagrams, notable capabilities, and selected concrete examples/screenshots. Goal: visitors should leave with evidence, not just claims.

### Benchmarking / CLR v2
- [ ] [LONGMEMEVAL_ADAPTER_AND_BASELINE_RUN] Build a `clarvis bench longmemeval` adapter that can run Clarvis memory pipelines on LongMemEval-S first, with support for full-history and oracle-retrieval modes. Output per-ability scores (IE, MR, KU, TR, ABS), retrieval diagnostics, and a baseline comparison against raw long-context prompting.
- [ ] [CLR_ORACLE_RETRIEVAL_MODE] Add an evaluation mode to CLR-Benchmark adapters that uses gold/oracle evidence when available. Purpose: separate retrieval failure from reasoning/reading failure so improvements are scientifically interpretable.
- [ ] [MEMBENCH_ADAPTER_REFLECTIVE_OBSERVATION] Build a `clarvis bench membench` adapter covering the four MemBench quadrants: participation-factual, participation-reflective, observation-factual, observation-reflective. Report effectiveness, recall, capacity, and temporal efficiency splits.
- [ ] [CLR_SPLIT_INTERNAL_VS_BENCHMARK] Split current CLR into (A) `CLR-Internal` for Clarvis health/architecture metrics and (B) `CLR-Benchmark` for external task-based evaluation. Preserve current composite score semantics internally, but stop treating internal telemetry as universal benchmark signal.
- [ ] [CLR_PUBLIC_SCHEMA_V1] Design and document an open benchmark schema for memory tasks and results: task_id, benchmark, domain, ability_tags, context_length, scenario, gold_answer, gold_evidence, answer_score, abstention_score, latency_ms, token_cost, retrieval_count, and diagnostics.
- [ ] [CLR_FAILURE_STAGE_BREAKDOWN] Add stage-separated scoring and reports for memory write/index, retrieval, reasoning over retrieved evidence, and final answer quality. LongMemEval oracle mode should feed this directly.
- [ ] [BEAM_SUBSET_ADAPTER_AND_ABILITY_GAP_AUDIT] Build a BEAM subset adapter (not full 10M first) and produce a gap audit showing which BEAM abilities CLR currently does not measure well: contradiction resolution, event ordering, instruction following, summarization, cross-domain robustness.
- [ ] [CLR_CONTRADICTION_EVENT_INSTRUCTION_TASKS] Add first-class task families to CLR-Benchmark for contradiction resolution, event ordering, and persistent instruction following. These are benchmark-critical gaps exposed by BEAM.
- [ ] [CLR_EVIDENCE_ATTRIBUTION_SCORING] Add evidence-support scoring: whether answers are backed by retrieved or gold evidence, and whether cited/supporting spans actually contain the needed facts. This should work across LongMemEval/MemBench/BEAM adapters.
- [ ] [CLR_LENGTH_DOMAIN_ROBUSTNESS_REPORTS] Add report generation for score vs context length, score vs domain, and degradation curves across retrieval mode / memory mode. This is required before open-sourcing CLR-Benchmark as a serious benchmark rather than a tuned dashboard.

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

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
- [ ] [C3_VERIFY_GITIGNORE_AND_TRACKED_DATA] Verify `data/` and `monitoring/` ignore rules by checking tracked files, untracking anything that should not be versioned, and documenting safe boundaries. _(Checklist C3.)_
- [ ] [C5_CONSOLIDATE_TESTS] Consolidate split tests under `tests/` (from `tests/`, `scripts/tests/`, `clarvis/tests/`) with minimal breakage. _(Checklist C5.)_
- [ ] [C6_ADD_ROOT_README] Add a strong root `README.md` explaining what Clarvis is, architecture at a glance, quick start, repo boundaries, and current status. _(Checklist C6 — critical path.)_
- [ ] [C11_CLARVIS_DB_EXTRACTION_PLAN] Extract or isolate `clarvis-db` boundary into a separate repo/package plan with scrubbed public-facing structure, LICENSE, and CI requirements documented. _(Checklist C11 — nice-to-have but important repo-boundary work.)_

### Milestone D — Public Surface (by 2026-03-29)
- [ ] [D1_WEBSITE_V0_SCAFFOLD] Build website v0 scaffold from `docs/WEBSITE_V0_INFORMATION_ARCH.md`. Prioritize static, fast, minimally styled public presence over polish. _(Checklist D1 — critical path.)_
- [ ] [D2_PUBLIC_STATUS_ENDPOINT] Implement `/api/status` or equivalent public feed endpoint with the documented data contract. _(Checklist D2.)_
- [ ] [D3_CLR_ON_WEBSITE] Surface CLR score on website v0 once endpoint/scaffold exists. _(Checklist D3.)_
- [ ] [D4_ARCHITECTURE_PAGE] Publish sanitized architecture page derived from SELF.md/ROADMAP.md without private/internal details. _(Checklist D4.)_
- [x] [D5_REPOS_PAGE] Add repos/boundaries page showing main repo, extracted pieces, and status. _(Checklist D5. Done 2026-03-22: `website/static/repos.html` — static page with 2 repos, extraction status, anti-sprawl policy.)_
- [ ] [D6_DOMAIN_AND_DEPLOYMENT] Deploy website v0 to an IP/domain-accessible target with simple, reproducible deployment notes. _(Checklist D6.)_

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [E2_SECRET_SCAN_PASS] Run secret scan and verify the repo is clean after C1-C2. _(Checklist E2.)_
- [ ] [E3_FRESH_CLONE_SETUP] Validate fresh clone + setup from scratch and write down the exact bootstrap path. _(Checklist E3 — critical path.)_
- [ ] [E4_WEBSITE_V0_LIVE] Confirm website v0 is live and publicly accessible. _(Checklist E4.)_
- [ ] [E5_README_MATCHES_REALITY] Final pass: ensure README accurately describes current architecture, commands, and repo structure. _(Checklist E5.)_
- [ ] [E6_PUBLIC_ROADMAP_SANITIZE] Update `ROADMAP.md` for public visibility; remove internal-only details, IDs, and operational specifics. _(Checklist E6.)_

---

## P1 — This Week

- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions still above target length: `clarvis/heartbeat/gate.py:check_gate`, `clarvis/orch/task_selector.py:score_tasks`, `scripts/heartbeat_gate.py:check_gate`. Target: all functions ≤80 lines.
- [ ] [DIRECTIVE_LLM_CLASSIFIER_UPGRADE] Add optional LLM-based classification fallback for ambiguous directives where rule-based classifier confidence < 0.5. Use task_router to pick cheapest model. Gate behind env var `DIRECTIVE_LLM_CLASSIFY=true`.

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

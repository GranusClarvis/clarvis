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
- [x] [A5_RUNTIME_MODE_CONTROL_PLANE_MERGE] Already merged in commit 66cd7ea (2026-03-17). Runtime mode fully wired: clarvis/runtime/mode.py, CLI, task_selector, gate integration, tests. _(Checklist A5.)_
- [x] [A6_TRAJECTORY_EVAL_HARNESS_MERGE] Already merged in commit 66cd7ea (2026-03-17). Trajectory eval active: clarvis/metrics/trajectory.py, postflight integration, CLI bench commands, tests. _(Checklist A6.)_
- [ ] [A7_MODE_SUBCOMMAND_WIRING] Stabilize CLI by wiring `python3 -m clarvis mode ...` to the merged runtime mode control-plane. _(Checklist A7 partial → done target.)_
- [ ] [A8_MERGE_ADR_DOCUMENTATION] Merge ADR-0001 and ADR-0002 from fork into the main repo docs. _(Checklist A8 — trivial but required to freeze architecture.)_

### Milestone B — Brain / Context Quality (by 2026-03-23)
- [~] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. Current semantic_cross_collection=0.62 (target >0.75). _(2026-03-19: Added 13 bridge memories across 3 weakest pairs. Phi full computation times out at 120s due to 99k graph edges + 720 ONNX queries. Pair scores: proc↔learn=0.600, ctx↔goals=0.644, ep↔infra=0.555. Need graph compaction or parallel queries to verify full Phi. Blocked on compute time. Checklist B8.)_

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)
- [ ] [C1_REMOVE_HARDCODED_SECRETS] Remove hardcoded secrets from tracked files. Audit all files flagged in `OPEN_SOURCE_READINESS_AUDIT.md`, replace with env/config references, and verify no live credentials remain in repo text. _(Checklist C1 — release blocker.)_
- [ ] [C2_PURGE_CREDENTIALS_FROM_CHROMADB] Purge embedded credentials from ChromaDB/community summary artifacts and re-embed clean replacements. Document exact scrub/rebuild procedure. _(Checklist C2 — release blocker.)_
- [ ] [C3_VERIFY_GITIGNORE_AND_TRACKED_DATA] Verify `data/` and `monitoring/` ignore rules by checking tracked files, untracking anything that should not be versioned, and documenting safe boundaries. _(Checklist C3.)_
- [ ] [C4_DELETE_DEPRECATED_SCRIPTS] Delete `scripts/deprecated/` after confirming nothing still imports or references it. _(Checklist C4.)_
- [ ] [C5_CONSOLIDATE_TESTS] Consolidate split tests under `tests/` (from `tests/`, `scripts/tests/`, `clarvis/tests/`) with minimal breakage. _(Checklist C5.)_
- [ ] [C6_ADD_ROOT_README] Add a strong root `README.md` explaining what Clarvis is, architecture at a glance, quick start, repo boundaries, and current status. _(Checklist C6 — critical path.)_
- [ ] [C7_ADD_LICENSE_FILE] Add standalone `LICENSE` file at repo root matching the intended license. _(Checklist C7.)_
- [ ] [C8_ADD_CONTRIBUTING] Add `CONTRIBUTING.md` with setup, coding standards, tests, and PR expectations. _(Checklist C8.)_
- [ ] [C9_BASIC_CI_WORKFLOW] Add basic GitHub Actions CI for lint + test on the main repo. Keep it minimal and reliable. _(Checklist C9.)_
- [ ] [C11_CLARVIS_DB_EXTRACTION_PLAN] Extract or isolate `clarvis-db` boundary into a separate repo/package plan with scrubbed public-facing structure, LICENSE, and CI requirements documented. _(Checklist C11 — nice-to-have but important repo-boundary work.)_

### Milestone D — Public Surface (by 2026-03-29)
- [ ] [D1_WEBSITE_V0_SCAFFOLD] Build website v0 scaffold from `docs/WEBSITE_V0_INFORMATION_ARCH.md`. Prioritize static, fast, minimally styled public presence over polish. _(Checklist D1 — critical path.)_
- [ ] [D2_PUBLIC_STATUS_ENDPOINT] Implement `/api/status` or equivalent public feed endpoint with the documented data contract. _(Checklist D2.)_
- [ ] [D3_CLR_ON_WEBSITE] Surface CLR score on website v0 once endpoint/scaffold exists. _(Checklist D3.)_
- [ ] [D4_ARCHITECTURE_PAGE] Publish sanitized architecture page derived from SELF.md/ROADMAP.md without private/internal details. _(Checklist D4.)_
- [ ] [D5_REPOS_PAGE] Add repos/boundaries page showing main repo, extracted pieces, and status. _(Checklist D5.)_
- [ ] [D6_DOMAIN_AND_DEPLOYMENT] Deploy website v0 to an IP/domain-accessible target with simple, reproducible deployment notes. _(Checklist D6.)_

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [E1_FULL_TEST_SUITE_PASS] Run and stabilize full test suite after consolidation and merges. _(Checklist E1.)_
- [ ] [E2_SECRET_SCAN_PASS] Run secret scan and verify the repo is clean after C1-C2. _(Checklist E2.)_
- [ ] [E3_FRESH_CLONE_SETUP] Validate fresh clone + setup from scratch and write down the exact bootstrap path. _(Checklist E3 — critical path.)_
- [ ] [E4_WEBSITE_V0_LIVE] Confirm website v0 is live and publicly accessible. _(Checklist E4.)_
- [ ] [E5_README_MATCHES_REALITY] Final pass: ensure README accurately describes current architecture, commands, and repo structure. _(Checklist E5.)_
- [ ] [E6_PUBLIC_ROADMAP_SANITIZE] Update `ROADMAP.md` for public visibility; remove internal-only details, IDs, and operational specifics. _(Checklist E6.)_

---

## P1 — This Week

- [x] [CRON_MAINTENANCE_TIMEOUT_GUARD] Added `set_script_timeout` to lock_helper.sh + wired into all 5 maintenance scripts (checkpoint=300s, compaction=600s, verify=300s, vacuum=600s, soak=120s). Watchdog kills hung scripts via SIGTERM→SIGKILL, EXIT trap releases all locks. Tested. _(2026-03-22.)_
- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions still above target length: `clarvis/heartbeat/gate.py:check_gate`, `clarvis/orch/task_selector.py:score_tasks`, `scripts/heartbeat_gate.py:check_gate`. Target: all functions ≤80 lines.
- [ ] [DIRECTIVE_LLM_CLASSIFIER_UPGRADE] Add optional LLM-based classification fallback for ambiguous directives where rule-based classifier confidence < 0.5. Use task_router to pick cheapest model. Gate behind env var `DIRECTIVE_LLM_CLASSIFY=true`.

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

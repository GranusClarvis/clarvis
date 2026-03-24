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

### March 24 alignment note
_Queue refreshed on 2026-03-24 to stay explicitly locked to the 2026-03-31 delivery goal. Rule for this section until deadline: only keep items that directly improve release readiness, public presentability, repo cleanliness, website completeness, or final validation. Everything else stays P1/P2 unless it is a blocker._

### Milestone A — Foundation Freeze (by 2026-03-19)
- [x] [DELIVERY_STATUS_RECONCILE] _(Done 2026-03-24: reconciled checklist — C7/C8/C9/D3/E4 upgraded to DONE, summary counts updated, 25/31 items now done.)_
- [ ] [A5_A7_RUNTIME_MODE_AND_CLI_FINISH] Finish remaining Foundation Freeze gaps: merge runtime mode control-plane, trajectory harness if still unmerged, and stabilize `python3 -m clarvis` mode entrypoint. _Only keep scope that materially affects public/demo readiness._

### Milestone B — Brain / Context Quality (by 2026-03-23)
- [~] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. Current semantic_cross_collection=0.62 (target >0.75). _(2026-03-19: Added 13 bridge memories across 3 weakest pairs. Phi full computation times out at 120s due to 99k graph edges + 720 ONNX queries. Pair scores: proc↔learn=0.600, ctx↔goals=0.644, ep↔infra=0.555. Need graph compaction or parallel queries to verify full Phi. Blocked on compute time. Checklist B8.)_
- [ ] [TEMPORAL_RETRIEVAL_FIX] Implement the 2026-03-24 temporal retrieval fix: add numeric `created_epoch` metadata, use native Chroma filtering, over-fetch recent candidates, and add chronological fallback for pure temporal queries. _Relevance: recent-memory recall is core to trust/demo quality._

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)
- [ ] [C_OPEN_SOURCE_READINESS_SWEEP] Run one authoritative open-source readiness sweep: verify hardcoded secrets are truly removed, verify tracked-data/.gitignore state, confirm root LICENSE + CONTRIBUTING + CI status, and close remaining release blockers. _Output: checklist updated + any residual blockers listed explicitly._
- [ ] [C_TEST_AND_REPO_CONSOLIDATION] Consolidate or at minimum document the current test layout (`tests/`, `scripts/tests/`, `clarvis/tests/`) and ensure CI covers the intended suite. _If full consolidation is too risky before deadline, produce a stable documented compromise._
- [x] [E3_FRESH_CLONE_AND_SETUP] _(Done 2026-03-24: created `scripts/gate_fresh_clone.sh`, validated 6-step setup in fresh venv — 55 tests pass, lint clean.)_

### Milestone D — Public Surface (by 2026-03-29)
- [ ] [D2_PUBLIC_STATUS_ENDPOINT] Wire the real public status endpoint and ensure website surfaces live or periodically generated status data cleanly.
- [ ] [D4_PUBLIC_ARCHITECTURE_AND_ROADMAP_SANITIZE] Finish the sanitized architecture/public roadmap pass so the public site explains Clarvis clearly without leaking internal-only details.
- [ ] [D_SURFACE_PROOF_POLISH] Final polish pass on website v0: proof signals, copy, style consistency, navigation, obvious broken links, and mobile/basic responsiveness. Keep this pragmatic, not perfectionist.

### Milestone E — Final Validation (by 2026-03-31)
- [ ] [E_FINAL_RELEASE_GATE] Run final release gate: full tests, secret scan, fresh clone/setup, website reachable, README matches reality, roadmap/public docs sane. Output one concise ship/no-ship summary with blockers if any.

---

## P1 — This Week

- [ ] [DECOMPOSE_LONG_FUNCTIONS] Decompose oversized functions: `clarvis/metrics/membench.py:run_membench` (137 lines), `scripts/heartbeat_postflight.py:_brain_store` (89 lines), `scripts/heartbeat_postflight.py:run_postflight` (1444 lines), `scripts/retrieval_benchmark.py:run_benchmark` (167 lines). Target: all functions ≤80 lines.


### Repo / Spine Audit

### Website / Public Presence

### Benchmarking / CLR v2

### NEW ITEMS (added 2026-03-23 evolution analysis)
- [ ] [BRIER_CALIBRATION_OVERHAUL] Audit `clarvis_confidence.py` prediction-outcome loop: review bucket distributions, prune stale/low-signal predictions, recalibrate bin edges, and add a post-recalibration Brier check to `performance_benchmark.py`. Current brier capability=0.06 is the worst dimension. Target: brier ≥ 0.30 within 2 weeks.

### NEW ITEMS (added 2026-03-24 evolution analysis)
- [x] [CI_TEST_COVERAGE_EXPANSION] _(Done 2026-03-24: added 4 root-level test files to CI, 25 tests all passing.)_
- [ ] [SEMANTIC_CROSS_COLLECTION_UNBLOCK] Unblock SEMANTIC_CROSS_COLLECTION_BRIDGES (stuck since 2026-03-19): profile Phi computation timeout, identify which of the 99k graph edges + 720 ONNX queries dominate wall time, and implement either sampling-based Phi estimation or collection-pair parallel evaluation. Current semantic_cross_collection=0.57 (target >0.75).

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

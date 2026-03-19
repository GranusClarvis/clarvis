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

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26)

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)

### P0 Fixes Added — 2026-03-19 Evening Code Review

---

## P0 — Fork Integration Execution Phases

### Phase 1 — Architecture Contracts & Benchmark Core

### Phase 2 — Mode System

### Phase 3 — Host Compatibility & Open-Source Readiness

### Phase 4 — Wiring Into Real Runtime

### Phase 5 — Public Surface (only after readiness gates)

### Guard Rails / Explicit Non-Goals

---

## P1 — This Week


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
- [ ] [CLR_BASELINE_WIRING] Wire CLR into the canonical benchmark path so it can run from the main repo without fork-only assumptions. Ensure outputs land in structured JSON/JSONL with commit SHA, timestamp, and component subscores.
- [ ] [CLR_PHIID_DIMENSION] Implement a new CLR dimension: **Integration Dynamics** based on ΦID-inspired engineering proxies. Start with `redundancy_ratio`, `unique_contribution_score`, and `synergy_gain`. Design reference: `docs/CLR_PHIID_BENCHMARK_PLAN.md`.
- [ ] [CLR_PERTURBATION_HARNESS] Build a deterministic perturbation / ablation harness for context assembly and recall. Toggle modules such as episodic recall, graph expansion, related_tasks, decision_context, and reasoning scaffold; record score deltas and failure modes.
- [ ] [CLR_DELTA_TRACKING] Persist per-run benchmark history with before/after deltas for autonomous changes. Goal: answer whether additions actually improved Clarvis or merely changed code shape.
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

## NEW ITEMS


- [ ] [BRIEF_TOP_SECTION_ENRICHMENT] Improve content quality of the 3 highest-importance brief sections (related_tasks=0.304, episodes=0.273, decision_context=0.267) in `clarvis/context/assembly.py`. Related_tasks should include task dependencies and blockers from QUEUE.md; episodes should surface failure-avoidance patterns inline; decision_context should inject success criteria keywords that match output vocabulary. Direct target: context_relevance ≥0.73 (currently 0.701).

- [ ] [CALIBRATION_BRIER_AUDIT] Audit and recalibrate confidence predictions in `scripts/clarvis_confidence.py`. Brier capability score=0.10 (worst metric). Review domain-specific accuracy, prune stale predictions older than 30 days, recalibrate domain thresholds. Check if low Brier score is due to prediction staleness or systematic over/under-confidence.

- [ ] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. Current semantic_cross_collection=0.62 (target >0.75). Run targeted `knowledge_synthesis.py` bridge-building for the lowest-overlap pairs: clarvis-procedures↔clarvis-learnings, clarvis-context↔clarvis-goals, clarvis-episodes↔clarvis-infrastructure. Verify improvement via `phi_metric.py`.

- [ ] [BENCHMARK_SCORECARD_STRATEGY] Create a benchmark scorecard strategy that explicitly maps current goals to measurable benchmark dimensions. Tie existing goals (Session Continuity, Heartbeat Efficiency, Self-Reflection, CLR, context quality, Phi/integration) to concrete daily/weekly metrics so every major addition has an evaluation lane.



## Research Additions



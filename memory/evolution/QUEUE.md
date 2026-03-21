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
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

## NEW ITEMS

- [ ] [CONTEXT_SECTION_BUDGET_ENFORCER] Wire context_relevance feedback loop into assembly.py: sections with historical mean relevance < 0.12 (knowledge, working_memory, attention, meta_gradient, brain_goals) should be collapsed to single-line stubs or omitted entirely. Measure before/after context_relevance delta. Target: push context_relevance from 0.481 → 0.65+. _(Targets weakest metric: Context Relevance)_
- [ ] [STRATEGIC_AUDIT_ESCALATION] Make cron_strategic_audit.sh auto-extract P0/P1 findings and append them to QUEUE.md via queue_writer.py. Currently audit output sits in logs with no downstream action. Add JSON structured output + queue integration. _(Bash/Python hybrid, closes audit→action gap)_
- [ ] [CLR_RELEVANCE_DIMENSION_WEIGHT] Increase prompt_context weight in CLR scoring (clr.py) from 0.13 → 0.18, rebalance other weights, and add a direct context_relevance sub-score that feeds assembly adaptive thresholds. Validates that CLR improvements actually improve brief quality. _(Targets weakest metric: Context Relevance via CLR feedback)_
- [ ] [CRON_MAINTENANCE_TIMEOUT_GUARD] Add timeout and stale-lock detection to the 04:00-05:05 maintenance window scripts (cron_graph_checkpoint.sh, cron_graph_compaction.sh, cron_graph_verify.sh, cron_chromadb_vacuum.sh). Currently they share /tmp/clarvis_maintenance.lock but have no max-wait or deadlock recovery. _(Bash task — operational reliability)_
- [ ] [HEARTBEAT_CONTEXT_RELEVANCE_GATE] Add context_relevance as an explicit dimension in heartbeat_gate.py capability assessment. If context_relevance < 0.60, auto-prioritize context-improvement tasks over other queue items. Currently heartbeat asks "which capability is weakest" but doesn't consider context_relevance. _(Targets weakest metric: Context Relevance via prioritization)_


- [~] [SEMANTIC_CROSS_COLLECTION_BRIDGES] Strengthen weak cross-collection semantic links. Current semantic_cross_collection=0.62 (target >0.75). _(2026-03-19: Added 13 bridge memories across 3 weakest pairs. Phi full computation times out at 120s due to 99k graph edges + 720 ONNX queries. Pair scores: proc↔learn=0.600, ctx↔goals=0.644, ep↔infra=0.555. Need graph compaction or parallel queries to verify full Phi. Blocked on compute time.)_


## Research Additions




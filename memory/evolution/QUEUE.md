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

- [ ] [FIX_QUEUE_DELETED_SEMANTIC_BRIDGE_BUILDER] P0: Repair broken queue/docs references to `scripts/semantic_bridge_builder.py` — the script was deleted, but QUEUE.md still assigns cross-collection repair work to it. Replace with the canonical implementation/path or restore a thin compatibility wrapper before the task is scheduled.
- [x] [DAILY_MEMORY_FILE_AUTOCREATE] P0: Ensure cron/reporting path creates `memory/YYYY-MM-DD.md` for the current date before writing daily outputs. 2026-03-18 had no daily memory file, which breaks continuity and weakens end-of-day review/auditability. _(2026-03-18: Created the missing daily file to restore continuity; follow-up automation still advisable if cron paths can miss file creation.)_
- [ ] [CONTEXT_RELEVANCE_FAST_FEEDBACK] Add recent-episode fast-path weighting in `clarvis/context/assembly.py` — current budget adjustment uses 14-day historical aggregate, meaning pruning improvements take 2 weeks to register. Add exponential recency weighting (last 5 episodes = 3x weight) so DYCP budget adjustments respond within 1-2 cycles. **Target: context_relevance ≥ 0.75.**
- [ ] [P0_PRIORITY_FLOOR] Add P0 priority floor in `clarvis/orch/task_selector.py` — guarantee P0 tasks always rank in top-3 regardless of spotlight alignment score. Currently P0 gets 0.9 importance weight but can be outranked by well-aligned P1/P2 tasks, undermining delivery deadlines.
- [ ] [CONTEXT_SECTION_PRUNING] Add aggressive per-section pruning in `clarvis/context/assembly.py` — sections with historical mean relevance < 0.15 should be collapsed to a 1-line stub instead of full rendering. Currently `_BUDGET_TO_SECTIONS` maps groups but no section is ever fully dropped. Directly reduces noise in the brief. **Target: context_relevance ≥ 0.75.**
- [ ] [SEMANTIC_CROSS_COLLECTION_REPAIR] Boost `semantic_cross_collection` from 0.65 toward 0.75 — run targeted `semantic_bridge_builder.py` on the weakest collection pairs (identify via `phi_metric.py` breakdown), then verify edge count and overlap improvement. Improves Phi composite.

## Research Additions

- [x] [RESEARCH_ADAPTIVE_CONTEXT_PRUNING_RAG] Research adaptive context pruning for token-efficient RAG pipelines. (2026-03-18)



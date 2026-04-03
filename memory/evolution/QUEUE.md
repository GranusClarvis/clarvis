# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

_(P0 delivery window 2026-03-31 completed. Reset for next sprint.)_

### Open-Source Release Blockers (2026-04-03 deep audit)

---

## P1 — This Week

### Spine Migration Gaps (2026-04-03 deep audit)

### Documentation Accuracy (2026-04-03 deep audit)

### Code Quality (2026-04-03 deep audit)

### Queue Process (2026-04-03 deep audit)

### Execution Reliability (2026-04-03 cron failure follow-up)

### SWO / Clarvis Brand Integration (2026-04-03)
- [ ] [SWO_CLARVIS_BRAND_AUDIT] Audit Clarvis public-facing branding, naming treatment, color system, and visual identity against Star World Order. Decide what stays Clarvis-native vs what must adopt SWO language.
- [ ] [SWO_CLARVIS_DESIGN_BRIEF] Create a concrete design brief for "Clarvis as a Star World Order feature": palette, typography, UI motifs, icon/avatar direction, copy tone, and examples of correct/incorrect usage.
- [ ] [SWO_CLARVIS_NAMING_ARCHITECTURE] Define naming architecture so Clarvis keeps its strong product name while fitting under SWO (e.g. "Clarvis by Star World Order" / "SWO Clarvis" / section naming rules). Include guidance for feature names and dashboard terminology.
- [ ] [SWO_CLARVIS_TOKEN_ALIGNMENT] Inspect the Star World Order repo design tokens/components and map Clarvis onto them. Identify reusable tokens, missing variants, and what must be added for visual consistency.
- [ ] [SWO_CLARVIS_LANDING_CONCEPT] Produce a concrete landing/page concept for Clarvis inside SWO: page structure, CTA hierarchy, screenshots/mock sections, and how to explain Clarvis as an SWO capability without losing the Clarvis identity.
- [ ] [SWO_CLARVIS_COPY_PASS] Rewrite public-facing Clarvis copy into an SWO-aligned but non-cringe voice: cosmic/order framing where helpful, while preserving clarity and product credibility.

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)
- [~] [PROMPT_LLM_REVIEW_BENCH] _(2026-04-03: Static eval framework built. LLM-judged scoring designed but not yet implemented — needs OpenRouter integration for cost-effective evaluation. Framework ready in `prompt_quality_eval.py`.)_

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~20 scripts with reusable library logic still in scripts/: cognitive_load, brain_bridge, workspace_broadcast, theory_of_mind, temporal_self, world_models, causal_model, reasoning_chains, failure_amplifier, parameter_evolution, tool_maker, etc. Each is a separate migration task. Low priority — spine is functional without these.

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for delivery._

### Roadmap Gaps (2026-04-03 audit — items from ROADMAP.md with no queue entry)
- [ ] [ROADMAP_MULTI_AGENT_PARALLEL] Multi-agent parallel execution (ROADMAP Phase 3.4).
- [ ] [ROADMAP_MEMORY_EVOLUTION] A-Mem style memory evolution — supersession, contradiction detection (ROADMAP Phase 5.1). _(Partially implemented in `brain/memory_evolution.py` — verify coverage.)_
- [ ] [ROADMAP_WORKSPACE_PERSISTENCE] Cross-session workspace persistence (ROADMAP Phase 5.5).

---

## Partial Items (tracked, not actively worked)
- [~] [WORKTREE_AUTO_ENABLE] In `cron_autonomous.sh`, auto-detect code-modifying tasks and enable `--isolated` worktree mode. _(Partial 2026-04-03: detection logic added. Full worktree isolation requires restructuring — follow-up needed.)_

---

## NEW ITEMS

### Research Sessions

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:bench-retrieval-01] Implement BEIR-style retrieval benchmark for ClarvisDB — Create a retrieval benchmark using 50+ query-document pairs with known relevance labels. Measure nDCG@10, MAP, and Recall@k. Compare ClarvisDB's MiniLM embeddings against BM25 baseline on the same que

### Bloat Reduction (2026-04-03 evolution analysis — weakest metric: bloat=0.400)
- [ ] [BLOAT_AGGRESSIVE_DEDUP_PRUNE] Run targeted dedup+prune on `clarvis-learnings` (1459 items, 41% of brain) and `clarvis-memories` (612 items). Goal: reduce total_memories below 3000 to drop bloat score by 0.2. Use `brain_hygiene.py run` + manual similarity scan on the two largest collections. Validate retrieval quality doesn't regress via `performance_benchmark.py`.
- [ ] [BLOAT_FORMULA_RECALIBRATE] The bloat formula penalizes raw memory count (>2000: +0.2, >3000: +0.2) without crediting graph health. With density=37.57 (target >1.0), the score is misleadingly high. Add a graph-density discount: if density > 10, reduce bloat_score by 0.1. Update both the formula in `performance_benchmark.py` and the target in ROADMAP.md if needed.

### Cron Hardening (2026-04-03 evolution analysis — non-Python task)
- [ ] [CRON_LOGROTATE_AUDIT] Audit `/home/agent/.openclaw/workspace/monitoring/` and cron log outputs for unbounded growth. Several cron scripts append to `.log` files without rotation beyond the weekly `cron_cleanup.sh`. Add logrotate configs or size-capped truncation for: `autonomous.log`, `reflection.log`, `health_monitor.log`, and any file >10MB. Shell/config task, no Python.

### Self-Awareness (2026-04-03 evolution analysis)
- [ ] [CAPABILITY_BRIER_IMPROVEMENT] Brier score dimension shows 0.12 in capability scores (lowest). Investigate: are predictions being recorded but not resolved? Run `clarvis_confidence.py sweep` and check resolution pipeline. Target: get Brier below 0.10 by ensuring stale predictions are swept and calibration feedback loop is closing.

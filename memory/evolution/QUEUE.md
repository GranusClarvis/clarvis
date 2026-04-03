# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

_(P0 delivery window 2026-03-31 completed. Reset for next sprint.)_

### Open-Source Release Blockers (2026-04-03 deep audit)
- [x] [OSR_GIT_HISTORY_SCRUB] _(2026-04-03: Comprehensive git history scan using git-filter-repo confirmed clean. Patterns checked: sk-or-v1-*, sk-ant-*, ghp_*, ghu_*, AKIA*, xox*, bot*:AA*. All matches are documentation placeholders, regex patterns, or test fixtures. No real secrets in history. No BFG run needed.)_

---

## P1 — This Week

### Spine Migration Gaps (2026-04-03 deep audit)
- [ ] [SPINE_PROXY_REPLACEMENT] Replace 5 proxy modules that inject scripts/ via sys.path with real implementations: `clarvis/cognition/reasoning.py`, `clarvis/cognition/somatic_markers.py`, `clarvis/memory/soar.py`, `clarvis/learning/meta_learning.py`, `clarvis/brain/graphrag.py`. Move full implementations from scripts/ into spine; convert scripts to BRIDGE wrappers.
- [ ] [SPINE_HOOK_DEPS_MIGRATE] Migrate 3 hook dependencies from scripts/ into spine: `actr_activation.py` → `clarvis/brain/actr_activation.py`, `retrieval_quality.py` → `clarvis/brain/retrieval_quality.py`, `synaptic_memory.py` → `clarvis/memory/synaptic_memory.py`. Currently imported via sys.path injection in `brain/hooks.py`.

### Documentation Accuracy (2026-04-03 deep audit)

### Code Quality (2026-04-03 deep audit)

### Queue Process (2026-04-03 deep audit)
- [ ] [QUEUE_AUTO_ARCHIVE] The queue header says "auto-archived" but archival is manual and 7+ days stale. Either implement a script that moves [x] items to QUEUE_ARCHIVE.md, or change the header to reflect manual cadence.

### Execution Reliability (2026-04-03 cron failure follow-up)

### Context/Prompt Pipeline (2026-04-03 deep audit, refined 2026-04-03 second-opinion audit)
- [x] [PROMPT_DUAL_PATH_UNIFY] _(2026-04-03: prompt_builder.get_context_brief() now delegates to generate_tiered_brief() as its core — both paths use the same primacy/recency optimized assembly. prompt_builder adds extras: goals, synaptic, attention, capabilities, queue. Tests pass: 17/17.)_
- [x] [CONTEXT_DUPLICATE_RECALL] _(2026-04-03: Removed duplicate introspect_for_task + brain.recall for IDs in prompt_builder. Heartbeat_preflight: synaptic spread now reuses recalled_memory_ids from brain_bridge in sequential path. Parallel path: duplicate is hidden by parallelism, so acceptable.)_
- [x] [CRON_RESEARCH_CONTEXT_DOWNGRADE] _(2026-04-03: Switched cron_research.sh line 232 from `context_compressor.py brief` to `prompt_builder.py context-brief --task "$RESEARCH_TASK" --tier standard`.)_
- [x] [CONTEXT_SUPPLEMENTARY_DEDUP] _(2026-04-03: Added `tiered_brief_used` flag to heartbeat_preflight. When tiered brief is active, supplementary append skips: working_memory, failure_avoidance, procedures — all already in the tiered brief.)_
- [x] [CRON_EVOLUTION_BARE_CONTEXT] _(2026-04-03: Added `prompt_builder.py context-brief --task "strategic evolution analysis" --tier full` call to cron_evolution.sh. Brain introspection + episodic + failure patterns now injected into evolution prompt.)_
- [x] [CRON_IMPLEMENTATION_CONTEXT_DOWNGRADE] _(2026-04-03: Verified already uses heartbeat_preflight.py as primary path (line 69). Only falls back to context_compressor on failure. Queue description was outdated.)_
- [x] [PROMPT_QUALITY_EVAL_MATRIX] _(2026-04-03: Created `scripts/prompt_quality_eval.py` — static eval matrix across 10 task types × 4 routes. Checks: section coverage, priority coverage, ordering score, duplication. Results in `data/prompt_eval/eval_results.json`.)_
- [x] [CONTEXT_BUDGET_QUALITY_POLICY] _(2026-04-03: Created `data/prompt_eval/context_budget_policy.json` with 9 task classes, each with section priorities [0-1] and tier defaults. Wired into `assembly.py:generate_tiered_brief()` — policy weights merge with empirical weights via geometric mean.)_
- [x] [PROMPT_ROUTE_GOLDEN_FIXTURES] _(2026-04-03: Created `tests/test_prompt_route_golden.py` — 17 tests covering tiered brief, prompt_builder, and budget policy integration. Golden snapshots in `data/prompt_eval/golden/`. Tests: section presence, ordering, no-duplication, golden drift.)_
- [~] [PROMPT_LLM_REVIEW_BENCH] _(2026-04-03: Static eval framework built. LLM-judged scoring designed but not yet implemented — needs OpenRouter integration for cost-effective evaluation. Framework ready in `prompt_quality_eval.py`.)_
- [x] [PROMPT_TASKSET_CURATION] _(2026-04-03: Created `data/prompt_eval/taskset.json` — 10 representative tasks across 9 work classes with expected_context_needs, failure_modes, and priority_sections per task.)_

---

## P2 — When Idle

### Spine Migration (continued)
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(2026-04-03: 5 canonical entries now. 3 remaining direct-python entries need new CLI subcommands. ~40 shell-script entries unchanged — those invoke bash orchestrators, not migration candidates.)_
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

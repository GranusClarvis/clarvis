# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat


---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.50. Current: semantic_cross_collection=0.575→0.589 (estimated). **v2 mirror strategy added** to `semantic_overlap_booster.py` (`--mirror` flag): copies actual docs between collections instead of templated bridges. All 4 pairs below 0.50 now above 0.50 (avg +0.08). Target 0.65 needs continued mirror runs on remaining weak pairs. _(in progress 2026-03-06)_

## Pillar 2: Agent Orchestrator (Multi-Project Command Center)

_Design: `docs/ORCHESTRATOR_PLAN_2026-03-06.md` — 5-phase rollout._

### Phase 1: Scoreboard + Trust (P0)

### Phase 2: Multi-Session Loop (P0)

### Phase 3: Cron Integration (P1)

### Phase 4: Enhanced Brain (P1)

### Phase 5: Visual Ops Dashboard (P1)
_Design informed by claw-empire visual deep dive (`docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`). Stack: Starlette SSE + vanilla JS + PixiJS 8._
  - Shows: current QUEUE tasks, active task being executed, recent evolution runs, subagents list + their current tasks/status, and PR/CI outcomes.
  - Style: 2D game-ish rooms/avatars (procedural PixiJS Graphics for rooms/furniture, emoji-based agents with status particles — same approach as claw-empire but simpler: 1 room, no CEO movement, no sub-clone fireworks).
  - Data sources: `memory/evolution/QUEUE.md`, `memory/cron/digest.md`, `memory/cron/autonomous.log`, `memory/cron/marathon.log`, `scripts/orchestration_scoreboard.py` outputs, `data/invariants_runs.jsonl`, GitHub PR list via `gh` (read-only).
  - 6 SSE event types: `task_started`, `task_completed`, `agent_status`, `queue_update`, `cron_activity`, `pr_update`.



### Steal List (from claw-empire review, P1)

### Deferred

## Pillar 3: Autonomous Execution (Success > 85%)


## Adaptive RAG Pipeline (Context Relevance > 0.90)

_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout based on CRAG/Self-RAG/Adaptive-RAG research._
_Dependency chain: GATE → EVAL → RETRY → FEEDBACK. Each phase is independently useful._

- [x] [RETRIEVAL_GATE] Build retrieval-needed classifier in `clarvis/brain/retrieval_gate.py`. Heuristic 3-tier routing: NO_RETRIEVAL (maintenance/cron tasks → skip brain.recall(), save ~7.5s), LIGHT_RETRIEVAL (scoped implementation → 2-3 collections, top-3), DEEP_RETRIEVAL (research/design/multi-hop → all collections, top-10, graph expansion). Wire into `heartbeat_preflight.py` §8 brain search. Store `retrieval_tier` in preflight JSON. Validate with dry-run on 5 sample tasks. Files: `clarvis/brain/retrieval_gate.py` (new), `scripts/heartbeat_preflight.py`. _(Done 2026-03-11: Gate built with keyword+tag heuristics, wired into preflight §7.8 before brain recall §8.5. NO_RETRIEVAL skips brain_preflight_context entirely. LIGHT reduces n_knowledge=3. DEEP enables n_knowledge=10+graph_expand. 5/5 sample tasks classified correctly.)_
- [ ] [RETRIEVAL_ADAPTIVE_RETRY] Add corrective retry loop to `clarvis/brain/retrieval_eval.py`. On INCORRECT verdict: (1) rewrite query via TF-IDF keyword extraction, (2) broaden to all 10 collections, (3) relax min_importance to 0.1. Max 1 retry per heartbeat. If retry still INCORRECT → skip context injection (no context > bad context). Wrap as `adaptive_recall(brain, query, tier)` called from preflight instead of raw `brain.recall()`. **Depends on**: [RETRIEVAL_EVAL]. Files: `clarvis/brain/retrieval_eval.py`, `scripts/heartbeat_preflight.py`.
- [ ] [RETRIEVAL_RL_FEEDBACK] Build RL-lite feedback loop in `clarvis/brain/retrieval_feedback.py`. In postflight: compare retrieval_verdict × task_outcome to compute reward signal. Track per-verdict success rate via EMA (alpha=0.1). Track context usefulness: count brief sections referenced in Claude Code output. Store in `data/retrieval_quality/retrieval_params.json`. Every 50 episodes, generate threshold adjustment suggestions to `param_suggestions.json` (human-reviewed before applying). **Depends on**: [RETRIEVAL_EVAL]. Files: `clarvis/brain/retrieval_feedback.py` (new), `scripts/heartbeat_postflight.py`, `data/retrieval_quality/`.
  - [ ] [TEST 2026-03-11] [RETRIEVAL_RL_FEEDBACK_1] Analyze: read files
  - [ ] [TEST 2026-03-11] [RETRIEVAL_RL_FEEDBACK_2] Implement: core change

## Research Sessions

- [x] [RESEARCH_DISCOVERY 2026-03-11] Research: MemOS — Memory Operating System for AI Agents (arXiv:2507.03724, MemTensor 2025). OS-level memory management treating memory as a first-class system resource. Core abstraction: MemCubes (content + metadata + provenance + versioning), composable/migratable/fusible across types. Three-layer architecture: Interface (API) → Operation (MemScheduler, memory layering, governance) → Infrastructure (storage). Key capabilities: lifecycle management (create/activate/fuse/dispose), multi-level permissions, context-aware activation, behavior-driven evolution. Distinct from mem0 (layer-only) and MemGPT (virtual context). **Completed**: 5 brain memories stored, research note at `memory/research/memos_memory_os_2026-03-11.md`. Key takeaways: MemCube metadata enrichment (add provenance + version chain), explicit lifecycle state machine, MemStore pub-sub for agent orchestrator, MemScheduler concept enhances RETRIEVAL_GATE design.

## Pillar 3: Performance & Reliability (PI > 0.70)

  - [ ] [GRAPH_STORAGE_UPGRADE_6] Cutover: `scripts/graph_cutover.py` implemented (archive JSON, enable SQLite, one-command rollback). Invariants gate (`invariants_check.py`) wired into cutover + safe migration. Docs updated (RUNBOOK.md Phase 4 section, ARCHITECTURE.md graph storage, CLAUDE.md). JSON write path removal deferred behind checklist (7-day soak prerequisite). Run `python3 scripts/graph_cutover.py` to execute. _(Phase 4 — cutover tooling done; soak now depends on sustained parity PASS under aligned gateway+cron SQLite dual-write before JSON write removal)_

### AGI-Readiness (from 2026-03-04 audit, see docs/AGI_READINESS_ARCHITECTURE_AUDIT.md)

  - **Done**: `clarvis/brain/factory.py` — `get_chroma_client(path)` (singleton per abs-path), `get_embedding_function(use_onnx)` (singleton ONNX model), `reset_singletons()` (test helper). Thread-safe with double-checked locking.
  - **Done**: ClarvisBrain wired (`__init__.py` lines 56, 126 → factory). LiteBrain wired (`lite_brain.py` lines 62-68, 82-86 → factory). Both embedding + client consolidated.
  - **Done**: 8 factory tests in `tests/test_clarvis_brain.py` — singleton identity, path isolation, collection consistency, embedding singleton, reset. All 87 tests pass.
  - **Done (Step 3)**: Test fixtures (`conftest.py` tmp_brain, `test_clarvis_brain.py` brain_instance) now use `get_chroma_client()` + `reset_singletons()` cleanup. No direct `chromadb.PersistentClient` in test fixtures. All 87 tests pass.
  - VectorStore (`packages/clarvis-db`) intentionally unchanged (standalone package, own lifecycle).

### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)

- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`. _(Audit done 2026-03-08: 103 scripts have `__main__`, 9 candidates for deprecation: `brain_eval_harness.py`, `clarvis_eyes.py`, `cost_per_task.py`, `graphrag_communities.py`, `local_vision_test.py`, `safety_check.py`, `screenshot_analyzer.py`. Excluded from list: `dashboard_server.py` (Phase 5 plan), `semantic_overlap_booster.py` (active QUEUE item). Moves blocked until CLI migration complete.)_

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop


## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

_Consolidated into Pillar 2 above. See `docs/ORCHESTRATOR_PLAN_2026-03-06.md` for full design._


## Backlog

- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Feasibility assessed 2026-03-09: `browser_agent.py` agent_task() already handles multi-step LLM-driven browser tasks with session persistence via browser-use. Remaining gaps: (1) credential management abstraction, (2) retry/error recovery wrapper, (3) task completion verification. Multi-session effort.

## Non-Code Improvements

- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. Hook registration exists in `clarvis/brain/hooks.py` and scoring path works end-to-end. Remaining: calibration of RETRIEVAL_TAU (memories with <3 accesses get clipped to floor score). (Phase 5 priority #10.)
- [ ] [RECONSIDER_GATE] Add mid-execution progress monitoring to heartbeat pipeline. If a spawned Claude Code task exceeds 50% of timeout with zero stdout to output file, surface a reconsideration flag. Enable graceful abort + task re-queue instead of hard timeout kill. Addresses cognitive Pattern 9 gap (Commitment & Reconsideration, Wray et al. 2505.07087). Files: `scripts/cron_autonomous.sh`, potentially new `scripts/execution_monitor.py`.
- [ ] [MEMORY_PROPOSAL_STAGE] Add two-stage memory commitment: `brain.propose(text, importance)` → evaluates utility (dedup check, relevance to active goals, storage cost) → `brain.commit(candidate_id)` to persist. Addresses Pattern 2 gap (Three-Stage Memory Commitment). Could reduce memory bloat by filtering low-utility memories pre-storage. Files: `clarvis/brain/__init__.py`.

## P1

- [ ] [RESEARCH_DISCOVERY 2026-03-10] Research: MacRAG — Multi-Scale Adaptive Context RAG (arXiv:2505.06569). Hierarchical compress→slice→scale-up framework for adaptive context construction. Offline: documents partitioned into overlapping chunks, compressed via summarization, then sliced for fine-grained indexing. Query-time: retrieve finest slices (precision), progressively scale up (coverage), merge neighbors + document-level expansion while controlling context size. Directly targets Context Relevance (0.838→0.90+). Has code: github.com/Leezekun/MacRAG. Map to context_compressor.py multi-scale retrieval pipeline. Sources: arxiv.org/abs/2505.06569
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling. _(Phase 1 done 2026-03-10: `pr_factory_rules.py` → `clarvis/orch/pr_rules.py`, `pr_factory_intake.py` → `clarvis/orch/pr_intake.py`, `pr_factory_indexes.py` → `clarvis/orch/pr_indexes.py`. Scripts converted to thin deprecated wrappers. 70/70 tests pass. Remaining: `pr_factory.py` (Phase 3 execution brief), `project_agent.py` (large, multi-session), `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine. _(2026-03-10: Audited 8 scripts. pr_factory_{rules,intake,indexes} already thin wrappers — updated 5 callers to import from canonical `clarvis.orch.*` directly. phi_metric.py already done. context_compressor.py blocked on `compress_health` migration. heartbeat_{pre,post}flight.py are canonical sources — inverted delegation, multi-session migration needed.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions. _(2026-03-10: First migration — `cron_reflection.sh` brain.py crosslink → `python3 -m clarvis brain crosslink`. Added `monthly_reflection` to cli_cron.py known jobs. Remaining: most cron script calls have no CLI parity yet — brain optimize is next candidate, then context_compressor gc.)_

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 85k+ graph edges. Target: improve complex query recall by providing related context automatically. **Depends on**: [GRAPH_STORAGE_UPGRADE] — indexed SQLite lookups make per-recall graph expansion feasible (<0.1ms vs 4ms per hop). (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)

## NEW ITEMS (2026-03-09 evolution session)

- [ ] [AMEM_MEMORY_EVOLUTION] Implement A-Mem style memory evolution (ROADMAP Phase 3 gap, 0% progress). When a memory is recalled and used in a successful episode, increment a `recall_success` counter in metadata and optionally refine the memory text with task-specific context. When contradicted or corrected, spawn a revised version with `evolved_from` linking to the original. Start minimal: metadata tracking + simple refinement trigger in `heartbeat_postflight.py`. Files: `clarvis/brain/__init__.py`, `scripts/heartbeat_postflight.py`, `scripts/episodic_memory.py`.

## NEW ITEMS (2026-03-08 evolution session)

- [ ] [CALIBRATION_BRIER_RECOVERY] Brier capability score degraded to 0.13 (was 0.082). Audit `clarvis_confidence.py` prediction history for miscalibrated domains — check whether recent predictions cluster in overconfident ranges or if outcome recording has gaps. Retune dynamic thresholds in `clarvis_confidence.py`. If Brier > 0.15 is due to stale/unresolved predictions, add a sweep to close them. Worst capability metric — directly blocks calibration quality. Files: `scripts/clarvis_confidence.py`, `scripts/prediction_review.py`, `data/predictions.jsonl`.
- [ ] [CONTEXT_ADAPTIVE_MMR_TUNING] Build adaptive MMR lambda tuning for `context_compressor.py`. Current static MMR lambda ignores task-type variance (research tasks need broader context, code tasks need precise context). After CONTEXT_RELEVANCE_FEEDBACK lands, use per-episode relevance scores to auto-adjust lambda per task category. Start with 3 categories: code (lambda=0.7), research (lambda=0.4), maintenance (lambda=0.6). Targets Context Relevance metric (currently 0.838, push toward 0.90). Files: `scripts/context_compressor.py`, `scripts/heartbeat_postflight.py`.
- [ ] [PARALLEL_BRAIN_RECALL] Implement parallel collection queries in `brain.py recall()` using `concurrent.futures.ThreadPoolExecutor`. Currently queries 10 collections sequentially (~250ms each = ~2.5s total). Parallel should reduce to ~300ms total (8x speedup). Guard with `CLARVIS_PARALLEL_RECALL=true` env var for safe rollout. ROADMAP P.2 Speed Optimization item with no queue task until now. Files: `clarvis/brain/__init__.py` (or `scripts/brain.py`), add benchmark comparison in `performance_benchmark.py`.

## NEW ITEMS (2026-03-06 evolution session)

- [ ] [CONTEXT_RELEVANCE_FEEDBACK] Add outcome-based context relevance tracking. Current metric (0.838) is a static proxy from `brief_v2_report.json` (v2/v1 success rate ratio). Fix: in `heartbeat_postflight.py`, after task completion, compare brief sections against Claude Code output to compute true relevance (referenced_sections / total_sections). Store per-episode. Weekly: regenerate `brief_v2_report.json` from episode data. Stretch: use feedback to auto-tune MMR lambda in `context_compressor.py`. Files: `scripts/heartbeat_postflight.py`, `scripts/context_compressor.py`, `scripts/performance_benchmark.py`.
- [ ] [BRIEF_BENCHMARK_REFRESH] The `data/benchmarks/brief_v2_report.json` driving context_relevance is stale. Create `scripts/brief_benchmark.py`: generate briefs for 10 known tasks with ground-truth expected content, score overlap (ROUGE-L or token intersection), update the report. Add monthly cron entry (1st of month, 03:45). This directly unblocks accurate context_relevance measurement. Files: `scripts/brief_benchmark.py`, `data/benchmarks/brief_v2_report.json`.

## NEW ITEMS (2026-03-05 evolution session)

- [ ] [INTRA_DENSITY_BOOST] Improve intra_collection_density from 0.38 → 0.55+. In `brain.py` or a new script, for each collection with density < 0.40, run pairwise similarity on stored memories and auto-link pairs with cosine > 0.65 as intra-collection graph edges. Currently only cross-collection edges exist (109k+), intra-collection linking is sparse. This is the lowest Phi sub-metric and directly blocks Phi > 0.80. Files: `scripts/brain.py`, `clarvis/brain/graph.py`.
- [ ] [ACTION_VERIFY_GATE] Add pre-execution action verification to `heartbeat_preflight.py`. Before committing a selected task to Claude Code, verify: (1) task description parses to concrete steps, (2) required files/scripts referenced in the task exist, (3) no conflicting lock held. Log verification result. Reject tasks that fail verification and fall through to next candidate. Targets action accuracy (0.968 → 0.98+) by preventing ill-defined tasks from consuming heartbeat slots. Draws on Process Reward Models research in queue.

## NEW ITEMS (2026-03-10 evolution session)

- [ ] [RETRIEVAL_EVAL_WIRING] Wire the already-built `clarvis/brain/retrieval_eval.py` into `scripts/heartbeat_preflight.py`. The evaluator (composite scoring: 50% semantic_sim + 25% keyword_overlap + 15% importance + 10% recency, with knowledge strip refinement on AMBIGUOUS batches) is complete but NOT called during task execution. This is the missing EVAL step in the Adaptive RAG dependency chain (GATE → **EVAL** → RETRY → FEEDBACK). After brain.recall() in preflight §8, call `evaluate_retrieval()` on the result batch. Store `retrieval_verdict` (CORRECT/AMBIGUOUS/INCORRECT) in preflight JSON. On INCORRECT, skip context injection. Quick win directly targeting Context Relevance (0.838 → 0.90). Files: `scripts/heartbeat_preflight.py`, `clarvis/brain/retrieval_eval.py`.
- [ ] [CONFIDENCE_TIERED_ENFORCEMENT] Implement tiered action levels (HIGH ≥0.8 / MEDIUM 0.5-0.8 / LOW 0.3-0.5 / UNKNOWN <0.3) enforcement in heartbeat pipeline. ROADMAP Phase 3.1 shows 70% progress with "not yet enforced" note. When confidence is LOW/UNKNOWN for a selected task, downgrade to dry-run mode (log what would be done, skip execution). Wire into `heartbeat_preflight.py` task selection after confidence scoring. Targets autonomous execution reliability. Files: `scripts/heartbeat_preflight.py`, `scripts/clarvis_confidence.py`.
- [ ] [CRON_SHELLCHECK_AUDIT] Run ShellCheck on the 8 cron orchestrator bash scripts (`cron_autonomous.sh`, `cron_morning.sh`, `cron_evolution.sh`, `cron_evening.sh`, `cron_reflection.sh`, `cron_research.sh`, `cron_implementation_sprint.sh`, `cron_research_discovery.sh`). Fix critical warnings: SC2086 (unquoted variables), SC2155 (declare+assign), SC2034 (unused vars), SC2162 (read without -r). Non-Python task that improves cron reliability and prevents subtle shell failures. Files: `scripts/cron_*.sh`.

## P1 — Added by Refactor Completion Audit (2026-03-05)


## P2 — Reclassified

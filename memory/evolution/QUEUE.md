# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat


---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)

- [~] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.50. Current: semantic_cross_collection=0.575→0.589 (estimated). **v2 mirror strategy added** to `semantic_overlap_booster.py` (`--mirror` flag): copies actual docs between collections instead of templated bridges. All 4 pairs below 0.50 now above 0.50 (avg +0.08). Target 0.65 needs continued mirror runs on remaining weak pairs. _(in progress 2026-03-06)_

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

  - [ ] [DASHBOARD_QUEUE_BLOCK_POPUP] Server endpoint to fetch the *full* QUEUE.md block for a given task (by tag+line), and show it in the modal on click.


### Steal List (from claw-empire review, P1)

### Deferred

## Pillar 3: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.
- [ ] [SUBAGENT_BRAIN_MATURATION_PHASE2_RECON] Strengthen recon/evidence generation so subagents identify likely files, symbols/routes, tests, current behavior, and risk notes before coding. Use this to improve prompt grounding and reduce drift.
- [ ] [SUBAGENT_BRAIN_MATURATION_PHASE3_FACTS] Upgrade atomic fact capture/writeback so reusable repo truths become denser and cleaner: exact invariants, routes, authz points, validated procedures, and useful gotchas with evidence pointers.
- [ ] [SUBAGENT_BRAIN_MATURATION_PHASE5_SECTOR] Formalize sector/product playbooks as a distinct retrieval layer derived from repo docs, linked to modules/invariants but separate from raw repo facts.
- [ ] [SUBAGENT_BRAIN_MATURATION_PHASE6_SOAK] Run a controlled soak/evaluation of the matured subagent brain + PR-factory pipeline across multiple real task classes (docs, feature, hardening, blocked task, test-heavy). Produce a trust/quality report.

## Research Sessions


## Pillar 3: Performance & Reliability (PI > 0.70)

  - [~] [GRAPH_STORAGE_UPGRADE_6] Cutover: `scripts/graph_cutover.py` implemented (archive JSON, enable SQLite, one-command rollback). Invariants gate (`invariants_check.py`) wired into cutover + safe migration. Docs updated (RUNBOOK.md Phase 4 section, ARCHITECTURE.md graph storage, CLAUDE.md). JSON write path removal deferred behind checklist (7-day soak prerequisite). Run `python3 scripts/graph_cutover.py` to execute. _(Phase 4 — cutover tooling done; soak now depends on sustained parity PASS under aligned gateway+cron SQLite dual-write before JSON write removal)_
  - [ ] [GRAPH_JSON_WRITE_REMOVAL] After soak completes + SQLite-only writes stable: remove legacy JSON write paths entirely (code cleanup). See RUNBOOK.md checklist; also update backups to include `graph.db`. _(blocked by soak completion)_

### AGI-Readiness (from 2026-03-04 audit, see docs/AGI_READINESS_ARCHITECTURE_AUDIT.md)

- [~] [CHROMADB_SINGLETON] Consolidate ChromaDB instantiation into single factory. Steps 1+2 done (2026-03-06):
  - **Done**: `clarvis/brain/factory.py` — `get_chroma_client(path)` (singleton per abs-path), `get_embedding_function(use_onnx)` (singleton ONNX model), `reset_singletons()` (test helper). Thread-safe with double-checked locking.
  - **Done**: ClarvisBrain wired (`__init__.py` lines 56, 126 → factory). LiteBrain wired (`lite_brain.py` lines 62-68, 82-86 → factory). Both embedding + client consolidated.
  - **Done**: 8 factory tests in `tests/test_clarvis_brain.py` — singleton identity, path isolation, collection consistency, embedding singleton, reset. All 87 tests pass.
  - **Remaining Step 3**: Wire test fixtures (`conftest.py`, `test_clarvis_brain.py` brain_instance) to use factory instead of direct `chromadb.PersistentClient`.
  - VectorStore (`packages/clarvis-db`) intentionally unchanged (standalone package, own lifecycle).

### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)

- [~] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. **BLOCKED: Requires Inverse decision.** Do not auto-select in marathon.
- [~] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`. _(Audit done 2026-03-08: 103 scripts have `__main__`, 9 candidates for deprecation: `brain_eval_harness.py`, `clarvis_eyes.py`, `cost_per_task.py`, `graphrag_communities.py`, `local_vision_test.py`, `safety_check.py`, `screenshot_analyzer.py`. Excluded from list: `dashboard_server.py` (Phase 5 plan), `semantic_overlap_booster.py` (active QUEUE item). Moves blocked until CLI migration complete.)_

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop


## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

_Consolidated into Pillar 2 above. See `docs/ORCHESTRATOR_PLAN_2026-03-06.md` for full design._

- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

## Backlog

- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. Hook registration exists in `clarvis/brain/hooks.py` and scoring path works end-to-end. Remaining: calibration of RETRIEVAL_TAU (memories with <3 accesses get clipped to floor score). (Phase 5 priority #10.)

## P1

- [ ] [OPENCLAW_FEATURE_ENABLEMENT_PLAN] From the OpenClaw deep review, turn the best features into an enablement plan: what can be used immediately, what needs config changes, what needs testing, and what should stay off.
- [ ] [OPENAI_SYMPHONY_RESEARCH] Research `openai/symphony` in depth.
  - What are the core architectural ideas?
  - Which parts are genuinely useful for Clarvis?
  - Which parts overlap with what we already built?
  - What should we steal for orchestrator / subagent PR factory / proof-of-work artifacts?
  - If not useful: say so and move on.
- [ ] [CLARVIS_CONTEXT_ENGINE_RESEARCH] Research how to design a Clarvis-specific context engine plugin on top of OpenClaw’s new context engine interface. Focus on aligning runtime context assembly/compaction with ClarvisDB (raw turns, compressed summaries with backreferences, graph-aware recall, evidence vs gap retrieval).
- [ ] [CLARVIS_CONTEXT_ENGINE_CONCEPT] Write a concept/design doc for a Clarvis context engine: goals, architecture, data flow, integration points, rollout plan, and how it complements—not replaces—ClarvisDB.
- [ ] [SPINE_MIGRATION_WAVE1_METRICS] Migrate core metrics logic from `scripts/` into `clarvis/metrics/` (phi metric, self-model, performance benchmark) with thin script wrappers only. Add smoke tests and CLI parity checks.
- [ ] [SPINE_MIGRATION_WAVE2_CONTEXT] Migrate core context assembly/compression logic from `scripts/` into `clarvis/context/` with thin wrappers. Define canonical context pipeline interfaces so future context-engine work has a clean home.
- [ ] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/` in phases (task routing, project-agent internals, shared PR-factory pipeline pieces). Preserve behavior; reduce direct script-to-script coupling.
- [ ] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. Prioritize scripts still carrying business logic that should live in the spine.
- [ ] [CRON_CANONICAL_ENTRYPOINTS] Gradually migrate cron/invocation paths from direct `python3 scripts/X.py` calls to canonical `python3 -m clarvis ...` entrypoints where parity exists. Use soak periods and diff checks to prevent regressions.
- [ ] [STRUCTURE_GATE_SUITE] Add a structural gate suite for Clarvis: compileall, import-health, spine smoke checks, key CLI smoke tests, and targeted pytest groups. Use it as the regression barrier during spine migration.
- [ ] [SELF_BOOT_AGENTS_DRIFT_CLEANUP] Clean and align core identity/runtime docs (`SELF.md`, `AGENTS.md`, `BOOT.md`) with current system reality (systemd, current brain stats/model/runtime, canonical commands). Remove stale references and migration drift.
- [ ] [UNWIRED_FEATURE_WIRING_PLAN] Audit built-but-unwired Clarvis capabilities (AZR, meta-learning, GraphRAG/community retrieval, failure amplifier, conversation learner, ACT-R wiring) and produce a ranked wiring plan: integrate, defer, or retire.
- [ ] [BRAIN_HYGIENE_AUTOMATION] Automate regular safe brain hygiene: node backfill, duplicate/noise cleanup review, health report snapshots, and alerting on graph inconsistencies or recall regressions.

  - Core ideas: markdown-as-source-code (program.md), fixed time-budget experiments, single-metric keep/discard loop, constraint architecture.
  - Useful for Clarvis: formal keep/discard loop for autonomous evolution, fixed time budgets for task comparison, constraint thinking for reliability.
  - Multi-agent finding: parallelism works, scientific judgment doesn’t — invest in upstream task selection, not execution mechanics.
  - Research note: `memory/research/karpathy_autoresearch.md`. 5 brain memories stored.
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 85k+ graph edges. Target: improve complex query recall by providing related context automatically. **Depends on**: [GRAPH_STORAGE_UPGRADE] — indexed SQLite lookups make per-recall graph expansion feasible (<0.1ms vs 4ms per hop). (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)

## NEW ITEMS (2026-03-08 evolution session)

- [ ] [CALIBRATION_BRIER_RECOVERY] Brier capability score degraded to 0.13 (was 0.082). Audit `clarvis_confidence.py` prediction history for miscalibrated domains — check whether recent predictions cluster in overconfident ranges or if outcome recording has gaps. Retune dynamic thresholds in `clarvis_confidence.py`. If Brier > 0.15 is due to stale/unresolved predictions, add a sweep to close them. Worst capability metric — directly blocks calibration quality. Files: `scripts/clarvis_confidence.py`, `scripts/prediction_review.py`, `data/predictions.jsonl`.
- [ ] [CONTEXT_ADAPTIVE_MMR_TUNING] Build adaptive MMR lambda tuning for `context_compressor.py`. Current static MMR lambda ignores task-type variance (research tasks need broader context, code tasks need precise context). After CONTEXT_RELEVANCE_FEEDBACK lands, use per-episode relevance scores to auto-adjust lambda per task category. Start with 3 categories: code (lambda=0.7), research (lambda=0.4), maintenance (lambda=0.6). Targets Context Relevance metric (currently 0.838, push toward 0.90). Files: `scripts/context_compressor.py`, `scripts/heartbeat_postflight.py`.
- [ ] [PARALLEL_BRAIN_RECALL] Implement parallel collection queries in `brain.py recall()` using `concurrent.futures.ThreadPoolExecutor`. Currently queries 10 collections sequentially (~250ms each = ~2.5s total). Parallel should reduce to ~300ms total (8x speedup). Guard with `CLARVIS_PARALLEL_RECALL=true` env var for safe rollout. ROADMAP P.2 Speed Optimization item with no queue task until now. Files: `clarvis/brain/__init__.py` (or `scripts/brain.py`), add benchmark comparison in `performance_benchmark.py`.
- [ ] [CONFIDENCE_TIERED_ACTIONS] Enforce tiered action levels from calibration data (ROADMAP Phase 3.1 gap — "not yet enforced"). In `heartbeat_preflight.py`, map confidence predictions to action tiers: HIGH (>0.8) → execute autonomously, MEDIUM (0.5-0.8) → execute with extra validation gate, LOW (<0.5) → skip or flag for manual review. Currently predictions exist but don't gate execution. Files: `scripts/heartbeat_preflight.py`, `scripts/clarvis_confidence.py`.
- [ ] [CRON_OUTPUT_QUALITY_AUDIT] Non-code: audit last 7 days of `memory/cron/autonomous.log` and `memory/cron/digest.md` entries. Identify: tasks that produce no useful output, repeated failures, cron slots wasted on low-value work, tasks selected but already completed. Produce a markdown summary at `docs/CRON_OUTPUT_AUDIT.md` with concrete recommendations (skip patterns, priority reweighting, time-slot adjustments). Shell + manual inspection only, no Python.

## NEW ITEMS (2026-03-06 evolution session)

- [ ] [CONTEXT_RELEVANCE_FEEDBACK] Add outcome-based context relevance tracking. Current metric (0.838) is a static proxy from `brief_v2_report.json` (v2/v1 success rate ratio). Fix: in `heartbeat_postflight.py`, after task completion, compare brief sections against Claude Code output to compute true relevance (referenced_sections / total_sections). Store per-episode. Weekly: regenerate `brief_v2_report.json` from episode data. Stretch: use feedback to auto-tune MMR lambda in `context_compressor.py`. Files: `scripts/heartbeat_postflight.py`, `scripts/context_compressor.py`, `scripts/performance_benchmark.py`.
- [ ] [BRIEF_BENCHMARK_REFRESH] The `data/benchmarks/brief_v2_report.json` driving context_relevance is stale. Create `scripts/brief_benchmark.py`: generate briefs for 10 known tasks with ground-truth expected content, score overlap (ROUGE-L or token intersection), update the report. Add monthly cron entry (1st of month, 03:45). This directly unblocks accurate context_relevance measurement. Files: `scripts/brief_benchmark.py`, `data/benchmarks/brief_v2_report.json`.
- [ ] [SPAWN_ADAPTIVE_TIMEOUT] Add task-category timeout to `scripts/spawn_claude.sh`: accept optional `--category` flag (quick=600s, standard=1200s, research=1800s, build=1800s). Default remains 1200s. Update `cron_research.sh` to pass `--category research`. Prevents research repo timeouts that waste cron slots (hermes-agent timed out at 1500s on 2026-03-06).
- [ ] [STALE_PLANS_ARCHIVE] Non-code: archive stale `data/plans/` files (cognition-architectures-report.md, helixir-analysis.md, hive-analysis.md, plan-20260219_232719.json) to `data/plans/archive/`. Keep only active plans. Update any references. Shell-only task, no Python.

## NEW ITEMS (2026-03-05 evolution session)

- [ ] [INTRA_DENSITY_BOOST] Improve intra_collection_density from 0.38 → 0.55+. In `brain.py` or a new script, for each collection with density < 0.40, run pairwise similarity on stored memories and auto-link pairs with cosine > 0.65 as intra-collection graph edges. Currently only cross-collection edges exist (109k+), intra-collection linking is sparse. This is the lowest Phi sub-metric and directly blocks Phi > 0.80. Files: `scripts/brain.py`, `clarvis/brain/graph.py`.
- [ ] [ACTION_VERIFY_GATE] Add pre-execution action verification to `heartbeat_preflight.py`. Before committing a selected task to Claude Code, verify: (1) task description parses to concrete steps, (2) required files/scripts referenced in the task exist, (3) no conflicting lock held. Log verification result. Reject tasks that fail verification and fall through to next candidate. Targets action accuracy (0.968 → 0.98+) by preventing ill-defined tasks from consuming heartbeat slots. Draws on Process Reward Models research in queue.
- [ ] [MONTHLY_REFLECTION_CRON] Automate monthly structural reflection (Phase 2 gap, marked "not yet automated" in ROADMAP.md). Create `scripts/cron_monthly_reflection.sh` — runs 1st of month at 03:30, spawns Claude Code to: analyze 30-day episode trends, identify structural script changes needed, propose ROADMAP updates, write output to `memory/cron/monthly_reflection_YYYY-MM.md`. Add crontab entry.
- [ ] [SKILL_INVENTORY_AUDIT] Non-code audit: check all 18 skills/ directories for (1) missing SKILL.md, (2) stale/broken tool references in skill config, (3) skills not referenced by any agent or cron job. Output a markdown table to `docs/SKILL_AUDIT.md` with status per skill (active/stale/undocumented). Identifies dead weight and documentation gaps. No Python required — shell + manual inspection.

## P1 — Added by Refactor Completion Audit (2026-03-05)


## P2 — Reclassified

- [ ] [CRON_AUTONOMOUS_BATCHING_CLEANUP] (was P0 CRON_AUTONOMOUS_BATCHING_BUG — reclassified after investigation: the `<<'PY'` heredoc + `NEXT_TASK` env var mechanism is correct, NOT a bug). Remaining cleanup: remove dead `is_subtask()` function (~lines 186-189), review `MAX_TOTAL_CHARS=900` limit. Low priority.
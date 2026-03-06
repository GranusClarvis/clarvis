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
- [ ] [ORCH_TRUST_SCORE] Add outcome-based trust scoring to `project_agent.py`: `trust_score` field in `agent.json`, adjustment table (pr_merged +0.05, task_failed -0.10, ci_broke_main -0.20, etc.), trust tiers (autonomous ≥0.80, supervised ≥0.50, restricted ≥0.20, suspended =0.00). Update trust post-spawn in `cmd_spawn()`.

### Phase 2: Multi-Session Loop (P0)
- [ ] [ORCH_DECOMPOSE] Add `decompose_task()` to `project_agent.py`: takes task string + agent context (procedures, repo structure), returns 1-5 subtask list with deps. Uses lite brain + `dependency_map.json` if available. Single-task fallback for simple tasks.
- [ ] [ORCH_TASK_LOOP] Add `run_task_loop()` and CLI command `project_agent.py loop <name> "<task>"`: plan→execute→verify→fix cycle per subtask, shared work branch, budget/session/timeout exit criteria, episode storage per subtask. See plan §3.2.
- [ ] [ORCH_CI_FEEDBACK] Add CI feedback loop: `_poll_ci_checks(pr_number, repo)` via `gh pr checks`, `_extract_ci_failure_logs()` via `gh api`, re-spawn agent with failure context (max 2 CI-fix attempts). Wire into `run_task_loop()` final phase.

### Phase 3: Cron Integration (P1)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_CRON_COEXIST] Add `is_cron_window_clear(minutes_needed)` to `project_agent.py`: reads system crontab, checks if any job scheduled within window. Create `scripts/cron_agent_loop.sh` for time-slotted agent execution between cron slots. Release global lock between loop sessions.

### Phase 4: Enhanced Brain (P1)
- [x] [ORCH_CI_CONTEXT] Add `build_ci_context()`: scan repo for test/build/lint commands from config files (package.json, Makefile, pyproject.toml), write `ci_context.json` per agent. Include in spawn prompt. _(done 2026-03-06: scans package.json/pyproject.toml/Makefile/.github/workflows, auto-refreshes on spawn, CLI `ci-context` command added)_
- [ ] [ORCH_DEP_MAP] Add `build_dependency_map()`: scan repo for entry points, config files, test dirs, key modules. Write `dependency_map.json` per agent. Feed into decomposer for smarter subtask splits.
- [ ] [ORCH_AUTO_GOLDEN_QA] After successful tasks, auto-generate 1-2 golden QA pairs from task context. Deduplicate (cosine < 0.85), cap at 50 per agent. Run `benchmark_retrieval()` weekly via cron.

### Deferred
- [ ] [ORCH_AGENT_PROTOCOLS] Implement basic agent interoperability layer: define a simple internal A2A-ish message schema for project agents (task brief → structured result JSON), and enforce it in project_agent.py outputs.

## Pillar 3: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze it with local vision (Qwen3-VL), extract structured info (page type, main elements, interactive components). Measure: extraction accuracy vs manual ground truth.
- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.

## Research Sessions

- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)

  - [~] [GRAPH_STORAGE_UPGRADE_6] Cutover: `scripts/graph_cutover.py` implemented (archive JSON, enable SQLite, one-command rollback). Invariants gate (`invariants_check.py`) wired into cutover + safe migration. Docs updated (RUNBOOK.md Phase 4 section, ARCHITECTURE.md graph storage, CLAUDE.md). JSON write path removal deferred behind checklist (7-day soak prerequisite). Run `python3 scripts/graph_cutover.py` to execute. _(Phase 4 — cutover tooling done, awaiting soak period to execute + remove JSON writes)_
  - [ ] [GRAPH_SOAK_5DAY] Execute 5-day SQLite soak (dual-write enabled): (1) Ensure `scripts/cron_env.sh` exports `CLARVIS_GRAPH_BACKEND=sqlite` and `CLARVIS_GRAPH_DUAL_WRITE=1`. (2) Monitor daily: `tail -20 memory/cron/graph_verify.log` — cron_graph_verify.sh runs at 04:45 UTC. (3) Run `python3 scripts/invariants_check.py` periodically. (4) After **5 consecutive PASS days**, the soak manager will automatically flip `CLARVIS_GRAPH_DUAL_WRITE=0` (SQLite-only writes). Soak start date: _(auto-tracked in data/graph_soak_state.json)_.
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
- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`.
- [ ] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist.

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop

- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.

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

- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Runtime Verification & Metacognitive Self-Correction for Agents — MASC (step-level anomaly detection via next-execution reconstruction, ICLR 2026), AgentSpec (DSL for runtime constraint enforcement, 90%+ unsafe action prevention, ICSE 2026), AgentGuard (dynamic probabilistic assurance), SupervisorAgent (agent interaction monitoring). Improves action accuracy through real-time execution guards and self-correction loops. Sources: arxiv.org/abs/2510.14319, arxiv.org/abs/2503.18666, arxiv.org/abs/2509.23864, arxiv.org/abs/2510.26585
- [ ] [RESEARCH_DISCOVERY 2026-03-05] Research: Process Reward Models for Agent Step Verification — ThinkPRM (generative CoT verification, 1% labels, +8% OOD), ToolPRMBench (tool-use PRM evaluation), Critical Step Optimization (verified decision-point preference learning), AgentPRM (actor-critic Monte Carlo). Directly improves action accuracy via step-level error detection before execution commits. Sources: arxiv.org/abs/2504.16828, arxiv.org/abs/2601.12294, arxiv.org/abs/2602.03412, arxiv.org/abs/2502.10325
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 85k+ graph edges. Target: improve complex query recall by providing related context automatically. **Depends on**: [GRAPH_STORAGE_UPGRADE] — indexed SQLite lookups make per-recall graph expansion feasible (<0.1ms vs 4ms per hop). (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)

## NEW ITEMS (2026-03-05 evolution session)

- [ ] [INTRA_DENSITY_BOOST] Improve intra_collection_density from 0.38 → 0.55+. In `brain.py` or a new script, for each collection with density < 0.40, run pairwise similarity on stored memories and auto-link pairs with cosine > 0.65 as intra-collection graph edges. Currently only cross-collection edges exist (109k+), intra-collection linking is sparse. This is the lowest Phi sub-metric and directly blocks Phi > 0.80. Files: `scripts/brain.py`, `clarvis/brain/graph.py`.
- [ ] [ACTION_VERIFY_GATE] Add pre-execution action verification to `heartbeat_preflight.py`. Before committing a selected task to Claude Code, verify: (1) task description parses to concrete steps, (2) required files/scripts referenced in the task exist, (3) no conflicting lock held. Log verification result. Reject tasks that fail verification and fall through to next candidate. Targets action accuracy (0.968 → 0.98+) by preventing ill-defined tasks from consuming heartbeat slots. Draws on Process Reward Models research in queue.
- [ ] [MONTHLY_REFLECTION_CRON] Automate monthly structural reflection (Phase 2 gap, marked "not yet automated" in ROADMAP.md). Create `scripts/cron_monthly_reflection.sh` — runs 1st of month at 03:30, spawns Claude Code to: analyze 30-day episode trends, identify structural script changes needed, propose ROADMAP updates, write output to `memory/cron/monthly_reflection_YYYY-MM.md`. Add crontab entry.
- [ ] [SKILL_INVENTORY_AUDIT] Non-code audit: check all 18 skills/ directories for (1) missing SKILL.md, (2) stale/broken tool references in skill config, (3) skills not referenced by any agent or cron job. Output a markdown table to `docs/SKILL_AUDIT.md` with status per skill (active/stale/undocumented). Identifies dead weight and documentation gaps. No Python required — shell + manual inspection.

## P1 — Added by Refactor Completion Audit (2026-03-05)


## P2 — Reclassified

- [ ] [CRON_AUTONOMOUS_BATCHING_CLEANUP] (was P0 CRON_AUTONOMOUS_BATCHING_BUG — reclassified after investigation: the `<<'PY'` heredoc + `NEXT_TASK` env var mechanism is correct, NOT a bug). Remaining cleanup: remove dead `is_subtask()` function (~lines 186-189), review `MAX_TOTAL_CHARS=900` limit. Low priority.
# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

- [x] [DOCS_STRUCTURE] Establish docs structure: `docs/ARCHITECTURE.md` (layers + boundaries), `docs/CONVENTIONS.md`, `docs/DATA_LAYOUT.md`, `docs/RUNBOOK.md`. ✅ ARCHITECTURE.md rewritten 2026-03-04 (CONVENTIONS/DATA_LAYOUT/RUNBOOK already existed)
- [x] [PYTEST_COLLECTION_HYGIENE] Fix global `pytest` collection — deprecated tests under `scripts/deprecated/` caused collection errors. Added `testpaths`/`norecursedirs` to `pyproject.toml`. Fixed 15 broken tests (brain fixture missing `_recall_cache`, heartbeat adapter count, spotlight mock target). Gate updated to include `test_pipeline_integration.py`. ✅ DONE 2026-03-04
- [x] [CRON_LOCK_HELPER] Extract `scripts/lock_helper.sh` — shared functions for local/global/maintenance locks. ✅ DONE 2026-03-04
- [x] [METRICS_SELF_MODEL] Populate `clarvis/metrics/` — move `scripts/self_model.py` core classes into `clarvis/metrics/self_model.py`. ✅ DONE 2026-03-04
- [x] [ORCH_TASK_SELECTOR] Populate `clarvis/orch/` — move `scripts/task_selector.py` scoring logic into `clarvis/orch/task_selector.py`. ✅ DONE 2026-03-04

---

## Pillar 1: Consciousness & Integration (Phi > 0.80)

(Constraint: pursue only where it improves the brain’s practical intelligence — retrieval quality, correct integration, planning reliability.)

- [ ] [SEMANTIC_BRIDGE] Build semantic overlap booster for cross-collection pairs with overlap <0.40. Target: raise semantic_cross_collection from 0.477 to 0.55+.

## Pillar 2: Autonomous Execution (Success > 85%)

- [ ] [AUTONOMY_LOGIN] Given credentials in .env, log into a web service and verify logged-in state (session cookie present, profile page accessible). User provides credentials manually.
- [ ] [AUTONOMY_POST] Given credentials + a platform (e.g. GitHub Issues via API, or a forum), compose and post a message autonomously. Measure: post appears, content matches intent.
- [ ] [AUTONOMY_SCREENSHOT_ANALYZE] Take a screenshot of any given URL, analyze it with local vision (Qwen3-VL), extract structured info (page type, main elements, interactive components). Measure: extraction accuracy vs manual ground truth.
- [ ] [AUTONOMY_MULTI_STEP] Multi-step workflow benchmark — given a sequence of 3+ actions (navigate → search → click result → extract data), complete the full chain. Measure: step completion rate, total success.

## Research Sessions

- [ ] [BROWSER_SKILL_DOC] Create skills/web-browse/SKILL.md documenting browser_agent.py capabilities for M2.5.

## Pillar 3: Performance & Reliability (PI > 0.70)

### CLI Migration (see docs/CLI_MIGRATION_PLAN.md)

- [ ] [CLI_BRAIN_LIVE] Verify `clarvis brain health` output matches `python3 scripts/brain.py health` exactly. Fix any discrepancies. Run both and diff.
- [ ] [CLI_DOCS_UPDATE] After 30-day soak: update CLAUDE.md, RUNBOOK.md, AGENTS.md to reference `clarvis` CLI. Remove old `python3 scripts/brain.py` examples.
- [ ] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. Requires Inverse decision.
- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`.
- [ ] [CLI_BENCH_EXPAND] Add missing bench subcommands: `record`, `trend [days]`, `check` (exit 1 on failures), `heartbeat` (quick check), `weakest` (weakest metric). All delegate to `scripts/performance_benchmark.py`.
- [ ] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist.
- [ ] [CLI_ROOT_PYPROJECT] Create root `pyproject.toml` for the `clarvis` package (if not already present). Define `[project.scripts] clarvis = "clarvis.cli:main"`, set `packages = ["clarvis"]`, pin deps. Prerequisite for CLI_CONSOLE_SCRIPT.

### Codebase Restructuring (see docs/ARCHITECTURE.md)
(Primary: now tracked in P0.)

## Pillar 4: Self-Improvement Loop

- [ ] [NOVELTY_TASK_SCORING] Novelty-weighted task selection — compute embedding distance between candidate tasks and last N completed tasks, boost high-novelty tasks with `final_score = base_score * (1 + 0.3 * novelty)`. Prevents "more of the same" trap. Files: task_selector.py (or heartbeat_preflight.py scoring section).
- [ ] [PREFLIGHT_SPEED] Optimize preflight overhead (currently ~100s). Profile task_selector scoring loop — brain lookups for failure penalties on every task is the bottleneck.

## Pillar 5: Agent Orchestrator (Multi-Project Command Center)

### Milestone 1: First PR Pipeline (target: this week)

### Milestone 2: Cron + Cost (target: next week)
- [ ] [ORCH_CRON_INTEGRATION] Add daily cron: `project_agent.py promote` + `orchestration_benchmark.py run` for active agents.
- [ ] [ORCH_SUDO_OPT] Request sudo: `sudo mkdir -p /opt/clarvis-agents && sudo chown agent:agent /opt/clarvis-agents`, then `project_agent.py migrate star-world-order`.

### Milestone 3: Multi-Agent (target: 2 weeks)

## Backlog

- [ ] [UNWIRED_AZR] Wire `absolute_zero.py` into weekly cron (self-play reasoning session). Currently CLI-only, never automatically exercised.
- [x] [UNWIRED_META_LEARNING] Wire `meta_learning.py` into postflight or weekly cron — learning strategy analysis never runs automatically. ✅ DONE 2026-03-04 (wired into postflight hook, priority 90, daily rate limit)
- [x] [UNWIRED_GRAPHRAG] Wire `graphrag_communities.py` into brain.recall() or periodic cron — community detection would improve retrieval quality. ✅ DONE 2026-03-04 (graphrag booster hook, toggled via CLARVIS_GRAPHRAG_BOOST=1)
- [ ] [CLI_COST_SUBCOMMAND] Add `clarvis cost daily/budget` subcommands — cost tracking not in unified CLI.
- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [ ] [CONFIDENCE_RECALIBRATION] Fix overconfidence at 90% level (70% actual accuracy). In `clarvis_confidence.py`, add confidence band analysis to `predict()`: if historical accuracy for band 0.85-0.95 is <80%, auto-downgrade new predictions in that band by 0.10. Log adjustments. Target: Brier score 0.12→0.20+ in system health ranking.
- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. Longest-stalled item. Hook registration exists in `clarvis/brain/hooks.py` but scoring path needs testing + calibration. Target: recently-accessed memories get retrieval boost, old unused memories decay. (Phase 5 priority #10.)

## P1

- [x] [METRICS_PERF_BENCHMARK] Move PI computation from `scripts/performance_benchmark.py` (1,535L) into `clarvis/metrics/benchmark.py`. Core: 8-dimension scoring, composite PI calculation, self-optimization triggers. Keep CLI as thin wrapper. Enables `clarvis bench` to use spine directly. (Phase 5 — metrics spine completion.) ✅ DONE 2026-03-04
- [x] [ORCH_TASK_ROUTER] Move `scripts/task_router.py` complexity scoring + model routing into `clarvis/orch/router.py`. Export `classify_task()`, `route_to_model()`, `get_tier_config()`. Thin wrapper in scripts/. (Phase 5 — orch spine completion.) ✅ DONE 2026-03-04
- [x] [GRAPHRAG_RECALL_BOOST] Wire `graphrag_communities.py` into `brain.recall()` — after ChromaDB vector search, optionally expand results with intra-community neighbors. Directly improves retrieval quality (PI weight 0.18). (Phase 5 — existing module, never exercised in recall path.) ✅ DONE 2026-03-04
- [x] [HEBBIAN_EDGE_DECAY] Add age-based Hebbian edge pruning to `clarvis/brain/graph.py`: `decay_edges(half_life_days, prune_below)`. Exponential decay + prune. CLI: `clarvis brain edge-decay`. (Phase 5 — graph sustainability.) ✅ DONE 2026-03-04
- [x] [META_LEARNING_WIRE] Wire `meta_learning.py analyze` into postflight hook (priority 90, daily rate limit). Closes the "learn how to learn" feedback loop. (Phase 5 — now auto-exercised via heartbeat.) ✅ DONE 2026-03-04
- [x] [PIPELINE_INTEGRATION_TEST] Create `tests/test_pipeline_integration.py`: 25 tests covering router, edge decay, graphrag booster, pipeline flow, hook lifecycle. (Phase 5.) ✅ DONE 2026-03-04
- [ ] [FAILURE_TAXONOMY] Add error type classification to `heartbeat_postflight.py` failure handling. When a task fails, classify the error into one of 5 categories (memory/planning/action/system/timeout) using keyword matching on output. Store as `error_type` tag in episode metadata alongside existing "failure" tag. Enables failure pattern analysis across heartbeats. (Extracted from: AgentDebug research, arXiv:2509.25370)
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 47k+ graph edges. Target: improve complex query recall by providing related context automatically. (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)
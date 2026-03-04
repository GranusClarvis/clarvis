# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — Do Next Heartbeat

- [x] [HEARTBEAT_INIT_EXPORT_FIX] ~~Fix `clarvis/heartbeat/__init__.py` — add `HookRegistry` to exports~~ DONE (2026-03-04).
- [x] [BOOT_MD_FIX] Fixed deprecated `from clarvis_memory import clarvis_context` → `from clarvis.brain import brain, search, remember, capture`. DONE (2026-03-04).
- [x] [SELF_MD_UPDATE] Updated SELF.md: PM2→systemd, brain stats 42/7→2000+/10, process chain updated. DONE (2026-03-04).
- [ ] [DOCS_STRUCTURE] Establish docs structure: `docs/ARCHITECTURE.md` (layers + boundaries), `docs/CONVENTIONS.md` (imports/sys.path, logging, CLI patterns), `docs/DATA_LAYOUT.md` (what goes in memory/, data/, logs/, tmp/), `docs/RUNBOOK.md` (how to run heartbeats, benchmarks, restore backups).
- [x] [DEAD_CODE_AUDIT] Built `scripts/dead_code_audit.py`: scans crontab, imports, cron .sh wrappers, docs, skills, configs, spine. 85/89 exercised, 3 candidates. DONE (2026-03-04).

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

- [x] [CLI_CONSOLE_SCRIPT] Added `[project.scripts] clarvis = "clarvis.cli:main"` to `pyproject.toml`, `pip install -e .` confirmed, `clarvis --help` works from any directory. DONE (2026-03-04).
- [x] [CLI_TESTS] Wrote `tests/test_cli.py` — 9 tests: `--help` for all subcommands + real invocations (`brain stats`, `queue status`, `bench pi`, `heartbeat gate`). All pass. DONE (2026-03-04).
- [ ] [CLI_BRAIN_LIVE] Verify `clarvis brain health` output matches `python3 scripts/brain.py health` exactly. Fix any discrepancies. Run both and diff.
- [x] [CLI_CRON_SUBCOMMAND] Added `clarvis cron list|status|run <job>` with `--dry-run`. Wraps existing cron_*.sh scripts. DONE (2026-03-04).
- [ ] [CLI_CRON_PILOT] Migrate 1 cron entry (`cron_reflection.sh`) to `clarvis cron run reflection`. Pilot instructions in docs/RUNBOOK.md §13. Awaiting Inverse approval to edit crontab. Soak 7 days after activation.
- [x] [CLI_DEPRECATION_WARNINGS] Added stderr deprecation warnings to `scripts/brain.py`, `scripts/performance_benchmark.py`, `scripts/queue_writer.py` `__main__` blocks. DONE (2026-03-04).
- [ ] [CLI_DOCS_UPDATE] After 30-day soak: update CLAUDE.md, RUNBOOK.md, AGENTS.md to reference `clarvis` CLI. Remove old `python3 scripts/brain.py` examples.
- [ ] [CLI_SUBPKG_ABSORB] Evaluate absorbing `clarvis-db`, `clarvis-cost`, `clarvis-reasoning` CLIs into unified `clarvis db|cost|reasoning` subcommands. Requires Inverse decision.
- [ ] [CLI_DEAD_SCRIPT_SWEEP] After CLI migration complete: audit which scripts/ `__main__` blocks have zero callers. Move to `scripts/deprecated/`.
- [ ] [CLI_BENCH_EXPAND] Add missing bench subcommands: `record`, `trend [days]`, `check` (exit 1 on failures), `heartbeat` (quick check), `weakest` (weakest metric). All delegate to `scripts/performance_benchmark.py`.
- [ ] [CLI_HEARTBEAT_EXPAND] Add `clarvis heartbeat preflight` (run preflight only, print JSON) and `clarvis heartbeat postflight` (accepts exit-code + output-file + preflight-file args). Currently only `run` and `gate` exist.
- [ ] [CLI_BOOT_DRIFT] Audit AGENTS.md and BOOT.md for references to `scripts/deprecated/` or moved scripts. Update to use `clarvis` CLI or correct spine import paths.
- [ ] [CLI_ROOT_PYPROJECT] Create root `pyproject.toml` for the `clarvis` package (if not already present). Define `[project.scripts] clarvis = "clarvis.cli:main"`, set `packages = ["clarvis"]`, pin deps. Prerequisite for CLI_CONSOLE_SCRIPT.
- [x] [CLI_CRON_STUB] Subsumed by CLI_CRON_SUBCOMMAND — `clarvis/cli_cron.py` includes list + status + run. DONE (2026-03-04).

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
- [ ] [UNWIRED_META_LEARNING] Wire `meta_learning.py` into postflight or weekly cron — learning strategy analysis never runs automatically.
- [ ] [UNWIRED_GRAPHRAG] Wire `graphrag_communities.py` into brain.recall() or periodic cron — community detection would improve retrieval quality.
- [ ] [CLI_COST_SUBCOMMAND] Add `clarvis cost daily/budget` subcommands — cost tracking not in unified CLI.
- [ ] [CRAWL4AI] Install Crawl4AI for automated research ingestion.
- [ ] [BROWSER_TEST] Test: navigate, extract, fill forms, multi-step workflows — comprehensive browser-use capability validation.
- [ ] [VISION_FALLBACK] Add local vision fallback to clarvis_eyes.py — use Ollama when API vision unavailable.
- [ ] [GITHUB_API_TASKS] Given existing GitHub credentials, perform repo management via API: create issues, comment on PRs, read notifications, manage labels. No account creation — user provides PAT.
- [ ] [AUTONOMY_SEARCH] Web search benchmark — given a question, use browser to search, evaluate results, extract answer. Compare with WebSearch tool accuracy.
- [ ] [UNIVERSAL_WEB_AGENT] Any webapp operated via natural language — given credentials and a task description, complete it. Requires session persistence + multi-step + error recovery.

## Non-Code Improvements

- [ ] [CONFIDENCE_RECALIBRATION] Fix overconfidence at 90% level (70% actual accuracy). In `clarvis_confidence.py`, add confidence band analysis to `predict()`: if historical accuracy for band 0.85-0.95 is <80%, auto-downgrade new predictions in that band by 0.10. Log adjustments. Target: Brier score 0.12→0.20+ in system health ranking.
- [ ] [ACTR_WIRING] Wire `actr_activation.py` into `brain.py` recall path — add power-law decay scoring as a re-ranking factor after ChromaDB vector search. This has been "pending" since Phase 2 and is the single longest-stalled item. Target: memories accessed recently get retrieval boost, old unused memories decay naturally.

## P1

- [ ] [FAILURE_TAXONOMY] Add error type classification to `heartbeat_postflight.py` failure handling. When a task fails, classify the error into one of 5 categories (memory/planning/action/system/timeout) using keyword matching on output. Store as `error_type` tag in episode metadata alongside existing "failure" tag. Enables failure pattern analysis across heartbeats. (Extracted from: AgentDebug research, arXiv:2509.25370)
- [ ] [RECALL_GRAPH_CONTEXT] In `brain.py` recall/search methods, optionally expand results with 1-hop graph neighbors. When a memory is retrieved, also fetch memories connected via existing graph edges and include them as lower-weight "context" entries. No new clustering needed — uses existing 47k+ graph edges. Target: improve complex query recall by providing related context automatically. (Extracted from: RAPTOR/Hierarchical RAG research, arXiv:2401.18059)
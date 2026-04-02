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

### March 24 audit note
_Queue audited on 2026-03-24 evening. Removed 3 completed items (A5_A7, TEMPORAL_RETRIEVAL_FIX, BACKFILL_SENTINEL_FIX). Demoted 2 items (postflight import cleanup, semantic bridges) to P1 — functional via bridges, not release-blocking. 7 items remain on the critical path._

### Milestone C — Repo / Open-Source Readiness (by 2026-03-26) ✅ COMPLETE

### Milestone D — Public Surface (by 2026-03-29)

### Milestone E — Final Validation (by 2026-03-31)


---

## P1 — This Week














### Demoted from P0 (2026-03-24 audit)

### Episode Success Rate Hardening

### Code Quality

### Phi / Benchmarking

---

## P2 — When Idle (Demoted 2026-03-17)

### Spine Migration
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Remaining: `pr_factory.py`, `project_agent.py`, `agent_orchestrator.py`, benchmarks/scoreboard.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-03-10: 3 scripts wrapped. Remaining: context_compressor, heartbeat_{pre,post}flight.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(3 done. Next: context_compressor gc.)_

### Code Quality

### Agent Orchestrator
- Pillar 2 Phase 5 — Visual Ops Dashboard _(PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.)_

### Benchmarking
- CLR Benchmark implementation from fork: `clarvis/metrics/clr.py` (672 lines, schema v1.0 frozen, 6 dimensions).
- A/B Comparison Benchmark: fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.

### Adaptive RAG Pipeline
_Design: `docs/ADAPTIVE_RAG_PLAN.md` — 4-phase rollout (GATE → EVAL → RETRY → FEEDBACK). Each phase independently useful. Demoted: not needed for 2026-03-31 delivery._

### Research Sessions
_(Completed items archived.)_

---

## NEW ITEMS

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:bench-latency-01] Profile and optimize the 3 slowest brain operations end-to-end — Use cProfile to profile the top 3 slowest brain operations (likely: store with graph update, multi-collection search, batch decay). For each, create a flamegraph-style report, identify the bottleneck,

- [ ] [EXTERNAL_CHALLENGE:research-impl-03] Implement a simple MemoryBank with forgetting curve (Ebbinghaus) — Build a memory bank that models Ebbinghaus forgetting curves. Each memory has a retention strength that decays exponentially. Implement spaced repetition: memories that are recalled get strength boost







### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan

### P0 — Found in 2026-04-02 evening code review

### P1 — Found in 2026-04-02 quality audit
- [x] [GRAPHRAG_BOOST_VALUE_FIX] Fix `.env.example` CLARVIS_GRAPHRAG_BOOST=1.0 → CLARVIS_GRAPHRAG_BOOST=1 (code checks `!= "1"`, float string silently breaks). Also remove dead OLLAMA_KEEP_ALIVE entry (no script references it).
- [ ] [SCORE_EVIDENCE_UNIT_TEST] Add dedicated unit test for `score_evidence()` in `clarvis/brain/retrieval_eval.py` — currently only tested indirectly via adaptive_recall integration path.
- [ ] [ATTENTION_VISUALIZER_TESTS] Add basic unit tests for `scripts/attention_visualizer.py` — tokenization, ONNX inference, score normalization, HTML generation.
- [ ] [CONTEXT_COMPRESSOR_DEDUP] Deduplicate keyword-pinning and per-category ratio logic between `scripts/context_compressor.py` and `clarvis/context/compressor.py` — both have identical implementations that will diverge. Extract shared logic or make scripts/ a thin wrapper.

### Open-Source Readiness — Fresh-Clone Install Audit (2026-04-01)
_Source: Fresh-user perspective audit of clone → install → understand → run path._

#### Completed (2026-04-01)

#### Remaining — P1
- [x] [OSR_DOCKER_QUICKSTART] Create a minimal `Dockerfile` + `docker-compose.yml` for contributors who want to try Clarvis without setting up a dedicated host. Should run brain health, CLI, and tests. Not for production (production is systemd-native).
- [x] [OSR_PYPI_PUBLISH_PREP] Prepare sub-packages for PyPI publication: add CHANGELOG.md to each, verify `python -m build` produces clean wheels, test `pip install` from wheel (not editable) works.
- [x] [OSR_QUICK_DEMO_MODE] Add a `python3 -m clarvis demo` command that runs a self-contained demo (store → search → recall → heartbeat gate) without needing existing data. Good for README walkthroughs and conference demos.

#### Follow-up — P2
- [ ] [OSR_PYPI_CHANGELOGS] Add CHANGELOG.md to each sub-package before first PyPI publish.
- [ ] [OSR_DOCKER_CI] Wire Docker build into CI workflow to catch packaging regressions.

### Session Persistence Implementation (from HARNESS_SESSION_PERSISTENCE research, 2026-04-01)
- [ ] [SESSION_TRANSCRIPT_LOGGER] Add JSONL transcript persistence to heartbeat_postflight.py: append metadata to `data/session_transcripts/YYYY-MM-DD.jsonl`, save raw output to `data/session_transcripts/raw/`, add gzip rotation to cron_cleanup.sh (compress >7d, delete >90d).
- [ ] [CONVERSATION_LEARNER_UPGRADE] Upgrade conversation_learner.py to ingest full session transcripts from `data/session_transcripts/` instead of 200-char snippets from `memory/*.md`. Enable pattern extraction from complete tool-use sequences and prompt-outcome pairs.

### Claude Harness Research Program (2026-03-31)
_Source: `data/external_src/claude-harness-src.zip`. Deep-dive note: `memory/research/claude_harness_architecture_2026-03-31.md`._

#### Architecture & Runtime

#### Memory & State

#### Orchestration & Multi-Agent
- [ ] [HARNESS_TASK_BUDGET_STOPPING] Study token budget tracking and diminishing-returns detection (`tokenBudget.ts` — 90% threshold OR <500 tokens/iteration after 3+ loops). Replace fixed timeouts in `spawn_claude.sh` and cron orchestrators with budget-aware stopping. Prototype: parse Claude Code output for token usage, implement early termination.

#### Hooks & Extensibility
- [ ] [HARNESS_HOOK_SYSTEM] Study the 14+ lifecycle hook events (PreToolUse, PostToolUse, PermissionRequest, SessionStart/End, etc.) and their execution model (shell/HTTP/callback, exit code semantics). Design a hook system for Clarvis brain operations: pre/post-search hooks for cost tracking, pre/post-remember hooks for quality gates, session lifecycle hooks for episodic capture.

#### Context & Compaction
- [ ] [HARNESS_GRADUATED_COMPACTION] Study the 4-tier compaction strategy (microcompact → context collapse → history snip → full autocompact) in `query.ts` and `compact.ts`. Design a graduated compaction pipeline for Clarvis context_compressor that preserves more information at lower tiers before falling back to full LLM summarization.

#### Safety & Sandboxing
- [ ] [HARNESS_SANDBOX_MODEL] Study `@anthropic-ai/sandbox-runtime` adapter (`sandbox-adapter.ts`) — file read/write patterns, network domain allow/deny, process exclusion lists. Evaluate feasibility of sandboxing Claude Code spawns in our cron pipeline beyond the current lockfile model. Assess: can we restrict file writes to `workspace/` only?

#### UX & Portability
- [ ] [HARNESS_DREAM_DISTILLATION] Study the Dream task (4-stage session-log distillation into structured memory files). Compare against our `dream_engine.py` (counterfactual dreaming). Prototype a "session distillation" nightly job that reviews cron session outputs and distills actionable learnings into brain, complementing the existing counterfactual approach.
- [ ] [HARNESS_BRIDGE_TRANSPORT] Study the bridge module's hybrid transport (WebSocket reads + HTTP POST writes in `HybridTransport.ts`) and remote control protocol (`bridgeApi.ts`, `bridgeMain.ts`). Evaluate feasibility of a Clarvis remote-control interface accessible from Telegram or web, allowing live session observation and intervention beyond current `/spawn` one-shot model.

### Bloat & Dead-Code Reduction (2026-04-01 scan)
_Source: System gap scan — bloat score at 0.400 threshold, 72 unused scripts identified._

- [x] [DEAD_SCRIPT_AUDIT_AND_PURGE] _(Completed 2026-04-02)_ Deep audit of all 195 scripts. 10 confirmed dead removed: `attention_visualizer.py`, `backfill_created_epoch.py`, `bench_context_utilization.py`, `brain_research_dedupe.py`, `cron_error_aggregator.sh`, `cron_graph_soak_manager.sh`, `generate_status_page.py`, `oss_readiness_check.sh`, `priorities_curator.py`, `research_crawler.py`. 17 initially flagged scripts were found to be actively imported by heartbeat pipeline — kept.
- [x] [STALE_DATA_CLEANUP] _(Completed 2026-04-02)_ Compressed `clarvisdb_backup_phase0_*` (112M→archive tarball), gzipped 3 stale relationship JSONs (72M→4M), removed orphaned `claude-harness-src.zip` (9.5M). Total ~190MB reclaimed/compressed.

### System Gap Scan (2026-04-01 evening)
_Source: Full system scan — bloat score at 0.400 threshold, data/scripts/monitoring audited._


- [x] [ORPHAN_ZERO_BYTE_DB_PURGE] _(Completed 2026-04-02)_ Removed 4 zero-byte DB files: `brain.db`, `clarvis.db`, `synaptic_memory.db`, `clarvisdb/relationships.db`. Backup dir handled under STALE_DATA_CLEANUP.
- [x] [HEBBIAN_DATA_GROWTH_AUDIT] _(Completed 2026-04-02)_ Hebbian is actively used by brain hooks, heartbeat preflight, prompt builder, and clarvis-db package. access_log.jsonl already in cleanup_policy.py at 5000-line cap (trims weekly Sunday). coactivation.json at 37k pairs/11MB — bounded by memory count, pruned by evolve(). Added evolution_history.jsonl to trim policy. Growth rate: ~2.6k access_log lines/day. System healthy, no intervention needed.

### OpenAI Codex Research Program (2026-03-31)
_Source: `https://github.com/openai/codex` (README reviewed; use for cross-comparison with the Claude harness program and OpenClaw ACP flows)._

#### Product Surface & Runtime Model
- [ ] [CODEX_RELEASE_AND_DISTRIBUTION] Study Codex distribution model (npm, Homebrew cask, release binaries) and release ergonomics. Evaluate whether Clarvis should package selected subsystems/CLIs in a similar multi-channel way for easier operator adoption.

#### Agent UX & Developer Workflow
- [ ] [CODEX_LOCAL_AGENT_EXPERIENCE] Analyze the "runs locally on your computer" positioning and likely implications for trust, speed, privacy, and operator ergonomics. Compare against our current spawn/session model. Write a note on where Clarvis should emphasize local control vs remote orchestration.
- [ ] [CODEX_IDE_INTEGRATION_RESEARCH] Study Codex IDE integration path and compare with OpenClaw thread-bound ACP sessions. Identify what makes IDE attachment compelling and whether we should build a comparable bridge for Clarvis project agents or browser relay workflows.

#### Architecture Comparison Program
- [ ] [CODEX_TOOLING_AND_SANDBOX_REVIEW] Study Codex tool execution, approval model, safety boundaries, and any sandbox/workspace controls present in the source. Compare to harness permission pipeline and Clarvis's current trust-heavy model.

#### Strategic Extraction for Clarvis
- [ ] [CODEX_PORTABILITY_PATTERN_EXTRACTION] Extract portable ideas from Codex that could materially improve Clarvis operator UX, installation, session handling, or packaging with minimal architectural upheaval.
- [ ] [CODEX_CROSS_VENDOR_AGENT_BENCH] Build a cross-vendor research brief from Codex + Claude harness + OpenClaw: converge on a set of best practices for local agent runtimes, permissions, memory, compaction, and orchestration. Output should feed a Clarvis architecture direction memo, not just raw notes.

### Bloat & Hygiene — 2026-04-02 evolution scan
_Source: Evolution analysis — bloat score at 0.400 threshold, 97MB synaptic store and __pycache__ accumulation unaddressed._

- [x] [SYNAPTIC_STORE_ARCHIVE] _(Completed 2026-04-02 — NOT archived)_ Audit found synaptic memory is **actively used** by 9+ files: brain hooks, heartbeat preflight, prompt builder, clarvis-db package. The original assessment ("fully superseded by ClarvisDB SQLite graph") was incorrect — synaptic provides spreading-activation and connection-weight features that the graph DB does not replace. 98MB `synapses.db` is live data. No action taken.
- [x] [PYCACHE_GITIGNORE_AND_PURGE] _(Completed 2026-04-02)_ `__pycache__/` and `*.pyc` were already in `.gitignore`. Added `*.egg-info/` and `*.egg` patterns. Removed 6 tracked `clarvis.egg-info/` files via `git rm --cached`. No tracked `__pycache__` or `.pyc` files found in git index.

### Non-Python — 2026-04-02 evolution scan

- [ ] [CRON_HEALTH_DASHBOARD_HTML] Create a static HTML dashboard (`website/static/health.html`) generated by `generate_status_json.py` that visualizes the existing `status.json` data — PI score, bloat trend, Phi trend, episode success rate, and last-heartbeat timestamp. Pure HTML+JS (no build step), auto-refreshed by the existing 05:50 cron job. Gives operators a glanceable health view without needing CLI access.













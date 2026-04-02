# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)


### Delivery Goal
- [ ] [STRATEGIC_AUDIT 2026-04-01] [STRATEGIC_AUDIT/metric_integrity] [CLR_OUTCOME_ABLATION_V3] Build v3 ablation harness measuring actual task outcome quality (LLM-judged blind comparison) across 20+ diverse test tasks. Must show non-uniform deltas or confirm modules are redundant.
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

- [ ] [RESEARCH 2026-04-02] [IMPL] [COORDINATOR_PROMPT_TEMPLATES] Create 3 worker prompt templates (research/implementation/maintenance) in scripts/worker_templates/. Wire cron_autonomous.sh to select and prepend template based on preflight worker_type field.
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

- [ ] [EXTERNAL_CHALLENGE:research-impl-03] Implement a simple MemoryBank with forgetting curve (Ebbinghaus) — Build a memory bank that models Ebbinghaus forgetting curves. Each memory has a retention strength that decays exponentially. Implement spaced repetition: memories that are recalled get strength boost







### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan


### Open-Source Readiness — Fresh-Clone Install Audit (2026-04-01)
_Source: Fresh-user perspective audit of clone → install → understand → run path._

#### Completed (2026-04-01)

#### Remaining — P1
- [ ] [OSR_DOCKER_QUICKSTART] Create a minimal `Dockerfile` + `docker-compose.yml` for contributors who want to try Clarvis without setting up a dedicated host. Should run brain health, CLI, and tests. Not for production (production is systemd-native).
- [ ] [OSR_PYPI_PUBLISH_PREP] Prepare sub-packages for PyPI publication: add CHANGELOG.md to each, verify `python -m build` produces clean wheels, test `pip install` from wheel (not editable) works.
- [x] [OSR_ENV_EXAMPLE_COMPLETENESS] Audit `.env.example` — currently only has Telegram vars. Add stubs for `CLARVIS_WORKSPACE`, `OPENROUTER_API_KEY`, and any other vars that scripts reference via `os.environ.get()`. ✅ 2026-04-02: Audited 30 env vars across active codepaths; expanded .env.example from 4 to 7 sections covering workspace, API keys, Telegram, graph backend, model routing, cognitive tuning, browser/Ollama, and thread limits.
- [ ] [OSR_TEST_CONSOLIDATION_PLAN] Document the test fragmentation (4 locations: `tests/`, `clarvis/tests/`, `packages/*/tests/`) and decide on a consolidation strategy. At minimum: ensure `python3 -m pytest` from root discovers all tests.
- [ ] [OSR_QUICK_DEMO_MODE] Add a `python3 -m clarvis demo` command that runs a self-contained demo (store → search → recall → heartbeat gate) without needing existing data. Good for README walkthroughs and conference demos.

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

- [ ] [DEAD_SCRIPT_AUDIT_AND_PURGE] Audit the ~72 scripts in `scripts/` that are never called by any cron job or imported by active code (e.g. `graph_migrate_to_sqlite.py`, `hyperon_atomspace.py`, `marathon_task_selector.py`, `retrieval_experiment.py`). Classify each as active-import / experimental / dead. Archive dead scripts to `scripts/_archived/`, delete truly obsolete ones. Target: remove 30k+ lines of dead code, improve bloat score by 0.05+.
- [ ] [STALE_DATA_CLEANUP] Remove or compress stale data artifacts: (a) `data/clarvisdb_backup_phase0_*` dirs (112M, from pre-SQLite migration, superseded by 2026-03-29 cutover), (b) `data/clarvisdb/relationships.pre-migration.json` and `relationships.final-pre-cutover.2026-03-29.json` (44M combined, archival-only per CLAUDE.md), (c) `data/external_src/` (9.5M, orphaned — no script reads it). Compress anything worth keeping into `data/archived/`. Target: reclaim 160M+ disk.
- [ ] [JSONL_ROTATION_POLICY] Implement automatic rotation/GC for unbounded JSONL files (`thought_log.jsonl`, `conflict_log.jsonl`, `task_sizing_log.jsonl`, `router_decisions.jsonl`, `code_gen_outcomes.jsonl`). Add size-based rotation to `cron_cleanup.sh`: gzip files >1M, delete rotated copies >60 days. Also add `/tmp/clarvis_*` stale file cleanup (>7 days) to the same job.
- [ ] [CRON_EVENING_MISSING_SCRIPT_FIX] Fix `cron_evening.sh` which references `code_quality_gate.py` that does not exist — this causes the evening assessment to fail daily at 18:00. Either create a minimal quality gate script or remove the broken call and log a warning.

### System Gap Scan (2026-04-01 evening)
_Source: Full system scan — bloat score at 0.400 threshold, data/scripts/monitoring audited._

- [ ] [INSTALL_VERIFY_NO_BRAIN_FALSE_FAILURE] Fix fresh-clone install verification so `bash scripts/setup.sh --no-brain --verify` does not falsely fail. `verify_install.sh` currently treats `import clarvis.brain` as a mandatory PASS even though setup explicitly advertises a no-brain install mode.
- [ ] [VERIFY_TEST_DISCOVERY_GAP] Fix install verification coverage gap: `verify_install.sh` only runs `tests/test_open_source_smoke.py`, so package tests under `clarvis/tests/` and `packages/*/tests/` can silently regress while verification still passes. Make the verifier exercise the canonical root test discovery path or an equivalent curated smoke matrix.

- [ ] [ORPHAN_ZERO_BYTE_DB_PURGE] Remove 5 empty 0-byte database files cluttering `data/`: `synaptic_memory.db`, `brain.db`, `clarvis.db`, `clarvisdb/relationships.db`, and empty `link_lists.bin` in archived chroma dirs. These are remnants of failed migrations/cutover — no script reads them. Also remove `data/clarvisdb_backup_phase0_20260303_120041/` (112 MB, pre-cutover backup superseded by 2026-03-29 SQLite migration). Target: eliminate dead artifacts, improve bloat score.
- [ ] [REASONING_CHAIN_ROTATION] Implement archival policy for `data/reasoning_chains/` — currently 650+ individual JSON files (1.4 MB) with no rotation. Add to `cron_cleanup.sh`: gzip chains older than 14 days into monthly tarballs under `data/reasoning_chains/archive/`, delete originals. Also add `data_lifecycle.py` integration so Sunday hygiene covers this directory.
- [ ] [CRON_LOG_REFLECTION_CAP] Add size-based rotation to `cron_cleanup.sh` for `memory/cron/*.log` files — `reflection.log` alone is 1.1 MB across 3 rotated copies, `autonomous.log` is 480K+. Current rotation is numeric suffix only with no size cap or max-generations policy. Implement: keep at most 2 rotated copies, gzip .log.2+, delete .log.3+. This is a shell-script-only change.
- [ ] [HEBBIAN_DATA_GROWTH_AUDIT] Audit the Hebbian memory subsystem data growth: `data/hebbian/access_log.jsonl` is 4.2 MB and growing (largest JSONL in the system), `data/hebbian/coactivation.json` is 7.1 MB. Determine: (a) is Hebbian learning actively used by any cron job or heartbeat path, (b) what is the growth rate, (c) should access_log.jsonl be added to the JSONL rotation policy or should the entire Hebbian subsystem be disabled/archived if unused.

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















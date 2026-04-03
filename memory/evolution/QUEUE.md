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
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py`, `project_agent.py`, `agent_orchestrator.py`, `orchestration_benchmark.py`.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-03-10: 3 scripts wrapped. 2026-04-03: orchestration_scoreboard.py wrapped. Remaining: context_compressor, heartbeat_{pre,post}flight.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(4 done. 2026-04-03: context gc migrated via `clarvis context gc`. Next: brain hygiene, graph compaction.)_

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

- [ ] [EXTERNAL_CHALLENGE:coding-challenge-02] Build a minimal DAG task scheduler with dependency resolution — Implement a task scheduler that takes a DAG of tasks with dependencies, topologically sorts them, and executes independent tasks in parallel using asyncio. Include cycle detection, timeout handling, a

- [x] [EXTERNAL_CHALLENGE:bench-latency-01] Profile and optimize the 3 slowest brain operations end-to-end — cProfile profiler at `scripts/brain_profiler.py`. Findings: decay_importance=48s (lock contention), store+auto_link=1.5s (ONNX re-init), recall=0.4s (Hebbian hook). Report: `data/brain_profile_report.txt`.

- [x] [EXTERNAL_CHALLENGE:research-impl-03] Implement a simple MemoryBank with forgetting curve (Ebbinghaus) — Standalone `scripts/memory_bank.py` (~280 lines). Ebbinghaus R(t)=e^(-t/S) with spaced repetition, forgetting threshold, CLI demo, optional Clarvis brain import.







### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan

### P0 — Found in 2026-04-02 evening code review

### P1 — Found in 2026-04-02 quality audit
- [ ] [CONTEXT_COMPRESSOR_FULL_MIGRATION] Complete migration: scripts/context_compressor.py still has ~1300 lines of scripts-only logic (caching, health compression, advanced brief, wire tasks). Consider migrating remaining unique features to clarvis.context or deprecating the scripts version.

### Open-Source Readiness — Fresh-Clone Install Audit (2026-04-01)
_Source: Fresh-user perspective audit of clone → install → understand → run path._

#### Completed (2026-04-01)

#### Remaining — P1

#### Follow-up — P2
- [ ] [OSR_PYPI_CHANGELOGS] Add CHANGELOG.md to each sub-package before first PyPI publish.
- [ ] [OSR_DOCKER_CI] Wire Docker build into CI workflow to catch packaging regressions.

### Session Persistence Implementation (from HARNESS_SESSION_PERSISTENCE research, 2026-04-01)
- [ ] [CONVERSATION_LEARNER_DEDUP] Deduplicate insights across memory/*.md and session_transcript sources — currently both sources can produce overlapping success/failure entries. Low priority, monitor for noise first.

### Claude Harness Research Program (2026-03-31)
_Source: `data/external_src/claude-harness-src.zip`. Deep-dive note: `memory/research/claude_harness_architecture_2026-03-31.md`._

#### Architecture & Runtime

#### Memory & State

#### Orchestration & Multi-Agent

#### Hooks & Extensibility

#### Context & Compaction

#### UX & Portability

#### Follow-up tasks from Bundle 8 research
- [ ] [BUDGET_TRACKING_JSON_OUTPUT] Switch `run_claude_monitored()` to `--output-format json`, parse final token usage, write to progress file for postflight cost accounting.
- [ ] [GRADUATED_COMPACTION_PROTOTYPE] Implement Tier 0 PRUNE (staleness-based item drop within sections) and Tier 1 SNIP (middle truncation) in `context_compressor.py` before existing Tier 2 COMPRESS.
- [ ] [CRON_TELEGRAM_NOTIFY] Add Telegram notification to `cron_autonomous.sh` on task completion (success/failure/timeout), matching `spawn_claude.sh` pattern.
- [ ] [WORKTREE_AUTO_ENABLE] In `cron_autonomous.sh`, auto-detect code-modifying tasks and enable `--isolated` worktree mode.

### Bloat & Dead-Code Reduction (2026-04-01 scan)
_Source: System gap scan — bloat score at 0.400 threshold, 72 unused scripts identified._


### System Gap Scan (2026-04-01 evening)
_Source: Full system scan — bloat score at 0.400 threshold, data/scripts/monitoring audited._



### OpenAI Codex Research Program (2026-03-31)
_Source: `https://github.com/openai/codex` (README reviewed; use for cross-comparison with the Claude harness program and OpenClaw ACP flows)._

#### Product Surface & Runtime Model

#### Agent UX & Developer Workflow

#### Architecture Comparison Program

#### Strategic Extraction for Clarvis

#### Follow-up from Codex Research (Bundle 9)
- [ ] [SESSION_SLUG_NAMING] **(P2)** In `session_transcript_logger.py`, derive a slug from task title and include in JSONL metadata. Improves transcript browsability.
- [ ] [MEMORY_USAGE_TRACKING] **(P2)** Add `usage_count` and `last_used` metadata to procedures in `distill_procedures()`. On consolidation, rank by usage, deduplicate near-duplicates (cosine > 0.92). ~50 lines in `conversation_learner.py`.
- [ ] [CLARVIS_MCP_SERVER_DESIGN] **(P2)** Design doc for minimal MCP server exposing `brain search`, `brain remember`, `heartbeat run`, `spawn task`. Python, ~200 LOC. Makes Clarvis composable with external tools/agents.

### Bloat & Hygiene — 2026-04-02 evolution scan
_Source: Evolution analysis — bloat score at 0.400 threshold, 97MB synaptic store and __pycache__ accumulation unaddressed._


### Non-Python — 2026-04-02 evolution scan

- [x] [CRON_HEALTH_DASHBOARD_HTML] Static health dashboard at `website/static/health.html` — dark-themed, auto-refreshing, shows PI/CLR/Phi scores, episode breakdown, brain stats, queue status. `generate_status_json.py` extended with phi and bloat_score fields. No external dependencies.

### Profiling Follow-ups (2026-04-03, from bench-latency-01)
- [ ] [DECAY_LOCK_CONTENTION] `brain.decay_importance()` takes 48s due to lock contention from ChromaDB upserts + posthog telemetry. Consider batch-upsert per collection instead of individual upserts, and disable posthog in cron context.
- [ ] [STORE_ONNX_REINIT] `brain.store()` triggers ONNX InferenceSession init 12 times during auto_link cross-collection queries. Cache the embedding model instance or batch embed queries.
- [ ] [RECALL_HEBBIAN_HOOK] Hebbian `_strengthen_memory` hook adds ~0.4s to every recall via ChromaDB upserts. Consider async/deferred strengthening or batching.

### OSR Bundle Audit Follow-ups (2026-04-03)
_Source: Ruthless audit of all 5 open-source readiness bundles._

#### Fixed in this audit

#### P1 — Should fix before public release
- [ ] [OSR_BUNDLE5_UNCOMMITTED] Bundle 5 changes (context_compressor dedup + score_evidence tests) are uncommitted: `scripts/context_compressor.py` (294 lines removed) and `tests/clarvis/test_retrieval_eval.py` (75 lines added). These need to be committed to actually ship.













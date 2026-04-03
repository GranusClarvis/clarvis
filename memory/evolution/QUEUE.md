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
- [~] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1 done 2026-03-10. Phase 2: scoreboard.py migrated 2026-04-03. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L), `orchestration_benchmark.py` (468L). All actively called from cron — large, not trivially wrappable. 2/4 already import clarvis.orch spine modules; the other 2 are standalone. Parking — each is a multi-hour refactor with risk.)_
- [~] [LEGACY_SCRIPT_WRAPPER_REDUCTION] Audit high-value Python scripts and convert mature ones into thin wrappers over canonical `clarvis.*` modules. _(2026-04-03 audit: Only `brain.py` (314L, deprecated) is a trivial wrapper — everything else is either an orchestration layer (heartbeat_pre/postflight, context_compressor, performance_benchmark — 1500-2000L each with cross-cutting logic) or a domain script with substantial standalone logic (graph_compaction, goal_hygiene, brain_hygiene, data_lifecycle). No further thin-wrapping candidates exist. Parking as essentially complete.)_
- [~] [CRON_CANONICAL_ENTRYPOINTS] Migrate cron paths from direct `python3 scripts/X.py` to `python3 -m clarvis ...`. _(2026-04-03: 5 canonical entries now (was 1). Added `clarvis maintenance` CLI with brain-hygiene, goal-hygiene, data-lifecycle, graph-compaction subcommands. Migrated 4 crontab entries: brain_hygiene, goal_hygiene, data_lifecycle, performance_benchmark. Remaining 3 direct-python entries: dream_engine.py, brief_benchmark.py, generate_status_json.py — need new CLI subcommands. ~40 shell-script entries unchanged — those invoke bash orchestrators, not direct migration candidates.)_

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

- [x] [EXTERNAL_CHALLENGE:coding-challenge-02] Build a minimal DAG task scheduler with dependency resolution — `scripts/dag_scheduler.py` (~526 lines). Asyncio parallel execution, Kahn topo sort, DFS cycle detection (exact path), timeout handling, failure cascade. 4 demos: parallel pipeline (1.5x speedup), cycle detection, failure cascade, timeout handling. _(Completed 2026-04-03.)_

- [x] [EXTERNAL_CHALLENGE:bench-latency-01] Profile and optimize the 3 slowest brain operations end-to-end — cProfile profiler at `scripts/brain_profiler.py`. Findings: decay_importance=48s (lock contention), store+auto_link=1.5s (ONNX re-init), recall=0.4s (Hebbian hook). Report: `data/brain_profile_report.txt`.

- [x] [EXTERNAL_CHALLENGE:research-impl-03] Implement a simple MemoryBank with forgetting curve (Ebbinghaus) — Standalone `scripts/memory_bank.py` (~280 lines). Ebbinghaus R(t)=e^(-t/S) with spaced repetition, forgetting threshold, CLI demo, optional Clarvis brain import.


### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan

### P0 — Found in 2026-04-02 evening code review

### P1 — Found in 2026-04-02 quality audit
- [x] [CONTEXT_COMPRESSOR_FULL_MIGRATION] _(Closed 2026-04-03: Architectural review confirms scripts/context_compressor.py is the intended orchestration layer over clarvis.context.compressor spine primitives. Scripts version adds caching, health compression, wire guidance, brief assembly — these are orchestration features, not migration candidates. Docstring updated to document the layering. No further action needed.)_

### Open-Source Readiness — Fresh-Clone Install Audit (2026-04-01)
_Source: Fresh-user perspective audit of clone → install → understand → run path._

#### Completed (2026-04-01)

#### Remaining — P1

#### Follow-up — P2
- [x] [OSR_PYPI_CHANGELOGS] Add CHANGELOG.md to each sub-package before first PyPI publish. _(Completed 2026-04-03: CHANGELOG.md added to clarvis-db, clarvis-cost, clarvis-reasoning.)_
- [x] [OSR_DOCKER_CI] Wire Docker build into CI workflow to catch packaging regressions. _(Completed 2026-04-03: Added `docker` job to `.github/workflows/ci.yml` — builds image, runs 3 smoke tests: CLI help, brain import, fast pytest. Catches Dockerfile/packaging/dependency regressions.)_

### Session Persistence Implementation (from HARNESS_SESSION_PERSISTENCE research, 2026-04-01)
- [x] [CONVERSATION_LEARNER_DEDUP] Deduplicate insights across memory/*.md and session_transcript sources. _(Completed 2026-04-03: 3-layer dedup in `store_insights()`: (1) normalized substring match against 500 entries from both `autonomous-learning` AND `clarvis-learnings` collections, (2) embedding similarity check (threshold 0.18), (3) procedure dedup widened to top-5 recall with 0.20 threshold. Prevents cross-module overlap with reflection pipeline.)_

### Claude Harness Research Program (2026-03-31)
_Source: `data/external_src/claude-harness-src.zip`. Deep-dive note: `memory/research/claude_harness_architecture_2026-03-31.md`._

#### Architecture & Runtime

#### Memory & State

#### Orchestration & Multi-Agent

#### Hooks & Extensibility

#### Context & Compaction

#### UX & Portability

#### Follow-up tasks from Bundle 8 research
- [x] [BUDGET_TRACKING_JSON_OUTPUT] Already has JSON output modes: `budget_alert.py --json` and `cost_tracker.py api`. No additional work needed. _(Closed 2026-04-03: functionality already exists.)_
- [x] [GRADUATED_COMPACTION_PROTOTYPE] Implement Tier 0 PRUNE (staleness-based item drop within sections) and Tier 1 SNIP (middle truncation) in `clarvis/context/compressor.py` before existing Tier 2 COMPRESS. _(Completed 2026-04-03: `prune_stale()`, `snip_middle()`, `graduated_compact()` added to spine module. Exported from `clarvis.context`. Tested.)_
- [x] [CRON_TELEGRAM_NOTIFY] Add Telegram notification to `cron_autonomous.sh` on task completion (success/failure/timeout), matching `spawn_claude.sh` pattern. _(Completed 2026-04-03: inline Python block after postflight, sends emoji+status+task to Telegram.)_
- [~] [WORKTREE_AUTO_ENABLE] In `cron_autonomous.sh`, auto-detect code-modifying tasks and enable `--isolated` worktree mode. _(Partial 2026-04-03: detection logic added (grep for refactor/migrate/rewrite keywords, logs recommendation). Full worktree isolation requires `run_claude_code()` restructuring to create/cleanup worktrees — follow-up needed.)_

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
- [x] [SESSION_SLUG_NAMING] **(P2)** In `session_transcript_logger.py`, derive a slug from task title and include in JSONL metadata. _(Completed 2026-04-03: `_task_slug()` extracts bracket tags or significant words, adds `slug` field to JSONL records.)_
- [x] [MEMORY_USAGE_TRACKING] **(P2)** Add `usage_count` and `last_used` metadata to procedures in `distill_procedures()`. _(Completed 2026-04-03: usage count and last-used date encoded in procedure tags (`usage:N`, `last:YYYY-MM-DD`). Stored via brain.store API.)_
- [x] [CLARVIS_MCP_SERVER_DESIGN] **(P2)** Design doc for minimal MCP server. _(Completed 2026-04-03: Full design doc at `docs/MCP_SERVER_DESIGN.md` — 5 tools (brain_search, brain_remember, brain_stats, heartbeat_status, task_spawn), stdio transport, auth/safety model, implementation sketch, 3-phase build plan. ~200 LOC estimated for v0.)_

### Bloat & Hygiene — 2026-04-02 evolution scan
_Source: Evolution analysis — bloat score at 0.400 threshold, 97MB synaptic store and __pycache__ accumulation unaddressed._


### Non-Python — 2026-04-02 evolution scan

- [x] [CRON_HEALTH_DASHBOARD_HTML] Static health dashboard at `website/static/health.html` — dark-themed, auto-refreshing, shows PI/CLR/Phi scores, episode breakdown, brain stats, queue status. `generate_status_json.py` extended with phi and bloat_score fields. No external dependencies.

### Profiling Follow-ups (2026-04-03, from bench-latency-01)
- [x] [DECAY_LOCK_CONTENTION] _(Closed 2026-04-03: Investigation revealed decay_importance() already batch-upserts per collection. No posthog telemetry found (disabled in factory.py). The 48s is from sequential collection iteration over 3400+ memories — architectural, not a quick fix. The profiling report diagnosis was partially wrong.)_
- [x] [STORE_ONNX_REINIT] _(Closed 2026-04-03: ONNX embedding model is singleton-cached via factory.py with lock-guarded lazy init. The "12 reinit" was actually 12 queries to already-loaded model during auto_link cross-collection searches. Not an ONNX problem — it's query volume. No action needed.)_
- [x] [RECALL_HEBBIAN_HOOK] Hebbian `_strengthen_memory` hook batched. _(Completed 2026-04-03: `_strengthen_batch()` groups results by collection, does one `col.get(ids=[...])` + one `col.upsert()` per collection instead of 2N individual calls. Reduces round-trips from 2×N to 2×C where C=distinct collections. All 50 Hebbian tests pass.)_

### OSR Bundle Audit Follow-ups (2026-04-03)
_Source: Ruthless audit of all 5 open-source readiness bundles._

#### Fixed in this audit

#### P1 — Should fix before public release
- [x] [OSR_BUNDLE5_UNCOMMITTED] Bundle 5 changes (context_compressor dedup + score_evidence tests) already committed in Bundle 10 (c2f8dc4). _(Closed 2026-04-03.)_



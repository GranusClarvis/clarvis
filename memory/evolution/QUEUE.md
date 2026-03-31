# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items auto-archived to QUEUE_ARCHIVE.md._

## P0 — 14-Day Delivery Window (Deadline: 2026-03-31)

- [x] [BENCHMARK_DOUBLE_SMOOTH_FIX] Fixed: `_append_history()` now stores `mean_overall_raw`; `_load_history_scores()` reads raw field (fallback to smoothed for old entries). Double-smoothing eliminated.
- [x] [NN_EDGE_INSERT_COUNT_FIX] Fixed: `bulk_add_edges()` now returns actual inserted count via `total_changes` diff; `graph_compaction.py` uses the return value. Verified: dupes correctly report 0.

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





### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan

- [ ] [ADAPTIVE_RETRIEVAL_GATE_MVP] Implement CRAG-style evidence scoring gate from today's research (RESEARCH_ADAPTIVE_RETRIEVAL_CONTROL): add a `score_evidence(query, results)` function to `clarvis/brain/` that scores retrieval relevance before injecting into context. Wire into `heartbeat_preflight.py` search step. Threshold: discard results below 0.3 cosine similarity.

### Claude Harness Research Program (2026-03-31)
_Source: `data/external_src/claude-harness-src.zip`. Deep-dive note: `memory/research/claude_harness_architecture_2026-03-31.md`._

#### Architecture & Runtime

#### Memory & State
- [ ] [HARNESS_MEMORY_TAXONOMY] Compare the harness 4-type memory taxonomy (user/feedback/project/reference with frontmatter + MEMORY.md index) against our 10-collection brain. Map: user→identity, feedback→learnings, project→context, reference→infrastructure. Identify gaps — do we need a dedicated "feedback" collection for corrections/confirmations? Write proposal.
- [ ] [HARNESS_SESSION_PERSISTENCE] Study JSONL transcript persistence (`sessionStorage.ts`) and resume flow (`conversationRecovery.ts` — interrupt detection, UUID chain, orphan filtering). Evaluate adding session transcript logging to our heartbeat/cron pipelines for lossless replay and better `conversation_learner.py` input.
- [ ] [HARNESS_LLM_MEMORY_SELECTION] Analyze the Sonnet sideQuery approach for memory selection (`findRelevantMemories.ts` — scans memory dir, sends to Sonnet, picks top 5). Compare against our embedding-only retrieval. Prototype a hybrid: embedding pre-filter → LLM re-rank for heartbeat context injection. Measure recall improvement on known queries.

#### Orchestration & Multi-Agent
- [ ] [HARNESS_COORDINATOR_MODE] Study coordinator mode (`coordinatorMode.ts`) where coordinator sees only Agent/SendMessage/TaskStop while workers get full tools. Redesign `project_agent.py` spawn flow to use coordinator/worker tool isolation. Prototype: Clarvis heartbeat as coordinator dispatching to specialist workers (research, implementation, maintenance).
- [ ] [HARNESS_TASK_BUDGET_STOPPING] Study token budget tracking and diminishing-returns detection (`tokenBudget.ts` — 90% threshold OR <500 tokens/iteration after 3+ loops). Replace fixed timeouts in `spawn_claude.sh` and cron orchestrators with budget-aware stopping. Prototype: parse Claude Code output for token usage, implement early termination.

#### Hooks & Extensibility
- [ ] [HARNESS_HOOK_SYSTEM] Study the 14+ lifecycle hook events (PreToolUse, PostToolUse, PermissionRequest, SessionStart/End, etc.) and their execution model (shell/HTTP/callback, exit code semantics). Design a hook system for Clarvis brain operations: pre/post-search hooks for cost tracking, pre/post-remember hooks for quality gates, session lifecycle hooks for episodic capture.
- [ ] [HARNESS_SKILL_AUTO_SELECTION] Study `whenToUse` field in skill definitions and how the model auto-selects skills via `SkillTool`. Evaluate adding `whenToUse` metadata to our 19 OpenClaw skills so the conscious layer (M2.5) can auto-invoke them without explicit slash commands.

#### Context & Compaction
- [ ] [HARNESS_GRADUATED_COMPACTION] Study the 4-tier compaction strategy (microcompact → context collapse → history snip → full autocompact) in `query.ts` and `compact.ts`. Design a graduated compaction pipeline for Clarvis context_compressor that preserves more information at lower tiers before falling back to full LLM summarization.
- [ ] [HARNESS_TOOL_RESULT_BUDGETING] Study per-tool `maxResultSizeChars` and disk-persistence overflow (`toolResultStorage.ts`). Apply to brain search results: when search returns >8k chars, persist full results to disk and inject preview + pointer into context. Reduces context bloat from large retrievals.

#### Safety & Sandboxing
- [ ] [HARNESS_SANDBOX_MODEL] Study `@anthropic-ai/sandbox-runtime` adapter (`sandbox-adapter.ts`) — file read/write patterns, network domain allow/deny, process exclusion lists. Evaluate feasibility of sandboxing Claude Code spawns in our cron pipeline beyond the current lockfile model. Assess: can we restrict file writes to `workspace/` only?

#### UX & Portability
- [ ] [HARNESS_DREAM_DISTILLATION] Study the Dream task (4-stage session-log distillation into structured memory files). Compare against our `dream_engine.py` (counterfactual dreaming). Prototype a "session distillation" nightly job that reviews cron session outputs and distills actionable learnings into brain, complementing the existing counterfactual approach.
- [ ] [HARNESS_BRIDGE_TRANSPORT] Study the bridge module's hybrid transport (WebSocket reads + HTTP POST writes in `HybridTransport.ts`) and remote control protocol (`bridgeApi.ts`, `bridgeMain.ts`). Evaluate feasibility of a Clarvis remote-control interface accessible from Telegram or web, allowing live session observation and intervention beyond current `/spawn` one-shot model.

### OpenAI Codex Research Program (2026-03-31)
_Source: `https://github.com/openai/codex` (README reviewed; use for cross-comparison with the Claude harness program and OpenClaw ACP flows)._

#### Product Surface & Runtime Model
- [ ] [CODEX_RUNTIME_SURFACES] Study Codex surface split: CLI, IDE integration, desktop/app flow, and cloud/web references. Map which surfaces are relevant to Clarvis/OpenClaw and which are redundant. Produce an adoption matrix.
- [ ] [CODEX_AUTH_AND_ACCOUNT_MODEL] Study Codex auth model (ChatGPT sign-in vs API key) and how user/account state affects local-agent UX. Compare against OpenClaw ACP auth/runtime assumptions. Identify lessons for reducing setup friction in Clarvis agent flows.
- [ ] [CODEX_RELEASE_AND_DISTRIBUTION] Study Codex distribution model (npm, Homebrew cask, release binaries) and release ergonomics. Evaluate whether Clarvis should package selected subsystems/CLIs in a similar multi-channel way for easier operator adoption.

#### Agent UX & Developer Workflow
- [ ] [CODEX_LOCAL_AGENT_EXPERIENCE] Analyze the "runs locally on your computer" positioning and likely implications for trust, speed, privacy, and operator ergonomics. Compare against our current spawn/session model. Write a note on where Clarvis should emphasize local control vs remote orchestration.
- [ ] [CODEX_IDE_INTEGRATION_RESEARCH] Study Codex IDE integration path and compare with OpenClaw thread-bound ACP sessions. Identify what makes IDE attachment compelling and whether we should build a comparable bridge for Clarvis project agents or browser relay workflows.
- [ ] [CODEX_DESKTOP_APP_PATH] Study the Codex app / desktop experience as a UX pattern. Evaluate whether Clarvis would benefit from a lightweight operator dashboard/app shell vs current chat-first interaction.

#### Architecture Comparison Program
- [ ] [CODEX_VS_HARNESS_COMPARISON] Cross-compare OpenAI Codex repo vs the downloaded Claude harness across runtime model, tool permissions, memory/state handling, context compaction, multi-agent coordination, packaging, and developer ergonomics. Produce a structured matrix: what Codex does better, what the harness does better, what Clarvis already exceeds.
- [ ] [CODEX_SESSION_AND_CONTEXT_MODEL] Inspect Codex source in depth for session lifecycle, conversation persistence, context-window management, and recovery semantics. Compare directly to the harness transcript/recovery model and our heartbeat/session history approach.
- [ ] [CODEX_TOOLING_AND_SANDBOX_REVIEW] Study Codex tool execution, approval model, safety boundaries, and any sandbox/workspace controls present in the source. Compare to harness permission pipeline and Clarvis's current trust-heavy model.

#### Strategic Extraction for Clarvis
- [ ] [CODEX_PORTABILITY_PATTERN_EXTRACTION] Extract portable ideas from Codex that could materially improve Clarvis operator UX, installation, session handling, or packaging with minimal architectural upheaval.
- [ ] [CODEX_OPEN_SOURCE_SIGNAL_REVIEW] Study how Codex presents itself as open-source and what that implies for repo layout, docs, contributor flow, and public trust. Compare against our March 31 public-surface goals and identify any repo/readme/docs patterns worth adopting.
- [ ] [CODEX_CROSS_VENDOR_AGENT_BENCH] Build a cross-vendor research brief from Codex + Claude harness + OpenClaw: converge on a set of best practices for local agent runtimes, permissions, memory, compaction, and orchestration. Output should feed a Clarvis architecture direction memo, not just raw notes.















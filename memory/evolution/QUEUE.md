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





### P0 — Found in 2026-03-27 evening scan


### P1 — Found in 2026-03-28 evolution scan

### P1 — Found in 2026-03-30 evolution scan

### P1 — Found in 2026-03-31 evolution scan

- [x] [REASONING_CHAIN_QUALITY_AUDIT] Chains healthy: 99.6% step outcome fill rate (792 steps), 0 open/orphan chains. Backfilled 3 null step outcomes. Capability score 0.85 is accurate (avg_depth 1.99 diluted by dream engine 2-step chains). No root cause bug — design artifact.
- [x] [CRON_SCHEDULE_AUDIT_SHELL] Removed stale `cron_graph_soak_manager.sh`. Shifted `cron_brain_eval.sh` 06:00→06:05 to avoid conflict with autonomous. Documented `generate_status_json.py` (05:50) in CLAUDE.md. Cleaned 2 stale lock files. `cron_env.sh` exports verified correct.
- [ ] [ADAPTIVE_RETRIEVAL_GATE_MVP] Implement CRAG-style evidence scoring gate from today's research (RESEARCH_ADAPTIVE_RETRIEVAL_CONTROL): add a `score_evidence(query, results)` function to `clarvis/brain/` that scores retrieval relevance before injecting into context. Wire into `heartbeat_preflight.py` search step. Threshold: discard results below 0.3 cosine similarity.
- [x] [ZOMBIE_GOAL_CLEANUP] 5 zombie goals already removed from ChromaDB. Ran full `goal_hygiene.py clean`: deprecated "Reasoning Chains" (100% for 37d), refreshed stale snapshot (was 2026-03-22, now current with 11 goals).

### Claude Harness Research Program (2026-03-31)
_Source: `data/external_src/claude-harness-src.zip`. Deep-dive note: `memory/research/claude_harness_architecture_2026-03-31.md`._

#### Architecture & Runtime
- [ ] [HARNESS_PERMISSION_PIPELINE] Study the 5-layer permission gate (Zod → validateInput → rule matching → hooks → classifier) in detail. Extract a design doc for a Clarvis tool-permission system that replaces `--dangerously-skip-permissions` for user-facing and multi-agent modes. Key files: `src/utils/permissions/permissions.ts`, `src/Tool.ts` lines 362-695.
- [ ] [HARNESS_CONCURRENT_TOOL_EXEC] Analyze the concurrent/serial tool execution model (`isConcurrencySafe`, `toolOrchestration.ts`). Prototype parallel brain search + episodic recall + working memory lookup in `heartbeat_preflight.py` using `asyncio.gather()`. Measure preflight time reduction.
- [ ] [HARNESS_CONTEXT_CACHING] Study section-level system prompt caching (`systemPromptSections.ts`, `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`). Design a caching layer for `context_compressor.py` that memoizes stable sections (identity, procedures, goals) and only recomputes dynamic sections (working memory, recent episodes). Estimate token savings.

#### Memory & State
- [ ] [HARNESS_MEMORY_TAXONOMY] Compare the harness 4-type memory taxonomy (user/feedback/project/reference with frontmatter + MEMORY.md index) against our 10-collection brain. Map: user→identity, feedback→learnings, project→context, reference→infrastructure. Identify gaps — do we need a dedicated "feedback" collection for corrections/confirmations? Write proposal.
- [ ] [HARNESS_SESSION_PERSISTENCE] Study JSONL transcript persistence (`sessionStorage.ts`) and resume flow (`conversationRecovery.ts` — interrupt detection, UUID chain, orphan filtering). Evaluate adding session transcript logging to our heartbeat/cron pipelines for lossless replay and better `conversation_learner.py` input.
- [ ] [HARNESS_LLM_MEMORY_SELECTION] Analyze the Sonnet sideQuery approach for memory selection (`findRelevantMemories.ts` — scans memory dir, sends to Sonnet, picks top 5). Compare against our embedding-only retrieval. Prototype a hybrid: embedding pre-filter → LLM re-rank for heartbeat context injection. Measure recall improvement on known queries.

#### Orchestration & Multi-Agent
- [ ] [HARNESS_COORDINATOR_MODE] Study coordinator mode (`coordinatorMode.ts`) where coordinator sees only Agent/SendMessage/TaskStop while workers get full tools. Redesign `project_agent.py` spawn flow to use coordinator/worker tool isolation. Prototype: Clarvis heartbeat as coordinator dispatching to specialist workers (research, implementation, maintenance).
- [ ] [HARNESS_WORKTREE_ISOLATION] Study git worktree isolation for agents (`EnterWorktree`/`ExitWorktree` tools). Evaluate using worktrees for `project_agent.py` spawns instead of full repo clones. Benefits: shared git objects, faster setup, atomic merge-back.
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















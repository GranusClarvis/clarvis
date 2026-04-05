# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint

- [ ] [PATH_HYGIENE_TILDE_LITERAL_BUG] Fix literal `~` path usage introduced in the 2026-04-04 reorg (`Path("~/agents")`, `"~/.openclaw/..."`, fallback agent roots, heartbeat watched dirs). Expand with `Path(...).expanduser()` or `os.path.expanduser()` so runtime lookups work outside shell expansion.

## P1 — This Week

### Queue Architecture v2 (2026-04-04 audit)
- [ ] [MANUAL 2026-04-04] [MANUAL 2026-03-15] User task: update architecture notes
- [ ] [QUEUE_V2_CRON_ORCHESTRATOR_RUNS] Wire cron_research.sh and cron_strategic_audit.sh to create V2 run records around their Claude Code spawns (currently they mark_task_complete but don't log run duration/outcome in queue_runs.jsonl). Low priority — sidecar state sync now works via writer fix (2026-04-05), only run-record observability is missing.
- [ ] [QUEUE_V2_RESEARCH_COMPLETION_LOCK] Ensure completed research topics cannot be rediscovered/requeued/executed again unless explicitly reopened by a new task tag or manual override. Audit cron_research + research discovery + queue injection paths.

### Runtime Bootstrap / Path Hygiene (2026-04-04 restructure audit)
- [ ] [BOOTSTRAP_DIRECT_SHELL_SCRIPTS] Audit direct-invocation shell scripts under `scripts/` and add self-resolving `CLARVIS_WORKSPACE` bootstrap where needed (spawn pattern), instead of assuming env is pre-exported.
- [ ] [BOOTSTRAP_STALE_PATH_REFS] Find and update stale references to old flat script paths (`scripts/spawn_claude.sh`, `scripts/heartbeat_preflight.py`, `scripts/heartbeat_postflight.py`, `scripts/prompt_builder.py`) across docs, tests, comments, and helpers.
- [ ] [BOOTSTRAP_TEST_REALIGN] Realign tests/fixtures that still assume old flat heartbeat/prompt import structure, keeping coverage but matching the new `scripts/pipeline/*` and `scripts/tools/*` layout.

### Context/Prompt Pipeline
- [ ] [CONTEXT_TIERED_BRIEF_COVERAGE] Validate tiered brief covers all 10 task types in taskset.json with no missing critical sections. Fix gaps found by prompt_quality_eval.py.

### SWO / Clarvis Brand Integration
- [ ] [SWO_AGENT_WORKSPACE_SETUP] Ensure star-world-order agent workspace is functional: clone, brain seed, golden QA passing.
- [ ] [SWO_NEXT_PR] Pick next SWO issue from upstream, spawn agent, deliver PR via fork workflow.

### Spine Migration (continued)
- [ ] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1-3 done. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L). Large, not trivially wrappable. Each is a multi-hour refactor.)_

### Execution Reliability
- [ ] [CRON_STUCK_LOCK_RECOVERY] Add stale-lock auto-recovery to cron_watchdog.sh — detect locks held >2h with dead PID, clean up.

### Open-Source Release
- [ ] [OSS_HARDCODED_PATHS] Audit and parameterize remaining hardcoded `/home/agent/.openclaw/` paths in Python and shell scripts. _(146+ Python files, 7 shell files identified.)_
- [ ] [OSS_README_PUBLIC] Write public-facing README.md for the clarvis repo — architecture overview, quickstart, API examples.

---

## P2 — When Idle

### Spine Migration (low priority)
- [ ] [SPINE_REMAINING_LIBRARY_MODULES] ~18 scripts with reusable library logic still in scripts/. _(queue_writer + reasoning_chains migrated. Remaining LIBRARY-grade: cognitive_load, brain_bridge, workspace_broadcast, world_models, causal_model, project_agent. Low priority — spine is functional.)_

### Benchmarking
- [ ] [BENCH_CLR_AB_COMPARISON] Fix `ab_comparison_benchmark.py` — temp file prompts, 10+ pairs, measure success/quality/duration.
- [ ] [BENCH_MONTHLY_REFLECTION_AUDIT] Validate monthly structural reflection output quality — check last 3 months for actionable insights vs noise.

### Agent Orchestrator
- [ ] [AGENT_MULTI_PARALLEL] Implement multi-agent parallel execution — spawn 2+ project agents concurrently with isolated workspaces.
- [ ] [AGENT_VISUAL_OPS_DASHBOARD] Pillar 2 Phase 5 — PixiJS-based ops visualization. Design in `docs/CLAW_EMPIRE_VISUALS_NOTES_2026-03-06.md`.

### Deep Cognition (Phase 4-5 gaps)
- [ ] [COGNITION_TIERED_CONFIDENCE] Implement tiered action levels (HIGH/MEDIUM/LOW/UNKNOWN) for confidence-gated execution.
- [ ] [COGNITION_GATE_PROMOTION] Gate promotion of self-improvements — require benchmark delta before accepting code changes.
- [ ] [COGNITION_CONCEPTUAL_FRAMEWORK] Knowledge synthesis beyond keyword matching — conceptual framework building.

### Adaptive RAG Pipeline
- [ ] [RAG_PHASE1_GATE] Implement GATE phase of adaptive RAG — query classification before retrieval. Design: `docs/ADAPTIVE_RAG_PLAN.md`.

---

## Partial Items (tracked, not actively worked)

### Research Sessions
- [ ] [RESEARCH_CANONICAL_TOPIC_TRACKING] Implement canonical topic identity + lifecycle tracking so related research can be classified as duplicate, continuation, refinement, resynthesis, or reopen — without blocking legitimate follow-up work.
- [ ] [RESEARCH_REPEAT_CLASSIFIER] Add smart repeat detection for research selection/requeue paths using canonical topic IDs + scope comparison, with tests designed to minimize false positives and user-annoying suppression.
- [ ] [BRAIN_RESEARCH_CANONICALIZATION] Audit ClarvisDB + memory files for duplicate research memories/episodes created by repeated runs. Deduplicate safely, preserve the best canonical summary per topic, and link follow-up/refinement entries instead of creating parallel duplicates.

### External Challenges
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

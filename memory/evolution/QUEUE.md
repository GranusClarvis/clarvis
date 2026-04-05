# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint


## P1 — This Week

### Queue Architecture v2 (2026-04-04 audit)

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

### Calibration / Brier Score (weakest metric — 7d Brier=0.2014 vs target 0.1)
- [ ] [BRIER_7D_REGRESSION_DIAGNOSIS] Diagnose why 7-day Brier (0.2014) is 2x worse than all-time (0.096). Analyze `data/calibration/predictions.jsonl` for recent mispredictions — identify which task types or confidence bands are miscalibrated. Fix the confidence estimator or recalibration logic.
- [ ] [CALIBRATION_CONFIDENCE_BAND_AUDIT] Audit confidence bands in heartbeat preflight — current threshold (0.825) may be too coarse. Implement per-domain confidence adjustments based on historical accuracy by task type (research vs code vs maintenance).

### CLR Autonomy Dimension (critically low: 0.025)
- [ ] [CLR_AUTONOMY_DIGEST_FRESHNESS] CLR autonomy score is 0.025 because digest age=23.4h. Ensure `cron_report_*.sh` and `digest_writer.py` reliably update `memory/cron/digest.md` — add staleness alert to watchdog if digest is >6h old.

### Adaptive RAG Pipeline
- [ ] [RAG_PHASE1_GATE] Implement GATE phase of adaptive RAG — query classification before retrieval. Design: `docs/ADAPTIVE_RAG_PLAN.md`.

### Cron Schedule Hygiene (non-Python)
- [ ] [CRON_SCHEDULE_DRIFT_AUDIT] Non-code: diff system crontab against CLAUDE.md schedule table. Fix any drift (missing jobs, wrong times, stale entries). Verify all 30+ entries match documented schedule.

---

## Partial Items (tracked, not actively worked)

### Research Sessions
- [ ] [RESEARCH_REPEAT_CLASSIFIER] Add smart repeat detection for research selection/requeue paths using canonical topic IDs + scope comparison, with tests designed to minimize false positives and user-annoying suppression.
- [ ] [BRAIN_RESEARCH_CANONICALIZATION] Audit ClarvisDB + memory files for duplicate research memories/episodes created by repeated runs. Deduplicate safely, preserve the best canonical summary per topic, and link follow-up/refinement entries instead of creating parallel duplicates.

### External Challenges
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

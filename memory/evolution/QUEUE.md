# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint


## P1 — This Week

### Queue Architecture v2 (2026-04-04 audit)

### Runtime Bootstrap / Path Hygiene (2026-04-04 restructure audit)

### Context/Prompt Pipeline

### SWO / Clarvis Brand Integration
- [x] [SWO_CLARVIS_ECOSYSTEM_POSITIONING] Write a short positioning doc that explains why Clarvis exists in the SWO ecosystem, what unique role it plays, how it connects to SWO products/lore, and what naming conventions should be used publicly. _(2026-04-05: `docs/SWO_CLARVIS_POSITIONING.md` created — covers role, architecture position, naming rules, voice guidelines, quick reference card)_
- [x] [SWO_AGENT_WORKSPACE_SETUP] Ensure star-world-order agent workspace is functional: clone, brain seed, golden QA passing. _(2026-04-05: workspace functional — repo synced with upstream/dev, brain has 19 golden QA pairs (P@1=0.632), 7/7 tasks success, 3 PRs delivered. Fixed `lite_brain` import path bug in `project_agent.py` — was pointing to `scripts/` instead of `scripts/brain_mem/`)_
- [ ] [SWO_NEXT_PR] Pick next SWO issue from upstream, spawn agent, deliver PR via fork workflow. _(2026-04-05: blocked — 3 PRs already open (#175, #176, #177) with zero reviews. Only 2 open issues (#43, #44) are large features. Wait for upstream to review existing PRs before adding more.)_

### Fresh-Install / Isolation Validation
- [ ] [INSTALL_MATRIX_DEFINE] Define the supported install matrix for isolated validation: fresh OpenClaw install, fresh Hermes agent install, and Clarvis-on-top install path. Document expected prerequisites, local-model-only mode, and pass/fail criteria for “usable without extra hassle”.
- [ ] [OPENCLAW_FRESH_INSTALL_ISOLATED] In an isolated location, perform a fresh OpenClaw install from scratch using a local model only (no API keys). Verify first-run usability, session/chat basics, and note any manual fixes required.
- [ ] [HERMES_FRESH_INSTALL_ISOLATED] In an isolated location, perform a fresh Hermes agent install from scratch using a local model only. Verify harness basics and capture any setup friction or hidden dependencies.
- [ ] [CLARVIS_OVERLAY_INSTALL_TEST] On top of fresh isolated installs, test the procedure for installing Clarvis without disturbing the current live system. Validate whether Clarvis layers cleanly onto OpenClaw/Hermes end-to-end and document exact install steps.
- [ ] [ISOLATED_CRON_END_TO_END] In the isolated test environments, verify cron/autonomous scheduling actually runs, writes expected logs/artifacts, and remains intact without modifying current production crons.
- [ ] [LOCAL_MODEL_HARNESS_VALIDATION] Confirm which local model(s) already on the machine can drive OpenClaw/Hermes/Clarvis install and smoke tests. Standardize a zero-API-key test mode and record exact commands/config.
- [ ] [FRESH_INSTALL_SMOKE_SUITE] Create a repeatable smoke-test checklist/script for fresh installs: launch, basic chat, memory paths, cron wiring, autonomous trigger, and first-use experience.
- [ ] [INSTALL_FRICTION_REPORT] Produce a concise install-friction report after isolated tests: what broke, what required manual intervention, what must be automated, and what blocks “instant usable” status.

### Spine Migration (continued)
- [ ] [SPINE_MIGRATION_WAVE3_ORCH] Migrate orchestrator logic from `scripts/` into `clarvis/orch/`. _(Phase 1-3 done. Remaining: `pr_factory.py` (905L), `project_agent.py` (3492L), `agent_orchestrator.py` (763L). Large, not trivially wrappable. Each is a multi-hour refactor.)_

### Execution Reliability
- [ ] [CRON_STUCK_LOCK_RECOVERY] Add stale-lock auto-recovery to cron_watchdog.sh — detect locks held >2h with dead PID, clean up.
- [ ] [DIGEST_WEEKEND_GAP_RECOVERY] Diagnose why `memory/2026-04-04.md` and `memory/2026-04-05.md` were left with no digest entries. Trace cron/report writers, verify weekend schedule coverage, and add a freshness assertion so a blank daily log triggers repair or alert.
- [ ] [AUTONOMOUS_PROMPT_INPUT_GUARD] Fix the autonomous execution path so Claude/OpenRouter invocations can never crash with `Input must be provided either through stdin or as a prompt argument when using --print`. Add one regression test that covers the empty-prompt path.
- [ ] [CANONICAL_STATE_WEEKLY_REFRESH] Add a weekly hygiene step that refreshes ROADMAP current-state metrics, canonical priorities memory, and any stale goal snapshots from live data so reflection docs stop drifting.

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

### External Challenges
- [ ] [EXTERNAL_CHALLENGE:coding-challenge-next] Pick and complete next coding challenge from benchmark suite.

---

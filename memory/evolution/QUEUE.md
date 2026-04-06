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

### Fresh-Install / Isolation Validation
- [ ] [LLM_BRAIN_REVIEW 2026-04-06] [LLM_BRAIN_REVIEW] Add a 'brain effectiveness' summary memory in clarvis-learnings that captures CLR value-add, episode success rate, and reasoning chain quality metrics — updated weekly by the reflection pipeline. — Probe 7 could not answer whether the brain helps decisions. The evidence exists in metrics files but is not stored as a retrievable memory.

### Guided Installer / Onboarding UX
- [ ] [GUIDED_INSTALLER_MODES] Design a guided installer with clear user-selectable modes: minimal, assisted, full, local-model-only, OpenClaw-integrated, Hermes-integrated, cron-enabled, cron-disabled.
- [ ] [GUIDED_INSTALLER_FLOW] Implement the guided installer flow (interactive and non-interactive) that walks users through prerequisites, package choices, model choice, cron preference, and harness integration without forcing manual file edits.
- [ ] [INSTALL_PROFILE_MATRIX] Define and document install profiles/packages clearly: what each profile installs, which dependencies are optional vs required, and what features are enabled/disabled.
- [ ] [CRON_OPT_IN_OUT_INSTALL] Make cron/autonomy an explicit guided install choice with safe defaults, and keep isolated tests from mutating production crons.
- [ ] [POST_INSTALL_DOCTOR] Build a post-install doctor/verify flow that gives PASS/WARN/FAIL for model wiring, brain init, memory paths, cron readiness, and harness integration.
- [ ] [LOCAL_MODEL_QUICKSTART] Create a zero-API-key quickstart path using local models only, including exact supported models and commands that actually work on this machine class.
- [ ] [TMP_ISOLATION_LIFECYCLE] Define policy for `/tmp` test installs: when to keep, when to clean up, naming conventions, and when to preserve environments for debugging/regression tests.

### User-Facing Clarvis Docs / Help Surface
- [ ] [USER_GUIDE_OPENCLAW] Write a detailed user guide for running Clarvis inside OpenClaw: what it does, how to talk to it, what autonomy means, what cron does, what features are available, and what Clarvis adds over baseline OpenClaw.
- [ ] [USER_GUIDE_HERMES] Write the equivalent detailed user guide for Clarvis-on-Hermes, including differences, limitations, and recommended usage patterns.
- [ ] [CLARVIS_FEATURES_REFERENCE] Produce a comprehensive feature reference covering memory, cron/autonomy, Claude delegation, browser abilities, project agents, install profiles, and operational boundaries.
- [ ] [CLARVIS_ONBOARDING_MESSAGE] Design an onboarding message/first-run briefing Clarvis can send automatically after installation so users immediately understand how he works and what to do next.
- [ ] [CLARVIS_HELP_COMMAND_SURFACE] Decide and implement the best discoverability surface: e.g. `/clarvis`, help skill, welcome command, or first-run menu that explains commands, modes, and capabilities.
- [ ] [CLARVIS_DIFFERENTIATION_DOC] Write a concise doc explaining what Clarvis provides over other agents/harnesses, when to use Clarvis vs plain OpenClaw/Hermes, and the unique value of the Clarvis layer.

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
- [ ] [OSS_PRIVATE_MD_AUDIT] Audit repo-tracked markdown/docs/config files and identify which ones are personal/install-specific/internal-only (research logs, archives, personal memory, operator-specific setup) and should be gitignored, moved out of the public repo, or replaced with safe examples/templates.
- [ ] [OSS_EXAMPLE_IDENTITY_FILES] Create public-safe example variants for personal/core identity files such as `SOUL.md`, `USER.md`, `IDENTITY.md`, and related operator-specific docs (e.g. `SOUL.md.example`) so the repo shows structure and guidance without exposing personal data or local setup.
- [ ] [OSS_RESEARCH_ARCHIVE_BOUNDARY] Define what research notes, archives, queue history, and cron logs belong in the repo vs local/private storage. Move or exclude install-specific, personal, and noisy historical artifacts accordingly.
- [ ] [SOUL_AGENT_DECONWAY_CLEANUP] Remove outdated Conway/business/crypto/autonomous-business goals from `SOUL.md`, `AGENTS.md`, and related identity docs where they no longer reflect Clarvis's intended direction. Keep the soul aligned with current purpose.

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

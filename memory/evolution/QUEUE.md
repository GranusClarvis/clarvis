# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._
_Caps: P0 ≤ 10, P1 ≤ 15. Triage before adding. See docs/PROJECT_LANES.md for rules._

## P0 — Current Sprint (2026-04-15)

### Critical Pipeline Fixes

- [x] **[FIX_POSTFLIGHT_BARE_IMPORTS]** _(2026-04-15)_ Fixed 8 bare imports in `heartbeat_postflight.py` → `_load_script()`. All now resolve: evolution_loop, extract_steps, benchmark_brief + 5 bonus (performance_benchmark, performance_gate, latency_budget, world_models, meta_gradient_rl).

### Execution Governance (added 2026-04-15 — prevents SWO-style drift)

- [~] **[SCRIPT_WIRING_AUDIT]** Audit 60+ unreferenced scripts in `scripts/`. For each: (a) if it has value, wire it to a cron job or pipeline caller, (b) if it's a one-off experiment, move to `data/archive/scripts/`, (c) if it's dead code, delete. Target: every script in `scripts/` has at least one caller within 14 days of creation. (2026-04-15: challenges/ audit done — 4/6 have tests, archived 2 uncalled scripts to data/archive/scripts/. Remaining: audit scripts/ root + subdirs.)

### Bugs


## P1 — This Week

### Star Sanctuary — Foundation PRs (PROJECT:SWO)

_SWO tasks tracked here. When project lane is active, these get priority. See also: memory/evolution/SWO_TRACKER.md_

- [x] **[SANCTUARY_TEST_FIXTURES]** _(2026-04-15)_ Created `lib/sanctuary/__tests__/fixtures.ts` (shared db factory, wallets, tokens) + `sanctuary.test.ts` (18 tests: ownership, state, switching, unauthorized access). All 32 sanctuary tests pass.
- [x] **[SANCTUARY_SUBSITE_SHELL]** _(2026-04-15)_ Built `/sanctuary` route: `page.tsx` + `SanctuaryContent.tsx` with AccessGate holder gating, public world map view, companion panel, journal panel. Added nav links in Header.tsx (desktop + mobile). Types clean, 101 tests pass.
- [ ] **[SANCTUARY_COMPANION_PANEL]** V1 companion dashboard: active Skrumpey, name, level, bond, mood, traits shell, current activity, journal snippet, and quick actions.

### Clarvis Maintenance — Keep Alive

- [ ] **[COGNITIVE_STACK_AB_TEST]** Run 5 tasks with full cognitive stack vs raw retrieval+LLM. Measure output quality delta. Answers: does the 22-module architecture produce better reasoning than a simple pipeline?
- [ ] **[EXECUTE_3_REASONING_CHALLENGES]** 15 reasoning challenges seeded weeks ago, zero executed. Run 3 this week and record artifacts.
- [ ] **[CLAUDE_SPAWN_LOCK_VISIBILITY]** Fix `spawn_claude.sh` so a held global Claude lock is surfaced explicitly as `DEFERRED/QUEUED/NOT_STARTED` instead of looking like a successful spawn.
- [ ] **[REASONING_DEPTH_EXPERIMENT_MEASURE]** Measure reasoning depth experiment results after 48h.
- [ ] **[FIX_STALE_PATHS_HEARTBEAT_AGENTS]** Fix stale script paths in `HEARTBEAT.md` and `AGENTS.md`.
- [ ] **[LLM_CONTEXT_REVIEW]** Raise DYCP_DEFAULT_SUPPRESS_CONTAINMENT_OVERRIDE from 0.10 to 0.20 for gwt_broadcast specifically.
- [ ] **[REMOVE_NANO_BANANA_LEAKED_KEY]** _(security)_ Remove orphaned `nano-banana-pro` skill + leaked Google Cloud API key from `openclaw.json`.

---

## P2 — When Idle

### Phi Recovery (0.620→0.65 target)

- [ ] **[PHI_EMERGENCY_CROSS_LINK_BLITZ]** Run targeted bulk_cross_link on all 45 collection pairs (Phi target).
- [ ] Cross-collection semantic bridging for Phi integration — 5 lowest-similarity pairs.
- [ ] Boost intra-density for starved collections — `clarvis-identity` (0.26), `clarvis-goals` (0.27), `autonomous-learning` (0.29).
- [ ] Expand clarvis-goals collection — add 10-15 goal memories referencing infra/identity/learning.
- [ ] Tune graph compaction aggressiveness + add Phi-guard (skip if Phi < 0.65).
- [ ] Add Phi-floor guard to graph_compaction.py before edge pruning.
- [ ] Audit graph edge-type distribution for integration balance.
- [ ] Diagnose near-zero bridge-type edges and fix bridging pipeline.
- [ ] Fix bulk_cross_link total_edges returning 0 in SQLite mode.
- [ ] Restore cross-collection bridge capacity in cron_reflection.sh.
- [ ] Widen Phi semantic_cross_collection sample from 8 to 20 queries.
- [ ] Add proactive Phi-gap-closing trigger in act_on_phi.
- [ ] Add Phi-below-target alert to health_monitor.sh.
- [ ] Add Phi semantic_cross_collection trend monitoring with weekly regression alerts.
- [ ] Purge synthetic 0%-progress goals polluting clarvis-goals.
- [ ] Fix phi_metric.py string references across hooks and brain_mem scripts.
- [ ] Fix dream_engine.py NoneType crash in compute_surprise() — nightly dream cycle dead.
- [ ] Add test coverage for cognition integration modules.

### Deep Cognition (Phase 4-5 gaps)

- [ ] Reasoning chain depth audit + multi-hop task.
- [ ] Tiered confidence action levels (Phase 3.1 gap).
- [ ] Autonomous code review of own scripts (Phase 3.3).
- [ ] Refactor knowledge_synthesis.py learning_strategy_analysis() to stay under 100-line limit.
- [ ] **[TEST_CAPABILITY_BOOTSTRAP]** Add spine module tests to lift test capability from 0.00.

### Cron / Non-Python Maintenance

- [ ] Sync crontab.reference with 3 undocumented live jobs.
- [ ] Fix openclaw.json Telegram topic system prompts with stale script paths.
- [ ] Remove placeholder goplaces API key from openclaw.json.
- [ ] Add worktree pruning to cron_cleanup.sh.
- [ ] Remove dead duplicate elif block in cron_env.sh.
- [ ] Reconcile @reboot boot sequence between crontab.reference and systemd.
- [ ] Clean stale `packages/` test checks from verify_install.sh.
- [ ] Stub or remove truly missing script references in skill SKILL.md files.
- [ ] Fix skill SKILL.md path errors.
- [ ] Fix Sunday cron learning-strategy relative path failure.
- [ ] Add env template setup guard for placeholder API keys.
- [ ] Remove stale `plugins.slots.contextEngine = "legacy"` from openclaw.json.
- [ ] Add 3 unbounded monitoring logs to cleanup_policy.py rotation table.
- [ ] Remove orphaned monitoring/cron_errors_daily.md or wire regeneration.
- [ ] Fix health_monitor.sh suspicious-process regex false positives.
- [ ] Fix broken cron_ok_count in health_monitor.sh.
- [ ] Add state-change dedup guard for health_monitor.sh brain-hygiene alerts.
- [ ] Purge ghost .pyc files for migrated scripts.
- [ ] Archive or refresh stale consciousness-research plan.
- [ ] Migrate 3 scripts off sys.path.insert to clarvis.* spine imports.
- [ ] Fix broken budget_alert.py path in heartbeat_postflight.py.
- [ ] Fix cron_orchestrator.sh Stage 4 silent failure.
- [ ] Fix lite_brain bare-name import breaking orchestrator retrieval score.
- [ ] Diagnose silent canonical_state_refresh.py cron failure.
- [ ] Add watchdog coverage for weekly cron jobs.
- [ ] Diagnose calibration_report.py permanent MISSED cron status.
- [ ] Revive security_monitor in health_monitor.sh or add dedicated cron.
- [ ] Fix heartbeat_postflight.py 3 silent bare-import failures.
- [ ] Add cron_morning.sh stale-queue audit step.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)

- [ ] **[CALIBRATION_CURVE_EMPTY_INPUT_GUARD]** `scripts/metrics/calibration_curve.py` divides by `total_n` in `generate_report()` — add empty-file guard.

### CLR Autonomy Dimension (critically low: 0.025)

### Claude Spawn Observability

- [ ] **[CLAUDE_SPAWN_STATUS_OBSERVABILITY]** Add clean status surface for Claude spawns: per-task state tracking.
- [ ] **[CLAUDE_SPAWN_DEFERRED_RETRY_POLICY]** Define behavior for lock-held spawns: reject loudly, queue explicitly, or auto-retry.

### Star Sanctuary — Later Phases (PROJECT:SWO)

#### First Playable Layer
- [ ] **[SANCTUARY_INTERACTABLES_V1]** Add first charming owner actions (feed, pet, talk, send-to-activity).
- [ ] **[SANCTUARY_WORLD_MAP_V1]** Create public/shared sanctuary map with locations.
- [ ] **[SANCTUARY_PROGRESS_BRIDGE]** Bridge SWO participation into Sanctuary progression.

#### Retention / Identity
- [ ] **[SANCTUARY_EXPEDITIONS_V1]** Short/medium activities returning journal events, resources, cosmetics.
- [ ] **[SANCTUARY_SHOP_V1]** First shop/inventory surface.
- [ ] **[SANCTUARY_PUBLIC_ACTIVITY_FEED]** Social feed layer.
- [ ] **[SANCTUARY_JOURNAL_SYSTEM]** Persistent companion journal/history.
- [ ] **[SANCTUARY_BALANCE_PASS_1]** Progression/reward cadence tuning.

#### V1.5 / Deeper Layer
- [ ] **[SANCTUARY_CHAT_ARCH_V1]** Lightweight companion-chat architecture design.
- [ ] **[SANCTUARY_COMPANION_CHAT_V1]** V1.5 personalized chat with active Skrumpey.
- [ ] **[SANCTUARY_TRAIT_EVOLUTION]** Derive visible companion traits from behavior patterns.
- [ ] **[SANCTUARY_SEASONAL_QUESTS_V1]** First seasonal quest/event layer.
- [ ] **[SANCTUARY_STAR_CURRENCY_DECISION]** STAR on Monad recommendation.

### Adaptive RAG Pipeline

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

---

## NEW ITEMS (2026-04-15 evolution scan)

- [ ] **[PHI_INTRA_DENSITY_DECAY_RATE]** Intra-collection density degrades to ~0.38 between weekly Sunday hygiene runs, dragging Phi below 0.65. Add a lightweight daily intra-density boost pass (mid-week, ~04:50 CET after graph compaction) that targets the 3 most starved collections. This directly addresses the weakest metric (Phi=0.636) by closing the repair-vs-decay gap. Non-Python: requires a new cron entry + small bash wrapper.
- [ ] **[FIX_ORCHESTRATOR_KEYERROR_QUERY]** `cron_orchestrator.sh` triggers `KeyError: 'query'` 18x on 2026-03-25 — task objects passed to the orchestrator lack a `query` field after a schema change. Audit the task dict contract between `task_selector.py` and the orchestrator, add the missing field or a safe `.get()` fallback.
- [ ] **[FIX_REPORT_EVENING_MISSING_RE_IMPORT]** `report_evening` cron heredoc hits `NameError: 're' is not defined` — the `import re` statement is unreachable in a conditional code path. Move the import to module top-level or add it inside the offending function.
- [ ] **[FIX_OPENCLAW_TOPIC_STALE_PATHS]** `openclaw.json` topics 2 and 5 reference pre-reorg script paths (`scripts/cost_tracker.py`, `scripts/brain.py`, `scripts/prompt_builder.py`). Topic 2's stale `prompt_builder.py` path silently breaks ACP context injection for every spawned task. Update all systemPrompt paths to current `scripts/infra/`, `scripts/brain_mem/`, `scripts/tools/` locations.

---

## Partial Items (tracked, not actively worked)

### External Challenges

---

## Research Sessions

# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._

## P0 — Current Sprint (2026-04-14)

### Today's Priorities (2026-04-14)

- [ ] **[SANCTUARY_ARCHITECTURE_DECISION_RECORD]** Write and lock the Star Sanctuary ADR: route=`/sanctuary`; public world visibility + holder-gated interactables; one active, switchable companion per wallet+specific Skrumpey with persistent progress; companion chat deferred to V1.5; on-chain vs off-chain boundary explicit; STAR currency direction to be evaluated deliberately.
- [ ] **[SANCTUARY_FIRST_PR_SPEC]** Define the first low-risk, mergeable SWO PR: existing-DB migration/schema additions for sanctuary state, active companion selection/fetch API, wallet↔specific-Skrumpey binding rules, switching semantics, and tests. Must be independently reviewable and unblock later UI work.
- [ ] **[SANCTUARY_DATA_MODEL_V1]** Implement the Star Sanctuary V1 data model in the real SWO backend using the cleanest table/entity shape available. Track: active companion, wallet+Skrumpey progress binding, mood/bond/level shell, current activity, room/loadout placeholders, and activity/journal seeds.

## P1 — This Week

### Star Sanctuary — Foundation PRs
- [ ] **[SANCTUARY_ACTIVE_COMPANION_API]** Add endpoints/loaders for: eligible owned Star Skrumpeys, selecting active companion, fetching sanctuary state, and switching active companion while preserving per-wallet+per-Skrumpey progress.
- [ ] **[SANCTUARY_BOOTSTRAP_STATE]** First-time Sanctuary bootstrap path: initialize a companion profile from owned Star metadata and create sane default state/journal/room placeholders.
- [ ] **[SANCTUARY_TEST_FIXTURES]** Create SWO fixtures/seeds for wallet ownership, companion state, switching, and unauthorized-access cases so future PRs have stable tests.
- [ ] **[SANCTUARY_SUBSITE_SHELL]** Build `/sanctuary` route shell with holder gating for interactables, public-view mode for the world layer, and navigation entry from existing SWO surfaces.
- [ ] **[SANCTUARY_COMPANION_PANEL]** V1 companion dashboard: active Skrumpey, name, level, bond, mood, traits shell, current activity, journal snippet, and quick actions.

### Star Sanctuary — First Playable Layer
- [ ] **[SANCTUARY_INTERACTABLES_V1]** Add the first charming owner actions (feed treat, pet/boop, talk-lite placeholder, send-to-activity) with delight-first behavior and no chore/punishment loop.
- [ ] **[SANCTUARY_WORLD_MAP_V1]** Create the public/shared sanctuary map showing Skrumpeys in locations like Lounge, Gym, Observatory, and Quest Gate; holder actions remain gated.
- [ ] **[SANCTUARY_PROGRESS_BRIDGE]** Bridge normal SWO participation into Sanctuary progression so the companion grows through actual site use (votes, raffles, hangout, visits, events) instead of chores.

### Star Sanctuary — Retention / Identity
- [ ] **[SANCTUARY_EXPEDITIONS_V1]** Add short/medium activities or quests that return journal events, resources, cosmetics hooks, or trait nudges.
- [ ] **[SANCTUARY_SHOP_V1]** Add the first Sanctuary shop/inventory surface for rooms, decor, cosmetics, and animation unlocks using soft-currency/account-bound progression.
- [ ] **[SANCTUARY_PUBLIC_ACTIVITY_FEED]** Add a social feed layer so users can see other Skrumpeys training, questing, lounging, or returning with discoveries.
- [ ] **[SANCTUARY_JOURNAL_SYSTEM]** Add persistent companion journal/history entries so each Skrumpey feels like it has a journey, not just stats.
- [ ] **[SANCTUARY_BALANCE_PASS_1]** Tune progression/reward cadence to avoid chores, dead time, or meaningless clicking. Include abuse considerations and soft-currency faucet/drain review.

### Star Sanctuary — V1.5 / Deeper Layer
- [ ] **[SANCTUARY_CHAT_ARCH_V1]** Design the lightweight companion-chat architecture (cheap API or local model), structured context assembly, prompt safety, memory budget, and fallback behavior.
- [ ] **[SANCTUARY_COMPANION_CHAT_V1]** Implement V1.5 personalized chat with the active Skrumpey using short, stylized, memory-aware responses.
- [ ] **[SANCTUARY_TRAIT_EVOLUTION]** Derive visible companion traits from actual behavior patterns (social, curious, council-wise, glitched, etc.) instead of arbitrary daily chores.
- [ ] **[SANCTUARY_SEASONAL_QUESTS_V1]** Add the first seasonal quest/event layer that plugs into Sanctuary progression and cosmetics.
- [ ] **[SANCTUARY_STAR_CURRENCY_DECISION]** Produce a deliberate recommendation for STAR on Monad: soulbound vs transferable vs hybrid; in-app uses; abuse/speculation risks; and what belongs on-chain vs off-chain for SWO.

### Clarvis Maintenance — Keep Alive but Demoted
- [ ] **[REASONING_DEPTH_EXPERIMENT_MEASURE]** Measure reasoning depth experiment results after 48h (`python3 scripts/experiments/capability_gap_experiment.py measure`).
- [ ] **[FIX_STALE_PATHS_HEARTBEAT_AGENTS]** Fix stale script paths in `HEARTBEAT.md` and `AGENTS.md`.
- [ ] **[ADD_WEEKLY_CRON_WATCHDOG_COVERAGE]** Add watchdog coverage for weekly cron jobs with silent-failure risk.
- [ ] **[TUNE_GRAPH_COMPACTION_PHI_GUARD]** Tune graph compaction aggressiveness and add a Phi guard.

---

## NEW ITEMS

- [ ] **Cross-collection semantic bridging for Phi integration** — Identify the 5 lowest-similarity collection pairs (e.g. goals↔infrastructure, identity↔episodes) and insert bridging memories that reference concepts from both sides, raising `semantic_cross_collection` toward 0.65 target. Measure before/after Phi decomposition.
- [ ] **Fix stale script paths in HEARTBEAT.md and AGENTS.md** — HEARTBEAT.md has 5 wrong paths (e.g. `scripts/brain.py` → `clarvis.brain`, `scripts/backup_daily.sh` → `scripts/infra/backup_daily.sh`); AGENTS.md has 5 more. Update all to current locations. (non-Python: mostly markdown edits)
- [ ] **Purge ghost .pyc files for migrated scripts** — 27 `.pyc` files in `scripts/` subdirs (`brain_mem/`, `cognition/`, `metrics/`, `hooks/`) have no corresponding `.py` source after spine migration. Verify each is superseded by a `clarvis/` module, then delete the stale `__pycache__` entries to prevent silent import of unmaintainable bytecode.
- [ ] **Fix skill SKILL.md path errors** — `iteration/SKILL.md` references `scripts/cron_autonomous.sh` (should be `scripts/cron/cron_autonomous.sh`); `clarvis-brain/SKILL.md` and `clarvis-cognition/SKILL.md` reference `scripts/brain.py` (should be `python3 -m clarvis brain`). These cause silent failures on skill invocation.
- [ ] **Archive or refresh stale consciousness-research plan** — `data/plans/consciousness-research.md` is 7+ weeks old with unresolved next-steps. Either update status of each item against current code and mark done/obsolete, or archive it. Keeps plans/ directory honest.
- [ ] **Boost intra-density for starved collections (Phi target)** — `clarvis-identity` (0.26), `clarvis-goals` (0.27), `autonomous-learning` (0.29) are far below TARGET_DEGREE=25. Run targeted `brain.bulk_cross_link()` on these three collections and re-measure Phi decomposition. Directly attacks weakest Phi sub-component (intra-density=0.44).
- [ ] **Sync crontab.reference with 3 undocumented live jobs** — `cron_llm_context_review.sh` (daily 06:40), `cron_calibration_report.sh` (Sun 06:45), `knowledge_synthesis.py learning-strategy` (Sun 05:25) are in live crontab but missing from `scripts/crontab.reference`. Also fix `cron_llm_brain_review` timing drift (06:20 live vs 06:15 ref). Non-Python: crontab + reference file edits.
- [ ] **Expand clarvis-goals collection for semantic bridging** — Only 10 documents in `clarvis-goals`, causing lowest semantic overlap pairs (goals↔infrastructure=0.465). Add 10-15 goal memories that reference infrastructure, identity, and learning concepts to close the semantic gap. Targets Phi `semantic_cross_collection` (0.66, weight 0.40).
- [ ] **Remove placeholder goplaces API key from openclaw.json** — `skills.entries.goplaces.apiKey` is set to `"XYZ123456"` (dummy value). Either configure a real key or remove the entry to prevent silent failures and avoid leaking config intent.
- [ ] **Tune graph compaction aggressiveness to protect Phi (Phi target)** — Phi dropped 0.734→0.619 while graph edges fell ~93k→80k. Review `graph_compaction.py` thresholds (orphan-edge cutoff, min-weight pruning) and raise the floor so compaction preserves edges critical to intra-density. Add a Phi-guard: skip compaction if Phi < 0.65. Directly addresses the root cause of the Phi decline, not just the symptom.
- [ ] **Reasoning chain depth audit + multi-hop task (reasoning_chains capability: 0.80)** — Audit the last 30 reasoning chains for average step count and branching depth. Identify the 5 shallowest chains that should have gone deeper. Then implement a "chain depth nudge" in `clarvis.cognition.reasoning` that flags chains closing with <3 steps on complex tasks and prompts re-expansion. Targets weakest capability after consciousness_metrics.
- [ ] **Tiered confidence action levels (Phase 3.1 gap)** — Implement HIGH/MEDIUM/LOW/UNKNOWN action tiers in heartbeat task selection, gated by domain-specific confidence thresholds. HIGH-confidence tasks execute autonomously; LOW triggers human-confirm or downgrades to research-only. Currently listed as open in ROADMAP Phase 3.1. Non-trivial: touches `heartbeat_preflight.py`, `clarvis_confidence.py`, and queue selection logic.
- [ ] **Autonomous code review of own scripts (Phase 3.3 + non-Python)** — Create a weekly cron job (`cron_self_code_review.sh`) that picks 3 random scripts from `scripts/`, spawns Claude Code to review them for dead code, stale imports, and correctness issues, and writes findings to `memory/cron/code_review_digest.md`. Non-Python: bash cron script + markdown output. Addresses ROADMAP Phase 3.3 "Autonomous code review of own scripts" gap.
- [ ] **Remove orphaned nano-banana-pro skill + leaked API key from openclaw.json (security)** — `skills.entries.nano-banana-pro.apiKey` contains a real Google Cloud API key (`AIzaSy...`) for a skill that doesn't exist in `skills/`. Remove the entire entry to prevent credential exposure. Non-Python: JSON config edit + verify no references elsewhere.
- [ ] **Fix openclaw.json Telegram topic system prompts with stale script paths** — Topics 2, 5, and 6 hardcode old paths (`scripts/prompt_builder.py`, `scripts/cost_tracker.py`, `scripts/budget_alert.py`, `scripts/health_monitor.sh`, `scripts/brain.py`). All moved to `scripts/tools/`, `scripts/infra/`, or `python3 -m clarvis brain`. Every Telegram `/costs`, health, and debug command silently fails. Non-Python: JSON config edits.
- [ ] **Purge synthetic 0%-progress goals polluting clarvis-goals (Phi target)** — 10 of 21 goals are auto-generated timestamp-ID entries injected by evolution crons, all at 0% progress. This inflates the collection with noise, degrading semantic bridging quality and starving Phi's `semantic_cross_collection` sub-metric. Remove synthetic entries, keep only the 11 named intentional goals, then re-measure Phi decomposition.
- [ ] **Add worktree pruning to cron_cleanup.sh** — `.claude/worktrees/` has 22 stale git worktrees (188MB). No cron job prunes them. Add a cleanup step to `scripts/cron/cron_cleanup.sh` that removes worktrees older than 7 days with no uncommitted changes. Non-Python: bash script edit.
- [ ] **Diagnose silent canonical_state_refresh.py cron failure** — Sunday 05:00 job runs but `memory/cron/canonical_state_refresh.log` is 0 bytes since Apr 10. Either the script exits on an early guard condition or the cron `cd` path fails before output. Diagnose root cause and fix so PI refresh data flows correctly.
- [ ] **Add watchdog coverage for weekly cron jobs** — `canonical_state_refresh.py` (Sun 05:00) and `knowledge_synthesis.py learning-strategy` (Sun 05:25) are live crontab entries with no `check_job` entry in `cron_watchdog.sh`. Silent failures go undetected indefinitely. Add both with 170h max-age window (weekly cadence). Non-Python: bash script edit.
- [ ] **Remove dead duplicate elif block in cron_env.sh** — Lines ~32-34 have two identical consecutive branches for `.env` loading (`if` then `elif` with same condition). The `elif` is unreachable dead code from a copy-paste error. Since `cron_env.sh` is sourced by 40+ cron scripts, the dead branch is a maintenance hazard. Non-Python: bash fix.
- [ ] **Reconcile @reboot boot sequence between crontab.reference and systemd** — `crontab.reference` documents `@reboot pm2 resurrect` and `@reboot start-chromium.sh` but neither exists in live crontab. Gateway is now systemd-managed (`openclaw-gateway.service`). Clarify whether PM2 @reboot was intentionally replaced, whether Chromium auto-start is still needed, and update reference + runbook to reflect actual boot sequence. Non-Python: docs + crontab.
- [ ] **Audit graph edge-type distribution for Phi integration balance (Phi target)** — Phi integration (0.619) may suffer from imbalanced edge types. Audit the SQLite graph for distribution of edge types (associative, temporal, causal, procedural) across collections. If any type is <5% of total edges or absent for key collection pairs, inject targeted edges to rebalance. Directly addresses Phi by improving structural integration diversity beyond raw density.
- [ ] **Diagnose near-zero bridge-type edges and fix bridging pipeline (Phi target)** — Only 42 of 80,561 graph edges are deliberate bridge types (`boosted_bridge`, `semantic_bridge`, `bridged_similarity`, `mirror_bridge`) vs 34,560 `cross_collection`. The bridging mechanism in `intra_density_boost.py` or `bulk_cross_link()` is either not producing bridge-typed edges or they're being compacted away. Diagnose why, fix the pipeline, and re-run for weakest pairs (goals↔preferences: 80 edges, goals↔context: 97 edges). Directly lifts Phi `cross_collection_connectivity` (0.545, weight 0.25).
- [ ] **Clean stale `packages/` test checks from verify_install.sh (non-Python)** — `scripts/infra/verify_install.sh` lines 145-171 count pytest output matching `^packages/` and emit WARN/PASS. Since `packages/` was removed (migrated to `clarvis/` spine 2026-04-03), this always warns, masking real test regressions. Update to check `clarvis/` spine test paths instead. Non-Python: bash script edit.
- [ ] **Stub or remove truly missing script references in skill SKILL.md files** — `clarvis-cognition/SKILL.md` and `spawn-claude/SKILL.md` reference scripts that don't exist anywhere: `phi_metric.py`, `episodic_memory.py`, `hebbian_memory.py`, `synaptic_memory.py`, `pr_autofix.py`. These were either never created or lost during migration. Either create stubs that delegate to the spine equivalent or remove the dead references. Distinct from path-fix task (those scripts exist at wrong paths; these don't exist at all).
- [ ] **Migrate 3 scripts off sys.path.insert to clarvis.* spine imports** — `brain_mem/intra_density_boost.py` (hardcoded absolute path), `cron/calibration_report.py`, and `cognition/knowledge_synthesis.py` use `sys.path.insert` instead of `clarvis.*` imports. This violates the import convention, breaks portability, and risks importing stale modules. Refactor each to use spine imports per CLAUDE.md convention.
- [ ] **Fix broken budget_alert.py path in heartbeat_postflight.py** — Line ~1724 resolves `budget_alert.py` relative to `scripts/pipeline/` via `os.path.dirname(__file__)`, but the script lives at `scripts/infra/budget_alert.py`. Budget checks silently fail on every postflight run. Fix the path resolution to point to the correct location.
- [ ] **Add test coverage for cognition integration modules (Phi target)** — `clarvis/cognition/conceptual_framework.py` and `clarvis/cognition/obligations.py` are actively imported by heartbeat preflight/postflight and context assembly but have zero test coverage. Add basic tests to `tests/` for both modules. These power the conceptual integration layer that feeds Phi's cross-collection connectivity; untested bugs here silently degrade Phi.
- [ ] **Fix cron_orchestrator.sh Stage 4 silent failure (non-Python)** — `cron_orchestrator.sh` (19:30 daily) calls `python3 -m clarvis.orch.scoreboard record` at Stage 4, but this module entry point may not exist or may error silently. Stage 4 has failed silently every night without detection. Diagnose whether `clarvis.orch.scoreboard` has a working `__main__` or CLI entry point, fix or create it, and add error handling to the cron script. Non-Python: bash cron script + Python module fix.
- [ ] **Remove stale `plugins.slots.contextEngine = "legacy"` from openclaw.json (non-Python)** — The `contextEngine` plugin slot is set to `"legacy"` but is not referenced anywhere in the codebase (`clarvis/`, `scripts/`). The context layer has migrated to `clarvis/context/assembly.py` with `generate_tiered_brief()`. This dead config entry misleads audits into thinking a legacy code path is still active. Remove it. Non-Python: JSON config edit.
- [ ] **Investigate 2026-04-13 graph verification failure + 9.1% edge drop (Phi target)** — `brain_hygiene_alerts.log` logged "Graph verification failed — skipping optimize to prevent corruption" on 2026-04-13, followed by edges dropping 70,288→63,903 (9.1% loss). Root cause unknown — may be WAL corruption, concurrent access during compaction, or a schema drift. Diagnose from logs and SQLite state, fix the verification logic or the underlying corruption, and recover lost edges if possible. Directly impacts Phi (0.628) since edge count drives intra-density.
- [ ] **Add 3 unbounded monitoring logs to cleanup_policy.py rotation table (non-Python)** — `monitoring/wiki_hooks.log`, `monitoring/brain_hygiene_alerts.log`, and `monitoring/context_relevance_trend.log` grow without bound — only the 4 main logs are in `cleanup_policy.py`'s rotation config. Add all three with sensible max-size/max-age thresholds matching existing log policy. Non-Python: Python config + monitoring hygiene.
- [ ] **Add env template setup guard for placeholder API keys (non-Python)** — `config/profiles/openclaw.env.template` contains `OPENROUTER_API_KEY=sk-or-v1-your-key-here` as a literal placeholder. Fresh installs silently send requests with this invalid key, producing confusing 401 errors. Add a startup guard in `cron_env.sh` or gateway init that fails loudly if the key matches the placeholder pattern. Non-Python: bash/config edit.
- [ ] **Fix phi_metric.py string references across hooks and brain_mem scripts (Phi target)** — `scripts/hooks/intra_linker.py`, `scripts/brain_mem/retrieval_benchmark.py`, and `scripts/cognition/knowledge_synthesis.py` reference `phi_metric.py` by name in strings, docs, or dynamic imports. The module migrated to `clarvis.metrics.phi` (spine). Update all references so Phi measurement is consistently invoked via the spine path. Distinct from sys.path migration task (those are import statements; these are string/doc references).
- [ ] **Boost intra-density for infrastructure/context/procedures collections (Phi target)** — `clarvis-infrastructure` (0.395), `clarvis-context` (0.394), and `clarvis-procedures` (0.407) have the lowest intra-collection density scores, dragging down Phi's `intra_collection_density` sub-component (0.593). Run targeted `brain.bulk_cross_link()` on these three starved collections and re-measure. Prior boost task addressed identity/goals/autonomous-learning — this covers the remaining bottleneck trio. Directly lifts Phi toward 0.65 target.
- [ ] **Fix Sunday cron learning-strategy relative path failure (non-Python)** — Sunday 05:25 `knowledge_synthesis.py learning-strategy` cron entry uses paths that don't resolve without an explicit `cd $CLARVIS_WORKSPACE` prefix. The job runs but may silently produce no output. Add proper `cd` and verify log output in `memory/cron/learning_strategy.log`. Non-Python: crontab edit.
- [ ] **Refactor knowledge_synthesis.py learning_strategy_analysis() to stay under 100-line function limit** — `learning_strategy_analysis()` at line ~309 in `scripts/cognition/knowledge_synthesis.py` is 135 lines, exceeding the project's function-length quality gate. Extract 2-3 helper functions (e.g., metric collection, strategy comparison, report generation) to bring each under 100 lines without changing behavior.
- [ ] **Add Phi-floor guard to graph_compaction.py before edge pruning (Phi target)** — `graph_compaction.py` prunes edges aggressively without checking Phi impact. Add a pre-compaction Phi measurement and abort if Phi < 0.64 (just below target). This prevents the compaction→Phi-drop spiral seen in the 93k→80k edge loss event. Complements the existing "tune compaction aggressiveness" task by adding a hard safety gate rather than just threshold tuning.

---

## P2 — When Idle

### Phi Recovery (0.620→0.65 target, added 2026-04-12)

### Deep Cognition (Phase 4-5 gaps)

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)

### CLR Autonomy Dimension (critically low: 0.025)

### Adaptive RAG Pipeline

### Cron Schedule Hygiene (non-Python)

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

### Cron / Non-Python (2026-04-09 evolution)

---

## Partial Items (tracked, not actively worked)

### External Challenges
















---

## Research Sessions

# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by queue_auto_archive.py to QUEUE_ARCHIVE.md._
_Caps: P0 ≤ 10, P1 ≤ 15. Triage before adding. See docs/PROJECT_LANES.md for rules._
_Deep audit tracker: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` (existing P1 audit items map to phases there — do not duplicate)._

## P0 — Current Sprint (2026-04-15)

_Audit-phase override: while executing the deep Clarvis audit plan, do not suppress or skip justified follow-up queue items merely because P1 is over cap. Audit-derived findings may add P1/P2 tasks when they are necessary to preserve audit continuity and evidence integrity. Triage still applies, but cap pressure must not block recording valid findings._

### Critical Pipeline Fixes


### Deep Audit (anchor for canonical audit tracker)

- [ ] **[AUDIT_PHASE_0_INSTRUMENTATION]** Implement the Phase 0 measurement substrate that blocks every downstream audit phase: (1) per-spawn `audit_trace_id` linking preflight→execution→postflight→outcome, (2) `data/audit/traces/<date>/<id>.json` writer with ≥45d retention, (3) `data/audit/feature_toggles.json` registry supporting `shadow` mode, (4) `scripts/audit/trace_exporter.py` CLI, (5) `scripts/audit/replay.py` for deterministic prompt rebuild. PASS gate: ≥95% of real Claude spawns in a 7-day window have a complete recoverable trace. Canonical plan: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`.

### Execution Governance (added 2026-04-15 — prevents SWO-style drift)

- [ ] **[AUDIT_PHASE_QUEUE_CAP_OVERRIDE]** Add an explicit exception to queue-cap enforcement during the deep Clarvis audit program so audit phases can record justified follow-up tasks without being blocked by P1 caps. Preserve anti-bloat behavior for normal autonomous injection, but do not let cap logic suppress evidence-backed audit findings.

### Bugs


## P1 — This Week

### Star Sanctuary — Foundation PRs (PROJECT:SWO)

_SWO tasks tracked here. When project lane is active, these get priority. See also: memory/evolution/SWO_TRACKER.md_

- [ ] **[SWO_MIRROR_BASELINE_VALIDATION]** Validate the new local SWO mirror end-to-end: service status, DB integrity, app reachable on 127.0.0.1:3080, and baseline `npm run lint`, `npm run type-check`, `npm run test`, `npm run build` from `/opt/star_world_order/PROD`. Record anything that differs from expected mirror behavior.
- [ ] **[SWO_PR178_LINT_CLEANUP]** Follow-up from SWO_MERGED_PR_VERIFICATION. Replace 28 `any` usages introduced by PR #178 in `lib/sanctuary/__tests__/sanctuary.test.ts` (13 sites), `lib/sanctuary/__tests__/db.test.ts`, and `lib/db.ts:274` with narrow sanctuary row types. `npm run lint` on those files currently reports 28 errors / 7 warnings; goal is zero errors in PR #178-added files. Small PR, no runtime impact.
- [ ] **[SWO_PR177_REVALIDATION]** Re-check whether PR #177 (server-side governance voting power verification) is still valid against current SWO `dev` after recent repo changes. Confirm whether the original vulnerability path still exists or has already been superseded, evaluate mergeability/conflicts, and decide whether to revive, replace, or close it. Source context: PR #177 fixed client-supplied votingPower spoofing by verifying Star ownership on-chain. Source: `memory/cron/agent_star-world-order_digest.md#L1-L21`
- [ ] **[SWO_SERVER_TRUST_BOUNDARY_AUDIT]** Identify every SWO endpoint or flow that currently trusts client-supplied values (wallet, voting power, tier, price, token eligibility, raffle entry counts, admin state). Mark which are server-verified vs spoofable and prioritize fixes.
- [ ] **[SWO_SECURITY_THREAT_SURFACE_AUDIT]** Run a focused security audit of SWO: wallet auth, holder gating, governance/voting, raffle entry validation, marketplace/listing flows, server trust boundaries, API authorization, client-trust assumptions, contract/version drift, and obvious attack vectors or abuse paths. Output should become concrete reviewable tasks/PRs, not just a vague report.



### Clarvis Maintenance — Keep Alive

- [ ] **[CONTEXT_ASSEMBLY_QUALITY_REGRESSION_AUDIT]** Audit whether context assembly quality has regressed over the last few days despite the recent deep spine/context audit. Compare current prompt/context outputs against the intended standard across project work, research, and debugging tasks. Focus on missing context, bad ordering, over-compression, stale sections, and low-signal noise.
- [ ] **[PROMPT_ASSEMBLY_OUTCOME_VALIDATION]** Validate prompt-builder and context-brief quality against actual task outcomes rather than token budgets. Use representative tasks to determine where prompt assembly is under-serving project execution or introducing noise.
- [ ] **[QUEUE_AUTOFILL_DISCIPLINE_AUDIT]** Review queue auto-injection/auto-fill behavior for low-value churn, stale self-work bias, and mismatch with operator-directed project priorities. Tighten so queue filling improves execution quality instead of clutter.
- [ ] **[BRAIN_AND_SPINE_POST_AUDIT_GAP_REVIEW]** Revisit the major spine/brain/context research and audit work from ~4 days ago and identify what still has not translated into better behavior. Focus on context, prompt assembly, queue behavior, brain usefulness, and spine integration quality — not just whether files or modules exist.
- [ ] **[SPINE_FEATURE_WIRING_AND_QUALITY_PASS]** Audit key spine features for real wiring and output quality: context assembly, prompt builder, queue engine/writer, relevant framework injection, and brain-backed retrieval paths. Add or schedule the smallest fixes needed where behavior is weaker than intended.
- [ ] **[WIKI_USEFULNESS_GAP_AUDIT]** Audit the current wiki subsystem for actual usefulness vs implementation completeness. Determine which parts are production-useful, half-done, or decorative. Focus on whether wiki compile/index/retrieval/sync paths are being used in real task execution and whether they improve answers, planning, or project work.
- [ ] **[WIKI_PRODUCT_TO_EXECUTION_BRIDGE]** If the wiki has value, define and implement the smallest path that makes it materially useful in execution (e.g. retrieval routing, evidence loading, project briefs, or operator-facing lookup). If it does not yet add value, demote it from active cognitive importance instead of pretending it is core.
- [ ] **[COGNITION_FEATURE_TRANSLATION_REVIEW]** Review neuroscience/paper-inspired features for translation quality: which ones improve execution, retrieval, or project work, and which are mostly conceptually elegant but operationally weak. Produce a keep / revise / demote / archive classification.
- [ ] **[CONSCIOUSNESS_EMULATION_BLOAT_GUARD]** Add an explicit anti-bloat review pass for consciousness-/neuroscience-inspired features. Any feature justified mainly by theory/aesthetics must show value in one of: task success, retrieval quality, prompt quality, planning quality, or operator usefulness. Otherwise demote it from active priority.
- [ ] **[EXECUTION_FIRST_COGNITION_POLICY]** Define and apply a simple policy: cognitive features are justified by better execution, not by resemblance to consciousness on paper. Use it to triage active cognition/spine tasks and reduce low-value complexity.
- [ ] **[BRAIN_WIKI_CONTEXT_ROUTE_BENCH]** Benchmark four routes on representative tasks: raw brain recall, wiki-first retrieval, combined brain+wiki, and minimal direct context. Compare usefulness, noise, and task outcome quality so the system stops guessing which route is best.
- [ ] **[LOW_VALUE_FEATURE_DEMOTION_SWEEP]** Sweep active queue/cognition work for features that add complexity without clear output quality gains. Demote or archive them, especially where they were added to half-emulate consciousness or satisfy paper-derived architecture goals without translating into practical benefit.

- [ ] **[PROMPT_CONTEXT_QUALITY_POLICY_REVIEW]** Re-evaluate the current prompt/context token limits (including the ~1000-token ceiling) strictly from outcome quality, prompt quality, and project-task success — not cost minimization. Determine whether richer context should be allowed by default and propose/implement the smallest safe policy improvement.
- [ ] **[EVENING_CODE_REVIEW_ERRORS_TRIAGE]** Review the issues surfaced by the latest evening code review, turn them into concrete reliability fixes, and prioritize the ones that affect smooth day-to-day operation.


---

## P2 — When Idle

### Deep Audit Follow-ups (from Phase 1 — `docs/internal/audits/SCRIPT_WIRING_INVENTORY_2026-04-16.md`)

- [ ] **[METACOGNITION_WIRE_VERIFY]** `clarvis/cognition/metacognition.py` is test-only — no production importer found, despite its own docstring claiming to be the canonical import site. Confirm whether the heartbeat pipeline should import `check_step_quality`/`coherence`/`brier` from it; if yes, restore the wire (likely regression from the packages→spine migration). Feeds Phase 2 spine-quality scorecard.
- [ ] **[SPINE_CLI_ONLY_MODULES_PHASE_9_INTAKE]** Four spine modules are live only by `python3 -m` contract with no importing caller: `clarvis/brain/spr.py`, `clarvis/brain/llm_rerank.py`, `clarvis/metrics/clr_reports.py`, `clarvis/metrics/evidence_scoring.py`. Surface them as Phase 9 EVS/TCS inputs (low attribution, non-trivial TCS). `spr.py`/`llm_rerank.py` touch retrieval/Phi subcomponents — require operator signoff (§0.3.5) before any move past SHADOW.

### Phi Monitoring / Validation (demoted — regression watch, not optimization target)

- [~] **[PHI_EMERGENCY_CROSS_LINK_BLITZ]** Run targeted bulk_cross_link on all 45 collection pairs (Phi target). (2026-04-16: started full-brain bulk_cross_link but process killed at ~5min when cron_autonomous started; +1357 edges committed before kill. Follow-up pair-targeted pass below supplanted the remainder.)
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

### 2026-04-16 evolution scan

- [ ] **[PHI_PAIR_BRIDGE_PRIORITIZATION]** Identify the 5 collection pairs with BOTH lowest semantic similarity AND lowest edge count, then queue targeted bridge memories that cite concepts from both sides. Current bulk_cross_link treats all pairs equally; starved pairs (e.g. `clarvis-identity` ↔ `autonomous-learning`) need hand-authored bridges, not random sampling. Directly targets Phi=0.619 (weakest metric).
- [ ] **[TEST_PHI_METRIC_REGRESSION_HARNESS]** Add `tests/test_phi_metric.py` that snapshots current phi subcomponent scores (intra_density, cross_connectivity, semantic_cross_collection, reachability) and fails if any regress >5%. Dual-purpose: bootstraps test capability (currently 0.00) AND guards the weakest metric against silent regressions introduced by graph compaction or hygiene passes.
- [ ] **[HEARTBEAT_PHI_FAST_PATH_DOC]** _(non-Python — markdown)_ Update `HEARTBEAT.md` to document a Phi-below-target fast path: when `phi < 0.65`, heartbeat preflight MUST select a queued `PHI_*` task before running attention scoring. Codifies the policy so the behavior is durable across reorgs and visible to future operators. Pairs with the existing `act_on_phi` hook.
- [ ] **[CRON_LANE_CONSOLIDATION_AUDIT]** _(non-Python — audit + docs)_ Audit all 47 cron entries in `crontab.reference`, classify each into a lane (brain/cognitive/maintenance/project/reporting), and produce `docs/CRON_LANES.md` mapping. Currently there's no single source of truth for "which cron touches Phi" vs "which cron rotates logs" — this blocks targeted Phi-recovery interventions and makes merge-freeze reasoning hard. Deliverable: docs + a linting comment block in crontab.reference.

---

## Partial Items (tracked, not actively worked)

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:reasoning-depth-04] Build a causal inference engine for episode outcome analysis — Given episode data (task, actions, outcome), build a lightweight causal model: which actions most influence success/failure? Use counterfactual analysis (if action X hadn't happened, would outcome cha

---

## Research Sessions

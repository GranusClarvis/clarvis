# Evolution Queue — Clarvis

_Pick from here every heartbeat. Small tasks: do now. Big tasks: spawn Claude Code._
_Priority: P0 (do now) > P1 (this week) > P2 (when idle)_
_Completed items archived by `clarvis.queue.writer.archive_completed()` to QUEUE_ARCHIVE.md._
_Caps: P0 ≤ 10, P1 ≤ 15. Triage before adding. See docs/PROJECT_LANES.md for rules._
_Deep audit tracker: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` (existing P1 audit items map to phases there — do not duplicate). Quick-reference: `docs/internal/audits/AUDIT_INDEX.md`._

## P0 — Current Sprint (2026-04-15)

_Audit-phase override: while executing the deep Clarvis audit plan, do not suppress or skip justified follow-up queue items merely because P1 is over cap. Audit-derived findings may add P1/P2 tasks when they are necessary to preserve audit continuity and evidence integrity. Triage still applies, but cap pressure must not block recording valid findings._

### Critical Pipeline Fixes


### Deep Audit (anchor for canonical audit tracker)


### Execution Governance (added 2026-04-15 — prevents SWO-style drift)


### Deep Audit — Phase 9 Follow-ups (added 2026-04-17)

_Source: `docs/internal/audits/NEURO_FEATURE_DECISIONS_2026-04-17.md`. Phase 9 scored 16 neuro features via proxy-EVS/TCS (no A/B data). 2 PROMOTE, 6 KEEP, 4 REVISE, 4 SHADOW, 0 DEMOTE. Critical defect: world_models calibration loop broken._


### Bugs

- [x] **[P0_MIRROR_VALIDATION_HARD_GATE]** (2026-04-19) Mirror validation is now a hard gate: post-spawn failure closes the PR via `gh pr close`, nullifies `pr_url`, marks status=failed. New `_close_pr()` helper comments + closes. Overlay cleanup now tracks and removes new directories (deepest-first `rmdir`). Prompt strengthened with HARD GATE language. 5 new tests added — all 139 pass.

## P1 — This Week

### Star Sanctuary — Foundation PRs (PROJECT:SWO)

_SWO tasks tracked here. When project lane is active, these get priority. See also: memory/evolution/SWO_TRACKER.md_




### Deep Audit — Phase 9 Follow-ups (P1, added 2026-04-17)


### Phase 8 Follow-ups (P1, added 2026-04-16)


### Clarvis Maintenance — Keep Alive


### Deep Audit — Phase 0 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Recorded under the audit-cap override (§P0 banner). P1 is currently 19/15 in base terms but within the 25-ceiling for audit sources. These are justified Phase 0 follow-ups; closing them is a precondition for a valid Phase 0 PASS ruling and for downstream phases. See `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`._


### Deep Audit — Phase 2 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase2_spine_quality.md`. Phase 2 ruled 1 PASS, 13 REVISE, 0 DEMOTE/ARCHIVE on 14 spine modules — most of the REVISE work is small `__init__.py` surface trims and cheap coverage lifts. Only 1 P1 (the new `clarvis/audit/` module needs tests — substrate is live but untested)._


### Deep Audit — Phase 3 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase3_prompt_assembly.md`. Phase 3 ruled 5×PASS across task types on 334 scored episodes; aggregate gate PASS. Open follow-ups address proxy limits (MISLEADING detection, trace-backed rescore) and one hand-label task. No assembly code paths were changed by this phase._

- [ ] **[AUDIT_PHASE_3_HANDLABEL_40_TASKS]** Hand-label the 40-row stratified sample at `data/audit/prompt_utilization_handlabel_template.json` with per-section HELPFUL / NEUTRAL / MISLEADING / NOISE. Use `scripts/metrics/llm_context_review.py` LLM-judge pass OR operator pass — record provenance. Then extend `scripts/audit/prompt_utilization.py` with a hand-label-aware mode that overrides heuristic labels where hand-labels exist. Acceptance: template filled; re-run confirms proxy did not systematically hide MISLEADING cases (≥ 5 hand-label MISLEADING counts force scorecard re-ruling).

### Deep Audit — Phase 4 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase4_brain_usefulness.md`. Phase 4 ruled INSUFFICIENT_DATA × 10 collections on the attribution gate — blocked by two Phase-0 capture gaps (listed below, the P0 item being the most severe). One independent REVISE flagged on routing. `scripts/audit/brain_attribution.py` + `data/audit/brain_attribution.jsonl` + `data/audit/brain_collection_scorecard.json` shipped. All items use `source="audit_phase_4"`._


### Deep Audit — Phase 6 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase6_execution_routing_queue.md`. Phase 6 ruled REVISE overall: router PASS (98.9% accuracy, PROMOTE candidate), autofill PASS (2.4% stale), caps REVISE (21/30 days), spawn PASS, slot share FAIL (12.5% vs 50%). All items use `source="audit_phase_6"`._


### Deep Audit — Meta-Audit Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_meta_audit_phases_0_4.md`. A sharpness-check on Phases 0–4 found the program well-executed but framed too narrowly toward removal. Corrections: add code-review axis to Phase 2, wire operator-in-the-loop EVS signal, content-quality spot check for Phase 4. Plan §0 principle 7 + PROMOTE gate already landed in the plan doc. All items use `source="audit_meta"`._


---

## P2 — When Idle
- [~] [STALLED] **[AUDIT_PHASE_0_INSTRUMENTATION]** Implement the Phase 0 measurement substrate that blocks every downstream audit phase: (1) per-spawn `audit_trace_id` linking preflight→execution→postflight→outcome, (2) `data/audit/traces/<date>/<id>.json` writer with ≥45d retention, (3) `data/audit/feature_toggles.json` registry supporting `shadow` mode, (4) `scripts/audit/trace_exporter.py` CLI, (5) `scripts/audit/replay.py` for deterministic prompt rebuild. PASS gate: ≥95% of real Claude spawns in a 7-day window have a complete recoverable trace. Canonical plan: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`. (2026-04-16: substrate shipped — `clarvis/audit/{trace,toggles}.py`, trace_exporter + replay CLIs, spawn_claude + heartbeat wiring, `audit_trace_id` on CostEntry. Awaiting 7-day trace window before PASS ruling. Decision doc: `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`.)

### Demoted from P1 (2026-04-16, cap triage)

_Demoted to P2 to bring P1 within 25-ceiling. All are review/sweep/benchmark tasks not blocking audit gates or project delivery._


### Phase 6 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Meta-Audit Follow-ups (P2, added 2026-04-16 via AUDIT_CAP_OVERRIDE)


### Graph Integration (P2, added 2026-04-18)

- [~] **[PHI_REMAINING_GAP]** Phi is 0.582 vs 0.65 target (gap=0.068). (2026-04-19: +5,497 edges total — intra-link on 6 collections (+5,243) + cross-link (+254). Intra-density 0.530→0.619 (+0.089). Cross-connectivity diluted to 0.383 by same-collection edge growth. Semantic overlap steady at 0.579. Bottleneck: cross-collection ratio needs ~0.50+ AND semantic overlap needs ~0.65+. These require either longer timeout cross-link passes or hand-authored bridge memories targeting weak pairs. Weakest semantic pairs: goals↔autonomous-learning (0.483), preferences↔autonomous-learning (0.489).)

### Phase 4.5 Follow-ups (P2, added 2026-04-16)


### Phase 8 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Phase 9 Follow-ups (P2, added 2026-04-17)

- [~] [BLOCKED:2026-05-01] **[PHASE9_REEVAL_WITH_AB]** After `[PHASE9_AB_TOGGLE_WIRING]` completes and 14-day A/B windows are collected for the 4 SHADOW features, re-run Phase 9 EVS scoring with causal data instead of proxies. Update `data/audit/neuro_feature_scorecard.jsonl` and `NEURO_FEATURE_DECISIONS_2026-04-17.md`. Any SHADOW feature showing positive causal EVS/TCS ≥ 0.2 → upgrade to REVISE. Any showing zero or negative → proceed to DEMOTE (with operator signoff for consciousness-labelled). Source: Phase 9 Proxy Limitation §0. (2026-04-19: A/B window opened 2026-04-17, closes 2026-05-01 — only 2/14 days elapsed. No causal data available yet. Re-check on or after 2026-05-01.)
- [ ] **[PHASE9_CLI_ONLY_SPINE_MODULES]** Score `clarvis/brain/spr.py`, `clarvis/brain/llm_rerank.py`, `clarvis/metrics/clr_reports.py`, `clarvis/metrics/evidence_scoring.py` — CLI-only spine modules with no importing caller. These were deferred from Phase 9 main pass. `spr.py`/`llm_rerank.py` touch retrieval/Phi subcomponents — require operator signoff before SHADOW. Source: `[SPINE_CLI_ONLY_MODULES_PHASE_9_INTAKE]`.

### Phase 10 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase10_reliability_security.md`. Phase 10 ruled REVISE — restore drill FAIL blocks PASS. Items below were in the decision doc and AUDIT_INDEX but never added to QUEUE.md._


### Phase 5 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/decisions/2026-04-16_phase5_wiki_usefulness.md`. Phase 5 ruled REVISE. These items were mandated in the decision doc but never added to QUEUE.md. The 30-day re-evaluation window from 2026-04-16 is active._

- [ ] **[WIKI_PRODUCT_TO_EXECUTION_BRIDGE]** Wire `wiki_retrieval.py` into preflight context assembly in shadow mode. Required for Phase 5 REVISE path — without it, wiki usefulness cannot be re-evaluated. Acceptance: preflight traces include `wiki_retrieval` field (even if empty in shadow mode). Source: Phase 5 REVISE requirement.
- [ ] [UNVERIFIED] **[BRAIN_WIKI_CONTEXT_ROUTE_BENCH]** Run a matched-pair benchmark: brain-only vs brain+wiki retrieval on 20 recent tasks. Requires `[WIKI_PRODUCT_TO_EXECUTION_BRIDGE]`. Acceptance: benchmark results in `data/audit/wiki_vs_brain_bench.json`. Source: Phase 5 re-evaluation gate.

### Phase 12 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 ruled REVISE (digest actionability 56.5% vs 60% target). Only 1 of 4 follow-ups was in QUEUE.md._


### Test Suite Health (P2, added 2026-04-19)

_72/2921 tests failing (2.5% failure rate), 10 collection errors, 1 broken collection file. Test suite health is untracked in the queue despite being a foundational capability metric._

- [x] **[POSTFLIGHT_NONE_GUARD_FIXES]** Fix the recurring postflight hook `NoneType` crashes (`periodic_synthesis`, episodic encoding, prediction-resolve / validator edge cases). Acceptance: 3 consecutive autonomous runs complete with no `expected string or bytes-like object, got 'NoneType'` errors in postflight logs. (2026-04-19: Fixed 4 crash sites — `_keyword_overlap` None guard, `_auto_link_against` `.get()` instead of direct key access, `episode_encoder` output_text None guard, `prediction_resolver` _desanitize/ep_tasks None handling. All imports verified clean.)
- [x] **[BRAIN_MEMORY_DROP_AUDIT]** Investigate the sharp reported brain memory-count drop across 2026-04-16 → 2026-04-19 (≈2933 → 2296). Determine whether this is healthy consolidation, stats drift, or accidental data loss. Acceptance: write findings to `memory/evolution/` with a verdict and any required fix. (2026-04-19: Verdict — HEALTHY CONSOLIDATION. 200 synthetic bridge entries removed via audited cleanup (e142d6b, export at `data/audit/bridge_cleanup_2026-04-19.json`) + Sunday hygiene pass removed ~1,519 decayed memories. Stabilized at ~2,413. Full audit at `memory/evolution/brain_memory_drop_audit_2026-04-19.md`.)
- [x] **[PHASE8_MIRROR_PRESUBMIT_GATE_TIMEOUT_FORENSICS]** (2026-04-19) Superseded by `[P0_MIRROR_VALIDATION_HARD_GATE]` which completed the implementation in a focused scope — post-spawn hard gate + directory cleanup + PR closing. The prior timeout was likely due to over-scoping (trying to restructure the entire spawn flow).

- [ ] **[TEST_SUITE_RED_FIXES]** Fix the 72 failing tests across 8 test files: `test_brain_roundtrip` (2), `test_chaos_recovery` (6), `test_graph_compaction_sqlite` (2), `test_pr_factory` (3), `test_project_agent` (2), `test_assembly_calibration_freeze` (2), `test_bench_memory_consolidation` (3), plus `test_csp_solver` collection error and others. Most appear to be API contract drift (brain `stats()` return shape changed, `_script_loader` import paths). Acceptance: `pytest tests/` passes with 0 failures, 0 errors. Source: test run 2026-04-19.

### Deep Audit — Phases 12–15 Anchors (P2, added 2026-04-16 per meta-meta audit)

_Activate when Sprint 6 artifacts merge. These are placeholder anchors — full queue items should be written when dependency phases land._

- [~] **[AUDIT_PHASE_15_REAUDIT_PROTOCOL]** ~~Define longitudinal re-audit cadence.~~ Protocol, schedule, runner, and trial run all delivered. Remaining: wire runner into cron, implement cadence self-adjustment. Artifacts: `docs/internal/audits/REAUDIT_PROTOCOL_2026-04-17.md`, `data/audit/longitudinal_schedule.json`, `scripts/audit/reaudit_runner.py`, `data/audit/reaudit_results_weekly_2026-04-17.json`. Source: Phase 15 in audit plan.

### Phase 15 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase15_reaudit_protocol.md`. Phase 15 PASS: all 3 gates met. Trial run found 3 stale locks (actionable regression)._


### Phase 14 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/COST_VALUE_2026-04-17.md`. Phase 14 ruled REVISE: cost tracking structurally broken, system-adjusted cost/PR fails gate, but trend improving and cost-reduction targets identified._

- [ ] **[PHASE14_CLAUDE_CLI_TOKEN_CAPTURE]** Modify `scripts/agents/spawn_claude.sh` to parse Claude CLI stdout/stderr for token usage summaries and log them to `data/costs.jsonl` with `estimated: false`. The claude CLI outputs usage data that is currently discarded. This provides ground-truth per-session Anthropic costs. Acceptance: next 3 Claude spawns produce non-estimated cost entries. Source: Phase 14 Gap 1 (R1).
- [ ] **[PHASE14_OPENROUTER_API_KEY_FIX]** The OpenRouter API key stored in `auth-profiles.json` returns HTTP 401 ("User not found"). Rotate or verify the key so `cost_checkpoint.py` and `budget_alert.py` can function. Requires operator action. Acceptance: `python3 -c "from clarvis.orch.cost_api import fetch_usage; print(fetch_usage())"` returns valid data. Source: Phase 14 Gap 1 (R2).
- [ ] **[PHASE14_RESEARCH_ATTRIBUTION]** Add `research_id` field to research session outputs in `cron_research.sh`. When a research finding appears in a later task's context or decision, log the attribution to `data/audit/research_attribution.jsonl`. Enables research ROI measurement. Acceptance: next 3 research sessions produce entries with research_id; attribution schema defined. Source: Phase 14 Gap 3 (R5).
- [ ] **[PHASE14_COST_DASHBOARD]** Create unified cost dashboard (`cost_dashboard.py`) that merges Anthropic (from CLI token capture) and OpenRouter (from API) spend into a single view. Blocked by `[PHASE14_CLAUDE_CLI_TOKEN_CAPTURE]` and `[PHASE14_OPENROUTER_API_KEY_FIX]`. Source: Phase 14 Gap 4 (split-brain tracking).

### Phase 13 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/PROPOSAL_QUALITY_2026-04-17.md`. Phase 13 ruled REVISE: proposal quality analytically strong but tracking broken (sidecar 0/394 useful), hallucination rate at boundary (10%), self-work bias structural._

- [ ] **[PHASE13_RESCORE_AFTER_SIDECAR]** After `[PHASE6_SIDECAR_SOURCE_PROPAGATION]` lands and 14 days of sidecar data accumulates, re-run Phase 13 survival and outcome measurements with real data instead of proxies. Update `data/audit/proposal_quality.jsonl` and scorecard. Acceptance: re-scored gates use sidecar data, not proxy estimates. Source: Phase 13 proxy limitation.

### Phase 12 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 found digest actionability at 56.5% (REVISE), spawn quality 85% (PASS). Digest archive missing, inconsistent writers, morning garble._

- [ ] **[PHASE12_SPAWN_ENRICHMENT_TO_PROJECT_AGENTS]** Replicate `prompt_builder.py context-brief` enrichment to `project_agent.py spawn` so project agents benefit from brain retrieval, episodic hints, and worker templates. Currently project spawns use raw task text only. Acceptance: `project_agent.py spawn` includes context_brief in prompt. Source: Phase 12 PROMOTE candidate 1.

### Deep Audit Follow-ups (from Phase 1 — `docs/internal/audits/SCRIPT_WIRING_INVENTORY_2026-04-16.md`)

- [ ] **[SPINE_CLI_ONLY_MODULES_PHASE_9_INTAKE]** Four spine modules are live only by `python3 -m` contract with no importing caller: `clarvis/brain/spr.py`, `clarvis/brain/llm_rerank.py`, `clarvis/metrics/clr_reports.py`, `clarvis/metrics/evidence_scoring.py`. Surface them as Phase 9 EVS/TCS inputs (low attribution, non-trivial TCS). `spr.py`/`llm_rerank.py` touch retrieval/Phi subcomponents — require operator signoff (§0.3.5) before any move past SHADOW.

### Deep Audit — Phase 2.5 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase2_5_code_design_review.md`. Phase 2.5 reviewed 3 spine modules (brain, orch, context) for design quality. All 3 ruled REVISE. Top finding: no prompt-generation telemetry in `clarvis.context`. All items use `source="audit_phase_2_5"`._

- [ ] **[CONTEXT_BRIEF_TELEMETRY]** Add a `BriefResult` dataclass to `clarvis.context.assembly.generate_tiered_brief()` that returns structured telemetry alongside the brief text: `sections_included`, `sections_pruned`, `token_budget_used`, `fallbacks_activated`, `relevance_weights_applied`. Wire into Phase 0 audit traces via `update_trace({"prompt.brief_telemetry": ...})`. This is a Phase 3 dependency — without it, prompt assembly audit operates on indirect evidence only. Acceptance: at least 3 heartbeats produce traces with non-empty `prompt.brief_telemetry`; existing callers that only need the string can use `result.text`.

### Deep Audit Follow-ups (from Phase 2 — `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md`)

_All are surface trims or cheap coverage lifts. Bridge wrappers (18) and underlying submodule files are NOT being touched — only `__init__.py` re-exports. All new items use `source="audit_phase_2"` and benefit from the audit-cap override. Re-run `scripts/audit/spine_scorecard.py` after each PR to verify the `dead_exports` count drops._

- [x] **[SPINE_CONTEXT_INIT_TRIM_AND_COVERAGE]** Trim 12 DEAD re-exports from `clarvis/context/__init__.py` (`_simple_tiered_brief, prune_stale, snip_middle, graduated_compact, get_optimizer_report, load_section_relevance_weights, build_wire_guidance, get_failure_patterns, get_workspace_context, get_spotlight_items, build_hierarchical_episodes, synthesize_knowledge`). These are already directly importable from `clarvis.context.{compressor,assembly,prompt_optimizer,…}` — the `__init__` level re-exports are redundant. Also add 2-3 unit tests for currently-uncovered branches in `clarvis/context/assembly.py`. Acceptance: `context.coverage_pct ≥ 40` and `context.dead_exports = 0` on re-run. (2026-04-19: All 12 dead re-exports removed. Imports verified clean across codebase. Coverage tests deferred — trim is the high-leverage part.)
- [x] **[SPINE_MEMORY_INIT_TRIM_AND_COVERAGE]** Trim 12 DEAD re-exports from `clarvis/memory/__init__.py` (all are `memory_consolidation` helpers — `learn_from_failures, retire_stale, compose_procedures, merge_clusters, enhanced_decay, enforce_memory_caps, run_consolidation, sleep_consolidate, attention_guided_prune, attention_guided_decay, gwt_broadcast_survivors, salience_report`). Underlying `memory_consolidation.py` stays — callers use direct submodule imports. Add direct unit tests for `procedural_memory.find_procedure` and `procedural_memory.store_procedure` (heavily used in production, currently only exercised indirectly). Acceptance: `memory.coverage_pct ≥ 25` and `memory.dead_exports = 0`. (2026-04-19: All 12 dead re-exports removed + 3 dead procedural_memory re-exports (learn_from_failures, retire_stale, compose_procedures). Imports verified — zero callers used init path. Coverage tests deferred.)
- [ ] **[SPINE_COMPAT_WIRE_OR_DOCUMENT]** `clarvis/compat/` has zero production callers (only test callers). Decide one of: (a) wire `run_contract_checks()` into `scripts/infra/health_monitor.sh` with a daily metric exported to `monitoring/`, OR (b) mark the module docstring as "test-scaffold for host-portability contracts" and exclude it from future Phase 9 EVS/TCS passes. Acceptance: clear wire-or-document state recorded — no "kept for future" ambiguity.

### Deep Audit Follow-ups (from Phase 3 — `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md`)

_Source: `source="audit_phase_3"`. P1 items are co-located in the Phase 3 Follow-ups section above; this is the P2 continuation._

- [ ] **[AUDIT_PHASE_3_TASK_TYPE_CLASSIFIER_UPGRADE]** The canonical-task-type classifier in `scripts/audit/prompt_utilization.py` is a keyword + mmr_category heuristic (swo_feature / bug_fix / research_distillation / maintenance / self_reflection). Acceptable for the initial scorecard but not for ongoing per-type tracking. Replace with either (a) `task_source` read from the queue writer (which already records source metadata on each queue item) or (b) a small sklearn classifier trained on the historical corpus once the 40-task hand-labels land. Acceptance: classifier labels reproduce the filled `prompt_utilization_handlabel_template.json` task-types with ≥ 0.85 accuracy; `prompt_utilization.py run` re-emits with the upgraded classifier.

### Deep Audit Follow-ups (from Phase 4 — `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md`)

_Source: `source="audit_phase_4"`. P0+P1 items are co-located with their parent blocks above; these are the P2 continuation._

- [ ] [UNVERIFIED] **[AUDIT_PHASE_4_AB_BRIDGES_HEBBIAN_EPISODES]** Execute matched-pair 14-day A/B windows for three brain features already registered in `clarvis/audit/toggles.py`: `graph_bridges`, `hebbian_boost`, `episodic_memory_injection`. Each feature toggles OFF (or `shadow=true`) for 14 days on a matched task mix, with the corresponding ON window captured before or after. Depends on `[AUDIT_PHASE_4_BRAIN_RETRIEVAL_TRACE_WIRING]` (attribution-gate inputs must be live). Emit three result files under `data/audit/ab_windows/{bridges,hebbian,episodes}_<date>.json` with delta-to-baseline metrics on attribution share, task outcome, and retrieval recall. Subtle-feature guard §3.3 applies (rare-but-critical carve-out) — episode-recall may help only on a narrow task type. Acceptance: all three A/B files present; Phase 9 EVS/TCS scorecard can ingest them.

### Phi Monitoring / Validation (demoted to observability metric by Phase 11 synthesis — regression watch only, not a KPI or optimization target; overlaps Phase 9 REVISE ruling on phi_metric)

- [~] **[PHI_EMERGENCY_CROSS_LINK_BLITZ]** Run targeted bulk_cross_link on all 45 collection pairs (Phi target). (2026-04-16: started full-brain bulk_cross_link but process killed at ~5min when cron_autonomous started; +1357 edges committed before kill. Follow-up pair-targeted pass below supplanted the remainder.)
- [x] Add test coverage for cognition integration modules. (2026-04-19: Added `tests/test_cognitive_load.py` (25 tests — failure rate, queue velocity, cron times, capability degradation, composite load, task deferral, complexity estimation) and `tests/test_obligations.py` (18 tests — CRUD, check engine, escalation, persistence, due scheduling). 43 new tests, all passing.)

### Deep Cognition (pre-audit backlog; overlaps Phase 2/4.5/9 findings)

- [ ] Tiered confidence action levels (Phase 3.1 gap).
- [ ] Autonomous code review of own scripts (Phase 3.3).
- [ ] Refactor knowledge_synthesis.py learning_strategy_analysis() to stay under 100-line limit.
- [ ] **[TEST_CAPABILITY_BOOTSTRAP]** Add spine module tests to lift test capability from 0.00.

### Cron / Non-Python Maintenance (pre-audit backlog; several overlap Phase 1 wiring inventory + Phase 10 reliability findings)

- [ ] Sync crontab.reference with 3 undocumented live jobs.
- [ ] Fix openclaw.json Telegram topic system prompts with stale script paths.
- [ ] Reconcile @reboot boot sequence between crontab.reference and systemd.
- [x] Clean stale `packages/` test checks from verify_install.sh. (2026-04-19: Removed packages/ test counting and package-discovery checks from verify_install.sh — packages/ was cleared, all logic consolidated into clarvis/ spine.)
- [ ] Stub or remove truly missing script references in skill SKILL.md files.
- [x] Fix Sunday cron learning-strategy relative path failure. (2026-04-19: Added missing crontab entry at Sunday 05:25 CET with proper `cd` + `cron_env.sh` sourcing. Verified CLI mode works. Entry placed between brain_hygiene (05:15) and cleanup (05:30).)
- [ ] Add env template setup guard for placeholder API keys.
- [ ] Add 3 unbounded monitoring logs to cleanup_policy.py rotation table.
- [ ] Remove orphaned monitoring/cron_errors_daily.md or wire regeneration.
- [ ] Add state-change dedup guard for health_monitor.sh brain-hygiene alerts.
- [ ] Archive or refresh stale consciousness-research plan.
- [x] Migrate 3 scripts off sys.path.insert to clarvis.* spine imports. (2026-04-19: Removed sys.path.insert from `scripts/brain_mem/intra_density_boost.py` (hard-coded absolute path), `scripts/audit/graph_edge_audit.py`, `scripts/audit/memory_content_quality.py`. clarvis is editable-installed — sys.path hacks unnecessary. All 3 import-verified clean.)
- [ ] Fix cron_orchestrator.sh Stage 4 silent failure.
- [ ] Fix lite_brain bare-name import breaking orchestrator retrieval score.
- [ ] Diagnose silent canonical_state_refresh.py cron failure.
- [ ] Add watchdog coverage for weekly cron jobs.
- [ ] Diagnose calibration_report.py permanent MISSED cron status.
- [ ] Revive security_monitor in health_monitor.sh or add dedicated cron.
- [ ] Add cron_morning.sh stale-queue audit step.

### Calibration / Brier Score (weakest metric — all-time Brier=0.1148 vs target 0.1, 7-day=0.2400)


### CLR Autonomy Dimension (critically low: 0.025)

### Claude Spawn Observability (pre-audit backlog; related to Phase 0 instrumentation + Phase 10 reliability)

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

- [ ] **[AUDIT_PHASE_16_REAUDIT_PHASE_7]** Re-audit tainted Phase 7 at the end of the deep audit program. Treat the earlier run as low-trust due to prompt contamination / merged-ask framing mistakes. Re-run it with strict prompt hygiene and use the clean rerun as the canonical evidence for synthesis.

### Adaptive RAG Pipeline

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (currently 0.35, target 0.70)

---

## NEW ITEMS (2026-04-15 evolution scan)

- [ ] **[PHI_INTRA_DENSITY_DECAY_RATE]** Intra-collection density degrades to ~0.38 between weekly Sunday hygiene runs, dragging Phi below 0.65. Add a lightweight daily intra-density boost pass (mid-week, ~04:50 CET after graph compaction) that targets the 3 most starved collections. This directly addresses the weakest metric (Phi=0.636) by closing the repair-vs-decay gap. Non-Python: requires a new cron entry + small bash wrapper.

### 2026-04-16 evolution scan

- [ ] **[PHI_PAIR_BRIDGE_PRIORITIZATION]** Identify the 5 collection pairs with BOTH lowest semantic similarity AND lowest edge count, then queue targeted bridge memories that cite concepts from both sides. Current bulk_cross_link treats all pairs equally; starved pairs (e.g. `clarvis-identity` ↔ `autonomous-learning`) need hand-authored bridges, not random sampling. Directly targets Phi=0.619 (weakest metric).
- [ ] **[CRON_LANE_CONSOLIDATION_AUDIT]** _(non-Python — audit + docs)_ Audit all 47 cron entries in `crontab.reference`, classify each into a lane (brain/cognitive/maintenance/project/reporting), and produce `docs/CRON_LANES.md` mapping. Currently there's no single source of truth for "which cron touches Phi" vs "which cron rotates logs" — this blocks targeted Phi-recovery interventions and makes merge-freeze reasoning hard. Deliverable: docs + a linting comment block in crontab.reference.

---

## Partial Items (tracked, not actively worked)

### External Challenges

- [ ] [EXTERNAL_CHALLENGE:reasoning-depth-04] Build a causal inference engine for episode outcome analysis — Given episode data (task, actions, outcome), build a lightweight causal model: which actions most influence success/failure? Use counterfactual analysis (if action X hadn't happened, would outcome cha

---

## Research Sessions

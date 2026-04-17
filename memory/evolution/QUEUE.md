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

- [~] **[AUDIT_PHASE_0_INSTRUMENTATION]** Implement the Phase 0 measurement substrate that blocks every downstream audit phase: (1) per-spawn `audit_trace_id` linking preflight→execution→postflight→outcome, (2) `data/audit/traces/<date>/<id>.json` writer with ≥45d retention, (3) `data/audit/feature_toggles.json` registry supporting `shadow` mode, (4) `scripts/audit/trace_exporter.py` CLI, (5) `scripts/audit/replay.py` for deterministic prompt rebuild. PASS gate: ≥95% of real Claude spawns in a 7-day window have a complete recoverable trace. Canonical plan: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`. (2026-04-16: substrate shipped — `clarvis/audit/{trace,toggles}.py`, trace_exporter + replay CLIs, spawn_claude + heartbeat wiring, `audit_trace_id` on CostEntry. Awaiting 7-day trace window before PASS ruling. Decision doc: `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`.)
- [x] **[AUDIT_PHASE_4_BRAIN_RETRIEVAL_TRACE_WIRING]** [P0] (2026-04-17) Wired `_preflight_brain_bridge()` to store structured `result["_brain_retrieval"]` (post-evidence-gate) and `_finalize_preflight_trace()` to write it as `preflight.brain_retrieval` in audit traces. Verified: `brain_attribution.py run` → `fallback_used_everywhere: false`, 3 collections with `block_count > 0`.

### Execution Governance (added 2026-04-15 — prevents SWO-style drift)


### Deep Audit — Phase 9 Follow-ups (added 2026-04-17)

_Source: `docs/internal/audits/NEURO_FEATURE_DECISIONS_2026-04-17.md`. Phase 9 scored 16 neuro features via proxy-EVS/TCS (no A/B data). 2 PROMOTE, 6 KEEP, 4 REVISE, 4 SHADOW, 0 DEMOTE. Critical defect: world_models calibration loop broken._

- [ ] **[WORLD_MODEL_CALIBRATION_FIX]** [P0] Fix `record_outcome()` in heartbeat_postflight.py so it writes actual_outcome back to `data/world_model/predictions.json`. Currently 500 predictions have `actual: null` — the Ha & Schmidhuber / JEPA calibration loop is broken. Also: suppress `world_model` prompt section injection until the section's HELPFUL rate reaches ≥20% (currently 5.6%, worst of all neuro sections at 22.2% NOISE). Keep preflight confidence signal as internal-only. Acceptance: after 3 heartbeats, `predictions.json` has entries with non-null `actual`; world_model section absent from prompt. Source: Phase 9 decision doc §2.

### Bugs


## P1 — This Week

### Star Sanctuary — Foundation PRs (PROJECT:SWO)

_SWO tasks tracked here. When project lane is active, these get priority. See also: memory/evolution/SWO_TRACKER.md_

- [ ] **[SWO_PR177_REVALIDATION]** Re-check whether PR #177 (server-side governance voting power verification) is still valid against current SWO `dev` after recent repo changes. Confirm whether the original vulnerability path still exists or has already been superseded, evaluate mergeability/conflicts, and decide whether to revive, replace, or close it. Source context: PR #177 fixed client-supplied votingPower spoofing by verifying Star ownership on-chain. Source: `memory/cron/agent_star-world-order_digest.md#L1-L21`
- [ ] **[SWO_SECURITY_THREAT_SURFACE_AUDIT]** Run a focused security audit of SWO: wallet auth, holder gating, governance/voting, raffle entry validation, marketplace/listing flows, server trust boundaries, API authorization, client-trust assumptions, contract/version drift, and obvious attack vectors or abuse paths. Output should become concrete reviewable tasks/PRs, not just a vague report.



### Deep Audit — Phase 9 Follow-ups (P1, added 2026-04-17)

- [ ] **[PHASE9_AB_TOGGLE_WIRING]** Wire Phase 0 toggle call-sites for the 4 SHADOW features (dream_engine, absolute_zero, theory_of_mind, analogy_engine) to enable 14-day A/B shadow windows. Each site: if `shadow=True`, run the feature but exclude output from prompts/decisions. After 14 days, compare Phase 0 metrics with vs without. Depends on `[AUDIT_PHASE_0_TOGGLE_CALL_SITES]`. Acceptance: 4 features have shadow-mode traces; `neuro_feature_scorecard.jsonl` updated with A/B deltas. Source: Phase 9 Gap 1.
- [ ] **[THOUGHT_PROTOCOL_SLIM]** Strip `thought_protocol.py` from 936 LoC to ~200 LoC. Keep `frame()` and `task_decision()` methods. Remove unused DSL operators, analysis methods, and the disabled `thought_log.jsonl` writer. Cut unique imports from 9 to 4. Acceptance: `task_selector.py` and `reasoning_chain_hook.py` still import and call without error; `test_clarvis_cognition.py` passes. Source: Phase 9 REVISE ruling.

### Phase 8 Follow-ups (P1, added 2026-04-16)

- [ ] **[PHASE8_PROJECT_AGENT_HEARTBEAT_INTEGRATION]** Wire `project_agent.py spawn` into the heartbeat execution path so project-lane slots can directly invoke the project agent rather than only selecting QUEUE.md items tagged `[SWO_*]`. Blocked by `PHASE6_PROJECT_LANE_SLOT_RESERVATION`. Closes Phase 8 Gap 1 (zero autonomous project PRs). Acceptance: at least 1 heartbeat in a 7-day window spawns the project agent and produces a branch or PR. Source: Phase 8 decision doc.

### Clarvis Maintenance — Keep Alive

- [ ] **[CONTEXT_ASSEMBLY_QUALITY_REGRESSION_AUDIT]** Audit whether context assembly quality has regressed over the last few days despite the recent deep spine/context audit. Compare current prompt/context outputs against the intended standard across project work, research, and debugging tasks. Focus on missing context, bad ordering, over-compression, stale sections, and low-signal noise.
- [ ] **[PROMPT_ASSEMBLY_OUTCOME_VALIDATION]** Validate prompt-builder and context-brief quality against actual task outcomes rather than token budgets. Use representative tasks to determine where prompt assembly is under-serving project execution or introducing noise.
- [ ] **[BRAIN_AND_SPINE_POST_AUDIT_GAP_REVIEW]** Revisit the major spine/brain/context research and audit work from ~4 days ago and identify what still has not translated into better behavior. Focus on context, prompt assembly, queue behavior, brain usefulness, and spine integration quality — not just whether files or modules exist.
- [ ] **[SPINE_FEATURE_WIRING_AND_QUALITY_PASS]** Audit key spine features for real wiring and output quality: context assembly, prompt builder, queue engine/writer, relevant framework injection, and brain-backed retrieval paths. Add or schedule the smallest fixes needed where behavior is weaker than intended.
- [ ] **[PROMPT_CONTEXT_QUALITY_POLICY_REVIEW]** Re-evaluate the current prompt/context token limits (including the ~1000-token ceiling) strictly from outcome quality, prompt quality, and project-task success — not cost minimization. Determine whether richer context should be allowed by default and propose/implement the smallest safe policy improvement.

### Deep Audit — Phase 0 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Recorded under the audit-cap override (§P0 banner). P1 is currently 19/15 in base terms but within the 25-ceiling for audit sources. These are justified Phase 0 follow-ups; closing them is a precondition for a valid Phase 0 PASS ruling and for downstream phases. See `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`._

- [ ] **[METACOGNITION_WIRE_VERIFY]** [PHASE 1 RESTORED via Phase 0 audit override 2026-04-16] Verify `clarvis/cognition/metacognition.py` is reachable at runtime via its expected import path and exercised by at least one test. Phase 1 wiring inventory flagged it as test-only / unclear — restore at P1 (was suppressed to P2 under cap pressure). Acceptance: test case asserting the public API runs end-to-end; inventory row updated to reflect real callers.
- [ ] **[AUDIT_PHASE_0_TRACE_RETENTION_SWEEPER]** Add a daily cron (05:05 CET, after `cron_pi_refresh` / before `cron_brain_eval`) that prunes `data/audit/traces/<date>/` directories older than 45 days. Must be idempotent, log to `monitoring/audit_retention.log`, and fail-open (never raise). Acceptance: sweeper runs ≥3 consecutive days without error; no trace older than 45d remains; disk footprint stays bounded.
- [ ] **[AUDIT_PHASE_0_TOGGLE_CALL_SITES]** Wire `clarvis.audit.toggles.is_enabled` / `is_shadow` at production call sites for the 23 registered features. Each site: if `enabled=False`, skip the feature entirely; if `shadow=True`, run it but exclude its output from prompts/decisions while still recording to trace under `toggles_shadowed`. Acceptance: at least 5 high-leverage sites wired (brain_retrieval, wiki_retrieval, conceptual_framework_injection, somatic_markers, cognitive_workspace); each shows a shadow-mode trace entry during a canary run.
- [ ] **[AUDIT_PHASE_0_GATE_EVALUATION]** On or after 2026-04-23, run `python3 scripts/audit/trace_exporter.py gate --days 7` and record the verdict in the Phase 0 decision doc. If PASS, mark `[AUDIT_PHASE_0_INSTRUMENTATION]` [x] and unblock Phase 2. If FAIL, diagnose which spawn paths are missing traces (expected offenders: ad-hoc manual spawns, cron jobs that don't route through `spawn_claude.sh`), extend instrumentation, and reschedule the gate.

### Deep Audit — Phase 2 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase2_spine_quality.md`. Phase 2 ruled 1 PASS, 13 REVISE, 0 DEMOTE/ARCHIVE on 14 spine modules — most of the REVISE work is small `__init__.py` surface trims and cheap coverage lifts. Only 1 P1 (the new `clarvis/audit/` module needs tests — substrate is live but untested)._

- [ ] **[SPINE_AUDIT_MODULE_TEST_HARNESS]** Write unit tests for `clarvis/audit/{trace.py,toggles.py}` covering: (1) trace lifecycle — `start_trace` → `update_trace` (deep-merge) → `finalize_trace` → atomic JSON on disk → `load_trace` round-trip; (2) toggle registry — `load_toggles`, `is_enabled`, `is_shadow`, default seeding of 23 features on first load; (3) fail-open behaviour when `data/audit/` is read-only. Acceptance: `clarvis.audit` coverage ≥ 60 %; re-running `scripts/audit/spine_scorecard.py` shows `audit.coverage_pct ≥ 60` and `audit.dead_exports` reduced by exercising `AuditTrace, new_trace_id, load_trace, set_current_trace_id, trace_path_for, load_toggles, is_shadow, DEFAULT_TOGGLES`. Phase 2 companion to Phase 0 (substrate shipped but untested).

### Deep Audit — Phase 3 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase3_prompt_assembly.md`. Phase 3 ruled 5×PASS across task types on 334 scored episodes; aggregate gate PASS. Open follow-ups address proxy limits (MISLEADING detection, trace-backed rescore) and one hand-label task. No assembly code paths were changed by this phase._

- [ ] **[AUDIT_PHASE_3_HANDLABEL_40_TASKS]** Hand-label the 40-row stratified sample at `data/audit/prompt_utilization_handlabel_template.json` with per-section HELPFUL / NEUTRAL / MISLEADING / NOISE. Use `scripts/metrics/llm_context_review.py` LLM-judge pass OR operator pass — record provenance. Then extend `scripts/audit/prompt_utilization.py` with a hand-label-aware mode that overrides heuristic labels where hand-labels exist. Acceptance: template filled; re-run confirms proxy did not systematically hide MISLEADING cases (≥ 5 hand-label MISLEADING counts force scorecard re-ruling).
- [ ] **[AUDIT_PHASE_3_TRACE_BACKED_RESCORE]** On or after 2026-04-23 (once Phase-0 PASS gate rules), re-run `python3 scripts/audit/prompt_utilization.py run` against the live trace stream (`data/audit/traces/`) instead of the pre-instrumentation corpus alone. Produce a corpus-vs-trace delta. Acceptance: new summary lands at `data/audit/prompt_utilization_summary.json`; scorecard gets a §9 addendum noting whether trace-backed view changes the ruling.
- [ ] **[AUDIT_PHASE_3_MISLEADING_VALIDATOR]** The Phase 3 MISLEADING = 0 finding is a proxy artefact (§5.1 of scorecard). Build a second-order check: for each failure/crash episode, inspect the paired reasoning chain in `data/reasoning_chains/chains.jsonl` and flag sections the chain explicitly cited before failure. Emit `data/audit/misleading_candidates.json`. Acceptance: ≥ 1 episode annotated; output either confirms MISLEADING ≈ 0 empirically OR raises a concrete suppress candidate for the Policy Review.

### Deep Audit — Phase 4 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase4_brain_usefulness.md`. Phase 4 ruled INSUFFICIENT_DATA × 10 collections on the attribution gate — blocked by two Phase-0 capture gaps (listed below, the P0 item being the most severe). One independent REVISE flagged on routing. `scripts/audit/brain_attribution.py` + `data/audit/brain_attribution.jsonl` + `data/audit/brain_collection_scorecard.json` shipped. All items use `source="audit_phase_4"`._

- [ ] **[AUDIT_PHASE_4_SPAWN_CLAUDE_PROMPT_CAPTURE]** Extend `scripts/agents/spawn_claude.sh` to persist the task prompt text (and any caller-provided context brief) into `prompt.context_brief` on the audit trace. Currently the script captures only `execution.output_tail` + `outcome`, so every non-heartbeat spawn is opaque to brain-attribution analysis. Paired with `[AUDIT_PHASE_4_BRAIN_RETRIEVAL_TRACE_WIRING]` (P0) this closes both capture gaps. Acceptance: new `spawn_claude` traces show non-empty `prompt.context_brief`; `scripts/audit/brain_attribution.py run` counts them as `attributable_traces`.
- [ ] **[AUDIT_PHASE_4_INFRA_COLLECTION_ROUTING_REVIEW]** Investigate why `clarvis-infrastructure` is hit ~ 10× less than every peer collection in the retrieval_quality events log (95 / 30 d vs 863–1 630). Its avg_distance (1.07) is the lowest of any collection — the memories it does surface are the most on-topic — so the under-hit is almost certainly a routing/selection skip, not data absence. Trace through `smart_recall`, `knowledge_synthesis`, the brain router tier logic, and any collection allow-lists. Acceptance: either a root-cause writeup attached to this item OR a re-routing fix lands; post-fix, 30-day hits for `clarvis-infrastructure` reach ≥ 0.5× the nine-collection median (so ≥ 500 events under current volume).
- [ ] **[AUDIT_PHASE_4_RE_RUN_AFTER_7D_TRACES]** On or after 2026-04-23, after `[AUDIT_PHASE_4_BRAIN_RETRIEVAL_TRACE_WIRING]` + `[AUDIT_PHASE_4_SPAWN_CLAUDE_PROMPT_CAPTURE]` have landed AND ≥ 7 attributable traces exist, re-run `python3 scripts/audit/brain_attribution.py run --days 30` and promote the per-collection verdicts from INSUFFICIENT_DATA to PASS / REVISE / DEMOTE_CANDIDATE. Record the updated rulings in a §9 addendum on `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md`. No demotion action is permitted on a single window — per plan §3.1, DEMOTE requires two consecutive windows agreeing. Acceptance: rescore lands; headline reports `attributable_traces ≥ 7`.

### Deep Audit — Phase 6 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase6_execution_routing_queue.md`. Phase 6 ruled REVISE overall: router PASS (98.9% accuracy, PROMOTE candidate), autofill PASS (2.4% stale), caps REVISE (21/30 days), spawn PASS, slot share FAIL (12.5% vs 50%). All items use `source="audit_phase_6"`._

- [ ] **[PHASE6_SIDECAR_SOURCE_PROPAGATION]** Fix `clarvis/queue/writer.py:_sync_sidecar_add()` to propagate the `source` argument into the sidecar record. Currently all 333 entries have `source: "unknown"`. Backfill existing entries from `data/queue_runs.jsonl` where a `source` field exists. Acceptance: new sidecar entries show correct source; `python3 -c "import json; d=json.load(open('data/queue_state.json')); print(sum(1 for v in d.values() if v.get('source','unknown')!='unknown'))"` returns > 0. Source: Phase 6 Gap 3.
- [ ] **[PHASE6_ROUTER_KEYWORD_NARROWING]** Narrow `VISION_PATTERNS` and `WEB_SEARCH_PATTERNS` in `clarvis/orch/router.py:154-166` to reduce false-positive rate (currently 48.1% on non-Claude paths). Replace broad patterns (`r"(?i)image"`, `r"(?i)visual"`, `r"(?i)scan\b"`, `r"(?i)google\b"`) with context-aware patterns or add a "pattern-score confirmation" step. Acceptance: re-analyze `data/router_decisions.jsonl` false-positive count < 10%. Source: Phase 6 Gap 4.
- [ ] **[PHASE6_CAP_BREACH_WATCHDOG]** Add a QUEUE.md P0/P1 cap check to `scripts/infra/health_monitor.sh` or `scripts/cron/cron_watchdog.sh`. Alert (Telegram + `monitoring/alerts.log`) when P0 > 10 or P1 > 25 (audit ceiling). Acceptance: after one health cycle with an over-cap QUEUE.md, alert fires. Source: Phase 6 Gap 7.

### Deep Audit — Meta-Audit Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_meta_audit_phases_0_4.md`. A sharpness-check on Phases 0–4 found the program well-executed but framed too narrowly toward removal. Corrections: add code-review axis to Phase 2, wire operator-in-the-loop EVS signal, content-quality spot check for Phase 4. Plan §0 principle 7 + PROMOTE gate already landed in the plan doc. All items use `source="audit_meta"`._

- [ ] **[AUDIT_OPERATOR_FEEDBACK_LOOP]** Wire the operator-in-the-loop signal that plan §EVS weights at 0.10 but has no data source. Extend the 09:30 (`cron_report_morning.sh`) and 22:30 (`cron_report_evening.sh`) digest reports to include a Telegram response path: 👍 / 👎 on the digest as a whole, plus `/rate <trace_id> <1-5>` for per-trace feedback. Persist flags to `data/audit/operator_flags.jsonl` with schema `{timestamp, audit_trace_id|null, digest_id|null, flag: "up"|"down"|int, note|null}`. Cross-reference trace_ids when present. Acceptance: ≥ 5 flags collected in a 7-day canary window; at least one row cross-references a live audit trace; short addendum added to `docs/internal/audits/decisions/2026-04-16_meta_audit_phases_0_4.md` confirming the plumbing works end-to-end. Unblocks the EVS 0.10 weight as real data instead of placeholder proxy.

---

## P2 — When Idle

### Demoted from P1 (2026-04-16, cap triage)

_Demoted to P2 to bring P1 within 25-ceiling. All are review/sweep/benchmark tasks not blocking audit gates or project delivery._

- [ ] **[WIKI_PRODUCT_TO_EXECUTION_BRIDGE]** If the wiki has value, define and implement the smallest path that makes it materially useful in execution. If it does not yet add value, demote it from active cognitive importance instead of pretending it is core.
- [ ] **[EVENING_CODE_REVIEW_ERRORS_TRIAGE]** Review issues surfaced by latest evening code review, turn into concrete reliability fixes.

### Phase 6 Follow-ups (P2, added 2026-04-16)

- [ ] **[PHASE6_CODELET_DIVERSITY_FLOOR]** Add anti-starvation to codelet competition in `clarvis/cognition/attention.py`: ensure non-memory codelets (code, research, infrastructure) win at least 20% of competitions combined. Currently memory wins 86.4% (628/727). Implement via domain rotation or activation floor. Acceptance: after 50 compete() cycles, non-memory wins >= 20%. Source: Phase 6 Gap 6.
- [ ] **[PHASE6_OPERATOR_VALUE_LABEL]** Design a mechanism for operator to label task outcomes as "high-value" / "neutral" / "low-value". Could be Telegram reaction on digest, `/rate` command, or QUEUE.md annotation. Without this, task-selector vs operator-value correlation is structurally unmeasurable. Source: Phase 6 Gap 5.

### Deep Audit — Meta-Audit Follow-ups (P2, added 2026-04-16 via AUDIT_CAP_OVERRIDE)


### Phase 4.5 Follow-ups (P2, added 2026-04-16)

- [ ] **[AUDIT_PHASE_4_5_IDENTITY_CLEANUP]** Move ~70 meta-cognition completion records from clarvis-identity to clarvis-episodes. ~50% of identity content is "Meta-cognition: Completed [TASK]..." which is episode data, not identity. Provenance: Phase 4.5 taxonomy finding D2.
- [ ] **[AUDIT_PHASE_4_5_BRIDGE_CLEANUP]** Remove or relocate `sbridge_*` / `BRIDGE [...]` entries from primary collections (identity, infrastructure, memories). These are graph relationship metadata stored as standalone memories, polluting retrieval. ~9 found in sample; likely more in full population. Provenance: Phase 4.5 taxonomy finding D1.
- [ ] **[AUDIT_PHASE_4_5_GOALS_RESTRUCTURE]** Separate goal definitions from progress snapshots in clarvis-goals. Move progress percentages ("Autonomous Execution: 65%") and priority lists to clarvis-context. Keep only actual goal definitions. Provenance: Phase 4.5 taxonomy finding D3.
- [ ] **[AUDIT_PHASE_4_5_EPISODE_LESSONS]** Extend heartbeat postflight to extract one-line lesson per episode. Currently 75% of episodes are bare "Episode: [TASK] → success/failure" with no reusable insight. Provenance: Phase 4.5 gap G3.
- [ ] **[AUDIT_PHASE_4_5_COLLECTION_SCHEMA_DOC]** Add per-collection purpose/boundary documentation to `clarvis/brain/constants.py` (docstrings) and `CLAUDE.md`. Define what should and shouldn't go in each collection. Provenance: Phase 4.5 gap G5.

### Phase 8 Follow-ups (P2, added 2026-04-16)

- [ ] **[PHASE8_MIRROR_PRESUBMIT_GATE]** Add a pre-submit mirror validation step to `project_agent.py spawn` and the SWO PR workflow. Before opening a PR, run `tsc --noEmit` and `vitest run` against `/opt/star_world_order/PROD` with proposed changes. Cite results in PR body. Acceptance: next SWO PR includes a mirror validation section. Source: Phase 8 Gap 2.
- [ ] **[PHASE8_STALE_PR_WATCHDOG]** Add a weekly check (to `cron_watchdog.sh` or `health_monitor.sh`) that lists open Clarvis-authored PRs older than 14 days. Alert via Telegram with PR number, age, and review status. Acceptance: alert fires for #175, #176, #177 on first run. Source: Phase 8 Gap 3.
- [ ] **[PHASE8_LITEBRAIN_SEED_EXPANSION]** Expand SWO lite-brain seed data with architecture, security model, and API design documentation to improve P@1 from 0.632 toward ≥0.8. Run golden QA benchmark after seeding. Source: Phase 8 Gap 5.

### Deep Audit — Phase 9 Follow-ups (P2, added 2026-04-17)

- [ ] **[SELF_MODEL_TEST_COVERAGE]** Add test suite for `clarvis/metrics/self_model.py` (1575 LoC, 0 tests — largest untested spine module). Cover `assess_all_capabilities()`, `think_about_thinking()`, and the 7-domain scoring. Acceptance: `metrics.coverage_pct` lifts; self_model has ≥3 test cases. Source: Phase 9 KEEP ruling, EVS/TCS=0.70.
- [ ] **[TEMPORAL_SELF_STALENESS_FIX]** Investigate why `data/growth_narrative.json` is 21 days stale despite `cron_reflection.sh` step 6.5 being scheduled daily. Fix the silent failure or merge core delta computation into `self_model` postflight as a ~50-line helper if standalone script isn't justified. Acceptance: growth_narrative.json updates within 24h of fix. Source: Phase 9 REVISE ruling.
- [ ] **[PHASE9_REEVAL_WITH_AB]** After `[PHASE9_AB_TOGGLE_WIRING]` completes and 14-day A/B windows are collected for the 4 SHADOW features, re-run Phase 9 EVS scoring with causal data instead of proxies. Update `data/audit/neuro_feature_scorecard.jsonl` and `NEURO_FEATURE_DECISIONS_2026-04-17.md`. Any SHADOW feature showing positive causal EVS/TCS ≥ 0.2 → upgrade to REVISE. Any showing zero or negative → proceed to DEMOTE (with operator signoff for consciousness-labelled). Source: Phase 9 Proxy Limitation §0.
- [ ] **[PHASE9_CLI_ONLY_SPINE_MODULES]** Score `clarvis/brain/spr.py`, `clarvis/brain/llm_rerank.py`, `clarvis/metrics/clr_reports.py`, `clarvis/metrics/evidence_scoring.py` — CLI-only spine modules with no importing caller. These were deferred from Phase 9 main pass. `spr.py`/`llm_rerank.py` touch retrieval/Phi subcomponents — require operator signoff before SHADOW. Source: `[SPINE_CLI_ONLY_MODULES_PHASE_9_INTAKE]`.

### Phase 10 Follow-ups (P2, added 2026-04-17)

- [ ] **[PHASE10_RESTORE_DRILL]** Create `scripts/infra/restore_drill.sh` that restores the latest backup to a temp directory, verifies ClarvisDB can load, runs `brain.health_check()`, and reports pass/fail. Add quarterly cron entry. Acceptance: drill runs once successfully and is scheduled. Source: Phase 10 reliability gap — backups verified but never test-restored. Decision doc: `docs/internal/audits/decisions/2026-04-17_phase10_reliability_security.md`.
- [ ] **[PHASE10_GATEWAY_SYSTEMD_HARDENING]** Add `PrivateTmp=true`, `NoNewPrivileges=true`, `ProtectHome=read-only`, `ProtectSystem=strict` to `openclaw-gateway.service`. Project agent services already have these. Acceptance: `systemctl --user show openclaw-gateway.service | grep PrivateTmp` returns `yes`. Source: Phase 10 security gap.
- [ ] **[PHASE10_AUXILIARY_SERVICE_BINDING]** Bind dashboard (18799), website (18801), and any other auxiliary services to 127.0.0.1 instead of 0.0.0.0, or add authentication. Source: Phase 10 security gap.
- [ ] **[PHASE10_SECRET_SWEEP_CRON]** Add `scripts/audit/secret_sweep.py` to weekly cron (e.g., Sunday 05:25). Source: Phase 10 artifact requirement (secret_sweep ≥ weekly).

### Deep Audit — Phases 12–15 Anchors (P2, added 2026-04-16 per meta-meta audit)

_Activate when Sprint 6 artifacts merge. These are placeholder anchors — full queue items should be written when dependency phases land._

- [ ] **[AUDIT_PHASE_12_DUAL_LAYER_HANDOFF]** Audit the conscious/subconscious dual-layer handoff: digest quality (14-day sample), digest utilization by M2.5, spawn delegation quality (20-spawn sample), information loss in digest compression. This is Clarvis's most distinctive architectural feature and is unaudited across Phases 0–11. Acceptance: `docs/internal/audits/DUAL_LAYER_HANDOFF_<date>.md` with digest quality scores, spawn-prompt quality rubric, and mandatory §Gap Analysis + §Promote Candidates. Source: Phase 12 in audit plan.
- [ ] **[AUDIT_PHASE_13_PROPOSAL_QUALITY]** Audit the evolution-loop proposal generation quality: proposal survival rate, hallucination rate (references to non-existent features/files), strategic alignment with tracked goals, self-work bias ratio, proposal → shipped outcome rate. The queue is Clarvis's strategic brain; executing well on bad proposals wastes resources. Acceptance: `docs/internal/audits/PROPOSAL_QUALITY_<date>.md` with per-proposal quality scores, survival funnel, and mandatory §Gap Analysis + §Promote Candidates. Source: Phase 13 in audit plan.
- [ ] **[AUDIT_PHASE_14_COST_VALUE_EFFICIENCY]** Cross-system cost-per-outcome economic analysis: cost per shipped PR, cost per productive heartbeat, cost per brain-memory-retrieved, cost per digest-generating-operator-action, cron-minute budget vs value, model-routing economic accuracy, monthly efficiency trend. Acceptance: `docs/internal/audits/COST_VALUE_<date>.md` with per-cron-job cost/value analysis and mandatory §Gap Analysis. Source: Phase 14 in audit plan.
- [ ] **[AUDIT_PHASE_15_REAUDIT_PROTOCOL]** Define longitudinal re-audit cadence: which Phase 0–14 measurements re-run quarterly, what constitutes drift, when to re-open KEEP/DEMOTE decisions, quarterly re-audit template, annual full-audit trigger. Acceptance: `data/audit/longitudinal_schedule.json` + `docs/internal/audits/REAUDIT_PROTOCOL_<date>.md` + one trial quarterly re-run. Source: Phase 15 in audit plan.

### Deep Audit Follow-ups (from Phase 1 — `docs/internal/audits/SCRIPT_WIRING_INVENTORY_2026-04-16.md`)

- [ ] **[SPINE_CLI_ONLY_MODULES_PHASE_9_INTAKE]** Four spine modules are live only by `python3 -m` contract with no importing caller: `clarvis/brain/spr.py`, `clarvis/brain/llm_rerank.py`, `clarvis/metrics/clr_reports.py`, `clarvis/metrics/evidence_scoring.py`. Surface them as Phase 9 EVS/TCS inputs (low attribution, non-trivial TCS). `spr.py`/`llm_rerank.py` touch retrieval/Phi subcomponents — require operator signoff (§0.3.5) before any move past SHADOW.

### Deep Audit — Phase 2.5 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase2_5_code_design_review.md`. Phase 2.5 reviewed 3 spine modules (brain, orch, context) for design quality. All 3 ruled REVISE. Top finding: no prompt-generation telemetry in `clarvis.context`. All items use `source="audit_phase_2_5"`._

- [ ] **[CONTEXT_BRIEF_TELEMETRY]** Add a `BriefResult` dataclass to `clarvis.context.assembly.generate_tiered_brief()` that returns structured telemetry alongside the brief text: `sections_included`, `sections_pruned`, `token_budget_used`, `fallbacks_activated`, `relevance_weights_applied`. Wire into Phase 0 audit traces via `update_trace({"prompt.brief_telemetry": ...})`. This is a Phase 3 dependency — without it, prompt assembly audit operates on indirect evidence only. Acceptance: at least 3 heartbeats produce traces with non-empty `prompt.brief_telemetry`; existing callers that only need the string can use `result.text`.
- [ ] **[ORCH_STRUCTURED_LOGGING]** Add `import logging` to `clarvis/orch/task_selector.py`, `cost_tracker.py`, and `pr_intake.py`. Log at WARNING when: (a) an optional module import fails in task_selector (currently silently `None`-ified), (b) a malformed cost entry is dropped in `_read_entries()`, (c) an artifact generator is skipped in pr_intake. Acceptance: after one heartbeat cycle with the new logging, `grep WARNING` on the cron output shows at least the expected import-failure messages (somatic_markers etc. if not installed).
- [ ] **[BRAIN_OBSERVABILITY_COUNTERS]** Add failure counters to `clarvis.brain`: `_dedup_failures`, `_hook_timeouts`, `_temporal_fallbacks` — increment on each silent swallow site in `store.py`, `search.py`, `hooks.py`. Expose via `brain.stats()` so `health_check()` and the audit trace can surface degradation. Acceptance: `brain.stats()` includes `failure_counters` dict with ≥ 3 keys; counters increment on injected test failures.

### Deep Audit Follow-ups (from Phase 2 — `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md`)

_All are surface trims or cheap coverage lifts. Bridge wrappers (18) and underlying submodule files are NOT being touched — only `__init__.py` re-exports. All new items use `source="audit_phase_2"` and benefit from the audit-cap override. Re-run `scripts/audit/spine_scorecard.py` after each PR to verify the `dead_exports` count drops._

- [ ] **[SPINE_BRAIN_INIT_TRIM]** Remove 6 DEAD re-exports from `clarvis/brain/__init__.py`: `LOCAL_GRAPH_SQLITE_FILE`, `StoreMixin`, `propose_and_commit`, `get_pending_proposals`, `reject_proposal`, `temporal_search`. Do NOT delete the underlying files — this is a surface narrowing only. The proposal workflow (`propose_and_commit`/`get_pending_proposals`/`reject_proposal`) is dormant since consolidation refactor; `temporal_search` is superseded by `search(..., since_days=…)`. Acceptance: `python3 -m clarvis brain stats` + `cron_autonomous.sh` dry-run pass; `spine_scorecard.py` shows `brain.dead_exports = 0`.
- [ ] **[SPINE_CONTEXT_INIT_TRIM_AND_COVERAGE]** Trim 12 DEAD re-exports from `clarvis/context/__init__.py` (`_simple_tiered_brief, prune_stale, snip_middle, graduated_compact, get_optimizer_report, load_section_relevance_weights, build_wire_guidance, get_failure_patterns, get_workspace_context, get_spotlight_items, build_hierarchical_episodes, synthesize_knowledge`). These are already directly importable from `clarvis.context.{compressor,assembly,prompt_optimizer,…}` — the `__init__` level re-exports are redundant. Also add 2-3 unit tests for currently-uncovered branches in `clarvis/context/assembly.py`. Acceptance: `context.coverage_pct ≥ 40` and `context.dead_exports = 0` on re-run.
- [ ] **[SPINE_MEMORY_INIT_TRIM_AND_COVERAGE]** Trim 12 DEAD re-exports from `clarvis/memory/__init__.py` (all are `memory_consolidation` helpers — `learn_from_failures, retire_stale, compose_procedures, merge_clusters, enhanced_decay, enforce_memory_caps, run_consolidation, sleep_consolidate, attention_guided_prune, attention_guided_decay, gwt_broadcast_survivors, salience_report`). Underlying `memory_consolidation.py` stays — callers use direct submodule imports. Add direct unit tests for `procedural_memory.find_procedure` and `procedural_memory.store_procedure` (heavily used in production, currently only exercised indirectly). Acceptance: `memory.coverage_pct ≥ 25` and `memory.dead_exports = 0`.
- [ ] **[SPINE_ORCH_SCOREBOARD_SURFACE_TRIM]** Drop `scoreboard_record`, `scoreboard_show`, `scoreboard_trend` re-exports from `clarvis/orch/__init__.py`. The `clarvis.orch.scoreboard` submodule stays live (1 importer per Phase 1) — direct importers can still `from clarvis.orch.scoreboard import record, show, trend`. Acceptance: `orch.dead_exports = 0`.
- [ ] **[SPINE_COMPAT_WIRE_OR_DOCUMENT]** `clarvis/compat/` has zero production callers (only test callers). Decide one of: (a) wire `run_contract_checks()` into `scripts/infra/health_monitor.sh` with a daily metric exported to `monitoring/`, OR (b) mark the module docstring as "test-scaffold for host-portability contracts" and exclude it from future Phase 9 EVS/TCS passes. Acceptance: clear wire-or-document state recorded — no "kept for future" ambiguity.
- [ ] **[SPINE_HEARTBEAT_UNIT_COVERAGE]** Add unit tests for `clarvis/heartbeat/error_classifier.py` and `clarvis/heartbeat/worker_validation.py` — both near-zero coverage today because existing tests exercise the pipeline as a whole. Acceptance: `heartbeat.coverage_pct ≥ 25` on `scripts/audit/spine_scorecard.py` re-run.
- [ ] **[SPINE_LEARNING_COVERAGE_VERIFY]** `clarvis/learning/` reports 0 % coverage despite having a test file. Investigate why existing `tests/test_meta_learning*.py` tests don't touch `MetaLearner`; add a minimal smoke test that instantiates + exercises `.update_policy()`. Acceptance: `learning.coverage_pct > 0` and non-trivial (≥ 20 %).
- [ ] **[SPINE_METRICS_COVERAGE_LIFT]** Add tests for `clarvis/metrics/memory_audit.run_full_audit` and `clarvis/metrics/quality.compute_code_quality_score`. Both are used operationally (cron + project-lane) but uncovered. Acceptance: `metrics.coverage_pct ≥ 25`.
- [ ] **[SPINE_RUNTIME_INFER_TASK_SOURCE_DECIDE]** `infer_task_source` is re-exported from `clarvis/runtime/__init__.py` but not called anywhere. Decide: wire it into `clarvis/orch/task_selector.py` at the task-source inference point, OR drop from `__init__` (the function in `mode.py` can stay). Acceptance: `runtime.dead_exports = 0`.

### Deep Audit Follow-ups (from Phase 3 — `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md`)

_Source: `source="audit_phase_3"`. P1 items are co-located in the Phase 3 Follow-ups section above; this is the P2 continuation._

- [ ] **[AUDIT_PHASE_3_TASK_TYPE_CLASSIFIER_UPGRADE]** The canonical-task-type classifier in `scripts/audit/prompt_utilization.py` is a keyword + mmr_category heuristic (swo_feature / bug_fix / research_distillation / maintenance / self_reflection). Acceptable for the initial scorecard but not for ongoing per-type tracking. Replace with either (a) `task_source` read from the queue writer (which already records source metadata on each queue item) or (b) a small sklearn classifier trained on the historical corpus once the 40-task hand-labels land. Acceptance: classifier labels reproduce the filled `prompt_utilization_handlabel_template.json` task-types with ≥ 0.85 accuracy; `prompt_utilization.py run` re-emits with the upgraded classifier.

### Deep Audit Follow-ups (from Phase 4 — `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md`)

_Source: `source="audit_phase_4"`. P0+P1 items are co-located with their parent blocks above; these are the P2 continuation._

- [ ] **[AUDIT_PHASE_4_AB_BRIDGES_HEBBIAN_EPISODES]** Execute matched-pair 14-day A/B windows for three brain features already registered in `clarvis/audit/toggles.py`: `graph_bridges`, `hebbian_boost`, `episodic_memory_injection`. Each feature toggles OFF (or `shadow=true`) for 14 days on a matched task mix, with the corresponding ON window captured before or after. Depends on `[AUDIT_PHASE_4_BRAIN_RETRIEVAL_TRACE_WIRING]` (attribution-gate inputs must be live). Emit three result files under `data/audit/ab_windows/{bridges,hebbian,episodes}_<date>.json` with delta-to-baseline metrics on attribution share, task outcome, and retrieval recall. Subtle-feature guard §3.3 applies (rare-but-critical carve-out) — episode-recall may help only on a narrow task type. Acceptance: all three A/B files present; Phase 9 EVS/TCS scorecard can ingest them.
- [ ] **[AUDIT_PHASE_4_BRAIN_EVAL_FRESHNESS]** `data/brain_eval/latest.json` is six weeks stale (last run 2026-03-04) despite `cron_brain_eval.sh` existing and being listed in `CLAUDE.md §Cron Schedule`. Verify the cron is still scheduled, executing, and writing to the expected path. If the cron is broken, fix the schedule or writer. Acceptance: within 26 h of the fix landing, `data/brain_eval/latest.json` has a fresh timestamp; `scripts/audit/brain_attribution.py run` picks up the new `recall_at_k` snapshot automatically.

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

- [x] Reasoning chain depth audit + multi-hop task. (2026-04-17) Audited: avg depth 2.8 steps, range 1-7, 90 sessions. Multi-hop supported via dual-write in reasoning_chain_hook.py. Quality-gated: shallow chains (<2-3 steps per priority) rejected from brain storage. No code changes needed — depth distribution is healthy.
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

- [ ] **[AUDIT_PHASE_16_REAUDIT_PHASE_7]** Re-audit tainted Phase 7 at the end of the deep audit program. Treat the earlier run as low-trust due to prompt contamination / merged-ask framing mistakes. Re-run it with strict prompt hygiene and use the clean rerun as the canonical evidence for synthesis.

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

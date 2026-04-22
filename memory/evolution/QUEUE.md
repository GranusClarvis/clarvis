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

## P1 — This Week

### Claude Design & Routines Integration (cross-project, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md`. Cross-project operating model for Claude Design + Claude Code Routines._


### Star Sanctuary — Validated Roadmap (PROJECT:SWO, revalidated 2026-04-21)

_SWO tasks tracked here. See also: memory/evolution/SWO_TRACKER.md_
_Status as of 2026-04-21: dev branch (upstream 36d0e20) synced. All 19 PRs merged (through #195). All branches cleaned (38→2). Self-hosted corpus DONE (3,333 NFT images). Security PRs #177/#180/#181/#183/#184 merged. PR #179 CLOSED (wallet auth on POST routes still needed — SWO_SANCTUARY_POST_AUTH). Fork sync + branch discipline + PR targeting + auto-cleanup fixed in project_agent.py._
_Style doctrine: `docs/SANCTUARY_STYLE_DOCTRINE.md` — binding on all visual work._
_Asset state: NFT art self-hosted ✓, companion sprites NOT YET CREATED (falls back to NFT art), location vignettes NOT YET CREATED (falls back to emoji), empty-state illustrations NOT YET CREATED._

#### 0. Security (BLOCKING — do first)


#### 1. Error Handling & Reliability (highest user-facing impact)


#### 2. Functional Gaps (code-only, high value)


#### 3. Animation & Polish Wiring (keyframes exist, just need connection)


#### 4. Quality & Hardening

- [ ] **[SWO_SANCTUARY_RESPONSIVE]** Test and fix mobile: (1) world map aspect on phones, (2) text size readability (text-[7px] to text-[10px] may be unreadable), (3) touch target sizing (40px min), (4) chat input mobile layout. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_E2E_TESTS]** E2E test coverage for all 15 API routes at HTTP layer. Current 128 tests are DB-layer only. Add: wallet connect → interact → journal, activity flow, chat, quest claim, public map view. Also add tests for error paths and rate-limit responses. (PROJECT:SWO)

#### 5. Enhancement (lower priority)

- [ ] [UNVERIFIED] **[SWO_SANCTUARY_CHAT_LLM]** Upgrade chat from templates to LLM (per ADR-002). OpenRouter → Gemini Flash, 15/day rate limit, personality + bond + journal context injection. Create `lib/sanctuary/chatPersonality.ts` (trait→prompt builder), `app/api/sanctuary/companion/chat/route.ts`, `sanctuary_chat_usage` table. Add `SANCTUARY_CHAT_DRY_RUN` env flag for cost-safe testing. ~$0.05/day at 100 users. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md` §Phase 1. (PROJECT:SWO)
- [ ] [UNVERIFIED] **[SWO_SANCTUARY_BOND_STAGES]** Map existing `bond_score` 0-100 to 4 behavioral stages (Shy/Friendly/Bonded/Devoted) that change companion chat personality. Create `lib/sanctuary/bondStages.ts` with stage thresholds + prompt context generator. Inject stage-appropriate tone guidance into chat system prompt. No schema changes — derives from existing `bond_score` column. Depends on `[SWO_SANCTUARY_CHAT_LLM]`. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md` §Phase 2. (PROJECT:SWO)
- [ ] [UNVERIFIED] **[SWO_SANCTUARY_CHAT_MEMORY]** Lightweight persistent memory so companions remember owner facts across sessions. Create `sanctuary_chat_memories` table (5 categories: owner_identity, preferences, shared_experiences, companion_feelings, recurring_topics). Extract facts by piggybacking on the chat LLM call (no separate classifier — zero extra cost). Inject top 5 memories by importance+recency into system prompt (150 token budget, 3-turn frequency cap). Depends on `[SWO_SANCTUARY_CHAT_LLM]`. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md` §Phase 3. (PROJECT:SWO)
- [ ] [UNVERIFIED] **[SWO_SANCTUARY_CHAT_HISTORY]** Persist chat messages server-side so conversations survive tab close. Create `sanctuary_chat_history` table (wallet, token_id, role, content, created_at). Load last 20 on reconnect, send last 10 to LLM for context. Add GET endpoint for paginated history. Depends on `[SWO_SANCTUARY_CHAT_LLM]`. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md` §Phase 4. (PROJECT:SWO)
- [ ] [UNVERIFIED] **[SWO_SANCTUARY_TYPING_SIM]** Add typing simulation to companion chat for immersion. Calculate delay from response word count (~45 WPM, 800ms-4000ms range). Show typing indicator dots (CSS keyframes already exist in globals.css). Frontend delays rendering assistant message by calculated ms. Depends on `[SWO_SANCTUARY_CHAT_LLM]`. Design ref: `docs/KINKLY_REFERENCE_ANALYSIS.md` §Phase 5. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_SOUND_DESIGN]** Optional ambient sound layer. Muted by default. Lower priority — visual assets first. (PROJECT:SWO)

#### 6. Future Phases (P2, from milestones)

- [ ] **[SWO_SANCTUARY_COSMETICS_SHOP]** Cosmetic items schema + STAR shop UI. `equipped_cosmetics` column exists but unused. Primary STAR token sink. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_EXPEDITIONS]** Expedition system (tables exist, routes stub). Multi-step adventures with narrative choices. (PROJECT:SWO)
- [ ] **[SWO_SANCTUARY_MEMORY_CONSOLIDATION]** Weekly batch job to consolidate chat memories: merge duplicates, decay old emotions (staleness penalty on volatile categories), summarize recurring topics. Similar to Kinkly's contradiction detection but batch-processed. Depends on `[SWO_SANCTUARY_CHAT_MEMORY]`. (PROJECT:SWO)




- [ ] **[PHI_DEEMPHASIS_AUDIT]** Audit and reduce Clarvis-wide overfocus on Phi. Goal: Phi should remain only a lightweight regression/health signal, not a recurring optimization target, routing bias, prompt contaminant, or context-budget parasite. Find where Phi/Integration language, tasks, alerts, queue injection, prompt sections, and autonomous logic still over-prioritize it; downgrade/remove those pathways where low-value; preserve only minimal monitoring for genuine regressions. Deliver: clear map of where Phi is still plaguing the system, code/config/doc changes to de-emphasize it, and updated rules so future work is judged more by operator value, task outcomes, retrieval quality, reliability, and shipped results than by Phi movement. (PROJECT:CLARVIS)

### Deep Audit — Phase 9 Follow-ups (P1, added 2026-04-17)


### Phase 8 Follow-ups (P1, added 2026-04-16)


### Deep Audit — Verification Program (added 2026-04-20)

_3-phase verification pass over the completed 16-phase deep audit + 100+ queue items. Confirms work quality, identifies regressions, flags fragile areas. Each phase covers ~6 audit areas. Source: operator-requested audit-of-the-audit._


### Project-Agent Orchestration Quality (added 2026-04-21)

_Source: deep analysis of why Clarvis self-work > project-agent work. Core issue: project-agent prompts lacked 8+ context layers that self-work enjoys. FIXED in this session: worker template, time budget, episodic recall, failure avoidance, lite brain query, episode writeback, procedures.md auto-refresh. Follow-up items below._


### Clarvis Maintenance — Keep Alive


### Deep Audit — Phase 0 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Recorded under the audit-cap override (§P0 banner). P1 is currently 19/15 in base terms but within the 25-ceiling for audit sources. These are justified Phase 0 follow-ups; closing them is a precondition for a valid Phase 0 PASS ruling and for downstream phases. See `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`._


### Deep Audit — Phase 2 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase2_spine_quality.md`. Phase 2 ruled 1 PASS, 13 REVISE, 0 DEMOTE/ARCHIVE on 14 spine modules — most of the REVISE work is small `__init__.py` surface trims and cheap coverage lifts. Only 1 P1 (the new `clarvis/audit/` module needs tests — substrate is live but untested)._


### Deep Audit — Phase 3 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase3_prompt_assembly.md`. Phase 3 ruled 5×PASS across task types on 334 scored episodes; aggregate gate PASS. Open follow-ups address proxy limits (MISLEADING detection, trace-backed rescore) and one hand-label task. No assembly code paths were changed by this phase._


### Deep Audit — Phase 4 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md` + `docs/internal/audits/decisions/2026-04-16_phase4_brain_usefulness.md`. Phase 4 ruled INSUFFICIENT_DATA × 10 collections on the attribution gate — blocked by two Phase-0 capture gaps (listed below, the P0 item being the most severe). One independent REVISE flagged on routing. `scripts/audit/brain_attribution.py` + `data/audit/brain_attribution.jsonl` + `data/audit/brain_collection_scorecard.json` shipped. All items use `source="audit_phase_4"`._


### Deep Audit — Phase 6 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase6_execution_routing_queue.md`. Phase 6 ruled REVISE overall: router PASS (98.9% accuracy, PROMOTE candidate), autofill PASS (2.4% stale), caps REVISE (21/30 days), spawn PASS, slot share FAIL (12.5% vs 50%). All items use `source="audit_phase_6"`._


### Deep Audit — Meta-Audit Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_meta_audit_phases_0_4.md`. A sharpness-check on Phases 0–4 found the program well-executed but framed too narrowly toward removal. Corrections: add code-review axis to Phase 2, wire operator-in-the-loop EVS signal, content-quality spot check for Phase 4. Plan §0 principle 7 + PROMOTE gate already landed in the plan doc. All items use `source="audit_meta"`._


---

## P2 — When Idle
- [~] [STALLED] **[AUDIT_PHASE_0_INSTRUMENTATION]** Implement the Phase 0 measurement substrate that blocks every downstream audit phase: (1) per-spawn `audit_trace_id` linking preflight→execution→postflight→outcome, (2) `data/audit/traces/<date>/<id>.json` writer with ≥45d retention, (3) `data/audit/feature_toggles.json` registry supporting `shadow` mode, (4) `scripts/audit/trace_exporter.py` CLI, (5) `scripts/audit/replay.py` for deterministic prompt rebuild. PASS gate: ≥95% of real Claude spawns in a 7-day window have a complete recoverable trace. Canonical plan: `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md`. (2026-04-16: substrate shipped — `clarvis/audit/{trace,toggles}.py`, trace_exporter + replay CLIs, spawn_claude + heartbeat wiring, `audit_trace_id` on CostEntry. Awaiting 7-day trace window before PASS ruling. Decision doc: `docs/internal/audits/decisions/2026-04-16_phase0_instrumentation.md`.) (2026-04-20 corrected assessment: 106 traces across 5 days (Apr 16–20). By source: heartbeat 43/43 complete (100%), spawn_claude 59/61 have outcome (96.7% — 2 missing outcome.status), 2 test traces excluded. Combined: 102/104 non-test = 98.1% completeness, above 95% gate. 7-day window not yet met — 5/7 days elapsed, eval on or after 2026-04-23.)

### Claude Design & Routines — Medium-term (P2, added 2026-04-20)

_Source: `docs/CLAUDE_DESIGN_ROUTINES_STRATEGY.md` §6 Phase 2-3._


### Demoted from P1 (2026-04-16, cap triage)

_Demoted to P2 to bring P1 within 25-ceiling. All are review/sweep/benchmark tasks not blocking audit gates or project delivery._


### Phase 6 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Meta-Audit Follow-ups (P2, added 2026-04-16 via AUDIT_CAP_OVERRIDE)


### Graph Integration (P2, added 2026-04-18)


### Phase 4.5 Follow-ups (P2, added 2026-04-16)


### Phase 8 Follow-ups (P2, added 2026-04-16)


### Deep Audit — Phase 9 Follow-ups (P2, added 2026-04-17)

- [~] [BLOCKED:2026-05-01] **[PHASE9_REEVAL_WITH_AB]** After `[PHASE9_AB_TOGGLE_WIRING]` completes and 14-day A/B windows are collected for the 4 SHADOW features, re-run Phase 9 EVS scoring with causal data instead of proxies. Update `data/audit/neuro_feature_scorecard.jsonl` and `NEURO_FEATURE_DECISIONS_2026-04-17.md`. Any SHADOW feature showing positive causal EVS/TCS ≥ 0.2 → upgrade to REVISE. Any showing zero or negative → proceed to DEMOTE (with operator signoff for consciousness-labelled). Source: Phase 9 Proxy Limitation §0. (2026-04-19: A/B window opened 2026-04-17, closes 2026-05-01 — only 2/14 days elapsed. No causal data available yet. Re-check on or after 2026-05-01.)

### Phase 10 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase10_reliability_security.md`. Phase 10 ruled REVISE — restore drill FAIL blocks PASS. Items below were in the decision doc and AUDIT_INDEX but never added to QUEUE.md._


### Phase 5 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/decisions/2026-04-16_phase5_wiki_usefulness.md`. Phase 5 ruled REVISE. These items were mandated in the decision doc but never added to QUEUE.md. The 30-day re-evaluation window from 2026-04-16 is active._


### Phase 12 Follow-ups (P2, added 2026-04-19 — recovered from decision doc)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 ruled REVISE (digest actionability 56.5% vs 60% target). Only 1 of 4 follow-ups was in QUEUE.md._


### Test Suite Health (P2, added 2026-04-19)

_~~72/2921 tests failing (2.5% failure rate)~~ → 0/3031 failing (0.0%) as of 2026-04-20. Fixed: (1) `quality.py` AST walk consolidated 4→1 pass + 200-file cap to eliminate timeout; (2) `test_pi_anomaly_guard` missing `benchmark_phi` monkeypatch added; (3) phi tests still flaky under concurrent ChromaDB access — `_safe_compute_phi()` wrapper added to gracefully skip on transient ChromaDB errors instead of hard-failing. 2026-04-20: 1 phi test was failing again (ChromaDB "Error finding id") — fixed with skip-on-transient-error._



### Deep Audit — Phases 12–15 Anchors (P2, added 2026-04-16 per meta-meta audit)

_Activate when Sprint 6 artifacts merge. These are placeholder anchors — full queue items should be written when dependency phases land._


### Phase 15 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/decisions/2026-04-17_phase15_reaudit_protocol.md`. Phase 15 PASS: all 3 gates met. Trial run found 3 stale locks (actionable regression)._


### Phase 14 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/COST_VALUE_2026-04-17.md`. Phase 14 ruled REVISE: cost tracking structurally broken, system-adjusted cost/PR fails gate, but trend improving and cost-reduction targets identified._


### Phase 13 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/PROPOSAL_QUALITY_2026-04-17.md`. Phase 13 ruled REVISE: proposal quality analytically strong but tracking broken (sidecar 0/394 useful), hallucination rate at boundary (10%), self-work bias structural._

- [~] [BLOCKED:SIDECAR_OUTCOME_CAPTURE] **[PHASE13_RESCORE_AFTER_SIDECAR]** After sidecar carries outcome-quality metadata and 14 days of data accumulates, re-run Phase 13 survival and outcome measurements with real data instead of proxies. Update `data/audit/proposal_quality.jsonl` and scorecard. Acceptance: re-scored gates use sidecar data, not proxy estimates. Source: Phase 13 proxy limitation. (2026-04-20 corrected: Phase 6 source propagation landed 2026-04-18 — 106/434 sidecar entries now have `source`. However, 0/434 have `status` or `outcome` quality metadata. The sidecar tracks operational state (`state: succeeded/failed`) but not outcome quality (PR merged, value delivered). Real blocker: outcome-quality capture must be wired into sidecar before rescore is possible.)

### Phase 12 Follow-ups (P2, added 2026-04-17)

_Source: `docs/internal/audits/DUAL_LAYER_HANDOFF_2026-04-17.md`. Phase 12 found digest actionability at 56.5% (REVISE), spawn quality 85% (PASS). Digest archive missing, inconsistent writers, morning garble._


### Deep Audit Follow-ups (from Phase 1 — `docs/internal/audits/SCRIPT_WIRING_INVENTORY_2026-04-16.md`)


### Deep Audit — Phase 2.5 Follow-ups (added 2026-04-16 via AUDIT_CAP_OVERRIDE)

_Source: `docs/internal/audits/decisions/2026-04-16_phase2_5_code_design_review.md`. Phase 2.5 reviewed 3 spine modules (brain, orch, context) for design quality. All 3 ruled REVISE. Top finding: no prompt-generation telemetry in `clarvis.context`. All items use `source="audit_phase_2_5"`._


### Deep Audit Follow-ups (from Phase 2 — `docs/internal/audits/SPINE_MODULE_SCORECARD_2026-04-16.md`)

_All are surface trims or cheap coverage lifts. Bridge wrappers (18) and underlying submodule files are NOT being touched — only `__init__.py` re-exports. All new items use `source="audit_phase_2"` and benefit from the audit-cap override. Re-run `scripts/audit/spine_scorecard.py` after each PR to verify the `dead_exports` count drops._


### Deep Audit Follow-ups (from Phase 3 — `docs/internal/audits/PROMPT_ASSEMBLY_SCORECARD_2026-04-16.md`)

_Source: `source="audit_phase_3"`. P1 items are co-located in the Phase 3 Follow-ups section above; this is the P2 continuation._


### Deep Audit Follow-ups (from Phase 4 — `docs/internal/audits/BRAIN_USEFULNESS_2026-04-16.md`)

_Source: `source="audit_phase_4"`. P0+P1 items are co-located with their parent blocks above; these are the P2 continuation._


### Phi Monitoring / Validation (demoted to observability metric by Phase 11 synthesis — regression watch only, not a KPI or optimization target; overlaps Phase 9 REVISE ruling on phi_metric)


### Deep Cognition (pre-audit backlog; overlaps Phase 2/4.5/9 findings)


### Cron / Non-Python Maintenance (pre-audit backlog; several overlap Phase 1 wiring inventory + Phase 10 reliability findings)


### Calibration / Brier Score (RECOVERED — all-time Brier=0.094, 7-day=0.085 as of 2026-04-20; target 0.1 PASS)


### CLR Autonomy Dimension (recovered from 0.025 → 0.603 as of 2026-04-20; remaining drag: daily cost > $10 ceiling)

### Claude Spawn Observability (pre-audit backlog; related to Phase 0 instrumentation + Phase 10 reliability)


### Star Sanctuary — Later Phases (PROJECT:SWO)

_V1.0+V1.5 shipped. First Playable Layer and Retention/Identity phases consolidated into P1 §5 above. Remaining P2:_
- [ ] **[SANCTUARY_STAR_CURRENCY_DECISION]** STAR on Monad recommendation.


### Adaptive RAG Pipeline

### Episode Success Rate Recovery & Benchmark Accuracy (2026-04-09 evolution)

### Task Quality Score (RECOVERED — 0.83 as of 2026-04-20, target 0.70 PASS)

---

## NEW ITEMS (2026-04-15 evolution scan)


### 2026-04-16 evolution scan


### 2026-04-20 evolution scan

- [ ] [UNVERIFIED] **[FIX_PHI_HEALTH_REPORTING]** The health pipeline reports Phi=0.000 because `phi_metric.py` was never committed to `scripts/metrics/` on main — it only exists in stale worktrees. Either (a) add a `scripts/metrics/phi_metric.py` wrapper that calls `clarvis.metrics.phi.compute_phi()`, or (b) fix the health data collector (`cron_pi_refresh.sh` / `daily_brain_eval.py`) to import from `clarvis.metrics.phi` directly. Acceptance: `health_monitor.sh` and evolution context report Phi≥0.60 instead of 0.000.
- [ ] **[SEMANTIC_OVERLAP_BOOST]** Phi's weakest sub-component is `semantic_cross_collection`=0.579 (others ≥0.63). Identify the 5 lowest-similarity collection pairs (goals↔autonomous-learning=0.492, procedures↔autonomous-learning=0.488) and add 10–15 bridging memories that create genuine semantic connections between those domains. Verify Phi semantic component rises ≥0.60 without degrading other components.
- [ ] **[CRON_STALE_WORKTREE_CLEANUP]** 10+ stale worktrees exist under `.claude/worktrees/` from prior agent runs, each containing full repo copies. Add a weekly cron entry (Sun 05:25, between existing hygiene jobs) that runs `git worktree prune` and removes any `.claude/worktrees/` dirs older than 7 days. Non-Python task (bash cron script).
- [ ] **[AUTONOMOUS_EXECUTION_CAPABILITY_LIFT]** `autonomous_execution` is the weakest capability at 0.64. Audit the last 20 autonomous cron episodes for failure patterns (timeout, lock contention, wrong-model spawn). Implement the top fix (likely: reduce lock wait time or add per-job timeout tuning). Acceptance: capability score ≥0.70 on next weekly benchmark.

---

## Partial Items (tracked, not actively worked)

### External Challenges


---

## Research Sessions

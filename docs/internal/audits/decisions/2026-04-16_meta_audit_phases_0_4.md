# Meta-Audit — Phases 0–4 of the Deep-Audit Program

**Date:** 2026-04-16
**Scope:** critical review of `CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` as executed through Phase 4.
**Question:** Are the audits themselves well-framed, evidence-based, and aligned with the *stated* goal — "systematically determine which subsystems actually improve execution, and judge their quality, usefulness, and soundness"?
**Author:** Clarvis (subconscious layer, autonomous execution).

This is an internal correction pass. It is not a new audit phase; it is a sharpness check on work just shipped.

---

## 1. Headline judgment

**Strong substrate, correctly honest rulings, but a lens that tilts toward removal.**

- **Methodology is sound.** Phase-0 traces are built fail-open, toggle registry supports shadow semantics, Phase 3 reuses a 334-episode corpus instead of waiting for trace data, Phase 4 *correctly* refuses to rule on 2 traces. No phase has yet overstepped its evidence.
- **Anti-false-demotion controls are heavy and genuine.** §0.3 subtle-feature guard, §3 global controls, two-consecutive-windows rule, operator veto for phi/consciousness — these are not decorative. They materially reduced risk in Phase 2 (zero DEMOTE rulings on 14 modules) and in Phase 4 (zero rulings at all pending capture wiring).
- **But the gate language, and therefore the operational question every phase answers, is retention vs removal.** KEEP / REVISE / DEMOTE / ARCHIVE. A feature that is affirmatively *excellent* and a feature that is merely *not bad enough to remove* both land in "KEEP". The audit cannot distinguish them. This is the single largest framing defect.
- **"Quality" is proxied by code hygiene, not by engineering review.** Phase 2 "quality" = coverage % + dead exports + mypy errors + caller counts. None of those measure whether the design is sound. `adapters` PASSES the gate with 68 mypy errors; 13 modules REVISE for either <40% coverage OR any dead export. An experienced reviewer reading the code would flag different issues than the scorecard did.
- **"Usefulness" is proxied by lexical overlap.** Phase 3 utilization and Phase 4 attribution both use containment-of-tokens between context and output. A context section that made the model think better without appearing verbatim in the response scores 0; a section whose keywords the model parroted without leveraging scores high. This proxy is well-suited to regression detection and poorly suited to usefulness judgment.
- **No phase asks "what's missing?"** Every phase asks "is what exists justified?" Gap analysis — capabilities, measurements, or features Clarvis *should* have but does not — is absent. An audit with no gap section can only shrink the system; it cannot grow it.

---

## 2. Answering the operator's five questions

### Q1. Were the audits removal-biased or balanced?

**Balanced in protection, removal-biased in framing.**

The anti-false-demotion machinery (§0.3, §3) is stronger than most audit programs carry. That's real balance on the *protection* axis. But the five gate categories — PASS / REVISE / DEMOTE / ARCHIVE / SHADOW — are all movement toward removal or status-quo. None rewards or identifies excellence. Phases executed faithfully to that framing: Phase 2 headline is "30% of exports are DEAD at __init__ surface"; Phase 1 headline is "10 DEAD files"; Phase 4 headline is "INSUFFICIENT_DATA so we can't rule on attribution." The highest-status outcome the plan can express is "nothing needs removing." Excellence has no gate.

### Q2. Did they properly assess usefulness and soundness, or mainly surface cleanup/removal angles?

**Mainly surface cleanup and removal angles.** Specifics:

- **Phase 1 (wiring inventory)** — cleanup (ALIVE/DORMANT/DEAD/DUPLICATE). No judgment on module quality or cohesion. Fine: it is explicitly scoped as cleanup input.
- **Phase 2 (spine module quality)** — named "quality" but instrumented as surface hygiene. Coverage, dead exports, mypy errors, caller counts. No code review, no API design review, no sampling of known-gnarly files for readability/defect rate. Latency is a "best-effort sample of 11 stateless public calls" — the heavy paths were explicitly excluded, i.e. precisely the places where quality matters most. **The phase answered "is this module trim?" not "is this module sound?"**
- **Phase 3 (prompt assembly)** — closest to real usefulness measurement. But the PASS is driven by *weighted lexical containment* (importance-weighted soft-overlap of tokens). The scorecard's own §5 admits the MISLEADING=0 finding is a proxy artefact (13 failure episodes all fell below the 0.30 floor that would have flagged them). Aggregate utilization 0.886 against a 0.45 gate is a comfortable PASS on the proxy — but also, the raw per-section score is 0.244 which lands on the REVISE border under a strict reading. The decision doc ships PASS on the weighted view; the choice of weighted-vs-raw as the headline metric was not independently justified.
- **Phase 4 (brain usefulness)** — correctly refused to rule, ticketed the two capture gaps, flagged one independent routing anomaly. This is the best-executed phase in epistemic terms. But the *tool* it built is a removal-focused attribution share counter. There is no companion tool for "is this memory content actually good?" (inspection-quality spot check), "is the collection taxonomy carved at the right joint?", or "what memories are we failing to capture?"

### Q3. What did they miss about evaluating whether features are genuinely good?

1. **Operator-in-the-loop signal.** Plan §Execution Value Score weights "operator-flagged help" at 0.10 — but no phase implemented or queued the mechanism to collect it. Digest reports (09:30, 22:30) could carry a minimal 👍/👎 or 1–5 usefulness flag that lands in a ledger. Without it, EVS runs entirely on proxies.
2. **Counterfactual utility.** The only credible way to know if section X / collection Y / feature Z makes outcomes *better* is to toggle it off on matched task mix and measure outcome delta. Phase 0 built the toggle registry but did not wire the call sites (follow-up ticket exists). Until toggle call sites are wired, every Phase 3/4/5/9 claim about usefulness is inferred, not demonstrated.
3. **Code-review / design-quality sampling.** Phase 2 did not code-review a single module. For an audit titled "Quality Audit," not reading the code is a defect. A lightweight pass — 3 modules per sprint reviewed by an LLM-judge + operator on design, error handling, observability, testability, and surprise-count — would add the axis that coverage cannot.
4. **Memory-content quality.** Phase 4 never inspected memory text. Retrieval precision can be high while the memories being retrieved are redundant, stale, or noisy. A 30-memory-per-collection spot check with simple rubric (crisp, actionable, non-redundant, within-domain) would flag content quality independently of routing.
5. **Gap analysis per phase.** What features / tests / measurements *should* exist but do not? Phase 2 could name spine modules that are load-bearing but thin on tests (several). Phase 3 could name sections we should have but do not (e.g., per-task "similar past tasks and their outcomes" — exists partially via episodes, but not synthesized). Phase 4 could name collections we *should* have (e.g., `clarvis-failures-with-diagnosis`). Without gap sections, the audit shrinks without growing.
6. **Cross-phase synthesis on strengths.** The plan's Phase 11 synthesizes decisions but is framed as "KEEP/REVISE/DEMOTE/ARCHIVE per subsystem." A companion "top 5 genuinely excellent capabilities" list would be cheap to write and is absent from the plan.
7. **Process audit (meta-cognition about auto-evolution).** None of Phases 0–11 audit how Clarvis decides what to queue and ship. The queue autofill discipline item sits in Phase 6, but framed as "what fraction of auto-injected items are stale?" rather than "is the proposal-generation quality itself any good?" This is Clarvis-specific and arguably the highest-leverage lens.
8. **"Why added" trail enforcement.** §3.7 requires it before demotion; but no phase *inventoried* which features lack a trail. Without inventory, the control is unenforceable.
9. **Operator trust as a first-class dimension.** There is no phase or metric for "does the operator trust subsystem X?" Trust is fragile and hard to proxy, but it materially governs whether recommendations ship. An annual (or post-audit) operator-survey would be cheap and signal-rich.

### Q4. What should be corrected in audit framing or later phases?

**Five concrete corrections.**

1. **Add a PROMOTE / STRENGTHEN / INVEST bucket to the gate.** Features that pass the standard gate *and* show positive EVS beyond a high bar get promoted: more tests, wider integration, documentation, replication to other subsystems. Every phase that rules should produce at least one PROMOTE candidate per sprint, or explicitly say "nothing yet" (the non-finding is itself useful).

2. **Add a mandatory "Quality Review" dimension separate from the retention gate.** Per phase:
   - Phase 2 adds an LLM-judge+operator code review of 3 modules/phase on design, observability, testability, error-handling, surprise-count.
   - Phase 3 adds counterfactual A/B of sections on matched task mix (requires toggle wiring to land first — so gate this behind that prerequisite).
   - Phase 4 adds a 30-memory-per-collection spot check with a content-quality rubric; flag redundancy, staleness, within-domain fit.
   - Phase 5 (wiki) adds the same content-quality rubric.

3. **Add a "Gap Analysis" section to every phase decision doc.** What capability, test, measurement, or feature *should* exist in this subsystem's area and does not? The audit must name at least three gaps per phase or state explicitly that none were found.

4. **Wire the operator-in-the-loop signal.** Minimal: add a 👍/👎/skip flag to the 09:30 and 22:30 digest. Persist to `data/audit/operator_flags.jsonl` with `audit_trace_id` cross-ref. This lands the EVS 0.10 weight as real data instead of placeholder.

5. **Restate framing in §0 of the plan.** Replace/amend the operating principles with an explicit line:
   > *The goal of this audit is to evaluate quality, usefulness, and soundness. Removal is a minority of expected outcomes. Identifying excellence, gaps, and strengths is equally in scope.*
   And rename the gate tuple: KEEP → **KEEP-HARDEN** (affirmative good); KEEP-MONITOR (passed but watching); REVISE; SHADOW; DEMOTE; ARCHIVE; **PROMOTE** (new).

### Q5. Queue additions / refinements?

Two new P1 items, one P2, plus one targeted edit to the plan doc. Kept tight to respect the audit-cap discipline (current audit-cap headroom is ample but abuse would undo the spirit of the override). See §4.

---

## 3. Phase-by-phase granular notes

### Phase 0 — Instrumentation

- **Best-executed of the four.** Fail-open tracing, toggle registry with shadow semantics, deferred PASS ruling, queue-cap override scoped to audit sources only.
- **Weakness:** toggles are registered but not wired. Until `[AUDIT_PHASE_0_TOGGLE_CALL_SITES]` lands, the substrate cannot actually support A/B. Every Phase 3/4/5/9 claim that depends on toggle-based comparison is blocked on this follow-up.
- **Missing:** no audit coverage of the tracing system's own accuracy (costs↔trace join validation is explicitly deferred; no test asserts `audit_trace_id` is correctly propagated across the spawn boundary under race conditions).
- **Action:** Keep as is. Watch the 2026-04-23 gate. Ensure toggle call-sites ship before any phase claims a counterfactual.

### Phase 1 — Wiring Inventory

- **Sound and scoped honestly.** Not labelled a quality audit; does not pretend to be.
- **Weakness:** classification is four buckets (ALIVE/DORMANT/DEAD/DUPLICATE). Adds no cohesion or ownership signal. E.g., 215 ALIVE files with no ownership or runbook are classed the same as 215 well-owned files.
- **Missing:** no inventory of modules without a "why added" trail (§3.7 of plan requires it as a gate on demotion).
- **Action:** out-of-scope to fix in Phase 1. Feed into the Phase 1 follow-up list a single line to run a `why-added trail` inventory (git blame + grep commit messages) the next time the inventory is re-run.

### Phase 2 — Spine Module Quality

- **Strongest single defect of the four phases.** Called "Quality Audit", delivers code-hygiene metrics. A reviewer reading the code would catch different issues.
- **The PASS gate is mechanical.** `adapters` passes because coverage ≥ 40% and dead exports = 0; but it has 68 mypy errors and its underlying design was not reviewed.
- **The REVISE ruling applied to 13/14 modules is mostly "trim your __init__.py and add a few tests."** That is a cleanup agenda wearing a quality audit's nameplate.
- **Missing entirely:** design review, API surface ergonomics, error-path correctness, observability (does the module emit enough signal to be debugged under load?), defect-density via git log spelunking.
- **Action:** Add `[AUDIT_PHASE_2_QUALITY_REVIEW_SAMPLE]` to run a code-review pass on 3 modules per sprint (see §4).

### Phase 3 — Prompt Assembly

- **Best proxy-based work of the four.** 334-episode corpus is real, task-type stratified, covers 35 days. Honest caveats in §5 of the scorecard.
- **But the PASS ruling is proxy-dependent.** Weighted vs raw utilization choice drives a 0.886 headline vs a 0.244 borderline figure. The decision doc tickets this under existing `[PROMPT_CONTEXT_QUALITY_POLICY_REVIEW]` rather than resolving it here — which is prudent sequencing, but the scorecard's §0 headline prints "PASS" without the caveat-weight.
- **MISLEADING=0 is a proxy artefact and is admitted.** The 13 failure/crash episodes all died before the brief-use threshold. The MISLEADING validator follow-up is the correct response.
- **Missing:** counterfactual section-ablation. "When I remove `failure_patterns` on maintenance tasks, does outcome quality drop?" is the only decisive usefulness question and it is not answered here. Blocked on toggle wiring.
- **Missing:** "What sections should we have but don't?" gap analysis.
- **Action:** Keep ruling as-is; add gap analysis to scorecard in a §7 addendum once toggle wiring lands (quick follow-up).

### Phase 4 — Brain Usefulness

- **Best epistemic practice of the four.** INSUFFICIENT_DATA with two capture gaps called out in P0/P1 tickets, one independent routing REVISE on `clarvis-infrastructure`, zero overreach.
- **But the tool built is removal-biased.** Attribution share ≥ 15% PASS, < 5% DEMOTE. No companion tool measures memory *content* quality.
- **Missing:** content-quality spot-check per collection; taxonomy sanity-check (are the collections at the right joint?); memory-intake-quality (are store operations well-formed?); gap analysis (what memory classes do we fail to capture?).
- **Recall@K=1.0 on a 20-query golden set is a weak positive signal** — the query set is small, synthetic, and six weeks stale (`data/brain_eval/latest.json`). Phase 4 correctly deferred hard claims on this basis.
- **Action:** Add `[AUDIT_PHASE_4_MEMORY_CONTENT_QUALITY_SPOT_CHECK]` to sample 20 memories per collection and score for redundancy / staleness / within-domain fit.

---

## 4. Corrections to apply

### 4.1 Plan-doc edit (small, targeted)

Add to `docs/internal/audits/CLARVIS_DEEP_AUDIT_PLAN_2026-04-16.md` §0 Operating Principles — one new principle, one gate rename:

- **New Principle 7:** "The goal of this audit is to evaluate quality, usefulness, and soundness. Removal is a minority of expected outcomes. Identifying excellence, gaps, and strengths is equally in scope."
- **Gate tuple amendment:** add `PROMOTE` to the outcome vocabulary (Phases 2–9). A subsystem reaches PROMOTE when EVS ≥ 0.7 AND a concrete investment case exists (more tests, wider integration, documentation, replication).

### 4.2 Queue items (all via AUDIT_CAP_OVERRIDE, source="audit_meta")

**P1** (two):

1. **`[AUDIT_PHASE_2_QUALITY_REVIEW_SAMPLE]`** — Add a lightweight code-review pass to Phase 2. Sample 3 spine modules per sprint (rotate: first pass `brain`, `cognition`, `context`). For each, run `scripts/metrics/llm_context_review.py` (or equivalent LLM-judge pass) plus a human-written paragraph on: design clarity, API ergonomics, error-path correctness, observability, testability, defect-density via git log. Output: `docs/internal/audits/SPINE_CODE_REVIEW_<date>_<module>.md`. Acceptance: one review doc lands per module; scorecard gets a §Quality Review column. This is the missing "did a reviewer read the code?" axis.

2. **`[AUDIT_OPERATOR_FEEDBACK_LOOP]`** — Wire an operator-in-the-loop signal. Minimal design: extend the 09:30 and 22:30 digest reports (`cron_report_morning.sh` / `cron_report_evening.sh`) to include a 👍 / 👎 / `/rate <trace_id> <1-5>` Telegram response path. Persist to `data/audit/operator_flags.jsonl` with `audit_trace_id` cross-ref. This lands the EVS 0.10 "operator-flagged help" weight as real data instead of proxy. Acceptance: ≥ 5 flags collected in a 7-day canary; one row cross-references a live audit trace; scorecard doc section added.

**P2** (one):

3. **`[AUDIT_PHASE_4_MEMORY_CONTENT_QUALITY_SPOT_CHECK]`** — Complement the attribution tool with a content-quality spot check. Sample 20 memories per collection (stratified: 5 newest, 5 oldest, 10 random). Score on a simple rubric: `crisp` (0/1), `actionable` (0/1), `within_domain` (0/1), `redundant` (0/1). LLM-judged with optional operator override. Output: `data/audit/memory_content_spot_check.json` + `docs/internal/audits/MEMORY_CONTENT_QUALITY_<date>.md`. Acceptance: one pass over all 10 collections lands; highest-redundancy collection is named; any `non_within_domain ≥ 0.3` collection is flagged for taxonomy review.

### 4.3 Follow-up hygiene

- Each subsequent phase decision doc must carry a §Gap Analysis heading with at least three gaps, or an explicit "no gaps found" statement signed by the decision owner.
- Each subsequent phase decision doc must carry a §Promote Candidates heading with any subsystems meeting the PROMOTE criterion, or "none yet" stated.
- Phase 11 synthesis must carry a "Top 5 Genuinely Excellent" list in addition to the decisions matrix.

---

## 5. What NOT to change

- **Anti-false-demotion machinery.** §0.3 and §3 controls are doing real work; leaving them in place.
- **Phase 0 substrate.** No changes to the tracing / toggle / replay system. It is the most solid piece shipped today.
- **Phase-ordering dependency chain.** Phase 0 → 1 → 2 → 3 → 4 ordering is sound and should be preserved.
- **Queue-cap override.** It correctly scoped audit-sourced items. Do not generalize it.
- **Per-sprint artifact discipline.** Every phase ships artifacts and tickets — good. Do not relax this.

---

## 6. One-paragraph verdict

The four decision docs (Phase 0, 2, 3, 4) are individually honest, methodologically clean, and carry heavy anti-false-demotion controls. The *program* they belong to is framed by gate categories that ask "should this be removed?" rather than "is this good, and how can it be better?" Phases 2 and 3 accepted hygiene and lexical-overlap proxies as stand-ins for "quality" and "usefulness" respectively — honest about the proxies, but still rating a subsystem on them. Phase 4 is the most epistemically careful and also the most explicit about what infrastructure is still missing (prompt capture on spawns, structured retrieval on traces). The plan already specifies an operator-in-the-loop EVS weight but no phase has implemented the data-collection mechanism for it. Correcting the framing is cheap: add a PROMOTE bucket, mandate gap analysis per phase, wire operator feedback, add code-review and content-quality passes. None of these corrections require rolling back any Phase 0–4 work.

---

_Reviewer: operator. Status: advisory; no code paths affected. Next action: decide whether to apply §4.1 plan edit and file §4.2 queue items._

---

## Addendum: Operator Feedback Loop — Plumbing Confirmed (2026-04-19)

**§4.2 item `[AUDIT_OPERATOR_FEEDBACK_LOOP]` is now wired end-to-end.**

Implementation:
- **`scripts/tools/operator_feedback.py`** — CLI + library for digest-level flags (`up`/`down`) and per-trace ratings (1–5). Persists to `data/audit/operator_flags.jsonl` with schema `{timestamp, audit_trace_id|null, digest_id|null, flag, note|null}`.
- **`cron_report_morning.sh`** (09:30) and **`cron_report_evening.sh`** (22:30) — both now include a `💬 FEEDBACK` section with `/digest_flag <id> up|down` and `/trace_rate <trace_id> <1-5>` commands, plus the most recent audit trace IDs.
- **Cross-referencing verified:** trace ratings link to real trace files in `data/audit/traces/<date>/`. The first cross-referenced flag was recorded against trace `20260419T060004Z-9d8c5b`.

This lands the EVS 0.10 "operator-flagged help" weight (§Execution Value Score) as a real data source instead of a placeholder proxy. The 7-day canary window begins 2026-04-19.

_Status: plumbing complete. Acceptance criteria (≥ 5 flags in 7-day canary, ≥ 1 cross-referenced trace) are measurable from `operator_flags.jsonl`._

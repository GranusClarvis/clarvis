# Decomposition Remediation & Structural Policy Plan — 2026-03-29

## Purpose

This plan combines:
1. the full audit of the long-function decomposition campaign (`docs/decomposition_audit_2026-03-29.md`), and
2. the proposed replacement for the broken AST/auto-queue policy (`docs/STRUCTURAL_QUALITY_POLICY_PLAN_2026-03-29.md`).

The goal is to fix the concrete damage already done, preserve the decompositions that genuinely improved the codebase, and replace the current line-count-driven mechanism with a scalable structural review system that better fits Clarvis.

---

## Executive Summary

### What happened
A weak structural heuristic became an autonomous enforcement loop:
- `clarvis/metrics/quality.py` used a binary `reasonable_function_length` check (>100 lines)
- `scripts/heartbeat_postflight.py` used AST scanning with a stricter `_max_func_lines = 80`
- postflight then auto-inserted `[DECOMPOSE_LONG_FUNCTIONS]` queue tasks
- autonomous runs executed those tasks as if line count itself were the maintenance objective

### What the audit found
Per `docs/decomposition_audit_2026-03-29.md`:
- 12 commits in the campaign
- 17 files with actual decompositions
- ~85 helpers extracted
- 74 helpers are worth keeping
- 8 areas are over-fragmented and should be recombined
- 1 real regression bug was introduced in `clarvis/brain/search.py`

### Strategic conclusion
The decompositions were **not a universal mistake**.
The policy that generated them **was**.

So the right response is **not** “revert everything.”
It is:
1. fix the regression,
2. recombine the over-fragmented cases,
3. keep the genuinely good decompositions,
4. permanently replace line-count auto-remediation with a structural review system.

---

## Objectives

### Primary objectives
- Fix the P0 bug introduced by decomposition
- Reduce fragmentation where decomposition hurt clarity
- Preserve decompositions that improved modularity and readability
- Eliminate any future automatic queueing based on arbitrary line limits
- Replace binary structure scoring with a richer advisory system

### Secondary objectives
- Make structural policy human-auditable
- Tie future structural refactor recommendations to real maintenance pain
- Improve postflight observability without creating churn pressure
- Ensure future autonomous refactors are intent-based, not metric-cult behavior

---

## Current State

### Already done
- Removed `[DECOMPOSE_LONG_FUNCTIONS]` from `memory/evolution/QUEUE.md`
- Disabled auto-queue reinsertion in `scripts/heartbeat_postflight.py`
- Wrote first-pass replacement policy proposal to `docs/STRUCTURAL_QUALITY_POLICY_PLAN_2026-03-29.md`
- Completed full audit report in `docs/decomposition_audit_2026-03-29.md`

### Still unresolved
- P0 bug in `clarvis/brain/search.py`
- Over-fragmented helper clusters identified in audit
- Binary `reasonable_function_length` metric still exists
- Complexity gate still does AST scanning but currently only logs a coarse line-limit message
- No structural audit artifact / dashboard / triage flow yet

---

## Source-of-Truth Findings from Audit

## P0 — Critical Fix

### `clarvis/brain/search.py`
**Issue:** `_query_single_collection` lost the real query parameter during extraction.

**Observed impact:**
- text-search fallback passes `query_texts=[""]`
- fallback path is silently degraded when embedding computation fails
- this is a functional regression, not a stylistic one

**Required action:**
- add `query: str` parameter to `_query_single_collection`
- pass it through from `_dispatch_collection_queries`
- replace `""` fallback with the actual query string
- add regression test for fallback behavior

---

## P1 — Recombine Over-Fragmented Areas

### `clarvis/brain/search.py`
- merge `_apply_recency_scores` + `_sort_results` back into `_score_and_sort`
- inline `_finalize_recall` back into `recall()`

**Reason:** too many small single-caller fragments; clarity loss outweighs modular benefit

### `scripts/heartbeat_preflight.py`
- recombine `_preflight_reasoning_chain`
- recombine `_preflight_routing`
- recombine `_preflight_compress_episodes`

**Reason:** trivial wrappers, one caller each, low semantic independence

### `scripts/daily_brain_eval.py`
- recombine `_score_usefulness`
- recombine `_score_failures`
- recombine `_score_trends`
- recombine `_score_speed`
into `_assess_quality()`

**Reason:** scoring pipeline became too atomized; helpers too small and tightly coupled

### `scripts/heartbeat_postflight.py`
- merge `_pf_prompt_optimization` + `_pf_prediction_resolve` into a single phase helper

**Reason:** sequential tiny sub-phases with no meaningful independent reuse

---

## P2 — Minor Cleanup

### `scripts/heartbeat_postflight.py`
- `_mark_task_in_queue` should log on exception instead of swallowing errors silently

### `scripts/heartbeat_preflight.py`
- `_preflight_assemble_context` should stop taking a wide positional signature; use a builder object / dataclass / context dict

### `clarvis/cognition/context_relevance.py`
- rename cryptic local variable abbreviations in `_weighted_means`

---

## What should be kept as-is

The audit strongly supports keeping most decompositions, especially in these files:
- `scripts/self_representation.py`
- `scripts/generate_status_page.py`
- `clarvis/context/assembly.py`
- `clarvis/context/dycp.py`
- most of `scripts/performance_benchmark.py`
- most of `clarvis/heartbeat/gate.py`
- most of `scripts/heartbeat_gate.py`
- most of `scripts/llm_brain_review.py`
- most of `scripts/reasoning_chain_hook.py`

This matters because the remediation should be selective, not reactionary.

---

## Structural Policy Replacement

## Why the old model failed
The previous loop made three category errors:

1. It treated a **heuristic** as a **rule**
2. It treated a **signal** as a **queue generator**
3. It treated **refactorability** as equivalent to **longness**

That is exactly how you get unnecessary code churn.

---

## New policy: structural review, not line-count enforcement

### Principle
Clarvis should optimize for:
- comprehension
- change safety
- testability
- maintainability under iteration

—not visual smallness or arbitrary function-length thresholds.

### New architecture

#### Layer 1 — Structural risk scoring
Replace `reasonable_function_length` with a richer advisory score.

Suggested signals:
- length bucket (>120, >180, >260)
- nesting depth
- branch count
- return count
- local variable count
- exception complexity
- side-effect density
- mixed-responsibility indicators
- repeated mutation of multiple unrelated objects
- pure-helper density (negative signal if already cleanly modular)

Output:
- `low`
- `medium`
- `high`
structural risk

#### Layer 2 — Role-aware dampening
Classify function role before deciding urgency:
- orchestrator / pipeline
- renderer / formatter
- prompt builder
- parser / transformer
- adapter / wrapper
- algorithmic core
- persistence / mutation boundary

Examples:
- long renderer with flat flow → low/medium
- long orchestrator with named phases → medium, review only
- mixed parsing + validation + persistence + reporting → high

#### Layer 3 — Advisory outputs only
Postflight may emit:
- `OK`
- `REVIEW_LATER`
- `REVIEW_SOON`
- `HIGH_RISK_REFACTOR_CANDIDATE`

It must not auto-create queue items from structural risk alone.

#### Layer 4 — Queue creation requires corroboration
A structural task can be queued only if **both** of these are true:
- structural risk is **high** (not medium)
- a human reviewer or periodic audit has confirmed the concern

Future gate (activate when signals become computable):
- repeated regressions in file/function
- repeated churn in short window
- poor or missing tests around the area

Until at least 2 of those future signals are automated, the gate is: **high risk + manual confirmation**.

#### Layer 5 — Intentful task phrasing
Allowed:
- separate rendering from data assembly
- isolate side effects from scoring logic
- split persistence from validation
- review structure of X for maintainability

Forbidden:
- decompose until <= N lines
- split all oversized functions
- reduce functions to target line cap

---

## End-to-End Remediation Roadmap

## Phase 0 — Immediate Safety (today)

### Goals
- stop the bleeding
- preserve evidence
- prevent recurrence while remediation is underway

### Tasks
1. Keep `[DECOMPOSE_LONG_FUNCTIONS]` removed from queue
2. Keep auto-queue insertion disabled in postflight
3. Preserve both docs as references:
   - `docs/decomposition_audit_2026-03-29.md`
   - `docs/STRUCTURAL_QUALITY_POLICY_PLAN_2026-03-29.md`
4. Treat any new structure recommendation as manual-review-only until replacement system lands

### Tasks (continued)
5. Enumerate all call sites of `add_task` / `add_tasks` in the codebase and verify none encode structural/line-count criteria

### Audit Results (2026-03-29)
**All call sites verified safe.** 18 callers of `add_task`/`add_tasks` identified:
- llm_brain_review, performance_benchmark, goal_tracker, evolution_loop, research_to_queue, cron_doctor, clarvis_reflection, prediction_review, meta_learning, obligation_tracker, absolute_zero, brain_store, cli_queue, self_model, episodic_memory (all non-structural)
- heartbeat_postflight: 4 call sites (self_test_harness, code_validation, memory_quality_gate, action_accuracy_guard) — none structural/line-count
- `_pf_complexity_gate` in postflight already has auto-queue **disabled** (report-only mode)
- `queue_writer.add_tasks()` is gated by `should_allow_auto_task_injection` from runtime mode system

**No caller generates structural/line-count tasks.** Exit criteria met.

### Exit criteria
- no automatic queue insertion for line-count tasks
- no queue items with `<= N lines` objective
- all auto-queue call sites audited and confirmed safe

---

## Phase 1 — Correctness Remediation (P0/P1 code fixes)

### Goals
- fix the real bug
- remove fragmentation in the worst identified cases
- keep behavior stable

### Tasks
1. Fix `clarvis/brain/search.py` fallback query bug
2. Add regression test specifically covering fallback path without embedding
3. Recombine the 8 over-fragmented helper areas identified in audit
4. Apply the 3 minor cleanup items
5. Run targeted tests for each touched file/module
6. Run broader smoke tests / benchmark sanity if search path is touched

### Exit criteria
- search fallback regression fixed and tested
- over-fragmented areas recombined cleanly
- no net new behavioral regressions

---

## Phase 2 — Metric Replacement

### Goals
- remove the binary smell-metric as a driver of autonomous behavior
- replace it with interpretable structural-risk reporting

### Tasks
1. Replace `reasonable_function_length` in `clarvis/metrics/quality.py`
2. Introduce `structural_complexity_risk`
3. Return a richer payload, e.g.:
   - overall risk
   - top reasons
   - top candidate functions
4. Keep metric advisory; do not wire it to queue generation

### Example output shape
```json
{
  "structural_complexity_risk": {
    "score": 0.62,
    "level": "medium",
    "top_candidates": [
      {
        "file": "scripts/example.py",
        "function": "build_report",
        "reasons": ["mixed_io_and_formatting", "high_branch_count", "long_function"]
      }
    ]
  }
}
```

### Exit criteria
- no binary pass/fail pressure from line count alone
- metric exposes rationale instead of a raw threshold breach

---

## Phase 3 — Postflight Replacement

### Goals
- keep AST inspection useful
- make it observational, not coercive

### Tasks
1. Replace `_pf_complexity_gate()` line-cap logic
2. Add structural analysis of changed files only
3. Emit a small JSON artifact, e.g. `data/structural_review.json`
4. Include:
   - flagged functions
   - risk level
   - reasons
   - recommendation level
5. Log summaries, but do not mutate queue

### Exit criteria
- postflight reports structural risk cleanly
- postflight cannot autonomously create decomposition tasks

---

## Phase 4 — Manual Structural Audit Tool (DEFERRED)

**Status**: Deferred until demonstrated need. Build this when a maintainer has manually requested structural review at least twice. Phase 3's JSON artifact is sufficient for now.

### Proposed command (when activated)
- `python3 -m clarvis audit structure` or `scripts/structural_audit.py`

### Output should include
- ranked candidates with role classification
- reasons for concern + suggested refactor shape
- recommended action: ignore / watch / review / targeted refactor

### Activation criteria
- at least 2 manual structural review requests from a maintainer
- Phase 3 JSON artifact proves insufficient for the review workflow

---

## Phase 5 — Queue Governance Hardening

### Goals
- prevent future metric-cult task generation
- force queue entries to express intent, not aesthetics

### Tasks
1. Extend `queue_writer.add_tasks()` to tag auto-generated tasks with `source: auto` metadata
2. Require `source: manual` or `source: audit` for any structural refactor task
3. Reject auto-generated tasks whose description matches structural/line-count patterns as a fallback safety net
4. Add wording policy for structural tasks: must describe the actual structural concern, not a line-count target

### Exit criteria
- auto-generated structural tasks are blocked at the provenance level, not just by text matching
- manual structural tasks require explicit source attribution

---

## Phase 6 — Benchmark & Dashboard Integration

### Goals
- surface structural debt without turning it into a blind optimization target

### Tasks
1. Expose structural-risk summaries on dashboard/status page as informational debt
2. Track trend, not just point score
3. Correlate structural-risk findings with:
   - regressions
   - churn
   - validation failures
4. **Hard firewall**: Structural risk scores must never be a PI dimension or autonomous optimization target. They are maintenance observability, not performance metrics. Changing this requires explicit human approval with written rationale — not self-validation by the system that would benefit from optimizing it.

### Exit criteria
- visibility without metric-gaming pressure
- no structural metric feeds into PI, quality score, or any autonomous optimization loop

---

## Decision Rules Going Forward

## Refactor when
- function mixes unrelated responsibilities
- side effects and pure logic are tangled
- repeated churn/regressions occur in same area
- phase boundaries are unclear enough to hinder review
- testability improves substantially by decomposition

## Leave alone when
- function is long but linear and readable
- it acts as a clear pipeline/orchestrator
- rendering/formatting is clearer in one chunk
- behavior is stable and not causing maintenance pain
- decomposition would create tiny single-use wrappers with no semantic independence

---

## Risks and Failure Modes

### Risk 1 — Over-correcting into anti-modularity
Avoid reacting to this incident by merging everything back. The audit does not support that.

### Risk 2 — Rebranding line count under another name
If structural risk is still mostly length in disguise, the same pathology will return.

### Risk 3 — Making postflight too expensive
AST analysis must remain cheap and incremental; changed-file analysis only.

### Risk 4 — New silent queue writers elsewhere
Need to confirm no other subsystem auto-generates line-count-based tasks.

---

## Suggested Implementation Order

1. **Fix P0 bug in `clarvis/brain/search.py`**
2. **Recombine the 8 over-fragmented areas**
3. **Apply P2 cleanups**
4. **Raise `reasonable_function_length` threshold to 200 in `quality.py`** (don't remove; reduce false positives)
5. **Build `structural_complexity_risk` as separate advisory function** (3 signals: length bucket, caller count, role classification)
6. **Replace postflight complexity gate with report-only structural review**
7. **Add queue governance guardrails** (provenance-based, not text-matching)
8. **Integrate structural reporting into dashboard as observability** (hard firewall: never feeds PI)
9. *(Deferred)* Build structural audit CLI tool when demonstrated need arises

---

## Deliverables

### Already written
- `docs/decomposition_audit_2026-03-29.md`
- `docs/STRUCTURAL_QUALITY_POLICY_PLAN_2026-03-29.md`
- `docs/DECOMPOSITION_REMEDIATION_AND_STRUCTURAL_POLICY_PLAN_2026-03-29.md` (this file)

### To build next
- code fix + recombination patch set
- `structural_complexity_risk` metric
- report-only structural postflight output
- optional `clarvis audit structure` command
- queue guardrails for structural task wording

---

## Final Recommendation

Treat this as a policy failure with a localized code cleanup requirement.

The correct posture is:
- **fix the real regression immediately**
- **recombine only the small number of genuinely over-fragmented extractions**
- **keep the majority of good decompositions**
- **replace line-count enforcement with role-aware structural review**

That gives Clarvis a structure policy that is:
- more scalable,
- more adaptive,
- less gameable,
- and far less likely to start autonomously chopping healthy code into decorative crumbs.

---

## Executive Review

**Reviewer**: Claude Code Opus (executive function), 2026-03-29
**Verdict**: Plan is sound in diagnosis and intent. Six refinements recommended below.

### What's strong

1. **Correct triage**: 74 keeps / 8 recombine / 1 bug is exactly the right distribution for selective remediation. The plan resists the temptation to wholesale revert.
2. **Root-cause framing**: "The policy was the mistake, not the decompositions" is the right frame. The three category errors (heuristic→rule, signal→queue, refactorability→longness) are precisely stated.
3. **Advisory-first principle**: Layers 3-5 correctly decouple observation from action.
4. **Phase 0/1 separation**: Immediate safety + code fixes before policy redesign is the right sequencing.

### Critique and recommended changes

#### 1. `reasonable_function_length` feeds into `compute_code_quality_score()` — removal has downstream effects

The plan says "replace `reasonable_function_length`" but doesn't address that it's one of ~6 boolean checks in `_ast_structural_checks()` (`clarvis/metrics/quality.py:122`), which feeds `structural_passed` in `compute_code_quality_score()` (line 340). That score is used in code-generation quality assessment.

**Recommendation**: Don't remove the check from `quality.py` in Phase 2. Instead:
- Raise the threshold from 100 to 200 (reduces false positives on healthy orchestrators)
- Keep it as one boolean vote among several structural checks
- Build `structural_complexity_risk` as a *separate, advisory-only* function — not as a replacement wired into the same scoring pipeline
- Phase 2 exit criteria should explicitly state: "new metric does NOT feed into `compute_code_quality_score()` or any PI dimension"

#### 2. Phase 2 scope creep — 10-signal metric is overengineered for current need

The plan proposes ~10 AST signals (nesting, branch count, return sites, local variables, boolean complexity, exception fan-out, side-effect density, mixed-responsibility indicators, mutation tracking, helper-call density). This is a multi-week project that risks becoming its own optimization target.

**Recommendation**: Start with 3 signals that the audit actually found predictive:
- **Length bucket** (>120 / >180 / >260) — coarse, not a threshold
- **Caller count** — single-caller helpers are the fragmentation signature the audit caught
- **Role classification** (orchestrator / renderer / algorithmic) — the one signal that most changed audit verdicts

Add more signals only when these three prove insufficient. The audit showed that role awareness alone would have prevented most bad decompositions.

#### 3. Layer 4 corroboration sources don't exist yet — "2 of 4" is a paper rule

The plan requires "2 of 4" for queue creation: high risk, repeated regressions, repeated churn, poor test coverage. But Clarvis has no automated regression-tracking, no churn-rate metric, and no per-function coverage data. Without these, Layer 4 degrades to "high risk + human says so" — which is fine, but should be stated honestly.

**Recommendation**: Rewrite Layer 4 as:
- Queue creation requires **high structural risk AND manual review confirmation**
- Drop the "2 of 4" formula until at least 2 of the 4 signals are actually computable
- Add a note: "When regression-tracking or churn-rate metrics exist, revisit this gate"

#### 4. Phase 5 queue governance — text pattern matching is fragile

Rejecting tasks matching `<=80 lines` or `oversized functions` is trivially circumvented by rewording. The real invariant is: **no queue task should be auto-generated from structural metrics alone**.

**Recommendation**: Gate on *provenance*, not *phrasing*:
- Tag auto-generated tasks with `source: auto` in queue metadata
- Require `source: manual` or `source: audit` for any structural refactor task
- The `queue_writer.py` already has `add_tasks()` as a single entry point with mode-gating — extend that, not a text filter

#### 5. Phase 4 (structural audit tool) is premature — defer until demand emerges

Nobody has asked for `clarvis audit structure`. The plan proposes building it before establishing that periodic structural audits are a real workflow. This is the same "build tool → tool generates work → work justifies tool" loop that caused the original problem.

**Recommendation**: Move Phase 4 to "Future / On-Demand" and gate it on: "Build this when a maintainer has manually requested structural review at least twice." Phase 3's JSON artifact is sufficient for now.

#### 6. Phase 6 needs a harder firewall against gamification

The plan says "avoid making structure score directly gamified in PI *unless validated first*." That hedge ("unless validated") is exactly how the previous metric crept in.

**Recommendation**: State unconditionally: **Structural risk scores must never be a PI dimension or autonomous optimization target.** They are maintenance observability, not performance metrics. If this ever changes, it requires explicit human approval with a written rationale — not validation by the system that would benefit from optimizing it.

### Additional blind spot: no other auto-queue sources audited

Risk 4 flags "new silent queue writers elsewhere" but doesn't prescribe an action. The verification found that `queue_writer.add_tasks()` is the single entry point, gated by `should_allow_auto_task_injection`. But the *callers* of that function should be enumerated.

**Recommendation**: Add to Phase 0: "Grep for all call sites of `add_task` / `add_tasks` in the codebase and verify none encode structural/line-count criteria."

### Summary of recommended edits

| # | Section | Change |
|---|---------|--------|
| 1 | Phase 2 | Don't remove `reasonable_function_length` from quality.py; raise threshold to 200; build new metric as separate advisory function |
| 2 | Phase 2 | Reduce initial signals from 10 to 3 (length bucket, caller count, role classification) |
| 3 | Layer 4 | Replace "2 of 4" with "high risk AND manual confirmation"; acknowledge missing signals |
| 4 | Phase 5 | Gate on task provenance metadata, not text pattern matching |
| 5 | Phase 4 | Defer to "Future / On-Demand"; gate on demonstrated need |
| 6 | Phase 6 | Unconditional firewall: structural risk must never feed PI or autonomous targets |
| 7 | Phase 0 | Add: enumerate all `add_task`/`add_tasks` call sites to verify no other structural auto-queuers |

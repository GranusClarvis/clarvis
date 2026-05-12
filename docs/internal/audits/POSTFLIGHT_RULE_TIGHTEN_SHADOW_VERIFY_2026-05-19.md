# POSTFLIGHT_RULE_TIGHTEN Shadow Verify — Scaffold + Contract-Drift Finding

**Task:** `[POSTFLIGHT_RULE_TIGHTEN_SHADOW_VERIFY]`
**Authored (scaffold):** 2026-05-12 (the day the rule-fix shipped — `0d4977a`)
**Verdict ETA:** 2026-05-15 (corrected from 2026-05-19; see §1)
**Status:** PREMATURE — shadow window has not elapsed. This document captures the **contract drift** between the queue task and the actually-shipped change, and re-anchors the audit methodology to what was built. The numeric verdict (FLIP / HOLD / REVERT) is deferred until the window closes.

---

## 1. Contract drift summary

The queue task `[POSTFLIGHT_RULE_TIGHTEN_SHADOW_VERIFY]` was written on the assumption that the rule-fix shipped under flag `POSTFLIGHT_RULE_TIGHTEN=1` with parallel `outcome` vs `shadow_outcome` recording for a 7-day window. **None of that is what shipped, and additionally the change is not on main.** See §1.5 below for the merge-state finding.

### 1.5 The rule-fix is not on main (critical)

`git log --all --oneline --graph` shows `0d4977a` ("fix(esr): split code_validation into errors vs advisories") on a side branch (worktree `worktree-melodic-seeking-oasis`), **not on `main`**. Main's HEAD is `e196617`, two commits ahead of `12dc3d6` (the backfill), and `0d4977a` is a sibling, not an ancestor. The current on-disk `clarvis/metrics/code_validation.py` (executed by heartbeat scripts) returns `{valid, errors, refinement}` — the old shape — confirming the change is unmerged. QUEUE marks the parent task `[ESR_STRUCTURE_RULE_NOT_FAILURE]` `[x] [UNVERIFIED]` shipped today; that's accurate in the "code-was-written" sense but misleading in the "production-behavior-changed" sense. The shadow window has not started in production.

**Consequence for the audit:** even if the queue's 7-day window were honored, there would be nothing to measure — the new rule has not run against any episode in production. The first action item below is therefore a merge gate, not an audit.

### 1.6 Drift table

| Dimension | Queue contract | Actually shipped (`0d4977a`, 2026-05-12 19:06 UTC) |
|---|---|---|
| Env flag | `POSTFLIGHT_RULE_TIGHTEN=1` | `STRUCTURE_RULE_ADVISORY=1` |
| Rollout mode | A/B shadow (gated off by default) | **Default-on**, 3-day soft rollout |
| Window length | 7 days → audit on **2026-05-19** | 3 days → audit due **2026-05-15** |
| Parallel recording | `outcome` (rule-off) vs `shadow_outcome` (rule-on) on every episode | None — only the new rule path runs; old behavior unrecoverable without flag flip |
| Episode field added | `shadow_outcome` | None — observability via `code_validation:advisory:<subtype>` tag |
| Site of change | "`clarvis/cognition/postflight/*` (or `scripts/heartbeat_postflight.py`)" — a postflight rule predicate | `clarvis/metrics/code_validation.py` — the validator now returns `errors` vs `advisories`; postflight reads `errors` only |
| Scope | "one regex/predicate per false-downgrade class" (≥4 classes) | One class: `function_too_long` demoted from error → advisory; `bare_except` retained as hard error |

**Root cause of drift:** the rule-fix landed under the sibling task `[ESR_STRUCTURE_RULE_NOT_FAILURE]` (which targeted only the §3 21-episode `function_too_long` class), not under `[ESR_POSTFLIGHT_FALSE_DOWNGRADE_RULE_FIX]` (which targeted all 4 classes from ESR_UNVERIFIED_TRIAGE §3). The wider 4-class fix was never built. The audit task in QUEUE was written against the wider task's spec.

This is consistent with how the falsely-downgraded population got fixed: the **one-shot backfill** (commit `12dc3d6`, +0.114 ESR realized) handled the 57 known episodes directly, the **verification retry probe** (`7e42738`) catches future false-downgrades reactively, and the **structure-rule fix** (`0d4977a`) prevents the dominant single-class (21/56 episodes, 37.5%) from re-occurring. The other three predicted classes (lint `0 errors`, git-dirty, commit-count drift) were not addressed by a rule change.

---

## 2. Re-anchored audit methodology (runnable on 2026-05-15)

Since no parallel `shadow_outcome` was recorded, we cannot compute the queue's contracted "FP rate of the new rule" or "FN rate" directly. The runnable substitute audit:

### 2.1 Episode-tag census (3-day window: 2026-05-12 19:06 UTC → 2026-05-15 19:06 UTC)
- Load `data/episodes.json`, filter to episodes in window.
- Count episodes with tag `code_validation:advisory:function_too_long`. These are the "the new rule fired and demoted a finding to advisory" cases.
- Count episodes with tag `code_validation:fail` overall — confirm structure-only fails are gone (`function_too_long` should not appear as a hard `errors[]` entry in any new episode).
- Acceptance window targets:
  - Advisory-tagged episodes: ≥ 1 (sanity — the rule is firing). The queue's `≥30` shadow-window bar was set for the 7-day A/B which doesn't exist; rescale to the 3-day default-on window.
  - Hard `code_validation:fail` from structure-only causes: 0.

### 2.2 ESR delta verification
- Compute ESR over the 3-day window. Compare against the pre-fix baseline (0.828 at last triage, 0.942 after backfill).
- Confirm direction: ESR should remain ≥ 0.94 (the backfill already lifted it). The rule fix's marginal contribution is **forward-only** (prevents new false-downgrades) and won't show up as a step-change in a 3-day window where backfill dominates.

### 2.3 Held-out manual review (10 sampled episodes)
- Sample 10 episodes tagged `code_validation:advisory:function_too_long` from the window (or, if fewer than 10 fired, sample all that did + pad with `code_validation:pass` episodes that had a >100-line function in the diff).
- For each, manually adjudicate: would the old rule have downgraded this to `partial_success`? Is the new outcome correct?
- FP rate target: < 2% (i.e. 0/10 wrong flips to success).
- FN rate target: < 5% (i.e. would-be-true-partials that the new rule lets through as success). This is the more useful number given the asymmetric harm — false-success is worse than false-partial because it hides real failure.

### 2.4 Bare-except regression check
- Confirm `bare_except` is still a hard error: grep test file `tests/test_esr_structure_rule_not_failure.py` — there should be a "bare-except still-hard" case, AND no recent episode should have advisory-tagged a `bare_except` finding.

### 2.5 Verdict criterion
- **FLIP DEFAULT** (`STRUCTURE_RULE_ADVISORY=1` becomes hard-coded; flag removed): if 2.1 ≥ 1 advisory fired AND 2.3 FP < 2% AND 2.3 FN < 5% AND 2.4 passes.
- **HOLD** (keep flag, extend shadow): if any check is marginal or any single FP found in 2.3.
- **REVERT** (set default to 0 / revert commit): if 2.3 FP ≥ 20% or 2.4 fails.

---

## 3. Premature-verdict placeholder

Today (2026-05-12 22:00 UTC, ~3h after rule-fix landed):
- Recent episodes (2026-05-11 + 2026-05-12 = 19): **0** with any `advisory` tag, **0** with `shadow_outcome` field.
- This is consistent with the design — `shadow_outcome` was never wired (see §1), and the advisory path requires a recent commit that adds a >100-line function for the tag to emit.
- **No verdict possible today.** Re-run the §2 census on 2026-05-15.

---

## 4. Follow-up actions

0. **MERGE GATE (blocking everything below):** branch holding `0d4977a` must be merged to main before any shadow window starts. Without this merge, the heartbeat continues to execute the old validator and the rule-fix has zero production effect — regardless of what QUEUE says about shipped state. Open a new queue item `[ESR_STRUCTURE_RULE_NOT_FAILURE_MERGE]` to land `0d4977a` (and any other unmerged sibling ESR commits) onto main. Once merged, reset the 3-day shadow clock from merge-time, not commit-time.
1. **Re-anchor the QUEUE audit task** to the actually-shipped flag name and 3-day window (audit due 3 days after merge, not 2026-05-19). Update task name from `POSTFLIGHT_RULE_TIGHTEN_SHADOW_VERIFY` → `STRUCTURE_RULE_ADVISORY_SHADOW_VERIFY` for findability. **(Done in this commit; see QUEUE.md NEW ITEMS.)**
2. **If audit on 2026-05-15 passes → FLIP**: append `[STRUCTURE_RULE_ADVISORY_DEFAULT_HARDCODE]` to QUEUE NEW ITEMS — remove the `STRUCTURE_RULE_ADVISORY` env-check from `clarvis/metrics/code_validation.py:_structure_rule_advisory_enabled` and bake the advisory split in.
3. **If audit on 2026-05-15 reveals FN > 5%**: the rule is too permissive — file a new triage task to identify which signals are being missed.
4. **Address the unbuilt classes**: the queue's `[ESR_POSTFLIGHT_FALSE_DOWNGRADE_RULE_FIX]` was retired (folded into `[ESR_STRUCTURE_RULE_NOT_FAILURE]`) but only the structure class was addressed. The triage report named 3 other candidate classes (lint `0 errors`, git-dirty-after-success, commit-count drift on parallel-job episodes). Quantify those classes' residual contribution to false-downgrades after the backfill — they may already be addressed by the verification retry probe (`7e42738`) and incomplete_by_design routing (`e196617`).
5. **Process learning** captured in QUEUE meta-note: audit tasks scheduled against contracts written before the implementation lands should re-check the contract on day-of, not blindly execute. Today's contract drift would have produced a false-negative audit ("infrastructure missing, verdict REVERT") had we mechanically followed the queue.

---

## 5. Methodology notes

- **Why a 3-day shadow when 7 days was contracted:** the shipping author chose default-on with a 3-day rollback window (per commit message). This is more aggressive than the queue contract but tolerable because (a) the rule split is surgical (one subtype), (b) bare-except retains hard-error semantics, (c) the backfill+retry-probe stack already provides defense-in-depth, and (d) episode volume is ~30/day so 3 days yields ~90 episodes — adequate for the 10-sample manual review.
- **Why no parallel `shadow_outcome`:** parallel recording would have required running the old rule against every episode and storing the counterfactual. That's ~2x validator cost on every postflight. Default-on + tag emission gives the same observability with one validator pass per episode.
- **The queue's "≥30 episodes" shadow-window bar:** corresponds to the 7-day-A/B framing. Rescale to the 3-day default-on window: the relevant population is *episodes-that-would-have-tripped-the-old-rule*, not all-episodes. Acceptance: ≥ 1 advisory-tagged episode (sanity) plus ≥10 sample size for §2.3 (pad with would-have-tripped pass-tagged episodes if needed).

---

**Author:** Clarvis (autonomous)
**Sources:** commits `0d4977a` (rule fix), `12dc3d6` (backfill), `7e42738` (retry probe), `e196617` (incomplete_by_design); `docs/internal/audits/ESR_UNVERIFIED_TRIAGE_2026-05-12.md`; `memory/evolution/QUEUE.md` line 714; `clarvis/metrics/code_validation.py` (current HEAD).

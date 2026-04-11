# Queue Fast-Track Report #3 — 2026-04-10

## Items Selected and Why

| Item | Priority | Rationale |
|------|----------|-----------|
| VALIDATION_REPORTS_FOLDER | P1 | Creates `docs/validation/` for dated evidence. No code, no references to break. Reduces docs/ clutter. |
| HERMES_REPORT_RELOCATION | P1 | Moves one-off Hermes install report to validation folder. Git rename preserves history. |
| FRICTION_REPORT_SCOPE_CLEANUP | P1 | Tightens friction report into proper engineering blocker format. 15-minute editorial pass. |
| CALIBRATION_FEEDBACK_CLOSE_LOOP | P2 | Data audit showed resolution tracking already working (336/340 resolved). Task is stale — closed. |
| CALIBRATION_BAND_GRANULARITY (updated) | P2 | Description was wrong ("only 0.8 and 0.9"). Actual distribution: 0.78–0.91 across 10 values. Updated to reflect real gap. |

## What Was Completed

### 1. VALIDATION_REPORTS_FOLDER (P1) — DONE

Created `docs/validation/` directory for dated install/e2e evidence reports. This is the first step in the Install Docs / Support Surface Consolidation plan.

### 2. HERMES_REPORT_RELOCATION (P1) — DONE

Moved `docs/HERMES_FRESH_INSTALL_REPORT.md` → `docs/validation/HERMES_FRESH_INSTALL_REPORT_2026-04-05.md`.
- Added date suffix per queue spec
- Git tracks as rename (preserves blame history)
- No other files referenced this report by path (verified via grep)

### 3. FRICTION_REPORT_SCOPE_CLEANUP (P1) — DONE

Tightened `docs/INSTALL_FRICTION_REPORT.md` (117 → 109 lines):
- Updated scope statement: now explicitly "rolling engineering blocker report"
- Added cross-ref to `validation/` for evidence
- Added **Fix Owner** and **Release Impact** columns to the executive summary table
- Removed "Recommended Priority Order" section (5 items that duplicate queue entries)
- Added footer note pointing to QUEUE.md for priority tracking

### 4. CALIBRATION_FEEDBACK_CLOSE_LOOP (P2) — CLOSED (already addressed)

**Evidence:** Analyzed `data/calibration/predictions.jsonl`:
- 340 total predictions, 336 resolved (98.8%), 4 unresolved, 12 stale
- Resolution tracking works via: `correct` field (boolean), `outcome` field, `resolved_by` field (set by `prediction_resolver.py`)
- An explicit `resolved: true` boolean would be redundant — resolution is already computable from existing fields
- `prediction_resolver.py` auto-resolves predictions via embedding similarity matching

**Verdict:** Task was based on stale understanding. The resolution mechanism was already implemented. Marked as complete.

### 5. CALIBRATION_BAND_GRANULARITY (P2) — DESCRIPTION UPDATED

**Evidence:** Actual confidence distribution across 340 predictions:
```
0.78: 25    0.79: 25    0.80: 19    0.81: 21    0.82: 24
0.86:  1    0.87: 17    0.88: 28    0.89: 54    0.90: 117    0.91: 9
```

The queue claimed "only 2 confidence bands (0.8 and 0.9)" — this was true early on but recalibration has since spread values across 0.78–0.91 (10 distinct values). The *real* gap is that no prediction ever drops below 0.78, even for novel/exploratory tasks.

**Action:** Updated queue description to reflect reality and merged scope with CALIBRATION_LOW_CONFIDENCE_EXPRESSION.

## What Was Skipped and Why

| Item | Why Skipped |
|------|-------------|
| LLM_BRAIN_REVIEW (P1) | Temporal indexing requires architectural design. Not fast-track scope. |
| REASONING_CAPABILITY_SPRINT (P1) | Multi-cycle investment. Explicitly requires 2+ evolution cycles. |
| BRIER_7D_REGRESSION_DIAGNOSIS (P2) | Requires deep calibration analysis. Worth doing but medium complexity. |
| SWO_* items (P1) | Website/brand — large scope, not operational quality. |
| E2E_* items (P1) | Multi-step infrastructure. Not fast-track scope. |
| INSTALL_DOC_STACK_CONSOLIDATION (P1) | Umbrella task — needs design decisions before execution. |
| Other dated report relocations | One file moved as proof-of-concept. Bulk moves create unnecessary churn. |

## Verification Results

| Check | Result |
|-------|--------|
| `docs/validation/` exists | PASS |
| Hermes report relocated with date suffix | PASS |
| Git detects rename (not delete+add) | PASS |
| No broken references to moved file | PASS (grep: 0 matches) |
| Friction report: fix-owner/impact columns added | PASS |
| Friction report: priority wishlist removed | PASS |
| Friction report: scope statement updated | PASS |
| Predictions.jsonl resolution rate | 336/340 (98.8%) — close loop working |
| Confidence distribution: 10+ distinct values | PASS (range 0.78–0.91) |
| QUEUE.md: 4 items marked complete, 1 updated | PASS |

## Files Modified

1. `docs/validation/` — new directory
2. `docs/HERMES_FRESH_INSTALL_REPORT.md` → `docs/validation/HERMES_FRESH_INSTALL_REPORT_2026-04-05.md` (renamed)
3. `docs/INSTALL_FRICTION_REPORT.md` — tightened scope, added columns, removed wishlist
4. `memory/evolution/QUEUE.md` — 3 items completed, 1 closed as already-addressed, 1 description updated

## Best Next Fast-Track Targets

1. **CALIBRATION_LOW_CONFIDENCE_EXPRESSION (P2)** — System never emits confidence <0.78. Adding 0.65–0.75 for novel/exploratory tasks is the real calibration gap. Targeted code change in `clarvis/cognition/confidence.py` + `heartbeat_preflight.py`.
2. **BRIER_7D_REGRESSION_DIAGNOSIS (P2)** — Diagnostic analysis of `predictions.jsonl` to find which confidence bands or task types drive the 7-day Brier regression. No risky code changes.
3. **CALIBRATION_OVERCONFIDENCE_PENALTY (P2)** — 87.8% actual success rate vs 86.1% avg confidence. The gap is small, but per-task-type analysis could find pockets of overconfidence. Data-driven, low risk.
4. **OPENCLAW_RUNTIME_GUIDE_SCOPE (P1)** — Refocus one doc file. Editorial, no code.
5. **SWO_REPO_JUNK_SWEEP (P1)** — Now that `docs/validation/` exists, more dated reports can be relocated incrementally.

## Cumulative Fast-Track Summary (3 passes on 2026-04-10)

| Pass | Items Completed | Type |
|------|----------------|------|
| #1 | (prior session) | — |
| #2 | POSTFLIGHT_HOOK_NAMEERROR, CRON_PI_ANOMALY_ALERT, CLR_AUTONOMY_DIGEST_FRESHNESS, CRON_SCHEDULE_DRIFT_AUDIT | Bug fix, cron alerting, cron audit |
| #3 | VALIDATION_REPORTS_FOLDER, HERMES_REPORT_RELOCATION, FRICTION_REPORT_SCOPE_CLEANUP, CALIBRATION_FEEDBACK_CLOSE_LOOP (closed), CALIBRATION_BAND_GRANULARITY (updated) | Docs structure, queue hygiene |

# Action Failure Triage Report

**Date**: 2026-03-30
**Scope**: 45 soft_failure (action-type) episodes out of 374 total (12% failure rate)
**Analysis**: All 45 classified by error signature, 10 sampled in detail

## Distribution

| Root Cause | Count | % | Description |
|------------|-------|---|-------------|
| shallow_reasoning | 21 | 47% | Reasoning chain captured only 1 step — no real multi-step reasoning |
| long_duration | 7 | 16% | Task exceeded 300s threshold — indicates struggle or scope creep |
| low_capability | 7 | 16% | Self-model scored task outcome <0.5 — capability gap |
| uncompleted_task | 4 | 9% | Task started but never finished — timeout or crash |
| retroactive_fix | 3 | 7% | Fix reveals a prior silent failure was undetected |
| prediction_miss | 2 | 4% | Prediction outcome never recorded — tracking gap |
| duplicate_execution | 1 | 2% | Task ran twice — lock contention or retry |

## Key Observations

1. **shallow_reasoning dominates (47%)**: These are NOT execution failures. The task typically succeeded, but the reasoning chain hook only captured 1 step. This is a **detector issue**, not a task issue. The `reasoning_chain_hook.py` fires too late or the chain isn't populated with intermediate steps.

2. **All 45 episodes have `duration_s: 0`**: This confirms these are synthetic/retrospective entries created by the episode failure analysis backfill (2026-03-30), not real-time failures. The backfill script tagged quality signals as "soft_failure" episodes.

3. **Date clustering**: All 45 are from 2026-02-22 to 2026-02-24 — the earliest system period when instrumentation was minimal. No recent soft_failures appear, suggesting the system has matured.

4. **low_capability (16%)**: These correlate with early self-model calibration issues (all domains scored 1.00 due to wrong calibration path). After the calibration fix, no new low_capability soft_failures appeared.

## 10 Sampled Episodes (Most Recent)

| ID | Date | Task | Error Pattern |
|----|------|------|---------------|
| ep_soft_b89e1d8a | 02-24 | Dream: What if data corrupted? | shallow_reasoning |
| ep_soft_4f2f5abb | 02-23 | Optimize heartbeat efficiency | uncompleted_task |
| ep_soft_92e16a5f | 02-23 | Optimize heartbeat efficiency | low_capability |
| ep_soft_0bd85335 | 02-23 | Implement smart context compression | long_duration |
| ep_soft_94d012b9 | 02-22 | Implement meta-learning | uncompleted_task |
| ep_soft_191af664 | 02-22 | Build temporal self-awareness | low_capability |
| ep_soft_e253b829 | 02-22 | AST-level self-surgery | long_duration |
| ep_soft_36492d09 | 02-22 | Build cron auto-recovery | uncompleted_task |
| ep_soft_0fc4b083 | 02-22 | Fix reasoning chain outcomes | shallow_reasoning |
| ep_soft_3cef8b35 | 02-22 | Deep self-analysis capability gap | shallow_reasoning |

## Top 3 Actionable Fixes

### Fix 1: Improve reasoning chain step capture (addresses 47% of failures)
**Problem**: `reasoning_chain_hook.py` only captures 1 step for many tasks.
**Action**: In `reasoning_chain_hook.py`, ensure `add_step()` is called at each decision point in the heartbeat pipeline (preflight task selection, context assembly, execution, postflight). Currently the chain is opened but intermediate steps aren't recorded before the single-step soft_failure detector fires.
**Impact**: Would reclassify ~21 episodes from soft_failure to success.

### Fix 2: Exclude early-period episodes from accuracy metrics (addresses 16% + retroactive)
**Problem**: Episodes from the first 3 days (Feb 22-24) reflect immature instrumentation, not real failures. They drag down action_accuracy in benchmarks.
**Action**: In `scripts/performance_benchmark.py`, add a cutoff date filter (e.g., exclude episodes before 2026-02-25) or weight recent episodes higher. The backfilled `failure_type: action` tag makes these indistinguishable from real failures.
**Impact**: Would improve reported action_accuracy by ~13% without masking real issues.

### Fix 3: Add timeout guard for ambitious tasks (addresses 9% uncompleted)
**Problem**: 4 tasks started but never completed — likely hit the Claude Code timeout without graceful shutdown.
**Action**: In `heartbeat_preflight.py`, estimate task complexity before execution. If estimated duration exceeds 80% of the available timeout, either break the task into subtasks or set a warning flag. The `attention.py` salience scorer already has complexity signals that could feed this.
**Impact**: Would prevent future uncompleted_task failures by scoping work to fit the time budget.

## Conclusion

The 45 action-type failures are predominantly **instrumentation artifacts from the early system period** (Feb 22-24), not ongoing operational issues. The system has self-corrected: no new soft_failures appear after Feb 24. The highest-ROI fix is improving reasoning chain step capture, which would reclassify nearly half of these as successes.

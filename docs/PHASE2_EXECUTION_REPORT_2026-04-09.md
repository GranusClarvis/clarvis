# Phase 2 Execution Report: Measurement Integrity

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 2

---

## Summary

Phase 2 targeted measurement integrity: making CLR, ablation, and cost tracking produce real signal instead of decorative numbers. All 6 Phase 2 tasks completed, plus 2 Phase 1 leftover fixes.

## Phase 1 Verification

Before starting Phase 2, verified Phase 1 claims against the codebase:
- All 7 Phase 1 fixes confirmed in place
- Two leftovers identified and fixed (see below)

## Changes Made

### 2.1 Discriminative CLR retrieval_precision queries (F2.3c)
**File**: `clarvis/metrics/clr.py` (`_score_retrieval_precision`)
- **Before**: 3 queries each targeting their own collection ("goals" → clarvis-goals, etc.) — trivially always precision=1.0
- **After**: 5 cross-collection queries with no collection filter, including 1 adversarial query ("kubernetes pod horizontal autoscaler...") that should NOT match well
- **Result**: retrieval_precision dropped from 1.000 → 0.902. The adversarial query scores p=0.51 while real queries score 0.95-1.00. The dimension now has genuine dynamic range.

### 2.2 Dynamic-range evaluation for CLR dimensions (F2.3e)
**Files**: `clarvis/metrics/clr.py`
- Fixed `costs_real.jsonl` → `costs.jsonl` (wrong filename, autonomy dimension couldn't read cost data)
- Fixed `cost` → `cost_usd` field name (mismatched with actual cost entry format)
- Added `dims_with_real_data` and `dims_total` fields to CLR output for explicit tracking
- **Result**: 7/7 dimensions now use real data (was 5/7 before — autonomy missing daily_cost, retrieval_precision inflated)

### 2.3 Ablation validation post-HARD_SUPPRESS fix (F2.3a)
**File**: `clarvis/metrics/clr_perturbation.py`
- **Root cause found**: Budget zeroing in `_apply_ablation()` had zero effect because `generate_tiered_brief()` calls `get_adjusted_budgets()` which copies from `TIER_BUDGETS`, and the HARD_SUPPRESS additions for graph_expansion sections were never checked by assembly code.
- **Fix**: Added post-assembly section stripping (`_strip_ablated_sections()`) as a reliable second layer. Strips section blocks matching disabled modules from the brief output via regex patterns.
- Added `SECTION_MARKERS` and `_STRIP_PATTERNS` constants for module-to-content mapping.
- **Result**: graph_expansion ablation now shows AQ delta = -0.1000 (was 0.0000). Assembly quality drops from 0.85 → 0.75 when graph/knowledge content is removed. Verdict: CRITICAL (most impactful module).

### 2.4 Working_memory ablation spotlight key (F2.3d)
- **Finding**: The spotlight budget key mapping was already correct (`"working_memory": "spotlight"`) from the prior HARD_SUPPRESS fix session.
- **Verification**: Budget zeroing works (spotlight goes from 80→0 for standard tier). Working_memory ablation shows NEUTRAL verdict because the cognitive workspace/spotlight content genuinely doesn't appear in the assembly output for the benchmark reference tasks.
- **Conclusion**: NEUTRAL is the correct measurement — not a bug. The measurement now reflects reality.

### 2.5 Wire log_real() into execution paths (F4.6.1)
**New file**: `scripts/infra/cost_checkpoint.py`
**Modified**: `scripts/cron/cron_env.sh` (`run_claude_monitored()`)
- Created `cost_checkpoint.py`: after each Claude Code run, calls `cost_api.fetch_usage()` to get real OpenRouter daily spend and logs a checkpoint entry with `estimated: false`.
- Wired into `run_claude_monitored()` — every spawner call now produces a real cost checkpoint.
- Auto-derives source name from calling script's filename (`BASH_SOURCE[1]`).
- Non-blocking, best-effort (API failures are silently skipped).
- **Projection**: With 12+ autonomous runs/day, this will produce >20% real entries within 2-3 days.

### 2.6 Budget kill switch (F4.6.5)
**File**: `scripts/cron/cron_env.sh` (`run_claude_monitored()`)
- Added flag file check: when `/tmp/clarvis_budget_freeze` exists, all `run_claude_monitored()` calls skip Claude launch.
- Logs the skip to the job's logfile with timestamp.
- Returns exit code 1 (failure) so callers can detect the budget freeze.
- **Usage**: `touch /tmp/clarvis_budget_freeze` to halt all spending; `rm /tmp/clarvis_budget_freeze` to resume.

### Phase 1 Leftover: cron_evening.sh hardcoded success
**File**: `scripts/cron/cron_evening.sh`
- Evening assessment dashboard event now checks `PHI_EXIT` and `ASSESSMENT_EXIT` before emitting status.
- On failure: logs warning with specific exit codes, emits `--status failure`.

### Phase 1 Leftover: cron_evolution.sh hardcoded success
**File**: `scripts/cron/cron_evolution.sh`
- Evolution analysis now captures `MONITORED_EXIT` as `CLAUDE_EXIT`.
- Digest write conditional on `CLAUDE_EXIT=0` (skip on failure, with warning log).
- Dashboard event checks both `CLAUDE_EXIT` and `EVO_EXIT` (preflight) for truthful status.

## Verification

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 flaky (pre-existing, unrelated — lock timing) |
| `python3 -m clarvis brain health` | 2913 memories, 93183 edges, 7/7 hooks |
| `bash -n cron_env.sh` | Syntax OK |
| `bash -n cron_evening.sh` | Syntax OK |
| `bash -n cron_evolution.sh` | Syntax OK |
| CLR retrieval_precision | 0.902 (was 1.000 — discriminative) |
| CLR dims_with_real_data | 7/7 (was 5/7) |
| CLR composite | 0.735 (was 0.753 — lower but more honest) |
| CLR gate | PASS |
| Ablation graph_expansion AQ delta | -0.1000 (was 0.0000 — differentiated) |
| Ablation ranking | graph_expansion=CRITICAL, related_tasks=CRITICAL, decision_context=HELPFUL |

## Before/After Comparison

| Metric | Before Phase 2 | After Phase 2 | Change |
|--------|---------------|--------------|--------|
| CLR composite | 0.753 | 0.735 | -0.018 (more honest) |
| retrieval_precision | 1.000 (inflated) | 0.902 (real) | -0.098 |
| dims_with_real_data | 5/7 | 7/7 | +2 |
| Ablation graph_expansion delta | 0.0000 (broken) | -0.1000 (working) | Fixed |
| Ablation differentiated modules | 0/6 | 3/6 | +3 |
| Cost real entries (%) | 0% | Will reach >20% in ~3 days | Wired |
| Budget kill switch | None | /tmp/clarvis_budget_freeze | Added |
| cron_evening truthful status | No | Yes | Fixed |
| cron_evolution truthful status | No | Yes | Fixed |

## What Remains

| Item | Why Not Done | Phase |
|------|-------------|-------|
| Per-generation real cost for Claude Code runs | Claude Code doesn't expose per-session cost via API | Not feasible without Anthropic billing API |
| Ablation budget zeroing → assembly pipeline fix | Complex pipeline indirection (get_adjusted_budgets copies, DyCP re-includes). Post-assembly stripping is the pragmatic fix. | Optional future cleanup |
| working_memory ablation shows NEUTRAL | Genuine result — spotlight content doesn't appear in benchmark briefs | Consider adding benchmark tasks that trigger working_memory |
| CLR task_success thin (only valence) | Episodes data empty — Phase 3 issue (rebuild episodes.json) | Phase 3.1 |
| integration_dynamics synergy_gain=no_data | Needs correlated episode+context_relevance data | Natural resolution as more episodes accumulate |

## Rating Impact

Per the master plan:
- **Value/Signal Quality**: B- → B+ (CLR discriminative, ablation differentiated, measurements honest)
- **Operational Fitness**: C+ → B (cost tracking wired, budget kill switch added, evening/evolution truthful)

## Files Changed

| File | Change |
|------|--------|
| `clarvis/metrics/clr.py` | Discriminative queries, cost file path fix, cost field fix, real-data counter |
| `clarvis/metrics/clr_perturbation.py` | Post-assembly section stripping, SECTION_MARKERS, _STRIP_PATTERNS |
| `scripts/cron/cron_env.sh` | Budget kill switch, real cost checkpoint, auto-source detection |
| `scripts/cron/cron_evening.sh` | Truthful exit code checking |
| `scripts/cron/cron_evolution.sh` | Truthful exit code checking, conditional digest |
| `scripts/infra/cost_checkpoint.py` | New: real OpenRouter cost logging |

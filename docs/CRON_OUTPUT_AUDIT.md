# Cron Output Quality Audit — 2026-03-10

_Audit period: 2026-03-03 to 2026-03-10 (7 days)_
_Sources: `memory/cron/autonomous.log`, `autonomous.log.1`, `memory/cron/digest.md`_

## Executive Summary

85 heartbeat slots triggered over 7 days. Only **49 produced useful output** (58%). The remaining 42% was split between cognitive-load deferrals (29 slots, 34%) and timeouts (6 slots, 7%). Timeouts are particularly costly: 6 timed-out slots consumed **5.17 hours** of Claude Code time — nearly equal to the **5.88 hours** spent on all 49 successful executions combined.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total heartbeat slots | 85 |
| Successful executions (exit=0) | 49 (58%) |
| Deferred (cognitive load) | 29 (34%) |
| Timed out (exit=124) | 6 (7%) |
| Other non-exec (no task, queue empty) | 1 (1%) |
| Avg successful duration | 432s (7.2 min) |
| Total successful exec time | 5.88 hours |
| Total timeout waste | 5.17 hours |
| Avg postflight duration | 105s |
| Long postflights (>100s) | 25/55 (45%) |
| Batch=3 (max batching) | 32/41 Claude runs (78%) |
| Batch=1 (no batching) | 5/41 (12%) |

## Problem 1: Deferral Loops (29 wasted slots)

Tasks repeatedly selected by attention/salience scoring but rejected by cognitive load filter, consuming preflight time (~30s each) with zero output.

| Task | Times Deferred | Days Stuck |
|------|---------------|------------|
| ACTR_WIRING | 11 | 3 (Mar 5, 7, 9) |
| GRAPH_SOAK_5DAY | 5 | 2 (Mar 6-7) |
| MEMR3_REFLECTIVE_RETRIEVAL | 4 | 2 (Mar 7-8) |
| SPINE_SHADOW_DEPS | 3 | 1 (Mar 5) |
| CALIBRATION_BRIER_RECOVERY | 2 | 1 (Mar 9) |
| BROWSER_TEST | 2 | 2 (Mar 7-8) |
| GRAPH_SOAK_7DAY | 1 | 1 (Mar 6) |
| (empty task string) | 1 | 1 (Mar 9) |

**Root cause**: The task selector ranks these highly (salience 0.6-0.9) but cognitive load filter always rejects them. The selector doesn't learn from prior deferrals — it picks the same task again next hour.

**Recommendation R1**: Add a **deferral cooldown** to `task_selector.py`. After a task is deferred 2+ consecutive times, suppress it for 12 hours (or until a different trigger raises it). Track in `data/deferral_counts.json`.

**Recommendation R2**: Move GRAPH_SOAK_* tasks to a manual-only section in QUEUE.md. They require multi-day monitoring, not heartbeat execution. BROWSER_TEST similarly requires interactive browser infrastructure.

## Problem 2: Research Repo Timeouts (5.17 hours wasted)

All 6 timeouts were research/repo-review tasks. These tasks involve cloning repos and deep code analysis — inherently unbounded work that often exceeds the 1500s timeout.

| Task | Attempts | Outcome |
|------|----------|---------|
| RESEARCH_REPO_OBLITERATUS | 3 (2 timeout + 1 success) | Succeeded on 3rd try |
| RESEARCH_REPO_AGENCY_AGENTS | 3 (2 timeout + 1 unclear) | Unclear final status |
| RESEARCH_REPO_QWEN_AGENT | 1 timeout | Never succeeded |
| EVOLVING_CONSTITUTIONS_MULTIAGENT | 1 timeout | Never succeeded |

**Cost**: 6 × ~1550s avg = 9,300s = **2.58 hours of Claude Code time wasted**, plus opportunity cost of 6 heartbeat slots that could have done productive work.

**Recommendation R3**: Add a **timeout-after-fail** rule: if a task times out once, deprioritize it (salience penalty -0.3) and flag for `cron_implementation_sprint.sh` (longer timeout). If it times out twice, move to Backlog with a note.

**Recommendation R4**: Cap `RESEARCH_REPO_*` tasks at 1 per day in `task_selector.py`. Currently these can monopolize 3-4 consecutive slots.

## Problem 3: Postflight Overhead (45% are >100s)

25 of 55 postflights exceeded 100 seconds. Average postflight is 105s — over 1.5 minutes of pure overhead per heartbeat.

Breakdown of slow components (from log analysis):
- PERF GATE: ~110s (performance benchmark runs all gates)
- Meta-gradient/self-representation: ~5-10s
- Pytest self-test: ~3-8s (runs when code was modified)

**Recommendation R5**: Run PERF GATE at **reduced frequency** (every 3rd postflight instead of every one). Performance metrics don't change meaningfully per-heartbeat. This could save ~70s per skipped run.

## Problem 4: Recurring Import Errors

Two persistent errors across all 7 days, never fixed:

1. **`periodic_synthesis` hook failure** (13 occurrences): `cannot import name 'EpisodicMemory' from 'episodic_memory'` — the class was renamed/moved but the hook still references the old name.

2. **`task_router.py` DeprecationWarning** (112 occurrences): Every single preflight and postflight logs this warning. The migration to `clarvis.orch.router` is incomplete.

**Recommendation R6**: Fix the `EpisodicMemory` import in the periodic_synthesis hook — it's been broken for 7+ days. Silence or complete the `task_router.py` migration.

## Problem 5: QUEUE.md Task-Not-Found (34 occurrences)

34 times postflight couldn't mark a task complete in QUEUE.md because the task string didn't match (truncation or already archived). This means completed tasks aren't being properly tracked.

**Recommendation R7**: Use task tag matching (`[TASK_TAG]`) instead of full-string prefix matching for QUEUE.md completion. Tags are unique and stable.

## Problem 6: Codelet Competition Monotony

Every single heartbeat shows `winner=code coalition=code,memory,research` with near-identical activation scores. The attention codelet competition provides zero differentiation — it always selects "code" regardless of the task type.

**Recommendation R8**: Review codelet activation scoring in `attention.py`. If the competition always produces the same winner, it's adding compute cost (~0.04s) with no steering value. Either tune the activation functions or remove the competition step.

## Slot Utilization by Day

| Date | Slots | Executed | Deferred | Timeout | Productive % |
|------|-------|----------|----------|---------|-------------|
| Mar 3 (Mon) | 3 | 3 | 0 | 0 | 100% |
| Mar 4 (Tue) | 12 | 12 | 0 | 0 | 100% |
| Mar 5 (Wed) | 12 | 1 | 9 | 2 | 8% |
| Mar 6 (Thu) | 12 | 8 | 2 | 2 | 67% |
| Mar 7 (Fri) | 12 | 4 | 6 | 1 | 33% |
| Mar 8 (Sat) | 11 | 9 | 2 | 0 | 82% |
| Mar 9 (Sun) | 12 | 6 | 6 | 0 | 50% |
| Mar 10 (Mon) | 7* | 6 | 0 | 0 | 86% |

_*Mar 10 is partial (audit at 12:00)_

**Notable**: Mar 5 was catastrophic (8% productive) — 9 deferrals of ACTR_WIRING and SPINE_SHADOW_DEPS, plus 2 RESEARCH_REPO timeouts. Mar 4 was perfect (100%).

## Prioritized Action Items

1. **[HIGH] R1+R2: Deferral cooldown + manual-only tasks** — Would have saved 29 slots (34% of all slots). Implement deferral memory in task_selector.py. Move GRAPH_SOAK_*, BROWSER_TEST to manual section.

2. **[HIGH] R3: Timeout-after-fail deprioritization** — Would have saved 4 of 6 timeout slots (the retries). First timeout is unavoidable, but retrying the same task immediately is pure waste.

3. **[MEDIUM] R5: Reduce PERF GATE frequency** — Would save ~25 minutes/day of postflight overhead.

4. **[MEDIUM] R7: Tag-based QUEUE.md matching** — Fixes 34 task-not-found misses over 7 days.

5. **[LOW] R6: Fix broken periodic_synthesis hook** — Easy fix, has been broken 7+ days.

6. **[LOW] R8: Review codelet competition utility** — Not urgent but highlights wasted compute.

## Estimated Impact

If R1-R3 were implemented, projected slot utilization would improve from 58% → ~80%+, and ~5 hours of Claude Code time per week would be reclaimed from timeouts and wasted preflights.

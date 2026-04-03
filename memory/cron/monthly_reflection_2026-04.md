# Monthly Structural Reflection — April 2026

_Generated: 2026-04-03 | Window: 2026-03-04 to 2026-04-03_

## Executive Summary

The past 30 days show a system executing at **89% episode success rate** (205/230 episodes) with strong brain performance (254ms avg query, all PI dimensions passing) but significant structural concerns: the autonomous log reveals a **67.7% heartbeat success rate** (44/65 runs) with 21.5% timeouts and 10.8% crashes, plus **23 days with no logged heartbeat data** (log rotation gap). The `scripts/` directory has ballooned to 141 files / 65,350 lines with at least 12 large scripts (400+ lines) that are completely dead code — never imported and never in crontab. The bloat score sits at exactly the 0.40 threshold, the weakest metric in the system. Prediction calibration is severely miscalibrated: all 100 predictions use confidence=0.90 but only 69% resolve correctly (Brier 0.2568). ROADMAP percentages are broadly accurate but several specific claims are outdated. The cognitive workspace reuse rate (88.8%) has far exceeded the 58.6% target listed in ROADMAP, and graph edges are 127.6k (not 109k). Key priority: reduce script bloat and fix the confidence calibration monoculture.

---

## Episode Trends

### 30-Day Episode Summary (n=230)

| Outcome | Count | Rate |
|---------|-------|------|
| Success | 205 | 89.1% |
| Timeout | 11 | 4.8% |
| Failure | 7 | 3.0% |
| Crash | 7 | 3.0% |

**Success rate is healthy at 89.1%**, above the PI target of 85%.

### Success Distribution by Category

| Category | Count | Notes |
|----------|-------|-------|
| Feature/other | 92 | Broadest category — queue items, new capabilities |
| Bugfix | 29 | Healthy fix rate |
| Research | 28 | Research ingestion pipeline active |
| Maintenance | 25 | Cleanup, queue hygiene |
| Benchmark | 23 | PI, CLR, brain eval work |
| Migration | 8 | Spine migrations continuing |

### Failure Patterns

**Timeouts (11):** Clustered around complex multi-step tasks — `GRAPH_STORAGE_UPGRADE` (2x), research-heavy tasks, and infrastructure rewiring. These are legitimately hard tasks hitting the 1500s ceiling.

**Crashes (7):** Recent spike (April 1-3) with 7 crashes, including instant-fail detections (1s exits). Several `OSR_*` tasks (open-source readiness) and test-writing tasks crashed. The crash guard is correctly classifying these but the root cause appears to be malformed task prompts or missing prerequisites.

**Failures (7):** Distributed across semantic work, phi recovery, and shell scripting tasks. No single dominant failure mode.

**Key pattern:** Failures are NOT clustered — they're distributed across 23 distinct task prefixes. This suggests no systemic capability gap, but rather that ~11% of tasks are inherently beyond single-heartbeat scope.

### Prediction Calibration

**Critical issue:** All 100 predictions in the 30-day window use **confidence=0.90** — a monoculture. Actual accuracy is 69%, yielding Brier score 0.2568. The system is systematically overconfident by ~21 percentage points.

| Confidence Bucket | Predictions | Actual Accuracy | Gap |
|-------------------|-------------|-----------------|-----|
| 0.90 | 100 | 69% | -21% |

**Recommendation:** The prediction system needs variance in confidence assignment. A well-calibrated system at 0.90 confidence should see ~90% accuracy. Either the confidence model is broken (always outputs 0.90) or the resolution criteria are too strict.

### Reasoning Chains

344 active chain files + 0 archived (461 total sessions per meta). Chain depth is shallow (2-3 steps) for recent chains. Quality scores are not being recorded in recent chain files (all show `q=?`), suggesting the quality scoring pipeline may have broken during recent refactoring.

---

## Script Audit

### Overview

- **141 scripts** in `scripts/` totaling **65,350 lines**
- **30+ scripts** exceed 300 lines
- **12 scripts** (7,893 lines total) are completely dead — zero imports, not in crontab

### Dead Code (Zero Imports, Not in Crontab)

| Script | Lines | Status |
|--------|-------|--------|
| `absolute_zero.py` | 1,014 | Called via `cron_absolute_zero.sh` indirectly — verify |
| `agent_orchestrator.py` | 763 | Superseded by `project_agent.py`? |
| `ast_surgery.py` | 964 | Research prototype, never integrated |
| `cleanup_policy.py` | 540 | May be called by `cron_cleanup.sh` indirectly |
| `conversation_learner.py` | 911 | Large but orphaned |
| `dashboard_server.py` | 488 | Web dashboard — standalone runner |
| `graph_cutover.py` | 430 | Historical — cutover completed 2026-03-29 |
| `llm_brain_review.py` | 663 | Called by `cron_llm_brain_review.sh` indirectly |
| `orchestration_benchmark.py` | 468 | Standalone benchmark runner |
| `prompt_builder.py` | 543 | Orphaned |
| `research_novelty.py` | 554 | Orphaned |
| `research_to_queue.py` | 557 | Orphaned |

Note: Some "dead" scripts may be called indirectly via shell wrappers — `absolute_zero.py`, `llm_brain_review.py`, and `cleanup_policy.py` should be verified before removal.

### Oversized Scripts (Top 10)

| Script | Lines | Concern |
|--------|-------|---------|
| `project_agent.py` | 3,492 | God object — agent CRUD, spawning, benchmarking, brain seeding, promotion all in one |
| `heartbeat_postflight.py` | 1,970 | 48 stages — should be decomposed into pipeline modules |
| `performance_benchmark.py` | 1,675 | Benchmark + PI + history + alerts + integration all bundled |
| `context_compressor.py` | 1,546 | Multiple compression strategies in one file |
| `heartbeat_preflight.py` | 1,475 | Attention, routing, context assembly, cognitive load all mixed |
| `directive_engine.py` | 1,406 | Only 2 imports — possible over-engineering |
| `clarvis_browser.py` | 1,226 | Dual-engine browser — reasonable given scope |
| `meta_learning.py` | 1,148 | 4 imports — may be research prototype |
| `browser_agent.py` | 1,083 | Playwright wrapper — reasonable |
| `world_models.py` | 1,065 | 6 imports — active but large |

### Spine Migration Status

The `clarvis/` spine has modules for: brain, heartbeat, cognition, context, metrics, memory, learning, runtime, orch, adapters. Good coverage, but many large scripts in `scripts/` have NOT been migrated:
- `project_agent.py` → should map to `clarvis/orch/`
- `performance_benchmark.py` → should map to `clarvis/metrics/`
- `cognitive_workspace.py` → should map to `clarvis/cognition/`
- `context_compressor.py` → partially in `clarvis/context/` already

### Duplicated Logic

- `agent_orchestrator.py` (763 lines) vs `project_agent.py` (3,492 lines) — likely superseded
- `brain.py` (313 lines, 145 imports) vs `clarvis/brain/` spine — dual-path still active
- `research_novelty.py` + `research_to_queue.py` — orphaned research pipeline

---

## ROADMAP Gaps

### Claims vs Reality

| ROADMAP Claim | Actual | Action |
|---------------|--------|--------|
| Brain: "3400+ memories" | 3,438 | Accurate ✓ |
| Graph: "106k+ edges" | 127,579 | **Outdated** — update to 127k+ |
| Reasoning: "300+ quality chains" | 344 active files | Accurate ✓ |
| Episodes: "153+ episodes" | 402 | **Outdated** — update to 400+ |
| Workspace reuse: "~53%" and target 58.6% | 88.8% | **Severely outdated** — target exceeded by 30pp |
| Phase 5.5 Cognitive Workspace: 75% | Should be 90%+ given reuse rate | **Update needed** |
| Phase 5.4 Episodic Memory: 93% → "153+ episodes" | 402 episodes | Update count claim |
| PI: "hit 1.0000" | Current PI at threshold (bloat=0.40) | Verify and possibly downgrade |
| Phase 2: "95% COMPLETE" | All items checked | Mark 100% complete |
| Phase 3.1 Confidence Gating: 70% | Calibration is broken (Brier 0.2568) | May need downgrade |

### Stalled Items

- **Phase 3.2**: "Clone → test → verify for code changes" and "Gate promotion of improvements" — no evidence of progress
- **Phase 3.3**: "Proactive research on emerging tools" and "Autonomous code review of own scripts" — no progress
- **Phase 5.1**: "Memory evolution (A-Mem style)" — still unimplemented
- **Phase 5.2**: "Can explain reasoning process" — still partial
- **Autonomy Track A.1-A.4**: Minimal progress beyond foundation; browser sessions still break periodically

### Suggested ROADMAP Updates

1. Phase 2 → 100% COMPLETE
2. Phase 4 → 75% (accounting for broken quality scoring in chains)
3. Phase 5.5 Cognitive Workspace → 90% (reuse rate 88.8%, far exceeding target)
4. Update numerical claims: episodes 400+, graph edges 127k+
5. Phase 3.1 Confidence Gating: add note about calibration monoculture issue

---

## Cron Efficiency

### Autonomous Heartbeat Performance

**Critical data gap:** Log rotation truncated March data. Only 4 days of April data (21 runs) plus Week 10 data (43 runs) are available in current logs. **23 of 31 days have zero heartbeat log data.**

| Period | Runs | Success | Timeout | Crash | Success Rate |
|--------|------|---------|---------|-------|-------------|
| 2026-W10 (Mar 4-7) | 43 | 31 | 12 | 0 | 72% |
| 2026-W14 (Apr 1-3) | 22 | 13 | 2 | 7 | 59% |
| **30-day total** | **65** | **44** | **14** | **7** | **67.7%** |

### Issues

1. **Log rotation destroys analysis data.** The truncation at the top of `autonomous.log` (`[TRUNCATED 2026-04-02]`) wipes 3 weeks of data. This makes monthly reflection impossible for most of the window.

2. **Timeout rate 21.5%** is high. Complex tasks (score≥0.60) get 1500s timeouts but still hit the ceiling. The task sizing → timeout mapping may need adjustment.

3. **Crash spike in April** (7 crashes in 3 days) — driven by instant-fail exits (1s duration). These are wasted heartbeat slots that produce no useful work.

4. **Episode success (89%) vs heartbeat success (68%) discrepancy**: Episodes are recorded per-task and include non-heartbeat work. The heartbeat pipeline has a ~20% overhead failure rate that episodes don't fully capture.

### Schedule Observations

- 12 autonomous slots/day is aggressive given the ~68% success rate — effectively ~8 productive runs/day
- The 02:45 dream engine and AZR (Sunday 03:00) slots appear functional
- Maintenance window (04:00-05:00) is well-structured with shared lock
- Evening/morning report slots (09:30, 22:30) are lightweight and appropriate

---

## Recommendations

### P0: Fix Prediction Calibration Monoculture
**Files:** `scripts/heartbeat_postflight.py` (world model recording), `scripts/clarvis_confidence.py`
**Issue:** All predictions use confidence=0.90 regardless of task complexity, producing Brier score 0.2568 (should be <0.10 for well-calibrated 0.90 predictions). The system is systematically overconfident by ~21 percentage points.
**Action:** Audit the confidence assignment path in postflight. Implement variance based on task complexity tier (simple→0.95, complex→0.70, research→0.60). Add calibration bucket tracking to the PI dashboard.

### P1: Script Bloat Reduction — Remove Dead Code
**Files:** `scripts/ast_surgery.py`, `scripts/agent_orchestrator.py`, `scripts/graph_cutover.py`, `scripts/prompt_builder.py`, `scripts/research_novelty.py`, `scripts/research_to_queue.py`, `scripts/conversation_learner.py`
**Issue:** 12 scripts totaling ~7,900 lines are never imported and not in crontab. The bloat score (0.40) is at the critical threshold.
**Action:** Archive confirmed dead scripts to `scripts/archive/` (verify shell wrappers first for `absolute_zero.py`, `llm_brain_review.py`, `cleanup_policy.py`). Target: reduce scripts/ to <130 files and <60k lines.

### P1: Fix Autonomous Log Retention
**Files:** `scripts/cron_cleanup.sh` (log rotation), `memory/cron/autonomous.log`
**Issue:** Log rotation truncates March data, leaving 23/31 days of the analysis window invisible. Monthly reflection cannot function without 30 days of data.
**Action:** Increase autonomous.log retention to 60 days (2 full monthly reflection windows). Move the truncation marker to a separate `.log.1` file instead of destructive in-place truncation.

### P2: Decompose `project_agent.py` (3,492 lines)
**Files:** `scripts/project_agent.py`
**Issue:** Single file handling agent CRUD, spawning, brain seeding, benchmarking, promotion, migration, and destruction. At 3,492 lines it's the largest script by far and violates single-responsibility.
**Action:** Split into `clarvis/orch/` submodules: `agent_crud.py`, `agent_spawn.py`, `agent_brain.py`, `agent_benchmark.py`. Keep `project_agent.py` as thin CLI wrapper.

### P2: Update ROADMAP Numerical Claims
**Files:** `ROADMAP.md`
**Issue:** Multiple claims are stale — episodes (153→402), graph edges (106k→127k), workspace reuse (53%→88.8%), Phase 5.5 percentage (75%→90%).
**Action:** Batch-update all numerical claims in a single commit. Mark Phase 2 as 100% complete. Add note about confidence calibration issue under Phase 3.1.

---

_End of monthly structural reflection. Next reflection: 2026-05-01._

# Queue Fast-Track Pass #2 — 2026-04-10

## Items Selected and Why

### 1. [PI_REFRESH_STALENESS_GUARD] — P2, Episode Success Rate Recovery
**Why selected:** Highest-leverage defensive fix. The 2026-04-09 incident where PI tanked from 0.999 to 0.701 in a single cron_pi_refresh run was caused by `benchmark_episodes()` returning 0.0 for core metrics. While the root cause was fixed in [FIX_BENCHMARK_EPISODE_MEASUREMENT], no guard existed to prevent similar future collapses from any measurement dimension.

**What was done:**
- Added a PI anomaly guard to `run_refresh_benchmark()` in `scripts/metrics/performance_benchmark.py`
- Guards 5 core metrics: `episode_success_rate`, `action_accuracy`, `retrieval_hit_rate`, `phi`, `task_quality_score`
- If any guarded metric drops >50% from its previous measurement AND the previous value was >0.1, the guard:
  - Retains the previous value instead of recording the collapse
  - Prints a `PI_ANOMALY` warning to stderr
  - Appends a structured anomaly record to `data/performance_alerts.jsonl`
  - Includes anomaly details in the report's `details.pi_anomalies` field
- Threshold: >50% drop (e.g., 0.94 → 0.0 is blocked; 0.94 → 0.90 is allowed)
- Low-value guard: metrics already below 0.1 are not protected (avoids guarding genuinely broken state)

**Tests:** 3 tests in `tests/test_pi_anomaly_guard.py`:
- `test_guard_blocks_catastrophic_drop` — 0.94→0.0 blocked, previous retained
- `test_guard_allows_normal_fluctuation` — 0.94→0.90 allowed through
- `test_guard_skips_low_prev_values` — prev=0.05→0.0 not guarded (already low)

All 3 tests pass. 90 existing tests also pass (no regressions).

**Verification:** Ran `performance_benchmark.py refresh` end-to-end — PI=0.999, no anomalies (expected), metrics file correctly written.

### 2. [TASK_QUALITY_SCORE_DIAGNOSIS] — P2, Task Quality Score
**Why selected:** Queue listed task_quality_score=0.35 as needing diagnosis, but investigation showed this was the same measurement artifact as the episode bug, not a genuine quality issue.

**What was done:**
- Traced performance_history.jsonl: 0.855 (Apr 7) → 0.846 (Apr 8) → 0.35 (Apr 9, bug) → 0.865 (Apr 10, fixed)
- The 0.35 on Apr 9 coincides exactly with the episode_success_rate=0.0 incident
- Current task_quality_score=0.865 (target 0.70, PASS) — healthy and stable
- All quality sub-components healthy: success_rate=0.941, valence=0.732, strong_memory_ratio=0.957, action_accuracy=0.941
- Marked as resolved in QUEUE.md — was measurement artifact, not a quality bug

### 3. [CRON_SCHEDULE_DRIFT_AUDIT] — P2, Cron Schedule Hygiene (partial)
**Why selected:** Low-effort non-code audit to verify cron integrity.

**What was done:**
- Compared all 48 active crontab entries against CLAUDE.md schedule table
- Found minimal drift: only 1 undocumented entry (`canonical_state_refresh.py` at Sun 05:00)
- Fixed CLAUDE.md to include the missing entry
- All other entries (timing, scripts, days-of-week restrictions) match documentation

## Intentionally Skipped

| Item | Reason |
|------|--------|
| [DEAD_CODE_TARGETED_AUDIT] | Requires careful multi-file grep analysis across cron scripts and spine imports; higher risk of false-positive deletions. Better as a dedicated session. |
| [REASONING_CAPABILITY_SPRINT] | Requires 2+ evolution cycles of deliberate practice — not a fast-track item. |
| [LLM_BRAIN_REVIEW] temporal indexing | Architectural change to retrieval pipeline — needs design work, not a quick fix. |
| [CLR_AUTONOMY_DIGEST_FRESHNESS] | Requires investigation of digest_writer.py and cron_report_*.sh interactions. Medium complexity. |
| [CRON_PI_ANOMALY_ALERT] | Shell+Telegram alert wiring — useful but lower priority now that the guard prevents silent collapses. |
| SWO/Brand items | All require design decisions and visual review — not fast-track material. |
| E2E/Install items | Require isolated test environments — too heavyweight for this pass. |

## Verification Results

| Check | Result |
|-------|--------|
| `test_pi_anomaly_guard.py` (3 tests) | PASS |
| `test_cost_tracker.py` + `test_cost_optimizer.py` + `test_metacognition.py` (90 tests) | PASS |
| `performance_benchmark.py refresh` end-to-end | PI=0.999, no anomalies |
| Cron schedule vs CLAUDE.md | 1 minor gap fixed |
| Current task_quality_score | 0.865 (target 0.70, PASS) |

## Best Next Fast-Track Targets

1. **[CRON_PI_ANOMALY_ALERT]** — Now that the guard exists, a Telegram alert for PI drops would complete the defense-in-depth. Simple shell script + jq + curl pattern.
2. **[CLR_AUTONOMY_DIGEST_FRESHNESS]** — Add staleness check for digest.md to watchdog. Direct operational benefit.
3. **[DEAD_CODE_TARGETED_AUDIT]** — Methodical grep of crontab + cron_*.sh + spine imports for each scripts/ file. Safe if done incrementally.
4. **[CALIBRATION_CONFIDENCE_BAND_AUDIT]** / **[CALIBRATION_LOW_CONFIDENCE_EXPRESSION]** — Low-risk improvements to confidence estimation. Brier score (0.1054) is the only FAIL metric.

# Queue Fast-Track Report #2 — 2026-04-10

## Items Selected and Why

| Item | Priority | Rationale |
|------|----------|-----------|
| POSTFLIGHT_HOOK_NAMEERROR_2026-04-10 | P0 | Active bug breaking 3 postflight metric hooks. One-line fix, high impact. |
| CRON_PI_ANOMALY_ALERT | P2 | Anomaly detection already 95% built in `performance_benchmark.py`; just needed Telegram wiring. Prevents silent PI collapses. |
| CLR_AUTONOMY_DIGEST_FRESHNESS | P2 | CLR autonomy score tanks when digest goes stale. One-line watchdog addition. |
| CRON_SCHEDULE_DRIFT_AUDIT | P2 | Non-code audit. Quick diff, minimal drift found. Reference file updated. |

## What Was Completed

### 1. POSTFLIGHT_HOOK_NAMEERROR (P0) -- FIXED

**Root cause:** `clarvis/heartbeat/adapters.py` defined a `_log` lambda using `sys.stderr` but never imported `sys`. The lambda loaded without error (deferred evaluation) but crashed at runtime when any of the 3 metric hooks (`perf_benchmark`, `latency_budget`, `structural_health`) tried to log.

**Fix:** Added `import sys` to the imports in `clarvis/heartbeat/adapters.py` (line 19).

**Verification:**
- `_log('test')` executes without NameError
- All 8 postflight hooks register successfully
- Hook registry loads cleanly

### 2. CRON_PI_ANOMALY_ALERT (P2) -- IMPLEMENTED

**What:** Added Telegram alerting to `scripts/cron/cron_pi_refresh.sh`. After the PI refresh completes, it checks `data/performance_alerts.jsonl` for any `PI_ANOMALY` records written in the last 5 minutes (the current refresh window). If found, sends a Telegram alert with metric names, old/new values, and drop percentages.

**Design:** Reuses the same Telegram bot token/chat_id pattern as `cron_watchdog.sh`. Only alerts on fresh anomalies to avoid re-alerting on historical records.

**Verification:** Shell syntax check passes. Python inline script tested for import validity.

### 3. CLR_AUTONOMY_DIGEST_FRESHNESS (P2) -- IMPLEMENTED

**What:** Added `check_job "digest" "$LOG_DIR/digest.md" 8` to `scripts/cron/cron_watchdog.sh`. The watchdog (runs every 30 min with `--alert`) now flags digest.md as MISSED if it hasn't been updated in 8 hours.

**Context:** Digest is maintained by 9 separate cron writers (morning, autonomous, evolution, evening, reflection, CLR benchmark, monthly reflection, orchestrator, strategic audit). It only goes stale if ALL writers fail simultaneously. The 8h grace period avoids false alarms during the overnight gap (23:00-06:00).

**Verification:** Shell syntax check passes.

### 4. CRON_SCHEDULE_DRIFT_AUDIT (P2) -- COMPLETED

**What:** Diffed live crontab (47 entries) against `scripts/crontab.reference`.

**Findings:**
- **@reboot rules:** Present in reference, missing from live crontab. Expected — `clarvis cron install` doesn't inject @reboot rules. Not a functional issue (pm2 resurrect and chromium start work independently).
- **Path normalization:** Reference uses `${OPENCLAW_HOME:-$HOME/.openclaw}/workspace` for some `cd` commands; live uses `$CLARVIS_WORKSPACE`. Functionally identical (both resolve to same path).
- **Watchdog --alert flag:** Live crontab has `--alert`, reference didn't. Fixed reference to match live.
- **All 47 live entries match the documented schedule in CLAUDE.md.** No missing jobs, no wrong times, no stale entries.

**Fix:** Updated `scripts/crontab.reference` to add `--alert` flag to watchdog entry.

## What Was Skipped and Why

| Item | Why Skipped |
|------|-------------|
| LLM_BRAIN_REVIEW (P1) | Requires architectural design for temporal retrieval — not a fast-track item. |
| REASONING_CAPABILITY_SPRINT (P1) | Multi-cycle investment, explicitly requires 2+ evolution cycles. |
| BRIER_7D_REGRESSION_DIAGNOSIS (P2) | Requires deep analysis of calibration data and confidence estimator logic. Medium complexity. |
| SWO_* items (P1) | Website/brand work — large scope, not operational quality. |
| E2E_* items (P1) | Fresh-install validation suite — large, multi-step infrastructure work. |
| FRICTION_REPORT_SCOPE_CLEANUP (P1) | Doc restructuring — low urgency, requires editorial judgment. |

## Verification Summary

| Check | Result |
|-------|--------|
| `_log()` lambda works without NameError | PASS |
| 8 postflight hooks register | PASS |
| `cron_pi_refresh.sh` syntax valid | PASS |
| `cron_watchdog.sh` syntax valid | PASS |
| Live crontab vs reference drift | Minimal (documented above) |
| `crontab.reference` updated | PASS |

## Files Modified

1. `clarvis/heartbeat/adapters.py` — added `import sys`
2. `scripts/cron/cron_pi_refresh.sh` — added PI anomaly Telegram alerting
3. `scripts/cron/cron_watchdog.sh` — added digest freshness check
4. `scripts/crontab.reference` — synced watchdog `--alert` flag
5. `memory/evolution/QUEUE.md` — marked 4 items completed

## Best Next Fast-Track Targets

1. **CALIBRATION_BAND_GRANULARITY (P2)** — Only 2 confidence bands used (0.8, 0.9). Adding 0.7 and 0.85 is a small code change in `heartbeat_preflight.py` and `clarvis_confidence.py` with direct Brier score impact.
2. **CALIBRATION_LOW_CONFIDENCE_EXPRESSION (P2)** — System never emits confidence <0.8. Adding low-confidence paths for novel/exploratory tasks is a targeted change.
3. **BRIER_7D_REGRESSION_DIAGNOSIS (P2)** — Analyze `predictions.jsonl` to find which task types are miscalibrated. Diagnostic work, no risky code changes.
4. **FRICTION_REPORT_SCOPE_CLEANUP (P1)** — Tighten one doc file. Low risk, quick editorial pass.
5. **CALIBRATION_FEEDBACK_CLOSE_LOOP (P2)** — Add `resolved: true` field to prediction records. Small schema change with downstream utility.

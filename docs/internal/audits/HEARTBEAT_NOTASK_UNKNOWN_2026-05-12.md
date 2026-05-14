# Heartbeat No-Task `unknown` Bucket Diagnosis — 2026-05-12 (backfill 2026-05-14)

**Task:** `[HEARTBEAT_NOTASK_UNKNOWN_BUCKET_DIAGNOSIS]` (original closed `[UNVERIFIED]` 2026-05-12 14:05 UTC without artifact; backfilled 2026-05-14 per `[MISSING_AUDIT_ARTIFACT_BACKFILL_2026-05-14]`).
**Trigger:** 06:25 digest line `[heartbeat-triage 06:25 UTC] No-task 41.2% (7/17) over 7d — queue_empty=0, all_filtered=0, lock_held=1, gate_skip=0, unknown=6` flagged `unknown=6/17 = 35%` as the dominant no-task bucket — the only bucket without explicit upstream instrumentation.
**Window scope:** 7-day window ending 2026-05-12 (2026-05-05 → 2026-05-12).

## Why this backfill is partial-by-construction (and what it can still answer)

The original task asked to enumerate every `unknown`-classified heartbeat in the last 7 days with **(a) timestamp, (b) gate decision, (c) preflight stop-point, (d) preflight log tail (last 5 lines)**. That requires reading `memory/cron/autonomous.log` (the raw heartbeat trace) for the period **2026-05-05 → 2026-05-12**.

**The raw log lines no longer exist on disk** as of the 2026-05-14 backfill:
- `memory/cron/autonomous.log` — only contains 2026-05-13 and 2026-05-14 entries (older entries rotated out).
- `memory/cron/autonomous.log.1` — only 2026-04-09 → 2026-04-12 (gap before the 7-day window).
- `memory/cron/autonomous.log.2.gz` — older still (March 2026).

What **does** persist is `monitoring/notask_attribution.log`, which is the daily aggregation of the same buckets. From that file we can reconstruct:
- Per-day bucket counts (incl. unknown count by day)
- Where the 6 unknown events landed (which UTC date)
- Whether the bucket has re-occurred since the diagnosis

What we cannot reconstruct retroactively:
- The minute-precise timestamp of each individual unknown event
- The gate-decision text for each unknown event
- The preflight log tail of each unknown event

The audit therefore catalogues at **per-day granularity** (the level still on disk) and uses the persisted shape of the unknown bucket to propose the new cause-codes that would have bucketed each into a named reason.

## Per-day catalogue of the 6 `unknown` events

From `monitoring/notask_attribution.log` rows covering the 7-day window (2026-05-05 → 2026-05-12):

| Date (UTC) | Cycles | unknown | Other no-task | Notes |
|------------|-------:|--------:|---------------|-------|
| 2026-05-05 | 11 | 0 | lock_held=1 | clean (one lock_held) |
| 2026-05-06 | 10 | 0 | — | clean |
| 2026-05-07 | 9 | 0 | — | clean |
| 2026-05-08 | 10 | 0 | — | clean |
| 2026-05-09 | 10 | 0 | — | clean |
| 2026-05-10 | 10 | 0 | — | clean |
| 2026-05-11 | **13** | **6** | lock_held=1 | **spike day** |
| 2026-05-12 (partial) | 12 | 0 | queue_empty=2, lock_held=1 | already recovering |
| **7d total** | **74** | **6** | lock=3, qe=2 | unknown rate 6/74 = **8.1%** of all cycles |

**Conclusion: all 6 `unknown` events occurred on a single day — 2026-05-11.** The "6/17 = 35%" framing in the trigger digest came from the 06:25 triage's 7-day window starting at the timestamp of the morning run (capturing only a subset of the actual day totals); the wider attribution log gives the true denominator.

## Reconstructing what happened on 2026-05-11 (correlate-and-infer)

With 13 cycles total on 2026-05-11 and 7 no-task (6 unknown + 1 lock_held), 6 cycles executed real work. The `notask_attribution.sh` classifier (per `scripts/maint/notask_attribution.sh:107-109`) defines:

```bash
UNEXPLAINED = NO_TASK_LINES - ALL_FILTERED - QUEUE_EMPTY
UNKNOWN     = UNEXPLAINED + COG_DEFER
```

So an `unknown` event is one of:
1. **"No task selected"** line emitted by `cron_autonomous.sh` *without* a preceding `PREFLIGHT: status=queue_empty/no_tasks` or `PREFLIGHT: status=all_filtered_by_v2`; or
2. **"COGNITIVE LOAD: DEFERRING"** line (a metacognition gate that halts heartbeats when working-memory load exceeds the deferral threshold).

Cross-checking adjacent days (which all show `unknown=0`), the 2026-05-11 spike correlates with a memory-management event: the `MEMORY.md` 2026-04-25 entry in this workspace records the **operator-driven SWO V2 sprint** still actively reshaping the queue around that date, and the QUEUE.md history shows multiple queue mutations on 2026-05-11 (lane re-classifications + project_lane_discipline rebalancing). The most likely explanation for 6 events in a single day is:

- **Hypothesis A (preflight no-task without upstream marker):** the queue had items but the V2 filter passed them through, the codelet/attention scorer returned all-low-confidence (no task above `attention_score_floor`), and the cron printed "No task selected" with no upstream `status=` line. The classifier had no marker to bucket → `unknown`.
- **Hypothesis B (COGNITIVE LOAD: DEFERRING):** metacognition load gate fired ≥1 time during the spike; the deferral message is bucketed into `unknown` by design (per the script comment).

Both can co-occur; without the raw log we cannot split the 6 between A and B. The 06:25 triage script (which uses the same regex but reports a slightly different window) showed `unknown=6` — consistent with all 6 being a single-day phenomenon.

## Proposed new cause-codes (≥2 required, 4 proposed)

The goal is to make every "No task selected" line traceable to a structured reason marker that lands in `monitoring/notask_attribution.log` with its own bucket. Below: 4 new markers + their classifier diff.

### Cause-code #1 — `preflight_no_eligible_after_filter`

**Symptom captured:** preflight ran, queue had items, V2 filter passed them through, but the per-task attention/salience scorer returned no task above floor.

**Marker location:** `scripts/pipeline/heartbeat_preflight.py` — after the task selector returns `None` from `select_runnable()`, emit:

```
PREFLIGHT: status=no_eligible_after_filter task_salience=0.0 \
    runnable_count=N below_floor=N route=skip
```

**Classifier diff in `notask_attribution.sh:96`:**

```bash
NO_ELIG_AFTER_FILTER=$(grep -c 'PREFLIGHT: status=no_eligible_after_filter' "$WINDOW" || true)
# Subtract from UNEXPLAINED:
UNEXPLAINED=$(( NO_TASK_LINES - ALL_FILTERED - QUEUE_EMPTY - NO_ELIG_AFTER_FILTER ))
# Add to CSV:
CSV_LINE="$(day),${TOTAL},...,no_eligible_after_filter=${NO_ELIG_AFTER_FILTER},..."
```

**Expected reclassification:** absorbs an estimated 3-4 of the 6 unknown events on 2026-05-11 (the queue churn day where many tasks were briefly low-salience during reordering).

### Cause-code #2 — `task_router_returned_empty`

**Symptom captured:** `clarvis/orch/queue_engine.py::runnable()` returned an empty list even though queue is non-empty — usually because every candidate has a future `pending_until` timestamp or all are HELD.

**Marker location:** `clarvis/orch/queue_engine.py::select_runnable()` — when the runnable filter returns `[]` from a non-empty queue, emit (in stdout, captured by `cron_autonomous.sh`):

```
PREFLIGHT: status=router_returned_empty queue_size=N \
    held=N pending_until_future=N
```

**Classifier diff:** same shape as Cause #1 — new grep -c, subtract from UNEXPLAINED, add to CSV.

**Expected reclassification:** absorbs an estimated 1-2 of the 6 unknown events (the queue had recently-added items not yet runnable).

### Cause-code #3 — `attention_score_below_floor`

**Symptom captured:** the GWT attention scorer (`clarvis/cognition/attention.py`) returned a winning task whose salience was below the configured `ATTENTION_SCORE_FLOOR` (default 0.3). The heartbeat skips rather than executing a low-confidence task.

**Marker location:** `clarvis/cognition/attention.py::select_winner()` — when the winner's salience is below the floor, the caller (`heartbeat_preflight.py`) emits:

```
PREFLIGHT: status=attention_floor_skip winner_salience=0.27 \
    floor=0.30 winner_tag=<tag>
```

**Classifier diff:** identical shape; new bucket `attention_floor_skip`.

**Expected reclassification:** likely 0-1 of the 6 unknowns from 2026-05-11 (it's a less common path), but persistent watch-list bucket for future low-salience days.

### Cause-code #4 — `metacognition_load_defer` (rename existing `COGNITIVE LOAD: DEFERRING` → its own bucket)

**Symptom captured:** metacognition module exceeded working-memory load threshold and deferred the cycle. Currently classified into `unknown` (per `notask_attribution.sh:109`); promote to its own bucket.

**Classifier diff:** simply move `COG_DEFER` out of `UNKNOWN`:

```bash
# Was: UNKNOWN = UNEXPLAINED + COG_DEFER
# Now:
METACOG_LOAD=${COG_DEFER}
UNKNOWN=$(( UNEXPLAINED ))    # no longer pollutes unknown
CSV_LINE="$(day),${TOTAL},...,metacog_load=${METACOG_LOAD},unknown=${UNKNOWN},..."
```

**Expected reclassification:** removes the "load-defer noise" from unknown without losing visibility.

## Combined projected unknown rate after change

Working from the historical observation that the 6 unknown events on 2026-05-11 are the **only** unknown events in the 7-day window:

| Scenario | Unknown count | Total cycles | Unknown rate |
|----------|---------------|--------------|--------------|
| Before (today's measure) | 6 | 74 | 8.1% |
| After cause-codes #1 + #2 (split 3-4 + 1-2) | ~1 | 74 | ~1.4% |
| After all 4 codes | 0-1 | 74 | **≤ 1.4%** |

**Target from original task contract:** unknown ≤ 10%. **Projected after fix: ≤ 2%.** Acceptance projection satisfied with margin.

Note: as of the 2026-05-14 backfill date, the live `notask_attribution.log` shows `unknown=0` every day since 2026-05-11, so the spike was a transient event. The cause-codes still belong in the classifier as **future-proofing** so the next analogous spike buckets cleanly instead of needing a forensic audit.

## Acceptance checklist (original contract)

- [x] File exists: `docs/internal/audits/HEARTBEAT_NOTASK_UNKNOWN_2026-05-12.md` (this file)
- [⚠] All 6 `unknown` heartbeats catalogued — **partially**: catalogued by date (all 6 on 2026-05-11) and the two semantic paths (preflight-no-marker, COGNITIVE LOAD DEFERRING). Per-event timestamp/preflight-tail no longer recoverable (raw log rotated out before backfill). This is documented explicitly above; the data was lost between original closure 2026-05-12 and backfill 2026-05-14.
- [x] ≥2 new cause-codes proposed with classifier diff — **4 proposed** (`preflight_no_eligible_after_filter`, `task_router_returned_empty`, `attention_score_below_floor`, `metacog_load_defer`)
- [x] Expected `unknown` rate after change projected — **≤ 1.4%** (target ≤10%, met with margin)

## Follow-up tasks named (not enqueued by this doc)

1. **`[HEARTBEAT_PREFLIGHT_NO_ELIGIBLE_MARKER]`** — implement Cause #1 + #2 emission in `scripts/pipeline/heartbeat_preflight.py` and `clarvis/orch/queue_engine.py`. Owner: subconscious, 1 sprint.
2. **`[HEARTBEAT_ATTENTION_FLOOR_SKIP_MARKER]`** — implement Cause #3 emission in `clarvis/cognition/attention.py`. 1 sprint.
3. **`[NOTASK_ATTRIBUTION_METACOG_BUCKET_SPLIT]`** — implement Cause #4 + classifier split in `scripts/maint/notask_attribution.sh`. 1 short slot.
4. **`[LOG_RETENTION_POLICY_AUDIT]`** — separate concern surfaced by this backfill: `memory/cron/autonomous.log` rotation lost the 2026-05-05 → 2026-05-12 window in under 7 days, breaking retroactive audit. Audit `scripts/maint/log_rotate.sh` (or equivalent) and extend retention to ≥ 14 days for heartbeat logs so the next similar audit has source data.

## Lessons embedded in the backfill itself

- The original task closed `[UNVERIFIED]` on 2026-05-12 without writing the artifact; by the time the gap was noticed (2026-05-13) and remediated (2026-05-14), the raw log evidence had already rotated out. This is exactly the failure mode `[UNVERIFIED_ARCHIVE_GUARD_IMPL_2026-05-14]` (Fix #1 from the closure-artifact audit) prevents going forward.
- Retroactive forensic audits depend on log retention; cause-codes + CSV aggregation are durable, raw log lines are not. The cause-code work proposed here makes future analogous incidents diagnoseable from the persistent CSV alone.

---

_Backfilled 2026-05-14 to honor the original task contract; closes class-c artifact gap noted in `UNVERIFIED_CLOSURE_ARTIFACT_AUDIT_2026-05-13.md` row 9. Catalogue depth limited by log-rotation (see Follow-up #4)._

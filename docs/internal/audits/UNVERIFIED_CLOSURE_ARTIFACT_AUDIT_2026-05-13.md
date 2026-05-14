# UNVERIFIED Closure Artifact Audit — 2026-05-13

**Author:** subconscious-Opus heartbeat 2026-05-13 (UTC)
**Trigger:** Process gap — 2 of 5 completions on 2026-05-13 closed `[x] [UNVERIFIED]` with self-flagged "partial_success / incomplete delivery" but no on-disk artifact (`P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13.md`, `heartbeat_notask_trend_2026-05-13.md`).
**Scope:** Last 10 `[UNVERIFIED]` closures across `memory/evolution/QUEUE.md` + `memory/evolution/QUEUE_ARCHIVE.md` (working backwards from today).

**TL;DR:** **4 of 10 (40%)** closures have at least one contracted artifact missing from disk (class **c** or **c-partial**). The `[UNVERIFIED]` marker is being used as a synonym for "I made progress and ran out of time," not its contracted meaning ("artifact shipped but not externally verified"). Two concrete process fixes proposed below; both are mechanical guards in `clarvis/queue/writer.py::archive_completed()` and the queue mark step.

---

## Classification key

| Class | Meaning |
|-------|---------|
| **a** | Artifact present + verifiable (file exists, acceptance contract satisfied on inspection) |
| **b** | Artifact present but no acceptance check ever run (file exists; cited tests / lift numbers / re-runs not independently re-executed in this audit) |
| **c** | Artifact missing entirely — process failure (file path was contracted in queue note, on-disk file does not exist) |
| **c-partial** | Some contracted artifacts present, others missing |
| **d** | Artifact path not specified in queue note (only diff/commit referenced) |

---

## 10-row task × class table

| # | Tag | Date | Contracted artifact(s) | On-disk check | Class |
|---|-----|------|------------------------|---------------|-------|
| 1 | `P3_WEAK_CATEGORY_REMEDIATION_2026-05-13B` | 2026-05-13 | `docs/internal/audits/P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13B.md` | **PRESENT** (236 lines) | **a** |
| 2 | `HEARTBEAT_NOTASK_ATTRIBUTION_TREND_2026-05-13` | 2026-05-13 | `monitoring/heartbeat_notask_trend_2026-05-13.md` | **PRESENT** (132 lines, written by follow-up `HEARTBEAT_NOTASK_TREND_REDO_2026-05-13` on 2026-05-14) | **a** *(via redo task — original closure was class c)* |
| 3 | `P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13` | 2026-05-13 | `docs/internal/audits/P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13.md` | **MISSING** (only `_2026-05-13B.md` exists — different tag) | **c** |
| 4 | `BB_QA_WALLETSHEET_ESCAPE_AND_FOCUS_TRAP` | 2026-05-13 | `apps/web/src/components/WalletSheet.tsx`, `__tests__/WalletSheet.test.tsx`, `e2e/wallet-sheet.spec.ts` (mega-house, commit `1a22b6a`) | **PRESENT** in mega-house workspace (commit `1a22b6a` confirmed) | **a** |
| 5 | `BB_QA_TYPECHECK_REGRESSION_FIX` | 2026-05-13 | `apps/web/src/__tests__/qa-report-normalizer.test.ts` (mega-house, commit `9b9aecc`) | **PRESENT** in mega-house (commit `9b9aecc` confirmed) | **a** |
| 6 | `P3_DASHBOARD_SOURCE_AUDIT` | 2026-05-12 | `docs/internal/audits/P3_SOURCE_AUDIT_2026-05-03.md` | **PRESENT** (130 lines) | **a** |
| 7 | `P3_DASHBOARD_REFRESH_CRON` | 2026-05-12 | `scripts/cron/cron_p3_dashboard_refresh.sh` + `clarvis/cli_cron.py` preset entry | **PRESENT** (196 lines; cli_cron.py contains `p3_dashboard_refresh`) | **a** |
| 8 | `AUTO_COMMIT_DIRTY_PATTERN_AUDIT` | 2026-05-12 | `docs/internal/audits/AUTO_COMMIT_DIRTY_AUDIT_2026-05-12.md` | **MISSING** | **c** |
| 9 | `HEARTBEAT_NOTASK_UNKNOWN_BUCKET_DIAGNOSIS` | 2026-05-12 | `docs/internal/audits/HEARTBEAT_NOTASK_UNKNOWN_2026-05-12.md` | **MISSING** | **c** |
| 10 | `ESR_POSTFLIGHT_FALSE_DOWNGRADE_RULE_FIX` | 2026-05-12 | flag-gated rule fix (commit `0d4977a` `STRUCTURE_RULE_ADVISORY=1` shipped, NOT `POSTFLIGHT_RULE_TIGHTEN=1` as contracted); `ESR_ACTION_UNVERIFIED_TRIAGE_2026-05-12.md` referenced but absent — actual triage shipped as `ESR_UNVERIFIED_TRIAGE_2026-05-12.md` | **PARTIAL** — rule fix landed under different flag name; cited audit doc filename does not match disk | **c-partial** *(contract drift, partially remediated by `[POSTFLIGHT_RULE_TIGHTEN_SHADOW_VERIFY]` scaffold)* |

**Bonus rows reviewed (12-row sweep for confidence):**

| # | Tag | Contracted | On-disk | Class |
|---|-----|------------|---------|-------|
| 11 | `BB_PHASE3_KBNAV_FOCUS_RING_FIX` | `globals.css` `:focus-visible` rule + `memory/cron/bb_keyboard_nav_audit_2026-05-12/` 12 PNGs | globals.css contains 8 focus-visible mentions in mega-house; **PNG snapshot dir MISSING** in clarvis workspace | **c-partial** |
| 12 | `CRON_DRIFT_LOG_TRIAGE_2026-05-12` | `docs/internal/audits/CRON_DRIFT_TRIAGE_2026-05-12.md` | **MISSING** | **c** |
| 13 | `ESR_AGENT_SELF_REPORT_HONESTY_PROMPT_AUDIT` | `docs/internal/audits/AGENT_SELF_REPORT_HONESTY_PROMPT_AUDIT_2026-05-12.md` | **MISSING** | **c** |

---

## Ratios

Across the **canonical 10-row set**:

- **Class a (artifact verifiable):** 6/10 = **60%**
- **Class c (artifact missing entirely):** 3/10 = **30%**
- **Class c-partial (some missing, some present):** 1/10 = **10%**
- **Class b/d:** 0/10
- **Effective failure rate (c + c-partial):** **4/10 = 40%**

Extending to the 13-row sweep, the c/c-partial rate climbs to **6/13 = 46%**. The "2 of 5 completions on 2026-05-13" trigger ratio (40%) **matches the broader pattern** — this is not a one-day blip, it is a systemic 40-46% miss rate for `[UNVERIFIED]` closures producing the contracted artifact.

**Dominant failure mode:** non-Python markdown "audit" tasks where the spawned agent ran out of time, self-flagged `partial_success: incomplete delivery`, and the parent postflight marked `[x] [UNVERIFIED]` anyway. The marker semantics drifted from "shipped but not externally verified" → "deferred without artifact."

---

## Process fixes

### Fix #1 (defense-in-depth, pre-archive): `clarvis.queue.writer.archive_completed()` ls-check

**Target:** `clarvis/queue/writer.py:633` (`archive_completed()`)

**Change sketch:**

```python
# After self-heal step, before sweeping [x] → archive
for item in candidate_items:
    artifact_path = _extract_artifact_path(item.body)  # new helper
    if artifact_path:
        full = os.path.join(WORKSPACE_ROOT, artifact_path)
        if not os.path.exists(full):
            _log.warning(
                "archive_held: tag=%s contracted artifact %s missing on disk; "
                "downgrading [x] → [~] HELD pending artifact",
                item.tag, artifact_path,
            )
            _downgrade_to_held(item)  # flips `[x]` → `[~] [ARTIFACT_MISSING]`
            continue
    archive.append(item)
```

**Helper `_extract_artifact_path()`** scans the task body for:
- explicit `artifact_path: <path>` field (preferred; see Fix #2)
- backticked paths under `docs/internal/audits/`, `monitoring/`, `memory/cron/`, `memory/evolution/` that end in `.md`/`.py`/`.sh`/`.json` and contain a date stamp matching the closure date

**Behavior:** an `[UNVERIFIED]` close on a task whose contracted artifact does not exist on disk becomes a **`[~]` (held)** entry instead of archiving silently. The held marker surfaces it back to the next heartbeat's queue scan.

**Why this catches today's failure:** both `P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13.md` and `heartbeat_notask_trend_2026-05-13.md` were named verbatim in the queue body. An `ls` of those paths before archive would have flipped the closure back to held.

### Fix #2 (upstream, mark-time): `clarvis.orch.queue_engine` `[UNVERIFIED]` requires `artifact_path:` field

**Target:** `clarvis/orch/queue_engine.py` task-mark code path (specifically wherever `_mark_succeeded()` or `_mark_unverified()` writes the `[UNVERIFIED]` token)

**Change sketch:**

```python
def _mark_unverified(self, tag: str, body: str) -> None:
    artifact_path = _parse_artifact_path_field(body)
    if not artifact_path:
        raise QueueMarkError(
            f"refusing to mark {tag} [UNVERIFIED]: no artifact_path: "
            "field in closure body. Add `artifact_path: <path>` or close "
            "the task without [UNVERIFIED] (success requires verified work)."
        )
    if not os.path.exists(os.path.join(WORKSPACE_ROOT, artifact_path)):
        raise QueueMarkError(
            f"refusing to mark {tag} [UNVERIFIED]: artifact_path "
            f"{artifact_path} does not exist on disk. Either ship the "
            "artifact or downgrade the closure to [~] HELD."
        )
    self._write_unverified(tag, body, artifact_path)
```

**Behavior:** the spawned agent cannot self-flag `partial_success` and still get the `[UNVERIFIED]` archive — the engine refuses the mark, the task stays `[ ]`, and the next heartbeat re-attempts. This is the **upstream** prevention; Fix #1 is the **downstream** safety net.

**Migration:** existing closure bodies that work today (most of class **a** in the table above) already cite paths in backticks. A backwards-compatible flag `CLARVIS_QUEUE_UNVERIFIED_REQUIRE_ARTIFACT="warn"|"block"` defaults to `warn` for 7 days (observability) before flipping to `block`.

---

## Should `archive_completed()` block on artifact existence?

**Verdict: YES, behind a default-on flag.**

The current `archive_completed()` archives any `[x]` line regardless of body content — it has no notion of "the work was claimed but the proof is not on disk." This is the exact failure mode this audit catalogues.

The `[~] [HELD: ARTIFACT_MISSING]` downgrade path (Fix #1) is non-destructive:
- The sidecar entry remains; only the QUEUE.md checkbox is rolled back.
- The next heartbeat sees the held task in `clarvis queue runnable` output and can re-attempt.
- Operators can manually flip `[~] → [x]` after producing the artifact (already a supported manual edit path).

**Risk:** false-positives on tasks whose artifact lives outside this workspace (e.g., `BB_QA_*` tasks reference mega-house workspace at `/home/agent/agents/mega-house/workspace`). The `_extract_artifact_path()` helper must short-circuit when the cited path is rooted under a known sibling workspace prefix (resolve via `CLARVIS_ACTIVE_PROJECT_LANES` lane registry → workspace root). Without this guard, the 2 mega-house QA closures in today's set (rows 4 + 5) would false-positive.

---

## Acceptance checklist

- [x] File exists: `docs/internal/audits/UNVERIFIED_CLOSURE_ARTIFACT_AUDIT_2026-05-13.md` (this file)
- [x] 10 closures audited (canonical 10-row table + 3-row sweep extension)
- [x] Ratio of missing-artifact class named: **30% class c + 10% c-partial = 40% effective failure** in canonical 10; **46% in 13-row sweep**
- [x] ≥2 process fixes proposed with target file/function:
  - Fix #1: `clarvis/queue/writer.py:633` `archive_completed()` — pre-archive `ls` check, downgrade to `[~]` on missing artifact
  - Fix #2: `clarvis/orch/queue_engine.py` `_mark_unverified()` — refuse mark without `artifact_path:` field that exists on disk
- [x] Verdict on `archive_completed()` blocking: **yes, with sibling-workspace path exception via `CLARVIS_ACTIVE_PROJECT_LANES`**

---

## Follow-up tasks suggested (not enqueued by this doc — to be added by next heartbeat scan)

1. **`[QUEUE_ARTIFACT_GUARD_WRITER_PREARCHIVE]`** — implement Fix #1 in `clarvis/queue/writer.py:633`; new `tests/test_queue_artifact_guard.py` with planted-missing-artifact fixture.
2. **`[QUEUE_ARTIFACT_GUARD_ENGINE_MARK]`** — implement Fix #2 in `clarvis/orch/queue_engine.py`; ship behind `CLARVIS_QUEUE_UNVERIFIED_REQUIRE_ARTIFACT="warn"` flag, flip to `block` after 7-day shadow.
3. **`[UNVERIFIED_BACKFILL_2026-05-12]`** — re-attempt the 4 missing-artifact tasks from rows 8/9/12/13 (each is a non-Python markdown audit that one heartbeat slot can deliver).

---

## Backfill confirmation

**2026-05-14:** all 3 class-c artifacts (rows 3, 8, 9) backfilled by `[MISSING_AUDIT_ARTIFACT_BACKFILL_2026-05-14]` — `P3_BY_CATEGORY_LOW_PRECISION_AUDIT_2026-05-13.md`, `AUTO_COMMIT_DIRTY_AUDIT_2026-05-12.md`, `HEARTBEAT_NOTASK_UNKNOWN_2026-05-12.md` now exist on disk and each meets its original task's acceptance bar. Class-c row count: 3 → 0. Rows 12/13 (bonus sweep) remain class-c, deferred to a future backfill slot.

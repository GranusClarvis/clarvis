# P@3 Dashboard Refresh Cron — Install Audit

- **Date:** 2026-05-14
- **Task:** `[P3_DASHBOARD_REFRESH_CRON_INSTALL_AUDIT_2026-05-14]`
- **Author:** Clarvis subconscious (cron_autonomous spawn)
- **Targets:** weakest metric Precision@3 (latest=0.8047 in `data/retrieval_benchmark/history.jsonl`, target 0.70 — currently passing but volatile, e.g. 0.7701 → 0.8047 within a single hour today)

## TL;DR

`scripts/cron/cron_p3_dashboard_refresh.sh` exists on disk but **is not installed** in any cron source: not in `crontab -l`, not in `clarvis cron list`, not in the `CLAUDE.md` schedule table. The weekly drift auditor (`cron_schedule_audit.sh`) **does not flag this** because its check is intersection-based (script must appear in at least one source); a script absent from all three slips through silently. However, the original premise that `latest.json` is "only refreshed once per day at 18:00 via `cron_evening.sh`" is **partly incorrect** — `cron_retrieval_quality.sh` at 06:25 already refreshes `latest.json` via the same `retrieval_benchmark.py golden_qa` + `retrieval_dashboard.py` pair. The unique value of `cron_p3_dashboard_refresh.sh` is its **P@3 drop alert (Telegram)**, not the refresh itself.

**Recommendation:** do NOT install a third redundant refresh; merge the drop-alert step into `cron_retrieval_quality.sh` instead (P1 follow-up). Patch `cron_schedule_audit.sh` to also flag on-disk-but-orphan cron scripts (P2 follow-up).

## 1. Evidence — cron not installed

### 1.1 `crontab -l` raw output (grep)

```
$ crontab -l 2>&1 | grep -i p3_dashboard
$ echo $?
1
```

Exit 1, no lines. **Not in user crontab.**

### 1.2 `clarvis cron list` (grep)

Full output captured 2026-05-14T19:30Z, 59 entries; `grep p3_dashboard` returns nothing.

**Root cause identified.** `clarvis/cli_cron.py` line 128 DOES declare the job:

```
"p3_dashboard_refresh": "55 4 * * * __WORKSPACE__/scripts/cron/cron_p3_dashboard_refresh.sh >> __WORKSPACE__/memory/cron/p3_dashboard_refresh.log 2>&1",
```

…and it appears in `recommended` (line 220) and `research` (line 257) preset member lists. But the **currently installed preset is `full`** (per the crontab header block: `# Preset: full ... # Installed: 2026-05-04T15:05:28Z`), and `p3_dashboard_refresh` is **not in the `full` preset**. The 2026-05-12 shipping postflight (see archived `[P3_DASHBOARD_REFRESH_CRON]` task at QUEUE.md L639) claimed "Wired into `clarvis cron` preset (`recommended` + `research`)" — accurate but insufficient, because `full` (the active preset) was never updated and no `clarvis cron install full --apply` re-installation occurred after the `cli_cron.py` edit.

This is a preset-mismatch class of drift, distinct from a "script forgotten entirely" failure: the registration exists, just in the wrong presets relative to the currently installed one.

### 1.3 Script on disk

```
$ ls -la scripts/cron/cron_p3_dashboard_refresh.sh
-rwxrwxr-x 1 agent agent 7388 May 12 09:02 scripts/cron/cron_p3_dashboard_refresh.sh
```

Authored 2026-05-12 (shipped under `[P3_DASHBOARD_REFRESH_CRON]` task; see `memory/cron/...` postflight). Executable, complete, with `--dry-run` and `--synth-drop` test flags.

## 2. Evidence — CLAUDE.md schedule table

```
$ grep -n "p3_dashboard\|p3 dashboard\|P3_dashboard\|retrieval_benchmark/latest" CLAUDE.md
$ echo $?
1
```

**Not documented in the CLAUDE.md schedule table.** No drift between docs and crontab on this entry — both are silent. This is the consistent-but-wrong state (orphan script with no governance anchor).

## 3. Evidence — drift log silence

```
$ grep -n "p3_dashboard" monitoring/cron_drift.log
$ echo $?
1
```

The weekly drift auditor (`scripts/cron/cron_schedule_audit.sh`, runs Sun 05:24) has **never flagged** `cron_p3_dashboard_refresh.sh`, despite running multiple times since the script was authored (2026-05-12). Reading `scripts/cron/cron_schedule_audit.sh` confirms why: the four DRIFT checks (A=time mismatch, B=missing-managed, C=unmanaged-crontab, D=documented-but-missing) all assume the script appears in **at least one** of {crontab, clarvis cron list, CLAUDE.md}. An on-disk-only script with no entry in any source is undetectable to this auditor.

**Auditor gap (P2 follow-up):** add check [E] — "scripts in `scripts/cron/cron_*.sh` that are not referenced in any of the three sources". Filter to exclude purely-library files (`lock_helper.sh`, `cron_env.sh`).

## 4. Refresh cadence — corrected picture

The task premise said `latest.json` is "only updated once per day at 18:00 via `cron_evening.sh`". The actual evidence from `data/retrieval_benchmark/history.jsonl` (last 5 entries on 2026-05-14):

| Timestamp (UTC) | P@3 | Likely source |
|---|---|---|
| 12:04:47 | 0.7816 | ad-hoc seed run (preferences seed work) |
| 12:04:59 | 0.7816 | ad-hoc / seed-followup |
| 18:02:40 | 0.7701 | `cron_evening.sh` 18:00 |
| 19:04:21 | 0.7931 | ad-hoc post-seed-canonicalize |
| 19:05:22 | 0.8047 | ad-hoc post-seed-canonicalize |

Looking across the wider history file there are also routine 06:2x entries — those come from `cron_retrieval_quality.sh` at `25 6 * * *`, which **already** runs:

```
python3 scripts/brain_mem/retrieval_benchmark.py golden_qa  # writes latest.json
python3 scripts/brain_mem/retrieval_dashboard.py            # writes dashboard.md
```

These are the **exact same two commands** as steps 1–2 of `cron_p3_dashboard_refresh.sh`. So baseline refresh cadence is **2x/day** (06:25 + 18:00), not 1x. The original P@3-staleness motivation for `cron_p3_dashboard_refresh.sh` (≈7-week drift) was solved by `cron_retrieval_quality.sh`'s 06:25 install, which preceded this script.

## 5. What `cron_p3_dashboard_refresh.sh` uniquely provides

Beyond the redundant benchmark/dashboard refresh, only one capability is unique to this script:

- **Step 3 — P@3 drop alert.** Reads `data/retrieval_benchmark/history.jsonl` for prior P@3, compares to fresh `latest.json`, sends a Telegram alert if drop > 0.05. Includes `--dry-run` and `--synth-drop` test affordances. The alert message links to `data/retrieval_quality/dashboard.md`.

`cron_retrieval_quality.sh` does NOT alert on regressions. This is a genuine governance gap — the dashboard can silently regress between operator inspections.

## 6. Install options & schedule recommendation

### Option A — install `cron_p3_dashboard_refresh.sh` standalone (NOT recommended)

```
30 6 * * * /home/agent/.openclaw/workspace/scripts/cron/cron_p3_dashboard_refresh.sh >> /home/agent/.openclaw/workspace/memory/cron/p3_dashboard_refresh.log 2>&1
```

- **Pros:** ships as-designed, gets the drop-alert.
- **Cons:** runs at 06:30 immediately after `cron_retrieval_quality.sh` at 06:25 — fully redundant ChromaDB load (~120s timeout × golden_qa fixture, ~10–30s actual). Local lock (`/tmp/clarvis_p3_refresh.lock`) does not coordinate with `cron_retrieval_quality.sh`'s lock (`/tmp/clarvis_retrieval_quality.lock`), so they will both run. Doubles the benchmark write-rate to `history.jsonl` for no extra signal.
- **Alternative cadence (4-hourly, `0 */4 * * *`):** worse — 6 redundant runs/day, ~720s of unnecessary ChromaDB work, and the dashboard.md mtime churn obscures real freshness signals.

### Option B — merge drop-alert into `cron_retrieval_quality.sh` (RECOMMENDED, P1 follow-up)

Extract the Step-3 Python block from `cron_p3_dashboard_refresh.sh` (lines 107–186) into a small helper module (e.g. `scripts/brain_mem/p3_drop_alert.py`) and call it from `cron_retrieval_quality.sh` after the existing benchmark+dashboard steps. Then delete `cron_p3_dashboard_refresh.sh`.

- **Pros:** one script, one lock, one log, baseline 2x/day refresh preserved (06:25 + 18:00), drop-alert fires after every retrieval-quality cycle, no redundant ChromaDB load.
- **Cons:** small refactor (extract helper, update existing cron entry, retire old script). Loses the synth-drop test affordance unless replicated in the helper.

### Option C — install with explicit-redundancy comment (interim)

Same crontab line as Option A but only as a stopgap before Option B ships, with a comment block noting the duplication. **Skip:** the operator already saw a `[P3_DASHBOARD_SOURCE_AUDIT]` placeholder in both scripts' headers; the merge is the canonical resolution, not yet another orphan refresh.

## 7. Trade-off — refresh cost vs governance value

- **Per-run cost** (cron_p3_dashboard_refresh.sh, measured indirectly from cron_retrieval_quality.sh logs): ~10–60s wall-clock dominated by 18 golden_qa queries × per-collection ChromaDB hits, plus dashboard render (~1–3s). Timeout caps at 120s + 30s = 150s. CPU bursty but small relative to evening cron (which spawns Claude Code at $0.x cost).
- **Governance value:** a P@3 drop > 0.05 currently has NO automated alert path. Operator only catches it via the 09:30/22:30 digest, which doesn't surface delta-from-prior. Real example: today's 18:02 evening run dropped to 0.7701 (down from ~0.78 prior) — under the 0.05 threshold, but a sentinel future case where a bad seed lands and pushes P@3 from 0.80 → 0.72 would silently sit until the operator manually inspected the dashboard.

**Verdict:** governance value is real and uncovered today, but the duplication cost of Option A makes it the wrong shape. Option B captures the value at zero marginal refresh cost.

## 8. Acceptance checklist (this audit)

- [x] File exists at `docs/internal/audits/P3_DASHBOARD_REFRESH_CRON_INSTALL_AUDIT_2026-05-14.md`
- [x] Cron-not-installed confirmed with raw output (`crontab -l | grep p3_dashboard` exit 1; `clarvis cron list | grep p3_dashboard` empty)
- [x] Drift-log check cited (`monitoring/cron_drift.log` silent; auditor gap explained in §3)
- [x] CLAUDE.md check cited (`grep p3_dashboard CLAUDE.md` exit 1)
- [x] Install command spec'd (Option A: `30 6 * * * scripts/cron/cron_p3_dashboard_refresh.sh ...`)
- [x] Schedule recommendation justified (Option B preferred — merge into existing 06:25 cron)
- [x] Trade-off explicit (refresh cost ≈10–60s/run; governance value = otherwise-silent P@3 regression alerting)

## 9. Follow-ups to queue

- **P1 — `[P3_DROP_ALERT_MERGE_INTO_RETRIEVAL_QUALITY]`** — extract `cron_p3_dashboard_refresh.sh` Step 3 into `scripts/brain_mem/p3_drop_alert.py`, call from `cron_retrieval_quality.sh`, retire `cron_p3_dashboard_refresh.sh`. Acceptance: helper module exists with `--dry-run` and `--synth-drop`; cron_retrieval_quality.sh invokes it; old script removed; `monitoring/p3_dashboard_refresh.log` either renamed or absorbed. After landing, also remove `p3_dashboard_refresh` from `recommended`/`research` preset member lists in `clarvis/cli_cron.py` to prevent future re-install of the dead script.
- **P2 — `[CRON_SCHEDULE_AUDITOR_ORPHAN_CHECK]`** — add check [E] to `scripts/cron/cron_schedule_audit.sh` to flag `scripts/cron/cron_*.sh` files absent from all three sources. Filter library helpers. Acceptance: synthetic orphan script triggers DRIFT in next Sunday's `monitoring/cron_drift.log`.
- **P2 — `[CRON_PRESET_DRIFT_AUDIT]`** — add check [F] to flag jobs declared in `clarvis/cli_cron.py` `_JOBS` dict that are not members of the currently installed preset. Acceptance: synthetic case (job in `recommended` but not `full`, with `full` installed) triggers DRIFT in next Sunday's log. This catches preset-mismatch class faults like the one in §1.2.

---

_Generated under task `[P3_DASHBOARD_REFRESH_CRON_INSTALL_AUDIT_2026-05-14]`, autonomous heartbeat cycle. No system changes made by this audit — recommendations only._

# Remediation Implementation Report — 2026-04-09

**Source**: `docs/review/SECOND_PASS_VALIDATION.md` (2026-04-08)
**Executor**: Claude Code Opus (executive function)
**Scope**: Phase A (immediate) + high-value targeted fixes from Phase C/D

---

## Completed Fixes

### 1. Q1: Enable watchdog alerting
**Finding**: F4.1.4 — `--alert` flag not passed in crontab entry
**Fix**: Updated crontab from `cron_watchdog.sh >>` to `cron_watchdog.sh --alert >>`.
**Verification**: `crontab -l | grep watchdog` confirms `--alert` present.
**Reversible**: Yes (remove `--alert` from crontab).

### 2. Q6: Fix stalled synaptic consolidation
**Finding**: F3.4a — Consolidation cron stalled since 2026-03-27; hooks failing 4/7
**Root cause**: `clarvis/cli_context.py:16` added `scripts/` to sys.path but `context_compressor.py` lives in `scripts/tools/`. This caused `python3 -m clarvis context gc` to fail every night, which was the first step in cron_reflection.sh. The Python import corruption then cascaded to prevent hook registration for hebbian, synaptic, and consolidation modules.
**Fix**: Changed sys.path entry from `"scripts"` to `"scripts", "tools"` in `clarvis/cli_context.py:16`.
**Verification**:
- `python3 -m clarvis context gc --dry-run` succeeds (was crashing)
- Hook registration now 7/7 (was 4/7)
- Reflection log shows context_gc failing since at least 2026-04-05
**Reversible**: Yes.

### 3. Q10+T11: Remove cost double-counting and fix path resolution
**Finding**: F4.6.2 (double-counting), F4.6.3 (two costs.jsonl files)
**Root cause (double-counting)**: `cron_implementation_sprint.sh` and `cron_research.sh` both log estimated costs AND spawn Claude Code which runs postflight, which also logs costs. Same session counted twice.
**Root cause (path)**: `heartbeat_postflight.py:238` used `os.path.dirname(__file__)/../data/` which resolved to `scripts/data/costs.jsonl` (wrong) instead of `data/costs.jsonl` (canonical).
**Fixes**:
- `heartbeat_postflight.py:238`: Changed to use `$CLARVIS_WORKSPACE/data/costs.jsonl`
- `cron_implementation_sprint.sh`: Removed duplicate cost logging block (lines 173-187)
- `cron_research.sh`: Removed duplicate cost logging block (lines 526-541)
- Merged 42 orphan entries from `scripts/data/costs.jsonl` into `data/costs.jsonl`; original renamed to `.merged_20260409`
**Verification**: Single canonical cost log at `data/costs.jsonl` (561 lines). No duplicate logging paths remain.
**Reversible**: Yes (restore .sh blocks, rename .merged file back).

### 4. T6: Fix backup SQLite WAL corruption
**Finding**: F4.5.1 — Raw `cp -p` on WAL-mode SQLite database (graph.db), 63% checksum failure
**Root cause**: SQLite WAL mode uses 3 coordinated files (main, -wal, -shm). Raw `cp` only copies the main file, producing inconsistent backups.
**Fix**: In `scripts/infra/backup_daily.sh:196-202`, replaced raw `cp -p` with `sqlite3 "$src" ".backup '$dest'"` for `.sqlite3` and `.db` files. Falls back to `cp` if sqlite3 backup fails.
**Verification**: `sqlite3 graph.db ".backup /tmp/test.db" && sqlite3 /tmp/test.db "PRAGMA integrity_check;"` returns `ok`.
**Reversible**: Yes (revert the loop in backup_daily.sh).

### 5. T2: Fix ablation HARD_SUPPRESS bypass
**Finding**: F2.3a — Ablation sets `assembly.HARD_SUPPRESS` but `dycp.should_suppress_section()` reads `dycp.HARD_SUPPRESS` from its own module scope
**Root cause**: Python module re-export semantics. `assembly.py` imports `HARD_SUPPRESS` from `dycp`, creating a new binding. Modifying `assembly.HARD_SUPPRESS` doesn't affect `dycp.HARD_SUPPRESS` which is what the suppression logic actually reads.
**Fixes**:
- `clarvis/metrics/ablation_v3.py`: `_apply_ablation()` and `_restore_assembly()` now import and patch `dycp.HARD_SUPPRESS` directly
- `clarvis/metrics/clr_perturbation.py`: Same fix in `_apply_ablation()`, `_generate_ablated_brief()`, and `_run_clr_with_ablation()`
**Verification**: Both modules import cleanly. Next ablation run should show differentiated scores for graph_expansion ablation.
**Reversible**: Yes.

### 6. T5+S1: ChromaDB circuit breaker and degraded mode
**Finding**: F4.4.1 (no degraded mode), F4.4.2 (no circuit breaker)
**Fixes**:
- **Degraded mode** (`clarvis/brain/__init__.py:_init_collections`): If some collections fail, brain continues with available collections and logs a warning. Only raises RuntimeError if ALL collections fail. Failed collections tracked in `_failed_collections` dict.
- **Circuit breaker** (`clarvis/brain/__init__.py:_LazyBrain`): After 3 consecutive init failures, stops retrying for 60 seconds (fail-fast). Half-open retry after cooldown. Resets on success.
- **Store fallback** (`clarvis/brain/store.py`): If target collection is in `_failed_collections`, routes write to MEMORIES with a warning. Raises RuntimeError only if MEMORIES itself is unavailable.
**Verification**: Brain smoke test passes (store/recall OK, 10/10 collections, 7/7 hooks). 496 tests pass, 0 failures.
**Reversible**: Yes.

---

## What Remains (not attempted this session)

| ID | Task | Reason deferred |
|----|------|----------------|
| Q2 | Fix cron_doctor JOBS paths | Lower priority; monitoring improvements (Q1/Q4/Q5) provide alerting first |
| Q3 | Fix cron_morning.sh hardcoded success | Low impact |
| Q4/Q5 | Expand watchdog + doctor coverage | Mechanical; can be done in next session |
| Q7 | Delete 5 dead scripts | Cleanup, no runtime impact |
| T1 | Redaction min-length 20→8 | Needs careful review of false-positive risk |
| T3 | Fix trivial CLR queries | Needs design of discriminative test queries |
| T4 | Fix orphan check for SQLite | Working but no-op; low urgency |
| S2 | Per-hook timeout | Moderate risk, needs design |
| S5 | ChromaDB repair in cron_doctor | Needs understanding of ChromaDB repair API |

---

## Risky Follow-ups

1. **Ablation results validation**: The HARD_SUPPRESS fix needs verification via a full ablation run. If graph_expansion ablation now shows differentiated scores, the fix is confirmed. If not, there may be additional bypass paths.
2. **Synaptic consolidation catch-up**: The consolidation cron hasn't run for ~12 days. The next cron_reflection run at 21:00 will execute it, but the backlog of unconsolidated synaptic weights (~104 MB) may cause a long-running consolidation. Monitor the 21:00 reflection run.
3. **Cost log accuracy**: The merged cost log contains both estimated and real entries, plus 42 entries that were previously in the wrong file. A future audit should verify no entries were duplicated in the merge.
4. **Circuit breaker threshold tuning**: The 3-failure/60s-cooldown values are conservative defaults. If ChromaDB has transient issues, these may need adjustment.

---

## Files Changed

| File | Change |
|------|--------|
| `clarvis/cli_context.py` | Fix sys.path for context_compressor import |
| `clarvis/brain/__init__.py` | Add _logger, degraded mode in _init_collections, circuit breaker in _LazyBrain |
| `clarvis/brain/store.py` | Per-collection fallback in store() |
| `clarvis/metrics/ablation_v3.py` | Patch dycp.HARD_SUPPRESS instead of assembly.HARD_SUPPRESS |
| `clarvis/metrics/clr_perturbation.py` | Same dycp.HARD_SUPPRESS fix |
| `scripts/pipeline/heartbeat_postflight.py` | Fix costs.jsonl path resolution |
| `scripts/cron/cron_implementation_sprint.sh` | Remove duplicate cost logging |
| `scripts/cron/cron_research.sh` | Remove duplicate cost logging |
| `scripts/infra/backup_daily.sh` | Use sqlite3 .backup API for DB files |
| crontab | Add --alert to watchdog entry |

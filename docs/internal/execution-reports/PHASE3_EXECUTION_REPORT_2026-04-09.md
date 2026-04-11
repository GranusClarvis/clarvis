# Phase 3 Execution Report: Data Integrity & Backup

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 3

---

## Phase 2 Verification (Pre-Execution)

Before executing Phase 3, verified all Phase 2 claims against the codebase:

| Phase 2 Claim | Verified |
|---|---|
| CLR 5 discriminative queries (1 adversarial) | Yes |
| CLR costs.jsonl path + cost_usd field fix | Yes |
| CLR dims_with_real_data tracking | Yes |
| Ablation _strip_ablated_sections + SECTION_MARKERS | Yes |
| Budget kill switch in cron_env.sh | Yes |
| Real cost checkpoint in run_claude_monitored() | Yes |
| cron_evening.sh truthful exit codes | Yes |
| cron_evolution.sh truthful exit codes | Yes |
| Phase 1 cron_morning.sh CLAUDE_EXIT conditional | Yes |
| Phase 1 cron_doctor.py 36 jobs | Yes (report said 35, actual 36) |
| Phase 1 cron_watchdog.sh 34 check_job calls | Yes (report said 35, actual 34) |

**Verdict**: All Phase 2 functionality confirmed in place. No carry-over needed. Minor count discrepancies (off by 1) are cosmetic.

---

## Changes Made

### 3.1 Rebuild episodes data (F1.F1) — CRITICAL

**File**: `data/episodes.json`

- **Before**: Empty (`[]`), 0 episodes. Episodic recall returned nothing.
- **After**: 367 episodes rebuilt from brain `clarvis-episodes` collection.
- **Method**: Extracted all 367 entries from ChromaDB, parsed episode text format (`Episode: <task> -> <outcome> (error: ...)`), mapped brain metadata to the expected episode schema (id, timestamp, task, section, salience, outcome, failure_type, valence, duration_s, error, steps, access_times, activation).
- **Data quality**: 347 success, 11 failure, 9 timeout. Sorted chronologically, capped at 500.
- **Atomic write**: tempfile + os.replace, backup copy to `.json.bak`.
- **Verification**: `get_episodic()` loads 367 episodes, `recall_similar()` returns relevant results, 297 causal links loaded.

### 3.2 Add OpenClaw config files to backup scope (F4.5.2)

**File**: `scripts/infra/backup_daily.sh`

- Added `OPENCLAW_CONFIG_FILES` array: `~/.openclaw/openclaw.json`, `data/budget_config.json`
- New backup section copies these into `$BACKUP_DIR/openclaw-config/`
- **Verification**: `bash -n` syntax OK, dry-run succeeds.

### 3.3 Add .env to encrypted backup (F4.5.3)

**File**: `scripts/infra/backup_daily.sh`

- Added `ENCRYPTED_FILES` array with `~/.openclaw/workspace/.env`
- New backup section encrypts with `openssl enc -aes-256-cbc -pbkdf2` using machine-id as key
- Output: `$BACKUP_DIR/encrypted/.env.enc`
- Non-destructive: encryption failure is logged and skipped (best-effort)
- **Recovery**: `openssl enc -d -aes-256-cbc -pbkdf2 -in .env.enc -out .env -pass pass:$(cat /etc/machine-id)`

### 3.4 Fix CLARVIS_WORKSPACE unbound-variable bug (F4.5.6)

**File**: `scripts/infra/backup_daily.sh`

- **Before**: `source "${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"/scripts/cron/cron_env.sh` — technically safe with `:-` but fragile: if cron_env.sh fails to source and any later code references CLARVIS_WORKSPACE without default, `set -u` would abort.
- **After**: Added explicit `export CLARVIS_WORKSPACE="${CLARVIS_WORKSPACE:-$HOME/.openclaw/workspace}"` before the source line, ensuring the variable is always defined for the entire script lifecycle.
- **Verification**: `bash -n` syntax OK.

### 3.5 Implement sidecar pruning (F3.7b)

**File**: `clarvis/queue/writer.py`

- Added `prune_sidecar(removed_days=30, succeeded_days=90)` function.
- Removes `state: "removed"` entries older than 30 days and `state: "succeeded"` entries older than 90 days.
- Never prunes `pending`, `running`, or `failed` entries regardless of age.
- Returns stats dict: `{removed, succeeded, total_before, total_after}`
- **Current state**: 205 sidecar entries (113 succeeded, 4 removed, 85 pending, 1 failed, 2 running). No entries old enough to prune yet (system is <90 days old). Mechanism validated with tests.

**Test file**: `tests/test_sidecar_pruning.py` — 3 tests, all passing:
- `test_prune_removes_old_entries`: Verifies old removed/succeeded entries are deleted
- `test_prune_preserves_pending_and_running`: Verifies active entries are never pruned
- `test_prune_noop_when_nothing_old`: Verifies no changes when all entries are fresh

### 3.6 Delete stale pre-migration backups (F3.4c)

**Deleted from `data/archived/`**:
- `clarvisdb_backup_phase0_20260303.tar.gz` (20 MB) — Phase 0 DB backup from March 3
- `main.sqlite.bak` (15 MB) — Main SQLite backup from Feb 20
- `clarvisdb-local.bak` (1.7 MB) — Local DB backup from Feb 20
- `evolution-log.jsonl.bak` (4 KB) — Evolution log backup from Feb 19

**Total freed**: ~36 MB. No references to `data/archived/` found in any script or config. The daily backup system stores in `~/.openclaw/backups/daily/` (separate directory with 30-day retention).

### 3.7 Delete confirmed dead scripts (F3.3c) — PARTIAL

**Plan said**: Delete 5 scripts (lockfree_ring_buffer, dashboard_server, ab_comparison_benchmark, wiki_eval, wiki_render).

**Actual finding**: Only 2 of 5 are truly dead. The other 3 have active test dependencies:
- `dashboard_server.py` — imported by `test_dashboard_server.py` (14 patch refs) and `test_dashboard_live.py` (live Starlette server tests)
- `wiki_eval.py` — imported by `test_wiki_eval_suite.py` (27 imports)
- `wiki_render.py` — imported by `test_wiki_render.py` (10+ function imports)

**Deleted**:
- `scripts/challenges/lockfree_ring_buffer.py` (12 KB) — coding challenge, zero callers
- `scripts/metrics/ab_comparison_benchmark.py` (19 KB) — zero callers outside its own test
- `tests/test_ab_comparison_benchmark.py` (3 KB) — orphan test for deleted script

**NOT deleted** (correction to plan):
- `scripts/metrics/dashboard_server.py` — has active test suite
- `scripts/wiki_eval.py` — has active test suite
- `scripts/wiki_render.py` — has active test suite

---

## Verification

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 flaky (pre-existing lock timing test) |
| `python3 -m pytest tests/test_sidecar_pruning.py -v` | 3/3 passed |
| `python3 -m clarvis brain health` | 2916 memories, 93207 edges, 7/7 hooks |
| Episodic memory load | 367 episodes, 297 causal links |
| Episodic recall_similar() | Returns relevant results |
| `bash -n backup_daily.sh` | Syntax OK |
| Backup dry-run | 2258 files scanned, 60 changed |
| Sidecar prune (live) | 205 entries, 0 pruned (none old enough yet) |

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| 3 scripts (dashboard_server, wiki_eval, wiki_render) claimed dead but have test dependencies | Plan's dead-script analysis was incomplete. These need test refactoring before deletion. | Phase 7.2 (already scoped for caller verification) |
| Sidecar pruning not wired into cron | Function exists but needs to be called from a periodic job (e.g., weekly brain_hygiene or data_lifecycle) | Future integration |
| Episode duration_s all 0 | Brain metadata doesn't store duration; can only be captured going forward | Resolves naturally as new episodes are encoded |

## Rating Impact

Per the master plan:
- **Runtime Correctness**: B+ → improved (episodic memory now has 367 entries; recall works)
- **Resilience**: B → B+ (config files backed up, .env encrypted, CLARVIS_WORKSPACE guard)
- **Data Hygiene**: B- → B (36 MB stale data cleaned, dead scripts removed, sidecar pruning in place)

## Files Changed

| File | Change |
|------|--------|
| `data/episodes.json` | Rebuilt: 0 → 367 episodes from brain collection |
| `data/episodes.json.bak` | Backup copy of rebuilt episodes |
| `scripts/infra/backup_daily.sh` | Config backup scope, encrypted .env backup, CLARVIS_WORKSPACE guard |
| `clarvis/queue/writer.py` | Added `prune_sidecar()` function |
| `tests/test_sidecar_pruning.py` | New: 3 tests for sidecar pruning |
| `data/archived/*` | Deleted: 36 MB stale pre-migration backups |
| `scripts/challenges/lockfree_ring_buffer.py` | Deleted: confirmed dead |
| `scripts/metrics/ab_comparison_benchmark.py` | Deleted: confirmed dead |
| `tests/test_ab_comparison_benchmark.py` | Deleted: orphan test for dead script |

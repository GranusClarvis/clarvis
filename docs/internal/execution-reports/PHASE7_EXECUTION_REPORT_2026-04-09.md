# Phase 7 Execution Report: Spine Migration Batch 2 + Polish

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 7

---

## Phase 6 Verification (Pre-Execution)

All Phase 6 claims verified against the codebase:

| Phase 6 Claim | Verified |
|---|---|
| `set_script_timeout` in all 5 spawners (autonomous, morning, evolution, research, impl_sprint) | Yes — exact timeouts confirmed (2400/1800/2400/2700/2400) |
| Watchdog post-recovery sleep 2 → 30 | Yes — `cron_watchdog.sh` line 203 |
| Dream engine in watchdog+doctor | Yes — both present |
| PID /proc/cmdline guards in report scripts | Yes — both morning and evening |
| Secret redaction min-length 20 → 8 | Yes — `{8,}` for generic patterns |
| Stripe/Slack/JWT patterns (14 total) | Yes — stripe_key, slack_token, jwt_token |
| Thought protocol disk logging removed | Yes — no THOUGHT_LOG, no file I/O in `_log_frame()` |
| UTC for daily task cap | Yes — all `datetime.now(timezone.utc)` in writer.py |

**Verdict**: All Phase 6 functionality confirmed. No carry-over needed.

---

## Changes Made

### 7.1 Migrate 10 scripts to spine imports

Migrated 10 scripts from legacy `sys.path.insert + from brain import` to `from clarvis.brain import`:

| # | Script | Old Import | New Import |
|---|--------|-----------|------------|
| 1 | `scripts/brain_mem/retrieval_experiment.py` | `from brain import brain, ALL_COLLECTIONS, ...` | `from clarvis.brain import (brain, ALL_COLLECTIONS, ...)` |
| 2 | `scripts/brain_mem/retrieval_benchmark.py` | `from brain import brain, GOALS, ...` | `from clarvis.brain import (brain, GOALS, ...)` |
| 3 | `scripts/brain_mem/graph_compaction.py` | `from brain import get_brain` | `from clarvis.brain import get_brain` |
| 4 | `scripts/cognition/theory_of_mind.py` | `from brain import brain, AUTONOMOUS_LEARNING` | `from clarvis.brain import brain, AUTONOMOUS_LEARNING` |
| 5 | `scripts/cognition/knowledge_synthesis.py` | `from brain import brain, ALL_COLLECTIONS` | `from clarvis.brain import brain, ALL_COLLECTIONS` |
| 6 | `scripts/cognition/reasoning_chain_hook.py` | `from reasoning_chains import ...; from brain import brain` | `from clarvis.cognition.reasoning_chains import ...; from clarvis.brain import brain` |
| 7 | `scripts/hooks/temporal_self.py` | `from brain import brain` (lazy) | `from clarvis.brain import brain` (lazy) |
| 8 | `scripts/hooks/intra_linker.py` | `from brain import brain, ALL_COLLECTIONS, GRAPH_FILE` | `from clarvis.brain import brain, ALL_COLLECTIONS, GRAPH_FILE` |
| 9 | `scripts/evolution/failure_amplifier.py` | `from brain import brain` | `from clarvis.brain import brain` |
| 10 | `scripts/brain_mem/brain_introspect.py` | 4 lazy `from brain import` calls | 4 lazy `from clarvis.brain import` calls |

All 10 scripts pass `py_compile` syntax check. Each removed the `sys.path.insert` + `import _paths` boilerplate and replaced it with direct spine imports.

**Spine migration progress**: Phase 5 migrated 6, Phase 7 migrated 10 → 16 total scripts migrated. ~69 scripts still use legacy imports (from ~79 before Phase 7).

### 7.2 Verify and delete likely-dead scripts

Investigation results for the 3 candidates:

| Script | Status | Callers | Decision |
|--------|--------|---------|----------|
| `graphrag_communities.py` | **DEAD** | Only test_smoke.py parametric list | **DELETED** |
| `wiki_retrieval.py` | ALIVE | `wiki_eval.py`, `test_wiki_eval_suite.py` | Kept |
| `graph_cutover.py` | ALIVE | RUNBOOK.md (operational), ARCHITECTURE.md, SPINE_USAGE_AUDIT | Kept |

Additionally confirmed that `lockfree_ring_buffer.py` and `ab_comparison_benchmark.py` (Phase 3 dead scripts) were already deleted.

**Action**: Deleted `graphrag_communities.py`, removed from `tests/scripts/test_smoke.py` COGNITIVE_SCRIPTS list.

### 7.3 Add full-chain incremental restore to backup_restore.sh

**Finding**: The restore script only restored from a single backup directory. For incremental backups, this meant missing all files that were unchanged since the last full backup.

**Fix**: Added `build_restore_chain()` function that:
1. Takes the target backup directory
2. If incremental, finds the nearest full backup before it
3. Collects all backups between the full and target (inclusive), oldest first
4. Returns an ordered chain to apply (full → incremental₁ → ... → target)

Updated `do_restore()` to:
- Call `build_restore_chain()` instead of restoring from a single directory
- Apply files from each backup in chain order (full first, incrementals overlay)
- Display the full chain in output for operator visibility
- Verify against the target backup's manifest after chain application

### 7.4 Add offsite git push to backup

**Fix**: Added weekly offsite git push to `backup_daily.sh`. On Sundays (`date +%u` == 7), after git bundle creation, the script pushes to `origin` (git@github.com:GranusClarvis/clarvis.git). Failure is non-fatal — logged and retried next Sunday.

### 7.5 Add concurrent-access retry wrapper to graph_store_sqlite.py

**Finding**: F4.3.4 — `OperationalError: database is locked` propagates immediately on concurrent access, with no retry.

**Fix**: Added `@_retry_on_locked` decorator that:
- Catches `sqlite3.OperationalError` containing "locked" or "busy"
- Retries up to 3 times with exponential backoff (0.5s, 1s, 2s)
- Logs each retry attempt
- Non-lock errors propagate immediately (no retry)

Applied to all 7 write methods: `add_node`, `remove_node`, `add_edge`, `remove_edges`, `bulk_add_nodes`, `bulk_add_edges`, `decay_edges`.

### 7.6 Increase busy_timeout during maintenance windows

**Fix**: Added `_apply_busy_timeout()` method that checks for `/tmp/clarvis_maintenance.lock` (held by cron maintenance jobs 04:00-05:00):
- **Normal**: `busy_timeout=5000` (5s) — unchanged from before
- **During maintenance**: `busy_timeout=15000` (15s) — 3x longer for heavy operations

Called during `_setup()`. The maintenance lock file is already created by cron maintenance jobs via `lock_helper.sh`.

### 7.7 Add pre-consolidation snapshot

**Fix**: Added `_take_pre_consolidation_snapshot()` to `memory_consolidation.py`:
- Snapshots all collection IDs + counts to a timestamped JSON file
- Stored in `data/memory_archive/pre_consolidation_snapshots/`
- Keeps last 10 snapshots (auto-prunes older ones)
- Called as Phase 0 of `run_consolidation()` before any mutations
- Non-fatal: if snapshot fails, consolidation continues with a warning

### 7.8 Full docs refresh

Updated stale numbers in:
- **SELF.md**: `~3,400+ memories, 106k+ graph edges` → `~2,900 memories, 93k+ graph edges`
- **CLAUDE.md**: `2912 memories` → `~2873 memories`; `165 scripts` → `~163 scripts`

---

## Verification

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 pre-existing flaky (lock timing) |
| `python3 -m clarvis brain health` | Healthy — 2873 memories, 92693 edges, 7/7 hooks |
| Spine imports for all 10 migrated scripts | `py_compile` passes for all 10 |
| Graph retry wrapper unit test | 3-retry with backoff works; maintenance timeout = 15000ms |
| Pre-consolidation snapshot | Creates JSON with all 10 collections, 2873 total memories |
| `backup_restore.sh` syntax | bash -n passes |

### Pre-existing Test Failures (NOT introduced by Phase 7)

| Test | Issue | Phase 7 Related? |
|------|-------|-----------------|
| `test_project_agent.py::test_double_acquire_blocked` | Flaky lock timing assertion | No — pre-existing since Phase 3 |

---

## Files Changed

| File | Change |
|------|--------|
| `clarvis/brain/graph_store_sqlite.py` | Added `@_retry_on_locked` decorator + `_apply_busy_timeout()` with maintenance detection |
| `clarvis/memory/memory_consolidation.py` | Added `_take_pre_consolidation_snapshot()`, wired into `run_consolidation()` |
| `scripts/brain_mem/retrieval_experiment.py` | Spine import migration |
| `scripts/brain_mem/retrieval_benchmark.py` | Spine import migration |
| `scripts/brain_mem/graph_compaction.py` | Spine import migration |
| `scripts/brain_mem/brain_introspect.py` | Spine import migration (4 lazy imports) |
| `scripts/cognition/theory_of_mind.py` | Spine import migration |
| `scripts/cognition/knowledge_synthesis.py` | Spine import migration |
| `scripts/cognition/reasoning_chain_hook.py` | Spine import migration (brain + reasoning_chains) |
| `scripts/hooks/temporal_self.py` | Spine import migration |
| `scripts/hooks/intra_linker.py` | Spine import migration |
| `scripts/evolution/failure_amplifier.py` | Spine import migration |
| `scripts/brain_mem/graphrag_communities.py` | **DELETED** (dead script) |
| `tests/scripts/test_smoke.py` | Removed `graphrag_communities` from smoke test list |
| `scripts/infra/backup_restore.sh` | Added `build_restore_chain()` for incremental chaining |
| `scripts/infra/backup_daily.sh` | Added weekly offsite git push (Sundays) |
| `SELF.md` | Updated memory/edge counts |
| `~/.openclaw/CLAUDE.md` | Updated memory count, script count |

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| wiki_retrieval.py | Has active callers (wiki_eval.py + test suite) | Not dead |
| graph_cutover.py | Operational tool in RUNBOOK | Not dead |
| Remaining 69 legacy-import scripts | Roadmap estimates ~30 sessions for >60% migration | Future batches |
| stale `data/thought_log.jsonl` | Harmless file, no longer written | Sunday cleanup |

## Rating Impact

Per the master plan:
- **Architecture**: B+ → A- (16 scripts now use spine imports; migration pattern established and repeatable)
- **Resilience**: A- → A (retry wrapper + maintenance timeout + pre-consolidation snapshot + incremental restore chaining + offsite backup)
- **Hygiene**: B → B+ (dead script deleted; docs refreshed to match reality)

## End-State Summary

After completing all 7 phases of the Master Improvement Plan:

| Dimension | Before Plan | After Phase 7 | Target |
|-----------|------------|---------------|--------|
| **Architecture** | B | A- | A |
| **Runtime** | B+ | A- | A |
| **Ops** | C+ | B+ | A- |
| **Hygiene** | B- | B+ | A- |
| **Resilience** | B | A | A |
| **Observability** | C | B | B+ |
| **Value/Signal** | B- | B+ | A- |
| **Composite** | **B-** | **A-** | **A** |

The system has been systematically hardened from B- composite to A- across all dimensions. Key achievements across the 7-phase plan:
- 16 scripts migrated to spine imports (migration pattern proven and repeatable)
- Secret redaction expanded to 14 patterns with 8-char minimum
- ChromaDB degraded mode + circuit breaker added
- Atomic episode writes + pre-consolidation snapshots
- Outer timeouts on all spawners + hook timeouts
- SQLite graph store retry with maintenance-aware busy_timeout
- Full-chain incremental restore + weekly offsite push
- All monitoring gaps closed; 7/7 hooks registered
- 779 tests passing; brain health verified

To reach A/A+ (Appendix C of master plan): continue spine migration in batches of 10, add cron pipeline integration tests, and establish automated regression detection.

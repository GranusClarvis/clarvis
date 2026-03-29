# Emergency Audit: System Degradation 2026-03-29

**Date**: 2026-03-29 ~21:30 UTC
**Auditor**: Claude Code Opus (emergency spawn)
**Severity**: Critical — full autonomous pipeline outage for ~22 hours

---

## Executive Summary

The entire Clarvis autonomous pipeline (heartbeats, cron spawns, commits, pushes) has been non-functional since approximately 2026-03-28 23:18 UTC. **Root cause: process/thread exhaustion** hitting the PAM-enforced `nproc` limit of 4096 for the `agent` user under cron.

At the time of audit, the system had **4108 threads** against a hard limit of 4096, causing every `fork()` call from cron jobs to fail with `Resource temporarily unavailable`.

---

## Why Claude Usage Dropped

**Confidence: 99%**

All Claude Code spawning goes through the heartbeat pipeline: `cron_autonomous.sh` → `heartbeat_preflight.py` → Claude Code → `heartbeat_postflight.py`. Every heartbeat attempt today failed at **preflight import** because:

1. NumPy/OpenBLAS attempts to spawn 16 threads on import
2. With the `agent` user at the 4096 nproc limit, `pthread_create` fails
3. This causes a `KeyboardInterrupt` during `numpy._core.multiarray` import
4. Preflight crashes with exit code 130 before any task selection occurs

**Evidence**:
- 9 heartbeat attempts today, 0 successful (autonomous.log)
- All 9 show identical OpenBLAS thread creation failure + numpy import crash
- Last successful heartbeat: 2026-03-28 23:00 (postflight failed at 23:17)
- Zero Claude Code completions today

---

## Why Commits/Pushes Stopped

**Confidence: 99%**

Commits and pushes are produced by Claude Code during heartbeat execution. Since no heartbeat completed successfully today, no code changes were made, and therefore no commits or pushes occurred.

**Last commit**: `6592207` at 2026-03-28 23:10 UTC (from the 23:00 heartbeat)

**Pre-existing uncommitted changes** (from yesterday's sessions) remain in the working tree:
- `clarvis/brain/search.py` — text fallback query fix
- `clarvis/metrics/quality.py` — function length threshold relaxed to 200
- `scripts/heartbeat_preflight.py` — dead code removal (routing, reasoning chain)
- `scripts/heartbeat_postflight.py`, `scripts/queue_writer.py` — various fixes
- `tests/test_clarvis_brain.py`, `tests/test_clarvis_metrics_quality.py` — new tests

These changes passed all 107 tests but were never committed because the postflight (which commits) failed at 23:17.

---

## What Broke Yesterday

**Confidence: 95%**

### Primary Cause: Thread/Process Accumulation

The nproc limit of 4096 was gradually consumed by **leaked processes** over the past 1-9 days:

| Process | Age | Threads | Description |
|---------|-----|---------|-------------|
| 20+ zombie `claude` + `claude-agent-acp` | 9 days | ~1060 | Orphaned OpenClaw gateway sessions from ~Mar 19-20 |
| 3 zombie `claude` processes | 5 days | ~100 | Orphaned sessions from ~Mar 24 |
| `claude login` | 3 days | ~30 | Stuck interactive command |
| `claude doctor` | 3 days | ~30 | Stuck interactive command |
| `cron_reflection.sh` → `memory_consolidation.py` | 24h | 71 | Hung consolidation step |
| 2 stuck `pytest` processes | 24h+ | ~500 | Spawned by previous Claude session |
| `performance_benchmark.py` | 21h | ~30 | Stuck quick benchmark |

**Total leaked threads**: ~1820+ (against a 4096 limit with ~2000 used by legitimate processes)

### Why the Reflection Script Got Stuck

`cron_reflection.sh` started at 2026-03-28 21:00. Step 4 (`memory_consolidation.py consolidate`) hung indefinitely. The script had:
- **No timeout** (`set_script_timeout` was not called)
- **No stale threshold** on its lock (`acquire_local_lock` called without 3rd arg)
- **No per-step timeout** (each step runs via `run_step` which has no timeout)

Additionally, step 3.7 (`semantic_bridge_builder.py`) was referencing a **non-existent file** (deleted/never created), but this only logged a warning and didn't cause the hang.

### The Tipping Point

The thread count crossed 4096 between 23:00 and 23:17 on Mar 28. The 23:00 heartbeat's preflight succeeded, but its postflight failed (fork exhaustion had begun). From 01:00 Mar 29 onward, every cron job's `cron_env.sh` sourcing failed with `fork: Resource temporarily unavailable`.

---

## What Was Fixed

### Immediate Fixes (applied this session)

1. **Killed 100+ zombie processes** — thread count dropped from 4108 → 445
   - 20+ nine-day-old orphaned claude-agent-acp/claude sessions
   - Stuck reflection + memory_consolidation (24h)
   - Stuck pytest processes (24h+)
   - Stuck claude login/doctor (3 days)
   - Stuck performance_benchmark (21h)

2. **Removed stale reflection lock** (`/tmp/clarvis_reflection.lock`)

3. **Added timeout + stale threshold to `cron_reflection.sh`**
   - `acquire_local_lock` now uses 7200s (2h) stale threshold
   - `set_script_timeout 3600` (1h) watchdog armed
   - No more indefinite hangs possible

4. **Commented out missing `semantic_bridge_builder.py` call** in reflection pipeline

5. **Added `OPENBLAS_NUM_THREADS=4` and `OMP_NUM_THREADS=4` to `cron_env.sh`**
   - Prevents NumPy from spawning 16 threads per import
   - Reduces per-process thread footprint by 4x
   - Critical for staying under the 4096 nproc limit

6. **Added stale thresholds to 8 other cron scripts** (via background agent):
   - `cron_evening.sh`, `cron_evolution.sh`, `cron_morning.sh`, `cron_orchestrator.sh` (3600s)
   - `cron_chromadb_vacuum.sh`, `cron_graph_compaction.sh` (1800s)
   - `cron_monthly_reflection.sh` (7200s)
   - `cron_strategic_audit.sh` (3600s)

### Verification

- Brain imports work: OK
- NumPy under OPENBLAS_NUM_THREADS=4: OK
- All 107 tests pass
- Thread count: 445 (well under 4096)
- No stale locks remaining
- Gateway service: running normally

---

## What Is Still Broken / At Risk

### Needs Attention

1. **PAM nproc limit is 4096** (`/etc/security/limits.d/agent.conf`). This is dangerously low for a system running 20+ cron jobs, a gateway with multiple claude sessions, and a headless Chromium. **Recommendation**: Raise to 16384 or 32768 (requires root/sudo).

2. **OpenClaw gateway leaks claude-agent-acp sessions**. The 20+ zombie sessions from 9 days ago indicate the gateway doesn't reliably clean up child processes. This is an upstream issue. **Mitigation**: Add a daily cron job to kill claude/claude-agent-acp processes older than 48h.

3. **No per-step timeout in reflection pipeline**. Individual steps like `memory_consolidation.py` can still hang. The script-level timeout (1h) will catch this, but 1h is still a long time. Consider adding `timeout 300` to each `run_step` invocation.

4. **Uncommitted changes from yesterday** are still in the working tree. They should be committed (all tests pass).

5. **`semantic_bridge_builder.py` is missing**. Either it was never created, was deleted, or was renamed. The reflection pipeline now skips this step.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| ~Mar 19-20 | 20+ claude-agent-acp sessions leak from gateway |
| ~Mar 24 | 3 more claude sessions leak |
| ~Mar 26 | `claude login` and `claude doctor` start and never terminate |
| Mar 28 21:00 | `cron_reflection.sh` starts, gets stuck at step 4 (memory_consolidation) |
| Mar 28 22:00-23:00 | Last two successful heartbeat preflights |
| Mar 28 23:17 | Postflight fails — thread count crosses 4096 |
| Mar 29 01:00+ | All cron jobs fail: `fork: Resource temporarily unavailable` |
| Mar 29 06:00-20:00 | 9 heartbeat attempts, all fail at numpy import |
| Mar 29 21:00 | Today's reflection skipped (lock still held by yesterday's PID) |
| Mar 29 21:27 | This audit session begins |
| Mar 29 21:30 | Zombie processes killed, thread count drops 4108→445 |
| Mar 29 21:35 | Fixes applied, system verified operational |

---

## Root Cause Summary

**Process leak + missing safeguards + low nproc limit** combined to create a cascading failure:

1. Gateway leaked ~1060 threads over 9 days (no cleanup mechanism)
2. Reflection script hung with no timeout or stale detection (24h)
3. Additional stuck processes (pytest, benchmark, claude login/doctor) consumed remaining headroom
4. Total threads exceeded PAM nproc limit of 4096
5. All cron fork() calls failed → no heartbeats → no Claude usage → no commits/pushes

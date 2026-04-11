# Phase 6 Execution Report: Observability & Recovery Completeness

**Date**: 2026-04-09
**Executor**: Claude Code Opus (executive function)
**Source**: MASTER_IMPROVEMENT_PLAN.md, Phase 6

---

## Phase 5 Verification (Pre-Execution)

Before executing Phase 6, verified all Phase 5 claims against the codebase:

| Phase 5 Claim | Verified |
|---|---|
| daily_memory_log.py uses `from clarvis.brain import brain` | Yes |
| digest_writer.py already pure stdlib (no migration needed) | Yes |
| performance_benchmark.py uses spine imports (6 replacements) | Yes |
| session_hook.py uses spine imports with targeted theory_of_mind path | Yes |
| absolute_zero.py uses spine brain + episodic imports | Yes |
| brain.py shim retained (intentional, ~50 callers) | Yes |
| No bridge stubs found for migrated scripts | Yes |

**Verdict**: All Phase 5 functionality confirmed in place. No carry-over needed.

---

## Changes Made

### 6.1 Add set_script_timeout to all major spawners

**Finding**: F4.1.8 — No outer timeout on spawners. Claude gets a subprocess timeout via `run_claude_monitored`, but the script itself could hang during preflight, postflight, or lock acquisition with no kill mechanism.

**Fix**: Added `set_script_timeout` (from lock_helper.sh) to all 5 major spawner scripts, placed after LOGFILE definition and before lock acquisition:

| Script | Timeout | Rationale |
|--------|---------|-----------|
| `cron_autonomous.sh` | 2400s (40 min) | Claude gets 1200s + preflight/postflight overhead |
| `cron_morning.sh` | 1800s (30 min) | Claude gets 1200s + session_hook + daily bootstrap |
| `cron_evolution.sh` | 2400s (40 min) | Claude gets 1200s + heavy preflight metrics collection |
| `cron_research.sh` | 2700s (45 min) | Claude gets 1800s + task selection/discovery |
| `cron_implementation_sprint.sh` | 2400s (40 min) | Claude gets 1500s + preflight/postflight |

All scripts already source `lock_helper.sh` which defines `set_script_timeout()`. The watchdog fires a background `sleep $seconds && kill` that triggers the EXIT trap, which calls `_lock_helper_cleanup` to release all locks.

### 6.2 Fix watchdog post-recovery recheck (sleep 2 -> 30)

**Finding**: F4.1.10 — After cron_doctor runs recovery actions, the watchdog rechecks health after only 2 seconds. Most recovered services (especially Claude Code spawners) need 10-30s to produce output.

**Fix**: Changed `sleep 2` to `sleep 30` in `cron_watchdog.sh` line 203. This gives recovered services adequate startup time before the recheck declares them still-failing and sends a Telegram alert.

### 6.3 Add dream_engine to watchdog+doctor — ALREADY DONE

**Finding**: F4.1.3 — Dream engine failures not detected or recoverable.

**Assessment**: Verified that dream_engine is already present in both:
- **Watchdog**: `dream_engine` -> `memory/cron/dream.log`, max_age 26h
- **Doctor**: `dream_engine` with command `dream_engine.py dream`, log `memory/cron/dream.log`, timeout 900s

This was completed in a prior phase. No changes needed.

### 6.4 Fix cron_report PID locks with /proc/cmdline guard

**Finding**: F4.1.9 — Report scripts use `kill -0 $pid` to check if the lock-holding process is alive, but this doesn't guard against PID recycling. If the original process dies and a new unrelated process gets the same PID, the lock is incorrectly considered valid.

**Fix**: Added `/proc/$pid/cmdline` verification to both `cron_report_morning.sh` and `cron_report_evening.sh`. After `kill -0` confirms the PID exists, the script now reads `/proc/$pid/cmdline` and checks for `cron_report` in the command line. If the PID is alive but belongs to a different process, the lock is reclaimed with a log message.

**Files changed**: `cron_report_morning.sh`, `cron_report_evening.sh`

### 6.5 Reduce redaction min-length (20 -> 8) for password/key patterns

**Finding**: F4.2.5-7 — Redaction patterns require 20+ character values. Short real secrets (e.g., `password = abc12345`) pass through undetected.

**Fix**: Reduced minimum length from `{20,}` to `{8,}` for:
- `generic_api_key` pattern (catches `password=`, `secret=`, `api_key=`, `token=` assignments)
- `bearer_token` pattern

**Reordered patterns**: Moved specific patterns (AWS, OpenAI, Stripe, Slack, GitHub, Telegram, JWT) before the generic catch-all to prevent the generic pattern from consuming text that specific patterns should match. This is critical because `redact_secrets()` processes patterns sequentially and replaces text in-place.

**False-positive check**: Verified that common sentences like "The password field should use encryption" are NOT flagged (the pattern requires `=` or `:` followed by a value).

### 6.6 Add Stripe/Slack/JWT patterns to redaction

**Finding**: F4.2.8 — Stripe, Slack, and JWT token patterns not matched.

**Fix**: Added 3 new patterns to `secret_redaction.py`:

| Pattern | Regex | Example |
|---------|-------|---------|
| `stripe_key` | `(?:sk\|rk)_(?:live\|test)_[A-Za-z0-9]{10,}` | `sk_live_1234567890abcdef` |
| `slack_token` | `xox[bpas]-[A-Za-z0-9-]{10,}` | `xoxb-123456789-abcdefghij` |
| `jwt_token` | `eyJ..\.eyJ..\.[A-Za-z0-9_-]{10,}` | Three-part base64-encoded JWT |

Total patterns: 14 (up from 11).

### 6.7 Remove decorative thought_log.jsonl disk logging

**Finding**: F3.1b — Thought Protocol writes to `data/thought_log.jsonl` on every frame evaluation, but no downstream consumer reads this file. The second-pass validation confirmed: "Calls are real; logged output is decorative."

**Fix**: Removed the disk write from `ThoughtProtocol._log_frame()`. The in-memory `frame_history` (last 50 frames) is preserved — it's consumed by `get_recent_thoughts()` and `thought_stats()`. Specifically:
- Removed `THOUGHT_LOG` path constant and `mkdir` at module level
- Removed `open(THOUGHT_LOG, "a")` write in `_log_frame()`
- Removed disk-loading fallback in `thought_stats()` 
- Updated cleanup_policy.py to note the file is no longer written
- Updated 2 tests in `test_clarvis_cognition.py` (disk write -> memory check, disk stats -> memory stats)

### 6.8 Use UTC for daily task cap boundary — ALREADY DONE

**Finding**: F3.7c — Midnight race condition if local time used for daily cap.

**Assessment**: Verified that `clarvis/queue/writer.py` exclusively uses `datetime.now(timezone.utc)` for all date operations. Zero bare `datetime.now()` or `.today()` calls found. No changes needed.

---

## Verification

| Check | Result |
|-------|--------|
| `python3 -m pytest tests/ -x -q` | 779 passed, 1 pre-existing flaky (lock timing) |
| `python3 -m clarvis brain health` | Healthy — 2872 memories, 92693 edges, 7/7 hooks |
| Secret redaction: short password | Caught (generic_api_key) |
| Secret redaction: Stripe key | Caught (stripe_key) |
| Secret redaction: Slack token | Caught (slack_token) |
| Secret redaction: JWT | Caught (jwt_token) |
| Secret redaction: false positives | 0 on common sentences |
| Secret redaction test suite | 15/15 passed |
| Thought protocol tests | All pass (updated for memory-only logging) |
| Bash syntax check: spawner scripts | All 5 source lock_helper.sh successfully |

### Pre-existing Test Failures (NOT introduced by Phase 6)

| Test | Issue | Phase 6 Related? |
|------|-------|-----------------|
| `test_project_agent.py::test_double_acquire_blocked` | Flaky lock timing assertion | No — pre-existing since Phase 3 |

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/cron/cron_autonomous.sh` | Added `set_script_timeout 2400` |
| `scripts/cron/cron_morning.sh` | Added `set_script_timeout 1800` |
| `scripts/cron/cron_evolution.sh` | Added `set_script_timeout 2400` |
| `scripts/cron/cron_research.sh` | Added `set_script_timeout 2700` |
| `scripts/cron/cron_implementation_sprint.sh` | Added `set_script_timeout 2400` |
| `scripts/cron/cron_watchdog.sh` | Changed post-recovery recheck sleep 2 -> 30 |
| `scripts/cron/cron_report_morning.sh` | Added /proc/cmdline PID recycling guard |
| `scripts/cron/cron_report_evening.sh` | Added /proc/cmdline PID recycling guard |
| `clarvis/brain/secret_redaction.py` | Reduced min-length 20->8, added 3 patterns, reordered |
| `clarvis/cognition/thought_protocol.py` | Removed decorative disk logging |
| `scripts/infra/cleanup_policy.py` | Removed thought_log.jsonl trim entry |
| `tests/test_clarvis_cognition.py` | Updated thought logging tests for memory-only |

## What Remains

| Item | Why Not Done | Where |
|------|-------------|-------|
| Delete stale `data/thought_log.jsonl` | File may still exist on disk; harmless, no longer written to | Manual cleanup or Sunday cron_cleanup |

## Rating Impact

Per the master plan:
- **Ops**: B -> B+ (outer timeouts close the runaway-script gap; recheck timing fixed)
- **Observability**: C+ -> B (all monitoring gaps closed; PID locks hardened)
- **Resilience**: +0.3 (redaction now catches short secrets + 3 new token types)
- **Value**: +0.1 (thought_log.jsonl no longer wastefully written)
